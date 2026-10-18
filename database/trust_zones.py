"""Live fact zones from config/trust_config.json.

Every duration, point value, class length and upgrade count is read from the
config. The stored zone is an input: the value returned here is what the app
and the fact-check report show.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import urlparse


def parse_date(value: Any) -> Optional[date]:
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def fact_moment(fact: Dict[str, Any]) -> Optional[date]:
    return (
        parse_date(fact.get("date_verified"))
        or parse_date(fact.get("own_date"))
        or parse_date(fact.get("source_date"))
    )


def age_days(moment: Optional[date], as_of: date) -> Optional[int]:
    if moment is None:
        return None
    return (as_of - moment).days


def ranked_zones(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    return sorted(config["zones"], key=lambda zone: zone["min"])


def zone_rank(name: Optional[str], config: Dict[str, Any]) -> Optional[int]:
    order = [zone["name"] for zone in ranked_zones(config)]
    if name not in order:
        return None
    return order.index(name)


def zone_for_score(score: int, config: Dict[str, Any]) -> str:
    for zone in sorted(config["zones"], key=lambda item: item["min"], reverse=True):
        if score >= zone["min"]:
            return zone["name"]
    return ranked_zones(config)[0]["name"]


def cap_zone(zone: Optional[str], ceiling: Optional[str], config: Dict[str, Any]) -> Optional[str]:
    zone_level = zone_rank(zone, config)
    ceiling_level = zone_rank(ceiling, config)
    if zone_level is None or ceiling_level is None:
        return zone
    if zone_level > ceiling_level:
        return ceiling
    return zone


def raise_zone(zone: Optional[str], floor: Optional[str], config: Dict[str, Any]) -> Optional[str]:
    zone_level = zone_rank(zone, config)
    floor_level = zone_rank(floor, config)
    if zone_level is None or floor_level is None:
        return zone
    if zone_level < floor_level:
        return floor
    return zone


def lowest_zone(config: Dict[str, Any]) -> str:
    return ranked_zones(config)[0]["name"]


def zone_below(name: str, config: Dict[str, Any]) -> str:
    level = zone_rank(name, config)
    if level is None or level == 0:
        return name
    return ranked_zones(config)[level - 1]["name"]


def finite_freshness_bands(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    bands = [band for band in config["freshness_points"] if band.get("max_days") is not None]
    bands.sort(key=lambda band: band["max_days"])
    return bands


def open_freshness_band(config: Dict[str, Any]) -> Dict[str, Any]:
    for band in config["freshness_points"]:
        if band.get("max_days") is None:
            return band
    return {"max_days": None, "points": ranked_zones(config)[0]["min"]}


def class_spec(name: str, config: Dict[str, Any]) -> Dict[str, Any]:
    classes = config["volatility"]["classes"]
    fallback = config["volatility"]["fallback_class"]
    return classes.get(name) or classes[fallback]


def volatility_class_name(
    fact: Dict[str, Any],
    config: Dict[str, Any],
    *,
    section_key: Optional[str] = None,
    subsection: Optional[str] = None,
    instruction_id: Optional[str] = None,
) -> str:
    classes = config["volatility"]["classes"]
    explicit = fact.get("volatility_class")
    if isinstance(explicit, str) and explicit in classes:
        return explicit
    mapping = config["volatility"]
    if instruction_id and instruction_id in (mapping.get("instructions") or {}):
        return mapping["instructions"][instruction_id]
    if section_key and subsection:
        key = f"{section_key}/{subsection}"
        if key in (mapping.get("subsections") or {}):
            return mapping["subsections"][key]
    if section_key and section_key in (mapping.get("sections") or {}):
        return mapping["sections"][section_key]
    return mapping["fallback_class"]


def class_window_days(spec: Dict[str, Any], config: Dict[str, Any]) -> Optional[int]:
    if spec.get("window_days") is not None:
        return int(spec["window_days"])
    finite = finite_freshness_bands(config)
    if not finite:
        return None
    return int(finite[0]["max_days"])


def freshness_points_for(age: Optional[int], spec: Dict[str, Any], config: Dict[str, Any], *, class_name: str) -> int:
    stale = int(open_freshness_band(config)["points"])
    if age is None or age < 0:
        return stale
    finite = finite_freshness_bands(config)
    full = int(finite[0]["points"]) if finite else stale
    partial = int(finite[1]["points"]) if len(finite) > 1 else stale
    if class_name == config["volatility"]["fallback_class"]:
        for band in finite:
            if age <= band["max_days"]:
                return int(band["points"])
        return stale
    fresh_days = spec.get("fresh_days")
    green_max = spec.get("green_max_days")
    if fresh_days is not None and age <= fresh_days:
        return full
    if green_max is not None and age <= green_max:
        return partial
    return stale


def source_points_for(fact: Dict[str, Any], config: Dict[str, Any]) -> Optional[int]:
    kinds = config["source_kinds"]
    points = config["source_points"]
    kind = fact.get("source_kind")
    if kind == kinds["official"]:
        return int(points["official"])
    if kind == kinds["media"]:
        return int(points["media"])
    if kind == kinds["internal"]:
        return int(points["internal"])
    if kind == kinds["traveler"]:
        reports = fact.get("reports")
        count = reports if isinstance(reports, int) and reports > 0 else 0
        per_report = int(points["traveler_per_report"])
        return min(int(points["traveler_max"]), per_report * count)
    return None


def agreeing_key(config: Dict[str, Any]) -> str:
    points = config["agreement_points"]
    return max(points, key=lambda key: points[key])


def host_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def http_urls(fact: Dict[str, Any]) -> List[str]:
    source = fact.get("source")
    if not isinstance(source, str):
        return []
    found = []
    seen = set()
    for token in source.split():
        if not (token.startswith("http://") or token.startswith("https://")):
            continue
        if token in seen:
            continue
        seen.add(token)
        found.append(token)
    return found


def is_official_publisher(url: str, config: Dict[str, Any]) -> bool:
    host = host_of(url)
    if not host:
        return False
    rules = config["official_publishers"]
    dotted = f".{host}"
    for marker in rules.get("dot_markers") or []:
        if marker in dotted:
            return True
    for suffix in rules.get("public_suffixes") or []:
        if host.endswith(suffix):
            return True
    bare = host[4:] if host.startswith("www.") else host
    for suffix in rules.get("host_suffixes") or []:
        if bare == suffix or bare.endswith("." + suffix):
            return True
    return False


def official_urls(fact: Dict[str, Any], config: Dict[str, Any]) -> List[str]:
    return [url for url in http_urls(fact) if is_official_publisher(url, config)]


def _outlet_key(item: Dict[str, Any]) -> Optional[tuple]:
    if item.get("repost_of"):
        return None
    person = str(item.get("person") or "").strip().lower()
    outlet = str(item.get("outlet") or item.get("url") or "").strip().lower()
    if outlet.startswith("http"):
        outlet = host_of(outlet)
    if person and outlet:
        return ("person", person, outlet)
    if person:
        return ("person", person)
    if outlet:
        return ("outlet", outlet)
    return None


def _counts_toward_upgrade(item: Dict[str, Any], config: Optional[Dict[str, Any]]) -> bool:
    """A listed source with a verdict counts only when that verdict is a confirmation.

    Older facts have no verdict. Those still count, so a new field does not
    drop confirmations that were already in the guide.
    """
    if not config:
        return True
    counted = (config.get("upgrade") or {}).get("counted_confirmation_verdicts")
    if not counted:
        return True
    verdict = item.get("verdict")
    if verdict is None:
        return True
    return verdict in counted


def confirmation_stats(
    fact: Dict[str, Any],
    as_of: date,
    fresh_days: Optional[int],
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Distinct fresh confirmations. A bare reports count is not independence."""
    items = fact.get("confirmations")
    reports = fact.get("reports") if isinstance(fact.get("reports"), int) else 0
    if not isinstance(items, list) or not items:
        moment = fact_moment(fact)
        age = age_days(moment, as_of)
        fresh = fresh_days is not None and age is not None and 0 <= age <= fresh_days
        return {"count": reports, "fresh_count": reports if fresh else 0, "independent": False}
    keys = []
    fresh_keys = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if not _counts_toward_upgrade(item, config):
            continue
        key = _outlet_key(item)
        if key is None:
            continue
        keys.append(key)
        moment = parse_date(item.get("date"))
        age = age_days(moment, as_of)
        if fresh_days is not None and age is not None and 0 <= age <= fresh_days:
            fresh_keys.append(key)
    distinct = list(dict.fromkeys(keys))
    fresh_distinct = list(dict.fromkeys(fresh_keys))
    return {"count": len(distinct), "fresh_count": len(fresh_distinct), "independent": True}


