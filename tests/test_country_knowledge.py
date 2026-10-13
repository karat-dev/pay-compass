"""Knowledge base for China, Hong Kong, Thailand and the UAE, plus forum isolation."""

from database.knowledge_base import (
    CHINA_DATA,
    HONG_KONG_DATA,
    THAILAND_DATA,
    UAE_DATA,
    TURKEY_DATA,
    COUNTRIES_KNOWLEDGE_BASE,
    DATE_VERIFIED,
    ALLOWED_FACT_STATUSES,
    format_fact,
    forum_section_text,
    render_user_facing,
)
from database.repositories.countries import CountryRepository
from bot.keyboards.country_kb import get_countries_keyboard, get_country_hub_keyboard
from scrapers.awd_scraper import (
    AwdForumScraper,
    INTERNAL_VERIFICATION_MARKER,
    user_facing_text_from_raw,
)

NEW_COUNTRIES = {
    "china": CHINA_DATA,
    "hong_kong": HONG_KONG_DATA,
    "thailand": THAILAND_DATA,
    "uae": UAE_DATA,
}

UNCERTAIN = {"под вопросом", "не подтверждено", "устарело"}


def _callbacks(markup):
    return [button.callback_data for row in markup.inline_keyboard for button in row]


def _button_texts(markup):
    return [button.text for row in markup.inline_keyboard for button in row]


def test_new_countries_registered():
    for slug, data in NEW_COUNTRIES.items():
        assert COUNTRIES_KNOWLEDGE_BASE[slug] is data
        assert data["slug"] == slug
        assert data["date_verified"] == DATE_VERIFIED
        assert CountryRepository.get_expert_data(slug) is data

    seeded = {c["slug"] for c in CountryRepository.INITIAL_COUNTRIES}
    assert {"china", "hong_kong", "thailand", "uae"} <= seeded


def test_country_buttons_include_new_guides_even_if_db_list_is_old():
    kb = get_countries_keyboard([{"slug": "turkey", "name": "Турция 🇹🇷"}])
    callbacks = _callbacks(kb)
    assert "country_china" in callbacks
    assert "country_hong_kong" in callbacks
    assert "country_thailand" in callbacks
    assert "country_uae" in callbacks
    texts = " ".join(_button_texts(kb))
    assert "Китай" in texts
    assert "Гонконг" in texts
    assert "Таиланд" in texts
    assert "ОАЭ" in texts


def test_hub_labels_and_no_forum_button():
    china = get_country_hub_keyboard("china")
    assert "csec_forum_china" not in _callbacks(china)
    assert "📱 QR и пополнение" in _button_texts(china)
    assert "📲 Открытые вопросы" in _button_texts(china)

    turkey = get_country_hub_keyboard("turkey")
    assert "csec_forum_turkey" not in _callbacks(turkey)
    assert "📱 Оплата по QR (Karekod)" in _button_texts(turkey)
    assert "📲 Золотая Корона" in _button_texts(turkey)


def test_every_fact_keeps_status_date_and_is_visible():
    for slug, data in NEW_COUNTRIES.items():
        shown = render_user_facing(data)
        assert data["facts"], slug
        for fact in data["facts"]:
            assert fact["status"] in ALLOWED_FACT_STATUSES
            assert fact["date_verified"] == "13.10.2026"
            rendered = format_fact(fact)
            assert rendered in shown, f"{slug}: {fact['title']} is not shown to users"
            assert f"Статус: {fact['status']}." in shown
        assert "forum.awd.ru" not in shown
        assert "Форум Винского" not in shown
        assert "Участники форума" not in shown


def test_uncertain_statuses_stay_honest():
    china = render_user_facing(CHINA_DATA)
    assert "Статус: устарело." in china
    assert "Статус: не подтверждено." in china
    assert "кошелёк, зарегистрированный на российский номер" in china
    assert "Т-Банк: перевод на Alipay/WeChat" in china

    hong_kong = render_user_facing(HONG_KONG_DATA)
    assert "Статус: не подтверждено." in hong_kong
    assert "в магазинах и ресторанах часто отклоняется" in hong_kong

    thailand = render_user_facing(THAILAND_DATA)
    assert "Статус: под вопросом." in thailand
    assert "Статус: устарело." in thailand
    assert "Статус: не подтверждено." in thailand
    assert "Bangkok Bank, Kasikorn" in thailand
    assert "нет отзывов >60 дней" in thailand

    uae = render_user_facing(UAE_DATA)
    assert "Статус: под вопросом." in uae
    assert "Статус: устарело." in uae
    assert "Статус: не подтверждено." in uae
    assert "нужны свежие отчёты" in uae
    assert "ADCB, Emirates NBD, Magnati" in uae

    for data in NEW_COUNTRIES.values():
        for fact in data["facts"]:
            if fact["status"] in UNCERTAIN:
                block = format_fact(fact)
                assert f"Статус: {fact['status']}." in block
                assert "Статус: подтверждено." not in block


def test_official_source_links_are_kept():
    china = render_user_facing(CHINA_DATA)
    assert "https://www.vtb.ru/personal/platezhi-i-perevody/perevody-v-kitaj/" in china
    assert "https://media.mts.ru/technologies/213834-kak-popolnit-wechat-i-alipay-iz-rossii" in china
    assert "https://www.rshb.ru/natural/debetcards/unionpay-china" in china
    assert "https://www.atb.su/atb-karta-unionpay-lp-6/" in china
    assert "https://www.rshb.ru/natural/debetcards/unionpay-cash" in china
    assert "PDF «Информация о доступности сети приёма карт UnionPay в мире»" in china

    assert "https://www.octopus.com.hk/" in render_user_facing(HONG_KONG_DATA)
    assert "https://www.true.th/en/help/mobile/setting/faq-mobile-banking-authen" in render_user_facing(THAILAND_DATA)

    mir = next(f for f in CHINA_DATA["facts"] if f["title"] == "Карта «Мир»")
    assert mir["status"] == "не подтверждено"
    assert mir["source"] is None


def test_forum_copy_is_not_user_facing():
    notice = forum_section_text(TURKEY_DATA)
    internal = TURKEY_DATA["community_insights"]
    assert internal["internal_only"] is True
    for item in internal["key_takeaways"]:
        assert item["details"] not in notice
        assert item["details"] not in render_user_facing(TURKEY_DATA)
    assert "Участники форума" not in notice
    assert "не цитируются" in notice

    scraper = AwdForumScraper()
    assert scraper.user_facing is False
    html = (
        '<div class="content">'
        "Вчера снял unionpay в банкомате без комисси, лиры выдал сразу, "
        "корона тоже дошла до обменника."
        "</div>"
    )
    posts = scraper.extract_messages_from_html(html)
    assert posts
    assert posts[0]["user_facing"] is False
    assert posts[0]["visibility"] == "internal_only"
    stored = scraper.build_stored_text({"title": "UnionPay и банковские карты в Турции"}, posts[0])
    assert stored.startswith(INTERNAL_VERIFICATION_MARKER)
    assert scraper.to_user_facing_text(stored) is None
    assert scraper.to_user_facing_text(posts[0]["text"]) is None
    assert user_facing_text_from_raw(stored) is None
    assert user_facing_text_from_raw("заметка с форум винского про банкомат") is None
    assert "forum.awd.ru" not in (user_facing_text_from_raw(stored) or "")
