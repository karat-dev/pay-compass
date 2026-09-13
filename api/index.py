import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from http.server import BaseHTTPRequestHandler
import json
import asyncio

_dp = None

def get_dispatcher():
    global _dp
    if _dp is None:
        from aiogram import Dispatcher
        from bot.storage import SupabaseStorage
        from bot.handlers.onboarding import onboarding_router
        from bot.handlers.menu import menu_router
        from bot.handlers.legal import legal_router
        from bot.handlers.stars import stars_router

        storage = SupabaseStorage()
        _dp = Dispatcher(storage=storage)
        _dp.include_router(onboarding_router)
        _dp.include_router(legal_router)
        _dp.include_router(menu_router)
        _dp.include_router(stars_router)
    return _dp

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            from config.settings import settings
            token_valid = bool(settings.BOT_TOKEN and ":" in settings.BOT_TOKEN)

            # Check incoming request path
            is_set_webhook = "set_webhook" in self.path or "webhook" in self.path

            if is_set_webhook:
                result = asyncio.run(self._set_webhook(settings))
                self._send_json(200, result)
                return

            # Default status response
            self._send_json(200, {
                "status": "ok",
                "service": "TravelPayBot Vercel Serverless",
                "bot_name": settings.BOT_NAME,
                "token_configured": token_valid,
                "path": self.path
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

            asyncio.run(self._process_update(data, settings))

            self._send_json(200, {"ok": True})
        except Exception as e:
            import traceback
            traceback.print_exc(file=sys.stderr)
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
        from aiogram import Bot
        from aiogram.types import Update

        bot = Bot(token=settings.BOT_TOKEN)
        dp = get_dispatcher()

        try:
            update = Update.model_validate(data, context={"bot": bot})
            await dp.feed_update(bot=bot, update=update)
        except Exception as e:
            import traceback
            print(f"[ERROR processing update]: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
        finally:
            try:
                await bot.session.close()
            except Exception:
                pass

    def _send_json(self, status_code: int, data: dict):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