def _gap_zones(config: Dict[str, Any]) -> set:
    return set(config["display"].get("gap_zones") or [])


def _is_gap(fact: Dict[str, Any], config: Dict[str, Any]) -> bool:
    return fact.get("fact_type") == "gap" or fact.get("zone") in _gap_zones(config)


def _is_advice(fact: Dict[str, Any], config: Dict[str, Any]) -> bool:
    hidden = set(config["display"].get("extra_hidden_zones") or [])
    return fact.get("fact_type") == "advice" or fact.get("zone") in hidden


def _blank(fact: Dict[str, Any], config: Dict[str, Any], *, kind: str, reason: str, class_name: str) -> Dict[str, Any]:
    stored = fact.get("zone")
    return {
        "kind": kind,
        "stored_zone": stored,
        "zone": stored,
        "score_zone": None,
        "score": None,
        "score_breakdown": None,
        "volatility_class": class_name,
        "age_days": None,
        "next_zone": None,
        "drops_on": None,
        "at_risk": False,
        "at_risk_reason": None,
        "owner_prompt": None,
        "downgraded": False,
        "upgraded": False,
        "upgrade_to": None,
        "suggested_action": None,
        "automatic": False,
        "reason": reason,
        "confirmations": {"count": 0, "fresh_count": 0, "independent": False},
    }


