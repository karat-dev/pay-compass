"""Idempotent rows for airport facts, ride services, taxi tariffs, and route_model.

Zone model is the 24.11.2026 rule, the same one as guide facts: an official
confirmed source is green, anything unconfirmed or secondary is yellow, and
an explicit risk cap is red. It does not use the point formula in
config/trust_config.json.

Ride services follow that rule in the words of the research file: green only
when status is «подтверждено» and the URL is the operator's own site (or the
official store listing, when that listing is the claim). «требует проверки
владельцем» and any other source are yellow.

``owner_check`` and ``legacy`` are internal. The migration grants no SELECT
on those columns to anon or authenticated.

Telegram and forum URLs are not copied into public source columns.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

from database.guide_facts_seed import assign_zone_status, private_marker_in_url, source_is_official
from database.knowledge_base import public_source_url

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "database" / "data"
AIRPORT_PATH = DATA / "airport_facts_2026-10-27.json"
RIDE_PATH = DATA / "ride_services_research.jsonl"
TARIFF_PATH = DATA / "taxi_tariff_rules.jsonl"
ROUTES_PATH = DATA / "route_model" / "routes.json"
MEASUREMENTS_PATH = DATA / "route_model" / "measurements.json"
RULES_PATH = DATA / "route_model" / "rules.json"

RULES_SOURCE_KEY = "route_model:rules"
RIDE_CONFIRMED = "подтверждено"
RIDE_OWNER_CHECK = "требует проверки владельцем"

# Operator site, or the official store when the row's claim is the store listing.
OFFICIAL_RIDE_HOSTS: Dict[str, Tuple[str, ...]] = {
    "Uber": ("uber.com",),
    "Bolt": ("bolt.eu",),
    "Grab": ("grab.com",),
    "Careem": ("careem.com",),
    "BiTaksi": ("bitaksi.com",),
    "Yango": ("yango.com",),
    "Yandex Go": ("yandex.ru", "ya.ru"),
    "DiDi": ("didiglobal.com", "didi.cn", "xiaojukeji.com"),
    "Amap": ("amap.com",),
    "AMap Global": ("itunes.apple.com", "apps.apple.com", "amap.com"),
    "inDrive": ("indrive.com",),
    "Kiwitaxi": ("kiwitaxi.ru", "kiwitaxi.com"),
    "GetTransfer": ("gettransfer.com",),
    "Яндекс Драйв": ("yandex.ru",),
    "Делимобиль": ("delimobil.ru",),
    "Ситидрайв": ("citydrive.ru",),
    "Welcome Pickups": ("welcomepickups.com",),
}

_ISO_SLUG = {
    "TR": "turkey",
    "AE": "uae",
    "TH": "thailand",
    "CN": "china",
    "GE": "georgia",
    "RU": "russia",
    "HK": "hong_kong",
}

_MEASUREMENT_PUBLIC_KEYS = (
    "kind",
    "value",
    "value_min",
    "value_max",
    "unit",
    "template",
    "source",
    "source_kind",
    "source_date",
    "agreement",
    "volatility",
    "transfer_topic",
    "transfer_measure",
    "gap",
    "text",
    "verified_by_us",
)
_MEASUREMENT_DETAIL_KEYS = (
    "numbers",
    "distance",
    "tolls_label",
    "slot_label",
    "slot_kind",
    "service",
    "direction",
    "pickup",
    "policy_name",
    "date_estimated",
    "sources_checked",
    "date_basis",
)
_MEASUREMENT_INTERNAL_KEYS = ("source_user_facing",)
_ROUTE_KEYS = (
    "id",
    "title",
    "departure_city_id",
    "destination_slug",
    "origin_iata",
    "iata",
    "tickets",
    "payment_targets",
    "airline_fact",
    "lead_facts",
    "sections",
)
_RULE_KEYS = (
    "evaluated_on",
    "ticket_url",
    "payment_phrase",
    "payment_button",
    "units",
    "integer_group",
    "integer_group_from",
    "volatility_classes",
    "engine_volatility",
    "formulas",
    "slot_joiner",
)

AIRPORT_INSERT_COLUMNS = (
    "source_key",
    "country_slug",
    "airport_code",
    "topic",
    "fact",
    "zone",
    "status",
    "source_url",
    "source_type",
    "source_is_official",
    "checked_at",
    "needs_owner_check",
    "decision_needed",
    "unknown_zone",
    "legacy",
)
RIDE_INSERT_COLUMNS = (
    "source_key",
    "service",
    "category",
    "country_iso2",
    "country_slug",
    "city",
    "status",
    "zone",
    "source_url",
    "availability",
    "payment",
    "account",
    "interface_lang",
    "ru_store_vpn",
    "airport",
    "pricing",
    "check_date",
    "store_source",
    "owner_check",
    "legacy",
)
TARIFF_INSERT_COLUMNS = (
    "source_key",
    "country_iso2",
    "service",
    "zone_label",
    "captured_at",
    "source_kind",
    "currency",
    "note",
    "tariffs",
    "zone",
)
ROUTE_INSERT_COLUMNS = (
    "source_key",
    "title",
    "departure_city_id",
    "destination_slug",
    "origin_iata",
    "iata",
    "tickets",
    "payment_targets",
    "airline_fact",
    "lead_facts",
    "sections",
)
MEASUREMENT_INSERT_COLUMNS = (
    "source_key",
    "kind",
    "gap",
    "value_num",
    "value_text",
    "value_min",
    "value_max",
    "unit",
    "template",
    "statement",
    "source_url",
    "source_kind",
    "source_date",
    "agreement",
    "volatility",
    "transfer_topic",
    "transfer_measure",
    "verified_by_us",
    "details",
    "legacy",
)
RULE_INSERT_COLUMNS = (
    "source_key",
    "evaluated_on",
    "ticket_url",
    "payment_phrase",
    "payment_button",
    "units",
    "integer_group",
    "integer_group_from",
    "volatility_classes",
    "engine_volatility",
    "formulas",
    "slot_joiner",
)

# Columns anon and authenticated may read. owner_check and legacy stay off this list.
AIRPORT_PUBLIC_COLUMNS = (
    "id",
    "source_key",
    "country_slug",
    "airport_code",
    "topic",
    "fact",
    "zone",
    "status",
    "source_url",
    "source_type",
    "source_is_official",
    "checked_at",
    "needs_owner_check",
    "decision_needed",
    "unknown_zone",
    "created_at",
    "updated_at",
)
RIDE_PUBLIC_COLUMNS = (
    "id",
    "source_key",
    "service",
    "category",
    "country_iso2",
    "country_slug",
    "city",
    "status",
    "zone",
    "source_url",
    "availability",
    "payment",
    "account",
    "interface_lang",
    "ru_store_vpn",
    "airport",
    "pricing",
    "check_date",
    "store_source",
    "created_at",
    "updated_at",
)
MEASUREMENT_PUBLIC_COLUMNS = (
    "id",
    "source_key",
    "kind",
    "gap",
    "value_num",
    "value_text",
    "value_min",
    "value_max",
    "unit",
    "template",
    "statement",
    "source_url",
    "source_kind",
    "source_date",
    "agreement",
    "volatility",
    "transfer_topic",
    "transfer_measure",
    "verified_by_us",
    "details",
    "created_at",
    "updated_at",
)

_DATE_COLUMNS = {"checked_at", "check_date", "source_date", "evaluated_on"}
_TIMESTAMP_COLUMNS = {"captured_at"}


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _blank(value: Any) -> Any:
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def _require_unique(rows: Sequence[Dict[str, Any]], label: str) -> None:
    keys = [row["source_key"] for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError(f"duplicate {label} source_key")


def _hostname(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def ride_source_is_official(service: str, source_url: Optional[str]) -> bool:
    """True when the URL is that service's own site or its official store claim."""
    if not source_url:
        return False
    host = _hostname(source_url)
    allowed = OFFICIAL_RIDE_HOSTS.get(service, ())
    return any(host == item or host.endswith("." + item) for item in allowed)


