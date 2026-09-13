import os
import sys

# Ensure workspace root is in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

import logging
from typing import Optional
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

app = FastAPI(title="TravelPayBot Webhook")

_bot = None
_dp = None
_storage = None

def get_bot_and_dispatcher():
    global _bot, _dp, _storage
    if _bot is None:
        from aiogram import Bot, Dispatcher
        from config.settings import settings
        from bot.storage import SupabaseStorage
        from bot.handlers.onboarding import onboarding_router
        from bot.handlers.menu import menu_router
        from bot.handlers.legal import legal_router
        from bot.handlers.stars import stars_router

        if not settings.BOT_TOKEN or ":" not in settings.BOT_TOKEN:
            raise ValueError(
                f"BOT_TOKEN is invalid or not set in Environment Variables! Current value: '{settings.BOT_TOKEN}'"
            )
        _bot = Bot(token=settings.BOT_TOKEN)
        _storage = SupabaseStorage()
        _dp = Dispatcher(storage=_storage)
        _dp.include_router(onboarding_router)
        _dp.include_router(legal_router)
        _dp.include_router(menu_router)
        _dp.include_router(stars_router)
    return _bot, _dp

@app.get("/")
async def root():
    from config.settings import settings
    token_status = "configured" if settings.BOT_TOKEN and ":" in settings.BOT_TOKEN else "missing_or_invalid"
    return {
        "status": "ok",
        "service": "TravelPayBot Webhook Serverless",
        "bot_name": settings.BOT_NAME,
        "token_status": token_status
    }

@app.get("/api/set_webhook")
async def setup_webhook(request: Request):
    """
    Helper endpoint to register webhook URL in Telegram with one click.
    Pass ?url=https://your-domain.vercel.app or auto-detect from Vercel headers.
    """
    try:
        from config.settings import settings
        bot, dp = get_bot_and_dispatcher()
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Bot initialization error: {e}. Check BOT_TOKEN in Vercel Environment Variables."}
        )

    host = request.query_params.get("url")
    if not host:
        host = request.headers.get("x-forwarded-host") or request.headers.get("host")
        if host:
            host = f"https://{host}"

    if not host:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Provide ?url=https://your-app.vercel.app"}
        )

    webhook_url = f"{host.rstrip('/')}/api/webhook"
    try:
        success = await bot.set_webhook(
            url=webhook_url,
            secret_token=settings.WEBHOOK_SECRET,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=True
        )
        return {
            "success": success,
            "webhook_url": webhook_url
        }
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": str(e)}
        )

@app.post("/api/webhook")
async def telegram_webhook(request: Request):
    """
    Incoming webhook updates from Telegram Bot API.
    """
    from config.settings import settings
    from aiogram.types import Update

    secret_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if settings.WEBHOOK_SECRET and secret_header != settings.WEBHOOK_SECRET:
        logger.warning("Unauthorized webhook request: secret mismatch")
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)

    try:
        bot, dp = get_bot_and_dispatcher()
        update_data = await request.json()
        update = Update.model_validate(update_data, context={"bot": bot})
        await dp.feed_update(bot=bot, update=update)
        return Response(status_code=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Error processing update: {e}", exc_info=True)
        return Response(status_code=status.HTTP_200_OK)
