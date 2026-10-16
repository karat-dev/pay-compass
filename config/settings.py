from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Optional, Union, Any

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Telegram Bot
    BOT_TOKEN: str = "mock_token_for_dev"
    ADMIN_TELEGRAM_ID: int = 303653591
    BOT_NAME: str = "TravelPayBot"
    # Public @username without @. Empty until set. Never hard-code a live username in links.
    BOT_USERNAME: str = ""
    WEBHOOK_SECRET: str = "travelpay_webhook_secret"
    VERCEL_URL: Optional[str] = None

    # Supabase
    SUPABASE_URL: str = "http://localhost:54321"
    SUPABASE_KEY: str = "mock_service_key"

    # Telethon (safely accept empty string or None)
    TELEGRAM_API_ID: Optional[int] = None
    TELEGRAM_API_HASH: Optional[str] = None
    TELETHON_SESSION_STRING: Optional[str] = None

    @field_validator("TELEGRAM_API_ID", mode="before")
    @classmethod
    def parse_api_id(cls, v: Any) -> Optional[int]:
        if v is None or v == "" or (isinstance(v, str) and not v.strip()):
            return None
        return int(v)

    @field_validator("TELEGRAM_API_HASH", "TELETHON_SESSION_STRING", mode="before")
    @classmethod
    def parse_empty_strings(cls, v: Any) -> Optional[str]:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v

    @field_validator("BOT_USERNAME", mode="before")
    @classmethod
    def strip_bot_username(cls, v: Any) -> str:
        if v is None:
            return ""
        name = str(v).strip()
        if name.startswith("@"):
            name = name[1:]
        return name

    # Scrapers
    RSHB_UNIONPAY_URL: str = "https://www.rshb.ru/natural/cards/tariffs/unionpay"

    # Stars Pricing
    STARS_PRICE_90_DAYS: int = 150

    # Telegram Mini App. URL must be https in production (BotFather menu button).
    # MINIAPP_DEV_AUTH accepts the local "dev:<id>" initData. Leave it unset on Vercel.
    MINIAPP_URL: str = "http://127.0.0.1:4173/miniapp/"
    MINIAPP_DEV_AUTH: bool = False
    MINIAPP_INITDATA_MAX_AGE_SECONDS: int = 86400

settings = Settings()


def bot_username() -> str:
    return settings.BOT_USERNAME or ""


def bot_url(text: Optional[str] = None) -> Optional[str]:
    """t.me link for the product bot. None until BOT_USERNAME is set."""
    name = bot_username()
    if not name:
        return None
    from urllib.parse import quote

    url = f"https://t.me/{name}"
    if text:
        url = f"{url}?text={quote(text)}"
    return url
