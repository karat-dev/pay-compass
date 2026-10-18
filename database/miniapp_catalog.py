"""Public Mini App catalog built from the existing knowledge base and route cards.

Facts are not copied by hand. Visibility uses the same zone rules as the bot
(config/trust_config.json via database.knowledge_base). Scores and internal
notes stay out of the payload.
"""

from __future__ import annotations

import hashlib
import json
import re
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from database.knowledge_base import (
    COUNTRIES_KNOWLEDGE_BASE,
    DATE_VERIFIED,
    INSTRUCTION_LABELS,
    INSTRUCTIONS,
    SECTION_KEYS,
    SECTION_ORDER,
    SUBSECTION_TITLES,
    TRUST_CONFIG,
    _RAW,
    fact_on_request,
    instructions_for_section,
    is_gap,
    public_source_url,
    user_visible_fact,
)
from database.partners import disclosure, public_offers
from database.routes import AVIASALES_MARKER, ROUTES, get_route, lead_lines, section_buttons, tickets_url
from texts.privacy_policy import PRIVACY_POLICY_TEXT

# Approved short labels for the Mini App section grid. Full titles stay in the data.
SHORT_SECTION_TITLES = {
    "1_checklist": "Чек-лист",
    "2_pay_on_site": "Оплата на месте картой РФ/QR",
    "3_local_wallets_cards": "Местные кошельки и карты",
    "4_cash_exchange": "Наличные/обмен",
    "5_atms": "Банкоматы",
    "6_transport": "Транспортная карта",
    "7_risks": "Мошенничество/115-ФЗ",
    "8_tax_free": "Tax free",
}

COUNTRY_ORDER = ("china", "hong_kong", "thailand", "uae", "turkey", "georgia")

# Aviasales city codes for the main city of a destination. A missing code hides
# the ticket button instead of guessing an airport.
DESTINATION_IATA = {
    "china": "BJS",
    "hong_kong": "HKG",
    "thailand": "BKK",
    "uae": "DXB",
    "turkey": "IST",
    "georgia": "TBS",
}

# Route matching lives on each built card (departure city + destination).
# DESTINATION_IATA above is only the empty-state ticket code, not a measured fact.

# Departure cities are a product choice for onboarding, not facts from the guides.
DEPARTURE_CITIES = (
    {"id": "mow", "name": "Москва", "iata": "MOW"},
    {"id": "led", "name": "Санкт-Петербург", "iata": "LED"},
    {"id": "kzn", "name": "Казань", "iata": "KZN"},
    {"id": "svx", "name": "Екатеринбург", "iata": "SVX"},
    {"id": "ovb", "name": "Новосибирск", "iata": "OVB"},
)

# A bank is offered only when one of its names actually appears in the loaded guides.
BANK_RULES = (
    {"id": "tbank", "label": "Т-Банк", "needles": ("Т-Банк", "Тинькофф")},
    {"id": "sber", "label": "Сбер", "needles": ("Сбер",)},
    {"id": "vtb", "label": "ВТБ", "needles": ("ВТБ",)},
    {"id": "mts", "label": "МТС", "needles": ("МТС", "Мой МТС")},
    {"id": "gpb", "label": "Газпромбанк", "needles": ("Газпромбанк",)},
    {"id": "atb", "label": "АТБ", "needles": ("АТБ",)},
    {"id": "rshb", "label": "Россельхозбанк", "needles": ("РСХБ", "Россельхозбанк")},
    {"id": "alfa", "label": "Альфа-Банк", "needles": ("Альфа-Банк", "Альфа‑Банк")},
)

OTHER_BANK = {"id": "other", "label": "Другой", "from_data": False}

_PRIVATE_KEYS = {
    "score",
    "score_breakdown",
    "reason",
    "decision_needed",
    "unknown_zone",
    "needs_owner_check",
    "status_derived_from",
    "source_user_facing",
    "supports",
    "supports_resolved",
    "agreement",
    "refuted",
    "verified_by_us",
    "stored_zone",
    "volatility_class",
    "next_zone",
    "drops_on",
    "at_risk",
    "at_risk_reason",
    "reports",
    "contradicted_by_own",
    "sources_checked",
}


