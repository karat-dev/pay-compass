"""Mini App catalog, Telegram initData and saved trip state."""

import json
import time

import pytest

from api.miniapp_http import dispatch, extract_route, normalize_screen
from api.telegram_auth import sign_init_data, validate_init_data, AuthError
from bot.keyboards.miniapp_kb import get_start_keyboard
from bot.notifications import notification_message
from config.settings import settings
from database.knowledge_base import (
    COUNTRIES_KNOWLEDGE_BASE,
    INSTRUCTIONS,
    SECTION_KEYS,
    select_facts,
)
from database.miniapp_catalog import SHORT_SECTION_TITLES, get_catalog
from database.miniapp_store import FileMiniappStore, SupabaseMiniappStore, set_store, supabase_is_configured
from database.routes import AVIASALES_MARKER


def _walk_keys(node, found):
    if isinstance(node, dict):
        found.update(node)
        for value in node.values():
            _walk_keys(value, found)
    elif isinstance(node, list):
        for value in node:
            _walk_keys(value, found)


def test_catalog_reuses_knowledge_base_rules():
    catalog = get_catalog()
    assert catalog["display_min"] == 50
    assert [country["slug"] for country in catalog["countries"]] == [
        "china", "hong_kong", "thailand", "uae", "turkey", "georgia",
    ]
    keys = set()
    _walk_keys(catalog, keys)
    assert "score" not in keys
    assert "score_breakdown" not in keys
    assert "needs_owner_check" not in keys
    assert "unknown_zone" not in keys

    for country in catalog["countries"]:
        kb = COUNTRIES_KNOWLEDGE_BASE[country["slug"]]
        assert [section["key"] for section in country["sections"]] == list(SECTION_KEYS)
        for section in country["sections"]:
            assert section["short_title"] == SHORT_SECTION_TITLES[section["key"]]
            kb_section = kb["sections"][section["key"]]
            assert [fact["text"] for fact in section["facts"] if not fact["hidden"]] == [
                fact["text"] for fact in select_facts(kb_section.get("facts") or [], False)
            ]
            assert [fact["text"] for fact in section["facts"]] == [
                fact["text"] for fact in select_facts(kb_section.get("facts") or [], True)
            ]
            for fact in section["facts"]:
                url = fact.get("source_url")
                if url:
                    low = url.lower()
                    assert "t.me/" not in low
                    assert "forum.awd.ru" not in low
                    assert url.startswith("http")

    for instruction_id, instruction in catalog["instructions"].items():
        steps = INSTRUCTIONS[instruction_id]["steps"]
        assert [step["text"] for step in instruction["steps"] if not step["hidden"]] == [
            step["text"] for step in select_facts(steps, False)
        ]
        assert "status" not in instruction


def test_banks_come_from_guides_and_route_card_has_no_price():
    catalog = get_catalog()
    banks = catalog["banks"]
    assert [bank["label"] for bank in banks[:2]] == ["Т-Банк", "Сбер"]
    assert all(bank["from_data"] for bank in banks if bank["id"] != "other")
    assert banks[-1] == {"id": "other", "label": "Другой", "from_data": False}
    assert [city["name"] for city in catalog["cities"]] == [
        "Москва", "Санкт-Петербург", "Казань", "Екатеринбург", "Новосибирск",
    ]

    route = catalog["routes"][0]
    assert route["title"] == "Москва → Гонконг через Пекин"
    assert route["marker"] == AVIASALES_MARKER
    assert f"marker={AVIASALES_MARKER}" in route["tickets_url"]
    assert "price" not in route
    assert "prices" not in route
    assert "₽" not in "\n".join(route["summary"])
    assert any(line.startswith("🛂") for line in route["summary"])
    assert any("PKX" in line and "PEK" in line for line in route["summary"])
    assert [item["name"] for item in route["airlines"][:5]] == [
        "Аэрофлот", "Air China", "China Eastern", "China Southern", "Hainan Airlines",
    ]
    assert all(item["placeholder"] for item in route["airlines"])
    assert [section["title"] for section in route["sections"]] == [
        "Пересадка", "Трансфер", "Связь", "Ввоз и вывоз", "Штампы и отметки", "Оплата",
    ]
    transfer = route["sections"][1]
    assert any(
        "c1.travelpayouts.com/click" in link["url"] and f"shmarker={AVIASALES_MARKER}" in link["url"]
        for link in transfer["links"]
    )
    assert "Welcome Pickups" in transfer["text"]
    assert not any("PLACEHOLDER" in link["url"] for link in transfer["links"])
    internet = route["sections"][2]
    assert "Airalo" in internet["text"]
    assert internet["links"] == []
    assert "example.com" not in internet["text"]
    assert "тестовый этап" in catalog["privacy"]
    assert "[" not in catalog["privacy"]


