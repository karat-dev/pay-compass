"""Decide which Supabase migrations to apply.

The baseline monorepo schema is not executed again when its tables are already
present. Mini App files stay idempotent and are the only SQL this helper marks
as pending.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Sequence, Set

BASELINE_VERSION = "20260913000000"
MINIAPP_VERSIONS = ("20261014000000", "20261016000000")
BASELINE_TABLES = frozenset({"users", "countries"})

_URL_RE = re.compile(r"postgres(?:ql)?://\S+", re.IGNORECASE)
_PASSWORD_RE = re.compile(r"(password|pwd)\s*=\s*\S+", re.IGNORECASE)
_VERSION_FILE_RE = re.compile(r"\b(20\d{12})(?:_[A-Za-z0-9_]+)?\.sql\b")
_VERSION_BULLET_RE = re.compile(r"(?m)^\s*[•*\-]\s*(20\d{12})\b")


def migration_plan(applied: Iterable[str], public_tables: Iterable[str]) -> Dict[str, List[str]]:
    """Return versions to record without running, and Mini App versions still pending."""
    recorded = {str(version) for version in applied}
    tables = {str(name) for name in public_tables}
    repair: List[str] = []
    if BASELINE_VERSION not in recorded and BASELINE_TABLES & tables:
        repair.append(BASELINE_VERSION)
        recorded.add(BASELINE_VERSION)
    pending = [version for version in MINIAPP_VERSIONS if version not in recorded]
    return {"repair": repair, "pending": pending}


def push_allowed(pending_local: Sequence[str]) -> bool:
    """True only when every unrecorded local migration is a Mini App file."""
    versions = [str(version) for version in pending_local]
    return bool(versions) and set(versions) <= set(MINIAPP_VERSIONS)


def parse_dry_run(text: str) -> List[str]:
    """Versions a `db push --dry-run` would apply. Empty when the remote is current."""
    if "Remote database is up to date." in text or "Schema migrations are up to date." in text:
        return []
    versions = _VERSION_FILE_RE.findall(text)
    if not versions:
        versions = _VERSION_BULLET_RE.findall(text)
    return versions


def redact_text(text: str, secret: str = "") -> str:
    """Remove connection strings and the raw secret from command output."""
    cleaned = text or ""
    if secret:
        cleaned = cleaned.replace(secret, "[redacted]")
    cleaned = _URL_RE.sub("[redacted-url]", cleaned)
    cleaned = _PASSWORD_RE.sub("password=[redacted]", cleaned)
    return cleaned


def pending_local_versions(local_versions: Sequence[str], applied: Iterable[str], repair: Iterable[str]) -> List[str]:
    recorded: Set[str] = {str(version) for version in applied} | {str(version) for version in repair}
    return [str(version) for version in local_versions if str(version) not in recorded]
