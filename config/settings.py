from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Optional, Union, Any

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Telegram Bot
    BOT_TOKEN: str = "mock_token_for_dev"
    ADMIN_TELEGRAM_ID: int = 0
    BOT_NAME: str = "TravelPayBot"
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

    # Scrapers
    RSHB_UNIONPAY_URL: str = "https://www.rshb.ru/natural/cards/tariffs/unionpay"

    # Stars Pricing
    STARS_PRICE_90_DAYS: int = 150

settings = Settings()
