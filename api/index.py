import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from http.server import BaseHTTPRequestHandler
import json
import asyncio

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            from config.settings import settings
            token_valid = bool(settings.BOT_TOKEN and ":" in settings.BOT_TOKEN)

            # Check incoming request path or forwarded URI
            request_uri = self.headers.get("x-matched-path") or self.headers.get("x-vercel-matched-path") or self.path

            if "set_webhook" in self.path or "set_webhook" in request_uri:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(self._set_webhook(settings))
                loop.close()
                self._send_json(200, result)
                return

            # Default status response
            self._send_json(200, {
                "status": "ok",
                "service": "TravelPayBot Vercel Serverless",
                "bot_name": settings.BOT_NAME,
                "token_configured": token_valid
            })
        except Exception as e:
            import traceback
            self._send_json(500, {
                "error": str(e),
                "traceback": traceback.format_exc()
            })

    def do_POST(self):
        try:
            from config.settings import settings
            secret_header = self.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if settings.WEBHOOK_SECRET and secret_header != settings.WEBHOOK_SECRET:
                self._send_json(401, {"error": "unauthorized"})
                return

            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._process_update(data, settings))
            loop.close()

            self._send_json(200, {"ok": True})
        except Exception as e:
            import traceback
            self._send_json(200, {"ok": False, "error": str(e)})

    async def _set_webhook(self, settings):
        from aiogram import Bot
        bot = Bot(token=settings.BOT_TOKEN)
        host = self.headers.get("x-forwarded-host") or self.headers.get("host")
        if host:
            host = f"https://{host}"
        webhook_url = f"{host.rstrip('/')}/"
        success = await bot.set_webhook(
            url=webhook_url,
            secret_token=settings.WEBHOOK_SECRET,
            drop_pending_updates=True
        )
        await bot.session.close()
        return {"success": success, "webhook_url": webhook_url}

    async def _process_update(self, data, settings):
        from aiogram import Bot, Dispatcher
        from aiogram.types import Update
        from bot.storage import SupabaseStorage
        from bot.handlers.onboarding import onboarding_router
        from bot.handlers.menu import menu_router
        from bot.handlers.legal import legal_router
        from bot.handlers.stars import stars_router

        bot = Bot(token=settings.BOT_TOKEN)
        storage = SupabaseStorage()
        dp = Dispatcher(storage=storage)
        dp.include_router(onboarding_router)
        dp.include_router(legal_router)
        dp.include_router(menu_router)
        dp.include_router(stars_router)

        update = Update.model_validate(data, context={"bot": bot})
        await dp.feed_update(bot=bot, update=update)
        await storage.close()
        await bot.session.close()

    def _send_json(self, status_code: int, data: dict):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
