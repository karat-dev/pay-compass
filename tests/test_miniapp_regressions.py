"""Rendered regressions for the trip route, the four-screen intro, and profile replay."""

import json
import shutil
import subprocess
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from api.index import handler
from api.miniapp_http import dispatch
from config.settings import settings
from database.miniapp_catalog import get_catalog
from database.miniapp_store import FileMiniappStore, set_store

ROOT = Path(__file__).resolve().parents[1]


def _dev_headers():
    return {"X-Telegram-Init-Data": "dev:1001"}


@pytest.fixture
def local_store(tmp_path, monkeypatch):
    store = FileMiniappStore(tmp_path / "store.json")
    set_store(store)
    monkeypatch.setattr(settings, "MINIAPP_DEV_AUTH", True)
    yield store
    set_store(None)


def _render_catalog(catalog, script):
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        input=json.dumps(catalog),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


RENDER_TRIPS = r"""
const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const catalog = JSON.parse(Buffer.concat(chunks).toString("utf8"));
globalThis.location = { hash: "#/trip", search: "", hostname: "127.0.0.1" };
globalThis.document = { documentElement: { dataset: {}, style: {} }, querySelector() { return null; } };
const { render } = await import("./miniapp/js/screens.js");

function paint(trip) {
  location.hash = "#/trip";
  const html = render({
    catalog,
    trip,
    profile: {
      bank_id: "tbank",
      departure_city_id: "mow",
      favorite_countries: [trip.destination_slug],
      notify_checklist: true,
      notify_trip: true,
      notify_alerts: false,
      intro_seen: true,
    },
    progress: {},
    unverified: {},
    openRoute: "",
    draft: {},
    sheet: null,
  });
  const ticket = html.split('<article class="ticket">')[1].split("</article>")[0];
  return { html, ticket };
}

const china = paint({
  destination_slug: "china",
  departure_city_id: "mow",
  depart_date: "2026-10-31",
  return_date: "2026-11-14",
});
const hongKong = paint({
  destination_slug: "hong_kong",
  departure_city_id: "mow",
  depart_date: "2026-11-12",
  return_date: "2026-11-20",
});
process.stdout.write(JSON.stringify({ china, hongKong }));
"""


def test_china_trip_has_no_hong_kong_route():
    painted = _render_catalog(get_catalog(), RENDER_TRIPS)["china"]
    ticket = painted["ticket"]
    assert "Разбор этого маршрута пока не готов" in ticket
    assert "https://www.aviasales.ru/search/MOW3110BJS1?marker=765617" in ticket
    assert "MOW · PEK · HKG" not in ticket
    assert "Москва → Гонконг через Пекин" not in ticket
    assert "HKG" not in ticket


def test_hong_kong_trip_keeps_its_breakdown():
    painted = _render_catalog(get_catalog(), RENDER_TRIPS)["hongKong"]
    ticket = painted["ticket"]
    assert "Москва → Гонконг через Пекин" in ticket
    assert "MOW · PEK · HKG" in ticket
    assert "MOW1211HKG1" in ticket
    assert "marker=765617" in ticket
    assert "Разбор этого маршрута пока не готов" not in ticket


RENDER_INTRO = r"""
const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const catalog = JSON.parse(Buffer.concat(chunks).toString("utf8"));
globalThis.location = { hash: "#/intro", search: "", hostname: "127.0.0.1" };
globalThis.document = { documentElement: { dataset: {}, style: {} }, querySelector() { return null; } };
const { render } = await import("./miniapp/js/screens.js");
const state = { catalog, introStep: 0, sheet: null, profile: { intro_seen: false }, trip: null };
const screens = [0, 1, 2, 3].map((step) => {
  state.introStep = step;
  const html = render(state);
  const dots = html.match(/<p class="intro-dots"[\s\S]*?<\/p>/)[0];
  const marks = [...dots.matchAll(/<span class="([^"]*)"/g)].map((item) => item[1].includes("is-on"));
  const title = html.match(/<h2>(.*?)<\/h2>/)[1];
  return { title, marks, html };
});
process.stdout.write(JSON.stringify(screens));
"""


