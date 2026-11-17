import copy
import hashlib
import json
import time
from uuid import uuid4

from app.guardrails.pipeline import (
    run_guarded_investigation,
)
from app.operations.context_budget import (
    apply_context_budget,
    dynamic_evidence_limit,
    estimate_request_cost,
    estimate_tokens,
)
from app.operations.store import (
    create_cache_key,
    get_cached_response,
    save_cached_response,
    save_request_metrics,
)


def query_hash(question):
    return hashlib.sha256(
        str(question).encode("utf-8")
    ).hexdigest()


def run_optimized_investigation(
    issue,
    application_area,
    current_status,
    attempted_action,
    user_role,
    error_message,
    conversation_id=None,
):
    request_start = time.perf_counter()

    request_payload = {
        "issue": str(issue or "").strip(),
        "application_area": str(
            application_area or "ALL"
        ),
        "current_status": str(
            current_status or ""
        ).strip(),
        "attempted_action": str(
            attempted_action or ""
        ).strip(),
        "user_role": str(
            user_role or ""
        ).strip(),
        "error_message": str(
            error_message or ""
        ).strip(),
    }

    cache_key = create_cache_key(
        request_payload
    )

    cached_result = get_cached_response(
        cache_key
    )

    if cached_result:
        cached_result = copy.deepcopy(
            cached_result
        )

        cached_result["cache"] = {
            "hit": True,
            "cache_key": cache_key,
        }

        cached_result.setdefault(
            "performance",
            {}
        )

        cached_result[
            "performance"
        ][
            "total_latency_ms"
        ] = round(
            (
                time.perf_counter()
                - request_start
            )
            * 1000,
            2,
        )

        record_metrics(
            request_payload,
            cached_result,
            cache_hit=True,
        )

        return cached_result

    result = run_guarded_investigation(
        issue=request_payload["issue"],
        application_area=request_payload[
            "application_area"
        ],
        current_status=request_payload[
            "current_status"
        ],
        attempted_action=request_payload[
            "attempted_action"
        ],
        user_role=request_payload[
            "user_role"
        ],
        error_message=request_payload[
            "error_message"
        ],
        conversation_id=conversation_id,
    )

    answer = result.get(
        "answer",
        {},
    )

    evidence = result.get(
        "evidence",
        [],
    )

    guardrails = result.get(
        "guardrails",
        {},
    )

    if not guardrails.get(
        "blocked",
        False,
    ):
        sufficiency = guardrails.get(
            "evidence_sufficiency",
            {},
        )

        maximum_records = (
            dynamic_evidence_limit(
                confidence=float(
                    answer.get(
                        "confidence",
                        0,
                    )
                ),
                evidence_sufficiency=float(
                    sufficiency.get(
                        "score",
                        0,
                    )
                ),
            )
        )

        budget = apply_context_budget(
            evidence=evidence,
            maximum_tokens=1800,
            maximum_records=(
                maximum_records
            ),
        )

        selected_evidence = budget[
            "selected"
        ]

        selected_ids = {
            item.get("document_id")
            for item
            in selected_evidence
        }

        answer["citations"] = [
            citation
            for citation
            in answer.get(
                "citations",
                [],
            )
            if citation in selected_ids
        ]

        result["evidence"] = (
            selected_evidence
        )

        result["context_budget"] = {
            "maximum_tokens": budget[
                "maximum_tokens"
            ],
            "used_tokens": budget[
                "used_tokens"
            ],
            "utilization_percent": budget[
                "utilization_percent"
            ],
            "maximum_records": (
                maximum_records
            ),
            "selected_records": len(
                selected_evidence
            ),
            "rejected_records": budget[
                "rejected"
            ],
        }

    else:
        result["context_budget"] = {
            "maximum_tokens": 0,
            "used_tokens": 0,
            "utilization_percent": 0,
            "maximum_records": 0,
            "selected_records": 0,
            "rejected_records": [],
        }

    input_tokens = estimate_tokens(
        request_payload
    )

    context_tokens = result[
        "context_budget"
    ]["used_tokens"]

    output_tokens = estimate_tokens(
        result.get(
            "answer",
            {},
        )
    )

    model = result.get(
        "model",
        "default",
    )

    result["usage"] = {
        "input_token_estimate": (
            input_tokens
        ),
        "context_token_estimate": (
            context_tokens
        ),
        "output_token_estimate": (
            output_tokens
        ),
        "total_token_estimate": (
            input_tokens
            + context_tokens
            + output_tokens
        ),
        "estimated_cost_usd": (
            0.0
            if result.get("provider") in {
                "Deterministic",
                "Guardrail",
            }
            else estimate_request_cost(
                model=model,
                input_tokens=(
                    input_tokens
                    + context_tokens
                ),
                output_tokens=(
                    output_tokens
                ),
            )
        ),
    }

    result["cache"] = {
        "hit": False,
        "cache_key": cache_key,
    }

    result.setdefault(
        "performance",
        {}
    )

    result[
        "performance"
    ]["total_latency_ms"] = round(
        (
            time.perf_counter()
            - request_start
        )
        * 1000,
        2,
    )

    save_cached_response(
        cache_key=cache_key,
        request_payload=(
            request_payload
        ),
        response_payload=result,
    )

    record_metrics(
        request_payload,
        result,
        cache_hit=False,
    )

    return result


def record_metrics(
    request_payload,
    result,
    cache_hit,
):
    answer = result.get(
        "answer",
        {},
    )

    performance = result.get(
        "performance",
        {},
    )

    usage = result.get(
        "usage",
        {},
    )

    guardrails = result.get(
        "guardrails",
        {},
    )

    save_request_metrics(
        {
            "request_id": str(
                uuid4()
            ),
            "query_hash": query_hash(
                request_payload[
                    "issue"
                ]
            ),
            "application_area": (
                request_payload[
                    "application_area"
                ]
            ),
            "provider": result.get(
                "provider",
                "",
            ),
            "model": result.get(
                "model",
                "",
            ),
            "retrieval_method": (
                result.get(
                    "retrieval_method",
                    "",
                )
            ),
            "retrieval_latency_ms": (
                performance.get(
                    "retrieval_latency_ms",
                    0,
                )
            ),
            "generation_latency_ms": (
                performance.get(
                    "generation_latency_ms",
                    0,
                )
            ),
            "total_latency_ms": (
                performance.get(
                    "total_latency_ms",
                    0,
                )
            ),
            "input_token_estimate": (
                usage.get(
                    "input_token_estimate",
                    0,
                )
            ),
            "context_token_estimate": (
                usage.get(
                    "context_token_estimate",
                    0,
                )
            ),
            "output_token_estimate": (
                usage.get(
                    "output_token_estimate",
                    0,
                )
            ),
            "estimated_cost_usd": (
                usage.get(
                    "estimated_cost_usd",
                    0,
                )
            ),
            "cache_hit": cache_hit,
            "evidence_count": len(
                result.get(
                    "evidence",
                    [],
                )
            ),
            "citations_count": len(
                answer.get(
                    "citations",
                    [],
                )
            ),
            "confidence": float(
                answer.get(
                    "confidence",
                    0,
                )
            ),
            "guardrail_blocked": (
                guardrails.get(
                    "blocked",
                    False,
                )
            ),
        }
    )
