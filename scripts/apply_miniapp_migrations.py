#!/usr/bin/env python3
"""Check Supabase connectivity and apply the Mini App migrations.

Prints table names, migration versions, and redacted errors. The connection
string is never written to stdout or stderr.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.miniapp_migrate import (  # noqa: E402
    BASELINE_VERSION,
    MINIAPP_VERSIONS,
    connection_candidates,
    migration_plan,
    parse_dry_run,
    pending_local_versions,
    push_allowed,
    redact_text,
)

MIGRATIONS = ROOT / "supabase" / "migrations"
FILES = {
    "20261014000000": MIGRATIONS / "20261014000000_miniapp.sql",
    "20261016000000": MIGRATIONS / "20261016000000_drop_username.sql",
}


def emit(line: str) -> None:
    print(redact_text(line, os.environ.get("SUPABASE_DB_URL") or ""), flush=True)


def run(cmd: list, *, url: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PGCONNECT_TIMEOUT"] = "20"
    completed = subprocess.run(cmd, capture_output=True, text=True, env=env)
    completed.stdout = redact_text(completed.stdout or "", url)
    completed.stderr = redact_text(completed.stderr or "", url)
    return completed


def psql(url: str, sql: str) -> subprocess.CompletedProcess:
    return run(
        ["psql", url, "-X", "-q", "-v", "ON_ERROR_STOP=1", "-At", "-c", sql],
        url=url,
    )


def fail(message: str, code: int = 1) -> None:
    emit("result=failed")
    emit("error=" + " ".join(message.split()))
    raise SystemExit(code)


def list_tables(url: str) -> list:
    result = psql(
        url,
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
        "ORDER BY table_name",
    )
    if result.returncode != 0:
        fail(result.stderr.strip() or result.stdout.strip() or "table listing failed")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def list_history(url: str) -> list:
    exists = psql(url, "SELECT to_regclass('supabase_migrations.schema_migrations')")
    if exists.returncode != 0:
        fail(exists.stderr.strip() or "migration history lookup failed")
    if not (exists.stdout or "").strip():
        return []
    result = psql(
        url,
        "SELECT version FROM supabase_migrations.schema_migrations ORDER BY version",
    )
    if result.returncode != 0:
        fail(result.stderr.strip() or "migration history query failed")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def local_versions() -> list:
    found = []
    for path in sorted(MIGRATIONS.glob("*.sql")):
        version = path.name.split("_", 1)[0]
        if version.isdigit():
            found.append(version)
    return found


def supabase(*args: str, url: str) -> subprocess.CompletedProcess:
    return run(
        ["supabase", *args, "--db-url", url, "--linked=false", "--yes"],
        url=url,
    )


def apply_with_psql(url: str, versions: list) -> None:
    for version in versions:
        path = FILES[version]
        result = run(
            ["psql", url, "-X", "-q", "-v", "ON_ERROR_STOP=1", "-f", str(path)],
            url=url,
        )
        if result.returncode != 0:
            emit("error=" + " ".join((result.stderr or result.stdout or "psql failed").split()))
            emit("result=failed")
            raise SystemExit(result.returncode or 1)
        repaired = supabase(
            "migration", "repair", version, "--status", "applied",
            url=url,
        )
        if repaired.returncode != 0:
            emit("error=" + " ".join((repaired.stderr or repaired.stdout or "repair failed").split()))
            emit("result=failed")
            raise SystemExit(repaired.returncode or 1)
        emit("applied=" + version)


def main() -> None:
    secret = (os.environ.get("SUPABASE_DB_URL") or "").strip()
    if not secret:
        emit("connectivity=false")
        emit("error=SUPABASE_DB_URL is empty")
        raise SystemExit(1)
    region = (os.environ.get("SUPABASE_POOLER_REGION") or "eu-central-1").strip()

    url = ""
    errors = []
    for candidate in connection_candidates(secret, region):
        userinfo = candidate.split("://", 1)[-1].split("@", 1)[0]
        user = userinfo.split(":", 1)[0]
        label = "tenant" if "." in user else "plain"
        probe = psql(candidate, "SELECT 1")
        if probe.returncode == 0 and (probe.stdout or "").strip() == "1":
            url = candidate
            break
        detail = (probe.stderr or probe.stdout or "SELECT 1 failed").strip()
        errors.append(f"user={label} " + " ".join(detail.split()))
    if not url:
        emit("connectivity=false")
        emit("error=" + " | ".join(errors))
        raise SystemExit(1)
    via = "session_pooler" if "pooler.supabase.com" in url else "direct"
    emit("connectivity=true")
    emit("connect_via=" + via)

    tables = list_tables(url)
    for name in tables:
        emit("table=" + name)
    history = list_history(url)
    for version in history:
        emit("history=" + version)

    plan = migration_plan(history, tables)
    for version in plan["repair"]:
        repaired = supabase(
            "migration", "repair", version, "--status", "applied",
            url=url,
        )
        if repaired.returncode != 0:
            emit("error=" + " ".join((repaired.stderr or repaired.stdout or "baseline repair failed").split()))
            emit("result=failed")
            raise SystemExit(repaired.returncode or 1)
        emit("repaired=" + version)

    recorded = list_history(url)
    full_pending = pending_local_versions(local_versions(), recorded, [])
    if BASELINE_VERSION in full_pending:
        emit("baseline=skipped")
    pending = [version for version in full_pending if version in FILES]

    if not full_pending:
        emit("push=up_to_date")
        emit("applied=none")
    elif push_allowed(full_pending):
        dry = supabase("db", "push", "--dry-run", "--include-all", url=url)
        dry_text = (dry.stdout or "") + "\n" + (dry.stderr or "")
        dry_versions = parse_dry_run(dry_text)
        up_to_date = "up to date" in dry_text
        emit("dry_run=" + (",".join(dry_versions) if dry_versions else ("up_to_date" if up_to_date else "unparsed")))
        unsafe = [version for version in dry_versions if version not in MINIAPP_VERSIONS]
        if dry.returncode == 0 and not unsafe and dry_versions and set(dry_versions) <= set(MINIAPP_VERSIONS):
            pushed = supabase("db", "push", "--include-all", url=url)
            if pushed.returncode != 0:
                emit("error=" + " ".join(((pushed.stderr or "") + " " + (pushed.stdout or "")).split()))
                emit("result=failed")
                raise SystemExit(pushed.returncode or 1)
            emit("push=cli")
            for version in dry_versions:
                emit("applied=" + version)
        elif dry.returncode == 0 and up_to_date and not dry_versions:
            emit("push=up_to_date")
            emit("applied=none")
        else:
            if unsafe:
                emit("push=skipped_unsafe")
            else:
                emit("push=sql")
                if dry.returncode != 0:
                    emit("error=" + " ".join(dry_text.split()))
            apply_with_psql(url, pending)
    else:
        skipped = [version for version in full_pending if version not in FILES]
        if skipped:
            emit("skipped=" + ",".join(skipped))
        if pending:
            emit("push=sql")
            apply_with_psql(url, pending)
        else:
            emit("push=up_to_date")
            emit("applied=none")

    emit("tables_after_start")
    for name in list_tables(url):
        emit("table_after=" + name)
    for version in list_history(url):
        emit("history_after=" + version)
    emit("result=ok")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        emit("result=failed")
        emit("error=" + " ".join(redact_text(str(exc), os.environ.get("SUPABASE_DB_URL") or "").split()))
        raise SystemExit(1)
