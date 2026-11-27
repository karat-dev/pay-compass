"""Transport-fact seed: zones, hidden notes, route_model rows, migration SQL."""

from __future__ import annotations

import json
import re
from pathlib import Path

from database.transport_facts_seed import (
    AIRPORT_PUBLIC_COLUMNS,
    MEASUREMENT_PUBLIC_COLUMNS,
    RIDE_CONFIRMED,
    RIDE_OWNER_CHECK,
    RIDE_PUBLIC_COLUMNS,
    RULES_SOURCE_KEY,
    build_airport_fact_rows,
    build_measurement_rows,
    build_ride_rows,
    build_route_rows,
    build_rule_rows,
    build_tariff_rows,
    count_summary,
    private_marker_in_url,
    render_seed_sql,
    ride_source_is_official,
    ride_zone,
    tariff_zone,
)

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20261127210000_transport_facts.sql"
MIRROR = ROOT / "database" / "migrations" / "009_transport_facts.sql"

def _grant_columns(sql: str, table: str) -> tuple:
    match = re.search(
        rf"GRANT SELECT \(([^;]*?)\) ON TABLE public\.{table} TO anon, authenticated;",
        sql,
        re.S,
    )
    assert match, f"column-level SELECT grant for {table} is missing"
    return tuple(part.strip() for part in match.group(1).split(",") if part.strip())


def _view_sql(sql: str, view: str, table: str) -> str:
    match = re.search(
        rf"CREATE VIEW public\.{view}\b.*?FROM public\.{table};",
        sql,
        re.S,
    )
    assert match, f"{view} view is missing"
    return match.group(0)


def _upsert(rows):
    merged = {}
    for row in rows:
        merged[row["source_key"]] = row
    return merged


def test_seed_counts_and_idempotent_keys():
    airports = build_airport_fact_rows()
    rides = build_ride_rows()
    tariffs = build_tariff_rows()
    routes = build_route_rows()
    measurements = build_measurement_rows()
    rules = build_rule_rows()
    again = (
        build_airport_fact_rows(),
        build_ride_rows(),
        build_tariff_rows(),
        build_route_rows(),
        build_measurement_rows(),
        build_rule_rows(),
    )
    first = (airports, rides, tariffs, routes, measurements, rules)
    for left, right in zip(first, again):
        assert [row["source_key"] for row in left] == [row["source_key"] for row in right]
        assert len(_upsert(list(left) + list(right))) == len(left)
    summary = count_summary(airports, rides, tariffs, routes, measurements, rules)
    assert summary == {
        "airport_facts": {
            "rows": 20,
            "by_zone": {"green": 14, "yellow": 6},
            "by_status": {"active": 20},
            "by_country": {
                "china": 3,
                "georgia": 2,
                "hong_kong": 4,
                "thailand": 3,
                "turkey": 4,
                "uae": 4,
            },
        },
        "ride_services": {
            "rows": 26,
            "by_zone": {"green": 14, "yellow": 12},
            "by_status": {RIDE_CONFIRMED: 14, RIDE_OWNER_CHECK: 12},
            "by_country": {
                "all": 3,
                "china": 4,
                "georgia": 3,
                "multi": 1,
                "russia": 5,
                "thailand": 4,
                "turkey": 3,
                "uae": 3,
            },
        },
        "taxi_tariff_rules": {"rows": 1, "by_zone": {"yellow": 1}},
        "transport_routes": 3,
        "transport_measurements": 94,
        "transport_rules": 1,
    }
    assert render_seed_sql() == render_seed_sql()


