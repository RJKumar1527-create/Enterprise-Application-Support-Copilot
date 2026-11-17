import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

OPERATIONS_DATABASE_PATH = (
    PROJECT_ROOT
    / "data"
    / "operations.db"
)


def utc_timestamp():
    return datetime.now(
        timezone.utc
    ).isoformat()


def get_connection():
    OPERATIONS_DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        OPERATIONS_DATABASE_PATH
    )

    connection.row_factory = sqlite3.Row

    return connection


def initialise_operations():
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS query_cache (
                cache_key TEXT PRIMARY KEY,
                request_json TEXT NOT NULL,
                response_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_accessed_at TEXT NOT NULL,
                hit_count INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS request_metrics (
                request_id TEXT PRIMARY KEY,
                query_hash TEXT NOT NULL,
                application_area TEXT,
                provider TEXT,
                model TEXT,
                retrieval_method TEXT,
                retrieval_latency_ms REAL,
                generation_latency_ms REAL,
                total_latency_ms REAL,
                input_token_estimate INTEGER,
                context_token_estimate INTEGER,
                output_token_estimate INTEGER,
                estimated_cost_usd REAL,
                cache_hit INTEGER NOT NULL,
                evidence_count INTEGER,
                citations_count INTEGER,
                confidence REAL,
                guardrail_blocked INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_metrics_created_at
            ON request_metrics(created_at);

            CREATE INDEX IF NOT EXISTS
            idx_metrics_provider
            ON request_metrics(provider);
            """
        )


def create_cache_key(payload):
    normalized = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
    )

    return hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()


def get_cached_response(cache_key):
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT response_json
            FROM query_cache
            WHERE cache_key = ?
            """,
            (cache_key,),
        ).fetchone()

        if row is None:
            return None

        connection.execute(
            """
            UPDATE query_cache
            SET
                last_accessed_at = ?,
                hit_count = hit_count + 1
            WHERE cache_key = ?
            """,
            (
                utc_timestamp(),
                cache_key,
            ),
        )

    return json.loads(
        row["response_json"]
    )


def save_cached_response(
    cache_key,
    request_payload,
    response_payload,
):
    timestamp = utc_timestamp()

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO query_cache (
                cache_key,
                request_json,
                response_json,
                created_at,
                last_accessed_at,
                hit_count
            )
            VALUES (?, ?, ?, ?, ?, 0)
            ON CONFLICT(cache_key)
            DO UPDATE SET
                request_json =
                    excluded.request_json,
                response_json =
                    excluded.response_json,
                last_accessed_at =
                    excluded.last_accessed_at
            """,
            (
                cache_key,
                json.dumps(
                    request_payload,
                    ensure_ascii=False,
                ),
                json.dumps(
                    response_payload,
                    ensure_ascii=False,
                ),
                timestamp,
                timestamp,
            ),
        )


def save_request_metrics(metrics):
    with get_connection() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO request_metrics (
                request_id,
                query_hash,
                application_area,
                provider,
                model,
                retrieval_method,
                retrieval_latency_ms,
                generation_latency_ms,
                total_latency_ms,
                input_token_estimate,
                context_token_estimate,
                output_token_estimate,
                estimated_cost_usd,
                cache_hit,
                evidence_count,
                citations_count,
                confidence,
                guardrail_blocked,
                created_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                metrics["request_id"],
                metrics["query_hash"],
                metrics.get(
                    "application_area",
                    "",
                ),
                metrics.get(
                    "provider",
                    "",
                ),
                metrics.get(
                    "model",
                    "",
                ),
                metrics.get(
                    "retrieval_method",
                    "",
                ),
                metrics.get(
                    "retrieval_latency_ms",
                    0,
                ),
                metrics.get(
                    "generation_latency_ms",
                    0,
                ),
                metrics.get(
                    "total_latency_ms",
                    0,
                ),
                metrics.get(
                    "input_token_estimate",
                    0,
                ),
                metrics.get(
                    "context_token_estimate",
                    0,
                ),
                metrics.get(
                    "output_token_estimate",
                    0,
                ),
                metrics.get(
                    "estimated_cost_usd",
                    0,
                ),
                int(
                    metrics.get(
                        "cache_hit",
                        False,
                    )
                ),
                metrics.get(
                    "evidence_count",
                    0,
                ),
                metrics.get(
                    "citations_count",
                    0,
                ),
                metrics.get(
                    "confidence",
                    0,
                ),
                int(
                    metrics.get(
                        "guardrail_blocked",
                        False,
                    )
                ),
                utc_timestamp(),
            ),
        )


def get_operations_summary():
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS total_requests,
                SUM(cache_hit) AS cache_hits,
                AVG(total_latency_ms)
                    AS average_latency_ms,
                AVG(retrieval_latency_ms)
                    AS average_retrieval_latency_ms,
                SUM(input_token_estimate)
                    AS total_input_tokens,
                SUM(context_token_estimate)
                    AS total_context_tokens,
                SUM(output_token_estimate)
                    AS total_output_tokens,
                SUM(estimated_cost_usd)
                    AS total_estimated_cost_usd,
                SUM(guardrail_blocked)
                    AS blocked_requests
            FROM request_metrics
            """
        ).fetchone()

    return dict(row) if row else {}


initialise_operations()
