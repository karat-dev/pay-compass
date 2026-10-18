import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from config.settings import bot_token
from bot.storage import SupabaseStorage
from bot.handlers.onboarding import onboarding_router
from bot.handlers.menu import menu_router
from bot.handlers.legal import legal_router
from bot.handlers.stars import stars_router
from bot.handlers.routes import routes_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Initializing Independent Travel Payments Bot...")

    bot = Bot(token=bot_token())
    storage = SupabaseStorage()
    dp = Dispatcher(storage=storage)

    # Register modular routers
    dp.include_router(onboarding_router)
    dp.include_router(legal_router)
    dp.include_router(menu_router)
    dp.include_router(routes_router)
    dp.include_router(stars_router)

    try:
        try:
            from bot.notifications import deliver_community_notices
            from database.community_service import mark_reminded, pending_notifications

            notes = pending_notifications()
            deliver_community_notices(notes)
            for note in notes:
                if note.get("kind") == "recheck_reminder" and note.get("review_id"):
                    mark_reminded(note["review_id"])
        except Exception:
            logger.exception("community reminders skipped")
        logger.info("Starting bot polling loop...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await storage.close()
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
