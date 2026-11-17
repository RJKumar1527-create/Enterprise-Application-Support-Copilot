import re
import time
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4

from app.ai.support_engine import (
    generate_answer_v2,
)
from app.memory.case_memory import (
    add_message,
    ensure_conversation,
    get_recent_messages,
    get_similar_validated_memories,
    save_investigation_memory,
)


class InvestigationStage(str, Enum):
    CLASSIFY = "CLASSIFY"
    PLAN = "PLAN"
    RETRIEVE = "RETRIEVE"
    VALIDATE = "VALIDATE"
    DIAGNOSE = "DIAGNOSE"
    MEMORY = "MEMORY"
    COMPLETE = "COMPLETE"
    ESCALATE = "ESCALATE"


@dataclass
class InvestigationState:
    investigation_id: str
    conversation_id: str
    issue: str
    application_area: str
    current_status: str
    attempted_action: str
    user_role: str
    error_message: str
    stage: InvestigationStage
    intent: str = "general_support"
    plan: list = field(
        default_factory=list
    )
    missing_information: list = field(
        default_factory=list
    )
    evidence_sufficient: bool = False
    answer_result: dict = field(
        default_factory=dict
    )
    similar_memories: list = field(
        default_factory=list
    )
    execution_trace: list = field(
        default_factory=list
    )


def add_trace(
    state,
    stage,
    detail,
    duration_ms=0,
):
    state.execution_trace.append(
        {
            "stage": stage,
            "detail": detail,
            "duration_ms": round(
                duration_ms,
                2,
            ),
        }
    )


def classify_issue(state):
    start = time.perf_counter()

    text = " ".join(
        [
            state.issue,
            state.application_area,
            state.current_status,
            state.attempted_action,
            state.error_message,
        ]
    ).lower()

    if (
        "batch" in text
        and "export" in text
    ):
        state.intent = "batch_export"

    elif any(
        term in text
        for term in [
            "d2021",
            "zhv",
            "zpt",
            "bcd",
            "ccd",
            "file remains",
        ]
    ):
        state.intent = (
            "d2021_processing"
        )

    elif any(
        term in text
        for term in [
            "authorize",
            "authorization",
            "permission",
            "role",
        ]
    ):
        state.intent = "authorization"

    elif "report" in text:
        state.intent = (
            "report_discovery"
        )

    else:
        state.intent = (
            "general_support"
        )

    state.stage = InvestigationStage.PLAN

    add_trace(
        state,
        "CLASSIFY",
        f"Detected intent: {state.intent}",
        (
            time.perf_counter()
            - start
        )
        * 1000,
    )

    return state


def build_investigation_plan(state):
    start = time.perf_counter()

    plans = {
        "batch_export": [
            (
                "Check the status of every "
                "invoice in the batch."
            ),
            (
                "Check authorization role "
                "and monetary limit."
            ),
            (
                "Check the batch freeze state."
            ),
            (
                "Check export mapping and "
                "output-directory access."
            ),
        ],
        "d2021_processing": [
            (
                "Validate the filename and "
                "file envelope."
            ),
            (
                "Check ZHV and ZPT records."
            ),
            (
                "Check CLO, MPC, BCD and CCD "
                "record hierarchy."
            ),
            (
                "Review scheduler, service and "
                "file-error records."
            ),
        ],
        "authorization": [
            (
                "Check the current invoice status."
            ),
            (
                "Check the user's role and "
                "authorization limit."
            ),
            (
                "Check screen and action permissions."
            ),
        ],
        "report_discovery": [
            (
                "Identify the required business "
                "measure."
            ),
            (
                "Retrieve the matching report "
                "definition."
            ),
            (
                "Return report purpose and "
                "required parameters."
            ),
        ],
        "general_support": [
            (
                "Identify the application area "
                "and workflow state."
            ),
            (
                "Retrieve business rules and "
                "similar incidents."
            ),
            (
                "Generate a read-only "
                "investigation plan."
            ),
        ],
    }

    state.plan = plans.get(
        state.intent,
        plans["general_support"],
    )

    state.stage = (
        InvestigationStage.RETRIEVE
    )

    add_trace(
        state,
        "PLAN",
        (
            f"Created {len(state.plan)} "
            "investigation steps."
        ),
        (
            time.perf_counter()
            - start
        )
        * 1000,
    )

    return state


def retrieve_and_diagnose(state):
    start = time.perf_counter()

    result = generate_answer_v2(
        issue=state.issue,
        application_area=(
            state.application_area
        ),
        current_status=(
            state.current_status
        ),
        attempted_action=(
            state.attempted_action
        ),
        user_role=state.user_role,
        error_message=(
            state.error_message
        ),
    )

    state.answer_result = result

    state.stage = (
        InvestigationStage.VALIDATE
    )

    add_trace(
        state,
        "RETRIEVE",
        (
            f"Retrieved "
            f"{len(result.get('evidence', []))} "
            "unique evidence records."
        ),
        (
            time.perf_counter()
            - start
        )
        * 1000,
    )

    return state


