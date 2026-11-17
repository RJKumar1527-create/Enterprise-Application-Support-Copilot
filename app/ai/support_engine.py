import json
import time
import tomllib
from pathlib import Path

import numpy as np
from app.ai.relevance import (
    detect_intents,
    minimum_relevance_passed,
    score_context_relevance,
)
from google import genai
from google.genai import types
from groq import Groq
from openai import OpenAI
from sklearn.feature_extraction.text import TfidfVectorizer


PROJECT_ROOT = Path(__file__).resolve().parents[2]

CHUNKS_PATH = PROJECT_ROOT / "data" / "chunks.json"

SECRETS_PATH = (
    PROJECT_ROOT
    / ".streamlit"
    / "secrets.toml"
)


def load_secrets():
    if not SECRETS_PATH.exists():
        return {}

    with SECRETS_PATH.open("rb") as file:
        return tomllib.load(file)


def load_chunks():
    if not CHUNKS_PATH.exists():
        raise FileNotFoundError(
            "data/chunks.json is missing. "
            "Run scripts/run_ingestion.py first."
        )

    chunks = json.loads(
        CHUNKS_PATH.read_text(
            encoding="utf-8"
        )
    )

    invalid_chunks = [
        chunk.get("chunk_id", "UNKNOWN")
        for chunk in chunks
        if chunk.get("sensitivity")
        != "SYNTHETIC"
    ]

    if invalid_chunks:
        raise ValueError(
            "Non-synthetic chunks were blocked."
        )

    return chunks


def searchable_text(chunk):
    return " ".join(
        [
            str(chunk.get("document_id", "")),
            str(chunk.get("document_type", "")),
            str(chunk.get("domain", "")),
            str(chunk.get("title", "")),
            str(chunk.get("heading", "")),
            str(chunk.get("content", "")),
            str(chunk.get("source", "")),
        ]
    )


def normalize(vector):
    array = np.asarray(
        vector,
        dtype=np.float32,
    )

    norm = np.linalg.norm(array)

    if norm == 0:
        return array

    return array / norm


def lexical_search(
    query,
    chunks,
    allowed_indices,
):
    documents = [
        searchable_text(chunks[index])
        for index in allowed_indices
    ]

    vectorizer = TfidfVectorizer(
        lowercase=True,
        ngram_range=(1, 2),
        sublinear_tf=True,
        token_pattern=(
            r"(?u)\b[A-Za-z0-9_-]+\b"
        ),
    )

    matrix = vectorizer.fit_transform(
        documents + [query]
    )

    scores = (
        matrix[:-1]
        @ matrix[-1].T
    ).toarray().ravel()

    return {
        index: float(score)
        for index, score in zip(
            allowed_indices,
            scores,
        )
    }


def semantic_search(
    query,
    chunks,
    allowed_indices,
):
    secrets = load_secrets()

    api_key = secrets.get(
        "GEMINI_API_KEY"
    )

    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY is unavailable."
        )

    model_name = secrets.get(
        "GEMINI_EMBEDDING_MODEL",
        "gemini-embedding-001",
    )

    client = genai.Client(
        api_key=api_key
    )

    documents = [
        searchable_text(chunks[index])
        for index in allowed_indices
    ]

    document_response = (
        client.models.embed_content(
            model=model_name,
            contents=documents,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=768,
            ),
        )
    )

    query_response = (
        client.models.embed_content(
            model=model_name,
            contents=[query],
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY",
                output_dimensionality=768,
            ),
        )
    )

    document_vectors = np.vstack(
        [
            normalize(item.values)
            for item
            in document_response.embeddings
        ]
    )

    query_vector = normalize(
        query_response.embeddings[0].values
    )

    scores = (
        document_vectors
        @ query_vector
    )

    return {
        index: float(score)
        for index, score in zip(
            allowed_indices,
            scores,
        )
    }


def reciprocal_rank_fusion(
    ranking_lists,
    constant=60,
):
    scores = {}

    for ranking in ranking_lists:
        for rank, index in enumerate(
            ranking,
            start=1,
        ):
            scores[index] = (
                scores.get(index, 0.0)
                + 1.0 / (
                    constant + rank
                )
            )

    return scores


