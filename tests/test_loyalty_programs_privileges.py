"""anon and authenticated cannot read loyalty legacy; service_role can."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
LOYALTY_MIGRATION = MIGRATIONS / "20261127220000_loyalty_programs.sql"

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
    if result.stdout:
        lines = [line for line in result.stdout.splitlines() if line != "SET"]
        result.stdout = "\n".join(lines) + ("\n" if lines else "")
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
    name = "loyalty_programs_privileges"
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
    _psql_file(name, LOYALTY_MIGRATION)
    yield name
    subprocess.run(
        ["sudo", "-u", "postgres", "psql", "-d", "postgres", "-c", f"DROP DATABASE IF EXISTS {name}"],
        check=False,
        capture_output=True,
        text=True,
    )


def _column_privilege(database: str, role: str, table: str, column: str) -> bool:
    quoted_role = role.replace("'", "''")
    quoted_column = column.replace("'", "''")
    output = _psql(
        database,
        "SELECT has_column_privilege("
        f"'{quoted_role}', 'public.{table}', '{quoted_column}', 'SELECT')",
    ).stdout.strip()
    return output == "t"


def _table_privilege(database: str, role: str, table: str, privilege: str) -> bool:
    output = _psql(
        database,
        "SELECT has_table_privilege("
        f"'{role}', 'public.{table}', '{privilege}')",
    ).stdout.strip()
    return output == "t"


def test_seed_counts_and_zones_survive_a_second_apply(privileges_db):
    counts = _psql(
        privileges_db,
        "SELECT (SELECT count(*) FROM public.loyalty_alliances) || ' ' || "
        "(SELECT count(*) FROM public.loyalty_programs);",
    ).stdout.strip()
    assert counts == "4 16"
    zones = _psql(
        privileges_db,
        "SELECT zone || ':' || count(*) FROM public.loyalty_programs "
        "GROUP BY zone ORDER BY zone;",
    ).stdout
    assert "green:3" in zones
    assert "yellow:13" in zones
    alliance_zones = _psql(
        privileges_db,
        "SELECT slug || ':' || zone FROM public.loyalty_alliances ORDER BY slug;",
    ).stdout
    assert "none:yellow" in alliance_zones
    assert "oneworld:green" in alliance_zones
    assert "skyteam:yellow" in alliance_zones
    assert "star-alliance:green" in alliance_zones

    _psql(
        privileges_db,
        "UPDATE public.loyalty_programs SET zone = 'yellow', verified = false "
        "WHERE slug = 'emirates';",
    )
    _psql_file(privileges_db, LOYALTY_MIGRATION)
    restored = _psql(
        privileges_db,
        "SELECT zone || ':' || verified FROM public.loyalty_programs WHERE slug = 'emirates';",
    ).stdout.strip()
    assert restored == "green:true"
    assert _psql(
        privileges_db,
        "SELECT count(*) FROM public.loyalty_programs;",
    ).stdout.strip() == "16"


def test_legacy_is_hidden_from_anon_and_authenticated(privileges_db):
    for role in ("anon", "authenticated"):
        for table in ("loyalty_alliances", "loyalty_programs"):
            assert _column_privilege(privileges_db, role, table, "legacy") is False
            assert _table_privilege(privileges_db, role, table, "INSERT") is False
            assert _table_privilege(privileges_db, role, table, "UPDATE") is False
            assert _table_privilege(privileges_db, role, table, "DELETE") is False
        assert _column_privilege(privileges_db, role, "loyalty_programs", "airline") is True
        assert _column_privilege(privileges_db, role, "loyalty_programs", "zone") is True
        assert _column_privilege(privileges_db, role, "loyalty_alliances", "name") is True

        airline = _psql(
            privileges_db,
            f"SET ROLE {role}; SELECT airline FROM public.loyalty_programs WHERE slug = 'emirates';",
        ).stdout.strip()
        assert airline == "Emirates"

        denied = _psql(
            privileges_db,
            f"SET ROLE {role}; SELECT legacy FROM public.loyalty_programs LIMIT 1;",
            expect_error=True,
        )
        assert "permission denied" in denied.stderr
        assert "Miles&Smiles" not in denied.stdout
        assert "Miles&Smiles" not in denied.stderr

        star = _psql(
            privileges_db,
            f"SET ROLE {role}; SELECT * FROM public.loyalty_programs LIMIT 1;",
            expect_error=True,
        )
        assert "permission denied" in star.stderr
        assert "Miles&Smiles" not in star.stdout

        public_row = _psql(
            privileges_db,
            f"SET ROLE {role}; SELECT slug || ':' || zone FROM public.loyalty_programs_public "
            "WHERE slug = 'emirates';",
        ).stdout.strip()
        assert public_row == "emirates:green"
        columns = _psql(
            privileges_db,
            "SELECT string_agg(column_name, ',' ORDER BY ordinal_position) "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'loyalty_programs_public';",
        ).stdout
        assert "legacy" not in columns.split(",")
        alliance_columns = _psql(
            privileges_db,
            "SELECT string_agg(column_name, ',' ORDER BY ordinal_position) "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'loyalty_alliances_public';",
        ).stdout
        assert "legacy" not in alliance_columns.split(",")

        insert_denied = _psql(
            privileges_db,
            f"SET ROLE {role}; INSERT INTO public.loyalty_alliances (slug, name, zone, checked_at) "
            "VALUES ('extra', 'Extra', 'yellow', '2026-10-28');",
            expect_error=True,
        )
        assert "permission denied" in insert_denied.stderr


def test_service_role_reads_legacy_and_directory_has_no_personal_columns(privileges_db):
    assert _column_privilege(privileges_db, "service_role", "loyalty_programs", "legacy") is True
    assert _column_privilege(privileges_db, "service_role", "loyalty_alliances", "legacy") is True
    assert _table_privilege(privileges_db, "service_role", "loyalty_programs", "INSERT") is True
    assert _table_privilege(privileges_db, "service_role", "loyalty_programs", "UPDATE") is True
    assert _table_privilege(privileges_db, "service_role", "loyalty_programs", "DELETE") is True
    original = _psql(
        privileges_db,
        "SET ROLE service_role; "
        "SELECT legacy->>'program' FROM public.loyalty_programs WHERE slug = 'turkish-airlines';",
    ).stdout.strip()
    assert original == "Miles&Smiles"
    assert _psql(
        privileges_db,
        "SET ROLE service_role; "
        "SELECT legacy->>'alliance' FROM public.loyalty_programs WHERE slug = 'ajet';",
    ).stdout.strip() == "none (дочка Turkish)"
    columns = _psql(
        privileges_db,
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' "
        "AND table_name IN ('loyalty_alliances', 'loyalty_programs') "
        "ORDER BY column_name;",
    ).stdout.lower()
    for name in (
        "card_number",
        "membership_number",
        "member_number",
        "user_id",
        "telegram_id",
        "passport",
        "phone",
        "email",
    ):
        assert name not in columns.split()
    options = _psql(
        privileges_db,
        "SELECT array_to_string(reloptions, ',') FROM pg_class "
        "WHERE relname IN ('loyalty_programs_public', 'loyalty_alliances_public') "
        "ORDER BY relname;",
    ).stdout
    assert options.count("security_invoker=true") == 2
