"""Idempotent rows for the loyalty alliance and program directory.

The source file is a reference only. It has no member numbers and no user
records. Card numbers stay in Telegram CloudStorage and are not columns here.

Zone rule (checked 2026-10-28):

- A program is ``verified`` only when an explicit verified flag is tied to an
  official URL: ``enrolment_url_verified`` plus an official enrolment URL, or
  ``russian_citizens.verified`` plus an official ``source`` URL.
- ``source_is_official`` is whether the public ``source_url`` host is the
  airline or alliance site. A yellow row can still cite an official URL.
- ``zone`` is ``green`` only when ``verified`` and ``source_is_official``.
  Every other program is ``yellow``. This directory has no ``red`` zone.
- An alliance is ``green`` only when ``promo_url`` is an official alliance
  page and ``promo`` is a concrete offer (not empty, unknown, or secondary).
  Otherwise the alliance is ``yellow``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "database" / "data" / "loyalty_programs.json"

CHECKED_AT = "2026-10-28"

# Hosts of the airlines and alliances in this directory. A URL on any other
# host is a secondary source and cannot make a row green.
OFFICIAL_HOSTS = (
    "turkishairlines.com",
    "ajet.com",
    "flypgs.com",
    "emirates.com",
    "flydubai.com",
    "qatarairways.com",
    "etihad.com",
    "airarabia.com",
    "airchina.com.cn",
    "airchina.com",
    "csair.com",
    "ceair.com",
    "hainanairlines.com",
    "aeroflot.ru",
    "thaiairways.com",
    "airasia.com",
    "cathaypacific.com",
    "staralliance.com",
    "skyteam.com",
    "oneworld.com",
)

# Same private markers as the guide-fact seed. These URLs are not public sources.
_PRIVATE_SOURCE_MARKERS = (
    "t.me/",
    "telegram.me/",
    "telegram.org/",
    "forum.awd.ru",
    "/forum",
)

# Keys that would mean a user card number or another personal record.
FORBIDDEN_KEYS = frozenset(
    {
        "account_number",
        "card_no",
        "card_number",
        "email",
        "ffp_number",
        "holder_name",
        "loyalty_number",
        "member_number",
        "membership_number",
        "pan",
        "passenger",
        "passport",
        "phone",
        "telegram_id",
        "user_id",
    }
)

_CARD_DIGITS = re.compile(r"\d{13,}")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

PUBLIC_ALLIANCE_COLUMNS = (
    "id",
    "slug",
    "name",
    "our_members",
    "promo",
    "promo_url",
    "status_match",
    "source_url",
    "zone",
    "checked_at",
    "created_at",
    "updated_at",
)

PUBLIC_PROGRAM_COLUMNS = (
    "id",
    "slug",
    "airline",
    "iata",
    "program_name",
    "alliance_slug",
    "alliance_label",
    "currency",
    "enrolment_url",
    "enrolment_url_verified",
    "mile_expiry",
    "mile_expiry_source",
    "key_partners",
    "can_join",
    "can_join_basis",
    "can_join_source",
    "can_join_verified",
    "status_match",
    "promos_url",
    "notes",
    "source_url",
    "source_is_official",
    "verified",
    "zone",
    "checked_at",
    "disclaimer",
    "created_at",
    "updated_at",
)

_ALLIANCE_SLUGS = {
    "Star Alliance": "star-alliance",
    "SkyTeam": "skyteam",
    "oneworld": "oneworld",
    "Без альянса": "none",
}

_PROGRAM_SLUGS = {
    "Turkish Airlines": "turkish-airlines",
    "AJet": "ajet",
    "Pegasus": "pegasus",
    "Emirates": "emirates",
    "flydubai": "flydubai",
    "Qatar Airways": "qatar-airways",
    "Etihad": "etihad",
    "Air Arabia": "air-arabia",
    "Air China": "air-china",
    "China Southern": "china-southern",
    "China Eastern": "china-eastern",
    "Hainan Airlines": "hainan-airlines",
    "Aeroflot": "aeroflot",
    "Thai Airways": "thai-airways",
    "AirAsia": "airasia",
    "Cathay Pacific": "cathay-pacific",
}

_ALLIANCE_COLUMNS = (
    "slug",
    "name",
    "our_members",
    "promo",
    "promo_url",
    "status_match",
    "source_url",
    "zone",
    "checked_at",
    "legacy",
)

_PROGRAM_COLUMNS = (
    "slug",
    "airline",
    "iata",
    "program_name",
    "alliance_slug",
    "alliance_label",
    "currency",
    "enrolment_url",
    "enrolment_url_verified",
    "mile_expiry",
    "mile_expiry_source",
    "key_partners",
    "can_join",
    "can_join_basis",
    "can_join_source",
    "can_join_verified",
    "status_match",
    "promos_url",
    "notes",
    "source_url",
    "source_is_official",
    "verified",
    "zone",
    "checked_at",
    "disclaimer",
    "legacy",
)


def load_directory(path: Path = DATA_PATH) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    assert_no_personal_data(payload)
    return payload


def assert_no_personal_data(payload: Any) -> None:
    """Reject keys or values that would store a person or a card number."""
    blob = json.dumps(payload, ensure_ascii=False)
    if _CARD_DIGITS.search(blob) or _EMAIL.search(blob):
        raise ValueError("loyalty directory contains a card number or email")
    for key in _keys(payload):
        if key.lower() in FORBIDDEN_KEYS:
            raise ValueError(f"loyalty directory contains personal key {key}")


def _keys(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _keys(item)


def _host(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


def is_official_url(url: Optional[str]) -> bool:
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return False
    host = _host(url)
    return any(host == base or host.endswith("." + base) for base in OFFICIAL_HOSTS)


def public_url(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text.startswith(("http://", "https://")):
        return None
    url = text.split()[0].rstrip(").,;")
    low = url.lower()
    if any(marker in low for marker in _PRIVATE_SOURCE_MARKERS):
        return None
    return url


def _blank(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _urls_in_text(value: Any) -> List[str]:
    if not isinstance(value, str):
        return []
    found = []
    for match in re.findall(r"https?://[^\s<>\"']+", value):
        url = public_url(match)
        if url:
            found.append(url)
    return found


def alliance_slug_for_program(label: str) -> str:
    text = label.strip()
    if text == "Star Alliance":
        return "star-alliance"
    if text == "oneworld":
        return "oneworld"
    if text.startswith("SkyTeam"):
        return "skyteam"
    if text == "none" or text.startswith("none "):
        return "none"
    raise ValueError(f"unknown alliance label: {label}")


def _alliance_zone(promo: Optional[str], promo_url: Optional[str]) -> str:
    if not is_official_url(promo_url):
        return "yellow"
    if promo is None:
        return "yellow"
    folded = promo.strip().lower()
    if folded in {"", "unknown"} or "вторич" in folded:
        return "yellow"
    return "green"


def _program_verification(program: Dict[str, Any]) -> Optional[str]:
    enrolment = public_url(program.get("enrolment_url"))
    if program.get("enrolment_url_verified") is True and is_official_url(enrolment):
        return enrolment
    citizens = program.get("russian_citizens") or {}
    source = public_url(citizens.get("source"))
    if citizens.get("verified") is True and is_official_url(source):
        return source
    return None


def _program_source_url(program: Dict[str, Any], verified_url: Optional[str]) -> Optional[str]:
    if verified_url:
        return verified_url
    citizens = program.get("russian_citizens") or {}
    candidates = [
        public_url(program.get("enrolment_url")),
        public_url(program.get("mile_expiry_source")),
        public_url(citizens.get("source")),
        public_url(program.get("promos_url")),
        *_urls_in_text(program.get("notes")),
    ]
    urls = [url for url in candidates if url]
    official = [url for url in urls if is_official_url(url)]
    if official:
        return official[0]
    return urls[0] if urls else None


def build_alliance_rows(payload: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    data = payload if payload is not None else load_directory()
    if data.get("checked") != CHECKED_AT:
        raise ValueError(f"directory checked date must be {CHECKED_AT}")
    rows: List[Dict[str, Any]] = []
    seen = set()
    for item in data["alliances"]:
        name = item["name"]
        slug = _ALLIANCE_SLUGS[name]
        if slug in seen:
            raise ValueError(f"duplicate alliance slug {slug}")
        seen.add(slug)
        promo_url = public_url(item.get("promo_url"))
        extra_source = public_url(item.get("source"))
        if is_official_url(promo_url):
            source_url = promo_url
        elif is_official_url(extra_source):
            source_url = extra_source
        else:
            source_url = promo_url or extra_source
        promo = _blank(item.get("promo"))
        rows.append(
            {
                "slug": slug,
                "name": name,
                "our_members": list(item.get("our_members") or []),
                "promo": promo,
                "promo_url": promo_url,
                "status_match": _blank(item.get("status_match")),
                "source_url": source_url,
                "zone": _alliance_zone(promo, promo_url),
                "checked_at": CHECKED_AT,
                "legacy": item,
            }
        )
    return rows


def build_program_rows(payload: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    data = payload if payload is not None else load_directory()
    disclaimer = data["disclaimer"]
    if not isinstance(disclaimer, str) or not disclaimer.strip():
        raise ValueError("directory disclaimer is empty")
    alliance_slugs = {row["slug"] for row in build_alliance_rows(data)}
    rows: List[Dict[str, Any]] = []
    seen = set()
    for item in data["programs"]:
        if item.get("checked") != CHECKED_AT:
            raise ValueError(f"{item.get('airline')} checked date must be {CHECKED_AT}")
        airline = item["airline"]
        slug = _PROGRAM_SLUGS[airline]
        if slug in seen:
            raise ValueError(f"duplicate program slug {slug}")
        seen.add(slug)
        alliance_slug = alliance_slug_for_program(item["alliance"])
        if alliance_slug not in alliance_slugs:
            raise ValueError(f"{slug} alliance {alliance_slug} is not in the directory")
        citizens = item.get("russian_citizens") or {}
        verified_url = _program_verification(item)
        source_url = _program_source_url(item, verified_url)
        source_is_official = is_official_url(source_url)
        verified = verified_url is not None
        if verified and not source_is_official:
            raise ValueError(f"{slug} is verified without an official source")
        rows.append(
            {
                "slug": slug,
                "airline": airline,
                "iata": item["iata"],
                "program_name": item["program"],
                "alliance_slug": alliance_slug,
                "alliance_label": item["alliance"],
                "currency": _blank(item.get("currency")),
                "enrolment_url": public_url(item.get("enrolment_url")),
                "enrolment_url_verified": bool(item.get("enrolment_url_verified")),
                "mile_expiry": _blank(item.get("mile_expiry")),
                "mile_expiry_source": public_url(item.get("mile_expiry_source")),
                "key_partners": _blank(item.get("key_partners")),
                "can_join": _blank(citizens.get("can_join")),
                "can_join_basis": _blank(citizens.get("basis")),
                "can_join_source": public_url(citizens.get("source")),
                "can_join_verified": citizens["verified"] if "verified" in citizens else None,
                "status_match": _blank(item.get("status_match")),
                "promos_url": public_url(item.get("promos_url")),
                "notes": _blank(item.get("notes")),
                "source_url": source_url,
                "source_is_official": source_is_official,
                "verified": verified,
                "zone": "green" if verified and source_is_official else "yellow",
                "checked_at": CHECKED_AT,
                "disclaimer": disclaimer,
                "legacy": item,
            }
        )
    return rows


def sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, (dict, list)):
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True)
        return "'" + encoded.replace("'", "''") + "'::jsonb"
    return "'" + str(value).replace("'", "''") + "'"


def _insert(
    table: str,
    columns: Sequence[str],
    rows: Sequence[Dict[str, Any]],
    *,
    date_columns: Sequence[str],
) -> str:
    column_sql = ", ".join(columns)
    updates = ",\n    ".join(f"{column} = EXCLUDED.{column}" for column in columns if column != "slug")
    values = []
    for row in rows:
        literals = []
        for column in columns:
            literal = sql_literal(row[column])
            if column in date_columns and row[column] is not None:
                literal += "::date"
            literals.append(literal)
        values.append("(" + ", ".join(literals) + ")")
    return (
        f"INSERT INTO public.{table} (\n    "
        + column_sql
        + "\n) VALUES\n"
        + ",\n".join(values)
        + "\nON CONFLICT (slug) DO UPDATE SET\n    "
        + updates
        + ",\n    updated_at = now();"
    )


def render_seed_sql(
    alliance_rows: Optional[Sequence[Dict[str, Any]]] = None,
    program_rows: Optional[Sequence[Dict[str, Any]]] = None,
) -> str:
    alliances = list(alliance_rows) if alliance_rows is not None else build_alliance_rows()
    programs = list(program_rows) if program_rows is not None else build_program_rows()
    parts = [
        "-- LOYALTY_PROGRAMS_SEED_BEGIN",
        "-- Idempotent seed. Re-running updates the same alliance and program slug.",
        _insert("loyalty_alliances", _ALLIANCE_COLUMNS, alliances, date_columns=("checked_at",)),
        _insert("loyalty_programs", _PROGRAM_COLUMNS, programs, date_columns=("checked_at",)),
        "-- LOYALTY_PROGRAMS_SEED_END",
    ]
    return "\n".join(parts) + "\n"


def count_summary(
    alliances: Sequence[Dict[str, Any]],
    programs: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    def zones(rows: Sequence[Dict[str, Any]]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for row in rows:
            counts[row["zone"]] = counts.get(row["zone"], 0) + 1
        return dict(sorted(counts.items()))

    return {
        "alliances": len(alliances),
        "programs": len(programs),
        "alliance_zones": zones(alliances),
        "program_zones": zones(programs),
        "checked_at": CHECKED_AT,
    }
