import logging
import asyncio
from typing import Optional, List
import httpx
from bs4 import BeautifulSoup
from config.settings import settings
from database.repositories.sources import SourceRepository
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

class RshbCrawleeScraper(BaseScraper):
    """
    Crawler for Russian Agricultural Bank (RSHB) UnionPay card rules and tariffs.
    Uses robust HTTP requests with retry logic and graceful failure recording.
    """
    def __init__(self, source_url: Optional[str] = None):
        url = source_url or settings.RSHB_UNIONPAY_URL
        super().__init__(
            name="RSHB_UnionPay",
            source_url=url,
            source_type="official",
            trust_score=10  # Highest confidence: official banking source
        )
        self.max_retries = 5

    async def run(self) -> int:
        await self.init_source()
        if not self.source_id:
            logger.error(f"Cannot initialize source record for {self.source_url}")
            return 0

        posts_saved = 0
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }

        async with httpx.AsyncClient(headers=headers, timeout=15.0, follow_redirects=True) as client:
            for attempt in range(1, self.max_retries + 1):
                try:
                    logger.info(f"Scraping {self.source_url} (attempt {attempt}/{self.max_retries})...")
                    resp = await client.get(self.source_url)
                    
                    if resp.status_code >= 400:
                        raise httpx.HTTPStatusError(
                            f"HTTP {resp.status_code}",
                            request=resp.request,
                            response=resp
                        )

                    soup = BeautifulSoup(resp.text, "html.parser")
                    
                    # Extract tariffs and notice blocks
                    content_blocks: List[str] = []
                    for tag in soup.find_all(["article", "section", "div", "p"]):
                        text = tag.get_text(strip=True)
                        if any(keyword in text.lower() for keyword in ["unionpay", "за рубежом", "комиссия", "снятие наличных", "лимиты"]):
                            if 50 < len(text) < 1500 and text not in content_blocks:
                                content_blocks.append(text)

                    # If parsing found sections or mock fallback content
                    if not content_blocks:
                        # Fallback extracted generic text
                        main_text = soup.get_text(separator=" ", strip=True)
                        if len(main_text) > 100:
                            content_blocks.append(main_text[:1000])

                    for block in content_blocks[:5]:
                        await SourceRepository.save_raw_post(self.source_id, block)
                        posts_saved += 1

                    await SourceRepository.record_success(self.source_id)
                    logger.info(f"Successfully scraped {posts_saved} items from {self.name}")
                    return posts_saved

                except Exception as e:
                    logger.warning(f"Attempt {attempt} failed for {self.name}: {e}")
                    if attempt == self.max_retries:
                        await self.failed_request_handler(str(e))
                        return 0
                    await asyncio.sleep(2 ** attempt)

        return 0

    async def failed_request_handler(self, error_message: str):
        """
        Triggered when all retries are exhausted.
        Marks source_health as degraded/down and records the incident.
        """
        logger.error(f"[FAILED REQUEST] Source {self.source_url} completely failed: {error_message}")
        if self.source_id:
            health_info = await SourceRepository.record_failure(self.source_id, error_message)
            logger.critical(
                f"Source {self.name} entered state '{health_info.get('status')}' "
                f"with {health_info.get('error_count')} consecutive errors."
            )
