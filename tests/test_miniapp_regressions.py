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
