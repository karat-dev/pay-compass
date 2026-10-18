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
    assert route["departure_city_id"] == "mow"
    assert route["destination_slug"] == "hong_kong"
    assert route["iata"] == "MOW · PEK · HKG"
    assert route["marker"] == AVIASALES_MARKER
    assert catalog["tickets_marker"] == AVIASALES_MARKER
    assert f"marker={AVIASALES_MARKER}" in route["tickets_url"]
    assert "HKG" in route["tickets_url"]
    china = next(country for country in catalog["countries"] if country["slug"] == "china")
    assert china["ticket_iata"] == "BJS"
    assert "HKG" not in china["ticket_iata"]
    assert "price" not in route
    assert "prices" not in route
    assert "₽" not in "\n".join(route["summary"])
    assert any(line.startswith("🛂") for line in route["summary"])
    assert any("PKX" in line and "PEK" in line for line in route["summary"])
    airline_names = [item["name"] for item in route["airlines"]]
    assert airline_names == [
        "Аэрофлот", "Air China", "China Eastern", "China Southern", "Hainan Airlines",
        "Cathay Pacific", "Hong Kong Airlines",
    ]
    assert airline_names.count("Air China") == 1
    assert all(item["placeholder"] for item in route["airlines"])
    assert any("для паспорта РФ" in line for line in route["summary"])
    assert [section["title"] for section in route["sections"]] == [
        "Пересадка", "Трансфер", "Связь", "Ввоз и вывоз", "Штампы и отметки", "Оплата",
    ]
    transfer = route["sections"][1]
    assert transfer["links"] == [
        {
            "label": "KiwiTaxi",
            "url": "https://kiwitaxi.tpk.lv/SYHLlog7?erid=2VtzqwJNmCZ",
            "placeholder": False,
            "partner": True,
        },
        {
            "label": "GetTransfer",
            "url": "https://gettransfer.tpk.lv/ZfIWEo1o?erid=2VtzqwTGgtd",
            "placeholder": False,
            "partner": True,
        },
    ]
    assert "Welcome Pickups" not in transfer["text"]
    assert "партнёрская ссылка" in transfer["text"]
    assert not any("PLACEHOLDER" in link["url"] for link in transfer["links"])
    internet = route["sections"][2]
    assert "Airalo" in internet["text"]
    assert "Yesim" in internet["text"]
    assert internet["links"] == [
        {
            "label": "Airalo",
            "url": "https://airalo.tpk.lv/NK1pNs4y?erid=2VtzqwXiejf",
            "placeholder": False,
            "partner": True,
        },
        {
            "label": "Yesim",
            "url": "https://yesim.tpk.lv/acVRMvIx?erid=2VtzqwNpj3b",
            "placeholder": False,
            "partner": True,
        },
    ]
    assert "партнёрская ссылка" in internet["text"]
    assert "example.com" not in internet["text"]
    offers = {offer["id"]: offer for offer in catalog["offers"]}
    assert catalog["partner_note"] == "партнёрская ссылка"
    assert offers["cherehapa"] == {
        "id": "cherehapa",
        "placement": "checklist",
        "label": "Оформить страховку",
        "url": "https://cherehapa.tpk.lv/gacNF5aA?erid=2VtzqwQJiKw",
    }
    assert "welcome_pickups" not in offers
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


# Frozen sample signed with token "123456789:AAFakeTokenForSignatureTest".
# auth_date 1700000000, user id 4242, start_param guide_china.
SIGNED_INIT_DATA = (
    "auth_date=1700000000&query_id=AAE"
    "&user=%7B%22id%22%3A4242%2C%22first_name%22%3A%22Ann%22%7D"
    "&start_param=guide_china"
    "&hash=ea0bc1f113e4208ba3cb878f45f2ccc613f5b77a65e7bf4249dfd73ef2448805"
)
SIGNATURE_TOKEN = "123456789:AAFakeTokenForSignatureTest"


def test_frozen_init_data_matches_telegram_hmac():
    identity = validate_init_data(
        SIGNED_INIT_DATA,
        bot_token=SIGNATURE_TOKEN,
        dev_auth=False,
        now=1700000100,
    )
    assert identity == {
        "telegram_id": 4242,
        "start_param": "guide_china",
        "dev": False,
    }
    with pytest.raises(AuthError) as mismatch:
        validate_init_data(
            SIGNED_INIT_DATA,
            bot_token=SIGNATURE_TOKEN + "x",
            dev_auth=False,
            now=1700000100,
        )
    assert mismatch.value.status == 401
    assert "подтвердить" in mismatch.value.message


