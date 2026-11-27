#!/usr/bin/env python3
"""Build the idempotent loyalty-directory seed and splice it into the migration.

This script does not open a database connection and does not push migrations.
Production applies supabase/migrations only when the migration is merged to main.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.loyalty_programs_seed import (  # noqa: E402
    build_alliance_rows,
    build_program_rows,
    count_summary,
    render_seed_sql,
)

SUPABASE_MIGRATION = ROOT / "supabase" / "migrations" / "20261127220000_loyalty_programs.sql"
MIRROR_MIGRATION = ROOT / "database" / "migrations" / "010_loyalty_programs.sql"
MIRROR_HEADER = (
    "-- Same migration as supabase/migrations/20261127220000_loyalty_programs.sql.\n"
    "-- Prefer the supabase/migrations copy: GitHub Actions applies that folder.\n\n"
)
BEGIN = "-- LOYALTY_PROGRAMS_SEED_BEGIN"
END = "-- LOYALTY_PROGRAMS_SEED_END"


def splice_seed(sql_text: str, seed: str) -> str:
    start = sql_text.index(BEGIN)
    end = sql_text.index(END)
    if end < start:
        raise ValueError("seed markers are out of order")
    end = end + len(END)
    if end < len(sql_text) and sql_text[end] == "\n":
        end += 1
    return sql_text[:start] + seed + sql_text[end:]


def write_migrations(seed: str) -> None:
    current = SUPABASE_MIGRATION.read_text(encoding="utf-8")
    updated = splice_seed(current, seed)
    SUPABASE_MIGRATION.write_text(updated, encoding="utf-8")
    MIRROR_MIGRATION.write_text(MIRROR_HEADER + updated, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="splice the seed into the migration files")
    parser.add_argument("--sql", action="store_true", help="print the seed SQL")
    args = parser.parse_args()
    alliances = build_alliance_rows()
    programs = build_program_rows()
    seed = render_seed_sql(alliances, programs)
    if args.write:
        write_migrations(seed)
    if args.sql:
        sys.stdout.write(seed)
    if not args.write and not args.sql:
        json.dump(count_summary(alliances, programs), sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
