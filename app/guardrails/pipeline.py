from app.ai.investigation_agent import (
    run_investigation,
)
from app.guardrails.safety import (
    calculate_evidence_sufficiency,
    safe_refusal,
    validate_evidence_records,
    validate_user_input,
)


def validate_optional_input(value):
    """
    Allow an empty optional field.

    When a value is supplied, apply the complete input
    guardrail and identifier-masking process.
    """
    if value is None or not str(value).strip():
        return {
            "allowed": True,
            "sanitized_text": "",
            "blocked_reasons": [],
            "warnings": [],
            "masked_items": [],
        }

    result = validate_user_input(value)

    return {
        "allowed": result.allowed,
        "sanitized_text": result.sanitized_text,
        "blocked_reasons": result.blocked_reasons,
        "warnings": result.warnings,
        "masked_items": result.masked_items,
    }


def run_guarded_investigation(
    issue,
    application_area,
    current_status,
    attempted_action,
    user_role,
    error_message,
    conversation_id=None,
):
    """
    Validate, sanitize and process a support investigation.

    The issue description is mandatory.

    Current status, attempted action, user role and error
    message are optional context fields.
    """

    # Mandatory support question
    issue_result = validate_user_input(
        issue
    )

    if not issue_result.allowed:
        return safe_refusal(
            reasons=[
                f"issue: {reason}"
                for reason
                in issue_result.blocked_reasons
            ],
            warnings=issue_result.warnings,
        )

    sanitized_values = {
        "issue": issue_result.sanitized_text
    }

    warnings = list(
        issue_result.warnings
    )

    masked_items = [
        {
            "field": "issue",
            **item,
        }
        for item
        in issue_result.masked_items
    ]

    # Optional incident context
    optional_values = {
        "current_status": current_status,
        "attempted_action": attempted_action,
        "user_role": user_role,
        "error_message": error_message,
    }

    for field_name, field_value in (
        optional_values.items()
    ):
        result = validate_optional_input(
            field_value
        )

        if not result["allowed"]:
            return safe_refusal(
                reasons=[
                    (
                        f"{field_name}: "
                        f"{reason}"
                    )
                    for reason
                    in result[
                        "blocked_reasons"
                    ]
                ],
                warnings=result[
                    "warnings"
                ],
            )

        sanitized_values[
            field_name
        ] = result["sanitized_text"]

        warnings.extend(
            result["warnings"]
        )

        masked_items.extend(
            [
                {
                    "field": field_name,
                    **item,
                }
                for item
                in result[
                    "masked_items"
                ]
            ]
        )

    result = run_investigation(
        issue=sanitized_values["issue"],
        application_area=(
            application_area
            or "ALL"
        ),
        current_status=sanitized_values[
            "current_status"
        ],
        attempted_action=sanitized_values[
            "attempted_action"
        ],
        user_role=sanitized_values[
            "user_role"
        ],
        error_message=sanitized_values[
            "error_message"
        ],
        conversation_id=conversation_id,
    )

    evidence = result.get(
        "evidence",
        [],
    )

    valid_evidence, rejected_evidence = (
        validate_evidence_records(
            evidence
        )
    )

    result["evidence"] = valid_evidence

    answer = result.get(
        "answer",
        {},
    )

    valid_evidence_ids = {
        item.get("document_id")
        for item in valid_evidence
    }

    answer["citations"] = list(
        dict.fromkeys(
            citation
            for citation in answer.get(
                "citations",
                [],
            )
            if citation
            in valid_evidence_ids
        )
    )

    sufficiency = (
        calculate_evidence_sufficiency(
            answer,
            valid_evidence,
        )
    )

    answer[
        "evidence_sufficient"
    ] = sufficiency["sufficient"]

    answer[
        "evidence_sufficiency_score"
    ] = sufficiency["score"]

    if not sufficiency["sufficient"]:
        answer["limitations"] = list(
            dict.fromkeys(
                answer.get(
                    "limitations",
                    [],
                )
                + [
                    (
                        "The retrieved evidence did not "
                        "meet the minimum sufficiency "
                        "threshold."
                    )
                ]
            )
        )

        answer[
            "human_escalation_required"
        ] = True

    else:
        answer[
            "human_escalation_required"
        ] = (
            float(
                answer.get(
                    "confidence",
                    0,
                )
            )
            < 0.75
        )

    result["answer"] = answer

    result["guardrails"] = {
        "blocked": False,
        "warnings": list(
            dict.fromkeys(warnings)
        ),
        "masked_items": masked_items,
        "rejected_evidence": (
            rejected_evidence
        ),
        "evidence_sufficiency": (
            sufficiency
        ),
    }

    return result
