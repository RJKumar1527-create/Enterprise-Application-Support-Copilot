import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

MEMORY_DATABASE_PATH = (
    PROJECT_ROOT
    / "data"
    / "copilot_memory.db"
)


def utc_timestamp():
    return datetime.now(
        timezone.utc
    ).isoformat()


def get_connection():
    MEMORY_DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        MEMORY_DATABASE_PATH
    )

    connection.row_factory = sqlite3.Row

    return connection


def initialise_memory():
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                conversation_id TEXT PRIMARY KEY,
                application_area TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS conversation_messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(conversation_id)
                    REFERENCES conversations(conversation_id)
            );

            CREATE TABLE IF NOT EXISTS investigation_memory (
                memory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER,
                conversation_id TEXT,
                issue_summary TEXT NOT NULL,
                confirmed_root_cause TEXT,
                resolution_summary TEXT,
                evidence_ids_json TEXT NOT NULL,
                validation_status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_messages_conversation
            ON conversation_messages(
                conversation_id
            );

            CREATE INDEX IF NOT EXISTS
            idx_memory_case
            ON investigation_memory(
                case_id
            );
            """
        )


def ensure_conversation(
    conversation_id,
    application_area,
):
    timestamp = utc_timestamp()

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO conversations (
                conversation_id,
                application_area,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(conversation_id)
            DO UPDATE SET
                application_area =
                    excluded.application_area,
                updated_at =
                    excluded.updated_at
            """,
            (
                conversation_id,
                application_area,
                timestamp,
                timestamp,
            ),
        )


def add_message(
    conversation_id,
    role,
    content,
    metadata=None,
):
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO conversation_messages (
                conversation_id,
                role,
                content,
                metadata_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                conversation_id,
                role,
                content,
                json.dumps(
                    metadata or {}
                ),
                utc_timestamp(),
            ),
        )

        connection.execute(
            """
            UPDATE conversations
            SET updated_at = ?
            WHERE conversation_id = ?
            """,
            (
                utc_timestamp(),
                conversation_id,
            ),
        )


def get_recent_messages(
    conversation_id,
    limit=6,
):
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                role,
                content,
                metadata_json,
                created_at
            FROM conversation_messages
            WHERE conversation_id = ?
            ORDER BY message_id DESC
            LIMIT ?
            """,
            (
                conversation_id,
                limit,
            ),
        ).fetchall()

    messages = []

    for row in reversed(rows):
        item = dict(row)

        item["metadata"] = json.loads(
            item.pop(
                "metadata_json"
            )
            or "{}"
        )

        messages.append(item)

    return messages


def save_investigation_memory(
    issue_summary,
    evidence_ids,
    conversation_id=None,
    case_id=None,
    confirmed_root_cause=None,
    resolution_summary=None,
    validation_status="AI_GENERATED",
):
    timestamp = utc_timestamp()

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO investigation_memory (
                case_id,
                conversation_id,
                issue_summary,
                confirmed_root_cause,
                resolution_summary,
                evidence_ids_json,
                validation_status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_id,
                conversation_id,
                issue_summary,
                confirmed_root_cause,
                resolution_summary,
                json.dumps(
                    evidence_ids
                ),
                validation_status,
                timestamp,
                timestamp,
            ),
        )

        return cursor.lastrowid


def get_similar_validated_memories(
    query,
    limit=3,
):
    query_terms = {
        term.lower()
        for term in query.split()
        if len(term) >= 4
    }

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM investigation_memory
            WHERE validation_status IN (
                'HUMAN_VALIDATED',
                'RESOLVED'
            )
            ORDER BY updated_at DESC
            LIMIT 100
            """
        ).fetchall()

    scored = []

    for row in rows:
        result = dict(row)

        searchable = " ".join(
            [
                str(
                    result.get(
                        "issue_summary",
                        "",
                    )
                ),
                str(
                    result.get(
                        "confirmed_root_cause",
                        "",
                    )
                ),
                str(
                    result.get(
                        "resolution_summary",
                        "",
                    )
                ),
            ]
        ).lower()

        matched_terms = sum(
            term in searchable
            for term in query_terms
        )

        if matched_terms == 0:
            continue

        result["similarity_score"] = round(
            matched_terms
            / max(
                len(query_terms),
                1,
            ),
            4,
        )

        result["evidence_ids"] = json.loads(
            result.pop(
                "evidence_ids_json"
            )
            or "[]"
        )

        scored.append(result)

    scored.sort(
        key=lambda item: item[
            "similarity_score"
        ],
        reverse=True,
    )

    return scored[:limit]


initialise_memory()
