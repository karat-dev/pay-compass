"""Read-only fact-check report: zones, upgrade rule, Telegram text."""

import hashlib
import json
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date
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


def test_july_own_experience_stays_a_manual_check():
    built = _bundle_report()
    july = [
        fact
        for fact in built["facts"]
        if fact["last_check_date"] == "2026-07-16" and "own_experience_override" in fact["flags"]
    ]
    assert len(july) == 10
    for fact in july:
        assert fact["current_zone"] == "green"
        assert fact["score_zone"] == "black"
        assert fact["computed_zone"] == "green"
        assert fact["status"] == "stale"
        assert fact["suggested_action"] == "owner_manual_check"
        assert fact["automatic"] is False


def test_corpus_counts_match_the_guide():
    built = _bundle_report()
    summary = built["summary"]
    assert summary["checked"] == 267
    assert summary["gaps"] == 11
    assert summary["needs_owner_decision"] == 8
    assert summary["needs_owner_manual_check"] == 17
    assert summary["unknown_zone"] == 43
    country = [fact for fact in built["facts"] if fact["instruction_id"] is None]
    visible = [fact for fact in country if fact["current_zone"] in ("green", "yellow")]
    hidden_url = [fact for fact in visible if "no_public_source" in fact["flags"]]
    assert len(visible) == 160
    assert len(hidden_url) == 78
    assert summary["confirmed"] + summary["not_confirmed"] + summary["stale"] + summary["could_not_check"] == 267


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


def test_reposts_of_one_outlet_do_not_upgrade():
    confirmations = [
        {"outlet": "same.example", "date": "2026-10-01"},
        {"outlet": "same.example", "date": "2026-10-02", "repost_of": "same.example"},
        {"outlet": "same.example", "date": "2026-10-03", "repost_of": "same.example"},
        {"outlet": "same.example", "date": "2026-10-04"},
        {"outlet": "same.example", "date": "2026-10-05"},
    ]
    stats = report.confirmation_stats(_fact(confirmations=confirmations), AS_OF, 30)
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
    }
    text = Path("/tmp/fact_check_report.txt").read_text(encoding="utf-8")
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


def test_workflow_is_manual_and_does_not_enable_dev_auth():
    text = WORKFLOW.read_text(encoding="utf-8")
    script = (ROOT / "scripts" / "fact_check_report.py").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "schedule:" not in text
    assert "upload-artifact@v4" in text
    assert "TELEGRAM_BOT_TOKEN" in text
    assert "OWNER_TELEGRAM_CHAT_ID" in text
    assert "MINIAPP_DEV_AUTH" not in text
    assert "MINIAPP_DEV_AUTH" not in script
    assert "--http" in text
    assert "--send-telegram" in text
