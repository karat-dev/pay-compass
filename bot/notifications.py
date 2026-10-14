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


def screen_from_start(text: str | None) -> str:
    parts = (text or "").split(maxsplit=1)
    if len(parts) < 2:
        return ""
    return normalize_screen(parts[1].strip())
