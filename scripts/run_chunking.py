import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
import argparse
import json
from pathlib import Path

from app.ingestion.pipeline import ingest


SOURCE_PATH = Path(
    "knowledge_base/source/domain_corpus.json"
)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--max-words",
        type=int,
        default=220,
    )

    parser.add_argument(
        "--overlap",
        type=int,
        default=1,
    )

    arguments = parser.parse_args()

    result = ingest(
        [SOURCE_PATH],
        arguments.max_words,
        arguments.overlap,
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
