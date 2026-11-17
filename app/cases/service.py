import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.memory.case_memory import (
    save_investigation_memory,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

CASE_DATABASE_PATH = (
    PROJECT_ROOT
    / "data"
    / "support_cases.db"
)


VALID_CASE_STATUSES = {
    "OPEN",
    "INVESTIGATING",
    "AWAITING INFORMATION",
    "RESOLVED",
    "CLOSED",
}

VALID_CHECK_STATUSES = {
    "PENDING",
    "COMPLETED",
    "NOT APPLICABLE",
}


def utc_timestamp():
    return datetime.now(
        timezone.utc
    ).isoformat()


def get_connection():
    CASE_DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        CASE_DATABASE_PATH
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


def initialise_case_management():
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS case_checklist (
                checklist_id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                sequence_number INTEGER NOT NULL,
                check_text TEXT NOT NULL,
                check_status TEXT NOT NULL DEFAULT 'PENDING',
                finding TEXT,
                completed_by TEXT,
                completed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS case_findings (
                finding_id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                finding_type TEXT NOT NULL,
                finding_text TEXT NOT NULL,
                evidence_reference TEXT,
                recorded_by TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS case_resolution_history (
                resolution_id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                previous_status TEXT,
                new_status TEXT NOT NULL,
                assigned_owner TEXT,
                confirmed_root_cause TEXT,
                resolution_notes TEXT,
                updated_by TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_case_checklist_case
            ON case_checklist(case_id);

            CREATE INDEX IF NOT EXISTS
            idx_case_findings_case
            ON case_findings(case_id);

            CREATE INDEX IF NOT EXISTS
            idx_case_resolution_case
            ON case_resolution_history(case_id);
            """
        )


def get_case(case_id):
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM support_cases
            WHERE case_id = ?
            """,
            (case_id,),
        ).fetchone()

    if row is None:
        return None

    case_record = dict(row)

    for field in [
        "probable_causes_json",
        "recommended_checks_json",
        "citations_json",
    ]:
        output_field = field.replace(
            "_json",
            "",
        )

        case_record[output_field] = json.loads(
            case_record.get(field)
            or "[]"
        )

        case_record.pop(
            field,
            None,
        )

    return case_record


def ensure_case_checklist(case_id):
    case_record = get_case(case_id)

    if case_record is None:
        raise ValueError(
            f"Support case {case_id} was not found."
        )

    with get_connection() as connection:
        existing_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM case_checklist
            WHERE case_id = ?
            """,
            (case_id,),
        ).fetchone()[0]

        if existing_count:
            return

        timestamp = utc_timestamp()

        for sequence, check_text in enumerate(
            case_record.get(
                "recommended_checks",
                [],
            ),
            start=1,
        ):
            connection.execute(
                """
                INSERT INTO case_checklist (
                    case_id,
                    sequence_number,
                    check_text,
                    check_status,
                    finding,
                    completed_by,
                    completed_at,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, 'PENDING', '', '', NULL, ?, ?)
                """,
                (
                    case_id,
                    sequence,
                    check_text,
                    timestamp,
                    timestamp,
                ),
            )


def get_case_workspace(case_id):
    ensure_case_checklist(case_id)

    case_record = get_case(case_id)

    with get_connection() as connection:
        checklist_rows = connection.execute(
            """
            SELECT *
            FROM case_checklist
            WHERE case_id = ?
            ORDER BY sequence_number
            """,
            (case_id,),
        ).fetchall()

        finding_rows = connection.execute(
            """
            SELECT *
            FROM case_findings
            WHERE case_id = ?
            ORDER BY finding_id DESC
            """,
            (case_id,),
        ).fetchall()

        resolution_rows = connection.execute(
            """
            SELECT *
            FROM case_resolution_history
            WHERE case_id = ?
            ORDER BY resolution_id DESC
            """,
            (case_id,),
        ).fetchall()

    checklist = [
        dict(row)
        for row in checklist_rows
    ]

    completed_count = sum(
        row["check_status"]
        in {
            "COMPLETED",
            "NOT APPLICABLE",
        }
        for row in checklist
    )

    progress_percent = round(
        (
            completed_count
            / len(checklist)
            * 100
        )
        if checklist
        else 0,
        2,
    )

    return {
        "case": case_record,
        "checklist": checklist,
        "findings": [
            dict(row)
            for row in finding_rows
        ],
        "resolution_history": [
            dict(row)
            for row in resolution_rows
        ],
        "progress": {
            "total_checks": len(checklist),
            "completed_checks": completed_count,
            "progress_percent": progress_percent,
        },
    }


def update_checklist_item(
    case_id,
    checklist_id,
    check_status,
    finding,
    completed_by,
):
    if check_status not in VALID_CHECK_STATUSES:
        raise ValueError(
            "Invalid checklist status."
        )

    timestamp = utc_timestamp()

    completed_at = (
        timestamp
        if check_status
        in {
            "COMPLETED",
            "NOT APPLICABLE",
        }
        else None
    )

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE case_checklist
            SET
                check_status = ?,
                finding = ?,
                completed_by = ?,
                completed_at = ?,
                updated_at = ?
            WHERE
                case_id = ?
                AND checklist_id = ?
            """,
            (
                check_status,
                str(finding or "").strip(),
                str(completed_by or "").strip(),
                completed_at,
                timestamp,
                case_id,
                checklist_id,
            ),
        )

        if cursor.rowcount == 0:
            raise ValueError(
                "Checklist item was not found."
            )

    return get_case_workspace(case_id)


def add_case_finding(
    case_id,
    finding_type,
    finding_text,
    evidence_reference,
    recorded_by,
):
    if not str(finding_text or "").strip():
        raise ValueError(
            "Finding text is required."
        )

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO case_findings (
                case_id,
                finding_type,
                finding_text,
                evidence_reference,
                recorded_by,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                case_id,
                str(finding_type or "GENERAL"),
                str(finding_text).strip(),
                str(
                    evidence_reference
                    or ""
                ).strip(),
                str(
                    recorded_by
                    or "Support Engineer"
                ).strip(),
                utc_timestamp(),
            ),
        )

    return get_case_workspace(case_id)


def update_case_resolution(
    case_id,
    case_status,
    assigned_owner,
    confirmed_root_cause,
    resolution_notes,
    updated_by,
):
    if case_status not in VALID_CASE_STATUSES:
        raise ValueError(
            "Invalid case status."
        )

    case_record = get_case(case_id)

    if case_record is None:
        raise ValueError(
            "Support case was not found."
        )

    workspace = get_case_workspace(
        case_id
    )

    if (
        case_status in {
            "RESOLVED",
            "CLOSED",
        }
        and workspace["progress"][
            "progress_percent"
        ]
        < 100
    ):
        raise ValueError(
            "All diagnostic checks must be completed "
            "or marked Not Applicable before resolving "
            "the case."
        )

    if (
        case_status in {
            "RESOLVED",
            "CLOSED",
        }
        and not str(
            confirmed_root_cause
            or ""
        ).strip()
    ):
        raise ValueError(
            "Confirmed root cause is required "
            "before resolving the case."
        )

    if (
        case_status in {
            "RESOLVED",
            "CLOSED",
        }
        and not str(
            resolution_notes
            or ""
        ).strip()
    ):
        raise ValueError(
            "Resolution notes are required "
            "before resolving the case."
        )

    previous_status = case_record.get(
        "case_status",
        "OPEN",
    )

    timestamp = utc_timestamp()

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE support_cases
            SET
                assigned_owner = ?,
                case_status = ?,
                resolution_notes = ?,
                updated_at = ?
            WHERE case_id = ?
            """,
            (
                str(
                    assigned_owner
                    or "Application Support"
                ).strip(),
                case_status,
                str(
                    resolution_notes
                    or ""
                ).strip(),
                timestamp,
                case_id,
            ),
        )

        connection.execute(
            """
            INSERT INTO case_resolution_history (
                case_id,
                previous_status,
                new_status,
                assigned_owner,
                confirmed_root_cause,
                resolution_notes,
                updated_by,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_id,
                previous_status,
                case_status,
                str(
                    assigned_owner
                    or ""
                ).strip(),
                str(
                    confirmed_root_cause
                    or ""
                ).strip(),
                str(
                    resolution_notes
                    or ""
                ).strip(),
                str(
                    updated_by
                    or "Support Engineer"
                ).strip(),
                timestamp,
            ),
        )

    if case_status in {
        "RESOLVED",
        "CLOSED",
    }:
        save_investigation_memory(
            case_id=case_id,
            conversation_id=None,
            issue_summary=case_record[
                "issue_description"
            ],
            confirmed_root_cause=str(
                confirmed_root_cause
            ).strip(),
            resolution_summary=str(
                resolution_notes
            ).strip(),
            evidence_ids=case_record.get(
                "citations",
                [],
            ),
            validation_status="RESOLVED",
        )

    return get_case_workspace(case_id)


initialise_case_management()