def test_signed_session_rejects_dev_login(local_store, monkeypatch):
    monkeypatch.setattr(settings, "MINIAPP_DEV_AUTH", False)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", SIGNATURE_TOKEN)
    user = json.dumps({"id": 4242, "first_name": "Ann"}, separators=(",", ":"))
    raw = sign_init_data(
        {
            "auth_date": str(int(time.time())),
            "query_id": "AAE",
            "user": user,
            "start_param": "guide_china",
        },
        SIGNATURE_TOKEN,
    )
    status, empty = dispatch("POST", "miniapp/session", b"{}", {})
    assert status == 401
    assert empty["error"] == "Откройте приложение из Telegram."

    status, dev = dispatch("POST", "miniapp/session", b"{}", {"X-Telegram-Init-Data": "dev:1001"})
    assert status == 401
    assert dev["error"] == "Локальный вход выключен."

    status, session = dispatch("POST", "miniapp/session", b"{}", {"X-Telegram-Init-Data": raw})
    assert status == 200, session
    assert session["telegram_id"] == 4242
    assert session["screen"] == "guide_china"
    dumped = json.dumps(session, ensure_ascii=False)
    assert "Ann" not in dumped
    assert "first_name" not in dumped


def test_intro_flag_is_once_and_date_stays_empty(local_store):
    status, session = dispatch("POST", "miniapp/session", b"{}", _dev_headers())
    assert status == 200
    assert session["intro_seen"] is False
    assert session["profile"] is None

    status, marked = dispatch("POST", "miniapp/intro", b"{}", _dev_headers())
    assert status == 200, marked
    assert marked["intro_seen"] is True
    assert marked["profile"]["intro_seen"] is True
    assert marked["profile"]["bank_id"] is None

    status, again = dispatch("POST", "miniapp/intro", b"{}", _dev_headers())
    assert again["intro_seen"] is True

    status, session = dispatch("POST", "miniapp/session", b"{}", _dev_headers())
    assert session["intro_seen"] is True
    assert session["trip"] is None

    status, saved = dispatch("POST", "miniapp/onboarding", json.dumps({
        "profile": {
            "bank_id": "tbank",
            "departure_city_id": "mow",
            "favorite_countries": ["hong_kong"],
            "consent_given": True,
            "onboarding_completed": True,
        },
        "trip": {"destination_slug": "hong_kong"},
    }).encode(), _dev_headers())
    assert status == 200, saved
    assert saved["profile"]["intro_seen"] is True
    assert saved["trip"]["depart_date"] is None
    stored = json.loads(local_store.path.read_text(encoding="utf-8"))
    assert stored["profiles"]["1001"]["intro_seen"] is True
    assert stored["trips"]["1001"]["depart_date"] is None


