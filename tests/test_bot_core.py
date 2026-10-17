import pytest
import asyncio
from bot.states import OnboardingStates, MainMenuStates
from texts.onboarding import STEP_1_TEXT, STEP_4_TEXT
from texts.privacy_policy import PRIVACY_POLICY_TEXT
from bot.keyboards.onboarding_kb import get_step_1_kb, get_step_4_kb
from bot.keyboards.country_kb import get_subscription_pay_keyboard
from scrapers.rss_fallback import MediaRssFallbackScraper
from scrapers.telethon_scraper import TelethonChannelScraper
from config.settings import settings

def test_onboarding_texts_exact_match():
    assert "независимый справочник по оплате" in STEP_1_TEXT
    assert "Мы НЕ продаём карты и НЕ берём комиссию" in STEP_1_TEXT
    assert "Мы обрабатываем ваш Telegram ID" in STEP_4_TEXT
    assert "152-ФЗ" in PRIVACY_POLICY_TEXT
    assert "тестовый этап" in PRIVACY_POLICY_TEXT
    assert "[" not in PRIVACY_POLICY_TEXT
    assert "/delete_me" in PRIVACY_POLICY_TEXT

def test_keyboards_structure():
    kb_step1 = get_step_1_kb()
    assert kb_step1.inline_keyboard[0][0].text == "Продолжить →"
    assert kb_step1.inline_keyboard[0][0].callback_data == "onboarding_next_2"

    kb_step4 = get_step_4_kb()
    assert kb_step4.inline_keyboard[0][0].text == "✅ Согласен и продолжить"
    assert kb_step4.inline_keyboard[1][0].text == "📄 Политика конфиденциальности"

    kb_stars = get_subscription_pay_keyboard(settings.STARS_PRICE_90_DAYS)
    assert f"{settings.STARS_PRICE_90_DAYS} Stars" in kb_stars.inline_keyboard[0][0].text

    from bot.keyboards.menu_kb import get_main_menu_kb
    import inspect
    import bot.handlers.stars as stars

    labels = [button.text for row in get_main_menu_kb().inline_keyboard for button in row]
    assert not any("подписк" in label.lower() or "Stars" in label for label in labels)
    source = inspect.getsource(stars)
    assert "send_invoice" not in source
    assert "activate_subscription" not in source
    assert "ok=False" in source

@pytest.mark.asyncio
async def test_country_access_stays_open():
    from database.repositories.countries import CountryRepository

    access = await CountryRepository.check_user_access(1001, "china", False)
    assert access == {"allowed": True, "reason": "launch_free", "country_id": "china"}


@pytest.mark.asyncio
async def test_scrapers_initialization():
    rss = MediaRssFallbackScraper()
    assert rss.trust_score == 7
    assert rss.source_type == "media"

    tg = TelethonChannelScraper("test_channel")
    assert tg.trust_score == 3
    assert tg.source_type == "telegram"
