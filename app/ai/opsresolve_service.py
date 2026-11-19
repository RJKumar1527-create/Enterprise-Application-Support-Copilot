from app.database.repository import (
    ims_database_repository,
)
from app.incidents.service import (
    save_self_service_resolution,
)
from app.operations.optimized_pipeline import (
    run_optimized_investigation,
)


def ask_operations_assistant(
    question,
    application_area,
    current_status,
    attempted_action,
    visible_error,
    operational_reference,
):
    database_context = (
        ims_database_repository
        .get_operational_context(
            application_area=(
                application_area
            ),
            reference=(
                operational_reference
            ),
        )
    )

    database_text = ""

    if database_context.get(
        "available"
    ):
        database_text = (
            "\nRead-only IMS DPT1 context:\n"
            + str(
                database_context.get(
                    "records",
                    [],
                )
            )
        )

    internal_result = (
        run_optimized_investigation(
            issue=(
                str(question)
                + database_text
            ),
            application_area=(
                application_area
            ),
            current_status=(
                current_status
            ),
            attempted_action=(
                attempted_action
            ),
            user_role="",
            error_message=(
                visible_error
            ),
        )
    )

    answer = internal_result.get(
        "answer",
        {},
    )

    evidence = internal_result.get(
        "evidence",
        [],
    )

    root_cause = answer.get(
        "most_likely_cause",
        (
            "The available information does "
            "not confirm a root cause."
        ),
    )

    resolution_steps = answer.get(
        "recommended_checks",
        [],
    )

    evidence_ids = list(
        dict.fromkeys(
            item.get("document_id")
            for item in evidence
            if item.get("document_id")
        )
    )

    can_self_resolve = (
        bool(resolution_steps)
        and not answer.get(
            "human_escalation_required",
            False,
        )
    )

    incident_required_when = [
        (
            "The resolution requires a production "
            "data correction."
        ),
        (
            "The resolution requires a permission "
            "or role change."
        ),
        (
            "The documented checks do not resolve "
            "the concern."
        ),
        (
            "The issue requires infrastructure or "
            "configuration investigation."
        ),
    ]

    return {
        "response": answer.get(
            "summary",
            "",
        ),
        "root_cause": root_cause,
        "resolution_steps": (
            resolution_steps
        ),
        "supporting_evidence": (
            evidence_ids
        ),
        "can_self_resolve": (
            can_self_resolve
        ),
        "incident_required_when": (
            incident_required_when
        ),
        "database_context": {
            "source": "IMS DPT1",
            "available": (
                database_context.get(
                    "available",
                    False,
                )
            ),
            "limitation": (
                database_context.get(
                    "reason",
                    ""
                )
            ),
        },
        "_internal": {
            "provider": internal_result.get(
                "provider"
            ),
            "model": internal_result.get(
                "model"
            ),
            "performance": (
                internal_result.get(
                    "performance",
                    {},
                )
            ),
            "usage": internal_result.get(
                "usage",
                {},
            ),
            "guardrails": (
                internal_result.get(
                    "guardrails",
                    {},
                )
            ),
        },
    }


def record_user_resolution(payload):
    save_self_service_resolution(
        question=payload.get(
            "question",
            "",
        ),
        application_area=payload.get(
            "application_area",
            "",
        ),
        root_cause=payload.get(
            "root_cause",
            "",
        ),
        resolution_steps=payload.get(
            "resolution_steps",
            [],
        ),
        evidence_ids=payload.get(
            "supporting_evidence",
            [],
        ),
    )

    return {
        "saved": True,
        "message": (
            "Self-service resolution was recorded."
        ),
    }