def _http_failed(results: Sequence[Dict[str, Any]], config: Dict[str, Any]) -> bool:
    rules = config["http"]
    minimum = int(rules["failure_min_status"])
    excluded = set(rules.get("failure_exclude_statuses") or [])
    for item in results:
        if item.get("error") and item.get("error") != "not_checked":
            return True
        code = item.get("status_code")
        if isinstance(code, int) and code >= minimum and code not in excluded:
            return True
    return False


def _source_failed(fact: Dict[str, Any], http_results: Sequence[Dict[str, Any]], config: Dict[str, Any]) -> bool:
    warning = config["early_warning"]
    field = warning["source_failure_field"]
    minimum = int(warning["source_failure_min_count"])
    count = fact.get(field)
    if fact.get("source_failed_once") is True:
        count = minimum
    if isinstance(count, int) and count >= minimum:
        return True
    return _http_failed(http_results, config)


def _boundaries(spec: Dict[str, Any], config: Dict[str, Any], *, class_name: str, verified: bool) -> List[int]:
    """Ages on which a freshness or override window has just closed."""
    found = []
    if class_name == config["volatility"]["fallback_class"]:
        for band in finite_freshness_bands(config):
            found.append(int(band["max_days"]) + 1)
    else:
        if spec.get("fresh_days") is not None:
            found.append(int(spec["fresh_days"]) + 1)
        if spec.get("green_max_days") is not None:
            found.append(int(spec["green_max_days"]) + 1)
    if verified:
        found.append(int(config["verified_by_us_max_days"]) + 1)
    return sorted(set(found))


def _score_zone(
    fact: Dict[str, Any],
    config: Dict[str, Any],
    *,
    as_of: date,
    class_name: str,
    spec: Dict[str, Any],
) -> Dict[str, Any]:
    moment = fact_moment(fact)
    days = age_days(moment, as_of)
    earned = source_points_for(fact, config)
    agreement = fact.get("agreement")
    if earned is None or agreement not in config["agreement_points"]:
        return {"ok": False, "age_days": days, "moment": moment}
    fresh = freshness_points_for(days, spec, config, class_name=class_name)
    agree_points = int(config["agreement_points"][agreement])
    score = earned + fresh + agree_points
    score_zone = zone_for_score(score, config)
    formula = score_zone
    green = config["upgrade"]["green_zone"]
    green_max = spec.get("green_max_days")
    own_limit = int(config["verified_by_us_max_days"])
    own_applies = False
    if fact.get("refuted"):
        formula = config["refuted_zone"]
    elif fact.get("contradicted_by_own"):
        formula = cap_zone(score_zone, config["contradicted_by_own_zone"], config)
    elif fact.get("verified_by_us") and days is not None and 0 <= days <= own_limit:
        if green_max is not None and days <= green_max:
            formula = config["verified_by_us_zone"]
            own_applies = True
    if formula == green and not own_applies:
        too_old = green_max is None or days is None or days > green_max
        if too_old:
            formula = cap_zone(formula, zone_below(green, config), config)
    kinds = config["source_kinds"]
    approved_field = config["upgrade"]["owner_approved_field"]
    if fact.get("source_kind") == kinds["traveler"] and not fact.get(approved_field):
        formula = cap_zone(formula, config["upgrade"]["traveler_unapproved_max_zone"], config)
    return {
        "ok": True,
        "age_days": days,
        "moment": moment,
        "score": score,
        "score_zone": score_zone,
        "formula_zone": formula,
        "score_breakdown": {"source": earned, "freshness": fresh, "agreement": agree_points},
    }


