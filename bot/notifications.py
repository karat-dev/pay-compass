"""Chat messages that only deep-link into a Mini App screen.

The bot is no longer the guide. Notifications stay in the chat; the screen
itself opens in the Mini App via a web_app button and startapp parameter.
"""

from __future__ import annotations

import logging

from aiogram.types import MenuButtonWebApp, WebAppInfo

from api.miniapp_http import normalize_screen
from bot.keyboards.miniapp_kb import get_miniapp_open_keyboard, miniapp_url

logger = logging.getLogger(__name__)

MINIAPP_START_TEXT = (
    "Умный туризм\n\n"
    "Справочник по оплате, чек-лист и разбор маршрута открываются в приложении. "
    "В чате остаются только уведомления — каждое со ссылкой на нужный экран.\n\n"
    "Мы не продаём карты и не берём комиссию."
)


def notification_message(text: str, screen: str, *, button: str = "Открыть в приложении") -> tuple:
    target = normalize_screen(screen)
    return text, get_miniapp_open_keyboard(target, label=button)


async def ensure_menu_button(bot) -> None:
    """Default chat menu button. BotFather can set the same URL by hand."""
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Открыть", web_app=WebAppInfo(url=miniapp_url())),
        )
    except Exception as exc:
        logger.warning("Mini App menu button was not set: %s", exc)


def deliver_community_notices(notices: list) -> None:
    """Send community reminders to Telegram. A missing bot token skips delivery."""
    import os

    import httpx

    from bot.keyboards.miniapp_kb import miniapp_url
    from config.settings import bot_token, settings, telegram_bot_token_configured

    if not notices or not telegram_bot_token_configured():
        return

    owner = os.environ.get("OWNER_TELEGRAM_CHAT_ID") or settings.ADMIN_TELEGRAM_ID
    token = bot_token()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for notice in notices:
        screen = str(notice.get("screen") or "")
        text, markup = notification_message(str(notice.get("text") or ""), screen)
        link = miniapp_url(normalize_screen(screen))
        if link and link not in text:
            text = text + "\n" + link
        chat = owner if notice.get("kind") == "moderation_queue" else (notice.get("user_id") or owner)
        payload = {"chat_id": chat, "text": text}
        try:
            payload["reply_markup"] = markup.model_dump(exclude_none=True)
        except Exception:
            payload.pop("reply_markup", None)
        try:
            response = httpx.post(url, json=payload, timeout=10)
            if response.status_code >= 400:
                httpx.post(url, json={"chat_id": chat, "text": text}, timeout=10)
        except Exception as exc:
            logger.warning("community notice was not delivered: %s", exc)


def screen_from_start(text: str | None) -> str:
    parts = (text or "").split(maxsplit=1)
    if len(parts) < 2:
        return ""
    return normalize_screen(parts[1].strip())