def test_client_flow_keeps_intro_ahead_of_deep_links():
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    script = """
import { afterPick, bootTarget, introExit, routeForTrip, searchTicketsUrl, tripCountdown, tripWhen } from "./miniapp/js/flow.js";
import { ticketsUrl } from "./miniapp/js/ui.js";
const assert = (ok, message) => { if (!ok) { console.error(message); process.exit(1); } };
assert(bootTarget({ introSeen: false, deepLink: "/guide/china", hash: "#/sos" }) === "/intro", "intro first");
assert(bootTarget({ introSeen: true, deepLink: "/guide/china", hash: "" }) === "/guide/china", "then deep link");
assert(bootTarget({ introSeen: true, deepLink: "/guide/china", hash: "#tgWebAppData=1" }) === "/guide/china", "ignore telegram hash");
assert(bootTarget({ introSeen: true, deepLink: "", hash: "#/sos" }) === "/sos", "keep app hash");
assert(introExit({ action: "pick", deepLink: "/guide/china" }) === "/pick", "pick before target");
assert(introExit({ action: "skip", deepLink: "/guide/china" }) === "/guide/china", "skip to target");
assert(introExit({ action: "skip", deepLink: "" }) === "/guide", "skip to guide");
assert(afterPick({ deepLink: "/guide/china" }) === "/guide/china", "finish on target");
assert(afterPick({ deepLink: "" }) === "/trip", "finish on trip");
assert(tripWhen("") === "Дата не выбрана", "missing date");
assert(tripWhen(null) === "Дата не выбрана", "null date");
assert(tripCountdown(null) === "", "no countdown");
assert(tripCountdown(0) === "Вылет сегодня", "chosen today");
const hkg = {
  id: "mow_hkg_via_pek",
  departure_city_id: "mow",
  destination_slug: "hong_kong",
  tickets_url: "https://www.aviasales.ru/search/MOW{DDMM}HKG1?marker=765617",
};
const routes = [hkg];
assert(routeForTrip(routes, { departure_city_id: "mow", destination_slug: "china" }) === null, "china has no hkg card");
assert(routeForTrip(routes, { departure_city_id: "led", destination_slug: "hong_kong" }) === null, "other origin");
assert(routeForTrip(routes, { departure_city_id: "mow", destination_slug: "hong_kong" }) === hkg, "moscow hong kong");
const chinaUrl = searchTicketsUrl({ origin: "MOW", destination: "BJS", depart: "2026-10-31", marker: "765617" });
assert(chinaUrl === "https://www.aviasales.ru/search/MOW3110BJS1?marker=765617", chinaUrl);
assert(!chinaUrl.includes("HKG"), "china link is not hong kong");
assert(searchTicketsUrl({ origin: "MOW", destination: "", depart: "2026-10-31", marker: "765617" }) === "", "hide a link we cannot build");
const hkgUrl = ticketsUrl(hkg, "2026-11-12");
assert(hkgUrl.includes("MOW1211HKG1") && hkgUrl.includes("marker=765617"), hkgUrl);
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    screens = (root / "miniapp" / "js" / "screens.js").read_text(encoding="utf-8")
    main = (root / "miniapp" / "js" / "main.js").read_text(encoding="utf-8")
    intro = screens.split("function introScreen", 1)[1].split("function dateFields", 1)[0]
    assert "Платите за границей без сюрпризов" in intro
    assert "Мы честно показываем, насколько уверены" in intro
    assert "Показать непроверенное" in intro
    assert "не исследовано" in intro
    assert "Всё к поездке в одном месте" in intro
    assert "Без лишнего" in intro
    assert "Ссылки на eSIM, страховку и трансфер — партнёрские." in intro
    assert ">скоро<" in intro
    assert "Пропустить" in intro
    assert "Справочник" not in intro
    assert "Гонконг" not in intro
    assert "[0, 1, 2, 3]" in screens
    assert "catalog.routes[0]" not in screens
    assert "MOW · PEK · HKG" not in screens
    assert "routeForTrip" in screens
    assert "Разбор этого маршрута пока не готов" in screens
    assert "Подобрать под поездку" in screens
    assert "Дата не выбрана" in screens
    assert "Подбор под поездку" in screens
    assert "Сообщить о неточности" in screens
    assert "Укажите дату вылета" not in main
    assert "intro_seen" in main
    assert "Math.min(3" in main
    css = (root / "miniapp" / "styles.css").read_text(encoding="utf-8")
    assert ".section-grid { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }" in css
    assert "overflow-wrap: anywhere" in css
    settings_source = (root / "config" / "settings.py").read_text(encoding="utf-8")
    assert "MINIAPP_DEV_AUTH: bool = False" in settings_source


def test_page_loads_telegram_sdk_and_names_the_failed_step():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    html = (root / "miniapp" / "index.html").read_text(encoding="utf-8")
    sdk = html.find("https://telegram.org/js/telegram-web-app.js")
    module = html.find('src="./js/main.js"')
    assert 0 <= sdk < module
    assert "if (live) return;" in html
    main = (root / "miniapp" / "js" / "main.js").read_text(encoding="utf-8")
    assert "tgWebAppData" in main
    assert 'failedTitle = "Не удалось войти"' in main
    assert 'failedTitle = "Справочник не открылся"' in main
    screens = (root / "miniapp" / "js" / "screens.js").read_text(encoding="utf-8")
    assert "state.failedTitle" in screens
    assert "<h2>Справочник не открылся</h2>" not in screens
    settings_source = (root / "config" / "settings.py").read_text(encoding="utf-8")
    assert "MINIAPP_DEV_AUTH: bool = False" in settings_source


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

    status, open_date = dispatch("POST", "miniapp/onboarding", json.dumps({
        "profile": {
            "bank_id": "sber",
            "departure_city_id": "led",
            "consent_given": True,
            "onboarding_completed": True,
            "intro_seen": True,
        },
        "trip": {"destination_slug": "georgia"},
    }).encode(), _dev_headers())
    assert status == 200, open_date
    assert open_date["trip"]["depart_date"] is None
    assert open_date["trip"]["return_date"] is None
    assert open_date["profile"]["intro_seen"] is True

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
    profile_upsert = next(call for call in rest.calls if call[0] == "upsert" and call[1] == "miniapp_profiles")
    assert profile_upsert[2] == "telegram_id"
    stored_profile = profile_upsert[3]
    assert "username" not in stored_profile
    assert "phone" not in stored_profile
    assert "first_name" not in stored_profile
    assert ("upsert", "miniapp_trips", "telegram_id") in [tuple(call[:3]) for call in rest.calls]
    assert any(call[1] == "miniapp_fact_reports" for call in rest.calls)
    assert {call[1] for call in rest.calls if call[0] == "delete"} == {
        "miniapp_profiles", "miniapp_trips", "miniapp_progress", "miniapp_fact_reports",
    }


def test_partner_links_and_bot_username(monkeypatch):
    from pathlib import Path

    from database.partners import partner_href

    kiwi = partner_href("kiwitaxi")
    assert kiwi == "https://kiwitaxi.tpk.lv/SYHLlog7?erid=2VtzqwJNmCZ"
    assert partner_href("kiwitaxi", project_id="4242") == kiwi
    assert partner_href("gettransfer") == "https://gettransfer.tpk.lv/ZfIWEo1o?erid=2VtzqwTGgtd"
    airalo = partner_href("airalo")
    assert airalo == "https://airalo.tpk.lv/NK1pNs4y?erid=2VtzqwXiejf"
    assert "erid=2VtzqwXiejf" in airalo
    assert partner_href("airalo", project_id="4242") == airalo
    assert partner_href("yesim") == "https://yesim.tpk.lv/acVRMvIx?erid=2VtzqwNpj3b"
    assert partner_href("cherehapa") == "https://cherehapa.tpk.lv/gacNF5aA?erid=2VtzqwQJiKw"
    from database.partners import load_partner_config
    assert "welcome_pickups" not in load_partner_config()["partners"]

    monkeypatch.setattr(settings, "BOT_USERNAME", "")
    status, payload = dispatch("GET", "miniapp/config", b"")
    assert status == 200
    assert payload["bot_username"] == ""
    assert payload["bot_url"] is None
    monkeypatch.setattr(settings, "BOT_USERNAME", "ExampleBot")
    status, payload = dispatch("GET", "miniapp/config", b"")
    assert payload["bot_url"] == "https://t.me/ExampleBot"

    from config.settings import bot_token

    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr(settings, "BOT_TOKEN", "mock_token_for_dev")
    status, payload = dispatch("GET", "miniapp/config", b"")
    assert status == 200
    assert payload["token_configured"] is False
    assert bot_token() == "mock_token_for_dev"

    monkeypatch.setenv("BOT_TOKEN", "fallback-token")
    assert bot_token() == "fallback-token"
    status, payload = dispatch("GET", "miniapp/config", b"")
    assert payload["token_configured"] is True
    assert "fallback-token" not in json.dumps(payload)

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "primary-token")
    assert bot_token() == "primary-token"
    status, payload = dispatch("GET", "miniapp/config", b"")
    assert payload["token_configured"] is True
    assert "primary-token" not in json.dumps(payload)

    root = Path(__file__).resolve().parents[1]
    screens = (root / "miniapp" / "js" / "screens.js").read_text(encoding="utf-8")
    assert "kiwitaxi" not in screens.lower()
    assert "airalo" not in screens.lower()
    assert "yesim" not in screens.lower()
    assert "gettransfer" not in screens.lower()
    assert "cherehapa" not in screens.lower()
    assert "tp.media" not in screens
    assert "tpk.lv" not in screens
    assert "partner_note" in screens
    assert "checklist" in screens and "placement" in screens
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