def ride_zone(status: str, official: bool) -> str:
    """Green only for a confirmed row backed by an official source."""
    if status == RIDE_CONFIRMED and official:
        return "green"
    if status not in {RIDE_CONFIRMED, RIDE_OWNER_CHECK}:
        raise ValueError(f"unexpected ride status: {status}")
    return "yellow"


def tariff_zone(source_kind: str) -> str:
    """A screenshot of our own measurement stays yellow. Official copy can be green."""
    if source_kind == "official":
        return "green"
    if source_kind == "user_screenshot":
        return "yellow"
    return "yellow"


def country_slug_for_iso(country: str) -> str:
    if country == "*":
        return "all"
    if "/" in country:
        return "multi"
    try:
        return _ISO_SLUG[country]
    except KeyError as exc:
        raise ValueError(f"unknown ride country {country}") from exc


def airport_source_key(country: str, airport: str, topic: str) -> str:
    return f"airport:{country}|{airport}|{topic}"


def ride_source_key(service: str, country: str, city: str) -> str:
    return f"ride:{service}|{country}|{city}"


def tariff_source_key(country: str, service: str, zone_label: str) -> str:
    return f"tariff:{country}|{service}|{zone_label}"


def _public_http_url(source: Any, *, source_kind: str = "", source_type: str = "", user_facing: Any = True) -> Optional[str]:
    if not isinstance(source, str):
        return None
    return public_source_url(
        {
            "source": source,
            "source_user_facing": True if user_facing is None else user_facing,
            "source_kind": source_kind,
            "source_type": source_type,
        }
    )


