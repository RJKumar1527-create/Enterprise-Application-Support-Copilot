import json
from pathlib import Path

import pandas as pd
import streamlit as st

from app.core.config import settings
from app.repository.metadata import (
    initialize,
    list_runs,
)


st.set_page_config(
    page_title=settings.app_name,
    page_icon="🔎",
    layout="wide",
)


CHUNKS_PATH = Path("data/chunks.json")

MANIFEST_PATH = Path(
    "data/chunk_manifest.json"
)

SOURCE_PATH = Path(
    "knowledge_base/source/domain_corpus.json"
)


try:
    initialize()

except Exception as error:
    st.error(
        "Metadata database initialization failed."
    )

    st.exception(error)
    st.stop()


def load_chunks():
    """Load generated chunks without processing documents."""
    if not CHUNKS_PATH.exists():
        return []

    return json.loads(
        CHUNKS_PATH.read_text(
            encoding="utf-8"
        )
    )


def load_manifest():
    """Load the current chunk manifest."""
    if not MANIFEST_PATH.exists():
        return {}

    return json.loads(
        MANIFEST_PATH.read_text(
            encoding="utf-8"
        )
    )


chunks = load_chunks()
manifest = load_manifest()
audit_runs = list_runs()


st.title(
    "Enterprise Application Support Copilot"
)

st.caption(
    "Production-Grade Domain RAG for Billing Operations "
    "and Incident Resolution"
)

st.info(
    "Document processing runs through controlled command-line "
    "jobs. This dashboard displays the persisted results without "
    "triggering Streamlit reruns."
)


setup_tab, ingestion_tab, chunking_tab = st.tabs(
    [
        "1. Production Setup",
        "2. Enterprise Ingestion",
        "3. Advanced Chunking & Audit",
    ]
)


# ---------------------------------------------------------
# Step 1
# ---------------------------------------------------------
with setup_tab:
    st.subheader(
        "Step 1: Production Setup"
    )

    st.success(
        "Modular enterprise foundation is operational."
    )

    status1, status2, status3, status4 = (
        st.columns(4)
    )

    status1.metric(
        "Environment",
        settings.environment,
    )

    status2.metric(
        "Source Corpus",
        (
            "Available"
            if SOURCE_PATH.exists()
            else "Missing"
        ),
    )

    status3.metric(
        "Metadata Store",
        "SQLite",
    )

    status4.metric(
        "Ingestion Runs",
        len(audit_runs),
    )

    st.markdown(
        "### Processing Commands"
    )

    st.code(
        (
            "python scripts\\run_ingestion.py\n"
            "python scripts\\run_chunking.py "
            "--max-words 220 --overlap 1"
        ),
        language="powershell",
    )

    st.warning(
        "Only documents marked SYNTHETIC are accepted. "
        "Client specifications, production incidents, real MPANs, "
        "internal SQL and credentials must not be ingested."
    )


# ---------------------------------------------------------
# Step 2
# ---------------------------------------------------------
with ingestion_tab:
    st.subheader(
        "Step 2: Enterprise Ingestion"
    )

    if not audit_runs:
        st.warning(
            "No ingestion result is available."
        )

        st.code(
            "python scripts\\run_ingestion.py",
            language="powershell",
        )

    else:
        latest_run = audit_runs[0]

        metric1, metric2, metric3, metric4 = (
            st.columns(4)
        )

        metric1.metric(
            "Documents",
            latest_run.get(
                "documents",
                0,
            ),
        )

        metric2.metric(
            "Chunks",
            latest_run.get(
                "chunks",
                0,
            ),
        )

        metric3.metric(
            "Added / Changed",
            (
                latest_run.get(
                    "added",
                    0,
                )
                + latest_run.get(
                    "changed",
                    0,
                )
            ),
        )

        metric4.metric(
            "Status",
            latest_run.get(
                "status",
                "UNKNOWN",
            ),
        )

        if (
            latest_run.get("status")
            == "COMPLETED"
        ):
            st.success(
                "Validated ingestion completed successfully."
            )

        st.markdown(
            "### Latest Ingestion Run"
        )

        st.dataframe(
            pd.DataFrame(
                [latest_run]
            ),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown(
        "### Source Information"
    )

    source_information = {
        "source_file": str(SOURCE_PATH),
        "source_exists": SOURCE_PATH.exists(),
        "source_size_kb": (
            round(
                SOURCE_PATH.stat().st_size
                / 1024,
                2,
            )
            if SOURCE_PATH.exists()
            else 0
        ),
        "classification": "SYNTHETIC",
        "supported_formats": [
            "JSON",
            "Markdown",
            "TXT",
            "CSV",
        ],
    }

    st.json(source_information)


# ---------------------------------------------------------
# Step 3
# ---------------------------------------------------------
with chunking_tab:
    st.subheader(
        "Step 3: Advanced Chunking & Audit"
    )

    if not chunks:
        st.warning(
            "No generated chunks are available."
        )

        st.code(
            (
                "python scripts\\run_chunking.py "
                "--max-words 220 --overlap 1"
            ),
            language="powershell",
        )

    else:
        chunks_df = pd.DataFrame(chunks)

        metric1, metric2, metric3, metric4 = (
            st.columns(4)
        )

        metric1.metric(
            "Generated Chunks",
            len(chunks_df),
        )

        metric2.metric(
            "Parent Documents",
            chunks_df[
                "document_id"
            ].nunique(),
        )

        metric3.metric(
            "Domains",
            chunks_df[
                "domain"
            ].nunique(),
        )

        metric4.metric(
            "Estimated Tokens",
            int(
                chunks_df[
                    "token_estimate"
                ].sum()
            ),
        )

        st.markdown(
            "### Chunk Quality Inspection"
        )

        display_columns = [
            "chunk_id",
            "document_id",
            "parent_id",
            "document_type",
            "domain",
            "title",
            "heading",
            "version",
            "token_estimate",
            "content_hash",
            "content",
        ]

        available_columns = [
            column
            for column in display_columns
            if column in chunks_df.columns
        ]

        st.dataframe(
            chunks_df[
                available_columns
            ],
            use_container_width=True,
            hide_index=True,
            height=520,
        )

        st.markdown(
            "### Chunk Statistics"
        )

        statistics = {
            "minimum_tokens": int(
                chunks_df[
                    "token_estimate"
                ].min()
            ),
            "maximum_tokens": int(
                chunks_df[
                    "token_estimate"
                ].max()
            ),
            "average_tokens": round(
                chunks_df[
                    "token_estimate"
                ].mean(),
                2,
            ),
            "manifest_entries": len(
                manifest
            ),
            "all_synthetic": bool(
                (
                    chunks_df[
                        "sensitivity"
                    ]
                    == "SYNTHETIC"
                ).all()
            ),
        }

        st.json(statistics)

    st.markdown("---")
    st.markdown(
        "### Ingestion Audit History"
    )

    if audit_runs:
        st.dataframe(
            pd.DataFrame(audit_runs),
            use_container_width=True,
            hide_index=True,
        )

    else:
        st.info(
            "No ingestion audit history is available."
        )
