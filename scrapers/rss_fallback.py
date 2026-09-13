import logging
import asyncio
from typing import List, Dict, Any
import feedparser
from scrapers.base import BaseScraper
from database.repositories.sources import SourceRepository

logger = logging.getLogger(__name__)

class MediaRssFallbackScraper(BaseScraper):
    """
    RSS fallback parser for major media (Banki.ru, TourDom, Profi.Travel, RBC).
    Activates when primary official scrapers fail or during regular aggregation.
    """
    DEFAULT_FEEDS = [
        {"name": "Banki.ru", "url": "https://www.banki.ru/xml/news.rss"},
        {"name": "TourDom", "url": "https://www.tourdom.ru/news/rss/"},
        {"name": "Profi.Travel", "url": "https://profi.travel/rss/news"}
    ]

    KEYWORDS = [
        "unionpay", "карта", "карты", "оплат", "банк", "за рубежом", 
        "турци", "оаэ", "египет", "таиланд", "казахстан", "грузи", "армени"
    ]

    def __init__(self, feed_url: str = "https://www.banki.ru/xml/news.rss", feed_name: str = "Banki.ru"):
        super().__init__(
            name=f"RSS_{feed_name}",
            source_url=feed_url,
            source_type="media",
            trust_score=7  # Media has trust score 7
        )

    async def run(self, max_items: int = 20) -> int:
        await self.init_source()
        if not self.source_id:
            logger.error(f"Cannot initialize RSS source for {self.source_url}")
            return 0

        try:
            logger.info(f"Fetching RSS feed from {self.source_url}...")
            # feedparser is synchronous, run in executor
            loop = asyncio.get_running_loop()
            feed = await loop.run_in_executor(None, feedparser.parse, self.source_url)

            if feed.bozo and not feed.entries:
                logger.warning(f"Failed to parse RSS feed from {self.source_url}: {feed.bozo_exception}")
                await self.failed_request_handler(str(feed.bozo_exception))
                return 0

            saved = 0
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                link = entry.get("link", "")
                full_text = f"{title}\n{summary}\nСсылка: {link}"

                # Keyword check for relevant payment/travel information
                if any(kw in full_text.lower() for kw in self.KEYWORDS):
                    await SourceRepository.save_raw_post(self.source_id, full_text)
                    saved += 1

            await SourceRepository.record_success(self.source_id)
            logger.info(f"RSS scraper saved {saved} relevant media items from {self.name}")
            return saved

        except Exception as e:
            logger.error(f"Error in RSS scraper for {self.name}: {e}")
            await self.failed_request_handler(str(e))
            return 0

    async def failed_request_handler(self, error_message: str):
        logger.error(f"[RSS FAILED] {self.name} ({self.source_url}): {error_message}")
        if self.source_id:
            await SourceRepository.record_failure(self.source_id, error_message)
