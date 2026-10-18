"""Read-only fact-check report: zones, upgrade rule, Telegram text."""

import hashlib
import json
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fact_check_report as report  # noqa: E402
from database.miniapp_catalog import _fact_id  # noqa: E402

AS_OF = date(2026, 10, 18)
CONFIG = report.load_json(report.CONFIG_PATH)
DATA_PATH = ROOT / "database" / "data" / "countries.json"
WORKFLOW = ROOT / ".github" / "workflows" / "fact-check-report.yml"


def _bundle_report(**kwargs):
    params = {"as_of": AS_OF, "check_http": False}
    params.update(kwargs)
    return report.build_report(**params)


def _fact(**overrides):
    base = {
        "text": "Тестовый факт",
        "zone": "red",
        "status": "unconfirmed",
        "source": None,
        "source_kind": "traveler",
        "reports": 1,
        "agreement": "agree",
        "fact_type": "fact",
        "date_verified": "2026-10-10",
        "verified_by_us": False,
        "refuted": False,
        "needs_owner_check": False,
        "decision_needed": None,
        "unknown_zone": None,
    }
    base.update(overrides)
    return base


def _assess(fact, **kwargs):
    params = {
        "config": CONFIG,
        "as_of": AS_OF,
        "scope": "georgia/3_local_wallets_cards/wallets",
        "country": "georgia",
        "category": "wallets",
        "check_http": False,
    }
    params.update(kwargs)
    return report.assess_fact(fact, **params)


def test_unired_is_an_automatic_downgrade():
    built = _bundle_report()
    rows = [
        fact
        for fact in built["facts"]
        if fact["text"].startswith("Unired:") and fact["instruction_id"] is None
    ]
    assert len(rows) == 1
    row = rows[0]
    assert row["country"] == "georgia"
    assert row["current_zone"] == "yellow"
    assert row["computed_zone"] == "red"
    assert row["status"] == "fail"
    assert row["suggested_action"] == "downgrade"
    assert row["automatic"] is True
    assert row["fact_id"] == _fact_id("georgia/3_local_wallets_cards/wallets", row["text"])


def test_expired_july_green_snapshot_is_gone():
    built = _bundle_report()
    stale = [
        fact
        for fact in built["facts"]
        if fact["last_check_date"] == "2026-07-16" and fact["current_zone"] == "green"
    ]
    assert stale == []


def test_corpus_counts_match_the_guide():
    built = _bundle_report()
    summary = built["summary"]
    assert summary["checked"] == 279
    assert summary["gaps"] == 13
    assert summary["needs_owner_decision"] == 10
    assert summary["needs_owner_manual_check"] == 12
    assert summary["unknown_zone"] == 39
    assert summary["refresh_search"] == 12
    country = [fact for fact in built["facts"] if fact["instruction_id"] is None]
    visible = [fact for fact in country if fact["current_zone"] in ("green", "yellow")]
    hidden_url = [fact for fact in visible if "no_public_source" in fact["flags"]]
    assert len(visible) == 161
    assert len(hidden_url) == 66
    assert summary["confirmed"] + summary["not_confirmed"] + summary["stale"] + summary["could_not_check"] == 279


def test_traveler_green_asks_the_owner_in_the_exact_phrase():
    row = _assess(_fact(zone="yellow", reports=5, source_kind="traveler", agreement="agree"))
    assert row["score_zone"] == "green"
    assert row["suggested_action"] == "owner_decision"
    assert row["automatic"] is False
    assert row["upgrade_to"] is None
    assert row["owner_prompt"] == "5 подтверждений, поднять до зелёного?"


def test_three_independent_fresh_confirmations_upgrade_only_to_yellow():
    confirmations = [
        {"person": "Анна", "outlet": "one.example", "date": "2026-10-01"},
        {"person": "Борис", "outlet": "two.example", "date": "2026-10-02"},
        {"person": "Вера", "outlet": "three.example", "date": "2026-10-03"},
    ]
    row = _assess(_fact(zone="red", reports=3, confirmations=confirmations))
    assert row["score_zone"] == "green"
    assert row["suggested_action"] == "upgrade_candidate"
    assert row["automatic"] is True
    assert row["upgrade_to"] == "yellow"
    assert row["owner_prompt"] == "3 подтверждений, поднять до зелёного?"