def _apply_upgrade(
    fact: Dict[str, Any],
    config: Dict[str, Any],
    *,
    stored: str,
    formula: str,
    stats: Dict[str, Any],
) -> str:
    stored_level = zone_rank(stored, config)
    formula_level = zone_rank(formula, config)
    if stored_level is None or formula_level is None:
        return formula if formula_level is not None else stored
    if formula_level <= stored_level:
        return formula
    allowed = stored
    yellow = config["upgrade"]["yellow_zone"]
    green = config["upgrade"]["green_zone"]
    needed = int(config["upgrade"]["yellow_min_independent_confirmations"])
    if (
        stats["independent"]
        and stats["fresh_count"] >= needed
        and formula_level >= zone_rank(yellow, config)
        and stored_level < zone_rank(yellow, config)
    ):
        allowed = yellow
    confirmed_field = config["upgrade"]["official_confirmed_field"]
    official_ok = (
        fact.get(confirmed_field) is True
        and fact.get("agreement") == agreeing_key(config)
        and bool(official_urls(fact, config))
        and formula == green
    )
    approved_field = config["upgrade"]["owner_approved_field"]
    traveler_ok = (
        fact.get("source_kind") == config["source_kinds"]["traveler"]
        and fact.get(approved_field) is True
        and formula == green
    )
    if official_ok or traveler_ok:
        allowed = green
    return cap_zone(allowed, formula, config) or stored