class _HTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self.links: List[Dict[str, str]] = []
        self._href: Optional[str] = None
        self._buf: List[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        attr = dict(attrs)
        if tag == "a":
            self._href = attr.get("href")
            self._buf = []
        elif tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            label = "".join(self._buf).strip()
            if label or self._href:
                self.links.append({"url": self._href, "label": label or self._href})
            if label:
                self.parts.append(label)
            self._href = None
            self._buf = []
        if tag in {"p", "div"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._buf.append(data)
        else:
            self.parts.append(data)


def html_to_plain(value: str) -> tuple:
    parser = _HTMLText()
    parser.feed(value or "")
    parser.close()
    text = "".join(parser.parts)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text, parser.links


def _display_date(value: Optional[str]) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    if len(value) >= 10 and value[4] == "-" and value[7] == "-":
        year, month, day = value[:10].split("-")
        return f"{day}.{month}.{year}"
    return value


def _fact_id(scope: str, text: str) -> str:
    digest = hashlib.sha256(f"{scope}\n{text}".encode("utf-8")).hexdigest()[:16]
    return f"{scope}:{digest}"


def _is_placeholder_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == "example" or host.endswith(".example") or host == "example.com"


def publish_fact(
    fact: Dict[str, Any],
    scope: str,
    *,
    country_slug: Optional[str] = None,
    section_key: Optional[str] = None,
    instruction_id: Optional[str] = None,
    subsection: Optional[str] = None,
    step_n: Optional[int] = None,
    stage: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if not user_visible_fact(fact):
        return None
    source_url = public_source_url(fact)
    published: Dict[str, Any] = {
        "id": _fact_id(scope, fact.get("text") or ""),
        "text": fact.get("text") or "",
        "zone": fact.get("zone"),
        "gap": is_gap(fact),
        "hidden": fact_on_request(fact),
        "date": _display_date(fact.get("date_verified")),
        "date_estimated": bool(fact.get("date_estimated")),
        "source_url": source_url,
        "volatility": fact.get("volatility") or "",
        "volatility_label": fact.get("volatility_label") or "",
        "country_slug": country_slug,
        "section_key": section_key,
        "instruction_id": instruction_id,
        "subsection": subsection,
    }
    if step_n is not None:
        published["n"] = step_n
    if stage:
        published["stage"] = stage
    return published


def _corpus_text() -> str:
    chunks: List[str] = []
    for country in COUNTRIES_KNOWLEDGE_BASE.values():
        chunks.append(country.get("name") or "")
        for section in country["sections"].values():
            for fact in section.get("facts") or []:
                chunks.append(fact.get("text") or "")
            for subsection in (section.get("subsections") or {}).values():
                for fact in subsection.get("facts") or []:
                    chunks.append(fact.get("text") or "")
    for instruction in INSTRUCTIONS.values():
        for key in ("service", "app", "provider", "intro", "costs", "limits"):
            value = instruction.get(key)
            if isinstance(value, str):
                chunks.append(value)
        for item in (instruction.get("prereq") or []) + (instruction.get("risks") or []):
            if isinstance(item, str):
                chunks.append(item)
        for step in instruction.get("steps") or []:
            chunks.append(step.get("text") or "")
    return "\n".join(chunks)


def banks_from_data() -> List[Dict[str, Any]]:
    corpus = _corpus_text()
    found = []
    for rule in BANK_RULES:
        if any(needle in corpus for needle in rule["needles"]):
            found.append({"id": rule["id"], "label": rule["label"], "from_data": True})
    found.append(dict(OTHER_BANK))
    return found


def _publish_pool(
    facts: List[Dict[str, Any]],
    scope: str,
    **meta: Any,
) -> List[Dict[str, Any]]:
    published = []
    for fact in facts:
        item = publish_fact(fact, scope, **meta)
        if item:
            published.append(item)
    return published


def _public_instructions() -> Dict[str, Any]:
    public: Dict[str, Any] = {}
    for instruction_id, instruction in INSTRUCTIONS.items():
        steps = []
        for index, step in enumerate(instruction.get("steps") or [], start=1):
            step_n = step.get("n") or index
            item = publish_fact(
                step,
                f"instruction/{instruction_id}/{step_n}",
                country_slug=(instruction.get("countries") or [None])[0],
                instruction_id=instruction_id,
                section_key=instruction.get("section"),
                step_n=step_n,
                stage=step.get("stage"),
            )
            if item:
                steps.append(item)
        public[instruction_id] = {
            "id": instruction_id,
            "service": instruction.get("service") or instruction_id,
            "label": INSTRUCTION_LABELS.get(instruction_id) or instruction.get("service") or instruction_id,
            "countries": list(instruction.get("countries") or []),
            "app": instruction.get("app"),
            "provider": instruction.get("provider"),
            "section": instruction.get("section"),
            "date": _display_date(instruction.get("date_verified")),
            "intro": instruction.get("intro"),
            "prereq": list(instruction.get("prereq") or []),
            "costs": instruction.get("costs"),
            "limits": instruction.get("limits"),
            "risks": list(instruction.get("risks") or []),
            "steps": steps,
        }
    return public


def _public_route(route_id: str = "mow_hkg_via_pek") -> Dict[str, Any]:
    route = get_route(route_id)
    partner_urls = {offer["url"] for offer in public_offers()}
    plain, links = html_to_plain(route.get("text") or "")
    airlines = []
    seen_airlines = set()
    for link in links:
        name = link["label"]
        if name in seen_airlines:
            continue
        seen_airlines.add(name)
        airlines.append({
            "name": name,
            "url": link["url"],
            "placeholder": _is_placeholder_url(link["url"]),
        })
    airline_names = {item["name"] for item in airlines}
    paragraphs = []
    for block in [part.strip() for part in plain.split("\n\n") if part.strip()]:
        if block in airline_names or block == "Авиакомпании":
            continue
        if any(name in block for name in airline_names) and "→" in block:
            continue
        paragraphs.append(block)
    sections = []
    for button in section_buttons(route):
        body = route["callback_replies"].get(button["callback_data"]) or ""
        text, section_links = html_to_plain(body)
        published_facts = []
        for fact in (route.get("section_facts") or {}).get(button["callback_data"]) or []:
            item = publish_fact(
                fact,
                f"route/{route['id']}/{button['callback_data']}",
                country_slug=route.get("destination_slug") or "",
            )
            if item:
                published_facts.append(item)
        sections.append({
            "id": button["callback_data"],
            "title": button["text"],
            "role": (route.get("section_roles") or {}).get(button["callback_data"]) or "",
            "text": text,
            "facts": published_facts,
            "links": [
                {
                    "label": link["label"],
                    "url": link["url"],
                    "placeholder": _is_placeholder_url(link["url"]),
                    "partner": link["url"] in partner_urls,
                }
                for link in section_links
                if link["label"] != "Источник"
            ],
        })
    lines = lead_lines(route.get("text") or "")
    title = lines[0] if lines else route["id"]
    summary = route.get("summary") or [
        paragraph for paragraph in paragraphs if paragraph != title
    ]
    lead_facts = [
        publish_fact(fact, f"route/{route['id']}/lead/{index}", country_slug=route.get("destination_slug") or "")
        for index, fact in enumerate(route.get("lead_facts") or [])
    ]
    lead_facts = [fact for fact in lead_facts if fact]
    return {
        "id": route["id"],
        "title": title,
        "summary": summary,
        "airlines": route.get("airlines") if "airlines" in route else airlines,
        "airline_gap": route.get("airline_gap") or "",
        "lead_facts": lead_facts,
        "tickets_url": tickets_url(route),
        "ticket_links": list(route.get("ticket_links") or []),
        "marker": AVIASALES_MARKER,
        "departure_city_id": route.get("departure_city_id") or "",
        "destination_slug": route.get("destination_slug") or "",
        "iata": route.get("iata") or "",
        "sections": sections,
    }


def _assert_public(payload: Dict[str, Any]) -> None:
    """Guard so a future field does not leak internal trust math into the app."""
    def walk(node: Any) -> None:
        if isinstance(node, dict):
            leaked = _PRIVATE_KEYS.intersection(node)
            if leaked:
                raise RuntimeError(f"public catalog leaked {sorted(leaked)}")
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(payload)


def build_catalog() -> Dict[str, Any]:
    instructions = _public_instructions()
    countries = []
    for slug in COUNTRY_ORDER:
        raw = COUNTRIES_KNOWLEDGE_BASE[slug]
        sections = []
        for key, title in SECTION_ORDER:
            section = raw["sections"][key]
            subsections = []
            for name, subsection in (section.get("subsections") or {}).items():
                subsections.append({
                    "id": name,
                    "title": SUBSECTION_TITLES.get(name, name),
                    "applicable": bool(subsection.get("applicable", True)),
                    "note": subsection.get("reason"),
                    "facts": _publish_pool(
                        subsection.get("facts") or [],
                        f"{slug}/{key}/{name}",
                        country_slug=slug,
                        section_key=key,
                        subsection=name,
                    ),
                })
            sections.append({
                "key": key,
                "title": title,
                "short_title": SHORT_SECTION_TITLES[key],
                "applicable": bool(section.get("applicable", True)),
                "note": section.get("reason"),
                "facts": _publish_pool(
                    section.get("facts") or [],
                    f"{slug}/{key}",
                    country_slug=slug,
                    section_key=key,
                ),
                "subsections": subsections,
                "instructions": instructions_for_section(raw, key),
            })
        countries.append({
            "slug": slug,
            "name": raw["name"],
            "headline": raw.get("headline") or "",
            "ticket_iata": DESTINATION_IATA.get(slug) or "",
            "sections": sections,
        })

    checked_at = _RAW.get("checked_at") if isinstance(_RAW, dict) else None
    catalog = {
        "version": 1,
        "checked_at": checked_at,
        "checked_label": DATE_VERIFIED,
        "display_min": TRUST_CONFIG["display"]["default_min"],
        "gap_label": TRUST_CONFIG["display"]["gap_label"],
        "gap_zone": (TRUST_CONFIG["display"].get("gap_zones") or [None])[0],
        "missing_zone": TRUST_CONFIG["display"]["missing_zone"],
        "zone_groups": [
            {"name": name, "title": TRUST_CONFIG["display"]["group_titles"][name]}
            for name in TRUST_CONFIG["display"]["group_order"]
        ],
        "zone_titles": dict(TRUST_CONFIG["display"]["zone_titles"]),
        "zone_legend": [dict(item) for item in TRUST_CONFIG["display"]["legend"]],
        "sources": [
            "database/data/countries.json",
            "config/trust_config.json",
            "database/data/routes",
        ],
        "banks": banks_from_data(),
        "cities": [dict(city) for city in DEPARTURE_CITIES],
        "privacy": PRIVACY_POLICY_TEXT,
        "countries": countries,
        "instructions": instructions,
        "routes": [_public_route(route_id) for route_id in ROUTES],
        "tickets_marker": AVIASALES_MARKER,
        "section_keys": list(SECTION_KEYS),
        "partner_note": disclosure(),
        "offers": public_offers(),
    }
    _assert_public(catalog)
    return catalog


_CATALOG: Optional[Dict[str, Any]] = None
_FACT_INDEX: Dict[str, Dict[str, Any]] = {}


def get_catalog() -> Dict[str, Any]:
    global _CATALOG, _FACT_INDEX
    if _CATALOG is None:
        _CATALOG = build_catalog()
        index: Dict[str, Dict[str, Any]] = {}

        def take(fact: Dict[str, Any]) -> None:
            if fact.get("id"):
                index[fact["id"]] = fact

        for country in _CATALOG["countries"]:
            for section in country["sections"]:
                for fact in section["facts"]:
                    take(fact)
                for subsection in section["subsections"]:
                    for fact in subsection["facts"]:
                        take(fact)
        for instruction in _CATALOG["instructions"].values():
            for step in instruction["steps"]:
                take(step)
        for route in _CATALOG["routes"]:
            for fact in route.get("lead_facts") or []:
                take(fact)
            for section in route["sections"]:
                for fact in section.get("facts") or []:
                    take(fact)
        _FACT_INDEX = index
    return _CATALOG


def find_fact(fact_id: str) -> Optional[Dict[str, Any]]:
    get_catalog()
    return _FACT_INDEX.get(fact_id)


def known_bank_ids() -> set:
    return {bank["id"] for bank in get_catalog()["banks"]}


def known_city_ids() -> set:
    return {city["id"] for city in get_catalog()["cities"]}


def known_country_slugs() -> set:
    return {country["slug"] for country in get_catalog()["countries"]}


def reload_catalog() -> Dict[str, Any]:
    """Test helper. The data files do not change at runtime."""
    global _CATALOG
    _CATALOG = None
    return get_catalog()


def catalog_json() -> str:
    return json.dumps(get_catalog(), ensure_ascii=False)