def test_init_data_signature_and_dev_switch():
    user = json.dumps({"id": 42, "first_name": "S", "username": "traveler"}, ensure_ascii=False)
    fields = {"auth_date": str(int(time.time())), "query_id": "qid", "user": user, "start_param": "guide_china"}
    raw = sign_init_data(fields, "test-token")
    identity = validate_init_data(raw, bot_token="test-token", max_age_seconds=1000)
    assert identity["telegram_id"] == 42
    assert identity["start_param"] == "guide_china"
    assert identity["dev"] is False
    assert "username" not in identity
    assert "first_name" not in identity
    assert "traveler" not in json.dumps(identity)

    tampered = raw.replace("guide_china", "guide_turkey")
    with pytest.raises(AuthError):
        validate_init_data(tampered, bot_token="test-token")

    stale = dict(fields, auth_date=str(int(time.time()) - 10_000))
    with pytest.raises(AuthError):
        validate_init_data(sign_init_data(stale, "test-token"), bot_token="test-token", max_age_seconds=1000)

    with pytest.raises(AuthError):
        validate_init_data("dev:1001", bot_token="test-token", dev_auth=False)
    assert validate_init_data("dev:1001", bot_token="test-token", dev_auth=True)["telegram_id"] == 1001


def test_screen_names_and_vercel_path():
    assert extract_route("/api/index.py?path=miniapp/session") == "miniapp/session"
    assert extract_route("/api/catalog") == "catalog"
    assert normalize_screen("guide_hong_kong") == "guide_hong_kong"
    assert normalize_screen("section_hong_kong_2_pay_on_site") == "section_hong_kong_2_pay_on_site"
    assert normalize_screen("instruction_wechat_pay") == "instruction_wechat_pay"
    assert normalize_screen("nope") == "trip"

    text, keyboard = notification_message("Чек-лист обновился.", "instruction_wechat_pay")
    assert "Чек-лист" in text
    button = keyboard.inline_keyboard[0][0]
    assert button.web_app is not None
    assert "startapp=instruction_wechat_pay" in button.web_app.url
    assert "callback_data" not in (button.model_dump() if hasattr(button, "model_dump") else {}) or button.callback_data is None

    start = get_start_keyboard("guide_china")
    labels = [item.text for row in start.inline_keyboard for item in row]
    assert "Открыть приложение" in labels
    assert any(item.web_app and "startapp=guide_china" in item.web_app.url for row in start.inline_keyboard for item in row)
    assert any(item.callback_data == "onboarding_show_privacy" for row in start.inline_keyboard for item in row)


@pytest.fixture
def local_store(tmp_path, monkeypatch):
    store = FileMiniappStore(tmp_path / "store.json")
    set_store(store)
    monkeypatch.setattr(settings, "MINIAPP_DEV_AUTH", True)
    yield store
    set_store(None)


def _dev_headers():
    return {"X-Telegram-Init-Data": "dev:1001"}


def test_onboarding_progress_and_report_roundtrip(local_store):
    catalog = get_catalog()
    fact = next(
        fact
        for country in catalog["countries"] if country["slug"] == "china"
        for section in country["sections"] if section["key"] == "3_local_wallets_cards"
        for subsection in section["subsections"]
        for fact in subsection["facts"]
        if fact["hidden"]
    )
    status, payload = dispatch("POST", "miniapp/onboarding", json.dumps({
        "profile": {
            "bank_id": "tbank",
            "departure_city_id": "mow",
            "favorite_countries": ["hong_kong", "china"],
            "notify_checklist": True,
            "notify_trip": False,
            "notify_alerts": True,
            "consent_given": True,
            "onboarding_completed": True,
        },
        "trip": {
            "destination_slug": "hong_kong",
            "depart_date": "2026-11-12",
            "return_date": "2026-11-20",
        },
    }).encode(), _dev_headers())
    assert status == 200, payload
    assert payload["profile"]["bank_id"] == "tbank"
    assert payload["trip"]["destination_slug"] == "hong_kong"
    assert payload["profile"]["notify_trip"] is False
    stored = json.loads(local_store.path.read_text(encoding="utf-8"))
    profile_row = stored["profiles"]["1001"]
    assert "username" not in profile_row
    assert "phone" not in profile_row
    assert "first_name" not in profile_row

    status, denied = dispatch("POST", "miniapp/session", b"{}", {})
    assert status == 401

    status, session = dispatch("POST", "miniapp/session", b"{}", _dev_headers())
    assert status == 200
    assert session["profile"]["onboarding_completed"] is True
    assert session["trip"]["depart_date"] == "2026-11-12"

    status, missing_date = dispatch("POST", "miniapp/onboarding", json.dumps({
        "profile": {
            "bank_id": "sber",
            "departure_city_id": "led",
            "consent_given": True,
            "onboarding_completed": True,
        },
        "trip": {"destination_slug": "georgia"},
    }).encode(), _dev_headers())
    assert status == 400
    assert "дат" in missing_date["error"].lower()

    status, saved = dispatch("POST", "miniapp/progress", json.dumps({
        "item_id": fact["id"],
        "completed": True,
        "kind": "step",
    }).encode(), _dev_headers())
    assert status == 200
    assert saved["progress"]["completed"] is True

    status, report = dispatch("POST", "miniapp/report", json.dumps({
        "fact_id": fact["id"],
        "comment": "  на кассе не сработало  ",
        "fact_text": "подменённый текст",
    }).encode(), _dev_headers())
    assert status == 200
    stored = local_store.raw_reports()
    assert stored[-1]["fact_text"] == fact["text"]
    assert stored[-1]["fact_text"] != "подменённый текст"
    assert stored[-1]["comment"] == "на кассе не сработало"
    assert report["report"]["fact_id"] == fact["id"]

    status, missing = dispatch("POST", "miniapp/report", json.dumps({"fact_id": "nope"}).encode(), _dev_headers())
    assert status == 404


