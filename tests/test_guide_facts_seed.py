"""Guide-fact seed: zones, bank wording, visa rules, and migration SQL."""

from __future__ import annotations

import re
from pathlib import Path

from database.guide_facts_seed import (
    COUNTRY_ROWS,
    DISCLAIMER,
    LEGACY_NOT_IN_GUIDE,
    _PRIVATE_SOURCE_MARKERS,
    assign_zone_status,
    build_guide_fact_rows,
    build_visa_rows,
    count_summary,
    detect_issuers,
    generalize_bank_wording,
    private_marker_in_url,
    render_seed_sql,
)
from database.knowledge_base import public_source_url

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20261127064000_guide_facts.sql"
MIRROR = ROOT / "database" / "migrations" / "008_guide_facts.sql"

BANK_TOKEN = re.compile(
    r"РСХБ|Россельхоз|АТБ|Инго|Т-Банк|Тинькофф|ВТБ|"
    r"(?<![А-Яа-яA-Za-z])МТС(?![А-Яа-яA-Za-z])|Центр-инвест|\bTBC\b|"
    r"Газпромбанк|(?<![А-Яа-яA-Za-z])Сбер(?![А-Яа-яA-Za-z])|\bBoG\b"
)

FK_INDEXES = (
    "idx_card_instructions_country_id ON public.card_instructions (country_id)",
    "idx_raw_posts_source_id ON public.raw_posts (source_id)",
    "idx_recommendations_country_id ON public.recommendations (country_id)",
    "idx_recommendations_partner_id ON public.recommendations (partner_id)",
    "idx_review_fact_links_review_id ON public.review_fact_links (review_id)",
    "idx_source_health_source_id ON public.source_health (source_id)",
    "idx_user_country_access_country_id ON public.user_country_access (country_id)",
    "idx_user_reports_fact_id ON public.user_reports (fact_id)",
)


def _upsert(rows):
    merged = {}
    for row in rows:
        merged[row["source_key"]] = row
    return merged


def test_seed_counts_and_idempotent_keys():
    first = build_guide_fact_rows()
    second = build_guide_fact_rows()
    assert [row["source_key"] for row in first] == [row["source_key"] for row in second]
    assert len(_upsert(first + second)) == len(first)
    summary = count_summary(first)
    assert summary["rows"] == 287
    assert summary["steps"] == 68
    assert summary["box"] == 8
    assert summary["by_country"] == {
        "china": 86,
        "georgia": 89,
        "hong_kong": 19,
        "thailand": 24,
        "turkey": 44,
        "uae": 25,
    }
    assert summary["by_zone"] == {"green": 98, "red": 23, "yellow": 166}
    assert summary["by_status"] == {"active": 255, "gap": 13, "outdated": 17, "refuted": 2}
    assert summary["rows"] == 211 + 68 + 8


def test_zone_rule_not_point_score():
    official = {"status": "confirmed", "source_kind": "official", "source_type": "official", "text": "ok"}
    assert assign_zone_status(official) == ("green", "active")
    unconfirmed = {"status": "unconfirmed", "source_kind": "official", "source_type": "official", "text": "later"}
    assert assign_zone_status(unconfirmed) == ("yellow", "active")
    measured = {"status": "confirmed", "source_kind": "internal", "source_type": "наш опыт", "text": "saw it"}
    assert assign_zone_status(measured) == ("yellow", "active")
    capped = {"status": "confirmed", "source_kind": "official", "source_type": "official", "max_zone": "red", "text": "cap"}
    assert assign_zone_status(capped) == ("red", "active")
    conflict = {"status": "unconfirmed", "source_kind": "traveler", "agreement": "conflict", "text": "split"}
    assert assign_zone_status(conflict) == ("red", "active")
    official_conflict = {
        "status": "confirmed",
        "source_kind": "official",
        "source_type": "official",
        "agreement": "conflict",
        "text": "official list",
    }
    assert assign_zone_status(official_conflict) == ("green", "active")
    gap = {"status": "gap", "fact_type": "gap", "zone": "gap", "text": "не исследовано"}
    assert assign_zone_status(gap) == ("yellow", "gap")
    refuted = {"status": "outdated_or_refuted", "refuted": True, "source_kind": "traveler", "text": "no"}
    assert assign_zone_status(refuted) == ("red", "refuted")
    stale = {"status": "outdated_or_refuted", "refuted": False, "source_kind": "internal", "text": "old"}
    assert assign_zone_status(stale) == ("yellow", "outdated")
    closing = {"status": "unconfirmed", "source_kind": "media", "text": "Сервис закрывается"}
    assert assign_zone_status(closing) == ("red", "active")


def test_rows_follow_zone_rule_and_hide_private_urls():
    rows = build_guide_fact_rows()
    for row in rows:
        assert row["zone"] in {"green", "yellow", "red"}
        assert row["status"] in {"active", "outdated", "refuted", "gap"}
        if row["status"] == "gap":
            assert row["zone"] != "green"
        assert not private_marker_in_url(row["source_url"])
        if row["source_url"]:
            assert row["source_url"].startswith("http")
            low = row["source_url"].lower()
            assert not any(marker in low for marker in _PRIVATE_SOURCE_MARKERS)
        original = row["legacy"]["original_text"]
        assert original
        assert row["legacy"]["original"]["text"] == original


