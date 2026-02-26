import logging
from datetime import datetime, timezone

# Configure module-level logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("monday-bi-agent")


class ToolTrace:
    """Captures a chain-of-thought trace for each query for transparency."""

    def __init__(self):
        self.logs: list[dict] = []

    def add(self, message: str):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": message,
        }
        self.logs.append(entry)
        logger.info(message)

    def get(self) -> list[dict]:
        return self.logs