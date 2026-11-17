import json
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

OPERATIONS_DATABASE_PATH = (
    PROJECT_ROOT
    / "data"
    / "operations.db"
)

EVALUATION_PATH = (
    PROJECT_ROOT
    / "data"
    / "evaluation"
    / "rag_evaluation_results.json"
)


def empty_summary():
    return {
        "total_requests": 0,
        "cache_hits": 0,
        "cache_hit_rate": 0.0,
        "average_latency_ms": 0.0,
        "average_retrieval_latency_ms": 0.0,
        "total_input_tokens": 0,
        "total_context_tokens": 0,
        "total_output_tokens": 0,
        "total_tokens": 0,
        "total_estimated_cost_usd": 0.0,
        "blocked_requests": 0,
        "blocked_rate": 0.0,
        "average_confidence": 0.0,
        "average_evidence_count": 0.0,
        "low_confidence_requests": 0,
    }


def get_connection():
    connection = sqlite3.connect(
        OPERATIONS_DATABASE_PATH
    )

    connection.row_factory = sqlite3.Row

    return connection


def get_request_summary():
    if not OPERATIONS_DATABASE_PATH.exists():
        return empty_summary()

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS total_requests,
                COALESCE(
                    SUM(cache_hit),
                    0
                ) AS cache_hits,
                COALESCE(
                    AVG(total_latency_ms),
                    0
                ) AS average_latency_ms,
                COALESCE(
                    AVG(retrieval_latency_ms),
                    0
                ) AS average_retrieval_latency_ms,
                COALESCE(
                    SUM(input_token_estimate),
                    0
                ) AS total_input_tokens,
                COALESCE(
                    SUM(context_token_estimate),
                    0
                ) AS total_context_tokens,
                COALESCE(
                    SUM(output_token_estimate),
                    0
                ) AS total_output_tokens,
                COALESCE(
                    SUM(estimated_cost_usd),
                    0
                ) AS total_estimated_cost_usd,
                COALESCE(
                    SUM(guardrail_blocked),
                    0
                ) AS blocked_requests,
                COALESCE(
                    AVG(confidence),
                    0
                ) AS average_confidence,
                COALESCE(
                    AVG(evidence_count),
                    0
                ) AS average_evidence_count,
                COALESCE(
                    SUM(
                        CASE
                            WHEN confidence < 0.70
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS low_confidence_requests
            FROM request_metrics
            """
        ).fetchone()

    values = dict(row)

    total_requests = int(
        values.get(
            "total_requests",
            0,
        )
        or 0
    )

    cache_hits = int(
        values.get(
            "cache_hits",
            0,
        )
        or 0
    )

    blocked_requests = int(
        values.get(
            "blocked_requests",
            0,
        )
        or 0
    )

    total_tokens = (
        int(
            values.get(
                "total_input_tokens",
                0,
            )
            or 0
        )
        + int(
            values.get(
                "total_context_tokens",
                0,
            )
            or 0
        )
        + int(
            values.get(
                "total_output_tokens",
                0,
            )
            or 0
        )
    )

    return {
        "total_requests": total_requests,
        "cache_hits": cache_hits,
        "cache_hit_rate": round(
            (
                cache_hits
                / total_requests
                * 100
            )
            if total_requests
            else 0,
            2,
        ),
        "average_latency_ms": round(
            float(
                values.get(
                    "average_latency_ms",
                    0,
                )
                or 0
            ),
            2,
        ),
        "average_retrieval_latency_ms": round(
            float(
                values.get(
                    "average_retrieval_latency_ms",
                    0,
                )
                or 0
            ),
            2,
        ),
        "total_input_tokens": int(
            values.get(
                "total_input_tokens",
                0,
            )
            or 0
        ),
        "total_context_tokens": int(
            values.get(
                "total_context_tokens",
                0,
            )
            or 0
        ),
        "total_output_tokens": int(
            values.get(
                "total_output_tokens",
                0,
            )
            or 0
        ),
        "total_tokens": total_tokens,
        "total_estimated_cost_usd": round(
            float(
                values.get(
                    "total_estimated_cost_usd",
                    0,
                )
                or 0
            ),
            6,
        ),
        "blocked_requests": blocked_requests,
        "blocked_rate": round(
            (
                blocked_requests
                / total_requests
                * 100
            )
            if total_requests
            else 0,
            2,
        ),
        "average_confidence": round(
            float(
                values.get(
                    "average_confidence",
                    0,
                )
                or 0
            )
            * 100,
            2,
        ),
        "average_evidence_count": round(
            float(
                values.get(
                    "average_evidence_count",
                    0,
                )
                or 0
            ),
            2,
        ),
        "low_confidence_requests": int(
            values.get(
                "low_confidence_requests",
                0,
            )
            or 0
        ),
    }


def get_provider_distribution():
    if not OPERATIONS_DATABASE_PATH.exists():
        return []

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                COALESCE(
                    provider,
                    'Unknown'
                ) AS provider,
                COALESCE(
                    model,
                    'Unknown'
                ) AS model,
                COUNT(*) AS request_count,
                AVG(total_latency_ms)
                    AS average_latency_ms,
                AVG(confidence)
                    AS average_confidence
            FROM request_metrics
            GROUP BY provider, model
            ORDER BY request_count DESC
            """
        ).fetchall()

    return [
        {
            "provider": row["provider"],
            "model": row["model"],
            "request_count": int(
                row["request_count"]
            ),
            "average_latency_ms": round(
                float(
                    row[
                        "average_latency_ms"
                    ]
                    or 0
                ),
                2,
            ),
            "average_confidence": round(
                float(
                    row[
                        "average_confidence"
                    ]
                    or 0
                )
                * 100,
                2,
            ),
        }
        for row in rows
    ]


def get_recent_requests(limit=20):
    if not OPERATIONS_DATABASE_PATH.exists():
        return []

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                request_id,
                application_area,
                provider,
                model,
                retrieval_method,
                retrieval_latency_ms,
                total_latency_ms,
                context_token_estimate,
                output_token_estimate,
                estimated_cost_usd,
                cache_hit,
                evidence_count,
                citations_count,
                confidence,
                guardrail_blocked,
                created_at
            FROM request_metrics
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [
        {
            **dict(row),
            "cache_hit": bool(
                row["cache_hit"]
            ),
            "guardrail_blocked": bool(
                row[
                    "guardrail_blocked"
                ]
            ),
            "confidence_percent": round(
                float(
                    row["confidence"]
                    or 0
                )
                * 100,
                2,
            ),
            "estimated_cost_usd": round(
                float(
                    row[
                        "estimated_cost_usd"
                    ]
                    or 0
                ),
                8,
            ),
        }
        for row in rows
    ]


def get_evaluation_summary():
    if not EVALUATION_PATH.exists():
        return {
            "available": False,
            "quality_gate_passed": False,
        }

    payload = json.loads(
        EVALUATION_PATH.read_text(
            encoding="utf-8"
        )
    )

    summary = payload.get(
        "summary",
        {},
    )

    return {
        "available": True,
        **summary,
    }


def get_support_analytics():
    return {
        "request_summary": (
            get_request_summary()
        ),
        "provider_distribution": (
            get_provider_distribution()
        ),
        "evaluation_summary": (
            get_evaluation_summary()
        ),
        "recent_requests": (
            get_recent_requests()
        ),
    }