def validate_evidence(state):
    start = time.perf_counter()

    evidence = state.answer_result.get(
        "evidence",
        [],
    )

    answer = state.answer_result.get(
        "answer",
        {},
    )

    evidence_ids = {
        item.get("document_id")
        for item in evidence
    }

    required_by_intent = {
        "batch_export": {
            "BATCH-001",
            "ACC-001",
            "WF-001",
            "INC-001",
        },
        "d2021_processing": {
            "D21-001",
            "D21-002",
            "INC-002",
        },
        "authorization": {
            "ACC-001",
            "WF-001",
        },
    }

    required_ids = required_by_intent.get(
        state.intent,
        set(),
    )

    direct_coverage = (
        len(
            required_ids
            & evidence_ids
        )
        / max(
            len(required_ids),
            1,
        )
        if required_ids
        else 1.0
    )

    confidence = float(
        answer.get(
            "confidence",
            0,
        )
    )

    citation_count = len(
        answer.get(
            "citations",
            [],
        )
    )

    state.evidence_sufficient = (
        len(evidence) >= 2
        and citation_count >= 1
        and direct_coverage >= 0.50
        and confidence >= 0.55
    )

    if not state.evidence_sufficient:
        if len(evidence) < 2:
            state.missing_information.append(
                "Additional domain evidence"
            )

        if direct_coverage < 0.50:
            state.missing_information.append(
                "Required workflow or "
                "incident coverage"
            )

        if not state.current_status:
            state.missing_information.append(
                "Current workflow status"
            )

        if not state.user_role:
            state.missing_information.append(
                "Current user role"
            )

    state.stage = (
        InvestigationStage.DIAGNOSE
        if state.evidence_sufficient
        else InvestigationStage.ESCALATE
    )

    add_trace(
        state,
        "VALIDATE",
        (
            "Evidence sufficient"
            if state.evidence_sufficient
            else (
                "Evidence insufficient: "
                + ", ".join(
                    state.missing_information
                )
            )
        ),
        (
            time.perf_counter()
            - start
        )
        * 1000,
    )

    return state


def apply_case_memory(state):
    start = time.perf_counter()

    state.similar_memories = (
        get_similar_validated_memories(
            query=state.issue,
            limit=3,
        )
    )

    answer = state.answer_result.get(
        "answer",
        {}
    )

    if state.similar_memories:
        answer[
            "similar_resolved_cases"
        ] = [
            {
                "memory_id": item[
                    "memory_id"
                ],
                "root_cause": item.get(
                    "confirmed_root_cause"
                ),
                "resolution": item.get(
                    "resolution_summary"
                ),
                "similarity": item[
                    "similarity_score"
                ],
            }
            for item
            in state.similar_memories
        ]

    else:
        answer[
            "similar_resolved_cases"
        ] = []

    state.answer_result[
        "answer"
    ] = answer

    state.stage = (
        InvestigationStage.MEMORY
    )

    add_trace(
        state,
        "MEMORY",
        (
            f"Found "
            f"{len(state.similar_memories)} "
            "validated case memories."
        ),
        (
            time.perf_counter()
            - start
        )
        * 1000,
    )

    return state


def store_ai_memory(state):
    start = time.perf_counter()

    evidence_ids = [
        item.get("document_id")
        for item
        in state.answer_result.get(
            "evidence",
            [],
        )
    ]

    answer = state.answer_result.get(
        "answer",
        {},
    )

    memory_id = (
        save_investigation_memory(
            issue_summary=state.issue,
            evidence_ids=evidence_ids,
            conversation_id=(
                state.conversation_id
            ),
            confirmed_root_cause=(
                answer.get(
                    "most_likely_cause"
                )
            ),
            resolution_summary=None,
            validation_status=(
                "AI_GENERATED"
            ),
        )
    )

    state.stage = (
        InvestigationStage.COMPLETE
    )

    add_trace(
        state,
        "STORE_MEMORY",
        (
            f"Stored AI investigation "
            f"memory {memory_id}."
        ),
        (
            time.perf_counter()
            - start
        )
        * 1000,
    )

    return state


def run_investigation(
    issue,
    application_area,
    current_status,
    attempted_action,
    user_role,
    error_message,
    conversation_id=None,
):
    conversation_id = (
        conversation_id
        or str(uuid4())
    )

    ensure_conversation(
        conversation_id,
        application_area,
    )

    add_message(
        conversation_id,
        "user",
        issue,
        {
            "application_area": (
                application_area
            ),
            "current_status": (
                current_status
            ),
            "attempted_action": (
                attempted_action
            ),
            "user_role": user_role,
            "error_message": (
                error_message
            ),
        },
    )

    state = InvestigationState(
        investigation_id=str(
            uuid4()
        ),
        conversation_id=(
            conversation_id
        ),
        issue=issue,
        application_area=(
            application_area
        ),
        current_status=(
            current_status
        ),
        attempted_action=(
            attempted_action
        ),
        user_role=user_role,
        error_message=error_message,
        stage=(
            InvestigationStage.CLASSIFY
        ),
    )

    state = classify_issue(state)

    state = build_investigation_plan(
        state
    )

    state = retrieve_and_diagnose(
        state
    )

    state = validate_evidence(state)

    state = apply_case_memory(state)

    if state.evidence_sufficient:
        state = store_ai_memory(state)

    answer = state.answer_result.get(
        "answer",
        {},
    )

    answer[
        "investigation_plan"
    ] = state.plan

    answer[
        "evidence_sufficient"
    ] = state.evidence_sufficient

    answer[
        "missing_information"
    ] = state.missing_information

    answer[
        "conversation_id"
    ] = state.conversation_id

    answer[
        "investigation_id"
    ] = state.investigation_id

    state.answer_result[
        "answer"
    ] = answer

    state.answer_result[
        "agent_trace"
    ] = state.execution_trace

    state.answer_result[
        "intent"
    ] = state.intent

    state.answer_result[
        "conversation_id"
    ] = state.conversation_id

    add_message(
        state.conversation_id,
        "assistant",
        answer.get(
            "summary",
            "",
        ),
        {
            "intent": state.intent,
            "citations": answer.get(
                "citations",
                [],
            ),
            "confidence": answer.get(
                "confidence",
                0,
            ),
            "evidence_sufficient": (
                state.evidence_sufficient
            ),
        },
    )

    state.answer_result[
        "conversation_memory"
    ] = get_recent_messages(
        state.conversation_id,
        limit=6,
    )

    return state.answer_result
