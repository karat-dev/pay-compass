"""Community reviews: confirmations, badge, antifraud, moderation, achievements.

Every threshold is read from config.community. A missing key raises ConfigError.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib.parse import parse_qsl
import json

from database.config_error import ConfigError
from database.trust_zones import (
    class_spec,
    class_window_days,
    fact_moment,
    official_urls,
    parse_date,
    volatility_class_name,
)

REQUIRED_COMMUNITY_KEYS = (
    ("community", "source_kind"),
    ("community", "outlet"),
    ("community", "verdicts"),
    ("community", "result_to_verdict"),
    ("community", "result_to_verdict", "success"),
    ("community", "result_to_verdict", "fail"),
    ("community", "result_to_verdict", "partial"),
    ("community", "partial_vote_weight"),
    ("community", "full_vote_weight"),
    ("community", "min_refutes_to_downgrade"),
    ("community", "fact_date_field"),
    ("community", "max_trip_age_days_on_submit"),
    ("community", "suggest_facts_limit"),
    ("community", "recheck_reminder_days"),
    ("community", "nick_max_length"),
    ("community", "moderation"),
    ("community", "moderation", "mode"),
    ("community", "moderation", "modes"),
    ("community", "moderation", "review_all_mode"),
    ("community", "moderation", "disputes_only_mode"),
    ("community", "moderation", "dispute_triggers"),
    ("community", "moderation", "trigger_codes"),
    ("community", "moderation", "trigger_codes", "official_conflict"),
    ("community", "moderation", "trigger_codes", "fraud_suspected"),
    ("community", "moderation", "trigger_codes", "refute_spike"),
    ("community", "moderation", "refute_spike"),
    ("community", "moderation", "refute_spike", "window_days"),
    ("community", "moderation", "refute_spike", "min_refutes"),
    ("community", "moderation", "actions"),
    ("community", "weights"),
    ("community", "weights", "base"),
    ("community", "weights", "photo_multiplier"),
    ("community", "weights", "default_level"),
    ("community", "weights", "level_multipliers"),
    ("community", "badge"),
    ("community", "badge", "label"),
    ("community", "badge", "caption"),
    ("community", "badge", "refute_penalty"),
    ("community", "badge", "max_refutes"),
    ("community", "badge", "levels"),
    ("community", "antifraud"),
    ("community", "antifraud", "min_tg_account_age_days"),
    ("community", "antifraud", "max_reviews_per_day"),
    ("community", "antifraud", "max_reviews_per_fact_window"),
    ("community", "antifraud", "tg_id_anchor_min"),
    ("community", "antifraud", "tg_id_anchors"),
    ("community", "antifraud", "linked_account_groups"),
    ("community", "antifraud", "flag_names"),
    ("community", "antifraud", "flag_names", "young"),
    ("community", "antifraud", "flag_names", "age_unknown"),
    ("community", "antifraud", "flag_names", "daily"),
    ("community", "antifraud", "flag_names", "fact_window"),
    ("community", "antifraud", "flag_names", "future"),
    ("community", "antifraud", "flag_names", "overlap"),
    ("community", "antifraud", "flag_names", "amount"),
    ("community", "antifraud", "flag_names", "fee"),
    ("community", "antifraud", "flag_names", "linked"),
    ("community", "antifraud", "outlier_check"),
    ("community", "antifraud", "outlier_check", "future_dates"),
    ("community", "antifraud", "outlier_check", "overlapping_trips"),
    ("community", "antifraud", "outlier_check", "amount_ratio"),
    ("community", "antifraud", "outlier_check", "fee_ratio"),
    ("community", "antifraud", "outlier_check", "min_samples"),
    ("community", "achievements"),
    ("community", "achievements", "recheck_month"),
    ("community", "achievements", "recheck_month", "code"),
    ("community", "achievements", "recheck_month", "title"),
    ("community", "achievements", "recheck_month", "recheck_min_days"),
    ("community", "achievements", "recheck_month", "recheck_max_days"),
    ("community", "downgrade"),
    ("community", "downgrade", "method"),
    ("community", "downgrade", "flag_by_method"),
    ("community", "statuses"),
    ("community", "statuses", "pending"),
    ("community", "statuses", "approved"),
    ("community", "statuses", "rejected"),
    ("community", "statuses", "idea"),
    ("community", "queue"),
    ("community", "queue", "statuses"),
    ("community", "queue", "statuses", "open"),
    ("community", "queue", "statuses", "closed"),
    ("community", "queue", "kinds"),
    ("community", "queue", "kinds", "review"),
    ("community", "queue", "kinds", "dispute"),
    ("community", "queue", "kinds", "idea"),
    ("community", "verdict_sources"),
    ("community", "verdict_sources", "auto"),
    ("community", "verdict_sources", "owner"),
    ("community", "not_counted_reasons"),
    ("community", "not_counted_reasons", "antifraud"),
    ("community", "not_counted_reasons", "pending_owner"),
    ("community", "not_counted_reasons", "owner"),
    ("community", "not_counted_reasons", "rejected"),
    ("community", "not_counted_reasons", "replaced"),
    ("community", "not_counted_reasons", "idea"),
    ("community", "topics"),
    ("community", "payment_methods"),
    ("community", "payment_method_topics"),
    ("community", "place_types"),
    ("community", "results"),
    ("community", "citizenships"),
    ("community", "form_hints"),
    ("community", "form_hints", "dates"),
    ("community", "form_hints", "topic"),
    ("community", "form_hints", "fact"),
    ("community", "form_hints", "action"),
    ("community", "form_hints", "changed"),
    ("community", "form_hints", "amount"),
    ("community", "form_hints", "duration"),
    ("community", "form_hints", "place"),
    ("community", "form_hints", "photo"),
    ("community", "form_hints", "citizenship"),
    ("community", "form_hints", "recheck"),
    ("community", "form_hints", "anonymous"),
    ("community", "actions"),
    ("community", "helped_counter"),
    ("community", "helped_counter", "dedupe_per_user"),
    ("community", "photo"),
    ("community", "photo", "confidence_min"),
    ("community", "photo", "clean_status"),
    ("community", "photo", "review_status"),
    ("community", "photo", "max_bytes"),
    ("community", "photo", "max_request_bytes"),
    ("community", "messages"),
    ("community", "messages", "moderation_queue"),
    ("community", "messages", "recheck_reminder"),
    ("community", "messages", "achievement"),
    ("community", "messages", "helped"),
    ("community", "messages", "consent"),
    ("community", "messages", "not_owner"),
    ("community", "messages", "trip_too_old"),
    ("community", "messages", "future_date"),
    ("community", "messages", "missing_field"),
    ("community", "messages", "bad_field"),
    ("community", "messages", "payment_method"),
    ("community", "messages", "changed_required"),
    ("community", "messages", "unknown_action"),
    ("community", "duration_units"),
    ("community", "photo", "jpeg_quality"),
    ("community", "photo", "card_min_digits"),
    ("community", "photo", "card_max_digits"),
    ("community", "photo", "mrz_marker"),
    ("community", "photo", "mrz_min_chevrons"),
    ("community", "photo", "redaction_rgb"),
    ("community", "photo", "face_cascade"),
    ("community", "photo", "face_scale_factor"),
    ("community", "photo", "face_min_neighbors"),
    ("community", "photo", "detector_ran_confidence"),
    ("community", "photo", "detector_failed_confidence"),
    ("community", "photo", "empty_ocr_confidence"),
    ("community", "photo", "ocr_unknown_confidence"),
    ("community", "photo", "ocr_confidence_scale"),
    ("community", "topic_by_section"),
    ("community", "topic_by_instruction"),
)


def need(config: Dict[str, Any], *path: str) -> Any:
    current: Any = config
    walked: List[str] = []
    for key in path:
        walked.append(key)
        if not isinstance(current, dict) or key not in current:
            raise ConfigError("В конфиге нет ключа " + ".".join(walked))
        current = current[key]
    return current


def require_community(config: Dict[str, Any]) -> Dict[str, Any]:
    for path in REQUIRED_COMMUNITY_KEYS:
        need(config, *path)
    community = config["community"]
    mode = community["moderation"]["mode"]
    if mode not in community["moderation"]["modes"]:
        raise ConfigError("community.moderation.mode вне community.moderation.modes")
    default_level = community["weights"]["default_level"]
    if default_level not in community["weights"]["level_multipliers"]:
        raise ConfigError("community.weights.default_level нет в level_multipliers")
    method = community["downgrade"]["method"]
    if method not in community["downgrade"]["flag_by_method"]:
        raise ConfigError("community.downgrade.method вне flag_by_method")
    verdicts = community["verdicts"]
    for name, verdict in community["result_to_verdict"].items():
        if verdict not in verdicts:
            raise ConfigError("community.result_to_verdict." + name + " вне verdicts")
    for level in community["badge"]["levels"]:
        if not isinstance(level, dict):
            raise ConfigError("community.badge.levels содержит не объект")
        for key in ("code", "title", "min_strength"):
            if key not in level:
                raise ConfigError("community.badge.levels без " + key)
    triggers = community["moderation"]["dispute_triggers"]
    for key, code in community["moderation"]["trigger_codes"].items():
        if code not in triggers:
            raise ConfigError("community.moderation.trigger_codes." + key + " вне dispute_triggers")
    anchors = community["antifraud"]["tg_id_anchors"]
    if not isinstance(anchors, list):
        raise ConfigError("community.antifraud.tg_id_anchors должен быть списком")
    return community


def message(config: Dict[str, Any], key: str) -> str:
    return str(need(config, "community", "messages", key))


def _codes(rows: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    found = {}
    for row in rows:
        if isinstance(row, dict) and row.get("code"):
            found[row["code"]] = row
    return found


def topic_for_fact(
    config: Dict[str, Any],
    *,
    section_key: Optional[str] = None,
    instruction_id: Optional[str] = None,
) -> Optional[str]:
    require_community(config)
    by_instruction = need(config, "community", "topic_by_instruction")
    if instruction_id and instruction_id in by_instruction:
        return by_instruction[instruction_id]
    by_section = need(config, "community", "topic_by_section")
    if section_key and section_key in by_section:
        return by_section[section_key]
    return None


def public_community_form(config: Dict[str, Any]) -> Dict[str, Any]:
    community = require_community(config)
    badge = community["badge"]
    photo = community["photo"]
    return {
        "topics": list(community["topics"]),
        "payment_methods": list(community["payment_methods"]),
        "payment_method_topics": list(community["payment_method_topics"]),
        "place_types": list(community["place_types"]),
        "results": list(community["results"]),
        "citizenships": list(community["citizenships"]),
        "cities_by_country": dict(community.get("cities_by_country") or {}),
        "duration_units": list(community.get("duration_units") or []),
        "fee_kinds": list(community.get("fee_kinds") or []),
        "form_hints": dict(community["form_hints"]),
        "actions": dict(community["actions"]),
        "badge_label": badge["label"],
        "badge_caption": badge["caption"],
        "helped_template": community.get("helped_template") or "",
        "photo_max_bytes": photo["max_bytes"],
        "verdicts": list(community["verdicts"]),
    }


def freshness_window(
    fact: Dict[str, Any],
    config: Dict[str, Any],
    *,
    section_key: Optional[str] = None,
    subsection: Optional[str] = None,
    instruction_id: Optional[str] = None,
) -> Any:
    name = volatility_class_name(
        fact,
        config,
        section_key=section_key,
        subsection=subsection,
        instruction_id=instruction_id,
    )
    spec = class_spec(name, config)
    fresh = spec.get("fresh_days")
    if fresh is None:
        fresh = class_window_days(spec, config)
    return fresh


def in_fresh_window(moment: Optional[date], as_of: date, window_days: Any) -> bool:
    if moment is None:
        return False
    age = (as_of - moment).days
    if age < 0:
        return False
    if window_days is None:
        return True
    return age <= window_days


def _day(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return parse_date(value)


def verdict_for_result(result: str, config: Dict[str, Any]) -> str:
    mapping = need(config, "community", "result_to_verdict")
    if result not in mapping:
        raise ConfigError("community.result_to_verdict без " + result)
    return mapping[result]


def badge_weight(review: Dict[str, Any], verdict: str, config: Dict[str, Any], level_code: Optional[str] = None) -> Any:
    community = require_community(config)
    weights = community["weights"]
    code = level_code or weights["default_level"]
    multipliers = weights["level_multipliers"]
    if code not in multipliers:
        raise ConfigError("Нет множителя уровня " + str(code))
    weight = weights["base"] * multipliers[code]
    clean = community["photo"]["clean_status"]
    if review.get("photo_path") and review.get("photo_redaction_status") == clean:
        weight = weight * weights["photo_multiplier"]
    if verdict == community["result_to_verdict"]["partial"]:
        weight = weight * community["partial_vote_weight"]
    return weight


def zone_vote_weight(verdict: str, config: Dict[str, Any]) -> Any:
    community = require_community(config)
    mapping = community["result_to_verdict"]
    if verdict == mapping["partial"]:
        return community["partial_vote_weight"]
    if verdict == mapping["success"]:
        return community["full_vote_weight"]
    return None


def _index_reviews(reviews: Sequence[Dict[str, Any]]) -> Dict[Any, Dict[str, Any]]:
    return {row.get("id"): row for row in reviews if isinstance(row, dict)}


def _latest_by_user(
    links: Sequence[Dict[str, Any]],
    reviews_by_id: Dict[Any, Dict[str, Any]],
    config: Dict[str, Any],
    *,
    fact_id: Optional[str],
    as_of: date,
    window_days: Any,
    counted_only: bool,
) -> Dict[Any, Dict[str, Any]]:
    field = need(config, "community", "fact_date_field")
    chosen: Dict[Any, Dict[str, Any]] = {}
    for link in links:
        if not isinstance(link, dict):
            continue
        if fact_id is not None and link.get("fact_id") != fact_id:
            continue
        if counted_only and not link.get("counted"):
            continue
        review = reviews_by_id.get(link.get("review_id"))
        if not review:
            continue
        moment = _day(review.get(field))
        if not in_fresh_window(moment, as_of, window_days):
            continue
        user_id = review.get("user_id")
        previous = chosen.get(user_id)
        if previous is None or (moment is not None and (previous["moment"] is None or moment >= previous["moment"])):
            chosen[user_id] = {"moment": moment, "link": link, "review": review}
    return chosen


def confirmation_items(
    links: Sequence[Dict[str, Any]],
    reviews: Sequence[Dict[str, Any]],
    config: Dict[str, Any],
    *,
    fact_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    community = require_community(config)
    reviews_by_id = _index_reviews(reviews)
    confirms = community["result_to_verdict"]["success"]
    partial = community["result_to_verdict"]["partial"]
    items = []
    for link in links:
        if not isinstance(link, dict) or not link.get("counted"):
            continue
        verdict = link.get("verdict")
        if verdict not in (confirms, partial):
            continue
        if fact_id is not None and link.get("fact_id") != fact_id:
            continue
        review = reviews_by_id.get(link.get("review_id"))
        if not review:
            continue
        weight = zone_vote_weight(verdict, config)
        items.append({
            "person": str(review.get("user_id")),
            "outlet": community["outlet"],
            "date": review.get(community["fact_date_field"]),
            "verdict": verdict,
            "weight": weight,
            "user_id": review.get("user_id"),
            "source_kind": community["source_kind"],
            "type": community["source_kind"],
        })
    return items


def count_refutes(
    links: Sequence[Dict[str, Any]],
    reviews: Sequence[Dict[str, Any]],
    config: Dict[str, Any],
    *,
    fact_id: str,
    as_of: date,
    window_days: Any,
) -> int:
    community = require_community(config)
    refute = community["result_to_verdict"]["fail"]
    chosen = _latest_by_user(
        links,
        _index_reviews(reviews),
        config,
        fact_id=fact_id,
        as_of=as_of,
        window_days=window_days,
        counted_only=True,
    )
    total = 0
    for row in chosen.values():
        if row["link"].get("verdict") == refute:
            total = total + 1
    return total


def has_fresh_official(fact: Dict[str, Any], config: Dict[str, Any], as_of: date, window_days: Any) -> bool:
    field = need(config, "upgrade", "official_confirmed_field")
    if fact.get(field) is True and official_urls(fact, config):
        if in_fresh_window(fact_moment(fact), as_of, window_days):
            return True
    official = need(config, "source_kinds", "official")
    counted = need(config, "upgrade", "counted_confirmation_verdicts")
    for item in fact.get("confirmations") or []:
        if not isinstance(item, dict):
            continue
        kind = item.get("source_kind") or item.get("type")
        if kind != official:
            continue
        verdict = item.get("verdict")
        if verdict is not None and verdict not in counted:
            continue
        if in_fresh_window(parse_date(item.get("date")), as_of, window_days):
            return True
    return False


def apply_community_state(
    fact: Dict[str, Any],
    links: Sequence[Dict[str, Any]],
    reviews: Sequence[Dict[str, Any]],
    config: Dict[str, Any],
    *,
    fact_id: str,
    as_of: date,
    window_days: Any,
) -> Dict[str, Any]:
    community = require_community(config)
    merged = dict(fact)
    merged["confirmations"] = list(fact.get("confirmations") or []) + confirmation_items(
        links, reviews, config, fact_id=fact_id
    )
    refutes = count_refutes(links, reviews, config, fact_id=fact_id, as_of=as_of, window_days=window_days)
    official = has_fresh_official(fact, config, as_of, window_days)
    disputes: List[Dict[str, str]] = []
    downgraded = False
    conflict = False
    threshold = community["min_refutes_to_downgrade"]
    if refutes >= threshold:
        trigger = community["moderation"]["trigger_codes"]["official_conflict"]
        if official:
            merged["community_conflict"] = True
            conflict = True
            disputes.append({
                "kind": community["queue"]["kinds"]["dispute"],
                "trigger": trigger,
            })
        else:
            flag = community["downgrade"]["flag_by_method"][community["downgrade"]["method"]]
            merged[flag] = True
            downgraded = True
    return {"fact": merged, "disputes": disputes, "downgraded": downgraded, "conflict": conflict, "refutes": refutes}


def community_badge(
    links: Sequence[Dict[str, Any]],
    reviews: Sequence[Dict[str, Any]],
    config: Dict[str, Any],
    *,
    fact_id: str,
    as_of: date,
    window_days: Any,
    level_code: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    community = require_community(config)
    confirms = community["result_to_verdict"]["success"]
    partial = community["result_to_verdict"]["partial"]
    refute = community["result_to_verdict"]["fail"]
    chosen = _latest_by_user(
        links,
        _index_reviews(reviews),
        config,
        fact_id=fact_id,
        as_of=as_of,
        window_days=window_days,
        counted_only=True,
    )
    confirm_weight = 0
    refute_weight = 0
    refute_count = 0
    for row in chosen.values():
        verdict = row["link"].get("verdict")
        weight = badge_weight(row["review"], verdict, config, level_code)
        if verdict == refute:
            refute_weight = refute_weight + weight
            refute_count = refute_count + 1
        elif verdict in (confirms, partial):
            confirm_weight = confirm_weight + weight
    badge = community["badge"]
    if refute_count > badge["max_refutes"]:
        return None
    strength = confirm_weight - badge["refute_penalty"] * refute_weight
    best = None
    for level in badge["levels"]:
        if strength >= level["min_strength"] and (best is None or level["min_strength"] >= best["min_strength"]):
            best = level
    if best is None:
        return None
    return {
        "code": best["code"],
        "title": best["title"],
        "strength": strength,
        "label": badge["label"],
        "caption": badge["caption"],
    }


def estimate_tg_age_days(telegram_id: Any, config: Dict[str, Any], as_of: date) -> Optional[int]:
    community = require_community(config)
    if telegram_id is None:
        return None
    points = []
    for row in community["antifraud"]["tg_id_anchors"]:
        if not isinstance(row, dict):
            raise ConfigError("community.antifraud.tg_id_anchors содержит не объект")
        moment = _day(row.get("on"))
        if moment is None or "telegram_id" not in row:
            raise ConfigError("community.antifraud.tg_id_anchors без telegram_id или даты")
        points.append((row["telegram_id"], moment))
    points.sort(key=lambda item: item[0])
    if len(points) < community["antifraud"]["tg_id_anchor_min"]:
        return None
    created = _account_created(telegram_id, points)
    if created is None:
        return None
    return (as_of - created).days


def _ends(points: Sequence[Any]) -> tuple:
    previous = None
    last = None
    for item in points:
        previous = last
        last = item
    return previous, last


def _first_two(points: Sequence[Any]) -> tuple:
    first = None
    second = None
    for item in points:
        if first is None:
            first = item
        elif second is None:
            second = item
            return first, second
    return first, second


def _account_created(telegram_id: Any, points: Sequence[Any]) -> Optional[date]:
    first, second = _first_two(points)
    previous, last = _ends(points)
    if first is None or second is None or previous is None or last is None:
        return None
    if telegram_id <= first[0]:
        left, right = first, second
    elif telegram_id >= last[0]:
        left, right = previous, last
    else:
        left, right = first, second
        for item in points:
            if item[0] <= telegram_id:
                left = item
            else:
                right = item
                break
    span_ids = right[0] - left[0]
    if span_ids == 0:
        return None
    span_days = (right[1] - left[1]).days
    offset = (telegram_id - left[0]) * span_days / span_ids
    from datetime import timedelta

    return left[1] + timedelta(days=offset)


def antifraud_flags(
    review: Dict[str, Any],
    history: Sequence[Dict[str, Any]],
    config: Dict[str, Any],
    *,
    as_of: date,
    age_days: Optional[int],
    window_days: Any,
    linked_user_ids: Iterable[Any] = (),
    amount_samples: Sequence[Any] = (),
    fee_samples: Sequence[Any] = (),
) -> List[str]:
    community = require_community(config)
    rules = community["antifraud"]
    names = rules["flag_names"]
    flags: List[str] = []
    if age_days is None:
        flags.append(names["age_unknown"])
    elif age_days < rules["min_tg_account_age_days"]:
        flags.append(names["young"])
    day_count = 0
    fact_count = 0
    field = community["fact_date_field"]
    for row in history:
        if not isinstance(row, dict):
            continue
        if row.get("id") == review.get("id"):
            continue
        created = _day(row.get("created_at"))
        if created == as_of:
            day_count = day_count + 1
        if row.get("fact_id") and review.get("fact_id") and row.get("fact_id") == review.get("fact_id"):
            if in_fresh_window(created, as_of, window_days):
                fact_count = fact_count + 1
        if rules["outlier_check"]["overlapping_trips"] and _trips_overlap(review, row, field):
            flags.append(names["overlap"])
    if day_count >= rules["max_reviews_per_day"]:
        flags.append(names["daily"])
    if review.get("fact_id") and fact_count >= rules["max_reviews_per_fact_window"]:
        flags.append(names["fact_window"])
    if rules["outlier_check"]["future_dates"]:
        start = _day(review.get("trip_date_start"))
        end = _day(review.get(field))
        if (start is not None and start > as_of) or (end is not None and end > as_of):
            flags.append(names["future"])
    if _outside_range(review.get("amount"), amount_samples, rules["outlier_check"]):
        flags.append(names["amount"])
    if _outside_range(review.get("fee"), fee_samples, rules["outlier_check"], ratio_key="fee_ratio"):
        flags.append(names["fee"])
    if linked_voters(review.get("user_id"), rules["linked_account_groups"], linked_user_ids):
        flags.append(names["linked"])
    return list(dict.fromkeys(flags))


def linked_voters(user_id: Any, groups: Sequence[Any], voter_ids: Iterable[Any]) -> List[Any]:
    text = str(user_id)
    voters = {str(item) for item in voter_ids}
    found = []
    for group in groups or []:
        members = [str(item) for item in group]
        if text not in members:
            continue
        for member in members:
            if member != text and member in voters:
                found.append(member)
    return found


def _trips_overlap(review: Dict[str, Any], other: Dict[str, Any], field: str) -> bool:
    if not other.get("country") or not review.get("country"):
        return False
    if other.get("country") == review.get("country"):
        return False
    if str(other.get("user_id")) != str(review.get("user_id")):
        return False
    start = _day(review.get("trip_date_start"))
    end = _day(review.get(field))
    other_start = _day(other.get("trip_date_start"))
    other_end = _day(other.get(field))
    if None in (start, end, other_start, other_end):
        return False
    return start <= other_end and other_start <= end


def _outside_range(value: Any, samples: Sequence[Any], rules: Dict[str, Any], ratio_key: str = "amount_ratio") -> bool:
    if value is None:
        return False
    usable = [item for item in samples if isinstance(item, (int, float)) and not isinstance(item, bool)]
    if len(usable) < rules["min_samples"]:
        return False
    low = min(usable)
    high = max(usable)
    ratio = rules[ratio_key]
    if value > high * ratio:
        return True
    if value * ratio < low:
        return True
    return False


def plan_intake(
    *,
    has_fact: bool,
    flags: Sequence[str],
    spike: bool,
    official_conflict: bool,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    community = require_community(config)
    statuses = community["statuses"]
    kinds = community["queue"]["kinds"]
    triggers = community["moderation"]["trigger_codes"]
    reasons = community["not_counted_reasons"]
    mode = community["moderation"]["mode"]
    queue: List[Dict[str, Any]] = []
    if not has_fact:
        return {
            "status": statuses["idea"],
            "counted": False,
            "reason": reasons["idea"],
            "queue": [{"kind": kinds["idea"], "trigger": None}],
        }
    if flags:
        queue.append({"kind": kinds["review"], "trigger": triggers["fraud_suspected"]})
    if official_conflict:
        queue.append({"kind": kinds["dispute"], "trigger": triggers["official_conflict"]})
    if spike:
        queue.append({"kind": kinds["dispute"], "trigger": triggers["refute_spike"]})
    if mode == community["moderation"]["review_all_mode"]:
        if not queue:
            queue.append({"kind": kinds["review"], "trigger": None})
        return {
            "status": statuses["pending"],
            "counted": False,
            "reason": reasons["antifraud"] if flags else reasons["pending_owner"],
            "queue": queue,
        }
    if mode == community["moderation"]["disputes_only_mode"]:
        if flags:
            return {
                "status": statuses["pending"],
                "counted": False,
                "reason": reasons["antifraud"],
                "queue": queue,
            }
        return {
            "status": statuses["approved"],
            "counted": True,
            "reason": None,
            "queue": queue,
        }
    raise ConfigError("community.moderation.mode не поддержан")


def refute_spike(
    links: Sequence[Dict[str, Any]],
    reviews: Sequence[Dict[str, Any]],
    config: Dict[str, Any],
    *,
    fact_id: str,
    as_of: date,
    extra_refute: bool = False,
) -> bool:
    community = require_community(config)
    window = community["moderation"]["refute_spike"]["window_days"]
    minimum = community["moderation"]["refute_spike"]["min_refutes"]
    total = count_refutes(links, reviews, config, fact_id=fact_id, as_of=as_of, window_days=window)
    if extra_refute:
        total = total + 1
    return total >= minimum


def links_replacing(
    existing: Sequence[Dict[str, Any]],
    new_link: Dict[str, Any],
    config: Dict[str, Any],
) -> List[Dict[str, Any]]:
    reason = need(config, "community", "not_counted_reasons", "replaced")
    updated = []
    for link in existing:
        same_user = str(link.get("user_id")) == str(new_link.get("user_id"))
        same_fact = link.get("fact_id") == new_link.get("fact_id")
        if same_user and same_fact and link.get("id") != new_link.get("id"):
            copy = dict(link)
            copy["counted"] = False
            copy["not_counted_reason"] = reason
            updated.append(copy)
        else:
            updated.append(dict(link))
    updated.append(dict(new_link))
    return updated


def apply_owner_action(
    review: Dict[str, Any],
    links: Sequence[Dict[str, Any]],
    action: str,
    config: Dict[str, Any],
    *,
    now: str,
    verdict: Optional[str] = None,
) -> Dict[str, Any]:
    community = require_community(config)
    actions = community["moderation"]["actions"]
    statuses = community["statuses"]
    sources = community["verdict_sources"]
    reasons = community["not_counted_reasons"]
    if action not in actions.values():
        raise ValueError(message(config, "unknown_action"))
    updated_review = dict(review)
    updated_links = [dict(link) for link in links if link.get("review_id") == review.get("id")]
    decision = action
    if action == actions["count"]:
        updated_review["status"] = statuses["approved"]
        updated_review["moderated_at"] = now
        for link in updated_links:
            link["counted"] = True
            link["verdict_source"] = sources["owner"]
            link["not_counted_reason"] = None
    elif action == actions["ignore"]:
        updated_review["status"] = statuses["approved"]
        updated_review["moderated_at"] = now
        for link in updated_links:
            link["counted"] = False
            link["verdict_source"] = sources["owner"]
            link["not_counted_reason"] = reasons["owner"]
    elif action == actions["reject"]:
        updated_review["status"] = statuses["rejected"]
        updated_review["moderated_at"] = now
        for link in updated_links:
            link["counted"] = False
            link["verdict_source"] = sources["owner"]
            link["not_counted_reason"] = reasons["rejected"]
    elif action == actions["change_verdict"]:
        if verdict not in community["verdicts"]:
            raise ValueError(message(config, "bad_field"))
        for link in updated_links:
            link["verdict"] = verdict
            link["verdict_source"] = sources["owner"]
            link["weight"] = badge_weight(updated_review, verdict, config)
    elif action == actions["accept_idea"]:
        updated_review["status"] = statuses["idea"]
        updated_review["moderated_at"] = now
    elif action == actions["close_idea"]:
        updated_review["status"] = statuses["rejected"]
        updated_review["moderated_at"] = now
    return {"review": updated_review, "links": updated_links, "decision": decision}


def recheck_award(
    review: Dict[str, Any],
    reviews: Sequence[Dict[str, Any]],
    links: Sequence[Dict[str, Any]],
    config: Dict[str, Any],
    *,
    fact_id: str,
) -> Optional[Dict[str, Any]]:
    community = require_community(config)
    spec = community["achievements"]["recheck_month"]
    approved = community["statuses"]["approved"]
    if review.get("status") != approved:
        return None
    field = community["fact_date_field"]
    new_day = _day(review.get(field))
    if new_day is None:
        return None
    linked_ids = {
        link.get("review_id")
        for link in links
        if link.get("fact_id") == fact_id
    }
    for other in reviews:
        if other.get("id") == review.get("id"):
            continue
        if str(other.get("user_id")) != str(review.get("user_id")):
            continue
        if other.get("status") != approved:
            continue
        if other.get("id") not in linked_ids:
            continue
        previous = _day(other.get(field))
        if previous is None or new_day < previous:
            continue
        gap = (new_day - previous).days
        if spec["recheck_min_days"] <= gap <= spec["recheck_max_days"]:
            return {
                "user_id": review.get("user_id"),
                "code": spec["code"],
                "scope": fact_id,
                "review_id": review.get("id"),
                "title": spec["title"],
            }
    return None


def helped_count(
    author_id: Any,
    reviews: Sequence[Dict[str, Any]],
    links: Sequence[Dict[str, Any]],
    views: Sequence[Dict[str, Any]],
    config: Dict[str, Any],
) -> int:
    community = require_community(config)
    reviews_by_id = _index_reviews(reviews)
    dedupe = community["helped_counter"]["dedupe_per_user"]
    users = set()
    pairs = set()
    for link in links:
        if not link.get("counted"):
            continue
        review = reviews_by_id.get(link.get("review_id"))
        if not review or str(review.get("user_id")) != str(author_id):
            continue
        counted_at = review.get("moderated_at") or review.get("created_at")
        for view in views:
            if view.get("fact_id") != link.get("fact_id"):
                continue
            if str(view.get("user_id")) == str(author_id):
                continue
            seen = view.get("first_seen_at")
            if seen is None or counted_at is None or str(seen) < str(counted_at):
                continue
            users.add(str(view.get("user_id")))
            pairs.add((str(view.get("user_id")), view.get("fact_id")))
    if dedupe:
        return len(users)
    return len(pairs)


def due_recheck_reminders(
    reviews: Sequence[Dict[str, Any]],
    achievements: Sequence[Dict[str, Any]],
    config: Dict[str, Any],
    *,
    as_of: date,
    links: Sequence[Dict[str, Any]] = (),
) -> List[Dict[str, Any]]:
    community = require_community(config)
    approved = community["statuses"]["approved"]
    code = community["achievements"]["recheck_month"]["code"]
    wait = community["recheck_reminder_days"]
    awarded = {(str(row.get("user_id")), row.get("code"), row.get("scope")) for row in achievements}
    fact_of = {}
    for link in links:
        fact_of.setdefault(link.get("review_id"), link.get("fact_id"))
    due = []
    for review in reviews:
        if not review.get("ready_to_recheck"):
            continue
        if review.get("recheck_reminded_at"):
            continue
        if review.get("status") != approved:
            continue
        anchor = _day(review.get("moderated_at") or review.get("created_at"))
        if anchor is None or (as_of - anchor).days < wait:
            continue
        scope = review.get("fact_id") or fact_of.get(review.get("id"))
        if (str(review.get("user_id")), code, scope) in awarded:
            continue
        later = False
        for other in reviews:
            if other.get("id") == review.get("id"):
                continue
            if str(other.get("user_id")) != str(review.get("user_id")):
                continue
            other_scope = other.get("fact_id") or fact_of.get(other.get("id"))
            if other_scope != scope:
                continue
            if str(other.get("created_at") or "") > str(review.get("created_at") or ""):
                later = True
        if later:
            continue
        due.append(review)
    return due


def suggest_facts(
    facts: Sequence[Dict[str, Any]],
    config: Dict[str, Any],
    *,
    country: str,
    city: str,
    topic: str,
) -> List[Dict[str, Any]]:
    community = require_community(config)
    limit = community["suggest_facts_limit"]
    city_norm = (city or "").casefold()
    ranked = []
    for fact in facts:
        if fact.get("country_slug") != country:
            continue
        if topic and fact.get("community_topic") != topic:
            continue
        text = (fact.get("text") or "").casefold()
        city_hit = bool(city_norm and city_norm in text)
        ranked.append((not city_hit, fact))
    ranked.sort(key=lambda item: item[0])
    chosen = []
    for _hit, fact in ranked:
        chosen.append(fact)
        if len(chosen) >= limit:
            break
    return chosen


def _require_text(value: Any, config: Dict[str, Any]) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(message(config, "missing_field"))
    return value.strip()


def _optional_number(value: Any, config: Dict[str, Any]) -> Any:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(message(config, "bad_field"))
    if isinstance(value, str):
        try:
            value = float(value) if "." in value else int(value)
        except ValueError as exc:
            raise ValueError(message(config, "bad_field")) from exc
    if value < 0:
        raise ValueError(message(config, "bad_field"))
    return value


def clean_review_fields(payload: Dict[str, Any], config: Dict[str, Any], as_of: date) -> Dict[str, Any]:
    community = require_community(config)
    if payload.get("consent") is not True:
        raise ValueError(message(config, "consent"))
    country = _require_text(payload.get("country"), config)
    city = _require_text(payload.get("city"), config)
    start = _day(payload.get("trip_date_start"))
    end = _day(payload.get("trip_date_end"))
    if start is None or end is None or end < start:
        raise ValueError(message(config, "bad_field"))
    if start > as_of or end > as_of:
        raise ValueError(message(config, "future_date"))
    if (as_of - end).days > community["max_trip_age_days_on_submit"]:
        raise ValueError(message(config, "trip_too_old"))
    topics = _codes(community["topics"])
    topic = payload.get("topic")
    if topic not in topics:
        raise ValueError(message(config, "bad_field"))
    results = _codes(community["results"])
    result = payload.get("result")
    if result not in results:
        raise ValueError(message(config, "bad_field"))
    citizenships = _codes(community["citizenships"])
    citizenship = payload.get("citizenship")
    if citizenship not in citizenships:
        raise ValueError(message(config, "bad_field"))
    action_text = _require_text(payload.get("action_text"), config)
    fact_id = payload.get("fact_id") or None
    if fact_id is not None and not isinstance(fact_id, str):
        raise ValueError(message(config, "bad_field"))
    changed = bool(payload.get("changed"))
    changed_text = payload.get("changed_text") or ""
    if not isinstance(changed_text, str):
        raise ValueError(message(config, "bad_field"))
    changed_text = changed_text.strip()
    if fact_id and changed and not changed_text:
        raise ValueError(message(config, "changed_required"))
    if topic in community["payment_method_topics"]:
        methods = _codes(community["payment_methods"])
        payment_method = payload.get("payment_method")
        if payment_method not in methods:
            raise ValueError(message(config, "payment_method"))
    else:
        payment_method = payload.get("payment_method") or None
        if payment_method:
            methods = _codes(community["payment_methods"])
            if payment_method not in methods:
                raise ValueError(message(config, "bad_field"))
    place_type = payload.get("place_type") or None
    if place_type:
        if place_type not in _codes(community["place_types"]):
            raise ValueError(message(config, "bad_field"))
    place_name = payload.get("place_name") or ""
    if not isinstance(place_name, str):
        raise ValueError(message(config, "bad_field"))
    fee_kind = payload.get("fee_kind") or None
    if fee_kind and fee_kind not in _codes(community.get("fee_kinds") or []):
        raise ValueError(message(config, "bad_field"))
    duration_min = _duration_minutes(payload, config)
    return {
        "country": country,
        "city": city,
        "trip_date_start": start.isoformat(),
        "trip_date_end": end.isoformat(),
        "topic": topic,
        "fact_id": fact_id,
        "action_text": action_text,
        "result": result,
        "changed_text": changed_text or None,
        "amount": _optional_number(payload.get("amount"), config),
        "currency": _optional_text(payload.get("currency")),
        "fee": _optional_number(payload.get("fee"), config),
        "fee_kind": fee_kind,
        "duration_min": duration_min,
        "place_type": place_type,
        "place_name": place_name.strip() or None,
        "citizenship": citizenship,
        "payment_method": payment_method,
        "ready_to_recheck": bool(payload.get("ready_to_recheck")),
        "is_anonymous": bool(payload.get("is_anonymous")),
    }


def _optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _duration_minutes(payload: Dict[str, Any], config: Dict[str, Any]) -> Any:
    raw = payload.get("duration_value")
    if raw is None or raw == "":
        raw = payload.get("duration_min")
        unit = payload.get("duration_unit")
        if raw is None or raw == "":
            return None
        if not unit:
            return _optional_number(raw, config)
    else:
        unit = payload.get("duration_unit")
    units = {row["code"]: row["minutes"] for row in need(config, "community", "duration_units")}
    if unit not in units:
        raise ValueError(message(config, "bad_field"))
    amount = _optional_number(raw, config)
    if amount is None:
        return None
    return amount * units[unit]


def telegram_nick(init_data: str, config: Dict[str, Any]) -> Optional[str]:
    """Public @username only. A display name is not a nick and is not stored."""
    require_community(config)
    raw = (init_data or "").strip()
    if not raw or raw.startswith("dev:"):
        return None
    pairs = dict(parse_qsl(raw, keep_blank_values=True))
    try:
        user = json.loads(pairs.get("user") or "")
    except json.JSONDecodeError:
        return None
    if not isinstance(user, dict):
        return None
    name = user.get("username")
    if not isinstance(name, str):
        return None
    limit = need(config, "community", "nick_max_length")
    cleaned = name.strip()
    if not cleaned or len(cleaned) > limit:
        return None
    return cleaned


def author_level_weight(config: Dict[str, Any]) -> Any:
    community = require_community(config)
    code = community["weights"]["default_level"]
    return community["weights"]["level_multipliers"][code]


def level_row(
    user_id: Any,
    reviews: Sequence[Dict[str, Any]],
    links: Sequence[Dict[str, Any]],
    views: Sequence[Dict[str, Any]],
    config: Dict[str, Any],
    *,
    now: str,
) -> Dict[str, Any]:
    community = require_community(config)
    approved = community["statuses"]["approved"]
    counted_ids = {link.get("review_id") for link in links if link.get("counted")}
    mine = [
        row for row in reviews
        if str(row.get("user_id")) == str(user_id) and row.get("status") == approved and row.get("id") in counted_ids
    ]
    confirms = community["result_to_verdict"]["success"]
    good = 0
    total = 0
    reviews_by_id = _index_reviews(reviews)
    for link in links:
        review = reviews_by_id.get(link.get("review_id"))
        if not review or str(review.get("user_id")) != str(user_id) or not link.get("counted"):
            continue
        total = total + 1
        if _later_independent_confirm(link, links, reviews_by_id, confirms, user_id):
            good = good + 1
    accuracy = None if total == 0 else good / total
    return {
        "user_id": user_id,
        "counted_reviews": len(mine),
        "accuracy": accuracy,
        "author_weight": author_level_weight(config),
        "helped_count": helped_count(user_id, reviews, links, views, config),
        "updated_at": now,
    }


def _later_independent_confirm(
    link: Dict[str, Any],
    links: Sequence[Dict[str, Any]],
    reviews_by_id: Dict[Any, Dict[str, Any]],
    confirms: str,
    user_id: Any,
) -> bool:
    for other in links:
        if other.get("fact_id") != link.get("fact_id") or not other.get("counted"):
            continue
        if other.get("verdict") != confirms:
            continue
        review = reviews_by_id.get(other.get("review_id"))
        if not review or str(review.get("user_id")) == str(user_id):
            continue
        if str(other.get("created_at") or "") > str(link.get("created_at") or ""):
            return True
    return False


def sort_by_badge(facts: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def key(fact: Dict[str, Any]) -> tuple:
        badge = fact.get("community_badge") or None
        strength = None if not isinstance(badge, dict) else badge.get("strength")
        missing = strength is None
        return (missing, 0 if strength is None else -strength)

    return sorted(list(facts), key=key)