def test_box_facts_are_red_and_india_visa_is_yellow():
    rows = build_guide_fact_rows()
    box = [row for row in rows if row["source_key"].startswith("box:")]
    assert len(box) == 8
    assert {row["zone"] for row in box} == {"red"}
    assert {row["max_zone"] for row in box} == {"red"}
    assert all(row["source_url"] is None for row in box)
    visas = build_visa_rows()
    assert len(visas) == 11
    india = next(row for row in visas if row["country_slug"] == "india")
    assert india["zone"] == "yellow"
    assert india["status"] == "active"
    assert india["source_is_official"] is False
    assert india["citizenship"] == "RU"
    assert india["rule_type"] == "entry"
    assert india["disclaimer"] == DISCLAIMER
    assert all(row["disclaimer"] == DISCLAIMER for row in visas)
    assert sum(1 for row in visas if row["zone"] == "green") == 10


def test_bank_wording_is_general_and_original_stays_in_legacy():
    rows = build_guide_fact_rows()
    normalized = [row for row in rows if row["issuer"]]
    assert len(normalized) == 79
    for row in normalized:
        original = row["legacy"]["original_text"]
        assert detect_issuers(original)
        assert not BANK_TOKEN.search(row["fact"])
        assert row["fact"] != original
        for name in row["issuer"].split(", "):
            assert name
    public, issuer, system = generalize_bank_wording(
        "Оформить UnionPay АТБ/РСХБ как запасной вариант."
    )
    assert public == "Оформить карты UnionPay банков РФ как запасной вариант."
    assert issuer == "РСХБ, АТБ"
    assert system == "UnionPay"
    public, issuer, system = generalize_bank_wording(
        "Т-Банк: перевод в Таиланд по номеру счёта через SWIFT — без комиссии."
    )
    assert public.startswith("Переводы из банков РФ")
    assert "Т-Банк" not in public
    assert issuer == "Т-Банк"
    assert system == "SWIFT"
    untouched, issuer, system = generalize_bank_wording("Наличные USD принимают в аэропорту.")
    assert untouched == "Наличные USD принимают в аэропорту."
    assert issuer is None and system is None


def test_private_source_helper_blocks_telegram_and_forums():
    hidden = public_source_url(
        {
            "source": "https://t.me/chinaguide/1",
            "source_user_facing": True,
            "source_kind": "traveler",
            "source_type": "telegram",
        }
    )
    assert hidden is None
    assert private_marker_in_url("https://forum.awd.ru/viewtopic.php?t=1")
    forum = public_source_url(
        {
            "source": "https://example.com/forum/thread",
            "source_user_facing": True,
            "source_kind": "forum",
            "source_type": "forum",
        }
    )
    assert forum is None


def test_migration_sql_is_additive_and_matches_the_seed():
    sql = MIGRATION.read_text(encoding="utf-8")
    mirror = MIRROR.read_text(encoding="utf-8")
    assert mirror.startswith("-- Same migration as supabase/migrations/20261127064000_guide_facts.sql.")
    assert sql in mirror
    seed = render_seed_sql()
    assert seed in sql
    assert "ON CONFLICT (source_key) DO UPDATE" in sql
    assert "ON CONFLICT (citizenship, country_slug, rule_type) DO UPDATE" in sql
    assert "ON CONFLICT (slug) DO UPDATE" in sql
    for index in FK_INDEXES:
        assert f"CREATE INDEX IF NOT EXISTS {index}" in sql
    for column_index in (
        "idx_guide_facts_country_topic ON public.guide_facts (country_slug, topic)",
        "idx_guide_facts_zone ON public.guide_facts (zone)",
        "idx_guide_facts_checked_at ON public.guide_facts (checked_at)",
        "idx_guide_facts_instruction_id ON public.guide_facts (instruction_id)",
    ):
        assert f"CREATE INDEX IF NOT EXISTS {column_index}" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "TO anon, authenticated" in sql
    assert "GRANT SELECT ON TABLE public.guide_facts, public.visa_rules TO anon, authenticated;" in sql
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.guide_facts, public.visa_rules TO service_role;" in sql
    for line in sql.splitlines():
        if "TO anon" in line or "TO authenticated" in line:
            assert "INSERT" not in line
            assert "UPDATE" not in line
            assert "DELETE" not in line
    upper = sql.upper()
    assert "DROP TABLE" not in upper
    assert "DELETE FROM" not in upper
    assert "TRUNCATE" not in upper
    for slug, _name, iso2, in_guide in COUNTRY_ROWS:
        assert f"'{slug}'" in sql
        assert f"'{iso2}'" in sql
        if slug in LEGACY_NOT_IN_GUIDE:
            assert in_guide is False
    assert "'china'" in sql and "TRUE" in sql
    assert "in_guide = EXCLUDED.in_guide" in sql
