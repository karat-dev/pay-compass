"""Trust score for a fact. Same formula as the guide's fact-check report.

Points come from config/trust_config.json. A stored zone is not an input.
Age is (as_of - fact date).days, the same count as scripts/fact_check_report.py.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional

ZONE_RANK = {"black": 0, "red": 1, "yellow": 2, "green": 3}


def parse_date(value: Any) -> Optional[date]:
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def fact_date(fact: Dict[str, Any]) -> Optional[date]:
    return (
        parse_date(fact.get("date_verified"))
        or parse_date(fact.get("own_date"))
        or parse_date(fact.get("source_date"))
    )


def age_days(moment: Optional[date], as_of: date) -> Optional[int]:
    if moment is None:
        return None
    return (as_of - moment).days


def freshness_points(days: Optional[int], config: Dict[str, Any]) -> int:
    if days is None or days < 0:
        return 0 if days is None else config["freshness_points"][0]["points"]
    finite = [band for band in config["freshness_points"] if band.get("max_days") is not None]
    finite.sort(key=lambda band: band["max_days"])
    for band in finite:
        if days <= band["max_days"]:
            return int(band["points"])
    for band in config["freshness_points"]:
        if band.get("max_days") is None:
            return int(band["points"])
    return 0


def source_points(kind: Optional[str], reports: Any, config: Dict[str, Any]) -> Optional[int]:
    points = config["source_points"]
    if kind == "official":
        return int(points["official"])
    if kind == "media":
        return int(points["media"])
    if kind == "internal":
        return int(points["internal"])
    if kind == "traveler":
        count = reports if isinstance(reports, int) and reports > 0 else 0
        return min(int(points["traveler_max"]), int(points["traveler_per_report"]) * count)
    return None


def zone_for_score(score: int, config: Dict[str, Any]) -> str:
    ranked = sorted(config["zones"], key=lambda zone: zone["min"], reverse=True)
    for zone in ranked:
        if score >= zone["min"]:
            return zone["name"]
    return "black"


def agreement_points(agreement: str, config: Dict[str, Any]) -> int:
    return int(config["agreement_points"][agreement])


def worst_zone(zones: list) -> str:
    """Lowest rank on the guide scale. Unknown names do not count."""
    ranked = [zone for zone in zones if zone in ZONE_RANK]
    if not ranked:
        return "advice-unsupported"
    return min(ranked, key=lambda zone: ZONE_RANK[zone])


def score_fact(fact: Dict[str, Any], config: Dict[str, Any], as_of: date) -> Dict[str, Any]:
    """Return score, breakdown, score_zone and computed_zone for one fact.

    Gaps and advice are not scored here. Advice takes its zone from supports.
    """
    kind = fact.get("source_kind") if isinstance(fact.get("source_kind"), str) else None
    agreement = fact.get("agreement")
    points = source_points(kind, fact.get("reports"), config)
    if points is None or agreement not in ("agree", "conflict"):
        raise ValueError(f"Cannot score fact without source kind and agreement: {fact.get('text', '')[:80]!r}")
    days = age_days(fact_date(fact), as_of)
    fresh = freshness_points(days, config)
    agree = agreement_points(agreement, config)
    score = points + fresh + agree
    score_zone = zone_for_score(score, config)
    computed = score_zone
    if fact.get("refuted"):
        computed = config["refuted_zone"]
    elif fact.get("contradicted_by_own"):
        cap = config["contradicted_by_own_zone"]
        if ZONE_RANK.get(score_zone, -1) > ZONE_RANK.get(cap, -1):
            computed = cap
    elif fact.get("verified_by_us"):
        limit = int(config["verified_by_us_max_days"])
        if days is not None and 0 <= days <= limit:
            computed = config["verified_by_us_zone"]
    return {
        "score": score,
        "score_breakdown": {"source": points, "freshness": fresh, "agreement": agree},
        "score_zone": score_zone,
        "computed_zone": computed,
        "age_days": days,
    }