def test_intro_has_four_screens_and_confidence_is_second():
    screens = _render_catalog(get_catalog(), RENDER_INTRO)
    assert [item["title"] for item in screens] == [
        "Платите за границей без сюрпризов",
        "Мы честно показываем, насколько уверены",
        "Всё к поездке в одном месте",
        "Без лишнего",
    ]
    assert [item["marks"] for item in screens] == [
        [True, False, False, False],
        [False, True, False, False],
        [False, False, True, False],
        [False, False, False, True],
    ]
    confidence = screens[1]["html"]
    assert 'data-zone="green"' in confidence
    assert 'data-zone="yellow"' in confidence
    assert 'data-zone="red"' in confidence
    assert 'data-zone="black"' in confidence
    assert "Показать непроверенное" in confidence
    assert "не исследовано" in confidence


def test_profile_replay_opens_intro_without_wiping_trip(local_store):
    status, saved = dispatch("POST", "miniapp/onboarding", json.dumps({
        "profile": {
            "bank_id": "sber",
            "departure_city_id": "mow",
            "favorite_countries": ["china"],
            "notify_checklist": True,
            "notify_trip": True,
            "notify_alerts": False,
            "consent_given": True,
            "onboarding_completed": True,
        },
        "trip": {
            "destination_slug": "china",
            "departure_city_id": "mow",
            "depart_date": "2026-10-31",
            "return_date": "2026-11-14",
        },
    }).encode(), _dev_headers())
    assert status == 200, saved

    status, marked = dispatch("POST", "miniapp/intro", b"{}", _dev_headers())
    assert status == 200, marked
    assert marked["profile"]["bank_id"] == "sber"
    assert marked["profile"]["departure_city_id"] == "mow"
    assert marked["profile"]["favorite_countries"] == ["china"]
    assert marked["intro_seen"] is True

    status, session = dispatch("POST", "miniapp/session", b"{}", _dev_headers())
    assert session["trip"]["destination_slug"] == "china"
    assert session["trip"]["depart_date"] == "2026-10-31"
    assert session["trip"]["return_date"] == "2026-11-14"
    assert session["profile"]["bank_id"] == "sber"

    script = r"""
import { beginIntroReplay, introExit } from "./miniapp/js/flow.js";
const state = {
  introStep: 3,
  introSeen: true,
  after: "",
  trip: { destination_slug: "china", departure_city_id: "mow", depart_date: "2026-10-31" },
  profile: { bank_id: "sber", departure_city_id: "mow", favorite_countries: ["china"], intro_seen: true },
};
const trip = state.trip;
const profile = state.profile;
const path = beginIntroReplay(state);
if (path !== "/intro" || state.introStep !== 0) process.exit(1);
if (state.trip !== trip || state.profile !== profile) process.exit(1);
if (state.trip.destination_slug !== "china" || state.profile.bank_id !== "sber") process.exit(1);
if (introExit({ action: "skip", deepLink: state.after }) !== "/guide") process.exit(1);
if (introExit({ action: "pick", deepLink: state.after }) !== "/pick") process.exit(1);
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    screens = (ROOT / "miniapp" / "js" / "screens.js").read_text(encoding="utf-8")
    assert 'data-action="replay-intro">Показать знакомство снова' in screens
    main = (ROOT / "miniapp" / "js" / "main.js").read_text(encoding="utf-8")
    assert 'action === "replay-intro"' in main
    assert "beginIntroReplay" in main


def test_intro_reset_workflow_updates_one_user():
    text = (ROOT / ".github" / "workflows" / "reset-intro-seen.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "SET intro_seen = false" in text
    assert "WHERE telegram_id = :'tid'::bigint" in text
    assert "DELETE" not in text
    assert "303653591" not in text


BACK_AND_FACTS = r"""
import { backPlan } from "./miniapp/js/flow.js";
import { groupFacts, parseRoute } from "./miniapp/js/ui.js";
import { render } from "./miniapp/js/screens.js";

