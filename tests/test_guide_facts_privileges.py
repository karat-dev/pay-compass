"""anon and authenticated cannot read guide_facts.legacy; service_role can."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"

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
    name = "guide_facts_privileges"
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
    # Grants and the view must survive a second apply.
    _psql_file(name, MIGRATIONS / "20261127064000_guide_facts.sql")
    yield name
    subprocess.run(
        ["sudo", "-u", "postgres", "psql", "-d", "postgres", "-c", f"DROP DATABASE IF EXISTS {name}"],
        check=False,
        capture_output=True,
        text=True,
    )


def _column_privilege(database: str, role: str, column: str) -> bool:
    quoted_role = role.replace("'", "''")
    quoted_column = column.replace("'", "''")
    output = _psql(
        database,
        "SELECT has_column_privilege("
        f"'{quoted_role}', 'public.guide_facts', '{quoted_column}', 'SELECT')",
    ).stdout.strip()
    return output == "t"


def test_legacy_is_hidden_from_anon_and_authenticated(privileges_db):
    for role in ("anon", "authenticated"):
        assert _column_privilege(privileges_db, role, "legacy") is False
        assert _column_privilege(privileges_db, role, "fact") is True
        assert _column_privilege(privileges_db, role, "source_url") is True
        assert _column_privilege(privileges_db, role, "zone") is True

        fact = _psql(
            privileges_db,
            f"SET ROLE {role}; SELECT fact FROM public.guide_facts "
            "WHERE source_key = 'guide:china:1_checklist:facts[2]';",
        ).stdout
        assert "UnionPay" in fact
        assert "АТБ" not in fact
        assert "РСХБ" not in fact

        denied = _psql(
            privileges_db,
            f"SET ROLE {role}; SELECT legacy FROM public.guide_facts LIMIT 1;",
            expect_error=True,
        )
        assert "permission denied" in denied.stderr
        assert "original_text" not in denied.stdout
        assert "original_text" not in denied.stderr
        assert "t.me/" not in denied.stdout

        star = _psql(
            privileges_db,
            f"SET ROLE {role}; SELECT * FROM public.guide_facts LIMIT 1;",
            expect_error=True,
        )
        assert "permission denied" in star.stderr
        assert "original_text" not in star.stdout
        assert "original_text" not in star.stderr

        public_star = _psql(
            privileges_db,
            f"SET ROLE {role}; SELECT * FROM public.guide_facts_public LIMIT 1;",
        ).stdout
        assert "original_text" not in public_star
        assert "t.me/" not in public_star
        columns = _psql(
            privileges_db,
            "SELECT string_agg(column_name, ',' ORDER BY ordinal_position) "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'guide_facts_public';",
        ).stdout
        assert "legacy" not in columns.split(",")


def test_service_role_still_reads_legacy(privileges_db):
    assert _column_privilege(privileges_db, "service_role", "legacy") is True
    assert _column_privilege(privileges_db, "service_role", "fact") is True
    original = _psql(
        privileges_db,
        "SET ROLE service_role; "
        "SELECT legacy->>'original_text' FROM public.guide_facts "
        "WHERE source_key = 'guide:china:1_checklist:facts[2]';",
    ).stdout
    assert "АТБ" in original or "РСХБ" in original
