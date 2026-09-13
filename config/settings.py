from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Telegram Bot
    BOT_TOKEN: str = Field(default="mock_token_for_dev")
    ADMIN_TELEGRAM_ID: int = Field(default=0)
    BOT_NAME: str = Field(default="TravelPayBot")
    WEBHOOK_SECRET: str = Field(default="travelpay_webhook_secret")
    VERCEL_URL: Optional[str] = Field(default=None)

    # Supabase
    SUPABASE_URL: str = Field(default="http://localhost:54321")
    SUPABASE_KEY: str = Field(default="mock_service_key")

    # Telethon
    TELEGRAM_API_ID: Optional[int] = Field(default=None)
    TELEGRAM_API_HASH: Optional[str] = Field(default=None)
    TELETHON_SESSION_STRING: Optional[str] = Field(default=None)

    # Scrapers
    RSHB_UNIONPAY_URL: str = Field(
        default="https://www.rshb.ru/natural/cards/tariffs/unionpay"
    )

    # Stars Pricing
    STARS_PRICE_90_DAYS: int = Field(default=150)

settings = Settings()
