"""Build route cards from measurements and rules. No typed durations."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from database.knowledge_base import (
    GAP_LABEL,
    TRUST_CONFIG,
    format_fact_html,
    is_gap,
    normalize_fact,
)
from database.partners import marker
from database.trust_score import fact_date, score_fact, worst_zone

MODEL_DIR = Path(__file__).with_name("data") / "route_model"
PARTNER_TOKEN = {
    "kiwitaxi": "{KIWITAXI_LINK}",
    "gettransfer": "{GETTRANSFER_LINK}",
    "airalo": "{AIRALO_LINK}",
    "yesim": "{YESIM_LINK}",
}


def _load(name: str) -> Any:
    with (MODEL_DIR / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def format_int(value: int, rules: Dict[str, Any]) -> str:
    """Group large integers. Width and threshold come from rules.json."""
    number = int(value)
    width = int(rules["integer_group"])
    if abs(number) < int(rules["integer_group_from"]):
        return str(number)
    sign = "-" if number < 0 else ""
    digits = str(abs(number))
    parts = []
    while digits:
        parts.append(digits[-width:])
        digits = digits[:-width]
    return sign + " ".join(reversed(parts))


def ru_plural(value: int, forms: List[str]) -> str:
    number = abs(int(value))
    if number % 10 == 1 and number % 100 != 11:
        return forms[0]
    if number % 10 in (2, 3, 4) and number % 100 not in (12, 13, 14):
        return forms[1]
    return forms[2]


def _as_of(rules: Dict[str, Any]) -> date:
    year, month, day = rules["evaluated_on"].split("-")
    return date(int(year), int(month), int(day))


def _status_for(zone: str) -> str:
    mapped = TRUST_CONFIG["zone_to_status"].get(zone)
    if mapped:
        return mapped
    if zone == "gap":
        return "gap"
    return "unconfirmed"


def _gap(text: str) -> Dict[str, Any]:
    if GAP_LABEL not in text.lower():
        text = f"{GAP_LABEL}: {text}"
    return normalize_fact({
        "text": text,
        "status": "gap",
        "fact_type": "gap",
        "zone": "gap",
        "source": None,
        "date_verified": None,
        "source_user_facing": False,
        "agreement": "agree",
    })


def _unit_label(value: Any, unit: Optional[str], rules: Dict[str, Any]) -> Optional[str]:
    forms = rules["units"].get(unit) if unit else None
    if forms and isinstance(value, int):
        return ru_plural(int(value), forms)
    return None


def _extra_numbers(measurement: Dict[str, Any], rules: Dict[str, Any], fields: Dict[str, Any]) -> None:
    for key, spec in (measurement.get("numbers") or {}).items():
        if not isinstance(spec, dict) or not isinstance(spec.get("value"), int):
            raise ValueError(f"Route number {key!r} must be an integer in data")
        fields[key] = format_int(spec["value"], rules)
        label = _unit_label(spec["value"], spec.get("unit"), rules)
        if label:
            fields[f"{key}_label"] = label


def _volatility(measurement: Dict[str, Any], rules: Dict[str, Any]) -> tuple:
    classes = rules["volatility_classes"]
    name = measurement.get("volatility")
    if name not in classes:
        raise ValueError(f"Unknown volatility class {name!r} on {measurement.get('template') or measurement.get('text') or ''}")
    return name, classes[name]


def _sources_checked(measurement: Dict[str, Any], rules: Dict[str, Any]) -> List[Dict[str, Any]]:
    checked = []
    for item in measurement.get("sources_checked") or []:
        if item.get("volatility") not in rules["volatility_classes"]:
            raise ValueError(f"Unknown volatility on a checked source: {item!r}")
        if not item.get("url") or not item.get("source_date"):
            raise ValueError(f"A checked source needs a url and a date: {item!r}")
        checked.append({
            "url": item["url"],
            "source_date": str(item["source_date"])[:10],
            "volatility": item["volatility"],
            "note": item.get("note") or "",
        })
    return checked


def _render_fields(measurement: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    unit = measurement.get("unit")
    if measurement.get("policy_name"):
        fields["policy_name"] = measurement["policy_name"]
    _extra_numbers(measurement, rules, fields)
    kind = measurement.get("kind")
    if kind == "date":
        year, month, day = str(measurement["value"]).split("-")
        fields["value"] = f"{day}.{month}.{year}"
        return fields
    if kind == "range":
        fields["value_min"] = format_int(int(measurement["value_min"]), rules)
        fields["value_max"] = format_int(int(measurement["value_max"]), rules)
        label = _unit_label(int(measurement["value_max"]), unit, rules)
        if label:
            fields["unit_label"] = label
        return fields
    if "value" in measurement and measurement.get("value") is not None and kind != "statement":
        fields["value"] = format_int(measurement["value"], rules) if isinstance(measurement["value"], int) else measurement["value"]
        label = _unit_label(measurement["value"], unit, rules)
        if label:
            fields["unit_label"] = label
    return fields


def _dated(measurement: Dict[str, Any], as_of: date) -> str:
    if measurement.get("source_date"):
        return str(measurement["source_date"])[:10]
    return as_of.isoformat()


def _stamp(fact: Dict[str, Any], measurement: Dict[str, Any], rules: Dict[str, Any], measurement_id: str) -> None:
    name, label = _volatility(measurement, rules)
    fact["measurement_id"] = measurement_id
    fact["volatility"] = name
    fact["volatility_label"] = label
    fact["sources_checked"] = _sources_checked(measurement, rules)


def measurement_fact(measurement_id: str, measurement: Dict[str, Any], rules: Dict[str, Any], as_of: date) -> Dict[str, Any]:
    if measurement.get("gap"):
        fact = _gap(measurement["text"])
        _stamp(fact, measurement, rules, measurement_id)
        return fact
    text = str(measurement["template"]).format(**_render_fields(measurement, rules))
    verified = _dated(measurement, as_of)
    raw = {
        "text": text,
        "status": "unconfirmed",
        "fact_type": "fact",
        "source": measurement.get("source"),
        "source_kind": measurement.get("source_kind"),
        "source_date": measurement.get("source_date"),
        "date_verified": verified,
        "date_estimated": bool(measurement.get("date_estimated")),
        "date_basis": measurement.get("date_basis"),
        "agreement": measurement.get("agreement") or "agree",
        "reports": measurement.get("reports") or 0,
        "source_user_facing": measurement.get("source_user_facing", True),
        "checked_at": as_of.isoformat(),
    }
    scored = score_fact(raw, TRUST_CONFIG, as_of)
    raw["status"] = _status_for(scored["computed_zone"])
    raw["zone"] = scored["computed_zone"]
    raw["score"] = scored["score"]
    raw["score_breakdown"] = scored["score_breakdown"]
    raw["status_derived_from"] = "zone"
    raw["reason"] = (
        f"источник {measurement.get('source_kind')}={scored['score_breakdown']['source']}; "
        f"свежесть {scored['age_days']} дн.={scored['score_breakdown']['freshness']}; "
        f"согласованность={scored['score_breakdown']['agreement']}"
    )
    fact = normalize_fact(raw)
    fact["agreement"] = raw["agreement"]
    fact["reports"] = raw.get("reports") or 0
    _stamp(fact, measurement, rules, measurement_id)
    if measurement.get("kind") == "range":
        fact["value_max"] = measurement["value_max"]
        fact["value"] = measurement["value_max"]
    elif measurement.get("kind") == "value" and isinstance(measurement.get("value"), int):
        fact["value"] = measurement["value"]
    return fact


def _input_minutes(fact: Dict[str, Any]) -> Optional[int]:
    if is_gap(fact):
        return None
    value = fact.get("value")
    if isinstance(value, int):
        return value
    return None


def allowance_fact(spec: Dict[str, Any], facts: Dict[str, Dict[str, Any]], rules: Dict[str, Any], as_of: date) -> Dict[str, Any]:
    """Sum transfer minutes and minimum connection minutes. Missing input → gap."""
    supports = []
    for measurement_id in spec["inputs"]:
        fact = facts.get(measurement_id)
        if fact is None or _input_minutes(fact) is None:
            gap = _gap(rules["formulas"]["allowance_gap"].format(pair=spec["pair"]))
            gap["rule_id"] = spec["id"]
            return gap
        supports.append(fact)
    total = sum(_input_minutes(fact) or 0 for fact in supports)
    forms = rules["units"]["minutes"]
    text = rules["formulas"]["allowance_text"].format(
        pair=spec["pair"],
        value=total,
        unit_label=ru_plural(total, forms),
    )
    zone = worst_zone([fact.get("zone") for fact in supports])
    dates = [fact_date(fact) for fact in supports]
    dates = [item for item in dates if item is not None]
    verified = min(dates).isoformat() if dates else as_of.isoformat()
    raw = {
        "text": text,
        "status": _status_for(zone),
        "fact_type": "advice",
        "zone": zone,
        "score": None,
        "score_breakdown": None,
        "date_verified": verified,
        "source": None,
        "source_user_facing": False,
        "agreement": "agree",
        "supports_resolved": [
            {"text": fact.get("text"), "zone": fact.get("zone"), "score": fact.get("score")}
            for fact in supports
        ],
        "status_derived_from": "advice_supports",
        "reason": "совет; зона = наихудшая из опор",
        "checked_at": as_of.isoformat(),
    }
    fact = normalize_fact(raw)
    fact["rule_id"] = spec["id"]
    fact["value"] = total
    return fact


def _spec_id(spec: Any) -> str:
    if isinstance(spec, str):
        return spec
    return spec["id"]


def _resolve(spec: Any, measurements: Dict[str, Any], built: Dict[str, Dict[str, Any]], rules: Dict[str, Any], as_of: date) -> Dict[str, Any]:
    if isinstance(spec, str):
        if spec not in built:
            built[spec] = measurement_fact(spec, measurements[spec], rules, as_of)
        return built[spec]
    if spec.get("rule") != "airport_change_allowance":
        raise ValueError(f"Unknown route rule: {spec!r}")
    for measurement_id in spec["inputs"]:
        if measurement_id not in built:
            built[measurement_id] = measurement_fact(measurement_id, measurements[measurement_id], rules, as_of)
    return allowance_fact(spec, built, rules, as_of)


def _partner_html(partner_ids: List[str]) -> str:
    tokens = [PARTNER_TOKEN[partner_id] for partner_id in partner_ids]
    joined = " или ".join(tokens)
    return f"Партнёрская ссылка: {joined}\n<i>{{PARTNER_NOTE}}</i>"


def _payment_html(route: Dict[str, Any], rules: Dict[str, Any]) -> str:
    lines = [
        rules["payment_phrase"].format(title=target["title"])
        for target in route["payment_targets"]
    ]
    return "<b>Оплата</b>\n" + "\n".join(lines)


def _section_html(title: str, facts: List[Dict[str, Any]], partners: List[str]) -> str:
    chunks = [f"<b>{title}</b>"]
    for fact in facts:
        chunks.append(format_fact_html(fact, warn=False).replace("\n", "\n"))
    if partners:
        chunks.append(_partner_html(partners))
    return "\n".join(chunks)


def build_routes(
    *,
    rules: Optional[Dict[str, Any]] = None,
    measurements: Optional[Dict[str, Any]] = None,
    definitions: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    rules = rules if rules is not None else _load("rules.json")
    measurements = measurements if measurements is not None else _load("measurements.json")
    definitions = definitions if definitions is not None else _load("routes.json")
    as_of = _as_of(rules)
    travel_marker = marker()
    cards = []
    for route in definitions:
        built: Dict[str, Dict[str, Any]] = {}
        needed: List[Any] = list(route.get("lead_facts") or [])
        needed.append(route["airline_fact"])
        for section in route["sections"]:
            needed.extend(section.get("facts") or [])
        for spec in needed:
            if isinstance(spec, str):
                _resolve(spec, measurements, built, rules, as_of)
            else:
                _resolve(spec, measurements, built, rules, as_of)
        lead = [_resolve(spec, measurements, built, rules, as_of) for spec in route.get("lead_facts") or []]
        airline = _resolve(route["airline_fact"], measurements, built, rules, as_of)
        ticket_links = []
        for ticket in route["tickets"]:
            ticket_links.append({
                "label": ticket["label"],
                "url": rules["ticket_url"].format(
                    origin=route["origin_iata"],
                    date="{DDMM}",
                    destination=ticket["destination"],
                    marker=travel_marker,
                ),
            })
        keyboard = []
        for link in ticket_links:
            keyboard.append([{"text": link["label"], "url": link["url"]}])
        replies: Dict[str, str] = {}
        section_facts: Dict[str, List[Dict[str, Any]]] = {}
        section_roles: Dict[str, str] = {}
        payment_callbacks = []
        for section in route["sections"]:
            callback = f"route:{route['id']}:{section['id']}"
            facts = [_resolve(spec, measurements, built, rules, as_of) for spec in section.get("facts") or []]
            section_facts[callback] = facts
            role = section.get("role") or ""
            if role:
                section_roles[callback] = role
            if role == "payment":
                payment_callbacks.append(callback)
                replies[callback] = _payment_html(route, rules)
            else:
                replies[callback] = _section_html(section["title"], facts, section.get("partners") or [])
            keyboard.append([{"text": section["title"], "callback_data": callback}])
        lead_lines = [fact["text"] for fact in lead]
        text = "<b>{}</b>\n\n{}\n{}".format(route["title"], "\n".join(lead_lines), airline["text"])
        cards.append({
            "id": route["id"],
            "parse_mode": "HTML",
            "text": text,
            "reply_markup": {"inline_keyboard": keyboard},
            "callback_replies": replies,
            "ticket_links": ticket_links,
            "payment_callbacks": payment_callbacks,
            "payment_targets": [
                {
                    "slug": target["slug"],
                    "title": target["title"],
                    "button": rules["payment_button"].format(title=target["title"]),
                }
                for target in route["payment_targets"]
            ],
            "departure_city_id": route["departure_city_id"],
            "destination_slug": route["destination_slug"],
            "iata": route["iata"],
            "airlines": [],
            "airline_gap": airline["text"],
            "summary": lead_lines,
            "lead_facts": lead,
            "section_facts": section_facts,
            "section_roles": section_roles,
        })
    return cards


def gap_texts(cards: Optional[List[Dict[str, Any]]] = None) -> List[str]:
    cards = cards if cards is not None else build_routes()
    seen = []
    for card in cards:
        for facts in card["section_facts"].values():
            for fact in facts:
                if is_gap(fact) and fact["text"] not in seen:
                    seen.append(fact["text"])
        if card["airline_gap"] not in seen:
            seen.append(card["airline_gap"])
    return seen