def _sanitize_sources_checked(items: Any) -> List[Dict[str, Any]]:
    cleaned: List[Dict[str, Any]] = []
    for item in items or []:
        copy = dict(item)
        url = copy.get("url")
        if isinstance(url, str):
            safe = _public_http_url(url, source_kind=str(item.get("volatility") or ""))
            if safe is None:
                copy.pop("url", None)
            else:
                copy["url"] = safe
        note = copy.get("note")
        if isinstance(note, str) and private_marker_in_url(note):
            copy.pop("note", None)
        cleaned.append(copy)
    return cleaned


def build_airport_fact_rows(
    facts: Optional[Sequence[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    raw = list(facts) if facts is not None else _load_json(AIRPORT_PATH)
    rows: List[Dict[str, Any]] = []
    for item in raw:
        source_type = _blank(item.get("source_type"))
        shaped = {
            "status": item.get("status"),
            "source_type": source_type,
            "source_kind": "official" if (source_type or "").lower() == "official" else source_type,
            "text": item["text"],
            "source": item.get("source"),
            "checked_at": item.get("checked_at"),
            "needs_owner_check": bool(item.get("needs_owner_check")),
        }
        zone, status = assign_zone_status(shaped)
        rows.append(
            {
                "source_key": airport_source_key(item["country"], item["airport"], item["topic"]),
                "country_slug": item["country"],
                "airport_code": item["airport"],
                "topic": item["topic"],
                "fact": item["text"],
                "zone": zone,
                "status": status,
                "source_url": _public_http_url(
                    item.get("source"),
                    source_kind=shaped["source_kind"] or "",
                    source_type=source_type or "",
                ),
                "source_type": source_type,
                "source_is_official": source_is_official(shaped),
                "checked_at": item["checked_at"],
                "needs_owner_check": bool(item.get("needs_owner_check")),
                "decision_needed": _blank(item.get("decision_needed")),
                "unknown_zone": _blank(item.get("unknown_zone")),
                "legacy": item,
            }
        )
    _require_unique(rows, "airport_facts")
    return rows


def build_ride_rows(records: Optional[Sequence[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    raw = list(records) if records is not None else _load_jsonl(RIDE_PATH)
    rows: List[Dict[str, Any]] = []
    for item in raw:
        status = item["status"]
        source_url = _public_http_url(item.get("source_url") or None)
        official = ride_source_is_official(item["service"], source_url)
        city = item.get("city") or ""
        rows.append(
            {
                "source_key": ride_source_key(item["service"], item["country"], city),
                "service": item["service"],
                "category": item["category"],
                "country_iso2": item["country"],
                "country_slug": country_slug_for_iso(item["country"]),
                "city": _blank(city),
                "status": status,
                "zone": ride_zone(status, official),
                "source_url": source_url,
                "availability": _blank(item.get("availability")),
                "payment": _blank(item.get("payment")),
                "account": _blank(item.get("account")),
                "interface_lang": _blank(item.get("interface_lang")),
                "ru_store_vpn": _blank(item.get("ru_store_vpn")),
                "airport": _blank(item.get("airport")),
                "pricing": _blank(item.get("pricing")),
                "check_date": item["check_date"],
                "store_source": None
                if private_marker_in_url(item.get("store_source"))
                else _blank(item.get("store_source")),
                "owner_check": _blank(item.get("owner_check")),
                "legacy": item,
            }
        )
    _require_unique(rows, "ride_services")
    return rows


def build_tariff_rows(records: Optional[Sequence[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    raw = list(records) if records is not None else _load_jsonl(TARIFF_PATH)
    rows: List[Dict[str, Any]] = []
    for item in raw:
        source_kind = item["source"]
        rows.append(
            {
                "source_key": tariff_source_key(item["country"], item["service"], item["zone"]),
                "country_iso2": item["country"],
                "service": item["service"],
                "zone_label": item["zone"],
                "captured_at": item["captured"],
                "source_kind": source_kind,
                "currency": item["currency"],
                "note": _blank(item.get("note")),
                "tariffs": item["tariffs"],
                "zone": tariff_zone(source_kind),
            }
        )
    _require_unique(rows, "taxi_tariff_rules")
    return rows


def build_route_rows(routes: Optional[Sequence[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    raw = list(routes) if routes is not None else _load_json(ROUTES_PATH)
    rows: List[Dict[str, Any]] = []
    for item in raw:
        unknown = set(item) - set(_ROUTE_KEYS)
        if unknown:
            raise ValueError(f"unexpected route fields: {sorted(unknown)}")
        rows.append(
            {
                "source_key": item["id"],
                "title": item["title"],
                "departure_city_id": item["departure_city_id"],
                "destination_slug": item["destination_slug"],
                "origin_iata": item["origin_iata"],
                "iata": item["iata"],
                "tickets": item.get("tickets") or [],
                "payment_targets": item.get("payment_targets") or [],
                "airline_fact": item.get("airline_fact"),
                "lead_facts": item.get("lead_facts") or [],
                "sections": item.get("sections") or [],
            }
        )
    _require_unique(rows, "transport_routes")
    return rows


def _measurement_details(item: Dict[str, Any], user_facing: bool) -> Dict[str, Any]:
    details: Dict[str, Any] = {}
    for key in _MEASUREMENT_DETAIL_KEYS:
        if key not in item or item[key] is None:
            continue
        if key == "sources_checked":
            details[key] = _sanitize_sources_checked(item[key])
            continue
        if key == "date_basis":
            basis = item[key]
            if not user_facing or (isinstance(basis, str) and private_marker_in_url(basis)):
                continue
        details[key] = item[key]
    return details


def _split_value(value: Any, label: str) -> Tuple[Optional[Any], Optional[str]]:
    if value is None:
        return None, None
    if isinstance(value, bool) or isinstance(value, (dict, list)):
        raise ValueError(f"{label} does not fit a numeric or text column")
    if isinstance(value, (int, float)):
        return value, None
    return None, str(value)


def build_measurement_rows(
    measurements: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    raw = measurements if measurements is not None else _load_json(MEASUREMENTS_PATH)
    known = set(_MEASUREMENT_PUBLIC_KEYS) | set(_MEASUREMENT_DETAIL_KEYS) | set(_MEASUREMENT_INTERNAL_KEYS)
    rows: List[Dict[str, Any]] = []
    for key, item in raw.items():
        unknown = set(item) - known
        if unknown:
            raise ValueError(f"unexpected measurement fields on {key}: {sorted(unknown)}")
        user_facing = item.get("source_user_facing") is not False
        value_num, value_text = _split_value(item.get("value"), key)
        value_min, min_text = _split_value(item.get("value_min"), key)
        value_max, max_text = _split_value(item.get("value_max"), key)
        if min_text is not None or max_text is not None:
            raise ValueError(f"{key} range bounds must be numeric")
        rows.append(
            {
                "source_key": key,
                "kind": item.get("kind"),
                "gap": bool(item.get("gap")),
                "value_num": value_num,
                "value_text": value_text,
                "value_min": value_min,
                "value_max": value_max,
                "unit": item.get("unit"),
                "template": item.get("template"),
                "statement": item.get("text"),
                "source_url": _public_http_url(
                    item.get("source"),
                    source_kind=str(item.get("source_kind") or ""),
                    source_type=str(item.get("source_kind") or ""),
                    user_facing=item.get("source_user_facing", True),
                ),
                "source_kind": item.get("source_kind"),
                "source_date": item.get("source_date"),
                "agreement": item.get("agreement"),
                "volatility": item["volatility"],
                "transfer_topic": item.get("transfer_topic"),
                "transfer_measure": item.get("transfer_measure"),
                "verified_by_us": bool(item.get("verified_by_us")),
                "details": _measurement_details(item, user_facing),
                "legacy": item,
            }
        )
    _require_unique(rows, "transport_measurements")
    return rows


def build_rule_rows(rules: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    raw = rules if rules is not None else _load_json(RULES_PATH)
    unknown = set(raw) - set(_RULE_KEYS)
    if unknown:
        raise ValueError(f"unexpected route rule fields: {sorted(unknown)}")
    return [
        {
            "source_key": RULES_SOURCE_KEY,
            "evaluated_on": raw["evaluated_on"],
            "ticket_url": raw["ticket_url"],
            "payment_phrase": raw["payment_phrase"],
            "payment_button": raw["payment_button"],
            "units": raw["units"],
            "integer_group": raw["integer_group"],
            "integer_group_from": raw["integer_group_from"],
            "volatility_classes": raw["volatility_classes"],
            "engine_volatility": raw["engine_volatility"],
            "formulas": raw["formulas"],
            "slot_joiner": raw["slot_joiner"],
        }
    ]


def sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite number in seed")
        return format(value, ".15g")
    if isinstance(value, (dict, list)):
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True)
        return "'" + encoded.replace("'", "''") + "'::jsonb"
    return "'" + str(value).replace("'", "''") + "'"


def _insert_sql(
    table: str,
    columns: Sequence[str],
    rows: Sequence[Dict[str, Any]],
    *,
    batch: int = 40,
) -> str:
    column_sql = ", ".join(columns)
    updates = ",\n    ".join(f"{column} = EXCLUDED.{column}" for column in columns if column != "source_key")
    chunks: List[str] = []
    for start in range(0, len(rows), batch):
        values: List[str] = []
        for row in rows[start : start + batch]:
            literals: List[str] = []
            for column in columns:
                literal = sql_literal(row[column])
                if row[column] is not None and column in _DATE_COLUMNS:
                    literal += "::date"
                elif row[column] is not None and column in _TIMESTAMP_COLUMNS:
                    literal += "::timestamptz"
                literals.append(literal)
            values.append("(" + ", ".join(literals) + ")")
        chunks.append(
            f"INSERT INTO public.{table} (\n    {column_sql}\n) VALUES\n"
            + ",\n".join(values)
            + "\nON CONFLICT (source_key) DO UPDATE SET\n    "
            + updates
            + ",\n    updated_at = now();"
        )
    return "\n\n".join(chunks)


def render_seed_sql(
    airports: Optional[Sequence[Dict[str, Any]]] = None,
    rides: Optional[Sequence[Dict[str, Any]]] = None,
    tariffs: Optional[Sequence[Dict[str, Any]]] = None,
    routes: Optional[Sequence[Dict[str, Any]]] = None,
    measurements: Optional[Sequence[Dict[str, Any]]] = None,
    rules: Optional[Sequence[Dict[str, Any]]] = None,
) -> str:
    airport_rows = list(airports) if airports is not None else build_airport_fact_rows()
    ride_rows = list(rides) if rides is not None else build_ride_rows()
    tariff_rows = list(tariffs) if tariffs is not None else build_tariff_rows()
    route_rows = list(routes) if routes is not None else build_route_rows()
    measurement_rows = list(measurements) if measurements is not None else build_measurement_rows()
    rule_rows = list(rules) if rules is not None else build_rule_rows()
    parts = [
        "-- TRANSPORT_FACTS_SEED_BEGIN",
        "-- Idempotent seed. Re-running updates the same source_key.",
        _insert_sql("airport_facts", AIRPORT_INSERT_COLUMNS, airport_rows),
        _insert_sql("ride_services", RIDE_INSERT_COLUMNS, ride_rows),
        _insert_sql("taxi_tariff_rules", TARIFF_INSERT_COLUMNS, tariff_rows),
        _insert_sql("transport_routes", ROUTE_INSERT_COLUMNS, route_rows),
        _insert_sql("transport_measurements", MEASUREMENT_INSERT_COLUMNS, measurement_rows, batch=20),
        _insert_sql("transport_rules", RULE_INSERT_COLUMNS, rule_rows),
        "-- TRANSPORT_FACTS_SEED_END",
    ]
    return "\n".join(parts) + "\n"


def _tally(rows: Iterable[Dict[str, Any]], key: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        value = row[key]
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def count_summary(
    airports: Optional[Sequence[Dict[str, Any]]] = None,
    rides: Optional[Sequence[Dict[str, Any]]] = None,
    tariffs: Optional[Sequence[Dict[str, Any]]] = None,
    routes: Optional[Sequence[Dict[str, Any]]] = None,
    measurements: Optional[Sequence[Dict[str, Any]]] = None,
    rules: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    airport_rows = list(airports) if airports is not None else build_airport_fact_rows()
    ride_rows = list(rides) if rides is not None else build_ride_rows()
    tariff_rows = list(tariffs) if tariffs is not None else build_tariff_rows()
    route_rows = list(routes) if routes is not None else build_route_rows()
    measurement_rows = list(measurements) if measurements is not None else build_measurement_rows()
    rule_rows = list(rules) if rules is not None else build_rule_rows()
    return {
        "airport_facts": {
            "rows": len(airport_rows),
            "by_zone": _tally(airport_rows, "zone"),
            "by_status": _tally(airport_rows, "status"),
            "by_country": _tally(airport_rows, "country_slug"),
        },
        "ride_services": {
            "rows": len(ride_rows),
            "by_zone": _tally(ride_rows, "zone"),
            "by_status": _tally(ride_rows, "status"),
            "by_country": _tally(ride_rows, "country_slug"),
        },
        "taxi_tariff_rules": {
            "rows": len(tariff_rows),
            "by_zone": _tally(tariff_rows, "zone"),
        },
        "transport_routes": len(route_rows),
        "transport_measurements": len(measurement_rows),
        "transport_rules": len(rule_rows),
    }