def test_live_zones_do_not_upgrade_without_the_rule():
    built = _bundle_report()
    order = [zone["name"] for zone in sorted(CONFIG["zones"], key=lambda item: item["min"])]
    rank = {name: index for index, name in enumerate(order)}
    for fact in built["facts"]:
        current = fact["current_zone"]
        computed = fact["computed_zone"]
        if current not in rank or computed not in rank:
            continue
        assert rank[computed] <= rank[current], fact["text"]


def test_early_warning_before_the_class_window_closes():
    share = CONFIG["early_warning"]["share"]
    window = CONFIG["volatility"]["classes"]["fast"]["window_days"]
    green_max = CONFIG["volatility"]["classes"]["fast"]["green_max_days"]
    # The last day inside the green cap is inside the warning share of the class window.
    age = green_max
    assert (green_max + 1 - age) < share * window
    checked = (AS_OF - timedelta(days=age)).isoformat()
    row = _assess(_fact(
        zone="green",
        source_kind="official",
        reports=0,
        agreement="agree",
        source="https://www.rshb.ru/tariffs",
        date_verified=checked,
        volatility_class="fast",
    ))
    assert row["computed_zone"] == CONFIG["upgrade"]["green_zone"]
    assert row["next_zone"] == CONFIG["upgrade"]["yellow_zone"]
    assert row["at_risk"] is True
    assert row["drops_on"]
    assert row["suggested_action"] == CONFIG["early_warning"]["refresh_action"]
    assert "Скоро съедут" in report.render_text({"as_of": "2026-10-18", "scope_label": "тест", "summary": {
        "checked": 1, "confirmed": 0, "not_confirmed": 0, "stale": 0, "could_not_check": 0,
        "needs_owner_decision": 0, "needs_owner_manual_check": 0, "gaps": 0, "unknown_zone": 0,
        "no_public_source": 0, "green_prompts": 0, "at_risk": 1, "refresh_search": 1,
    }, "facts": [row]})


def test_conflict_and_a_failed_source_are_at_risk_without_a_near_drop():
    conflict = _assess(_fact(zone="yellow", agreement=CONFIG["early_warning"]["conflict_agreement"], source_kind="media", reports=0, source="https://example.test/a"))
    assert conflict["at_risk"] is True
    assert CONFIG["early_warning"]["reasons"]["conflict"] in conflict["at_risk_reason"]
    failed = _assess(_fact(
        zone="yellow",
        source_kind="official",
        agreement="agree",
        reports=0,
        source="https://www.rshb.ru/tariffs",
        source_failure_count=CONFIG["early_warning"]["source_failure_min_count"],
        date_verified="2026-10-17",
        volatility_class="slow",
    ))
    assert failed["at_risk"] is True
    assert failed["suggested_action"] == CONFIG["early_warning"]["refresh_action"]


def test_reposts_of_one_outlet_do_not_upgrade():
    confirmations = [
        {"outlet": "same.example", "date": "2026-10-01"},
        {"outlet": "same.example", "date": "2026-10-02", "repost_of": "same.example"},
        {"outlet": "same.example", "date": "2026-10-03", "repost_of": "same.example"},
        {"outlet": "same.example", "date": "2026-10-04"},
        {"outlet": "same.example", "date": "2026-10-05"},
    ]
    fresh_days = CONFIG["volatility"]["classes"]["medium"]["fresh_days"]
    stats = report.confirmation_stats(_fact(confirmations=confirmations), AS_OF, fresh_days)
    assert stats["independent"] is True
    assert stats["fresh_count"] == 1
    row = _assess(_fact(zone="red", reports=5, confirmations=confirmations))
    assert row["suggested_action"] == "owner_decision"
    assert row["automatic"] is False
    assert row["upgrade_to"] is None


