"""anon and authenticated cannot read owner_check or legacy; service_role can."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
TRANSPORT_MIGRATION = "20261127210000_transport_facts.sql"

STORAGE_STUB = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        CREATE ROLE anon NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        CREATE ROLE authenticated NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        CREATE ROLE service_role NOLOGIN BYPASSRLS;
    END IF;
END $$;
CREATE SCHEMA storage;
CREATE TABLE storage.buckets (
    id text PRIMARY KEY,
    name text,
    public boolean,
    allowed_mime_types text[]
);
CREATE TABLE storage.objects (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    bucket_id text
);
ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;
"""

OWNER_NOTE = "не ориентироваться на Uber в Китае"
UBER_CHINA = "ride:Uber|CN|Beijing/Shanghai"
GRAB_KEY = "bkk_dmk_grab_justgrab"


def _psql_available() -> bool:
    if shutil.which("psql") is None or shutil.which("sudo") is None:
        return False
    probe = subprocess.run(
        ["sudo", "-u", "postgres", "psql", "-d", "postgres", "-At", "-c", "SELECT 1"],
        capture_output=True,
        text=True,
    )
    return probe.returncode == 0


pytestmark = pytest.mark.skipif(not _psql_available(), reason="local postgres is not available")


def _psql(database: str, sql: str, *, expect_error: bool = False) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["sudo", "-u", "postgres", "psql", "-d", database, "-v", "ON_ERROR_STOP=1", "-At", "-c", sql],
        capture_output=True,
        text=True,
    )
    if result.stdout.startswith("SET\n"):
        result.stdout = result.stdout[4:]
    if expect_error:
        assert result.returncode != 0, result.stdout
        return result
    assert result.returncode == 0, result.stderr
    return result


