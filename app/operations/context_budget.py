import json
import math


MAX_CONTEXT_TOKENS = 1800
MAX_EVIDENCE_RECORDS = 5
MAX_CHUNKS_PER_SOURCE = 1


MODEL_COSTS_PER_MILLION = {
    "openai/gpt-oss-20b": {
        "input": 0.10,
        "output": 0.50,
    },
    "default": {
        "input": 0.20,
        "output": 0.80,
    },
}


def estimate_tokens(value):
    """
    Estimate tokens without adding another tokenizer
    dependency inside the restricted VDI.
    """
    if value is None:
        return 0

    if not isinstance(value, str):
        value = json.dumps(
            value,
            ensure_ascii=False,
        )

    return max(
        1,
        math.ceil(
            len(value) / 4
        ),
    )


def deduplicate_context(evidence):
    """
    Retain one strongest evidence record per document ID
    and remove duplicate content hashes.
    """
    selected = []
    document_ids = set()
    content_hashes = set()

    ordered = sorted(
        evidence or [],
        key=lambda item: (
            float(
                item.get(
                    "retrieval_score",
                    0,
                )
            )
        ),
        reverse=True,
    )

    for item in ordered:
        document_id = str(
            item.get(
                "document_id",
                "",
            )
        )

        content_hash = str(
            item.get(
                "content_hash",
                "",
            )
        )

        if document_id in document_ids:
            continue

        if (
            content_hash
            and content_hash
            in content_hashes
        ):
            continue

        selected.append(item)

        document_ids.add(document_id)

        if content_hash:
            content_hashes.add(
                content_hash
            )

    return selected


def apply_context_budget(
    evidence,
    maximum_tokens=MAX_CONTEXT_TOKENS,
    maximum_records=MAX_EVIDENCE_RECORDS,
):
    """
    Select the strongest unique evidence fitting within
    the configured context-token budget.
    """
    deduplicated = deduplicate_context(
        evidence
    )

    selected = []
    used_tokens = 0
    rejected = []

    for item in deduplicated:
        content = " ".join(
            [
                str(
                    item.get(
                        "title",
                        "",
                    )
                ),
                str(
                    item.get(
                        "content",
                        "",
                    )
                ),
                str(
                    item.get(
                        "source",
                        "",
                    )
                ),
            ]
        )

        token_estimate = estimate_tokens(
            content
        )

        if len(selected) >= maximum_records:
            rejected.append(
                {
                    "document_id": item.get(
                        "document_id"
                    ),
                    "reason": (
                        "Maximum evidence count reached"
                    ),
                }
            )

            continue

        if (
            selected
            and used_tokens
            + token_estimate
            > maximum_tokens
        ):
            rejected.append(
                {
                    "document_id": item.get(
                        "document_id"
                    ),
                    "reason": (
                        "Context token budget exceeded"
                    ),
                }
            )

            continue

        enriched = dict(item)

        enriched[
            "context_token_estimate"
        ] = token_estimate

        selected.append(enriched)

        used_tokens += token_estimate

    return {
        "selected": selected,
        "rejected": rejected,
        "used_tokens": used_tokens,
        "maximum_tokens": maximum_tokens,
        "utilization_percent": round(
            (
                used_tokens
                / maximum_tokens
                * 100
            ),
            2,
        ),
    }


def dynamic_evidence_limit(
    confidence,
    evidence_sufficiency,
):
    """
    Use less context when evidence is already strong.

    High-confidence answers:
    3 evidence records

    Medium-confidence answers:
    4 evidence records

    Lower-confidence answers:
    5 evidence records
    """
    if (
        confidence >= 0.85
        and evidence_sufficiency
        >= 0.80
    ):
        return 3

    if (
        confidence >= 0.70
        and evidence_sufficiency
        >= 0.65
    ):
        return 4

    return 5


def estimate_request_cost(
    model,
    input_tokens,
    output_tokens,
):
    rates = MODEL_COSTS_PER_MILLION.get(
        model,
        MODEL_COSTS_PER_MILLION[
            "default"
        ],
    )

    input_cost = (
        input_tokens
        / 1_000_000
        * rates["input"]
    )

    output_cost = (
        output_tokens
        / 1_000_000
        * rates["output"]
    )

    return round(
        input_cost + output_cost,
        8,
    )
