from __future__ import annotations

from urllib.parse import urlencode

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from config.settings import settings


def miniapp_url(screen: str | None = None) -> str:
    base = (settings.MINIAPP_URL or "").strip() or "http://127.0.0.1:4173/miniapp/"
    if not base.endswith("/"):
        base += "/"
    if not screen:
        return base
    return base + "?" + urlencode({"startapp": screen})


def get_miniapp_open_keyboard(screen: str | None = None, label: str = "Открыть приложение") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, web_app=WebAppInfo(url=miniapp_url(screen)))],
    ])


def get_start_keyboard(screen: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Открыть приложение", web_app=WebAppInfo(url=miniapp_url(screen)))],
        [InlineKeyboardButton(text="📄 Политика конфиденциальности", callback_data="onboarding_show_privacy")],
    ])