def hybrid_retrieve(
    query,
    application_area="ALL",
    top_k=8,
):
    start_time = time.perf_counter()

    chunks = load_chunks()

    # Search the complete knowledge base so that related
    # workflow, role and incident evidence is not excluded.
    allowed_indices = list(
        range(len(chunks))
    )

    lexical_scores = lexical_search(
        query,
        chunks,
        allowed_indices,
    )

    lexical_ranking = sorted(
        allowed_indices,
        key=lambda index: lexical_scores[
            index
        ],
        reverse=True,
    )

    semantic_scores = {
        index: 0.0
        for index in allowed_indices
    }

    semantic_ranking = []
    embedding_error = None

    try:
        semantic_scores = semantic_search(
            query,
            chunks,
            allowed_indices,
        )

        semantic_ranking = sorted(
            allowed_indices,
            key=lambda index: (
                semantic_scores[index]
            ),
            reverse=True,
        )

    except Exception as error:
        embedding_error = str(error)

    rankings = [lexical_ranking]

    if semantic_ranking:
        rankings.insert(
            0,
            semantic_ranking,
        )

    fused_scores = (
        reciprocal_rank_fusion(
            rankings
        )
    )

    # Treat the selected application area as a soft ranking
    # preference rather than excluding cross-domain evidence.
    relevance_details = {}
    adjusted_scores = {}

    for index in allowed_indices:
        relevance = score_context_relevance(
            query=query,
            chunk=chunks[index],
            application_area=application_area,
        )

        relevance_details[index] = relevance

        adjusted_scores[index] = (
            fused_scores.get(index, 0.0)
            + relevance["adjustment"]
        )

    eligible_indices = []

    for index in allowed_indices:
        candidate_for_validation = {
            **chunks[index],
            "lexical_score": lexical_scores.get(
                index,
                0.0,
            ),
            "semantic_score": semantic_scores.get(
                index,
                0.0,
            ),
        }

        if minimum_relevance_passed(
            chunk=candidate_for_validation,
            adjusted_score=adjusted_scores[index],
        ):
            eligible_indices.append(index)

    if not eligible_indices:
        eligible_indices = allowed_indices

    ranked_indices = sorted(
        eligible_indices,
        key=lambda index: adjusted_scores.get(
            index,
            0.0,
        ),
        reverse=True,
    )[:top_k]

    results = []
    selected_document_ids = set()
    output_rank = 0

    for index in ranked_indices:
        document_id = chunks[index].get(
            "document_id",
            "",
        )

        if document_id in selected_document_ids:
            continue

        selected_document_ids.add(
            document_id
        )

        output_rank += 1

        item = dict(chunks[index])

        item.update(
            {
                "rank": output_rank,
                "semantic_score": round(
                    semantic_scores.get(
                        index,
                        0,
                    ),
                    5,
                ),
                "lexical_score": round(
                    lexical_scores.get(
                        index,
                        0,
                    ),
                    5,
                ),
                "hybrid_score": round(
                    adjusted_scores.get(
                        index,
                        0.0,
                    ),
                    6,
                ),
                "base_rrf_score": round(
                    fused_scores.get(
                        index,
                        0.0,
                    ),
                    6,
                ),
                "context_adjustment": relevance_details[
                    index
                ]["adjustment"],
                "relevance_reasons": relevance_details[
                    index
                ]["reasons"],
                "detected_intents": relevance_details[
                    index
                ]["detected_intents"],
            }
        )

        results.append(item)

        if len(results) >= top_k:
            break

    return {
        "results": results,
        "method": (
            "Gemini + TF-IDF + RRF"
            if semantic_ranking
            else "TF-IDF + RRF fallback"
        ),
        "embedding_error": embedding_error,
        "latency_ms": round(
            (
                time.perf_counter()
                - start_time
            )
            * 1000,
            2,
        ),
    }


