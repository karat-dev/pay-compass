"""
Parser for Forum AWD (Форум Винского) payment topics.

Collected posts are internal verification material only. They are stored with
an internal marker and must not be copied into bot messages, country guides,
or any other traveler-facing text.
"""

import logging
import asyncio
import re
from typing import List, Dict, Any, Optional
import httpx
from scrapers.base import BaseScraper
from database.repositories.sources import SourceRepository

logger = logging.getLogger(__name__)

# Prefix on every stored forum row. User-facing formatters must drop these rows.
INTERNAL_VERIFICATION_MARKER = "[INTERNAL_VERIFICATION_ONLY]"


def user_facing_text_from_raw(text: Optional[str]) -> Optional[str]:
    """Return text only when it is safe to show a traveler.

    Forum rows are internal verification and always return None.
    """
    if not text or INTERNAL_VERIFICATION_MARKER in text:
        return None
    lowered = text.lower()
    if "forum.awd.ru" in lowered or "форум винского" in lowered:
        return None
    return text


class AwdForumScraper(BaseScraper):
    """
    Scrapes payment threads from Forum AWD for internal verification.
    Does not produce traveler-facing copy.
    """

    user_facing = False

    TARGET_TOPICS = [
        {
            "country": "turkey",
            "topic_id": 410784,
            "title": "UnionPay и банковские карты в Турции",
            "url": "https://forum.awd.ru/viewtopic.php?t=410784"
        },
        {
            "country": "turkey",
            "topic_id": 412500,
            "title": "Обмен валюты и наличные в Турции",
            "url": "https://forum.awd.ru/viewtopic.php?t=412500"
        }
    ]

    KEYWORDS = [
        "unionpay", "юнионпей", "рсхб", "газпромбанк", "атб",
        "банкомат", "лир", "комисси", "без комисси", "снял", "сняла",
        "dcc", "конвертац", "корона", "золотая корона", "обменник", "доллар"
    ]

    def __init__(self):
        super().__init__(
            name="ForumAWD_Scraper",
            source_url="https://forum.awd.ru",
            source_type="forum",
            trust_score=8  # High community trust
        )

    def extract_messages_from_html(self, html: str) -> List[Dict[str, Any]]:
        """Parses HTML content of forum topic to extract individual traveler posts."""
        messages = []
        # Find post bodies: <div class="content">...</div>
        post_blocks = re.findall(r'<div class="content">(.*?)</div>', html, re.DOTALL | re.IGNORECASE)
        
        # Clean HTML tags
        for block in post_blocks:
            clean_text = re.sub(r'<[^>]+>', ' ', block)
            clean_text = ' '.join(clean_text.split())
            if len(clean_text) > 40:
                # Check keyword relevance
                lower = clean_text.lower()
                matches = sum(1 for kw in self.KEYWORDS if kw in lower)
                if matches >= 1:
                    relevance_score = min(0.95, 0.6 + (matches * 0.08))
                    messages.append({
                        "text": clean_text,
                        "relevance": round(relevance_score, 2),
                        "matches_count": matches,
                        "user_facing": False,
                        "visibility": "internal_only",
                    })
        return messages

    def build_stored_text(self, topic: Dict[str, Any], post: Dict[str, Any]) -> str:
        """Raw forum text plus the internal-only marker. Not for users."""
        body = f"[{topic['title']}]\n{post['text']}\nРелевантность: {post['relevance']}"
        return f"{INTERNAL_VERIFICATION_MARKER}\n{body}"

    def to_user_facing_text(self, stored_text: Optional[str] = None) -> None:
        """Forum output is never shown to users, with or without the marker."""
        return None

    async def fetch_topic_page(self, client: httpx.AsyncClient, topic_url: str) -> Optional[str]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8"
        }
        try:
            resp = await client.get(topic_url, headers=headers, timeout=12.0, follow_redirects=True)
            if resp.status_code == 200:
                return resp.text
            else:
                logger.warning(f"Forum AWD returned status {resp.status_code} for {topic_url}")
                return None
        except Exception as e:
            logger.warning(f"Error fetching Forum AWD topic {topic_url}: {e}")
            return None

    async def run(self, max_posts_per_topic: int = 15) -> int:
        await self.init_source()
        if not self.source_id:
            logger.error(f"Cannot initialize Forum AWD source.")
            return 0

        total_saved = 0
        async with httpx.AsyncClient() as client:
            for topic in self.TARGET_TOPICS:
                html = await self.fetch_topic_page(client, topic["url"])
                if not html:
                    continue

                posts = self.extract_messages_from_html(html)
                for p in posts[:max_posts_per_topic]:
                    entry_text = self.build_stored_text(topic, p)
                    if self.to_user_facing_text(entry_text) is not None:
                        logger.error("Forum AWD text was marked user-facing; refusing to store it.")
                        continue
                    await SourceRepository.save_raw_post(self.source_id, entry_text)
                    total_saved += 1

        logger.info(
            f"Forum AWD scraper stored {total_saved} internal verification reports. "
            "These rows are not for user-facing texts."
        )
        return total_saved
