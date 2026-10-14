"""Validate Telegram Mini App initData before trusting a user id.

https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
The secret key is HMAC-SHA256 of the bot token, keyed by the literal "WebAppData".
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Dict, Mapping, Optional
from urllib.parse import parse_qsl


class AuthError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _data_check_string(pairs: Mapping[str, str]) -> str:
    rows = [f"{key}={value}" for key, value in sorted(pairs.items()) if key != "hash"]
    return "\n".join(rows)


def sign_init_data(fields: Mapping[str, str], bot_token: str) -> str:
    """Build a valid initData query string. Used by tests and local fixtures."""
    secret = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    check = _data_check_string(fields)
    digest = hmac.new(secret, check.encode("utf-8"), hashlib.sha256).hexdigest()
    from urllib.parse import urlencode

    payload = dict(fields)
    payload["hash"] = digest
    return urlencode(payload)


def validate_init_data(
    init_data: str,
    *,
    bot_token: str,
    dev_auth: bool = False,
    max_age_seconds: int = 86400,
    now: Optional[int] = None,
) -> Dict[str, Any]:
    raw = (init_data or "").strip()
    if not raw:
        raise AuthError(401, "Откройте приложение из Telegram.")

    if raw.startswith("dev:"):
        if not dev_auth:
            raise AuthError(401, "Локальный вход выключен.")
        tail = raw.split(":", 1)[1].strip()
        if not tail.isdigit():
            raise AuthError(401, "Некорректный локальный пользователь.")
        telegram_id = int(tail)
        if telegram_id <= 0:
            raise AuthError(401, "Некорректный локальный пользователь.")
        return {
            "telegram_id": telegram_id,
            "username": "dev",
            "start_param": None,
            "dev": True,
        }

    pairs = dict(parse_qsl(raw, keep_blank_values=True, strict_parsing=False))
    received = pairs.get("hash") or ""
    if not received or not bot_token:
        raise AuthError(401, "Не удалось подтвердить Telegram.")

    secret = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    check = _data_check_string(pairs)
    expected = hmac.new(secret, check.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise AuthError(401, "Не удалось подтвердить Telegram.")

    try:
        auth_date = int(pairs.get("auth_date") or "0")
    except ValueError as exc:
        raise AuthError(401, "Не удалось подтвердить Telegram.") from exc
    current = int(now if now is not None else time.time())
    if auth_date <= 0 or current - auth_date > max_age_seconds or auth_date > current + 60:
        raise AuthError(401, "Сессия Telegram устарела. Откройте приложение ещё раз.")

    try:
        user = json.loads(pairs.get("user") or "")
    except json.JSONDecodeError as exc:
        raise AuthError(401, "Не удалось подтвердить Telegram.") from exc
    if not isinstance(user, dict) or not str(user.get("id") or "").isdigit():
        raise AuthError(401, "Не удалось подтвердить Telegram.")

    start_param = pairs.get("start_param") or None
    username = user.get("username")
    return {
        "telegram_id": int(user["id"]),
        "username": username if isinstance(username, str) else None,
        "start_param": start_param,
        "dev": False,
    }
