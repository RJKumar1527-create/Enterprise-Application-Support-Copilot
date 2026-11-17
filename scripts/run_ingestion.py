import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
import json
from pathlib import Path

from app.core.config import settings
from app.ingestion.pipeline import ingest


SOURCE_PATH = Path(
    "knowledge_base/source/domain_corpus.json"
)


def main():
    result = ingest(
        [SOURCE_PATH],
        settings.chunk_max_words,
        settings.chunk_overlap_sentences,
    )

    summary = {
        key: value
        for key, value in result.items()
        if key != "chunk_records"
    }

    print(
        json.dumps(
            summary,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
