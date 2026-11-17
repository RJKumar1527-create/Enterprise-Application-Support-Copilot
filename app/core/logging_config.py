import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Format application log records as JSON."""

    def format(self, record):
        return json.dumps(
            {
                "timestamp": datetime.now(
                    timezone.utc
                ).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
        )


def get_application_logger(
    name="enterprise_support_copilot",
    level="INFO",
):
    """
    Create an application-specific logger.

    Streamlit root logging handlers are not modified.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)

    return logger
