"""Schema v2 country guides: trust zones, gaps, forum isolation."""

from database.knowledge_base import (
    ALLOWED_FACT_STATUSES,
    CHINA_DATA,
    COUNTRIES_KNOWLEDGE_BASE,
    DATE_VERIFIED,
    DEFAULT_ZONES,
    FACT_FIELDS,
    FACT_TYPES,
    GAP_LABEL,
    HIDDEN_ZONES,
    HONG_KONG_DATA,
    INSTRUCTIONS,
    SECTION_KEYS,
    THAILAND_DATA,
    TRUST_CONFIG,
    TURKEY_DATA,
    UAE_DATA,
    fact_on_request,
    format_fact,
    forum_section_text,
    is_gap,
    iter_facts,
    render_instruction,
    render_section,
    render_section_html,
    render_user_facing,
    user_visible_fact,
    zone_sets,
)
from database.repositories.countries import CountryRepository
from bot.keyboards.country_kb import get_countries_keyboard, get_country_hub_keyboard, get_section_nav_keyboard
from bot.handlers.menu import _parse_section_callback
from scrapers.awd_scraper import (
    AwdForumScraper,
    INTERNAL_VERIFICATION_MARKER,
    user_facing_text_from_raw,
)

GUIDES = {
    "china": CHINA_DATA,
    "hong_kong": HONG_KONG_DATA,
    "thailand": THAILAND_DATA,
    "uae": UAE_DATA,
    "turkey": TURKEY_DATA,
}


def _callbacks(markup):
    return [button.callback_data for row in markup.inline_keyboard for button in row]


def _button_texts(markup):
    return [button.text for row in markup.inline_keyboard for button in row]


def _check_fact(fact):
    for field in FACT_FIELDS:
        assert field in fact
    assert fact["status"] in ALLOWED_FACT_STATUSES
    assert fact["type"] in FACT_TYPES
    assert fact["type"] == fact["fact_type"]
    assert isinstance(fact["zone"], str) and fact["zone"]
    assert fact["score"] is None or isinstance(fact["score"], int)
    assert fact["score_breakdown"] is None or isinstance(fact["score_breakdown"], dict)
    assert fact["date_verified"] is None or isinstance(fact["date_verified"], str)
    assert fact["date_estimated"] is None or isinstance(fact["date_estimated"], bool)
    assert fact["source"] is None or isinstance(fact["source"], str)
    assert isinstance(fact["needs_owner_check"], bool)
    assert fact["decision_needed"] is None or isinstance(fact["decision_needed"], str)
    assert fact["unknown_zone"] is None or isinstance(fact["unknown_zone"], str)


def test_schema_v2_sections_and_fact_fields():
    assert SECTION_KEYS == (
        "1_checklist",
        "2_pay_on_site",
        "3_local_wallets_cards",
        "4_cash_exchange",
        "5_atms",
        "6_transport",
        "7_risks",
        "8_tax_free",
    )
    for slug, country in GUIDES.items():
        assert COUNTRIES_KNOWLEDGE_BASE[slug] is country
        assert country["slug"] == slug
        assert country["schema_version"] == 2
        assert country["date_verified"] == DATE_VERIFIED
        assert "community_insights" not in country
        assert list(country["sections"]) == list(SECTION_KEYS)
        assert CountryRepository.get_expert_data(slug) is country
        for key in SECTION_KEYS:
            section = country["sections"][key]
            assert isinstance(section["applicable"], bool)
            if not section["applicable"]:
                assert isinstance(section["reason"], str) and section["reason"].strip()
            for fact in section["facts"]:
                _check_fact(fact)
            if key == "3_local_wallets_cards":
                assert set(section["subsections"]) >= {"wallets", "local_card"}
                for subsection in section["subsections"].values():
                    for fact in subsection["facts"]:
                        _check_fact(fact)
        for instruction_id in country["instruction_ids"]:
            for step in INSTRUCTIONS[instruction_id]["steps"]:
                _check_fact(step)

    seeded = {item["slug"] for item in CountryRepository.INITIAL_COUNTRIES}
    assert {"china", "hong_kong", "thailand", "uae", "turkey"} <= seeded


def test_thresholds_come_from_config():
    assert TRUST_CONFIG["display"]["default_min"] == 50
    assert TRUST_CONFIG["zones"][0]["name"] == "green"
    assert TRUST_CONFIG["zones"][0]["min"] == 75
    assert DEFAULT_ZONES == {"green", "yellow"}
    assert {"red", "black", "advice-unsupported"} <= HIDDEN_ZONES
    stricter, hidden = zone_sets({
        "zones": TRUST_CONFIG["zones"],
        "display": {"default_min": 75, "extra_hidden_zones": []},
    })
    assert stricter == {"green"}
    assert {"yellow", "red", "black"} <= hidden