def test_supabase_store_uses_service_tables():
    class Rest:
        def __init__(self):
            self.calls = []

        async def select(self, table, params):
            self.calls.append(("select", table, params))
            return []

        async def upsert(self, table, data, on_conflict):
            self.calls.append(("upsert", table, on_conflict, data))
            return data

        async def insert(self, table, data):
            self.calls.append(("insert", table, data))
            return data

        async def delete(self, table, params):
            self.calls.append(("delete", table, params))
            return []

    rest = Rest()
    store = SupabaseMiniappStore(rest)

    async def run():
        await store.save_profile(7, {
            "bank_id": "sber",
            "departure_city_id": "kzn",
            "favorite_countries": ["turkey"],
            "notify_checklist": True,
            "notify_trip": True,
            "notify_alerts": False,
            "consent_given": True,
            "onboarding_completed": True,
        })
        await store.save_trip(7, {
            "destination_slug": "turkey",
            "departure_city_id": "kzn",
            "depart_date": "2026-12-01",
            "return_date": None,
        })
        await store.add_report(7, {"fact_id": "abc", "fact_text": "факт", "comment": ""})
        await store.delete_user(7)

    import asyncio
    asyncio.run(run())
    assert ("upsert", "miniapp_profiles", "telegram_id") == tuple(rest.calls[0][:3])
    stored_profile = rest.calls[0][3]
    assert "username" not in stored_profile
    assert "phone" not in stored_profile
    assert "first_name" not in stored_profile
    assert ("upsert", "miniapp_trips", "telegram_id") == tuple(rest.calls[1][:3])
    assert rest.calls[2][1] == "miniapp_fact_reports"
    assert {call[1] for call in rest.calls if call[0] == "delete"} == {
        "miniapp_profiles", "miniapp_trips", "miniapp_progress", "miniapp_fact_reports",
    }


def test_partner_links_and_bot_username(monkeypatch):
    from pathlib import Path

    from database.partners import partner_href

    kiwi = partner_href("kiwitaxi")
    assert kiwi is not None
    assert kiwi.startswith("https://c1.travelpayouts.com/click?")
    assert "shmarker=765617" in kiwi
    assert "promo_id=647" in kiwi
    assert partner_href("welcome_pickups") is None
    assert partner_href("airalo") is None
    airalo = partner_href("airalo", project_id="4242")
    assert airalo is not None
    assert airalo.startswith("https://tp.media/r?")
    assert "marker=765617" in airalo
    assert "trs=4242" in airalo
    assert "p=8310" in airalo
    assert "campaign_id=541" in airalo

    monkeypatch.setattr(settings, "BOT_USERNAME", "")
    status, payload = dispatch("GET", "miniapp/config", b"")
    assert status == 200
    assert payload["bot_username"] == ""
    assert payload["bot_url"] is None
    monkeypatch.setattr(settings, "BOT_USERNAME", "ExampleBot")
    status, payload = dispatch("GET", "miniapp/config", b"")
    assert payload["bot_url"] == "https://t.me/ExampleBot"

    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    status, payload = dispatch("GET", "miniapp/config", b"")
    assert status == 200
    assert payload["token_configured"] is False
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "present")
    status, payload = dispatch("GET", "miniapp/config", b"")
    assert payload["token_configured"] is True
    assert "present" not in json.dumps(payload)

    root = Path(__file__).resolve().parents[1]
    screens = (root / "miniapp" / "js" / "screens.js").read_text(encoding="utf-8")
    assert "kiwitaxi" not in screens.lower()
    assert "airalo" not in screens.lower()
    assert "tp.media" not in screens
    landing = (root / "landing" / "index.html").read_text(encoding="utf-8")
    assert "smarttttravel" not in landing
    assert "TravelPaymentsGuideBot" not in landing
    example = (root / ".env.example").read_text(encoding="utf-8")
    assert "BOT_USERNAME=" in example


def test_supabase_flag_ignores_placeholders(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_URL", "http://localhost:54321")
    monkeypatch.setattr(settings, "SUPABASE_KEY", "mock_service_key")
    assert supabase_is_configured() is False
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://abccompany.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_KEY", "service-role-secret")
    assert supabase_is_configured() is True
