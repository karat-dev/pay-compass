"""
Country guides, schema v2 (13.10.2026).

Eight sections in a fixed order. Travellers see confirmed facts by default.
Unconfirmed and outdated facts appear only on request, with a warning.
needs_owner_check, decision_needed and unknown_zone stay internal.
Forum summaries are not stored and are not shown.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

DATA_PATH = Path(__file__).with_name("data") / "countries_v2.json"

SECTION_ORDER = (
    ("1_checklist", "Что сделать до поездки"),
    ("2_pay_on_site", "Чем платить на месте: российская карта / QR"),
    ("3_local_wallets_cards", "Местные кошельки и карты"),
    ("4_cash_exchange", "Наличные и обмен"),
    ("5_atms", "Банкоматы и комиссии"),
    ("6_transport", "Транспортная карта"),
    ("7_risks", "Мошенники, 115-ФЗ, что делать при блокировке"),
    ("8_tax_free", "Tax free"),
)
SECTION_KEYS = tuple(key for key, _title in SECTION_ORDER)
SECTION_TITLES = dict(SECTION_ORDER)
SECTION_BY_NUMBER = {str(index): key for index, (key, _title) in enumerate(SECTION_ORDER, start=1)}
NUMBER_BY_SECTION = {key: number for number, key in SECTION_BY_NUMBER.items()}

SUBSECTION_TITLES = {
    "wallets": "Кошельки и пополнение из РФ",
    "local_card": "Местная карта или счёт",
}

ALLOWED_FACT_STATUSES = ("confirmed", "unconfirmed", "outdated")
ON_REQUEST_STATUSES = ("unconfirmed", "outdated")
DATE_VERIFIED = "13.10.2026"
STATUS_WARNING = {
    "unconfirmed": "Не подтверждено",
    "outdated": "Устарело",
}

NOT_FOR_TOURIST_LOCAL_CARD = ("china", "hong_kong", "uae", "turkey")
LOCAL_CARD_NOT_FOR_TOURIST = "не актуально для туриста"

# Kept in the data, hidden until there is a verified fact. Not shown even on request.
TURKEY_FORCE_UNCONFIRMED = (
    "Газпромбанк",
    "Visa/Mastercard банков РФ",
    "ВТБ: TR QR",
    "Сбер: TR QR",
)

INSTRUCTION_SECTION = {
    "mts_tr_qr": "2_pay_on_site",
    "tbank_qr_abroad": "2_pay_on_site",
    "mts_china_wallets": "3_local_wallets_cards",
    "vtb_china_wallets": "3_local_wallets_cards",
    "wechat_pay": "3_local_wallets_cards",
    "alipay": "3_local_wallets_cards",
}
INSTRUCTION_LABELS = {
    "mts_tr_qr": "📋 Мой МТС: оплата по QR",
    "tbank_qr_abroad": "📋 Т-Банк: QR",
    "mts_china_wallets": "📋 Мой МТС: пополнение",
    "vtb_china_wallets": "📋 ВТБ: перевод в Китай",
    "wechat_pay": "📋 WeChat Pay по шагам",
    "alipay": "📋 Alipay по шагам",
}

FACT_FIELDS = (
    "text",
    "status",
    "date_verified",
    "source",
    "needs_owner_check",
    "decision_needed",
    "unknown_zone",
)


def _date_verified(checked_at: Optional[str]) -> str:
    if not checked_at:
        return DATE_VERIFIED
    year, month, day = checked_at.split("-")
    return f"{day}.{month}.{year}"


def normalize_fact(raw: Dict[str, Any]) -> Dict[str, Any]:
    status = raw.get("status")
    if status not in ALLOWED_FACT_STATUSES:
        raise ValueError(f"Unexpected fact status: {status!r} in {raw.get('text', '')[:80]!r}")
    source = raw.get("source")
    return {
        "text": raw["text"],
        "status": status,
        "checked_at": raw.get("checked_at"),
        "date_verified": _date_verified(raw.get("checked_at")),
        "source": source if source else None,
        "source_type": raw.get("source_type"),
        "needs_owner_check": bool(raw.get("needs_owner_check")),
        "decision_needed": raw.get("decision_needed") or None,
        "unknown_zone": raw.get("unknown_zone") or None,
    }


def _normalize_subsection(raw_facts: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "applicable": True,
        "reason": None,
        "facts": [normalize_fact(fact) for fact in raw_facts],
    }


def _load_raw() -> Dict[str, Any]:
    with DATA_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def iter_facts(country: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for section in country["sections"].values():
        yield from section.get("facts") or []
        for subsection in (section.get("subsections") or {}).values():
            yield from subsection.get("facts") or []


def _mark_turkey_unconfirmed(country: Dict[str, Any]) -> None:
    if country["slug"] != "turkey":
        return
    for fact in iter_facts(country):
        if any(marker in fact["text"] for marker in TURKEY_FORCE_UNCONFIRMED):
            fact["status"] = "unconfirmed"


def _apply_local_card_decisions(country: Dict[str, Any]) -> None:
    section = country["sections"]["3_local_wallets_cards"]
    local_card = section["subsections"]["local_card"]
    if country["slug"] in NOT_FOR_TOURIST_LOCAL_CARD:
        local_card["applicable"] = False
        local_card["reason"] = LOCAL_CARD_NOT_FOR_TOURIST
        for fact in local_card["facts"]:
            fact["excluded_from_user_view"] = True
        return
    if country["slug"] == "thailand":
        for fact in local_card["facts"]:
            if "Bangkok Bank" in fact["text"] and "Kasikorn" in fact["text"]:
                fact["hidden_until_verified"] = True


def _build_country(slug: str, raw: Dict[str, Any], instruction_ids: List[str]) -> Dict[str, Any]:
    sections: Dict[str, Any] = {}
    for key, title in SECTION_ORDER:
        raw_section = raw["sections"][key]
        section: Dict[str, Any] = {
            "id": key,
            "title": title,
            "applicable": bool(raw_section.get("applicable", True)),
            "reason": raw_section.get("reason") or None,
            "facts": [normalize_fact(fact) for fact in raw_section.get("facts") or []],
        }
        if "subsections" in raw_section:
            section["subsections"] = {
                name: _normalize_subsection(facts)
                for name, facts in raw_section["subsections"].items()
            }
        sections[key] = section

    country = {
        "schema_version": 2,
        "name": raw["name"],
        "slug": slug,
        "date_verified": DATE_VERIFIED,
        "headline": (
            "По умолчанию здесь только подтверждённые факты. "
            "Непроверенное и устаревшее открывается кнопкой «Показать непроверенное»."
        ),
        "sections": sections,
        "instruction_ids": instruction_ids,
    }
    if raw.get("base"):
        country["base"] = raw["base"]
    _mark_turkey_unconfirmed(country)
    _apply_local_card_decisions(country)
    return country


def _build_instructions(raw_instructions: Dict[str, Any]) -> Dict[str, Any]:
    built: Dict[str, Any] = {}
    for instruction_id, raw in raw_instructions.items():
        steps = []
        for step in raw.get("steps") or []:
            fact = normalize_fact({
                "text": step["text"],
                "status": step["status"],
                "checked_at": step.get("checked_at"),
                "source": step.get("source"),
                "source_type": None,
                "needs_owner_check": step.get("needs_owner_check"),
                "decision_needed": step.get("decision_needed"),
                "unknown_zone": step.get("unknown_zone"),
            })
            fact["n"] = step.get("n")
            fact["stage"] = step.get("stage")
            steps.append(fact)
        built[instruction_id] = {
            "id": instruction_id,
            "service": raw.get("service"),
            "countries": list(raw.get("countries") or []),
            "app": raw.get("app"),
            "provider": raw.get("provider"),
            "status": raw.get("status"),
            "checked_at": raw.get("checked_at"),
            "date_verified": _date_verified(raw.get("checked_at")),
            "sources": list(raw.get("sources") or []),
            "steps": steps,
            "section": INSTRUCTION_SECTION.get(instruction_id),
        }
    return built


def _assemble() -> tuple:
    raw = _load_raw()
    instructions = _build_instructions(raw.get("instructions") or {})
    countries: Dict[str, Any] = {}
    for slug, raw_country in raw["countries"].items():
        instruction_ids = [
            instruction_id
            for instruction_id, instruction in instructions.items()
            if slug in instruction["countries"]
        ]
        countries[slug] = _build_country(slug, raw_country, instruction_ids)
    return raw, countries, instructions


_RAW, _COUNTRIES, INSTRUCTIONS = _assemble()
CHINA_DATA = _COUNTRIES["china"]
HONG_KONG_DATA = _COUNTRIES["hong_kong"]
THAILAND_DATA = _COUNTRIES["thailand"]
UAE_DATA = _COUNTRIES["uae"]
TURKEY_DATA = _COUNTRIES["turkey"]
COUNTRIES_KNOWLEDGE_BASE = {
    "turkey": TURKEY_DATA,
    "china": CHINA_DATA,
    "hong_kong": HONG_KONG_DATA,
    "thailand": THAILAND_DATA,
    "uae": UAE_DATA,
}


def user_visible_fact(fact: Dict[str, Any]) -> bool:
    if fact.get("hidden_until_verified") or fact.get("excluded_from_user_view"):
        return False
    return True


def select_facts(facts: List[Dict[str, Any]], show_unverified: bool) -> List[Dict[str, Any]]:
    chosen = []
    for fact in facts:
        if not user_visible_fact(fact):
            continue
        if fact["status"] == "confirmed" or (show_unverified and fact["status"] in ON_REQUEST_STATUSES):
            chosen.append(fact)
    return chosen


def section_has_unverified(country: Dict[str, Any], section_key: str) -> bool:
    section = country["sections"][section_key]
    pools = [section.get("facts") or []]
    for subsection in (section.get("subsections") or {}).values():
        if subsection.get("applicable", True):
            pools.append(subsection.get("facts") or [])
    for pool in pools:
        for fact in pool:
            if user_visible_fact(fact) and fact["status"] in ON_REQUEST_STATUSES:
                return True
    return False


def format_fact(fact: Dict[str, Any], *, warn: bool = False) -> str:
    """Traveller-facing fact. Internal flags are never included."""
    lines = [fact["text"]]
    if warn and fact["status"] in STATUS_WARNING:
        lines.append(f"⚠️ {STATUS_WARNING[fact['status']]}, проверено {fact['date_verified']}.")
    else:
        lines.append(f"Проверено: {fact['date_verified']}.")
    source = fact.get("source")
    if isinstance(source, str) and source.startswith("http"):
        lines.append(f"Источник: {source}")
    else:
        lines.append("Официальной ссылки нет.")
    return "\n".join(lines)


def _render_fact_blocks(facts: List[Dict[str, Any]], show_unverified: bool) -> List[str]:
    blocks = []
    for fact in select_facts(facts, show_unverified):
        warn = fact["status"] in ON_REQUEST_STATUSES
        blocks.append(format_fact(fact, warn=warn))
    return blocks


def render_section(country: Dict[str, Any], section_key: str, show_unverified: bool = False) -> str:
    section = country["sections"][section_key]
    lines = [f"{section['title']} — {country['name']}"]
    if show_unverified:
        lines.append(
            "⚠️ Непроверенное и устаревшее. Это не подтверждённые правила. "
            "У такого факта есть пометка «не подтверждено» или «устарело» и дата проверки."
        )
    else:
        lines.append("Только подтверждённые факты.")

    if not section["applicable"]:
        lines.append(f"Раздел не применим: {section['reason']}")
        return "\n\n".join(lines)

    blocks = _render_fact_blocks(section.get("facts") or [], show_unverified)
    if blocks:
        lines.extend(blocks)
    elif not section.get("subsections"):
        lines.append("Подтверждённых фактов в этом разделе нет." if not show_unverified else "Дополнительных непроверенных фактов нет.")

    for name, subsection in (section.get("subsections") or {}).items():
        title = SUBSECTION_TITLES.get(name, name)
        lines.append(title)
        if not subsection.get("applicable", True):
            lines.append(subsection.get("reason") or "Не применимо.")
            continue
        sub_blocks = _render_fact_blocks(subsection.get("facts") or [], show_unverified)
        if sub_blocks:
            lines.extend(sub_blocks)
        elif not show_unverified:
            lines.append("Подтверждённых фактов нет.")
        else:
            lines.append("Дополнительных непроверенных фактов нет.")

    return "\n\n".join(lines)


def render_user_facing(country: Dict[str, Any], show_unverified: bool = False) -> str:
    parts = [country["name"], country["headline"]]
    for key, _title in SECTION_ORDER:
        parts.append(render_section(country, key, show_unverified=show_unverified))
    return "\n\n".join(parts)


def render_instruction(instruction_id: str, show_unverified: bool = False) -> str:
    instruction = INSTRUCTIONS[instruction_id]
    lines = [instruction["service"] or instruction_id]
    if show_unverified:
        lines.append(
            "⚠️ Непроверенные шаги. Это не подтверждённая инструкция. "
            "У такого шага есть пометка «не подтверждено» или «устарело» и дата проверки."
        )
    else:
        lines.append("Только подтверждённые шаги.")
    blocks = _render_fact_blocks(instruction.get("steps") or [], show_unverified)
    if blocks:
        lines.extend(blocks)
    elif not show_unverified:
        lines.append("Подтверждённых шагов нет.")
    else:
        lines.append("Дополнительных непроверенных шагов нет.")
    return "\n\n".join(lines)


def instruction_has_unverified(instruction_id: str) -> bool:
    for step in INSTRUCTIONS[instruction_id].get("steps") or []:
        if user_visible_fact(step) and step["status"] in ON_REQUEST_STATUSES:
            return True
    return False


def instructions_for_section(country: Dict[str, Any], section_key: str) -> List[str]:
    found = []
    for instruction_id in country.get("instruction_ids") or []:
        if INSTRUCTION_SECTION.get(instruction_id) == section_key:
            found.append(instruction_id)
    return found


def forum_section_text(country: Optional[Dict[str, Any]] = None) -> str:
    """Old forum button. No quotes and no forum summaries."""
    del country
    return (
        "Сообщения с форумов в справочник не входят и не цитируются. "
        "Они используются только для внутренней сверки."
    )


def _html_source(source: Optional[str]) -> str:
    if isinstance(source, str) and source.startswith("http"):
        url = source.split()[0]
        note = html.escape(source[len(url):].strip())
        link = f'<a href="{html.escape(url, quote=True)}">Источник</a>'
        return f"{link} {note}".strip()
    return "Официальной ссылки нет."


def format_fact_html(fact: Dict[str, Any], *, warn: bool = False) -> str:
    lines = [html.escape(fact["text"])]
    if warn and fact["status"] in STATUS_WARNING:
        lines.append(
            f"⚠️ {html.escape(STATUS_WARNING[fact['status']])}, проверено {html.escape(fact['date_verified'])}."
        )
    else:
        lines.append(f"Проверено: {html.escape(fact['date_verified'])}.")
    lines.append(_html_source(fact.get("source")))
    return "\n".join(lines)


def _html_blocks(facts: List[Dict[str, Any]], show_unverified: bool) -> List[str]:
    blocks = []
    for fact in select_facts(facts, show_unverified):
        blocks.append(format_fact_html(fact, warn=fact["status"] in ON_REQUEST_STATUSES))
    return blocks


def render_section_html(country: Dict[str, Any], section_key: str, show_unverified: bool = False) -> str:
    section = country["sections"][section_key]
    lines = [f"<b>{html.escape(section['title'])}</b> — {html.escape(country['name'])}"]
    if show_unverified:
        lines.append(
            "⚠️ Непроверенное и устаревшее. Это не подтверждённые правила. "
            "У такого факта есть пометка «не подтверждено» или «устарело» и дата проверки."
        )
    else:
        lines.append("Только подтверждённые факты.")
    if not section["applicable"]:
        lines.append(f"Раздел не применим: {html.escape(section['reason'] or '')}")
        return "\n\n".join(lines)
    blocks = _html_blocks(section.get("facts") or [], show_unverified)
    if blocks:
        lines.extend(blocks)
    elif not section.get("subsections"):
        lines.append(
            "Подтверждённых фактов в этом разделе нет."
            if not show_unverified
            else "Дополнительных непроверенных фактов нет."
        )
    for name, subsection in (section.get("subsections") or {}).items():
        lines.append(f"<b>{html.escape(SUBSECTION_TITLES.get(name, name))}</b>")
        if not subsection.get("applicable", True):
            lines.append(html.escape(subsection.get("reason") or "Не применимо."))
            continue
        sub_blocks = _html_blocks(subsection.get("facts") or [], show_unverified)
        if sub_blocks:
            lines.extend(sub_blocks)
        elif not show_unverified:
            lines.append("Подтверждённых фактов нет.")
        else:
            lines.append("Дополнительных непроверенных фактов нет.")
    text = "\n\n".join(lines)
    if len(text) > 4000:
        text = text[:3900] + "\n\n…"
    return text


def render_instruction_html(instruction_id: str, show_unverified: bool = False) -> str:
    instruction = INSTRUCTIONS[instruction_id]
    lines = [f"<b>{html.escape(instruction['service'] or instruction_id)}</b>"]
    if show_unverified:
        lines.append(
            "⚠️ Непроверенные шаги. Это не подтверждённая инструкция. "
            "У такого шага есть пометка «не подтверждено» или «устарело» и дата проверки."
        )
    else:
        lines.append("Только подтверждённые шаги.")
    blocks = _html_blocks(instruction.get("steps") or [], show_unverified)
    if blocks:
        lines.extend(blocks)
    elif not show_unverified:
        lines.append("Подтверждённых шагов нет.")
    else:
        lines.append("Дополнительных непроверенных шагов нет.")
    text = "\n\n".join(lines)
    if len(text) > 4000:
        text = text[:3900] + "\n\n…"
    return text
