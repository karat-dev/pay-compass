"""Migration planning must not replay the baseline schema."""

from database.miniapp_migrate import (
    BASELINE_VERSION,
    connection_candidates,
    migration_plan,
    parse_dry_run,
    pending_local_versions,
    push_allowed,
    redact_text,
    session_pooler_url,
)


def test_existing_baseline_is_recorded_not_rerun():
    plan = migration_plan(
        applied=[],
        public_tables=["countries", "users", "events"],
    )
    assert plan["repair"] == [BASELINE_VERSION]
    assert plan["pending"] == ["20261014000000", "20261016000000", "20261018160000"]
    assert BASELINE_VERSION not in plan["pending"]


def test_recorded_baseline_and_miniapp_stay_idle():
    plan = migration_plan(
        applied=["20260913000000", "20261014000000", "20261016000000", "20261018160000"],
        public_tables=["users", "miniapp_profiles"],
    )
    assert plan == {"repair": [], "pending": []}


def test_missing_baseline_is_not_executed():
    plan = migration_plan(applied=[], public_tables=[])
    assert plan["repair"] == []
    assert plan["pending"] == ["20261014000000", "20261016000000", "20261018160000"]
    local = pending_local_versions(
        ["20260913000000", "20261014000000", "20261016000000"],
        applied=[],
        repair=[],
    )
    assert not push_allowed(local)
    assert push_allowed(["20261014000000", "20261016000000", "20261018160000"])


def test_dry_run_parser_and_redaction():
    text = "DRY RUN: migrations will *not* be pushed to the database.\n• 20261014000000_miniapp.sql\n"
    assert parse_dry_run(text) == ["20261014000000"]
    assert parse_dry_run("Remote database is up to date.\n") == []
    secret = "postgresql://postgres.example:s3cret@aws-0-eu-central-1.pooler.supabase.com:5432/postgres"
    cleaned = redact_text("failed " + secret + " password=s3cret", secret)
    assert secret not in cleaned
    assert "s3cret" not in cleaned
    assert "pooler.supabase.com" not in cleaned
    assert "[redacted]" in cleaned

    direct = "postgresql://postgres:p%2Fa!ss@db.abcproject.supabase.co:5432/postgres"
    pooled = session_pooler_url(direct, "eu-central-1")
    assert pooled is not None
    assert "db.abcproject.supabase.co" not in pooled
    assert "postgres.abcproject:p%2Fa!ss@" in pooled
    assert "@aws-0-eu-central-1.pooler.supabase.com:5432/postgres?sslmode=require" in pooled
    assert connection_candidates(direct)[0] == pooled
    assert connection_candidates(pooled) == [pooled]