def _forecast_drop(
    fact: Dict[str, Any],
    config: Dict[str, Any],
    *,
    as_of: date,
    shown: str,
    class_name: str,
    spec: Dict[str, Any],
    section_key: Optional[str],
    subsection: Optional[str],
    instruction_id: Optional[str],
    http_results: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    moment = fact_moment(fact)
    current_age = age_days(moment, as_of)
    if moment is None or current_age is None:
        return {"next_zone": None, "drops_on": None}
    shown_level = zone_rank(shown, config)
    if shown_level is None:
        return {"next_zone": None, "drops_on": None}
    for boundary in _boundaries(spec, config, class_name=class_name, verified=bool(fact.get("verified_by_us"))):
        if current_age is not None and boundary <= current_age:
            continue
        future = moment + timedelta(days=boundary)
        later = resolve_zone(
            fact,
            config=config,
            as_of=future,
            section_key=section_key,
            subsection=subsection,
            instruction_id=instruction_id,
            http_results=http_results,
            forecast=False,
        )
        later_level = zone_rank(later["zone"], config)
        if later_level is not None and later_level < shown_level:
            return {"next_zone": later["zone"], "drops_on": future.isoformat()}
    return {"next_zone": None, "drops_on": None}


def resolve_zone(
    fact: Dict[str, Any],
    *,
    config: Dict[str, Any],
    as_of: date,
    section_key: Optional[str] = None,
    subsection: Optional[str] = None,
    instruction_id: Optional[str] = None,
    http_results: Optional[Sequence[Dict[str, Any]]] = None,
    forecast: bool = True,
) -> Dict[str, Any]:
    http_results = list(http_results or [])
    class_name = volatility_class_name(
        fact,
        config,
        section_key=section_key,
        subsection=subsection,
        instruction_id=instruction_id,
    )
    spec = class_spec(class_name, config)
    messages = config.get("messages") or {}
    if _is_gap(fact, config):
        return _blank(fact, config, kind="gap", reason=messages.get("gap") or "", class_name=class_name)
    if _is_advice(fact, config):
        return _blank(fact, config, kind="advice", reason=messages.get("advice") or "", class_name=class_name)

    scored = _score_zone(fact, config, as_of=as_of, class_name=class_name, spec=spec)
    if not scored["ok"]:
        blank = _blank(fact, config, kind="unscored", reason=messages.get("unscored") or "", class_name=class_name)
        blank["zone"] = lowest_zone(config)
        blank["age_days"] = scored["age_days"]
        return blank

    stored = fact.get("zone")
    fresh_days = spec.get("fresh_days")
    if fresh_days is None:
        fresh_days = class_window_days(spec, config)
    stats = confirmation_stats(fact, as_of, fresh_days if fresh_days is not None else None, config)
    formula = scored["formula_zone"]
    if zone_rank(stored, config) is None:
        shown = formula
    else:
        shown = _apply_upgrade(fact, config, stored=stored, formula=formula, stats=stats)

    stored_level = zone_rank(stored, config)
    shown_level = zone_rank(shown, config)
    downgraded = stored_level is not None and shown_level is not None and shown_level < stored_level
    upgraded = stored_level is not None and shown_level is not None and shown_level > stored_level
    green = config["upgrade"]["green_zone"]
    prompt = None
    traveler = fact.get("source_kind") == config["source_kinds"]["traveler"]
    approved = fact.get(config["upgrade"]["owner_approved_field"]) is True
    if traveler and not approved and scored["score_zone"] == green and shown != green:
        count = stats["fresh_count"] if stats["independent"] else stats["count"]
        prompt = config["upgrade"]["owner_prompt_template"].format(n=count)

    action = None
    automatic = False
    upgrade_to = None
    if downgraded:
        action = "downgrade"
        automatic = True
    elif upgraded:
        action = "upgrade_candidate"
        automatic = True
        upgrade_to = shown
    elif prompt:
        action = "owner_decision"

    reason = messages.get("matched") or ""
    if downgraded:
        reason = (messages.get("downgrade") or "").format(stored=stored, zone=shown, as_of=as_of.isoformat())
    elif upgraded:
        reason = (messages.get("upgrade") or "").format(stored=stored, zone=shown)
    elif prompt:
        reason = prompt

    drop = {"next_zone": None, "drops_on": None}
    if forecast and scored["ok"]:
        drop = _forecast_drop(
            fact,
            config,
            as_of=as_of,
            shown=shown,
            class_name=class_name,
            spec=spec,
            section_key=section_key,
            subsection=subsection,
            instruction_id=instruction_id,
            http_results=http_results,
        )

    reasons = []
    warning = config["early_warning"]
    if drop["drops_on"]:
        remaining = (parse_date(drop["drops_on"]) - as_of).days
        window = class_window_days(spec, config)
        share = warning["share"]
        if window is not None and remaining < share * window:
            reasons.append(warning["reasons"]["window"])
    if fact.get("agreement") == warning["conflict_agreement"]:
        reasons.append(warning["reasons"]["conflict"])
    if _source_failed(fact, http_results, config):
        reasons.append(warning["reasons"]["source_failed"])
    at_risk = bool(reasons)
    at_risk_reason = "; ".join(reasons) if reasons else None
    if at_risk and action not in ("downgrade", "upgrade_candidate"):
        action = warning["refresh_action"]
        automatic = False
        if at_risk_reason:
            reason = f"{at_risk_reason}. {prompt}" if prompt else at_risk_reason

    return {
        "kind": "scored",
        "stored_zone": stored,
        "zone": shown,
        "score_zone": scored["score_zone"],
        "score": scored["score"],
        "score_breakdown": scored["score_breakdown"],
        "volatility_class": class_name,
        "age_days": scored["age_days"],
        "next_zone": drop["next_zone"],
        "drops_on": drop["drops_on"],
        "at_risk": at_risk,
        "at_risk_reason": at_risk_reason,
        "owner_prompt": prompt,
        "downgraded": downgraded,
        "upgraded": upgraded,
        "upgrade_to": upgrade_to,
        "suggested_action": action,
        "automatic": automatic,
        "reason": reason,
        "confirmations": stats,
    }
