"""Idempotent rows for guide countries, guide facts, and visa rules.

Zone model is the 24.11.2026 rule (official source, our measurement,
unconfirmed, max_zone, explicit risk). It does not use the point formula
in config/trust_config.json.

Bank names in payment wording are generalized to «issuer + payment system»
in the public ``fact`` text. The original object, including the original
text, is kept in ``legacy``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from database.knowledge_base import (
    INSTRUCTION_SECTION,
    _PRIVATE_SOURCE_MARKERS,
    public_source_url,
)

ROOT = Path(__file__).resolve().parents[1]
COUNTRIES_PATH = ROOT / "database" / "data" / "countries.json"
VISA_PATH = ROOT / "database" / "data" / "visa_regimes.json"
BOX_PATH = ROOT / "database" / "data" / "box_only_new_facts.json"

DISCLAIMER = "Правила меняются, сверьтесь перед вылетом"
VISA_CITIZENSHIP = "RU"
VISA_RULE_TYPE = "entry"

GUIDE_COUNTRY_SLUGS = ("china", "hong_kong", "thailand", "uae", "turkey", "georgia")
LEGACY_NOT_IN_GUIDE = ("armenia", "egypt", "kazakhstan")

# Display name, iso2, in_guide. Names are used only when the slug is inserted.
COUNTRY_ROWS: Tuple[Tuple[str, str, str, bool], ...] = (
    ("china", "Китай", "CN", True),
    ("hong_kong", "Гонконг", "HK", True),
    ("thailand", "Таиланд", "TH", True),
    ("uae", "ОАЭ", "AE", True),
    ("turkey", "Турция", "TR", True),
    ("georgia", "Грузия", "GE", True),
    ("armenia", "Армения", "AM", False),
    ("egypt", "Египет", "EG", False),
    ("kazakhstan", "Казахстан", "KZ", False),
    ("vietnam", "Вьетнам", "VN", False),
    ("indonesia", "Индонезия", "ID", False),
    ("india", "Индия", "IN", False),
    ("uzbekistan", "Узбекистан", "UZ", False),
)

VISA_SLUGS = {
    "China": "china",
    "Hong Kong": "hong_kong",
    "Thailand": "thailand",
    "Turkey": "turkey",
    "Georgia": "georgia",
    "UAE": "uae",
    "Vietnam": "vietnam",
    "Indonesia (Bali)": "indonesia",
    "India": "india",
    "Egypt": "egypt",
    "Uzbekistan": "uzbekistan",
}

# Canonical issuer, pattern against the original wording.
ISSUER_PATTERNS: Tuple[Tuple[str, str], ...] = (
    ("Центр-инвест", r"Центр-инвест"),
    ("Инго", r"Инго(?:\s+Банк)?"),
    ("Газпромбанк", r"Газпромбанк"),
    ("РСХБ", r"РСХБ|Россельхозбанк"),
    ("АТБ", r"АТБ"),
    ("Т-Банк", r"Т-Банк|Т‑Банк|Тинькофф"),
    ("ВТБ", r"ВТБ"),
    ("МТС", r"МТС"),
    ("TBC", r"\bTBC\b"),
    ("Сбер", r"\bСбер(?:банк)?\b"),
    ("BoG", r"\bBoG\b|Bank of Georgia"),
)

SYSTEM_PATTERNS: Tuple[Tuple[str, str], ...] = (
    ("UnionPay", r"UnionPay"),
    ("Visa", r"\bVisa\b|\bVISA\b"),
    ("Mastercard", r"Mastercard"),
    ("Мир", r"«Мир»|(?<![А-Яа-яA-Za-z])Мир(?![А-Яа-яA-Za-z])"),
    ("QR", r"\bQR\b"),
    ("SWIFT", r"SWIFT"),
    ("Alipay", r"Alipay"),
    ("WeChat Pay", r"WeChat"),
    ("Apple Pay", r"Apple Pay"),
    ("Google Pay", r"Google Pay"),
    ("Nihao China", r"Nihao"),
)

INSTRUCTION_PAYMENT_SYSTEM = {
    "mts_tr_qr": "QR",
    "tbank_qr_abroad": "QR",
    "mts_china_wallets": "WeChat Pay, Alipay",
    "vtb_china_wallets": "WeChat Pay, Alipay",
    "wechat_pay": "WeChat Pay",
    "alipay": "Alipay",
    "tbc_georgia": "Visa",
}

# Sentences where a mechanical swap would hide a contrast between issuers.
_EXACT_PUBLIC: Dict[str, str] = {
    "Привязка: по АТБ один отзыв, по РСХБ данные противоречат друг другу.": (
        "Привязка карт UnionPay банков РФ: по одному эмитенту один отзыв, по другому данные противоречат."
    ),
    "АТБ UnionPay привязывается и к Alipay, и к WeChat Pay (единственная из карт российских банков, по данным канала); Центр-инвест UnionPay — только к Alipay.": (
        "Карты UnionPay банков РФ: одна привязывается и к Alipay, и к WeChat Pay, другая — только к Alipay."
    ),
    "Оплата по QR российскими банками в Грузии — официальных сведений не найдено (МТС, ВТБ, Т-Банк Грузию не указывают).": (
        "Оплата по QR из банков РФ в Грузии — официальных сведений не найдено (эти эмитенты Грузию не указывают)."
    ),
}

# Longest phrases first. Bank tokens become a generic issuer.
_PHRASE_SUBS: Tuple[Tuple[str, str], ...] = (
    (r"UnionPay\s+АТБ\s*/\s*РСХБ", "карты UnionPay банков РФ"),
    (r"UnionPay\s+РСХБ\s*/\s*АТБ", "карты UnionPay банков РФ"),
    (r"АТБ\s*/\s*РСХБ", "банков РФ"),
    (r"РСХБ\s*/\s*АТБ", "банков РФ"),
    (r"АТБ\s+и\s+РСХБ", "банки РФ"),
    (r"МТС,\s*ВТБ,\s*Т-Банк", "банки РФ"),
    (r"TBC\s*/\s*BoG", "банка в стране пребывания"),
    (r"из ВТБ Онлайн", "из приложения банка РФ"),
    (r"«Мой МТС»", "приложение банка РФ"),
    (r"Мой МТС", "приложение банка РФ"),
    (r"ВТБ Онлайн", "приложение банка РФ"),
    (r"курс Т-Банка", "курс банка РФ"),
    (r"курс МТС", "курс банка РФ"),
    (r"мобильный счёт МТС", "мобильный счёт банка РФ"),
    (r"со счёта МТС", "со счёта банка РФ"),
    (r"счёта МТС", "счёта банка РФ"),
    (r"абоненты МТС", "клиенты банка РФ"),
    (r"на странице ВТБ", "на странице банка РФ"),
    (r"список стран ВТБ", "список стран банка РФ"),
    (r"в официальном списке отделений TBC", "в официальном списке отделений банка в стране пребывания"),
    (r"на сайте TBC", "на сайте банка в стране пребывания"),
    (r"Инго Банк", "банк РФ"),
    (r"Газпромбанка", "банка РФ"),
    (r"Газпромбанк", "банк РФ"),
    (r"Центр-инвест", "банк РФ"),
    (r"Россельхозбанк", "банк РФ"),
    (r"Т-Банка", "банка РФ"),
    (r"Т-Банк", "банк РФ"),
    (r"Тинькофф", "банк РФ"),
    (r"РСХБ", "банк РФ"),
    (r"АТБ", "банк РФ"),
    (r"ВТБ", "банк РФ"),
    (r"(?<![А-Яа-яA-Za-z])МТС(?![А-Яа-яA-Za-z])", "банк РФ"),
    (r"(?<![А-Яа-яA-Za-z])Сбербанк(?![А-Яа-яA-Za-z])", "банк РФ"),
    (r"(?<![А-Яа-яA-Za-z])Сбер(?![А-Яа-яA-Za-z])", "банк РФ"),
    (r"TBC Bank", "банк в стране пребывания"),
    (r"«TBC Card»", "«карта банка в стране пребывания»"),
    (r"TBC Card", "карта банка в стране пребывания"),
    (r"Приложения TBC", "Приложения банка в стране пребывания"),
    (r"приложения TBC", "приложения банка в стране пребывания"),
    (r"приложение TBC", "приложение банка в стране пребывания"),
    (r"приложении TBC", "приложении банка в стране пребывания"),
    (r"в отделение TBC", "в отделение банка в стране пребывания"),
    (r"в отделении TBC", "в отделении банка в стране пребывания"),
    (r"отделение TBC", "отделение банка в стране пребывания"),
    (r"банкоматах TBC", "банкоматах банка в стране пребывания"),
    (r"банкомате TBC", "банкомате банка в стране пребывания"),
    (r"банкомат TBC", "банкомат банка в стране пребывания"),
    (r"терминалах TBC", "терминалах банка в стране пребывания"),
    (r"внутри TBC", "внутри банка в стране пребывания"),
    (r"из TBC", "из банка в стране пребывания"),
    (r"на TBC", "на карту банка в стране пребывания"),
    (r"картой TBC", "картой банка в стране пребывания"),
    (r"Карта TBC", "Карта банка в стране пребывания"),
    (r"карта TBC", "карта банка в стране пребывания"),
    (r"карты TBC", "карты банка в стране пребывания"),
    (r"карту TBC", "карту банка в стране пребывания"),
    (r"номер карты TBC", "номер карты банка в стране пребывания"),
    (r"\bTBC\b", "банк в стране пребывания"),
    (r"\bBoG\b", "банк в стране пребывания"),
)

_POLISH_SUBS: Tuple[Tuple[str, str], ...] = (
    (r"банк РФ\s+UnionPay", "карты UnionPay банков РФ"),
    (r"UnionPay\s+банк РФ", "карты UnionPay банков РФ"),
    (r"карты UnionPay банков РФ\s+банков РФ", "карты UnionPay банков РФ"),
    (r"карты карты UnionPay", "карты UnionPay"),
    (r"карты UnionPay банков РФ привязывается", "Карты UnionPay банков РФ привязываются"),
    (r"^карты UnionPay банков РФ,", "Карты UnionPay банков РФ:"),
    (r"Привязка карты UnionPay", "Привязка карт UnionPay"),
    (r"в банкоматах банк РФ", "в банкоматах эмитента"),
    (r"в банкоматах банка РФ", "в банкоматах эмитента"),
    (r"банк РФ\s+банк РФ", "банк РФ"),
    (r"банка РФ\s+банка РФ", "банка РФ"),
    (r"банков РФ\s+банков РФ", "банков РФ"),
    (r"банк в стране пребывания\s+банк в стране пребывания", "банк в стране пребывания"),
    (r"^банк РФ:\s*оплата по QR", "Оплата по QR из банков РФ"),
    (r"Оплата по QR из банков РФ в Китае из приложения банка РФ", "Оплата по QR из банков РФ в Китае, в приложении банка"),
    (r"^банк РФ:\s*QR\b", "Оплата по QR из банков РФ:"),
    (r"^банк РФ:\s*в Турции QR не работает", "Оплата по QR из банков РФ: в Турции не работает"),
    (r"^банк РФ:\s*TR QR", "Оплата по QR из банков РФ: TR QR"),
    (r"^банк РФ поддерживает оплату по TR QR", "Оплата по QR из банков РФ: заявлена поддержка TR QR"),
    (r"^банк РФ:\s*перевод", "Переводы из банков РФ:"),
    (r"^банк РФ:\s*Платежи", "Переводы из банков РФ: Платежи"),
    (r"^Пополнение через банк РФ по номеру", "Переводы из банков РФ по номеру"),
    (r"^Перевод с банка РФ", "Переводы из банков РФ"),
    (r"^банк РФ\s*→", "Переводы из банков РФ →"),
    (r"^банк в стране пребывания:\s*карту Visa", "Карта Visa банка в стране пребывания:"),
    (r"Тариф карта банка", "Тариф карты банка"),
    (r"При подключении карта банка", "При подключении карты банка"),
    (r"банк РФ заявляет", "эмитент заявляет"),
    (r"пришёл за секунды", "приходят за секунды"),
    (r"\s{2,}", " "),
    (r"\s+([,.;:])", r"\1"),
    (r"\(\s+", "("),
    (r"\s+\)", ")"),
)


def _load(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def detect_issuers(text: str) -> List[str]:
    found: List[str] = []
    for name, pattern in ISSUER_PATTERNS:
        if re.search(pattern, text):
            found.append(name)
    return found


def detect_systems(text: str) -> List[str]:
    found: List[str] = []
    for name, pattern in SYSTEM_PATTERNS:
        if re.search(pattern, text):
            found.append(name)
    return found


def _polish(text: str) -> str:
    for pattern, repl in _POLISH_SUBS:
        text = re.sub(pattern, repl, text)
    text = text.strip()
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    return text


def generalize_bank_wording(
    text: str,
    *,
    instruction_id: Optional[str] = None,
) -> Tuple[str, Optional[str], Optional[str]]:
    """Return public text, issuer, payment_system.

    When the original names a specific bank, the public text keeps the
    conditions but speaks about the issuer and the payment system. The
    caller stores the untouched original in ``legacy``.
    """
    issuers = detect_issuers(text)
    systems = detect_systems(text)
    if not issuers:
        return text, None, None
    if text in _EXACT_PUBLIC:
        rewritten = _EXACT_PUBLIC[text]
    else:
        rewritten = text
        for pattern, repl in _PHRASE_SUBS:
            rewritten = re.sub(pattern, repl, rewritten)
        rewritten = _polish(rewritten)
    if systems:
        payment: Optional[str] = ", ".join(systems)
    elif instruction_id and INSTRUCTION_PAYMENT_SYSTEM.get(instruction_id):
        payment = INSTRUCTION_PAYMENT_SYSTEM[instruction_id]
    elif re.search(r"\bперевод|пополнение из|пополнение через", text, re.IGNORECASE):
        payment = "перевод"
    else:
        payment = None
    if payment is None and rewritten.lower().startswith("переводы из банков"):
        payment = "перевод"
    return rewritten, ", ".join(issuers), payment


def source_is_official(fact: Dict[str, Any]) -> bool:
    kind = (fact.get("source_kind") or "").strip().lower()
    source_type = (fact.get("source_type") or "").strip().lower()
    return kind == "official" or source_type == "official"


def _explicit_risk(fact: Dict[str, Any], official: bool) -> bool:
    """Risk, contradiction, or closure that is not an official confirmation."""
    if fact.get("refuted") is True or fact.get("contradicted_by_own") is True:
        return True
    if (fact.get("agreement") or "").lower() == "conflict" and not official:
        return True
    source_type = (fact.get("source_type") or "").lower()
    if "противореч" in source_type and not official:
        return True
    text = (fact.get("text") or "").lower()
    if not official and any(token in text for token in ("закрывается", "закрыт", "закрытие")):
        return True
    return False


def assign_zone_status(fact: Dict[str, Any]) -> Tuple[str, str]:
    """User zone and lifecycle status. Not the point-score formula."""
    raw_status = fact.get("status")
    fact_type = fact.get("fact_type") or fact.get("type")
    raw_zone = fact.get("zone")
    is_gap = raw_status == "gap" or fact_type == "gap" or raw_zone == "gap"
    official = source_is_official(fact)
    risk = _explicit_risk(fact, official)
    max_zone = fact.get("max_zone")

    if is_gap:
        status = "gap"
    elif raw_status == "outdated_or_refuted" or fact.get("refuted") is True:
        status = "refuted" if fact.get("refuted") is True else "outdated"
    else:
        status = "active"

    if max_zone == "red" or risk:
        zone = "red"
    elif is_gap:
        zone = "yellow"
    elif official and raw_status == "confirmed" and max_zone != "red":
        zone = "green"
    else:
        zone = "yellow"

    if status == "gap" and zone == "green":
        zone = "yellow"
    return zone, status


def _checked_at(fact: Dict[str, Any], fallback: Optional[str] = None) -> str:
    for key in ("checked_at", "source_date"):
        value = fact.get(key)
        if isinstance(value, str) and len(value) >= 10 and value[4] == "-":
            return value[:10]
    verified = fact.get("date_verified")
    if isinstance(verified, str) and len(verified) >= 10 and verified[2] == ".":
        day, month, year = verified[:10].split(".")
        return f"{year}-{month}-{day}"
    if fallback:
        return fallback[:10]
    raise ValueError("fact has no checked_at")


def _topic_for_section(section_key: str) -> str:
    return section_key


def _iter_country_facts(raw: Dict[str, Any]) -> Iterable[Tuple[str, str, str, Dict[str, Any]]]:
    for slug, country in raw["countries"].items():
        for section_key, section in country["sections"].items():
            for index, fact in enumerate(section.get("facts") or []):
                yield slug, section_key, f"facts[{index}]", fact
            for sub_name, sub in (section.get("subsections") or {}).items():
                facts = sub if isinstance(sub, list) else (sub.get("facts") or [])
                for index, fact in enumerate(facts):
                    yield slug, section_key, f"subsections.{sub_name}[{index}]", fact


def _legacy(original: Dict[str, Any], **extra: Any) -> Dict[str, Any]:
    payload = {"original_text": original.get("text"), "original": original}
    payload.update(extra)
    return payload


def _fact_row(
    *,
    source_key: str,
    country_slug: str,
    topic: str,
    original: Dict[str, Any],
    instruction_id: Optional[str] = None,
    step_n: Optional[int] = None,
    checked_fallback: Optional[str] = None,
    extra_legacy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    text = original["text"]
    public_text, issuer, payment_system = generalize_bank_wording(
        text, instruction_id=instruction_id
    )
    zone, status = assign_zone_status(original)
    legacy = _legacy(original, source_key=source_key)
    if extra_legacy:
        legacy.update(extra_legacy)
    return {
        "source_key": source_key,
        "country_slug": country_slug,
        "topic": topic,
        "fact": public_text,
        "zone": zone,
        "status": status,
        "source_url": public_source_url(original),
        "source_type": original.get("source_type") or original.get("source_kind") or None,
        "source_is_official": source_is_official(original),
        "checked_at": _checked_at(original, checked_fallback),
        "verified_by": "owner" if original.get("verified_by_us") else None,
        "max_zone": original.get("max_zone") or None,
        "needs_owner_check": bool(original.get("needs_owner_check")),
        "decision_needed": original.get("decision_needed") or None,
        "unknown_zone": original.get("unknown_zone") or None,
        "instruction_id": instruction_id,
        "step_n": step_n,
        "issuer": issuer,
        "payment_system": payment_system,
        "legacy": legacy,
    }


def build_guide_fact_rows(
    countries: Optional[Dict[str, Any]] = None,
    box_facts: Optional[Sequence[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    raw = countries if countries is not None else _load(COUNTRIES_PATH)
    box = list(box_facts) if box_facts is not None else _load(BOX_PATH)
    rows: List[Dict[str, Any]] = []
    for slug, section_key, locator, fact in _iter_country_facts(raw):
        rows.append(
            _fact_row(
                source_key=f"guide:{slug}:{section_key}:{locator}",
                country_slug=slug,
                topic=_topic_for_section(section_key),
                original=fact,
                extra_legacy={"path": f"{slug}.{section_key}.{locator}"},
            )
        )
    for instruction_id, instruction in (raw.get("instructions") or {}).items():
        countries_for = list(instruction.get("countries") or [])
        country_slug = countries_for[0]
        topic = INSTRUCTION_SECTION[instruction_id]
        for step in instruction.get("steps") or []:
            step_n = int(step["n"])
            rows.append(
                _fact_row(
                    source_key=f"step:{instruction_id}:{step_n}",
                    country_slug=country_slug,
                    topic=topic,
                    original=step,
                    instruction_id=instruction_id,
                    step_n=step_n,
                    checked_fallback=instruction.get("checked_at"),
                    extra_legacy={
                        "instruction_id": instruction_id,
                        "service": instruction.get("service"),
                    },
                )
            )
    for item in box:
        fact = item["fact"]
        path = item["path"]
        rows.append(
            _fact_row(
                source_key=f"box:{path}",
                country_slug=item["country"],
                topic=path.split(".", 1)[1].split(".", 1)[0],
                original=fact,
                extra_legacy={"path": path, "box_only": True},
            )
        )
    keys = [row["source_key"] for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate guide fact source_key")
    return rows


def build_visa_rows(visa_rules: Optional[Sequence[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    raw = list(visa_rules) if visa_rules is not None else _load(VISA_PATH)
    rows: List[Dict[str, Any]] = []
    for item in raw:
        slug = VISA_SLUGS[item["country"]]
        zone = item["status"]
        if zone not in {"green", "yellow", "red"}:
            raise ValueError(f"unexpected visa zone for {item['country']}: {zone}")
        source = item.get("source_url")
        source_fact = {
            "source": source,
            "source_user_facing": True,
            "source_kind": "official" if item.get("source_is_official") else "media",
            "source_type": "official" if item.get("source_is_official") else "secondary",
        }
        rows.append(
            {
                "citizenship": VISA_CITIZENSHIP,
                "country_slug": slug,
                "rule_type": VISA_RULE_TYPE,
                "country": item["country"],
                "regime_type": item["regime_type"],
                "max_stay_days": item.get("max_stay_days"),
                "day_counting": item.get("day_counting"),
                "allowed_purposes": list(item.get("allowed_purposes") or []),
                "regime_expiry_or_trial_end": item.get("regime_expiry_or_trial_end"),
                "user_wording_ru": item["user_wording_ru"],
                "source_url": public_source_url(source_fact),
                "source_is_official": bool(item.get("source_is_official")),
                "zone": zone,
                "status": "active",
                "last_checked": item["last_checked"],
                "notes": item.get("notes"),
                "disclaimer": DISCLAIMER,
            }
        )
    return rows


def private_marker_in_url(url: Optional[str]) -> bool:
    if not url:
        return False
    low = url.lower()
    return any(marker in low for marker in _PRIVATE_SOURCE_MARKERS)


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


_FACT_COLUMNS = (
    "source_key",
    "country_slug",
    "topic",
    "fact",
    "zone",
    "status",
    "source_url",
    "source_type",
    "source_is_official",
    "checked_at",
    "verified_by",
    "max_zone",
    "needs_owner_check",
    "decision_needed",
    "unknown_zone",
    "instruction_id",
    "step_n",
    "issuer",
    "payment_system",
    "legacy",
)

_VISA_COLUMNS = (
    "citizenship",
    "country_slug",
    "rule_type",
    "country",
    "regime_type",
    "max_stay_days",
    "day_counting",
    "allowed_purposes",
    "regime_expiry_or_trial_end",
    "user_wording_ru",
    "source_url",
    "source_is_official",
    "zone",
    "status",
    "last_checked",
    "notes",
    "disclaimer",
)


def _insert_facts(rows: Sequence[Dict[str, Any]]) -> str:
    columns = ", ".join(_FACT_COLUMNS)
    updates = ",\n    ".join(
        f"{column} = EXCLUDED.{column}" for column in _FACT_COLUMNS if column != "source_key"
    )
    chunks: List[str] = []
    batch = 40
    for start in range(0, len(rows), batch):
        values = []
        for row in rows[start : start + batch]:
            literals = []
            for column in _FACT_COLUMNS:
                value = row[column]
                if column in {"checked_at"} and value is not None:
                    literals.append(sql_literal(value) + "::date")
                else:
                    literals.append(sql_literal(value))
            values.append("(" + ", ".join(literals) + ")")
        chunks.append(
            "INSERT INTO public.guide_facts (\n    "
            + columns
            + "\n) VALUES\n"
            + ",\n".join(values)
            + "\nON CONFLICT (source_key) DO UPDATE SET\n    "
            + updates
            + ",\n    updated_at = now();"
        )
    return "\n\n".join(chunks)


def _insert_visas(rows: Sequence[Dict[str, Any]]) -> str:
    columns = ", ".join(_VISA_COLUMNS)
    updates = ",\n    ".join(
        f"{column} = EXCLUDED.{column}"
        for column in _VISA_COLUMNS
        if column not in {"citizenship", "country_slug", "rule_type"}
    )
    values = []
    for row in rows:
        literals = []
        for column in _VISA_COLUMNS:
            value = row[column]
            if column in {"last_checked", "regime_expiry_or_trial_end"} and value is not None:
                literals.append(sql_literal(value) + "::date")
            else:
                literals.append(sql_literal(value))
        values.append("(" + ", ".join(literals) + ")")
    return (
        "INSERT INTO public.visa_rules (\n    "
        + columns
        + "\n) VALUES\n"
        + ",\n".join(values)
        + "\nON CONFLICT (citizenship, country_slug, rule_type) DO UPDATE SET\n    "
        + updates
        + ",\n    updated_at = now();"
    )


def _insert_countries() -> str:
    values = []
    for slug, name, iso2, in_guide in COUNTRY_ROWS:
        values.append(
            "("
            + ", ".join(
                [
                    sql_literal(name),
                    sql_literal(slug),
                    sql_literal(iso2),
                    "TRUE" if in_guide else "FALSE",
                ]
            )
            + ")"
        )
    return (
        "INSERT INTO public.countries (name, slug, iso2, in_guide)\nVALUES\n"
        + ",\n".join(values)
        + "\nON CONFLICT (slug) DO UPDATE SET\n"
        + "    iso2 = EXCLUDED.iso2,\n"
        + "    in_guide = EXCLUDED.in_guide,\n"
        + "    updated_at = now();\n"
    )


def render_seed_sql(
    fact_rows: Optional[Sequence[Dict[str, Any]]] = None,
    visa_rows: Optional[Sequence[Dict[str, Any]]] = None,
) -> str:
    facts = list(fact_rows) if fact_rows is not None else build_guide_fact_rows()
    visas = list(visa_rows) if visa_rows is not None else build_visa_rows()
    parts = [
        "-- GUIDE_FACTS_SEED_BEGIN",
        "-- Idempotent seed. Re-running updates the same source_key / visa key.",
        _insert_countries(),
        _insert_facts(facts),
        _insert_visas(visas),
        "-- GUIDE_FACTS_SEED_END",
    ]
    return "\n".join(parts) + "\n"


def count_summary(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    by_country: Dict[str, int] = {}
    by_zone: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    for row in rows:
        by_country[row["country_slug"]] = by_country.get(row["country_slug"], 0) + 1
        by_zone[row["zone"]] = by_zone.get(row["zone"], 0) + 1
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1
    return {
        "rows": len(rows),
        "by_country": dict(sorted(by_country.items())),
        "by_zone": dict(sorted(by_zone.items())),
        "by_status": dict(sorted(by_status.items())),
        "box": sum(1 for row in rows if row["source_key"].startswith("box:")),
        "steps": sum(1 for row in rows if row["instruction_id"]),
        "normalized": sum(1 for row in rows if row["issuer"]),
    }