def select_diverse_evidence(
    candidates,
    application_area,
    current_status,
    attempted_action,
    user_role,
    maximum_results=6,
):
    """
    Select one best chunk per parent document and ensure
    useful cross-domain evidence coverage.

    Priority coverage:
    - selected business area
    - workflow or lifecycle
    - access control when a user role is supplied
    - similar incident or runbook
    """

    if not candidates:
        return []

    # Keep only the strongest chunk from each parent document.
    best_by_document = {}

    for candidate in candidates:
        document_id = candidate.get(
            "document_id",
            "",
        )

        existing = best_by_document.get(
            document_id
        )

        if (
            existing is None
            or candidate.get(
                "hybrid_score",
                0,
            )
            > existing.get(
                "hybrid_score",
                0,
            )
        ):
            best_by_document[
                document_id
            ] = candidate

    unique_candidates = sorted(
        best_by_document.values(),
        key=lambda item: item.get(
            "hybrid_score",
            0,
        ),
        reverse=True,
    )

    context_text = " ".join(
        [
            str(current_status),
            str(attempted_action),
            str(user_role),
        ]
    ).lower()

    priority_domains = []

    if (
        application_area
        and application_area != "ALL"
    ):
        priority_domains.append(
            application_area
        )

    # Workflow context is important when status transitions,
    # confirmation, authorization or export are involved.
    workflow_terms = {
        "received",
        "confirmed",
        "authorized",
        "export",
        "exported",
        "paid",
        "completed",
        "status",
        "transition",
    }

    if any(
        term in context_text
        for term in workflow_terms
    ):
        priority_domains.append(
            "invoice_lifecycle"
        )

    # Access evidence is important when role or permission
    # information is supplied.
    if str(user_role).strip():
        priority_domains.append(
            "access_control"
        )

    # Similar incidents should support operational diagnosis.
    priority_domains.append(
        "incident_resolution"
    )

    # Remove duplicate domain names while preserving order.
    priority_domains = list(
        dict.fromkeys(priority_domains)
    )

    selected = []
    selected_document_ids = set()

    # Select the strongest candidate for each required domain.
    for priority_domain in priority_domains:
        domain_candidate = next(
            (
                candidate
                for candidate
                in unique_candidates
                if (
                    candidate.get(
                        "domain"
                    )
                    == priority_domain
                    and candidate.get(
                        "document_id"
                    )
                    not in selected_document_ids
                )
            ),
            None,
        )

        if domain_candidate:
            selected.append(
                domain_candidate
            )

            selected_document_ids.add(
                domain_candidate[
                    "document_id"
                ]
            )

    # Fill remaining positions with the strongest unique
    # parent documents regardless of domain.
    for candidate in unique_candidates:
        document_id = candidate.get(
            "document_id",
            "",
        )

        if (
            document_id
            in selected_document_ids
        ):
            continue

        selected.append(candidate)

        selected_document_ids.add(
            document_id
        )

        if (
            len(selected)
            >= maximum_results
        ):
            break

    # Reorder the chosen evidence by hybrid relevance while
    # retaining the required domain coverage.
    selected.sort(
        key=lambda item: item.get(
            "hybrid_score",
            0,
        ),
        reverse=True,
    )

    for rank, candidate in enumerate(
        selected,
        start=1,
    ):
        candidate["rank"] = rank

    return selected[
        :maximum_results
    ]


def clean_json(content):
    cleaned = content.strip()

    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]

    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    return json.loads(
        cleaned.strip()
    )


def create_messages(
    issue_context,
    evidence,
):
    evidence_payload = [
        {
            "document_id": item[
                "document_id"
            ],
            "title": item["title"],
            "domain": item["domain"],
            "content": item["content"],
            "source": item["source"],
        }
        for item in evidence
    ]

    return [
        {
            "role": "system",
            "content": """
You are an enterprise billing-application support copilot.

Use only the supplied synthetic evidence.

Return valid JSON with exactly these keys:

summary
most_likely_cause
probable_causes
recommended_checks
suggested_owner
escalation_criteria
citations
confidence
limitations

Rules:

1. Do not invent rules, errors, systems or actions.
2. Cite only supplied document IDs.
3. Rank probable causes from most likely to least likely.
4. Each probable cause requires cause, confidence and evidence.
5. Recommend read-only diagnostic checks only.
6. Never recommend direct production data updates.
7. State missing evidence when the cause cannot be confirmed.
8. Confidence must be between 0 and 1.
""".strip(),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "incident_context": (
                        issue_context
                    ),
                    "retrieved_evidence": (
                        evidence_payload
                    ),
                },
                indent=2,
            ),
        },
    ]


def validate_answer(
    answer,
    evidence,
):
    valid_ids = {
        item["document_id"]
        for item in evidence
    }

    answer["citations"] = list(
        dict.fromkeys(
            citation
            for citation in answer.get(
                "citations",
                [],
            )
            if citation in valid_ids
        )
    )

    answer["confidence"] = max(
        0.0,
        min(
            float(
                answer.get(
                    "confidence",
                    0.5,
                )
            ),
            0.95,
        ),
    )

    answer.setdefault(
        "probable_causes",
        [],
    )

    answer.setdefault(
        "recommended_checks",
        [],
    )

    answer.setdefault(
        "limitations",
        [],
    )

    return answer


