import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.database.repository import (
    ims_database_repository,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

CHUNKS_PATH = (
    PROJECT_ROOT
    / "data"
    / "chunks.json"
)

INCIDENT_DATABASE_PATH = (
    PROJECT_ROOT
    / "data"
    / "opsresolve.db"
)


def utc_timestamp():
    return datetime.now(
        timezone.utc
    ).isoformat()


def check_knowledge_base():
    if not CHUNKS_PATH.exists():
        return {
            "healthy": False,
            "document_count": 0,
            "reason": "Knowledge chunks are unavailable.",
        }

    try:
        chunks = json.loads(
            CHUNKS_PATH.read_text(
                encoding="utf-8"
            )
        )

        return {
            "healthy": bool(chunks),
            "document_count": len(
                {
                    chunk.get("document_id")
                    for chunk in chunks
                }
            ),
            "chunk_count": len(chunks),
        }

    except Exception as error:
        return {
            "healthy": False,
            "document_count": 0,
            "reason": str(error),
        }


def check_incident_store():
    try:
        with sqlite3.connect(
            INCIDENT_DATABASE_PATH
        ) as connection:
            connection.execute(
                "SELECT 1"
            ).fetchone()

        return {
            "healthy": True,
            "database": "SQLite",
        }

    except Exception as error:
        return {
            "healthy": False,
            "database": "SQLite",
            "reason": str(error),
        }


def get_health_status():
    return {
        "status": "UP",
        "application": "OpsResolve AI",
        "timestamp": utc_timestamp(),
    }


def get_readiness_status():
    knowledge = check_knowledge_base()

    incident_store = (
        check_incident_store()
    )

    database_enabled = (
        ims_database_repository
        .settings.enabled
    )

    ready = (
        knowledge["healthy"]
        and incident_store["healthy"]
    )

    return {
        "status": (
            "READY"
            if ready
            else "NOT_READY"
        ),
        "application": "OpsResolve AI",
        "timestamp": utc_timestamp(),
        "components": {
            "knowledge_base": knowledge,
            "incident_store": (
                incident_store
            ),
            "ims_dpt1": {
                "enabled": database_enabled,
                "mode": "READ_ONLY",
                "required_for_startup": False,
            },
        },
    }
