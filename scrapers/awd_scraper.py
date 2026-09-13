"""
Parser and analyzer for Forum AWD (Форум Винского) payment topics.
Extracts real traveler messages, filters relevant payment reports,
evaluates confidence scores, and produces summarized insights.
"""

import logging
import asyncio
import re
from typing import List, Dict, Any, Optional
import httpx
from scrapers.base import BaseScraper
from database.repositories.sources import SourceRepository

logger = logging.getLogger(__name__)

class AwdForumScraper(BaseScraper):
    """
    Scrapes and analyzes payment threads from Forum AWD (Форум Винского).
    Collects raw messages, filters noise, and extracts validated facts.
    """

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
                        "matches_count": matches
                    })
        return messages

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
                    entry_text = f"[{topic['title']}]\n{p['text']}\nРелевантность: {p['relevance']}"
                    await SourceRepository.save_raw_post(self.source_id, entry_text)
                    total_saved += 1

        logger.info(f"Forum AWD scraper parsed {total_saved} relevant reports.")
        return total_saved
