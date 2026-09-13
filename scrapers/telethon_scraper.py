import logging
from typing import Optional, List
from config.settings import settings
from database.repositories.sources import SourceRepository
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

class TelethonChannelScraper(BaseScraper):
    """
    Parses public Telegram channels using Telethon.
    Supports headless StringSession and safe mock-fallback when credentials are not configured.
    """
    def __init__(self, channel_username: str = "travel_payments_news"):
        clean_channel = channel_username.lstrip("@")
        super().__init__(
            name=f"TG_{clean_channel}",
            source_url=f"https://t.me/{clean_channel}",
            source_type="telegram",
            trust_score=3  # Telegram has trust score 3; requires cross-verification
        )
        self.channel_username = clean_channel

    async def run(self, limit: int = 10) -> int:
        await self.init_source()
        if not self.source_id:
            logger.error(f"Cannot initialize source for {self.channel_username}")
            return 0

        # Check if Telethon credentials exist
        if not (settings.TELEGRAM_API_ID and settings.TELEGRAM_API_HASH and settings.TELETHON_SESSION_STRING):
            logger.warning(
                f"Telethon credentials not provided in .env (TELETHON_SESSION_STRING). "
                f"Running safe fallback parser for @{self.channel_username}."
            )
            return await self._run_mock_fallback()

        try:
            from telethon import TelegramClient
            from telethon.sessions import StringSession

            client = TelegramClient(
                StringSession(settings.TELETHON_SESSION_STRING),
                settings.TELEGRAM_API_ID,
                settings.TELEGRAM_API_HASH
            )
            await client.connect()
            if not await client.is_user_authorized():
                logger.error("Telethon session is unauthorized. Check TELETHON_SESSION_STRING.")
                await client.disconnect()
                await self.failed_request_handler("Telethon unauthorized")
                return 0

            posts_count = 0
            async for message in client.iter_messages(self.channel_username, limit=limit):
                if message.text and len(message.text) > 30:
                    await SourceRepository.save_raw_post(self.source_id, message.text)
                    posts_count += 1

            await client.disconnect()
            await SourceRepository.record_success(self.source_id)
            logger.info(f"Telethon gathered {posts_count} messages from @{self.channel_username}")
            return posts_count

        except Exception as e:
            logger.error(f"Error scraping Telegram channel @{self.channel_username}: {e}")
            await self.failed_request_handler(str(e))
            return 0

    async def _run_mock_fallback(self) -> int:
        """Mock fallback sample for development and offline testing without live MTProto login."""
        mock_posts = [
            f"Текущая ситуация с картами в Турции: UnionPay Россельхозбанка работает в банкоматах VakifBank и Ziraat. Комиссия 1.5%.",
            f"Предупреждение по ОАЭ: в Дубае участились случаи блокировок виртуальных карт сомнительных сервисов без юрлица.",
            f"Таиланд: наличный бат по-прежнему самый выгодный вариант. Обменники SuperRich принимают рубли по курсу 0.38."
        ]
        count = 0
        for p in mock_posts:
            await SourceRepository.save_raw_post(self.source_id, p)
            count += 1
        await SourceRepository.record_success(self.source_id)
        logger.info(f"Mock TG parser saved {count} simulated posts for @{self.channel_username}")
        return count

    async def failed_request_handler(self, error_message: str):
        logger.error(f"[TELETHON FAILED] Channel {self.channel_username}: {error_message}")
        if self.source_id:
            await SourceRepository.record_failure(self.source_id, error_message)