const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const catalog = JSON.parse(Buffer.concat(chunks).toString("utf8"));
globalThis.location = { hash: "#/trip", search: "", hostname: "127.0.0.1" };
globalThis.document = { documentElement: { dataset: {}, style: {} }, querySelector() { return null; } };

function plan(hash, extra = {}) {
  const screen = parseRoute(hash);
  if (extra.instructionSection) screen.instructionSection = extra.instructionSection;
  return backPlan({
    screen,
    stackDepth: extra.stackDepth == null ? 1 : extra.stackDepth,
    introSeen: Boolean(extra.introSeen),
    introStep: extra.introStep || 0,
    pickStep: extra.pickStep || 0,
    instructionIndex: extra.instructionIndex || 0,
    openRoute: extra.openRoute || "",
    sheet: Boolean(extra.sheet),
    returnTo: extra.returnTo || "",
  });
}

const plans = {
  deepCountry: plan("#/guide/china", { introSeen: true }),
  deepSection: plan("#/guide/hong_kong/2_pay_on_site", { introSeen: true }),
  deepChinaPay: plan("#/guide/china/2_pay_on_site", { introSeen: true }),
  payFromTrip: plan("#/guide/china/2_pay_on_site", { introSeen: true, stackDepth: 2 }),
  hongKongPayFromTrip: plan("#/guide/hong_kong/2_pay_on_site", { introSeen: true, stackDepth: 2 }),
  deepFact: plan("#/guide/china/2_pay_on_site?fact=abc", { introSeen: true }),
  deepInstruction: plan("#/guide/turkey/i/mts_tr_qr", { introSeen: true, instructionSection: "2_pay_on_site" }),
  deepPick: plan("#/pick"),
  deepIntroReplay: plan("#/intro", { introSeen: true }),
  firstIntro: plan("#/intro", { introSeen: false }),
  guide: plan("#/guide", { stackDepth: 4 }),
  trip: plan("#/trip", { stackDepth: 3 }),
  history: plan("#/guide/china", { stackDepth: 2, introSeen: true }),
  introStep: plan("#/intro", { introStep: 2, stackDepth: 3 }),
  pickStep: plan("#/pick", { pickStep: 1, stackDepth: 3 }),
  instructionStep: plan("#/guide/turkey/i/mts_tr_qr", { instructionIndex: 2, stackDepth: 3, instructionSection: "2_pay_on_site" }),
  route: plan("#/trip", { openRoute: "route:mow_hkg_via_pek:5", stackDepth: 2 }),
  sheet: plan("#/profile", { sheet: true }),
};

const groups = groupFacts([
  { id: "old-green", zone: "green", date: "01.01.2024" },
  { id: "new-green", zone: "green", date: "02.03.2026" },
  { id: "yellow", zone: "yellow", date: "01.06.2025" },
  { id: "red", zone: "red", date: "01.01.2020" },
  { id: "black", zone: "black", date: "01.02.2020" },
]);

function paint(hash, extra = {}) {
  location.hash = hash;
  return render({
    catalog,
    introSeen: extra.introSeen !== false,
    introStep: extra.introStep || 0,
    step: extra.step || 0,
    stackDepth: extra.stackDepth == null ? 1 : extra.stackDepth,
    unverified: extra.unverified || {},
    progress: {},
    openRoute: extra.openRoute || "",
    trip: extra.trip || null,
    profile: { favorite_countries: [], bank_id: "tbank", departure_city_id: "mow" },
    draft: extra.draft || { bank_id: "tbank", departure_city_id: "mow", destination_slug: "turkey", consent: true },
    cursor: {},
    sheet: null,
  });
}

