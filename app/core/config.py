from dataclasses import dataclass
import os

@dataclass(frozen=True)
class Settings:
    app_name: str = "Enterprise Application Support Copilot"
    environment: str = os.getenv("APP_ENV", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    chunk_max_words: int = int(os.getenv("CHUNK_MAX_WORDS", "220"))
    chunk_overlap_sentences: int = int(os.getenv("CHUNK_OVERLAP_SENTENCES", "1"))

settings = Settings()
