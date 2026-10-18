"""Zone and score from config/trust_config.json.

The stored zone in the guide is this function's output for the check date.
Callers pass the config and the date; the numbers are not written here.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Optional


def parse_date(value: Any) -> Optional[date]:
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _open_freshness(config: Dict[str, Any]) -> int:
    for band in config["freshness_points"]:
        if band.get("max_days") is None:
            return int(band["points"])
    return 0


def freshness_points(age: Optional[int], config: Dict[str, Any]) -> int:
    stale = _open_freshness(config)
    if age is None or age < 0:
        return stale
    finite = [band for band in config["freshness_points"] if band.get("max_days") is not None]
    for band in sorted(finite, key=lambda item: item["max_days"]):
        if age <= int(band["max_days"]):
            return int(band["points"])
    return stale


def source_points(fact: Dict[str, Any], config: Dict[str, Any]) -> Optional[int]:
    points = config["source_points"]
    kind = fact.get("source_kind")
    if kind == "official":
        return int(points["official"])
    if kind == "media":
        return int(points["media"])
    if kind == "internal":
        return int(points["internal"])
    if kind == "traveler":
        reports = fact.get("reports")
        count = reports if isinstance(reports, int) and reports > 0 else 0
        return min(int(points["traveler_max"]), int(points["traveler_per_report"]) * count)
    return None


def zone_for_score(score: int, config: Dict[str, Any]) -> str:
    ranked = sorted(config["zones"], key=lambda zone: zone["min"], reverse=True)
    for zone in ranked:
        if score >= int(zone["min"]):
            return zone["name"]
    return sorted(config["zones"], key=lambda zone: zone["min"])[0]["name"]


def score_fact(fact: Dict[str, Any], config: Dict[str, Any], as_of: date) -> Optional[Dict[str, Any]]:
    """Return score, zone, status and breakdown. None when the formula has no inputs."""
    earned = source_points(fact, config)
    agreement = fact.get("agreement")
    if earned is None or agreement not in config["agreement_points"]:
        return None
    moment = parse_date(fact.get("date_verified"))
    age = None if moment is None else (as_of - moment).days
    fresh = freshness_points(age, config)
    agree_points = int(config["agreement_points"][agreement])
    score = earned + fresh + agree_points
    zone = zone_for_score(score, config)
    if fact.get("refuted"):
        zone = config["refuted_zone"]
    elif fact.get("verified_by_us") and age is not None and 0 <= age <= int(config["verified_by_us_max_days"]):
        zone = config["verified_by_us_zone"]
    status = config["zone_to_status"].get(zone, fact.get("status"))
    return {
        "score": score,
        "zone": zone,
        "status": status,
        "score_breakdown": {"source": earned, "freshness": fresh, "agreement": agree_points},
        "age_days": age,
    }


def percent_text(rate: Decimal, places: int) -> str:
    quant = Decimal("1") if places <= 0 else Decimal("1").scaleb(-places)
    value = (rate * Decimal(100)).quantize(quant, rounding=ROUND_HALF_UP)
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(".", ",")


def _georgia_rule(config: Dict[str, Any]) -> Dict[str, Any]:
    return config["tax_free_rules"]["georgia_refund"]


def georgia_refund_rate(config: Dict[str, Any]) -> Decimal:
    """Share of the price without VAT left after the Revenue Service fee and the bank fee."""
    rule = _georgia_rule(config)
    vat = Decimal(rule["vat_of_price_ex_vat"])
    service = Decimal(rule["service_fee_of_price_ex_vat"])
    bank = Decimal(rule["bank_fee_of_remainder"])
    return (vat - service) * (Decimal(1) - bank)


def georgia_shelf_refund_rate(config: Dict[str, Any]) -> Decimal:
    """Share of the shelf price. The shelf price already includes VAT."""
    vat = Decimal(_georgia_rule(config)["vat_of_price_ex_vat"])
    return georgia_refund_rate(config) / (Decimal(1) + vat)


def georgia_refund_text(config: Dict[str, Any]) -> str:
    rule = _georgia_rule(config)
    vat = Decimal(rule["vat_of_price_ex_vat"])
    service = Decimal(rule["service_fee_of_price_ex_vat"])
    bank = Decimal(rule["bank_fee_of_remainder"])
    places = int(rule["result_decimal_places"])
    shelf = percent_text(georgia_shelf_refund_rate(config), places)
    ex_vat = percent_text(georgia_refund_rate(config), places)
    return (
        "На руки остаётся не весь НДС. Правило Налоговой службы: "
        f"НДС {percent_text(vat, 0)}% цены без НДС, минус сбор службы {percent_text(service, 0)}% "
        f"той же цены, минус комиссия банка {percent_text(bank, 0)}% от оставшейся суммы. "
        f"Получается ≈{shelf}% от цены на ценнике (≈{ex_vat}% от цены без НДС)."
    )
