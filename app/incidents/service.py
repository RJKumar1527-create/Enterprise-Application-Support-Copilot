import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATABASE_PATH = (
    PROJECT_ROOT
    / "data"
    / "opsresolve.db"
)


VALID_PRIORITIES = {
    "Low",
    "Medium",
    "High",
    "Critical",
}

VALID_STATUSES = {
    "Open",
    "Investigating",
    "Awaiting Information",
    "Resolved",
    "Closed",
}


def utc_timestamp():
    return datetime.now(
        timezone.utc
    ).isoformat()


def get_connection():
    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = sqlite3.Row

    return connection


def initialise_incidents():
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                incident_id INTEGER
                    PRIMARY KEY AUTOINCREMENT,
                incident_reference TEXT UNIQUE,
                title TEXT NOT NULL,
                issue_description TEXT NOT NULL,
                application_area TEXT NOT NULL,
                current_status TEXT,
                attempted_action TEXT,
                visible_error TEXT,
                operational_reference TEXT,
                identified_root_cause TEXT,
                steps_attempted TEXT,
                business_impact TEXT,
                priority TEXT NOT NULL,
                contact_reference TEXT,
                incident_status TEXT NOT NULL,
                resolution_notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS
            self_service_resolutions (
                resolution_id INTEGER
                    PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                application_area TEXT,
                root_cause TEXT,
                resolution_steps_json TEXT NOT NULL,
                evidence_ids_json TEXT NOT NULL,
                user_feedback TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_incident_status
            ON incidents(incident_status);

            CREATE INDEX IF NOT EXISTS
            idx_incident_updated
            ON incidents(updated_at);
            """
        )


def raise_incident(payload):
    priority = payload.get(
        "priority",
        "Medium",
    )

    if priority not in VALID_PRIORITIES:
        raise ValueError(
            "Invalid incident priority."
        )

    title = str(
        payload.get("title", "")
    ).strip()

    issue = str(
        payload.get(
            "issue_description",
            "",
        )
    ).strip()

    if not title or not issue:
        raise ValueError(
            "Incident title and issue "
            "description are required."
        )

    timestamp = utc_timestamp()

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO incidents (
                incident_reference,
                title,
                issue_description,
                application_area,
                current_status,
                attempted_action,
                visible_error,
                operational_reference,
                identified_root_cause,
                steps_attempted,
                business_impact,
                priority,
                contact_reference,
                incident_status,
                resolution_notes,
                created_at,
                updated_at
            )
            VALUES (
                NULL, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, 'Open', '', ?, ?
            )
            """,
            (
                title,
                issue,
                payload.get(
                    "application_area",
                    "general",
                ),
                payload.get(
                    "current_status",
                    "",
                ),
                payload.get(
                    "attempted_action",
                    "",
                ),
                payload.get(
                    "visible_error",
                    "",
                ),
                payload.get(
                    "operational_reference",
                    "",
                ),
                payload.get(
                    "identified_root_cause",
                    "",
                ),
                payload.get(
                    "steps_attempted",
                    "",
                ),
                payload.get(
                    "business_impact",
                    "",
                ),
                priority,
                payload.get(
                    "contact_reference",
                    "",
                ),
                timestamp,
                timestamp,
            ),
        )

        incident_id = cursor.lastrowid

        incident_reference = (
            f"INC-{datetime.now().year}-"
            f"{incident_id:05d}"
        )

        connection.execute(
            """
            UPDATE incidents
            SET incident_reference = ?
            WHERE incident_id = ?
            """,
            (
                incident_reference,
                incident_id,
            ),
        )

    return get_incident(incident_id)


def get_incident(incident_id):
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM incidents
            WHERE incident_id = ?
            """,
            (incident_id,),
        ).fetchone()

    return dict(row) if row else None


def list_incidents():
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM incidents
            ORDER BY updated_at DESC
            """
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def update_incident(
    incident_id,
    incident_status,
    identified_root_cause,
    resolution_notes,
):
    if incident_status not in VALID_STATUSES:
        raise ValueError(
            "Invalid incident status."
        )

    if (
        incident_status
        in {"Resolved", "Closed"}
        and not str(
            identified_root_cause or ""
        ).strip()
    ):
        raise ValueError(
            "Root cause is required before "
            "resolving an incident."
        )

    if (
        incident_status
        in {"Resolved", "Closed"}
        and not str(
            resolution_notes or ""
        ).strip()
    ):
        raise ValueError(
            "Resolution notes are required "
            "before resolving an incident."
        )

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE incidents
            SET
                incident_status = ?,
                identified_root_cause = ?,
                resolution_notes = ?,
                updated_at = ?
            WHERE incident_id = ?
            """,
            (
                incident_status,
                str(
                    identified_root_cause
                    or ""
                ).strip(),
                str(
                    resolution_notes
                    or ""
                ).strip(),
                utc_timestamp(),
                incident_id,
            ),
        )

    return get_incident(incident_id)


def save_self_service_resolution(
    question,
    application_area,
    root_cause,
    resolution_steps,
    evidence_ids,
):
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO self_service_resolutions (
                question,
                application_area,
                root_cause,
                resolution_steps_json,
                evidence_ids_json,
                user_feedback,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, 'RESOLVED', ?)
            """,
            (
                question,
                application_area,
                root_cause,
                json.dumps(
                    resolution_steps
                ),
                json.dumps(
                    evidence_ids
                ),
                utc_timestamp(),
            ),
        )


initialise_incidents()
