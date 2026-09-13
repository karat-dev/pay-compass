import asyncio
import logging
from scrapers.crawlee_scraper import RshbCrawleeScraper
from scrapers.telethon_scraper import TelethonChannelScraper
from scrapers.rss_fallback import MediaRssFallbackScraper
from database.client import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ScraperRunner")

async def run_all_scrapers():
    logger.info("Starting automated daily data collection pipeline...")

    # 1. Official Bank Scraper (RSHB)
    rshb = RshbCrawleeScraper()
    rshb_count = await rshb.run()
    logger.info(f"Official RSHB scraper finished with {rshb_count} raw items.")

    # 2. Telegram Parser (Telethon / fallback)
    tg = TelethonChannelScraper("travel_payments_news")
    tg_count = await tg.run()
    logger.info(f"Telegram parser finished with {tg_count} raw items.")

    # 3. Media RSS Fallback
    rss = MediaRssFallbackScraper()
    rss_count = await rss.run()
    logger.info(f"Media RSS scraper finished with {rss_count} raw items.")

    await db.close()
    logger.info("Pipeline execution completed.")

if __name__ == "__main__":
    asyncio.run(run_all_scrapers())