def test_default_view_is_green_and_yellow():
    for slug, country in GUIDES.items():
        default = render_user_facing(country, show_unverified=False)
        requested = render_user_facing(country, show_unverified=True)
        assert "forum.awd.ru" not in default and "forum.awd.ru" not in requested
        assert "форум" not in default.lower() and "форум" not in requested.lower()
        assert "согласованность" not in default and "согласованность" not in requested
        assert "Форум Винского" not in default
        for fact in iter_facts(country):
            if not user_visible_fact(fact):
                assert fact["text"] not in default
                assert fact["text"] not in requested
                continue
            for private in ("unknown_zone", "decision_needed", "reason"):
                value = fact.get(private)
                if isinstance(value, str) and value.strip():
                    assert value not in default
                    assert value not in requested
            if fact.get("score_breakdown"):
                assert "score_breakdown" not in default
            if is_gap(fact):
                assert fact["text"] in default
                assert GAP_LABEL in format_fact(fact)
                continue
            shown_by_default = fact.get("zone") in DEFAULT_ZONES
            if shown_by_default:
                assert fact["text"] in default
                if fact.get("date_estimated") and fact.get("date_verified"):
                    assert "дата ориентировочная" in format_fact(fact, warn=False)
            else:
                assert fact_on_request(fact)
                assert fact["text"] not in default
                assert fact["text"] in requested
                warned = format_fact(fact, warn=True)
                assert "⚠️ Непроверено" in warned
            rendered = format_fact(fact, warn=fact_on_request(fact))
            if fact.get("source_user_facing") is False:
                source = fact.get("source")
                if isinstance(source, str) and source.startswith("http"):
                    assert source.split()[0] not in rendered
                assert "Официальной ссылки нет." in rendered or is_gap(fact)
            elif shown_by_default and isinstance(fact.get("source"), str) and fact["source"].startswith("http"):
                assert fact["source"].split()[0] in default


def test_gaps_show_and_red_black_stay_behind_the_button():
    china_cards = render_section(CHINA_DATA, "3_local_wallets_cards")
    assert "Счёт в китайском банке для туриста — не исследовано." in china_cards
    assert "Привязка UnionPay АТБ/РСХБ к Alipay/WeChat." not in china_cards
    china_all = render_section(CHINA_DATA, "3_local_wallets_cards", show_unverified=True)
    assert "Привязка UnionPay АТБ/РСХБ к Alipay/WeChat." in china_all
    assert "⚠️ Непроверено" in china_all

    opening = "Bangkok Bank и Kasikorn не открывают счета туристам"
    thailand_default = render_user_facing(THAILAND_DATA)
    assert opening in thailand_default
    assert "Мобильный банк привязан к SIM" in thailand_default

    turkey_default = render_user_facing(TURKEY_DATA)
    turkey_all = render_user_facing(TURKEY_DATA, show_unverified=True)
    hidden = (
        "ВТБ поддерживает оплату по TR QR в Турции",
        "UnionPay Газпромбанка снимает лиры",
    )
    for phrase in hidden:
        assert phrase not in turkey_default
        assert phrase in turkey_all
    assert "Газпромбанк под санкциями США" in turkey_default
    assert "Участники форума" not in turkey_default
    assert "community_insights" not in TURKEY_DATA


def test_not_applicable_section_states_reason():
    transport = render_section(THAILAND_DATA, "6_transport")
    assert "не применим" in transport
    assert "Единой туристической транспортной карты нет" in transport


def test_unverified_button_and_eight_section_hub():
    kb = get_countries_keyboard([{"slug": "turkey", "name": "Турция 🇹🇷"}])
    callbacks = _callbacks(kb)
    assert "country_china" in callbacks
    assert "country_hong_kong" in callbacks
    assert "country_thailand" in callbacks
    assert "country_uae" in callbacks

    hub = get_country_hub_keyboard("china")
    hub_callbacks = _callbacks(hub)
    assert "csec_forum_china" not in hub_callbacks
    for number in range(1, 9):
        assert f"csec_{number}_china" in hub_callbacks

    cards = get_section_nav_keyboard("turkey", "5", show_unverified=False)
    assert "Показать непроверенное" in _button_texts(cards)
    assert "cunv_5_turkey" in _callbacks(cards)
    hidden = get_section_nav_keyboard("turkey", "5", show_unverified=True)
    assert "Скрыть непроверенное" in _button_texts(hidden)

    assert _parse_section_callback("csec_qr_hong_kong") == ("hong_kong", "2", False)
    assert _parse_section_callback("cunv_8_uae") == ("uae", "8", True)


def test_official_links_and_html_fit_telegram():
    china = render_user_facing(CHINA_DATA)
    assert "https://www.vtb.ru/personal/platezhi-i-perevody/qr/" in china
    assert "https://www.rshb.ru/natural/debetcards/unionpay-china" in china
    assert "https://www.atb.su/atb-karta-unionpay-lp-6/" in china
    assert "https://www.octopus.com.hk/" in render_user_facing(HONG_KONG_DATA)
    assert "https://www.true.th/en/help/mobile/setting/faq-mobile-banking-authen" in render_user_facing(THAILAND_DATA)

    for country in GUIDES.values():
        for key in SECTION_KEYS:
            page = render_section_html(country, key, show_unverified=True)
            assert len(page) < 4096
            for fact in iter_facts(country):
                if fact.get("unknown_zone"):
                    assert fact["unknown_zone"] not in page
    for instruction_id in INSTRUCTIONS:
        page = render_instruction(instruction_id, show_unverified=True)
        assert "needs_owner_check" not in page


def test_forum_copy_is_not_user_facing():
    notice = forum_section_text(TURKEY_DATA)
    assert "Участники форума" not in notice
    assert "не цитируются" in notice
    assert "Форум Винского" not in notice

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
    assert user_facing_text_from_raw(stored) is None
    assert user_facing_text_from_raw("заметка с форум винского про банкомат") is None