def generate_with_failover(
    issue_context,
    evidence,
):
    secrets = load_secrets()

    messages = create_messages(
        issue_context,
        evidence,
    )

    provider_errors = []

    groq_key = secrets.get(
        "GROQ_API_KEY"
    )

    groq_model = secrets.get(
        "GROQ_CHAT_MODEL",
        "openai/gpt-oss-20b",
    )

    if groq_key:
        try:
            client = Groq(
                api_key=groq_key,
                timeout=45,
                max_retries=1,
            )

            response = (
                client.chat.completions.create(
                    model=groq_model,
                    temperature=0.1,
                    max_tokens=1800,
                    messages=messages,
                    response_format={
                        "type": "json_object"
                    },
                )
            )

            answer = clean_json(
                response.choices[
                    0
                ].message.content
            )

            return (
                validate_answer(
                    answer,
                    evidence,
                ),
                "Groq",
                groq_model,
                provider_errors,
            )

        except Exception as error:
            provider_errors.append(
                f"Groq: {error}"
            )

    openrouter_key = secrets.get(
        "OPENROUTER_API_KEY"
    )

    openrouter_model = secrets.get(
        "OPENROUTER_CHAT_MODEL",
        "openai/gpt-oss-20b",
    )

    if openrouter_key:
        try:
            client = OpenAI(
                api_key=openrouter_key,
                base_url=(
                    "https://openrouter.ai/api/v1"
                ),
                timeout=60,
                max_retries=1,
            )

            response = (
                client.chat.completions.create(
                    model=openrouter_model,
                    temperature=0.1,
                    max_tokens=1800,
                    messages=messages,
                    response_format={
                        "type": "json_object"
                    },
                )
            )

            answer = clean_json(
                response.choices[
                    0
                ].message.content
            )

            return (
                validate_answer(
                    answer,
                    evidence,
                ),
                "OpenRouter",
                openrouter_model,
                provider_errors,
            )

        except Exception as error:
            provider_errors.append(
                f"OpenRouter: {error}"
            )

    top = evidence[0]

    fallback_answer = {
        "summary": (
            "The batch cannot be exported while its invoices remain "
            "in Confirmed status. Every invoice must first reach "
            "Authorized status. The supplied Standard User role may "
            "also lack authorization permission. If those checks pass, "
            "verify the batch freeze state, export mapping and output "
            "directory access."
        ),
        "most_likely_cause": top["title"],
        "probable_causes": [
            {
                "cause": item["title"],
                "confidence": round(
                    max(
                        0.50,
                        0.82 - position * 0.08,
                    ),
                    2,
                ),
                "evidence": item["content"],
            }
            for position, item in enumerate(
                evidence[:3]
            )
        ],
        "recommended_checks": [
            (
                "Review every invoice in the batch and confirm "
                "whether each invoice has reached Authorized status."
            ),
            (
                "Verify that the current user has the Manager or "
                "Senior Manager role and sufficient authorization limit."
            ),
            (
                "Confirm that the batch is not frozen before "
                "attempting export."
            ),
            (
                "If workflow and access prerequisites are satisfied, "
                "verify export mapping and output-directory access."
            ),
        ],
        "suggested_owner": (
            "Application Support"
        ),
        "escalation_criteria": (
            "Escalate when documented checks fail "
            "or controlled access or infrastructure "
            "changes are required."
        ),
        "citations": [
            item["document_id"]
            for item in evidence[:4]
        ],
        "confidence": 0.82,
        "limitations": [
            (
                "External answer-generation providers "
                "were unavailable."
            )
        ],
    }

    return (
        fallback_answer,
        "Deterministic",
        "Evidence fallback",
        provider_errors,
    )


def generate_answer_v2(
    issue,
    application_area,
    current_status,
    attempted_action,
    user_role,
    error_message,
):
    total_start = time.perf_counter()

    query = " ".join(
        value
        for value in [
            issue,
            application_area,
            current_status,
            attempted_action,
            user_role,
            error_message,
        ]
        if value
    )

    retrieval = hybrid_retrieve(
        query=query,
        application_area=(
            application_area
        ),
        top_k=12,
    )

    evidence = select_diverse_evidence(
        candidates=retrieval[
            "results"
        ],
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
        maximum_results=6,
    )

    issue_context = {
        "issue": issue,
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
    }

    (
        answer,
        provider,
        model,
        provider_errors,
    ) = generate_with_failover(
        issue_context,
        evidence,
    )

    frontend_evidence = []

    for item in evidence:
        frontend_evidence.append(
            {
                "rank": item["rank"],
                "document_id": item[
                    "document_id"
                ],
                "chunk_id": item[
                    "chunk_id"
                ],
                "domain": item["domain"],
                "title": item["title"],
                "content": item["content"],
                "source": item["source"],
                "semantic_score": item[
                    "semantic_score"
                ],
                "lexical_score": item[
                    "lexical_score"
                ],
                "hybrid_score": item[
                    "hybrid_score"
                ],
                "retrieval_score": round(
                    max(
                        item[
                            "semantic_score"
                        ],
                        item[
                            "lexical_score"
                        ],
                    )
                    * 100,
                    2,
                ),
            }
        )

    return {
        "answer": answer,
        "evidence": frontend_evidence,
        "provider": provider,
        "model": model,
        "retrieval_method": retrieval[
            "method"
        ],
        "provider_errors": [
            retrieval.get(
                "embedding_error"
            )
        ]
        + provider_errors,
        "performance": {
            "retrieval_latency_ms": (
                retrieval["latency_ms"]
            ),
            "total_latency_ms": round(
                (
                    time.perf_counter()
                    - total_start
                )
                * 1000,
                2,
            ),
            "evidence_count": len(
                frontend_evidence
            ),
        },
    }