const closed = paint("#/guide/turkey/2_pay_on_site");
const opened = paint("#/guide/turkey/2_pay_on_site", { unverified: { "turkey/2_pay_on_site": true } });
const headers = {
  guide: paint("#/guide").match(/<header class="header">[\s\S]*?<\/header>/)[0],
  country: paint("#/guide/turkey").match(/<header class="header">[\s\S]*?<\/header>/)[0],
  section: paint("#/guide/turkey/2_pay_on_site").match(/<header class="header">[\s\S]*?<\/header>/)[0],
  trip: paint("#/trip", { trip: { destination_slug: "hong_kong", departure_city_id: "mow", depart_date: "2026-11-12", return_date: "2026-11-20" } }).match(/<header class="header">[\s\S]*?<\/header>/)[0],
  route: paint("#/trip", { openRoute: "route:mow_hkg_via_pek:5", trip: { destination_slug: "hong_kong", departure_city_id: "mow", depart_date: "2026-11-12", return_date: "2026-11-20" } }).match(/<header class="header">[\s\S]*?<\/header>/)[0],
  pick: paint("#/pick").match(/<header class="header">[\s\S]*?<\/header>/)[0],
  intro: paint("#/intro", { introSeen: false, introStep: 0 }).match(/<header class="header">[\s\S]*?<\/header>/)[0],
  replay: paint("#/intro", { introSeen: true, introStep: 0 }).match(/<header class="header">[\s\S]*?<\/header>/)[0],
};

