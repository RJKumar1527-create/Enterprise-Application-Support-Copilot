import re
from dataclasses import dataclass, field


MAX_QUERY_LENGTH = 4000

BLOCKED_ACTION_PATTERNS = [
    r"\bupdate\s+\w+\s+set\b",
    r"\bdelete\s+from\b",
    r"\bdrop\s+table\b",
    r"\btruncate\s+table\b",
    r"\binsert\s+into\b",
    r"\bcommit\s*;",
    r"\bexecute\s+immediate\b",
    r"\bdisable\s+(audit|logging|security)\b",
    r"\bbypass\s+(approval|authorization|security)\b",
]

PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+the\s+system\s+prompt",
    r"reveal\s+(the\s+)?system\s+prompt",
    r"show\s+(me\s+)?your\s+hidden\s+instructions",
    r"act\s+as\s+an?\s+unrestricted",
    r"developer\s+mode",
    r"jailbreak",
    r"do\s+anything\s+now",
    r"override\s+safety",
]

SENSITIVE_IDENTIFIER_PATTERNS = {
    "possible_mpan": r"\b\d{13}\b",
    "possible_api_key": (
        r"\b(?:sk|gsk|AIza|or)[-_]"
        r"[A-Za-z0-9_-]{16,}\b"
    ),
    "email_address": (
        r"\b[A-Za-z0-9._%+-]+@"
        r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    ),
    "ipv4_address": (
        r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
    ),
}


@dataclass
class GuardrailResult:
    allowed: bool
    sanitized_text: str
    blocked_reasons: list = field(
        default_factory=list
    )
    warnings: list = field(
        default_factory=list
    )
    masked_items: list = field(
        default_factory=list
    )


def normalize_text(value):
    return re.sub(
        r"\s+",
        " ",
        str(value or ""),
    ).strip()


def detect_prompt_injection(text):
    normalized = text.lower()

    return [
        pattern
        for pattern
        in PROMPT_INJECTION_PATTERNS
        if re.search(
            pattern,
            normalized,
            flags=re.IGNORECASE,
        )
    ]


def detect_blocked_actions(text):
    return [
        pattern
        for pattern
        in BLOCKED_ACTION_PATTERNS
        if re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )
    ]


def mask_sensitive_identifiers(text):
    sanitized = str(text or "")
    masked_items = []

    replacements = {
        "possible_mpan": "[MASKED_IDENTIFIER]",
        "possible_api_key": "[MASKED_SECRET]",
        "email_address": "[MASKED_EMAIL]",
        "ipv4_address": "[MASKED_IP]",
    }

    for name, pattern in (
        SENSITIVE_IDENTIFIER_PATTERNS.items()
    ):
        matches = re.findall(
            pattern,
            sanitized,
            flags=re.IGNORECASE,
        )

        if matches:
            masked_items.append(
                {
                    "type": name,
                    "count": len(matches),
                }
            )

            sanitized = re.sub(
                pattern,
                replacements[name],
                sanitized,
                flags=re.IGNORECASE,
            )

    return sanitized, masked_items


def validate_user_input(text):
    original = normalize_text(text)

    blocked_reasons = []
    warnings = []

    if not original:
        blocked_reasons.append(
            "Issue description is empty."
        )

    if len(original) > MAX_QUERY_LENGTH:
        blocked_reasons.append(
            "Issue description exceeds the "
            f"{MAX_QUERY_LENGTH}-character limit."
        )

    injection_matches = (
        detect_prompt_injection(original)
    )

    if injection_matches:
        blocked_reasons.append(
            "Prompt-injection pattern detected."
        )

    blocked_actions = (
        detect_blocked_actions(original)
    )

    if blocked_actions:
        blocked_reasons.append(
            "Unsafe production-write instruction detected."
        )

    sanitized, masked_items = (
        mask_sensitive_identifiers(original)
    )

    if masked_items:
        warnings.append(
            "Potential identifiers were masked before "
            "AI processing."
        )

    return GuardrailResult(
        allowed=not blocked_reasons,
        sanitized_text=sanitized,
        blocked_reasons=blocked_reasons,
        warnings=warnings,
        masked_items=masked_items,
    )