def test_zone_rule_for_airports_rides_and_tariffs():
    assert ride_zone(RIDE_CONFIRMED, True) == "green"
    assert ride_zone(RIDE_CONFIRMED, False) == "yellow"
    assert ride_zone(RIDE_OWNER_CHECK, True) == "yellow"
    assert ride_source_is_official("Uber", "https://www.uber.com/global/en/cities/")
    assert not ride_source_is_official("Uber", "https://example.com/blog/uber-istanbul")
    assert not ride_source_is_official("Uber", None)
    assert tariff_zone("user_screenshot") == "yellow"
    assert tariff_zone("official") == "green"

    for row in build_airport_fact_rows():
        confirmed_official = row["source_is_official"] and row["legacy"]["status"] == "confirmed"
        assert row["zone"] == ("green" if confirmed_official else "yellow")
        assert row["status"] == "active"
        assert row["zone"] in {"green", "yellow", "red"}
        assert not private_marker_in_url(row["source_url"])
    for row in build_ride_rows():
        official = ride_source_is_official(row["service"], row["source_url"])
        assert row["zone"] == ride_zone(row["status"], official)
        assert not private_marker_in_url(row["source_url"])
        if row["source_url"]:
            assert row["source_url"].startswith("http")
            assert " " not in row["source_url"]
    tariffs = build_tariff_rows()
    assert len(tariffs) == 1
    tariff = tariffs[0]
    assert tariff["zone"] == "yellow"
    assert tariff["source_kind"] == "user_screenshot"
    assert tariff["currency"] == "CNY"
    assert tariff["country_iso2"] == "CN"
    assert tariff["service"] == "DiDi"
    assert tariff["tariffs"]["Standard"]["min_fare"] == 35


def test_private_urls_and_owner_notes_stay_out_of_public_fields():
    hidden_airport = build_airport_fact_rows(
        [
            {
                "country": "china",
                "airport": "PEK",
                "topic": "forum",
                "text": "Служебная заметка",
                "status": "confirmed",
                "checked_at": "2026-10-27",
                "source": "https://t.me/chinaguide/1",
                "source_type": "telegram",
                "needs_owner_check": False,
                "decision_needed": None,
                "unknown_zone": None,
            }
        ]
    )[0]
    assert hidden_airport["source_url"] is None
    assert "t.me/" in hidden_airport["legacy"]["source"]
    assert hidden_airport["zone"] == "yellow"

    hidden_ride = build_ride_rows(
        [
            {
                "service": "Uber",
                "category": "ride_hailing",
                "country": "TR",
                "city": "Istanbul",
                "status": RIDE_CONFIRMED,
                "source_url": "https://forum.awd.ru/viewtopic.php?t=1",
                "availability": "есть",
                "owner_check": "внутреннее: не публиковать",
                "check_date": "2026-10-31",
            }
        ]
    )[0]
    assert hidden_ride["source_url"] is None
    assert hidden_ride["zone"] == "yellow"
    assert hidden_ride["owner_check"] == "внутреннее: не публиковать"
    assert "forum.awd.ru" in hidden_ride["legacy"]["source_url"]

    measurements = build_measurement_rows()
    hidden = [row for row in measurements if row["legacy"].get("source_user_facing") is False]
    assert len(hidden) == 15
    for row in hidden:
        assert row["source_url"] is None
        public_blob = json.dumps(
            {
                "template": row["template"],
                "statement": row["statement"],
                "details": row["details"],
                "source_url": row["source_url"],
            },
            ensure_ascii=False,
        ).lower()
        assert "screenshot" not in public_blob
        assert "t.me/" not in public_blob
        assert row["legacy"].get("source")
    shown = [row for row in measurements if row["source_url"]]
    assert len(shown) == 50
    for row in shown:
        assert not private_marker_in_url(row["source_url"])