def _psql_file(database: str, path: Path) -> None:
    result = subprocess.run(
        ["sudo", "-u", "postgres", "psql", "-d", database, "-v", "ON_ERROR_STOP=1", "-f", str(path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


@pytest.fixture(scope="module")
def privileges_db():
    name = "transport_facts_privileges"
    subprocess.run(
        ["sudo", "-u", "postgres", "psql", "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", f"DROP DATABASE IF EXISTS {name}"],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["sudo", "-u", "postgres", "psql", "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", f"CREATE DATABASE {name}"],
        check=True,
        capture_output=True,
        text=True,
    )
    _psql(name, STORAGE_STUB)
    for path in sorted(MIGRATIONS.glob("*.sql")):
        _psql_file(name, path)
    # Grants, views, and the upsert must survive a second apply.
    _psql_file(name, MIGRATIONS / TRANSPORT_MIGRATION)
    yield name
    subprocess.run(
        ["sudo", "-u", "postgres", "psql", "-d", "postgres", "-c", f"DROP DATABASE IF EXISTS {name}"],
        check=False,
        capture_output=True,
        text=True,
    )


def _column_privilege(database: str, role: str, table: str, column: str) -> bool:
    quoted_role = role.replace("'", "''")
    quoted_table = table.replace("'", "''")
    quoted_column = column.replace("'", "''")
    output = _psql(
        database,
        "SELECT has_column_privilege("
        f"'{quoted_role}', 'public.{quoted_table}', '{quoted_column}', 'SELECT')",
    ).stdout.strip()
    return output == "t"


def _view_columns(database: str, view: str) -> set:
    output = _psql(
        database,
        "SELECT column_name FROM information_schema.columns "
        f"WHERE table_schema = 'public' AND table_name = '{view}';",
    ).stdout
    return {line.strip() for line in output.splitlines() if line.strip()}


def test_seed_counts_stay_stable_after_second_apply(privileges_db):
    counts = _psql(
        privileges_db,
        """
        SELECT 'airport_facts|' || count(*)::text FROM public.airport_facts
        UNION ALL SELECT 'airport_green|' || count(*)::text FROM public.airport_facts WHERE zone = 'green'
        UNION ALL SELECT 'airport_yellow|' || count(*)::text FROM public.airport_facts WHERE zone = 'yellow'
        UNION ALL SELECT 'ride_services|' || count(*)::text FROM public.ride_services
        UNION ALL SELECT 'ride_green|' || count(*)::text FROM public.ride_services WHERE zone = 'green'
        UNION ALL SELECT 'ride_yellow|' || count(*)::text FROM public.ride_services WHERE zone = 'yellow'
        UNION ALL SELECT 'taxi|' || count(*)::text FROM public.taxi_tariff_rules
        UNION ALL SELECT 'taxi_yellow|' || count(*)::text FROM public.taxi_tariff_rules WHERE zone = 'yellow'
        UNION ALL SELECT 'routes|' || count(*)::text FROM public.transport_routes
        UNION ALL SELECT 'measurements|' || count(*)::text FROM public.transport_measurements
        UNION ALL SELECT 'rules|' || count(*)::text FROM public.transport_rules
        UNION ALL SELECT 'airport_keys|' || count(DISTINCT source_key)::text FROM public.airport_facts
        UNION ALL SELECT 'ride_keys|' || count(DISTINCT source_key)::text FROM public.ride_services;
        """,
    ).stdout.splitlines()
    assert sorted(line.strip() for line in counts) == sorted(
        [
            "airport_facts|20",
            "airport_green|14",
            "airport_yellow|6",
            "ride_services|26",
            "ride_green|14",
            "ride_yellow|12",
            "taxi|1",
            "taxi_yellow|1",
            "routes|3",
            "measurements|94",
            "rules|1",
            "airport_keys|20",
            "ride_keys|26",
        ]
    )


def test_internal_columns_are_hidden_and_public_reads_work(privileges_db):
    for role in ("anon", "authenticated"):
        assert _column_privilege(privileges_db, role, "ride_services", "owner_check") is False
        assert _column_privilege(privileges_db, role, "ride_services", "legacy") is False
        assert _column_privilege(privileges_db, role, "ride_services", "zone") is True
        assert _column_privilege(privileges_db, role, "airport_facts", "legacy") is False
        assert _column_privilege(privileges_db, role, "airport_facts", "fact") is True
        assert _column_privilege(privileges_db, role, "transport_measurements", "legacy") is False
        assert _column_privilege(privileges_db, role, "transport_measurements", "source_url") is True

        denied = _psql(
            privileges_db,
            f"SET ROLE {role}; SELECT owner_check FROM public.ride_services LIMIT 1;",
            expect_error=True,
        )
        assert "permission denied" in denied.stderr
        assert OWNER_NOTE not in denied.stdout
        assert OWNER_NOTE not in denied.stderr

        star = _psql(
            privileges_db,
            f"SET ROLE {role}; SELECT * FROM public.ride_services LIMIT 1;",
            expect_error=True,
        )
        assert "permission denied" in star.stderr
        assert OWNER_NOTE not in star.stdout
        assert "screenshot" not in star.stdout.lower()

        public_star = _psql(
            privileges_db,
            f"SET ROLE {role}; SELECT source_key || '|' || zone FROM public.ride_services_public "
            f"WHERE source_key = '{UBER_CHINA}';",
        ).stdout.strip()
        assert public_star == f"{UBER_CHINA}|yellow"
        ride_columns = _view_columns(privileges_db, "ride_services_public")
        assert "owner_check" not in ride_columns
        assert "legacy" not in ride_columns
        airport_columns = _view_columns(privileges_db, "airport_facts_public")
        assert "legacy" not in airport_columns
        measurement_columns = _view_columns(privileges_db, "transport_measurements_public")
        assert "legacy" not in measurement_columns

        leaked = _psql(
            privileges_db,
            f"""
            SET ROLE {role};
            SELECT count(*) FROM (
                SELECT source_url FROM public.airport_facts_public
                UNION ALL SELECT source_url FROM public.ride_services_public
                UNION ALL SELECT source_url FROM public.transport_measurements_public
            ) sources
            WHERE source_url ILIKE '%t.me/%'
               OR source_url ILIKE '%telegram.me/%'
               OR source_url ILIKE '%telegram.org/%'
               OR source_url ILIKE '%forum.awd.ru%'
               OR source_url ILIKE '%/forum%';
            """,
        ).stdout.strip()
        assert leaked == "0"

        grab = _psql(
            privileges_db,
            f"SET ROLE {role}; SELECT coalesce(source_url, '') || '|' || details::text "
            f"FROM public.transport_measurements_public WHERE source_key = '{GRAB_KEY}';",
        ).stdout.lower()
        assert "screenshot" not in grab
        assert grab.startswith("|")

        tariff = _psql(
            privileges_db,
            f"SET ROLE {role}; SELECT zone || '|' || currency FROM public.taxi_tariff_rules;",
        ).stdout.strip()
        assert tariff == "yellow|CNY"

        denied_write = _psql(
            privileges_db,
            f"""
            SET ROLE {role};
            INSERT INTO public.taxi_tariff_rules (
                source_key, country_iso2, service, zone_label, captured_at,
                source_kind, currency, tariffs, zone
            ) VALUES (
                'tariff:probe', 'CN', 'DiDi', 'probe', now(),
                'user_screenshot', 'CNY', '{{}}'::jsonb, 'yellow'
            );
            """,
            expect_error=True,
        )
        assert "permission denied" in denied_write.stderr


def test_service_role_reads_internal_notes(privileges_db):
    assert _column_privilege(privileges_db, "service_role", "ride_services", "owner_check") is True
    assert _column_privilege(privileges_db, "service_role", "ride_services", "legacy") is True
    assert _column_privilege(privileges_db, "service_role", "airport_facts", "legacy") is True
    assert _column_privilege(privileges_db, "service_role", "transport_measurements", "legacy") is True
    note = _psql(
        privileges_db,
        "SET ROLE service_role; "
        f"SELECT owner_check FROM public.ride_services WHERE source_key = '{UBER_CHINA}';",
    ).stdout.strip()
    assert note == OWNER_NOTE
    legacy_note = _psql(
        privileges_db,
        "SET ROLE service_role; "
        f"SELECT legacy->>'owner_check' FROM public.ride_services WHERE source_key = '{UBER_CHINA}';",
    ).stdout.strip()
    assert legacy_note == OWNER_NOTE
    screenshot = _psql(
        privileges_db,
        "SET ROLE service_role; "
        f"SELECT legacy->>'source' FROM public.transport_measurements WHERE source_key = '{GRAB_KEY}';",
    ).stdout
    assert "screenshot" in screenshot.lower()
