import re


INTENT_PROFILES = {
    "batch_export": {
        "trigger_terms": {
            "batch",
            "export",
            "exported",
            "output file",
            "confirmed batch",
        },
        "preferred_domains": {
            "batch_processing",
            "invoice_lifecycle",
            "access_control",
            "incident_resolution",
        },
        "preferred_documents": {
            "BATCH-001",
            "WF-001",
            "ACC-001",
            "INC-001",
        },
        "negative_documents": {
            "INC-002",
            "D21-001",
            "D21-002",
        },
        "negative_terms": {
            "d2021 file",
            "input location",
            "file remains unprocessed",
            "zhv",
            "zpt",
        },
    },
    "d2021_processing": {
        "trigger_terms": {
            "d2021",
            "zhv",
            "zpt",
            "clo",
            "mpc",
            "bcd",
            "ccd",
            "input file",
            "file remains",
        },
        "preferred_domains": {
            "d2021",
            "incident_resolution",
        },
        "preferred_documents": {
            "D21-001",
            "D21-002",
            "INC-002",
        },
        "negative_documents": set(),
        "negative_terms": set(),
    },
    "authorization": {
        "trigger_terms": {
            "authorize",
            "authorized",
            "authorization",
            "permission",
            "role",
            "manager",
            "standard user",
        },
        "preferred_domains": {
            "access_control",
            "invoice_lifecycle",
            "batch_processing",
        },
        "preferred_documents": {
            "ACC-001",
            "WF-001",
            "BATCH-001",
        },
        "negative_documents": {
            "INC-002",
        },
        "negative_terms": {
            "file remains unprocessed",
            "input location",
        },
    },
}


def normalize_text(value):
    """Normalize text for deterministic comparisons."""
    return re.sub(
        r"\s+",
        " ",
        str(value or "").lower(),
    ).strip()


def detect_intents(query):
    """Detect one or more support intents."""
    normalized_query = normalize_text(query)

    detected = []

    for intent_name, profile in (
        INTENT_PROFILES.items()
    ):
        matched_terms = [
            term
            for term in profile[
                "trigger_terms"
            ]
            if term in normalized_query
        ]

        if matched_terms:
            detected.append(
                {
                    "intent": intent_name,
                    "matched_terms": (
                        matched_terms
                    ),
                    "profile": profile,
                }
            )

    if not detected:
        detected.append(
            {
                "intent": "general_support",
                "matched_terms": [],
                "profile": {
                    "preferred_domains": set(),
                    "preferred_documents": set(),
                    "negative_documents": set(),
                    "negative_terms": set(),
                },
            }
        )

    return detected


def score_context_relevance(
    query,
    chunk,
    application_area="ALL",
):
    """
    Return an intent-aware score adjustment and reasons.

    Positive values boost directly relevant evidence.
    Negative values suppress contextually unrelated evidence.
    """
    detected_intents = detect_intents(query)

    document_id = str(
        chunk.get("document_id", "")
    )

    domain = str(
        chunk.get("domain", "")
    )

    chunk_text = normalize_text(
        " ".join(
            [
                chunk.get("title", ""),
                chunk.get("heading", ""),
                chunk.get("content", ""),
            ]
        )
    )

    adjustment = 0.0
    reasons = []

    if (
        application_area != "ALL"
        and domain == application_area
    ):
        adjustment += 0.025
        reasons.append(
            "Matches selected application area"
        )

    for detected in detected_intents:
        profile = detected["profile"]

        if (
            document_id
            in profile[
                "preferred_documents"
            ]
        ):
            adjustment += 0.050
            reasons.append(
                "Preferred evidence for detected intent"
            )

        if (
            domain
            in profile[
                "preferred_domains"
            ]
        ):
            adjustment += 0.018
            reasons.append(
                "Relevant domain for detected intent"
            )

        if (
            document_id
            in profile[
                "negative_documents"
            ]
        ):
            adjustment -= 0.090
            reasons.append(
                "Document conflicts with detected intent"
            )

        negative_term_matches = [
            term
            for term in profile[
                "negative_terms"
            ]
            if term in chunk_text
        ]

        if negative_term_matches:
            adjustment -= min(
                0.080,
                0.025
                * len(
                    negative_term_matches
                ),
            )

            reasons.append(
                "Contains terms unrelated to "
                "the detected incident"
            )

    return {
        "adjustment": round(
            adjustment,
            6,
        ),
        "reasons": list(
            dict.fromkeys(reasons)
        ),
        "detected_intents": [
            item["intent"]
            for item in detected_intents
        ],
    }


def minimum_relevance_passed(
    chunk,
    adjusted_score,
):
    """
    Remove weak evidence unless the document is a specifically
    preferred rule selected by the intent profile.
    """
    document_id = str(
        chunk.get("document_id", "")
    )

    preferred_documents = {
        document
        for profile
        in INTENT_PROFILES.values()
        for document
        in profile[
            "preferred_documents"
        ]
    }

    if document_id in preferred_documents:
        return adjusted_score > 0

    lexical_score = float(
        chunk.get("lexical_score", 0)
    )

    semantic_score = float(
        chunk.get("semantic_score", 0)
    )

    return (
        adjusted_score > 0
        and (
            lexical_score >= 0.015
            or semantic_score >= 0.30
        )
    )