def test_official_page_confirms_green_only_when_wording_is_checked():
    source = "https://www.rshb.ru/natural/cards/tariffs"
    opened = {"url": source, "status_code": 200, "error": None, "content_confirmed": False}
    confirmed = {"url": source, "status_code": 200, "error": None, "content_confirmed": True}
    fact = _fact(
        zone="yellow",
        source_kind="official",
        reports=0,
        source=source,
        agreement="agree",
    )
    pending = _assess(fact, check_http=True, http_by_url={source: opened})
    assert pending["suggested_action"] == "owner_manual_check"
    assert pending["automatic"] is False
    assert pending["upgrade_to"] is None
    ready = _assess(fact, check_http=True, http_by_url={source: confirmed})
    assert ready["suggested_action"] == "upgrade_candidate"
    assert ready["automatic"] is True
    assert ready["upgrade_to"] == "green"
    assert ready["owner_prompt"] is None


def test_fetch_never_marks_content_confirmed(monkeypatch):
    class Response:
        status = 200

        def read(self, _size):
            return b"ok"

        def getcode(self):
            return 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda *_args, **_kwargs: Response())
    opened = report._fetch("https://www.rshb.ru/tariffs", 1)
    assert opened["status_code"] == 200
    assert opened["content_confirmed"] is False

    def raise_missing(*_args, **_kwargs):
        raise urllib.error.HTTPError("https://example.test/missing", 404, "missing", hdrs=None, fp=None)

    monkeypatch.setattr(urllib.request, "urlopen", raise_missing)
    missing = report._fetch("https://example.test/missing", 1)
    assert missing["status_code"] == 404
    assert missing["content_confirmed"] is False


def test_official_publisher_is_a_bank_operator_or_government_site():
    assert report.is_official_publisher("https://www.rshb.ru/tariffs")
    assert report.is_official_publisher("https://cbr.ru/faq/")
    assert report.is_official_publisher("https://www.octopus.com.hk/cards")
    assert report.is_official_publisher("https://english.www.gov.cn/news")
    assert report.is_official_publisher("https://www.immigration.go.th/visa") is True
    assert report.is_official_publisher("https://georgiaguidebook.com/tbc") is False
    assert report.is_official_publisher("https://card-open.ru/vtb") is False


def test_app_shows_live_unired_and_july_cards():
    from database.knowledge_base import GEORGIA_DATA, INSTRUCTIONS, iter_facts

    unired = [fact for fact in iter_facts(GEORGIA_DATA) if fact["text"].startswith("Unired:")]
    assert len(unired) == 1
    assert unired[0]["zone"] == "red"
    assert unired[0]["stored_zone"] == "yellow"
    july = [
        fact for fact in iter_facts(GEORGIA_DATA)
        if fact.get("date_verified") == "2026-07-16" and fact.get("verified_by_us")
    ]
    july.extend(
        step for step in INSTRUCTIONS["tbc_georgia"]["steps"]
        if step.get("date_verified") == "2026-07-16" and step.get("verified_by_us")
    )
    assert [fact["text"] for fact in july] == ["Карта TBC работает везде, где платили (Грузия)."]
    assert all(fact["zone"] != "green" for fact in july)


def test_zone_module_reads_thresholds_from_config():
    source = (ROOT / "database" / "trust_zones.py").read_text(encoding="utf-8")
    report_source = (ROOT / "scripts" / "fact_check_report.py").read_text(encoding="utf-8")
    for needle in ("90", "180", "0.25"):
        assert needle not in source
        assert needle not in report_source
    assert "yellow_min_independent_confirmations" in source
    assert CONFIG["verified_by_us_max_days"] == 90
    assert CONFIG["early_warning"]["share"] == 0.25


