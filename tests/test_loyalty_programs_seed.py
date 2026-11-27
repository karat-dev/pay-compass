"""Loyalty directory seed: counts, zones, idempotency, and no personal data."""

from __future__ import annotations

import json
import re
from pathlib import Path

from database.loyalty_programs_seed import (
    CHECKED_AT,
    DATA_PATH,
    FORBIDDEN_KEYS,
    PUBLIC_ALLIANCE_COLUMNS,
    PUBLIC_PROGRAM_COLUMNS,
    assert_no_personal_data,
    build_alliance_rows,
    build_program_rows,
    count_summary,
    is_official_url,
    load_directory,
    render_seed_sql,
)

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20261127220000_loyalty_programs.sql"
MIRROR = ROOT / "database" / "migrations" / "010_loyalty_programs.sql"

GREEN_PROGRAMS = {"emirates", "flydubai", "qatar-airways"}
GREEN_ALLIANCES = {"star-alliance", "oneworld"}
PROGRAM_ALLIANCES = {
    "turkish-airlines": "star-alliance",
    "air-china": "star-alliance",
    "thai-airways": "star-alliance",
    "china-eastern": "skyteam",
    "aeroflot": "skyteam",
    "qatar-airways": "oneworld",
    "cathay-pacific": "oneworld",
    "pegasus": "none",
    "ajet": "none",
    "emirates": "none",
    "flydubai": "none",
    "etihad": "none",
    "air-arabia": "none",
    "china-southern": "none",
    "hainan-airlines": "none",
    "airasia": "none",
}
MEMBER_HINTS = {
    "turkish-airlines": "Turkish",
    "air-china": "Air China",
    "thai-airways": "Thai",
    "china-eastern": "China Eastern",
    "aeroflot": "Aeroflot",
    "qatar-airways": "Qatar",
    "cathay-pacific": "Cathay",
    "pegasus": "Pegasus",
    "ajet": "AJet",
    "emirates": "Emirates",
    "flydubai": "flydubai",
    "etihad": "Etihad",
    "air-arabia": "Air Arabia",
    "china-southern": "China Southern",
    "hainan-airlines": "Hainan",
    "airasia": "AirAsia",
}


def _anon_columns(sql: str, table: str) -> tuple:
    match = re.search(
        rf"GRANT SELECT \(([^;]*?)\) ON TABLE public\.{table} TO anon, authenticated;",
        sql,
        re.S,
    )
    assert match, f"column-level SELECT grant for {table} is missing"
    return tuple(part.strip() for part in match.group(1).split(",") if part.strip())


def _view_sql(sql: str, view: str) -> str:
    match = re.search(
        rf"CREATE VIEW public\.{view}\b.*?FROM public\.{view.removesuffix('_public')};",
        sql,
        re.S,
    )
    assert match, f"{view} view is missing"
    return match.group(0)


def test_directory_has_four_alliances_and_sixteen_programs():
    payload = load_directory()
    assert payload["checked"] == CHECKED_AT
    assert len(payload["alliances"]) == 4
    assert len(payload["programs"]) == 16
    alliances = build_alliance_rows(payload)
    programs = build_program_rows(payload)
    assert [row["slug"] for row in alliances] == ["star-alliance", "skyteam", "oneworld", "none"]
    assert len({row["slug"] for row in programs}) == 16
    summary = count_summary(alliances, programs)
    assert summary == {
        "alliances": 4,
        "programs": 16,
        "alliance_zones": {"green": 2, "yellow": 2},
        "program_zones": {"green": 3, "yellow": 13},
        "checked_at": CHECKED_AT,
    }


