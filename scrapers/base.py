import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from database.repositories.sources import SourceRepository

logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    def __init__(self, name: str, source_url: str, source_type: str, trust_score: int):
        self.name = name
        self.source_url = source_url
        self.source_type = source_type
        self.trust_score = trust_score
        self.source_id: Optional[str] = None

    async def init_source(self):
        source = await SourceRepository.get_or_create_source(
            url=self.source_url,
            source_type=self.source_type,
            trust_score=self.trust_score
        )
        if source:
            self.source_id = source.get("id")

    @abstractmethod
    async def run(self) -> int:
        """Runs the scraper and returns the count of collected posts."""
        pass
