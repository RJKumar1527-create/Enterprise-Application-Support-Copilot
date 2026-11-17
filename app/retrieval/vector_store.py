import hashlib
import json
import tomllib
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from google import genai
from google.genai import types


CHUNKS_PATH = Path("data/chunks.json")
VECTOR_PATH = Path("data/chunk_vectors.npz")
METADATA_PATH = Path("data/vector_index_metadata.json")
SECRETS_PATH = Path(".streamlit/secrets.toml")


def load_secrets():
    """Load local Streamlit secrets for command-line jobs."""
    if not SECRETS_PATH.exists():
        raise FileNotFoundError(
            ".streamlit/secrets.toml was not found."
        )

    with SECRETS_PATH.open("rb") as file:
        return tomllib.load(file)


def load_chunks():
    """Load persisted chunk records."""
    if not CHUNKS_PATH.exists():
        raise FileNotFoundError(
            "data/chunks.json was not found. "
            "Run scripts/run_ingestion.py first."
        )

    return json.loads(
        CHUNKS_PATH.read_text(encoding="utf-8")
    )


def normalize(vector):
    """Normalize a vector for cosine similarity."""
    array = np.asarray(
        vector,
        dtype=np.float32,
    )

    norm = np.linalg.norm(array)

    if norm == 0:
        return array

    return array / norm


def chunk_text(chunk):
    """Create embedding text with domain metadata."""
    return "\n".join(
        [
            f"Document ID: {chunk['document_id']}",
            f"Document Type: {chunk['document_type']}",
            f"Domain: {chunk['domain']}",
            f"Title: {chunk['title']}",
            f"Heading: {chunk['heading']}",
            f"Content: {chunk['content']}",
            f"Source: {chunk['source']}",
        ]
    )


def index_hash(chunks):
    """Create a stable hash of indexed chunk content."""
    content = json.dumps(
        [
            {
                "chunk_id": chunk["chunk_id"],
                "content_hash": chunk["content_hash"],
            }
            for chunk in chunks
        ],
        sort_keys=True,
    )

    return hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()


def build_vector_index():
    """Build and persist Gemini embeddings for all chunks."""
    secrets = load_secrets()

    api_key = secrets["GEMINI_API_KEY"]

    model_name = secrets.get(
        "GEMINI_EMBEDDING_MODEL",
        "gemini-embedding-001",
    )

    chunks = load_chunks()

    if not chunks:
        raise ValueError(
            "No chunks are available for indexing."
        )

    client = genai.Client(
        api_key=api_key
    )

    texts = [
        chunk_text(chunk)
        for chunk in chunks
    ]

    vectors = []
    batch_size = 50

    for start in range(
        0,
        len(texts),
        batch_size,
    ):
        batch = texts[
            start:start + batch_size
        ]

        response = client.models.embed_content(
            model=model_name,
            contents=batch,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=768,
            ),
        )

        for embedding in response.embeddings:
            vectors.append(
                normalize(embedding.values)
            )

    matrix = np.vstack(vectors)

    VECTOR_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    np.savez_compressed(
        VECTOR_PATH,
        vectors=matrix,
    )

    metadata = {
        "index_version": "1.0",
        "embedding_model": model_name,
        "document_count": len(
            {
                chunk["document_id"]
                for chunk in chunks
            }
        ),
        "chunk_count": len(chunks),
        "dimensions": int(
            matrix.shape[1]
        ),
        "index_hash": index_hash(chunks),
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "status": "HEALTHY",
    }

    METADATA_PATH.write_text(
        json.dumps(
            metadata,
            indent=2,
        ),
        encoding="utf-8",
    )

    return metadata


def load_vector_index():
    """Load vectors and metadata."""
    if not VECTOR_PATH.exists():
        raise FileNotFoundError(
            "Vector index does not exist."
        )

    if not METADATA_PATH.exists():
        raise FileNotFoundError(
            "Vector metadata does not exist."
        )

    vectors = np.load(
        VECTOR_PATH
    )["vectors"]

    metadata = json.loads(
        METADATA_PATH.read_text(
            encoding="utf-8"
        )
    )

    return vectors, metadata


def embed_query(query):
    """Generate a normalized Gemini query embedding."""
    secrets = load_secrets()

    api_key = secrets["GEMINI_API_KEY"]

    model_name = secrets.get(
        "GEMINI_EMBEDDING_MODEL",
        "gemini-embedding-001",
    )

    client = genai.Client(
        api_key=api_key
    )

    response = client.models.embed_content(
        model=model_name,
        contents=[query],
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=768,
        ),
    )

    return normalize(
        response.embeddings[0].values
    )