def test_seed_is_idempotent_and_zones_follow_the_official_source_rule():
    first_alliances = build_alliance_rows()
    second_alliances = build_alliance_rows()
    first_programs = build_program_rows()
    second_programs = build_program_rows()
    assert first_alliances == second_alliances
    assert first_programs == second_programs
    assert render_seed_sql() == render_seed_sql(first_alliances, first_programs)
    merged = {}
    for row in first_programs + second_programs:
        merged[row["slug"]] = row
    assert len(merged) == 16

    alliances = {row["slug"]: row for row in first_alliances}
    programs = {row["slug"]: row for row in first_programs}
    assert {slug for slug, row in alliances.items() if row["zone"] == "green"} == GREEN_ALLIANCES
    assert {slug for slug, row in programs.items() if row["zone"] == "green"} == GREEN_PROGRAMS
    for row in programs.values():
        assert row["zone"] in {"green", "yellow"}
        assert row["checked_at"] == CHECKED_AT
        assert row["disclaimer"] == load_directory()["disclaimer"]
        assert row["zone"] == ("green" if row["verified"] and row["source_is_official"] else "yellow")
        if row["zone"] == "green":
            assert row["verified"] is True
            assert row["source_is_official"] is True
            assert is_official_url(row["source_url"])
            assert row["enrolment_url_verified"] is True
    for row in alliances.values():
        assert row["zone"] in {"green", "yellow"}
        assert row["checked_at"] == CHECKED_AT
        if row["zone"] == "green":
            assert is_official_url(row["promo_url"])
            assert row["promo"] not in {None, "", "unknown"}

    pegasus = programs["pegasus"]
    aeroflot = programs["aeroflot"]
    assert pegasus["can_join_verified"] is True
    assert pegasus["enrolment_url_verified"] is False
    assert pegasus["verified"] is False
    assert pegasus["zone"] == "yellow"
    assert aeroflot["can_join_verified"] is True
    assert aeroflot["zone"] == "yellow"
    assert programs["emirates"]["zone"] == "green"
    assert programs["flydubai"]["program_name"].startswith("Emirates Skywards")
    assert alliances["skyteam"]["zone"] == "yellow"
    assert alliances["skyteam"]["promo"] == "unknown"
    assert alliances["none"]["zone"] == "yellow"
    assert alliances["none"]["our_members"] == [
        "Pegasus",
        "AJet",
        "Emirates",
        "flydubai",
        "Etihad",
        "Air Arabia",
        "China Southern",
        "Hainan",
        "AirAsia",
    ]
    assert "вторич" in alliances["oneworld"]["status_match"]
    assert alliances["oneworld"]["zone"] == "green"


def test_every_program_points_at_its_alliance_member_list():
    alliances = {row["slug"]: row for row in build_alliance_rows()}
    programs = {row["slug"]: row for row in build_program_rows()}
    assert set(programs) == set(PROGRAM_ALLIANCES)
    for slug, alliance_slug in PROGRAM_ALLIANCES.items():
        row = programs[slug]
        assert row["alliance_slug"] == alliance_slug
        members = " ".join(alliances[alliance_slug]["our_members"])
        assert MEMBER_HINTS[slug] in members
    assert programs["ajet"]["alliance_label"] == "none (дочка Turkish)"
    assert programs["aeroflot"]["alliance_label"].startswith("SkyTeam")
    assert programs["china-southern"]["alliance_slug"] == "none"


def test_directory_has_no_personal_data_or_card_numbers():
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    assert_no_personal_data(payload)
    blob = json.dumps(payload, ensure_ascii=False).lower()
    for key in FORBIDDEN_KEYS:
        assert f'"{key}"' not in blob
    assert "@" not in blob
    assert re.search(r"\d{13,}", blob) is None
    for row in build_program_rows() + build_alliance_rows():
        legacy = json.dumps(row["legacy"], ensure_ascii=False).lower()
        for key in FORBIDDEN_KEYS:
            assert f'"{key}"' not in legacy


def test_migration_sql_is_additive_and_matches_the_seed():
    sql = MIGRATION.read_text(encoding="utf-8")
    mirror = MIRROR.read_text(encoding="utf-8")
    assert mirror.startswith(
        "-- Same migration as supabase/migrations/20261127220000_loyalty_programs.sql."
    )
    assert sql in mirror
    seed = render_seed_sql()
    assert seed in sql
    assert "ON CONFLICT (slug) DO UPDATE" in sql
    assert "CREATE INDEX IF NOT EXISTS idx_loyalty_programs_alliance_slug" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "TO anon, authenticated" in sql
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.loyalty_alliances, public.loyalty_programs TO service_role;" in sql
    assert "legacy" not in _anon_columns(sql, "loyalty_alliances")
    assert "legacy" not in _anon_columns(sql, "loyalty_programs")
    assert _anon_columns(sql, "loyalty_alliances") == PUBLIC_ALLIANCE_COLUMNS
    assert _anon_columns(sql, "loyalty_programs") == PUBLIC_PROGRAM_COLUMNS
    for view, table in (
        ("loyalty_alliances_public", "loyalty_alliances"),
        ("loyalty_programs_public", "loyalty_programs"),
    ):
        view_sql = _view_sql(sql, view)
        assert "security_invoker = true" in view_sql
        selected = view_sql.split("SELECT", 1)[1].split("FROM", 1)[0]
        assert "legacy" not in selected
        assert table in view_sql
    for line in sql.splitlines():
        if "TO anon" in line or "TO authenticated" in line:
            assert "INSERT" not in line
            assert "UPDATE" not in line
            assert "DELETE" not in line
    upper = sql.upper()
    assert "DROP TABLE" not in upper
    assert "DELETE FROM" not in upper
    assert "TRUNCATE" not in upper
    for name in (
        "card_number",
        "membership_number",
        "member_number",
        "user_id",
        "telegram_id",
        "passport",
    ):
        assert name not in sql.lower()
    assert "20261127064000_guide_facts" not in sql
    for slug in (*GREEN_PROGRAMS, *GREEN_ALLIANCES, "pegasus", "aeroflot", "none"):
        assert f"'{slug}'" in sql