def test_route_model_rows_follow_the_json():
    routes = build_route_rows()
    assert [row["source_key"] for row in routes] == [
        "mow_hkg_via_pek",
        "mow_china",
        "mow_thailand",
    ]
    assert {row["destination_slug"] for row in routes} == {"hong_kong", "china", "thailand"}
    assert all(row["lead_facts"] and row["sections"] for row in routes)
    measurements = build_measurement_rows()
    visa = next(row for row in measurements if row["source_key"] == "china_visa_free_days")
    assert visa["value_num"] == 30
    assert visa["source_url"].startswith("https://www.mfa.gov.cn/")
    gap = next(row for row in measurements if row["source_key"] == "pek_pkx_transfer_minutes")
    assert gap["gap"] is True
    assert gap["statement"].startswith("Сколько минут")
    assert gap["source_url"] is None
    rules = build_rule_rows()
    assert rules[0]["source_key"] == RULES_SOURCE_KEY
    assert rules[0]["evaluated_on"] == "2026-10-18"
    assert "airport_change_allowance" in rules[0]["formulas"]


def test_migration_sql_is_additive_and_matches_the_seed():
    sql = MIGRATION.read_text(encoding="utf-8")
    mirror = MIRROR.read_text(encoding="utf-8")
    assert mirror.startswith(
        "-- Same migration as supabase/migrations/20261127210000_transport_facts.sql."
    )
    assert sql in mirror
    seed = render_seed_sql()
    assert seed in sql
    assert sql.count("ON CONFLICT (source_key) DO UPDATE") >= 6
    for index in (
        "idx_airport_facts_country_airport ON public.airport_facts (country_slug, airport_code)",
        "idx_airport_facts_zone ON public.airport_facts (zone)",
        "idx_ride_services_country_service ON public.ride_services (country_iso2, service)",
        "idx_ride_services_zone ON public.ride_services (zone)",
        "idx_taxi_tariff_rules_country_service ON public.taxi_tariff_rules (country_iso2, service)",
        "idx_transport_routes_destination ON public.transport_routes (destination_slug)",
        "idx_transport_measurements_volatility ON public.transport_measurements (volatility)",
        "idx_transport_measurements_topic ON public.transport_measurements (transfer_topic, transfer_measure)",
    ):
        compact = " ".join(sql.split())
        assert f"CREATE INDEX IF NOT EXISTS {index}" in compact
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "TO anon, authenticated" in sql
    assert "security_invoker = true" in sql
    assert (
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE\n"
        "    public.airport_facts,\n"
        "    public.ride_services,\n"
        "    public.taxi_tariff_rules,\n"
        "    public.transport_routes,\n"
        "    public.transport_measurements,\n"
        "    public.transport_rules\n"
        "TO service_role;"
    ) in sql
    assert "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;" in sql
    assert _grant_columns(sql, "airport_facts") == AIRPORT_PUBLIC_COLUMNS
    assert _grant_columns(sql, "ride_services") == RIDE_PUBLIC_COLUMNS
    assert _grant_columns(sql, "transport_measurements") == MEASUREMENT_PUBLIC_COLUMNS
    for table, view in (
        ("airport_facts", "airport_facts_public"),
        ("ride_services", "ride_services_public"),
        ("transport_measurements", "transport_measurements_public"),
    ):
        view_sql = _view_sql(sql, view, table)
        assert "security_invoker = true" in view_sql
        select_list = view_sql.split("SELECT", 1)[1].split("FROM", 1)[0]
        columns = {part.strip().strip(",") for part in select_list.split(",") if part.strip()}
        assert "legacy" not in columns
        assert "owner_check" not in columns
    for line in sql.splitlines():
        if "TO anon" in line or "TO authenticated" in line:
            assert "INSERT" not in line
            assert "UPDATE" not in line
            assert "DELETE" not in line
    upper = sql.upper()
    assert "DROP TABLE" not in upper
    assert "DELETE FROM" not in upper
    assert "TRUNCATE" not in upper
    for line in sql.splitlines():
        low = line.lower()
        if any(token in low for token in ("drop table", "delete from", "truncate", "alter table")):
            for name in ("users", "reviews", "events", "user_states", "miniapp_"):
                assert name not in low
    assert "GUIDE_FACTS_SEED_BEGIN" not in sql
    assert "ALTER TABLE public.guide_facts" not in sql
    assert "ALTER TABLE public.countries" not in sql