process.stdout.write(JSON.stringify({ plans, groups, closed, opened, headers }));
"""


def _zones(html):
    return __import__("re").findall(r'<div class="fact-group" data-zone="([^"]+)">', html)


def _ids_in_zone(html, zone, following):
    import re
    start = html.index(f'<div class="fact-group" data-zone="{zone}">')
    end = html.index(following, start) if following else len(html)
    return re.findall(r'data-fact-id="([^"]+)"', html[start:end])


def test_back_from_a_deep_link_goes_to_the_parent_screen():
    painted = _render_catalog(get_catalog(), BACK_AND_FACTS)
    plans = painted["plans"]
    assert plans["deepCountry"] == {"type": "parent", "path": "/guide"}
    assert plans["deepSection"] == {"type": "parent", "path": "/guide/hong_kong"}
    assert plans["deepChinaPay"] == {"type": "parent", "path": "/guide/china"}
    assert plans["payFromTrip"] == {"type": "history"}
    assert plans["hongKongPayFromTrip"] == {"type": "history"}
    assert plans["deepFact"] == {"type": "parent", "path": "/guide/china/2_pay_on_site"}
    assert plans["deepInstruction"] == {"type": "parent", "path": "/guide/turkey/2_pay_on_site"}
    assert plans["deepPick"] == {"type": "parent", "path": "/trip"}
    assert plans["deepIntroReplay"] == {"type": "parent", "path": "/profile"}
    assert plans["firstIntro"] == {"type": "none"}
    assert plans["guide"] == {"type": "none"}
    assert plans["trip"] == {"type": "none"}
    assert plans["history"] == {"type": "history"}
    assert plans["introStep"] == {"type": "intro-step"}
    assert plans["pickStep"] == {"type": "pick-step"}
    assert plans["instructionStep"] == {"type": "instruction-step"}
    assert plans["route"] == {"type": "route"}
    assert plans["sheet"] == {"type": "sheet"}
    assert 'data-action="back"' in painted["headers"]["country"]
    assert 'data-action="back"' in painted["headers"]["section"]
    assert 'data-action="back"' in painted["headers"]["pick"]
    assert 'data-action="back"' in painted["headers"]["replay"]
    assert 'data-action="back"' in painted["headers"]["route"]
    assert 'data-action="back"' not in painted["headers"]["guide"]
    assert 'data-action="back"' not in painted["headers"]["trip"]
    assert 'data-action="back"' not in painted["headers"]["intro"]


def test_section_facts_are_grouped_by_confidence_and_date():
    catalog = get_catalog()
    painted = _render_catalog(catalog, BACK_AND_FACTS)
    closed = painted["closed"]
    opened = painted["opened"]
    assert _zones(closed) == ["green", "yellow"]
    assert "Подтверждено" in closed
    assert "Скорее всего верно" in closed
    assert "Сначала подтверждённые, внутри группы — более свежая проверка выше." in closed
    assert "Мало подтверждений" not in closed
    assert "Устарело или опровергнуто" not in closed
    assert _zones(opened)[:2] == ["green", "yellow"]
    assert "red" in _zones(opened)
    assert "black" in _zones(opened)
    assert opened.index("Скрыть непроверенное") < opened.index('<div class="fact-group" data-zone="red">')
    assert opened.index('<div class="instruction-block">') > opened.index('data-zone="black"')
    assert "По шагам" in opened.split('<div class="instruction-block">')[1]

    section = next(item for item in next(country for country in catalog["countries"] if country["slug"] == "turkey")["sections"] if item["key"] == "2_pay_on_site")
    green_ids = _ids_in_zone(closed, "green", '<div class="fact-group" data-zone="yellow">')

    def checked(fact):
        day, month, year = fact["date"].split(".")
        return (year, month, day)

    expected = sorted(
        [fact for fact in section["facts"] if fact["zone"] == "green" and not fact["hidden"]],
        key=checked,
        reverse=True,
    )
    assert green_ids == [fact["id"] for fact in expected]
    assert [group["title"] for group in painted["groups"]] == [
        "Подтверждено", "Скорее всего верно", "Мало подтверждений", "Устарело или опровергнуто",
    ]
    assert [fact["id"] for fact in painted["groups"][0]["facts"]] == ["new-green", "old-green"]




RENDER_ROUTE_DETAILS = r"""
const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const catalog = JSON.parse(Buffer.concat(chunks).toString("utf8"));
globalThis.location = { hash: "#/trip", search: "", hostname: "127.0.0.1" };
globalThis.document = { documentElement: { dataset: {}, style: {} }, querySelector() { return null; } };
const { render } = await import("./miniapp/js/screens.js");
const trip = {
  destination_slug: "hong_kong",
  departure_city_id: "mow",
  depart_date: "2026-11-12",
  return_date: "2026-11-20",
};
const profile = {
  bank_id: "tbank",
  departure_city_id: "mow",
  favorite_countries: ["hong_kong"],
  notify_checklist: true,
  notify_trip: true,
  notify_alerts: false,
  intro_seen: true,
  citizenship: "ru",
};
function paint(openRoute) {
  location.hash = "#/trip";
  return render({
    catalog,
    trip,
    profile,
    progress: {},
    unverified: {},
    openRoute,
    draft: {},
    sheet: null,
  });
}
const closed = paint("");
const payment = paint("route:mow_hkg_via_pek:5");
const transfer = paint("route:mow_hkg_via_pek:1");
location.hash = "#/profile";
const profileHtml = render({
  catalog,
  trip,
  profile,
  progress: {},
  unverified: {},
  openRoute: "",
  draft: {},
  sheet: null,
});
process.stdout.write(JSON.stringify({ closed, payment, transfer, profileHtml }));
"""


def test_route_airlines_are_deduped_and_collapsed():
    painted = _render_catalog(get_catalog(), RENDER_ROUTE_DETAILS)["closed"]
    ticket = painted.split('<article class="ticket">')[1].split("</article>")[0]
    fold = ticket.split('<details class="airline-fold">', 1)
    assert len(fold) == 2
    assert not fold[1].startswith(" open")
    assert "<summary>Авиакомпании на маршруте (7)</summary>" in ticket
    assert ticket.count("Air China") == 1
    assert "Cathay Pacific" in ticket
    assert "Hong Kong Airlines" in ticket
    assert "Страницы авиакомпаний ещё не подключены — пока только названия." in fold[1]
    assert "для паспорта РФ" in ticket
    assert 'class="airline-row"' in fold[1]
    assert ticket.index("airline-row") > ticket.index("<details")


def test_payment_compass_opens_guide_sections():
    painted = _render_catalog(get_catalog(), RENDER_ROUTE_DETAILS)
    payment = painted["payment"]
    assert 'class="jump" data-action="open-section" data-slug="china" data-key="2_pay_on_site">Компас оплаты → Китай</button>' in payment
    assert 'class="jump" data-action="open-section" data-slug="hong_kong" data-key="2_pay_on_site">Компас оплаты → Гонконг</button>' in payment
    transfer = painted["transfer"].split('<div class="route-copy">')[1]
    assert "PEK → город" in transfer
    assert "open-section" not in transfer
    assert "Компас оплаты" not in transfer


def test_profile_passport_setting_is_russian_citizenship():
    painted = _render_catalog(get_catalog(), RENDER_ROUTE_DETAILS)["profileHtml"]
    screen = painted.split('<section class="screen">')[1].split("</section>")[0]
    assert screen.count('data-group="citizenship"') == 1
    assert 'data-id="ru"' in screen
    assert "Гражданство РФ" in screen
    assert "Визы и правила въезда считаем для граждан РФ. Другие паспорта появятся позже." in screen
    assert "скоро" not in screen


def test_citizenship_defaults_to_ru_and_rejects_other_passports(local_store):
    status, marked = dispatch("POST", "miniapp/intro", b"{}", _dev_headers())
    assert status == 200, marked
    assert marked["profile"]["citizenship"] == "ru"
    assert "passport_number" not in marked["profile"]

    body = {
        "bank_id": "sber",
        "departure_city_id": "mow",
        "favorite_countries": ["china"],
        "notify_checklist": True,
        "notify_trip": True,
        "notify_alerts": False,
        "consent_given": True,
        "onboarding_completed": True,
    }
    status, saved = dispatch("POST", "miniapp/profile", json.dumps(body).encode(), _dev_headers())
    assert status == 200, saved
    assert saved["profile"]["citizenship"] == "ru"

    rejected = dict(body)
    rejected["citizenship"] = "de"
    rejected["passport_number"] = "0000"
    status, error = dispatch("POST", "miniapp/profile", json.dumps(rejected).encode(), _dev_headers())
    assert status == 400
    assert error["error"] == "Пока доступно только гражданство РФ."

    status, session = dispatch("POST", "miniapp/session", b"{}", _dev_headers())
    assert session["profile"]["citizenship"] == "ru"
    stored = json.loads(local_store.path.read_text(encoding="utf-8"))
    row = stored["profiles"]["1001"]
    assert row["citizenship"] == "ru"
    assert "passport_number" not in row
    assert "phone" not in row
    assert "first_name" not in row


def test_citizenship_migration_only_adds_a_column():
    supabase_sql = (ROOT / "supabase" / "migrations" / "20261017120000_citizenship.sql").read_text(encoding="utf-8")
    mirror = (ROOT / "database" / "migrations" / "005_citizenship.sql").read_text(encoding="utf-8")
    for text in (supabase_sql, mirror):
        assert "ADD COLUMN IF NOT EXISTS citizenship TEXT NOT NULL DEFAULT 'ru'" in text
        assert "DROP " not in text
        assert "UPDATE " not in text
        assert "DELETE " not in text
    assert "miniapp_profiles" in supabase_sql
    assert "miniapp_trips" not in supabase_sql


def test_georgia_country_page_does_not_scroll_at_320px():
    chrome = shutil.which("google-chrome") or shutil.which("google-chrome-stable")
    if chrome is None and Path("/usr/local/bin/google-chrome").is_file():
        chrome = "/usr/local/bin/google-chrome"
    if chrome is None:
        pytest.skip("Chrome is not installed")
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        result = subprocess.run(
            ["node", str(ROOT / "tests" / "check_country_width.mjs"), base, chrome],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=40,
        )
    finally:
        server.shutdown()
        server.server_close()
    assert result.returncode == 0, result.stdout + result.stderr
    measured = json.loads(result.stdout)
    assert measured["clientWidth"] == 320
    assert measured["scrollWidth"] <= 321
    assert measured["titleRight"] <= 321
