"""
Country guides, schema v2 with a trust scale (13.10.2026).

Eight sections in a fixed order. Display thresholds live in config/trust_config.json.
By default travellers see green and yellow zones. Red and black open with
«Показать непроверенное». Gaps are labelled «не исследовано».
Scores, breakdowns, needs_owner_check, decision_needed and unknown_zone stay internal.
Forum summaries are not stored and are not shown.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

# Generated bundle: countries plus scored step-by-step instructions.
# A regeneration replaces this file; display thresholds stay in config/trust_config.json.
DATA_PATH = Path(__file__).with_name("data") / "countries.json"

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

ALLOWED_FACT_STATUSES = ("confirmed", "unconfirmed", "outdated", "outdated_or_refuted", "gap")
FACT_TYPES = ("fact", "advice", "gap")
DATE_VERIFIED = "13.10.2026"
TRUST_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "trust_config.json"


def load_trust_config() -> Dict[str, Any]:
    with TRUST_CONFIG_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def zone_sets(config: Dict[str, Any]) -> tuple:
    """Default zones are those at or above display.default_min. The rest stay behind the button."""
    display = config["display"]
    default_min = display["default_min"]
    default = {zone["name"] for zone in config["zones"] if zone["min"] >= default_min}
    hidden = {zone["name"] for zone in config["zones"] if zone["min"] < default_min}
    hidden.update(display.get("extra_hidden_zones") or [])
    return default, hidden


TRUST_CONFIG = load_trust_config()
DEFAULT_ZONES, HIDDEN_ZONES = zone_sets(TRUST_CONFIG)
GAP_ZONES = set(TRUST_CONFIG["display"].get("gap_zones") or ["gap"])
GAP_LABEL = TRUST_CONFIG["display"]["gap_label"]

INSTRUCTION_SECTION = {
    "mts_tr_qr": "2_pay_on_site",
    "tbank_qr_abroad": "2_pay_on_site",
    "mts_china_wallets": "3_local_wallets_cards",
    "vtb_china_wallets": "3_local_wallets_cards",
    "wechat_pay": "3_local_wallets_cards",
    "alipay": "3_local_wallets_cards",
    "tbc_georgia": "3_local_wallets_cards",
}
INSTRUCTION_LABELS = {
    "mts_tr_qr": "📋 Мой МТС: оплата по QR",
    "tbank_qr_abroad": "📋 Т-Банк: QR",
    "mts_china_wallets": "📋 Мой МТС: пополнение",
    "vtb_china_wallets": "📋 ВТБ: перевод в Китай",
    "wechat_pay": "📋 WeChat Pay по шагам",
    "alipay": "📋 Alipay по шагам",
    "tbc_georgia": "📋 TBC: карта за 1–2 дня",
}

FACT_FIELDS = (
    "text",
    "type",
    "status",
    "zone",
    "score",
    "score_breakdown",
    "date_verified",
    "date_estimated",
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
    fact_type = raw.get("fact_type") or raw.get("type") or "fact"
    if fact_type not in FACT_TYPES:
        raise ValueError(f"Unexpected fact type: {fact_type!r} in {raw.get('text', '')[:80]!r}")
    source = raw.get("source") or None
    if "date_verified" in raw:
        date_verified = raw.get("date_verified") or None
    else:
        date_verified = _date_verified(raw.get("checked_at"))
    breakdown = raw.get("score_breakdown")
    return {
        "text": raw["text"],
        "type": fact_type,
        "fact_type": fact_type,
        "status": status,
        "zone": raw.get("zone"),
        "score": raw.get("score"),
        "score_breakdown": breakdown if isinstance(breakdown, dict) else None,
        "date_verified": date_verified,
        "date_estimated": raw.get("date_estimated"),
        "checked_at": raw.get("checked_at"),
        "source": source,
        "source_type": raw.get("source_type"),
        "source_user_facing": raw.get("source_user_facing", True),
        "source_kind": raw.get("source_kind"),
        "needs_owner_check": bool(raw.get("needs_owner_check")),
        "decision_needed": raw.get("decision_needed") or None,
        "unknown_zone": raw.get("unknown_zone") or None,
        "reason": raw.get("reason"),
        "refuted": bool(raw.get("refuted")),
        "verified_by_us": bool(raw.get("verified_by_us")),
        "status_derived_from": raw.get("status_derived_from"),
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
            "По умолчанию зелёная и жёлтая зоны. "
            "Красная и чёрная открываются кнопкой «Показать непроверенное». "
            "Пробелы в данных подписаны «не исследовано»."
        ),
        "sections": sections,
        "instruction_ids": instruction_ids,
    }
    if raw.get("base"):
        country["base"] = raw["base"]
    return country


def _build_instructions(raw_instructions: Dict[str, Any]) -> Dict[str, Any]:
    built: Dict[str, Any] = {}
    for instruction_id, raw in raw_instructions.items():
        steps = []
        for step in raw.get("steps") or []:
            fact = normalize_fact(step)
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
            "prereq": [item for item in (raw.get("prereq") or []) if isinstance(item, str)],
            "costs": raw.get("costs") if isinstance(raw.get("costs"), str) else None,
            "limits": raw.get("limits") if isinstance(raw.get("limits"), str) else None,
            "risks": [item for item in (raw.get("risks") or []) if isinstance(item, str)],
            "intro": raw.get("intro") if isinstance(raw.get("intro"), str) else None,
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
GEORGIA_DATA = _COUNTRIES["georgia"]
COUNTRIES_KNOWLEDGE_BASE = {
    "turkey": TURKEY_DATA,
    "china": CHINA_DATA,
    "hong_kong": HONG_KONG_DATA,
    "thailand": THAILAND_DATA,
    "uae": UAE_DATA,
    "georgia": GEORGIA_DATA,
}


def user_visible_fact(fact: Dict[str, Any]) -> bool:
    if fact.get("hidden_until_verified") or fact.get("excluded_from_user_view"):
        return False
    return True


def is_gap(fact: Dict[str, Any]) -> bool:
    return fact.get("type") == "gap" or fact.get("zone") in GAP_ZONES


def fact_on_request(fact: Dict[str, Any]) -> bool:
    """Red, black, and other non-default zones. Gaps are not in this bucket."""
    if is_gap(fact):
        return False
    return fact.get("zone") not in DEFAULT_ZONES


def select_facts(facts: List[Dict[str, Any]], show_unverified: bool) -> List[Dict[str, Any]]:
    chosen = []
    for fact in facts:
        if not user_visible_fact(fact):
            continue
        if is_gap(fact) or fact.get("zone") in DEFAULT_ZONES:
            chosen.append(fact)
        elif show_unverified and fact_on_request(fact):
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
            if user_visible_fact(fact) and fact_on_request(fact):
                return True
    return False


def _display_date(value: Optional[str]) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    if len(value) >= 10 and value[4] == "-" and value[7] == "-":
        year, month, day = value[:10].split("-")
        return f"{day}.{month}.{year}"
    return value


_PRIVATE_SOURCE_MARKERS = (
    "t.me/",
    "telegram.me/",
    "telegram.org/",
    "forum.awd.ru",
    "/forum",
)


def public_source_url(fact: Dict[str, Any]) -> Optional[str]:
    """URL safe to show. Forum and Telegram sources stay internal even if flagged."""
    if fact.get("source_user_facing") is False:
        return None
    source = fact.get("source")
    if not isinstance(source, str) or not source.startswith("http"):
        return None
    url = source.split()[0]
    low = url.lower()
    if any(marker in low for marker in _PRIVATE_SOURCE_MARKERS):
        return None
    kind = (fact.get("source_kind") or "").lower()
    source_type = (fact.get("source_type") or "").lower()
    if kind in {"telegram", "forum"}:
        return None
    if "telegram" in source_type or "форум" in source_type or "forum" in source_type:
        return None
    return url


def _source_line(fact: Dict[str, Any]) -> str:
    url = public_source_url(fact)
    if url:
        return f"Источник: {url}"
    return "Официальной ссылки нет."


def format_fact(fact: Dict[str, Any], *, warn: bool = False) -> str:
    """Traveller-facing line. Scores, breakdowns and internal flags stay out."""
    if is_gap(fact):
        text = fact["text"]
        if GAP_LABEL not in text.lower():
            return f"{GAP_LABEL}: {text}"
        return text
    lines = [fact["text"]]
    shown_date = _display_date(fact.get("date_verified"))
    if warn:
        when = f", проверено {shown_date}" if shown_date else ""
        lines.append(f"⚠️ Непроверено{when}.")
    elif shown_date:
        estimate = " (дата ориентировочная)" if fact.get("date_estimated") else ""
        lines.append(f"Проверено: {shown_date}{estimate}.")
    lines.append(_source_line(fact))
    return "\n".join(lines)


def _render_fact_blocks(facts: List[Dict[str, Any]], show_unverified: bool) -> List[str]:
    blocks = []
    for fact in select_facts(facts, show_unverified):
        blocks.append(format_fact(fact, warn=fact_on_request(fact)))
    return blocks


def render_section(country: Dict[str, Any], section_key: str, show_unverified: bool = False) -> str:
    section = country["sections"][section_key]
    lines = [f"{section['title']} — {country['name']}"]
    if show_unverified:
        lines.append(
            "⚠️ Красная и чёрная зоны. Это не проверенные правила. "
            "У такого факта есть пометка «непроверено» и дата, если она известна."
        )
    else:
        lines.append("Зелёная и жёлтая зоны. Пробелы подписаны «не исследовано».")

    if not section["applicable"]:
        lines.append(f"Раздел не применим: {section['reason']}")
        return _with_checklist_offer(section_key, "\n\n".join(lines), as_html=False)

    blocks = _render_fact_blocks(section.get("facts") or [], show_unverified)
    if blocks:
        lines.extend(blocks)
    elif not section.get("subsections"):
        lines.append("В зелёной и жёлтой зоне фактов нет." if not show_unverified else "Дополнительных непроверенных фактов нет.")

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
            lines.append("В зелёной и жёлтой зоне фактов нет.")
        else:
            lines.append("Дополнительных непроверенных фактов нет.")

    return _with_checklist_offer(section_key, "\n\n".join(lines), as_html=False)


def render_user_facing(country: Dict[str, Any], show_unverified: bool = False) -> str:
    parts = [country["name"], country["headline"]]
    for key, _title in SECTION_ORDER:
        parts.append(render_section(country, key, show_unverified=show_unverified))
    return "\n\n".join(parts)


def _instruction_preamble(instruction: Dict[str, Any]) -> List[str]:
    """User-facing intro and prerequisites. Internal status strings stay out."""
    blocks: List[str] = []
    intro = instruction.get("intro")
    if intro:
        blocks.append(intro)
    prereq = instruction.get("prereq") or []
    if prereq:
        blocks.append("До начала:\n" + "\n".join(f"• {item}" for item in prereq))
    return blocks


def _instruction_footer(instruction: Dict[str, Any]) -> List[str]:
    blocks: List[str] = []
    if instruction.get("costs"):
        blocks.append(f"Комиссия и курс: {instruction['costs']}")
    if instruction.get("limits"):
        blocks.append(f"Лимиты: {instruction['limits']}")
    risks = instruction.get("risks") or []
    if risks:
        blocks.append("На что смотреть:\n" + "\n".join(f"• {item}" for item in risks))
    return blocks


def render_instruction(instruction_id: str, show_unverified: bool = False) -> str:
    instruction = INSTRUCTIONS[instruction_id]
    lines = [instruction["service"] or instruction_id]
    if show_unverified:
        lines.append(
            "⚠️ Красная и чёрная зоны. Это не проверенные шаги. "
            "У такого шага есть пометка «непроверено» и дата, если она известна."
        )
    else:
        lines.append("Зелёная и жёлтая зоны.")
    lines.extend(_instruction_preamble(instruction))
    blocks = _render_fact_blocks(instruction.get("steps") or [], show_unverified)
    if blocks:
        lines.extend(blocks)
    elif not show_unverified:
        lines.append("В зелёной и жёлтой зоне шагов нет.")
    else:
        lines.append("Дополнительных непроверенных шагов нет.")
    lines.extend(_instruction_footer(instruction))
    return "\n\n".join(lines)


def instruction_has_unverified(instruction_id: str) -> bool:
    for step in INSTRUCTIONS[instruction_id].get("steps") or []:
        if user_visible_fact(step) and fact_on_request(step):
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


def _html_source(fact: Dict[str, Any]) -> str:
    url = public_source_url(fact)
    if not url:
        return "Официальной ссылки нет."
    source = fact.get("source") or ""
    note = html.escape(source[len(url):].strip()) if isinstance(source, str) else ""
    link = f'<a href="{html.escape(url, quote=True)}">Источник</a>'
    return f"{link} {note}".strip()


def format_fact_html(fact: Dict[str, Any], *, warn: bool = False) -> str:
    if is_gap(fact):
        text = fact["text"]
        if GAP_LABEL not in text.lower():
            text = f"{GAP_LABEL}: {text}"
        return html.escape(text)
    lines = [html.escape(fact["text"])]
    shown_date = _display_date(fact.get("date_verified"))
    if warn:
        when = f", проверено {html.escape(shown_date)}" if shown_date else ""
        lines.append(f"⚠️ Непроверено{when}.")
    elif shown_date:
        estimate = " (дата ориентировочная)" if fact.get("date_estimated") else ""
        lines.append(f"Проверено: {html.escape(shown_date)}{estimate}.")
    lines.append(_html_source(fact))
    return "\n".join(lines)


def _html_blocks(facts: List[Dict[str, Any]], show_unverified: bool) -> List[str]:
    blocks = []
    for fact in select_facts(facts, show_unverified):
        blocks.append(format_fact_html(fact, warn=fact_on_request(fact)))
    return blocks


def render_section_html(country: Dict[str, Any], section_key: str, show_unverified: bool = False) -> str:
    section = country["sections"][section_key]
    lines = [f"<b>{html.escape(section['title'])}</b> — {html.escape(country['name'])}"]
    if show_unverified:
        lines.append(
            "⚠️ Красная и чёрная зоны. Это не проверенные правила. "
            "У такого факта есть пометка «непроверено» и дата, если она известна."
        )
    else:
        lines.append("Зелёная и жёлтая зоны. Пробелы подписаны «не исследовано».")
    if not section["applicable"]:
        lines.append(f"Раздел не применим: {html.escape(section['reason'] or '')}")
        return _with_checklist_offer(section_key, "\n\n".join(lines), as_html=True)
    blocks = _html_blocks(section.get("facts") or [], show_unverified)
    if blocks:
        lines.extend(blocks)
    elif not section.get("subsections"):
        lines.append(
            "В зелёной и жёлтой зоне фактов нет."
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
            lines.append("В зелёной и жёлтой зоне фактов нет.")
        else:
            lines.append("Дополнительных непроверенных фактов нет.")
    return _with_checklist_offer(section_key, "\n\n".join(lines), as_html=True)


def _with_checklist_offer(section_key: str, text: str, *, as_html: bool) -> str:
    """Travel insurance is a partner offer, not a verified country fact."""
    if section_key != "1_checklist":
        return text
    from database.partners import checklist_offer_html, checklist_offer_text

    extra = checklist_offer_html() if as_html else checklist_offer_text()
    if not extra:
        return text
    return f"{text}\n\n{extra}"


def render_instruction_html(instruction_id: str, show_unverified: bool = False) -> str:
    instruction = INSTRUCTIONS[instruction_id]
    lines = [f"<b>{html.escape(instruction['service'] or instruction_id)}</b>"]
    if show_unverified:
        lines.append(
            "⚠️ Красная и чёрная зоны. Это не проверенные шаги. "
            "У такого шага есть пометка «непроверено» и дата, если она известна."
        )
    else:
        lines.append("Зелёная и жёлтая зоны.")
    for block in _instruction_preamble(instruction):
        lines.append(html.escape(block))
    blocks = _html_blocks(instruction.get("steps") or [], show_unverified)
    if blocks:
        lines.extend(blocks)
    elif not show_unverified:
        lines.append("В зелёной и жёлтой зоне шагов нет.")
    else:
        lines.append("Дополнительных непроверенных шагов нет.")
    for block in _instruction_footer(instruction):
        lines.append(html.escape(block))
    return "\n\n".join(lines)


TELEGRAM_MESSAGE_LIMIT = 4096


def split_telegram_html(text: str, limit: int = 4000) -> List[str]:
    """Split a message on paragraph boundaries so each part fits Telegram."""
    if len(text) <= limit:
        return [text or ""]
    pages: List[str] = []
    current = ""

    def flush_piece(piece: str) -> None:
        if piece:
            pages.append(piece)

    for part in text.split("\n\n"):
        if not part:
            continue
        candidate = part if not current else f"{current}\n\n{part}"
        if len(candidate) <= limit:
            current = candidate
            continue
        flush_piece(current)
        current = ""
        if len(part) <= limit:
            current = part
            continue
        line_buf = ""
        for line in part.split("\n"):
            line_candidate = line if not line_buf else f"{line_buf}\n{line}"
            if len(line_candidate) <= limit:
                line_buf = line_candidate
                continue
            flush_piece(line_buf)
            line_buf = ""
            while len(line) > limit:
                flush_piece(line[:limit])
                line = line[limit:]
            line_buf = line
        current = line_buf
    flush_piece(current)
    labeled: List[str] = []
    total = len(pages)
    if total <= 1:
        return pages or [""]
    for index, page in enumerate(pages, start=1):
        prefix = f"{index}/{total}\n\n"
        room = TELEGRAM_MESSAGE_LIMIT - len(prefix)
        labeled.append(prefix + page[:room])
    return labeled


def section_html_pages(country: Dict[str, Any], section_key: str, show_unverified: bool = False) -> List[str]:
    return split_telegram_html(render_section_html(country, section_key, show_unverified=show_unverified))


def instruction_html_pages(instruction_id: str, show_unverified: bool = False) -> List[str]:
    return split_telegram_html(render_instruction_html(instruction_id, show_unverified=show_unverified))