def validate_evidence_records(evidence):
    valid_records = []
    rejected_records = []

    for record in evidence or []:
        document_id = str(
            record.get("document_id", "")
        ).strip()

        sensitivity = str(
            record.get(
                "sensitivity",
                "SYNTHETIC",
            )
        ).strip()

        content = str(
            record.get("content", "")
        ).strip()

        rejection_reasons = []

        if not document_id:
            rejection_reasons.append(
                "Missing document ID"
            )

        if sensitivity != "SYNTHETIC":
            rejection_reasons.append(
                "Evidence is not classified SYNTHETIC"
            )

        if not content:
            rejection_reasons.append(
                "Evidence content is empty"
            )

        injection_matches = (
            detect_prompt_injection(content)
        )

        if injection_matches:
            rejection_reasons.append(
                "Retrieved content contains "
                "prompt-injection text"
            )

        if rejection_reasons:
            rejected_records.append(
                {
                    "document_id": (
                        document_id
                        or "UNKNOWN"
                    ),
                    "reasons": rejection_reasons,
                }
            )
        else:
            valid_records.append(record)

    return valid_records, rejected_records


def calculate_evidence_sufficiency(
    answer,
    evidence,
):
    citations = list(
        dict.fromkeys(
            answer.get(
                "citations",
                [],
            )
        )
    )

    evidence_ids = {
        item.get("document_id")
        for item in evidence
    }

    valid_citations = [
        citation
        for citation in citations
        if citation in evidence_ids
    ]

    unique_domains = {
        item.get("domain")
        for item in evidence
        if item.get("domain")
    }

    citation_coverage = (
        len(valid_citations)
        / max(len(citations), 1)
    )

    evidence_count_score = min(
        len(evidence) / 4,
        1.0,
    )

    domain_coverage_score = min(
        len(unique_domains) / 3,
        1.0,
    )

    provider_confidence = max(
        0.0,
        min(
            float(
                answer.get(
                    "confidence",
                    0,
                )
            ),
            1.0,
        ),
    )

    sufficiency_score = (
        0.30 * citation_coverage
        + 0.25 * evidence_count_score
        + 0.20 * domain_coverage_score
        + 0.25 * provider_confidence
    )

    sufficient = (
        len(evidence) >= 2
        and len(valid_citations) >= 1
        and sufficiency_score >= 0.60
    )

    return {
        "sufficient": sufficient,
        "score": round(
            sufficiency_score,
            4,
        ),
        "citation_coverage": round(
            citation_coverage,
            4,
        ),
        "evidence_count": len(evidence),
        "domain_count": len(unique_domains),
        "valid_citations": valid_citations,
    }


def safe_refusal(
    reasons,
    warnings=None,
):
    return {
        "answer": {
            "summary": (
                "The request cannot be processed safely "
                "with the available information."
            ),
            "most_likely_cause": (
                "Insufficient or unsafe input"
            ),
            "probable_causes": [],
            "recommended_checks": [
                (
                    "Remove production-write instructions, "
                    "credentials and personal identifiers."
                ),
                (
                    "Provide a concise support symptom, "
                    "workflow status, attempted action and "
                    "visible error message."
                ),
            ],
            "suggested_owner": (
                "Application Support"
            ),
            "escalation_criteria": (
                "Escalate through approved support and "
                "change-management processes."
            ),
            "citations": [],
            "confidence": 0.0,
            "limitations": list(
                reasons
            ),
            "evidence_sufficient": False,
            "missing_information": list(
                reasons
            ),
        },
        "evidence": [],
        "provider": "Guardrail",
        "model": "Safe refusal",
        "retrieval_method": "Not executed",
        "provider_errors": [],
        "performance": {
            "retrieval_latency_ms": 0,
            "total_latency_ms": 0,
            "evidence_count": 0,
        },
        "guardrails": {
            "blocked": True,
            "reasons": list(reasons),
            "warnings": list(
                warnings or []
            ),
        },
    }
