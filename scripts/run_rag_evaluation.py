import json
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from app.ai.investigation_agent import (
    classify_issue,
    InvestigationStage,
    InvestigationState,
)
from app.ai.support_engine import (
    hybrid_retrieve,
)
from app.guardrails.safety import (
    validate_user_input,
)


EVALUATION_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "rag_evaluation_set.json"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "evaluation"
    / "rag_evaluation_results.json"
)


def recall_at_k(
    retrieved,
    expected,
    k,
):
    expected_set = set(expected)

    if not expected_set:
        return 1.0

    retrieved_set = set(
        retrieved[:k]
    )

    return (
        len(
            retrieved_set
            & expected_set
        )
        / len(expected_set)
    )


def precision_at_k(
    retrieved,
    expected,
    k,
):
    retrieved_top_k = retrieved[:k]

    if not retrieved_top_k:
        return 0.0

    expected_set = set(expected)

    return (
        len(
            set(retrieved_top_k)
            & expected_set
        )
        / len(retrieved_top_k)
    )


def reciprocal_rank(
    retrieved,
    expected,
):
    expected_set = set(expected)

    for rank, document_id in enumerate(
        retrieved,
        start=1,
    ):
        if document_id in expected_set:
            return 1.0 / rank

    return 0.0


def detect_intent(question, area):
    state = InvestigationState(
        investigation_id="evaluation",
        conversation_id="evaluation",
        issue=question,
        application_area=area,
        current_status="",
        attempted_action="",
        user_role="",
        error_message="",
        stage=InvestigationStage.CLASSIFY,
    )

    state = classify_issue(state)

    return state.intent


def main():
    records = json.loads(
        EVALUATION_PATH.read_text(
            encoding="utf-8-sig"
        )
    )

    results = []

    for record in records:
        question = record["question"]

        guardrail_result = (
            validate_user_input(
                question
            )
        )

        blocked = not guardrail_result.allowed

        if record["should_be_blocked"]:
            results.append(
                {
                    "question_id": record[
                        "question_id"
                    ],
                    "question": question,
                    "blocked": blocked,
                    "expected_blocked": True,
                    "guardrail_correct": blocked,
                    "recall_at_5": None,
                    "precision_at_5": None,
                    "reciprocal_rank": None,
                    "forbidden_document_rate": None,
                    "latency_ms": 0,
                    "retrieved_documents": [],
                }
            )

            continue

        start_time = time.perf_counter()

        retrieval = hybrid_retrieve(
            query=question,
            application_area=record[
                "application_area"
            ],
            top_k=5,
        )

        latency_ms = (
            time.perf_counter()
            - start_time
        ) * 1000

        retrieved_documents = [
            item["document_id"]
            for item in retrieval[
                "results"
            ]
        ]

        forbidden_set = set(
            record.get(
                "forbidden_documents",
                [],
            )
        )

        forbidden_count = len(
            set(retrieved_documents)
            & forbidden_set
        )

        forbidden_rate = (
            forbidden_count
            / max(
                len(retrieved_documents),
                1,
            )
        )

        detected_intent = detect_intent(
            question,
            record[
                "application_area"
            ],
        )

        results.append(
            {
                "question_id": record[
                    "question_id"
                ],
                "question": question,
                "blocked": blocked,
                "expected_blocked": False,
                "guardrail_correct": (
                    not blocked
                ),
                "expected_intent": record[
                    "expected_intent"
                ],
                "detected_intent": (
                    detected_intent
                ),
                "intent_correct": (
                    detected_intent
                    == record[
                        "expected_intent"
                    ]
                ),
                "recall_at_5": round(
                    recall_at_k(
                        retrieved_documents,
                        record[
                            "expected_documents"
                        ],
                        5,
                    ),
                    4,
                ),
                "precision_at_5": round(
                    precision_at_k(
                        retrieved_documents,
                        record[
                            "expected_documents"
                        ],
                        5,
                    ),
                    4,
                ),
                "reciprocal_rank": round(
                    reciprocal_rank(
                        retrieved_documents,
                        record[
                            "expected_documents"
                        ],
                    ),
                    4,
                ),
                "forbidden_document_rate": round(
                    forbidden_rate,
                    4,
                ),
                "latency_ms": round(
                    latency_ms,
                    2,
                ),
                "retrieval_method": retrieval[
                    "method"
                ],
                "retrieved_documents": (
                    retrieved_documents
                ),
            }
        )

    retrieval_results = [
        result
        for result in results
        if result["recall_at_5"]
        is not None
    ]

    guardrail_results = [
        result
        for result in results
        if result["expected_blocked"]
    ]

    summary = {
        "question_count": len(results),
        "retrieval_question_count": len(
            retrieval_results
        ),
        "guardrail_question_count": len(
            guardrail_results
        ),
        "average_recall_at_5": round(
            sum(
                item["recall_at_5"]
                for item
                in retrieval_results
            )
            / max(
                len(retrieval_results),
                1,
            ),
            4,
        ),
        "average_precision_at_5": round(
            sum(
                item["precision_at_5"]
                for item
                in retrieval_results
            )
            / max(
                len(retrieval_results),
                1,
            ),
            4,
        ),
        "mean_reciprocal_rank": round(
            sum(
                item["reciprocal_rank"]
                for item
                in retrieval_results
            )
            / max(
                len(retrieval_results),
                1,
            ),
            4,
        ),
        "average_forbidden_document_rate": round(
            sum(
                item[
                    "forbidden_document_rate"
                ]
                for item
                in retrieval_results
            )
            / max(
                len(retrieval_results),
                1,
            ),
            4,
        ),
        "intent_accuracy": round(
            sum(
                bool(
                    item.get(
                        "intent_correct"
                    )
                )
                for item
                in retrieval_results
            )
            / max(
                len(retrieval_results),
                1,
            ),
            4,
        ),
        "guardrail_accuracy": round(
            sum(
                item[
                    "guardrail_correct"
                ]
                for item
                in guardrail_results
            )
            / max(
                len(guardrail_results),
                1,
            ),
            4,
        ),
        "average_latency_ms": round(
            sum(
                item["latency_ms"]
                for item
                in retrieval_results
            )
            / max(
                len(retrieval_results),
                1,
            ),
            2,
        ),
    }

    passed = (
        summary[
            "average_recall_at_5"
        ]
        >= 0.85
        and summary[
            "mean_reciprocal_rank"
        ]
        >= 0.80
        and summary[
            "guardrail_accuracy"
        ]
        >= 0.95
        and summary[
            "average_forbidden_document_rate"
        ]
        <= 0.10
    )

    summary[
        "quality_gate_passed"
    ] = passed

    payload = {
        "summary": summary,
        "results": results,
    }

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            payload,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            summary,
            indent=2,
        )
    )

    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