def test_country_scope_and_bad_slug():
    georgia = _bundle_report(scope="country", country="georgia")
    assert georgia["summary"]["checked"] > 0
    assert any(fact["text"].startswith("Unired:") for fact in georgia["facts"])
    assert all(fact["country"] == "georgia" for fact in georgia["facts"])
    missing = subprocess.run(
        [sys.executable, "scripts/fact_check_report.py", "--scope", "country", "--country", "narnia", "--no-http"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert missing.returncode == 2


def test_script_does_not_write_product_data():
    before = hashlib.sha256(DATA_PATH.read_bytes()).hexdigest()
    config_before = hashlib.sha256(report.CONFIG_PATH.read_bytes()).hexdigest()
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/fact_check_report.py",
            "--as-of",
            "2026-10-18",
            "--no-http",
            "--json",
            "/tmp/fact_check_report.json",
            "--text",
            "/tmp/fact_check_report.txt",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert hashlib.sha256(DATA_PATH.read_bytes()).hexdigest() == before
    assert hashlib.sha256(report.CONFIG_PATH.read_bytes()).hexdigest() == config_before
    payload = json.loads(Path("/tmp/fact_check_report.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert set(payload["facts"][0]) >= {
        "fact_id",
        "country",
        "category",
        "current_zone",
        "computed_zone",
        "status",
        "reason",
        "source_urls",
        "http_results",
        "last_check_date",
        "suggested_action",
        "next_zone",
        "drops_on",
        "at_risk",
        "at_risk_reason",
    }
    assert "at_risk" in payload["summary"]
    text = Path("/tmp/fact_check_report.txt").read_text(encoding="utf-8")
    assert "Скоро съедут" in text
    assert "Ручные проверки владельца" in text
    assert "Проверено:" in text


def test_telegram_skip_names_the_secret_and_does_not_send():
    built = _bundle_report()

    def fail_send(_token, _chat, _text):
        raise AssertionError("send must not be called")

    skipped = report.deliver_telegram(built, token="", chat_id="", run_url="https://example.test/run", send=fail_send)
    assert skipped["sent"] is False
    assert skipped["secret"] == "TELEGRAM_BOT_TOKEN"
    note = report.telegram_note(skipped)
    assert "TELEGRAM_BOT_TOKEN" in note
    assert "OWNER_TELEGRAM_CHAT_ID" in note

    sent_to = {}

    def capture(token, chat, text):
        sent_to["token"] = token
        sent_to["chat"] = chat
        sent_to["text"] = text

    delivered = report.deliver_telegram(built, token="secret-token", chat_id="", run_url="", send=capture)
    assert delivered["sent"] is True
    assert delivered["chat_id"] == "303653591"
    assert sent_to["chat"] == "303653591"
    assert "secret-token" not in report.telegram_note(delivered)


def test_telegram_message_has_counts_and_stays_within_limit():
    built = _bundle_report()
    messages = report.format_telegram_messages(built, "https://github.com/karat-dev/pay-compass/actions/runs/1")
    assert len(messages) == 1
    text = messages[0]
    assert len(text) <= 4096
    for line in (
        "Проверено:",
        "Сошлось:",
        "Не сошлось:",
        "Не смогли проверить:",
        "Нужно решение владельца:",
        "actions/runs/1",
    ):
        assert line in text
    huge = "строка\n" * 2000
    parts = report.split_telegram(huge, run_url="https://example.test/run/99", limit=500)
    assert parts
    assert all(len(part) <= 500 for part in parts)
    assert any("https://example.test/run/99" in part for part in parts)


def test_blank_scope_means_the_whole_guide(monkeypatch):
    monkeypatch.setenv("FACT_CHECK_SCOPE", "")
    monkeypatch.setenv("FACT_CHECK_COUNTRY", "")
    args = report.parse_args([])
    assert args.scope == "all"
    assert args.country == ""


def test_transfer_section_counts_live_zones_risk_stale_and_gaps():
    from datetime import timedelta

    built = _bundle_report()
    block = built["transfers"]
    labels = CONFIG["display"]["transfer_report"]
    assert block["title"] == labels["title"] == "Трансферы и маршруты"
    assert block["at_risk_label"] == "Скоро съедут"
    assert block["stale_label"] == "Устарело"
    assert block["gap_label"] == CONFIG["display"]["gap_label"]
    counted = sum(item["count"] for item in block["zones"]) + block["gaps"]
    rows = report.transfer_rows(
        report.load_json(report.MODEL_DIR / "rules.json"),
        report.load_json(report.MODEL_DIR / "measurements.json"),
        report.load_json(report.MODEL_DIR / "routes.json"),
        CONFIG,
        AS_OF,
    )
    assert counted == len(rows)
    assert block["gaps"] == len(block["gap_rows"])
    assert block["at_risk"] == len(block["at_risk_rows"])
    assert block["stale"] == len(block["stale_rows"])
    assert block["gaps"] > 0 and block["stale"] > 0
    gap_text = "\n".join(row["text"] for row in block["gap_rows"])
    assert "PEK и PKX" in gap_text
    assert "PVG и SHA" in gap_text
    assert "BKK и DMK" in gap_text
    assert "в город" in gap_text
    assert all("Виза не нужна" not in row["text"] for row in rows)
    green = next(item for item in block["zones"] if item["zone"] == "green")
    yellow = next(item for item in block["zones"] if item["zone"] == "yellow")
    assert green["count"] > 0 and yellow["count"] > 0
    text = report.render_text(built)
    assert text.index(block["title"]) < text.index("Не сошлось с формулой")
    messages = report.format_telegram_messages(built, "https://github.com/karat-dev/pay-compass/actions/runs/1")
    telegram = "\n".join(messages)
    assert block["title"] in telegram
    assert f"{block['at_risk_label']}: {block['at_risk']}" in telegram
    assert f"{block['stale_label']}: {block['stale']}" in telegram
    assert f"{block['gap_label']}: {block['gaps']}" in telegram
    assert all(len(part) <= 4096 for part in messages)
    georgia = _bundle_report(scope="country", country="georgia")
    assert georgia["transfers"]["gaps"] == 0
    assert sum(item["count"] for item in georgia["transfers"]["zones"]) == 0

    rules = report.load_json(report.MODEL_DIR / "rules.json")
    measurements = report.load_json(report.MODEL_DIR / "measurements.json")
    sample = json.loads(json.dumps(measurements["pvg_sha_link_minutes"]))
    travel = CONFIG["volatility"]["classes"][CONFIG["volatility"]["transfer_measures"]["travel_time"]]
    sample["source_date"] = (AS_OF - timedelta(days=int(travel["fresh_days"]))).isoformat()
    sample["date_estimated"] = False
    aged = report.measurement_fact("pvg_sha_link_minutes", sample, rules, AS_OF)
    assert aged["volatility_class"] == CONFIG["volatility"]["transfer_measures"]["travel_time"]
    assert aged["at_risk"] is True
    sample["source_date"] = (AS_OF - timedelta(days=int(travel["fresh_days"]) + 1)).isoformat()
    older = report.measurement_fact("pvg_sha_link_minutes", sample, rules, AS_OF)
    assert report._freshness_is_stale(older, CONFIG)


def test_workflow_schedule_and_push_stay_read_only():
    text = WORKFLOW.read_text(encoding="utf-8")
    script = (ROOT / "scripts" / "fact_check_report.py").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "cron: '0 6 * * 1'" in text
    assert "branches:\n      - main" in text
    assert "database/data/countries.json" in text
    assert "database/data/route_model/measurements.json" in text
    assert "config/trust_config.json" in text
    assert "Трансферы и маршруты" in text
    assert "inputs.scope || 'all'" in text
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "upload-artifact@v4" in text
    assert "TELEGRAM_BOT_TOKEN" in text
    assert "OWNER_TELEGRAM_CHAT_ID" in text
    assert "MINIAPP_DEV_AUTH" not in text
    assert "MINIAPP_DEV_AUTH" not in script
    assert "--http" in text
    assert "--send-telegram" in text
