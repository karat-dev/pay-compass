#!/usr/bin/env python3
"""Read-only fact-check report for the payment guide.

Prints a Russian summary and can write fact_check_report.json. It does not
edit countries, trust config, or the database.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.knowledge_base import INSTRUCTION_SECTION, SECTION_ORDER, is_gap, public_source_url  # noqa: E402
from database.miniapp_catalog import _fact_id  # noqa: E402
from database.route_model import MODEL_DIR, allowance_fact, measurement_fact  # noqa: E402
from database.trust_zones import (  # noqa: E402
    confirmation_stats,
    http_urls as trust_http_urls,
    is_official_publisher as trust_is_official_publisher,
    open_freshness_band,
    resolve_zone,
    zone_rank,
)

DATA_PATH = ROOT / "database" / "data" / "countries.json"
CONFIG_PATH = ROOT / "config" / "trust_config.json"

TELEGRAM_SECRET_NAME = "TELEGRAM_BOT_TOKEN"
CHAT_SECRET_NAME = "OWNER_TELEGRAM_CHAT_ID"
DEFAULT_OWNER_CHAT_ID = "303653591"
TELEGRAM_LIMIT = 4096
SCHEMA_VERSION = 1

COUNTRY_ORDER = ("china", "hong_kong", "thailand", "uae", "turkey", "georgia")
SECTION_CATEGORY = {
    "1_checklist": "checklist",
    "2_pay_on_site": "pay_on_site",
    "3_local_wallets_cards": "wallets_and_cards",
    "4_cash_exchange": "cash",
    "5_atms": "atms",
    "6_transport": "transport",
    "7_risks": "risks",
    "8_tax_free": "tax_free",
}
SUBSECTION_CATEGORY = {
    "wallets": "wallets",
    "local_card": "local_card",
}
ACTIONS = (
    "downgrade",
    "fix_link",
    "upgrade_candidate",
    "rerun",
    "owner_decision",
    "owner_manual_check",
    "refresh_search",
)

def load_json(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


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


def fresh_limit_days(config: Dict[str, Any]) -> Optional[int]:
    finite = [band["max_days"] for band in config["freshness_points"] if band.get("max_days") is not None]
    if not finite:
        return None
    return min(finite)


def is_official_publisher(url: str, config: Optional[Dict[str, Any]] = None) -> bool:
    """Bank, operator, or government site. Guide blogs do not qualify."""
    active = config if config is not None else load_json(CONFIG_PATH)
    return trust_is_official_publisher(url, active)


def http_urls(fact: Dict[str, Any]) -> List[str]:
    return trust_http_urls(fact)


def _rank(zone: Optional[str], config: Dict[str, Any]) -> Optional[int]:
    return zone_rank(zone, config)


def _weekday_matches(moment: date, cron_dow: int) -> bool:
    """Cron day-of-week: 0 and 7 are Sunday, 1 is Monday. date.weekday starts at Monday."""
    normalized = int(cron_dow) % 7
    sunday_based = (moment.weekday() + 1) % 7
    return sunday_based == normalized


def next_schedule_date(schedule: Dict[str, Any], as_of: date) -> date:
    """First calendar date strictly after as_of that matches the config schedule."""
    day_of_month = schedule.get("day_of_month")
    day_of_week = schedule.get("day_of_week")
    cursor = as_of
    for _ in range(366):
        cursor = cursor + timedelta(days=1)
        if day_of_month is not None and cursor.day != int(day_of_month):
            continue
        if day_of_week is not None and not _weekday_matches(cursor, int(day_of_week)):
            continue
        return cursor
    raise ValueError(f"No date for schedule {schedule.get('id')}")


def _schedule_matches(schedule: Dict[str, Any], class_name: Optional[str], category: Optional[str]) -> bool:
    classes = schedule.get("classes")
    categories = schedule.get("categories")
    if not classes and not categories:
        return False
    if classes is not None and class_name not in classes:
        return False
    if categories is not None and category not in categories:
        return False
    return True


def _covering_schedules(
    config: Dict[str, Any],
    *,
    class_name: Optional[str],
    category: Optional[str],
) -> List[Dict[str, Any]]:
    matched = [
        schedule
        for schedule in (config.get("auto_checks") or {}).get("schedules") or []
        if _schedule_matches(schedule, class_name, category)
    ]
    categorized = [schedule for schedule in matched if schedule.get("categories")]
    return categorized or matched


def _is_product_question(source: Dict[str, Any], resolved: Dict[str, Any], config: Dict[str, Any]) -> bool:
    rules = (config.get("auto_checks") or {}).get("product") or {}
    verified = rules.get("verified_field")
    if verified and source.get(verified) is True:
        return True
    if source.get("source_kind") in set(rules.get("source_kinds") or []):
        return True
    conflict_field = rules.get("conflict_field")
    if conflict_field and source.get(conflict_field) == config["early_warning"]["conflict_agreement"]:
        return True
    if source.get("volatility") == rules.get("conflict_volatility"):
        return True
    review_kind = rules.get("review_source_kind")
    green = config["upgrade"]["green_zone"]
    if source.get("source_kind") == review_kind and (
        resolved.get("owner_prompt")
        or resolved.get("score_zone") == green
        or source.get("score_zone") == green
    ):
        return True
    for field in (rules.get("owner_check_field"), rules.get("decision_field"), rules.get("refresh_field")):
        if field and source.get(field):
            return True
    return False


def _uncovered_text(config: Dict[str, Any], kind: str) -> str:
    labels = config["auto_checks"]
    word = labels["kind_labels"][kind]
    return labels["uncovered_text"].format(kind=word)


def auto_check_fields(
    source: Dict[str, Any],
    resolved: Dict[str, Any],
    config: Dict[str, Any],
    as_of: date,
    *,
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """Next planned automatic check, or an explicit owner question when none covers the fact."""
    labels = config["auto_checks"]
    product = labels["kinds"]["product"]
    logic = labels["kinds"]["logic"]
    if _is_product_question(source, resolved, config):
        return {
            "next_auto_check": None,
            "owner_question_type": product,
            "auto_check_text": _uncovered_text(config, product),
        }
    kind = resolved.get("kind")
    gap = kind == "gap" or source.get("fact_type") == "gap" or source.get("gap") is True
    if gap or kind == "unscored":
        return {
            "next_auto_check": None,
            "owner_question_type": logic,
            "auto_check_text": _uncovered_text(config, logic),
        }
    automatic_sources = set(labels.get("source_kinds") or [])
    if source.get("fact_type") == "advice" and source.get("source_kind") not in automatic_sources:
        return {
            "next_auto_check": None,
            "owner_question_type": logic,
            "auto_check_text": _uncovered_text(config, logic),
        }
    class_name = resolved.get("volatility_class") or source.get("volatility_class")
    schedules = _covering_schedules(config, class_name=class_name, category=category)
    if not schedules:
        return {
            "next_auto_check": None,
            "owner_question_type": logic,
            "auto_check_text": _uncovered_text(config, logic),
        }
    planned = min(next_schedule_date(schedule, as_of) for schedule in schedules)
    if resolved.get("at_risk"):
        drop = parse_date(resolved.get("drops_on"))
        if drop is not None and as_of <= drop < planned:
            planned = drop
    return {
        "next_auto_check": planned.isoformat(),
        "owner_question_type": None,
        "auto_check_text": labels["date_text"].format(date=planned.isoformat()),
    }


def summarize_auto_checks(rows: Sequence[Dict[str, Any]], config: Dict[str, Any]) -> Dict[str, Any]:
    labels = config["auto_checks"]
    product = labels["kinds"]["product"]
    logic = labels["kinds"]["logic"]
    dates: Dict[str, int] = {}
    product_count = 0
    logic_count = 0
    for row in rows:
        when = row.get("next_auto_check")
        if when:
            dates[str(when)] = dates.get(str(when), 0) + 1
        elif row.get("owner_question_type") == product:
            product_count += 1
        else:
            logic_count += 1
    return {
        "label": labels["summary_label"],
        "dates": [{"date": key, "count": dates[key]} for key in sorted(dates)],
        "product": product_count,
        "logic": logic_count,
        "owner_label": labels["owner_summary"].format(
            product_label=labels["kind_labels"]["product"],
            logic_label=labels["kind_labels"]["logic"],
            product=product_count,
            logic=logic_count,
        ),
    }


def _auto_lines(block: Optional[Dict[str, Any]]) -> List[str]:
    if not block:
        return []
    lines = [block["label"]]
    for item in block.get("dates") or []:
        lines.append(f"{item['date']}: {item['count']}")
    lines.append(block["owner_label"])
    lines.append("")
    return lines


def assess_fact(
    fact: Dict[str, Any],
    *,
    config: Dict[str, Any],
    as_of: date,
    scope: str,
    country: str,
    category: str,
    instruction_id: Optional[str] = None,
    section_key: Optional[str] = None,
    subsection: Optional[str] = None,
    http_by_url: Optional[Dict[str, Dict[str, Any]]] = None,
    check_http: bool = False,
) -> Dict[str, Any]:
    text = fact.get("text") or ""
    current = fact.get("zone")
    moment = fact_date(fact)
    days = age_days(moment, as_of)
    urls = http_urls(fact)
    public = public_source_url(fact)
    http_by_url = http_by_url or {}
    http_results = []
    if check_http:
        for url in urls:
            http_results.append(dict(http_by_url.get(url) or {"url": url, "status_code": None, "error": "not_checked", "content_confirmed": False}))
    flags: List[str] = []
    if fact.get("unknown_zone"):
        flags.append("unknown_zone")
    if fact.get("needs_owner_check"):
        flags.append("needs_owner_check")
    if fact.get("decision_needed"):
        flags.append("decision_needed")
    gap = fact.get("fact_type") == "gap" or current == "gap" or fact.get("zone") in set(config["display"].get("gap_zones") or ["gap"])
    if gap:
        flags.append("gap")
    if not public:
        flags.append("no_public_source")

    last_check = None
    if parse_date(fact.get("date_verified")):
        last_check = fact.get("date_verified")[:10]
    elif parse_date(fact.get("checked_at")):
        last_check = fact.get("checked_at")[:10]

    base: Dict[str, Any] = {
        "fact_id": _fact_id(scope, text),
        "country": country,
        "category": category,
        "instruction_id": instruction_id,
        "text": text,
        "current_zone": current,
        "computed_zone": None,
        "score_zone": None,
        "score": None,
        "status": "inconclusive",
        "reason": "",
        "source_urls": urls,
        "public_source_url": public,
        "http_results": http_results,
        "last_check_date": last_check,
        "suggested_action": None,
        "automatic": False,
        "upgrade_to": None,
        "owner_prompt": None,
        "next_zone": None,
        "drops_on": None,
        "at_risk": False,
        "at_risk_reason": None,
        "next_auto_check": None,
        "owner_question_type": None,
        "auto_check_text": "",
        "flags": flags,
    }
    resolved = resolve_zone(
        fact,
        config=config,
        as_of=as_of,
        section_key=section_key,
        subsection=subsection,
        instruction_id=instruction_id,
        http_results=http_results,
    )
    base["next_zone"] = resolved["next_zone"]
    base["drops_on"] = resolved["drops_on"]
    base["at_risk"] = resolved["at_risk"]
    base["at_risk_reason"] = resolved["at_risk_reason"]
    if resolved["at_risk"]:
        flags.append("at_risk")

    if gap or resolved["kind"] == "gap":
        base["reason"] = resolved["reason"] or config["messages"]["gap"]
        base["suggested_action"] = "owner_decision"
        return _finalize_http(base, flags, config, source=fact, resolved=resolved, as_of=as_of)
    if resolved["kind"] == "advice" or fact.get("fact_type") == "advice" or current in set(config["display"].get("extra_hidden_zones") or []):
        base["reason"] = resolved["reason"] or config["messages"]["advice"]
        if fact.get("needs_owner_check"):
            base["suggested_action"] = "owner_manual_check"
        elif fact.get("decision_needed"):
            base["suggested_action"] = "owner_decision"
        return _finalize_http(base, flags, config, source=fact, resolved=resolved, as_of=as_of)
    if resolved["kind"] != "scored":
        base["reason"] = resolved["reason"] or config["messages"]["unscored"]
        base["suggested_action"] = "rerun"
        return _finalize_http(base, flags, config, source=fact, resolved=resolved, as_of=as_of)

    score_zone = resolved["score_zone"]
    computed = resolved["zone"]
    score = resolved["score"]
    fresh = (resolved["score_breakdown"] or {}).get("freshness")
    if (
        fact.get("verified_by_us")
        and _rank(score_zone, config) is not None
        and _rank(computed, config) is not None
        and _rank(score_zone, config) < _rank(computed, config)
    ):
        flags.append("own_experience_override")

    stored_fresh = None
    breakdown = fact.get("score_breakdown")
    if isinstance(breakdown, dict) and "freshness" in breakdown:
        stored_fresh = breakdown.get("freshness")

    base["computed_zone"] = computed
    base["score_zone"] = score_zone
    base["score"] = score
    if score_zone != current:
        flags.append("score_zone_mismatch")
    if computed != current:
        flags.append("zone_mismatch")

    current_rank = _rank(current, config)
    computed_rank = _rank(computed, config)
    score_rank = _rank(score_zone, config)
    if current_rank is None or computed_rank is None:
        base["status"] = "inconclusive"
        base["reason"] = "Записанная зона вне шкалы green/yellow/red/black."
        base["suggested_action"] = "rerun"
        return _finalize_http(base, flags, config, source=fact, resolved=resolved, as_of=as_of)
    if current != computed:
        base["status"] = "fail"
    elif score_rank is not None and score_rank < current_rank:
        base["status"] = "stale"
    elif stored_fresh is not None and stored_fresh != fresh:
        base["status"] = "stale"
        flags.append("freshness_drift")
    else:
        base["status"] = "ok"

    action, automatic, upgrade_to, prompt, reason = _action(
        fact,
        config=config,
        as_of=as_of,
        current=current,
        computed=computed,
        score_zone=score_zone,
        days=days,
        urls=urls,
        http_results=http_results,
        check_http=check_http,
    )
    if resolved["at_risk"] and action not in ("downgrade", "upgrade_candidate"):
        action = config["early_warning"]["refresh_action"]
        automatic = False
        reason = resolved["at_risk_reason"] or reason
        prompt = resolved["owner_prompt"] or prompt
    if fact.get("refresh_search") and action not in ("downgrade", "upgrade_candidate"):
        action = config["early_warning"]["refresh_action"]
        automatic = False
        checked = fact.get("date_verified") or fact.get("checked_at") or ""
        owner_reason = (
            f"Заявление владельца {checked}: нужен новый поиск подтверждения у оператора или в СМИ. "
            "Свой ли это опыт, ещё не подтверждено."
        )
        if resolved["at_risk"] and resolved.get("at_risk_reason"):
            reason = f"{owner_reason} {resolved['at_risk_reason']}"
        else:
            reason = owner_reason
    base["suggested_action"] = action
    base["automatic"] = automatic
    base["upgrade_to"] = upgrade_to
    base["owner_prompt"] = prompt or resolved["owner_prompt"]
    base["reason"] = reason
    if base["suggested_action"] == "owner_decision" and base["owner_prompt"]:
        flags.append("traveler_green_needs_owner")
    return _finalize_http(base, flags, config, source=fact, resolved=resolved, as_of=as_of)


def _finalize_http(
    row: Dict[str, Any],
    flags: List[str],
    config: Dict[str, Any],
    *,
    source: Optional[Dict[str, Any]] = None,
    resolved: Optional[Dict[str, Any]] = None,
    as_of: Optional[date] = None,
) -> Dict[str, Any]:
    rules = config["http"]
    excluded = set(rules["failure_exclude_statuses"])
    minimum = int(rules["failure_min_status"])
    for result in row["http_results"]:
        code = result.get("status_code")
        error = result.get("error")
        if error and error != "not_checked":
            flags.append("http_inconclusive")
        elif isinstance(code, int) and code in excluded:
            flags.append("http_blocked")
        elif isinstance(code, int) and code >= minimum:
            flags.append("http_failed")
    row["flags"] = sorted(set(flags))
    if row["suggested_action"] is not None and row["suggested_action"] not in ACTIONS:
        raise RuntimeError(f"unexpected action {row['suggested_action']}")
    if as_of is not None and source is not None and resolved is not None:
        row.update(auto_check_fields(source, resolved, config, as_of, category=row.get("category")))
    return row


def _status_ok(code: Any, config: Dict[str, Any]) -> bool:
    rules = config["http"]
    return isinstance(code, int) and int(rules["success_min_status"]) <= code <= int(rules["success_max_status"])


def _page_opened(results: Sequence[Dict[str, Any]], config: Dict[str, Any]) -> bool:
    return any(_status_ok(item.get("status_code"), config) for item in results)


def _page_confirms(results: Sequence[Dict[str, Any]], config: Dict[str, Any]) -> bool:
    return any(item.get("content_confirmed") and _status_ok(item.get("status_code"), config) for item in results)


def _http_broken(results: Sequence[Dict[str, Any]], config: Dict[str, Any]) -> bool:
    broken = set(config["http"]["broken_statuses"])
    return any(isinstance(item.get("status_code"), int) and item["status_code"] in broken for item in results)


def _http_retry(results: Sequence[Dict[str, Any]], config: Dict[str, Any]) -> bool:
    rules = config["http"]
    retry_codes = set(rules["retry_statuses"])
    retry_min = int(rules["retry_min_status"])
    for item in results:
        code = item.get("status_code")
        error = item.get("error")
        if error and error != "not_checked":
            return True
        if isinstance(code, int) and (code >= retry_min or code in retry_codes):
            return True
    return False


def _action(
    fact: Dict[str, Any],
    *,
    config: Dict[str, Any],
    as_of: date,
    current: str,
    computed: str,
    score_zone: str,
    days: Optional[int],
    urls: Sequence[str],
    http_results: Sequence[Dict[str, Any]],
    check_http: bool,
) -> tuple:
    current_rank = _rank(current, config)
    computed_rank = _rank(computed, config)
    fresh_days = fresh_limit_days(config)
    stats = confirmation_stats(fact, as_of, fresh_days, config)
    official = [url for url in urls if is_official_publisher(url, config)]
    traveler_kind = config["source_kinds"]["traveler"]
    green = config["upgrade"]["green_zone"]
    yellow = config["upgrade"]["yellow_zone"]
    needed = int(config["upgrade"]["yellow_min_independent_confirmations"])
    green_rank = _rank(green, config)
    yellow_rank = _rank(yellow, config)
    traveler_only = fact.get("source_kind") == traveler_kind and not official
    count_for_prompt = stats["fresh_count"] if stats["independent"] else stats["count"]
    green_prompt = config["upgrade"]["owner_prompt_template"].format(n=count_for_prompt)

    if current_rank is not None and computed_rank is not None and current_rank > computed_rank:
        return (
            "downgrade",
            True,
            None,
            None,
            config["messages"]["downgrade"].format(stored=current, zone=computed, as_of=as_of.isoformat()),
        )

    raise_green = traveler_only and score_zone == green and current_rank is not None and green_rank is not None and current_rank < green_rank
    score_rank = _rank(score_zone, config)
    auto_yellow = (
        stats["independent"]
        and stats["fresh_count"] >= needed
        and current_rank is not None
        and yellow_rank is not None
        and current_rank < yellow_rank
        and score_rank is not None
        and score_rank >= yellow_rank
    )
    if raise_green and auto_yellow:
        return (
            "upgrade_candidate",
            True,
            yellow,
            green_prompt,
            config["messages"]["upgrade"].format(stored=current, zone=yellow) + " " + green_prompt,
        )
    if raise_green:
        why = "Независимость людей и площадок в данных не размечена, поэтому жёлтый сам не ставится. " if not stats["independent"] else ""
        return ("owner_decision", False, None, green_prompt, why + green_prompt)

    if official and score_zone == green and current_rank is not None and green_rank is not None and current_rank < green_rank:
        if _page_confirms(http_results, config):
            return (
                "upgrade_candidate",
                True,
                green,
                None,
                "Официальная страница открылась и сверка текста разрешена. Повышение до зелёного автоматическое.",
            )
        if check_http and _page_opened(http_results, config):
            return (
                "owner_manual_check",
                False,
                None,
                None,
                "Официальная страница открылась. Текст факта со страницей не сверен, до зелёного автоматически не поднимаем.",
            )
        if check_http and _http_broken(http_results, config):
            return ("fix_link", False, None, None, "Официальная ссылка не открывается.")
        if check_http and _http_retry(http_results, config):
            return ("rerun", False, None, None, "Официальную страницу не удалось прочитать, прогон нужно повторить.")
        if not check_http:
            return ("rerun", False, None, None, "Чтобы решить зелёный, нужно открыть официальную страницу. В этом прогоне HTTP выключен.")

    if (
        stats["independent"]
        and stats["fresh_count"] >= needed
        and current_rank is not None
        and yellow_rank is not None
        and current_rank < yellow_rank
        and score_rank is not None
        and score_rank >= yellow_rank
    ):
        return (
            "upgrade_candidate",
            True,
            yellow,
            None,
            config["messages"]["upgrade"].format(stored=current, zone=yellow),
        )

    if traveler_only and current == green and score_zone == green:
        shown = stats["fresh_count"] if stats["independent"] else stats["count"]
        return (
            "owner_decision",
            False,
            None,
            None,
            f"Зелёный держится на отзывах ({shown}), официальной страницы нет. Само так не оставляем, нужно решение владельца.",
        )

    if fact.get("needs_owner_check"):
        return ("owner_manual_check", False, None, None, "Пометка needs_owner_check: нужна ручная проверка владельца.")
    if fact.get("decision_needed"):
        return ("owner_decision", False, None, None, str(fact.get("decision_needed")))
    if fact.get("unknown_zone"):
        return ("owner_manual_check", False, None, None, "Внутренняя пометка, что проверку не закрыли.")
    if fact.get("verified_by_us") and score_rank is not None and current_rank is not None and score_rank < current_rank:
        return (
            "owner_manual_check",
            False,
            None,
            None,
            f"По баллам зона {score_zone} (сумма без надбавки). В файле {current} из-за «проверено нами».",
        )
    visible = {zone["name"] for zone in config["zones"] if zone["min"] >= config["display"]["default_min"]}
    if not public_source_url(fact) and current in visible and fact.get("source_kind") != config["source_kinds"]["internal"]:
        return ("fix_link", False, None, None, "На карточке, которую видно сразу, нет публичной ссылки.")
    if _http_broken(http_results, config):
        broken = ", ".join(str(code) for code in config["http"]["broken_statuses"])
        return ("fix_link", False, None, None, f"Ссылка источника отвечает {broken}.")
    if _http_retry(http_results, config):
        return ("rerun", False, None, None, "Источник не ответил, проверку ссылки нужно повторить.")
    if current != computed and current_rank is not None and computed_rank is not None and current_rank < computed_rank:
        return (
            "owner_manual_check",
            False,
            None,
            None,
            f"Формула даёт {computed}, в файле {current}. Автоматически вверх не поднимаем.",
        )
    if days is not None and days < 0:
        return ("rerun", False, None, None, "Дата проверки в будущем.")
    return (None, False, None, None, "Зона сходится с формулой на дату отчёта.")


def _facts_of(node: Any) -> List[Dict[str, Any]]:
    if isinstance(node, list):
        return [item for item in node if isinstance(item, dict)]
    if isinstance(node, dict):
        return [item for item in (node.get("facts") or []) if isinstance(item, dict)]
    return []


def iter_records(bundle: Dict[str, Any], *, scope: str, country: Optional[str]) -> Iterable[Dict[str, Any]]:
    countries = bundle.get("countries") or {}
    order = [slug for slug in COUNTRY_ORDER if slug in countries]
    order.extend(slug for slug in countries if slug not in order)
    if scope == "country":
        order = [slug for slug in order if slug == country]
    instructions = bundle.get("instructions") or {}
    for slug in order:
        raw_country = countries[slug]
        for key, _title in SECTION_ORDER:
            section = (raw_country.get("sections") or {}).get(key) or {}
            for fact in _facts_of(section):
                yield {
                    "fact": fact,
                    "country": slug,
                    "category": SECTION_CATEGORY[key],
                    "scope": f"{slug}/{key}",
                    "section_key": key,
                    "subsection": None,
                    "instruction_id": None,
                }
            subsections = section.get("subsections") or {}
            if isinstance(subsections, dict):
                for name, subsection in subsections.items():
                    category = SUBSECTION_CATEGORY.get(name, name)
                    for fact in _facts_of(subsection):
                        yield {
                            "fact": fact,
                            "country": slug,
                            "category": category,
                            "scope": f"{slug}/{key}/{name}",
                            "section_key": key,
                            "subsection": name,
                            "instruction_id": None,
                        }
        for instruction_id in sorted(instructions):
            instruction = instructions[instruction_id]
            if slug not in (instruction.get("countries") or []):
                continue
            section_key = INSTRUCTION_SECTION.get(instruction_id)
            for index, step in enumerate(instruction.get("steps") or [], start=1):
                if not isinstance(step, dict):
                    continue
                step_n = step.get("n") or index
                yield {
                    "fact": step,
                    "country": slug,
                    "category": SECTION_CATEGORY.get(section_key, section_key or ""),
                    "scope": f"instruction/{instruction_id}/{step_n}",
                    "section_key": section_key,
                    "subsection": None,
                    "instruction_id": instruction_id,
                }


def check_urls(urls: Sequence[str], *, timeout: float = 10.0, workers: int = 6) -> Dict[str, Dict[str, Any]]:
    unique = list(dict.fromkeys(urls))
    if not unique:
        return {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(_fetch, url, timeout): url for url in unique}
        found = {}
        for future in as_completed(futures):
            url = futures[future]
            found[url] = future.result()
    return found


def _fetch(url: str, timeout: float) -> Dict[str, Any]:
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": "PayCompassFactCheck/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read(256)
            code = getattr(response, "status", None) or response.getcode()
            return {"url": url, "status_code": int(code), "error": None, "content_confirmed": False}
    except urllib.error.HTTPError as exc:
        return {"url": url, "status_code": int(exc.code), "error": None, "content_confirmed": False}
    except Exception as exc:  # noqa: BLE001 — report the failure, do not crash the run
        return {"url": url, "status_code": None, "error": exc.__class__.__name__, "content_confirmed": False}


def _route_matches(route: Dict[str, Any], scope: str, country: Optional[str]) -> bool:
    if scope != "country" or not country:
        return True
    if route.get("destination_slug") == country:
        return True
    return any(target.get("slug") == country for target in route.get("payment_targets") or [])


def _walk_route(route: Dict[str, Any]) -> tuple:
    ids: List[str] = []
    allowances: List[Dict[str, Any]] = []

    def take(spec: Any) -> None:
        if isinstance(spec, str):
            ids.append(spec)
        elif isinstance(spec, dict) and spec.get("rule") == "airport_change_allowance":
            allowances.append(spec)
            ids.extend(spec.get("driving_inputs") or [])
        elif isinstance(spec, dict) and spec.get("rule") in ("driving_summary", "transit_summary"):
            ids.extend(spec.get("inputs") or [])

    for spec in list(route.get("lead_facts") or []):
        take(spec)
    if route.get("airline_fact"):
        take(route["airline_fact"])
    for section in route.get("sections") or []:
        for spec in section.get("facts") or []:
            take(spec)
    return ids, allowances


def _transfer_topics(config: Dict[str, Any]) -> Dict[str, str]:
    return (config.get("volatility") or {}).get("transfer_topics") or {}


def transfer_rows(
    rules: Dict[str, Any],
    measurements: Dict[str, Any],
    routes: Sequence[Dict[str, Any]],
    config: Dict[str, Any],
    as_of: date,
    *,
    scope: str = "all",
    country: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Score airport, city, public-transport and taxi measurements with the live zone."""
    topics = _transfer_topics(config)
    selected: List[str] = []
    allowances: List[Dict[str, Any]] = []
    seen_rules = set()
    for route in routes:
        if not _route_matches(route, scope, country):
            continue
        ids, specs = _walk_route(route)
        for measurement_id in ids:
            measurement = measurements.get(measurement_id) or {}
            if measurement.get("transfer_topic") in topics and measurement_id not in selected:
                selected.append(measurement_id)
        for spec in specs:
            rule_id = spec.get("id")
            inputs = spec.get("inputs") or []
            if not rule_id or rule_id in seen_rules or not inputs:
                continue
            if all((measurements.get(item) or {}).get("transfer_topic") in topics for item in inputs):
                seen_rules.add(rule_id)
                allowances.append(spec)
    if scope != "country":
        for measurement_id, measurement in measurements.items():
            if measurement.get("transfer_topic") in topics and measurement_id not in selected:
                selected.append(measurement_id)
    built: Dict[str, Dict[str, Any]] = {}
    rows: List[Dict[str, Any]] = []
    for measurement_id in selected:
        measurement = measurements[measurement_id]
        fact = measurement_fact(measurement_id, measurement, rules, as_of)
        built[measurement_id] = fact
        rows.append(_transfer_row(measurement_id, fact, measurement, config, as_of))
    for spec in allowances:
        for measurement_id in spec["inputs"]:
            if measurement_id not in built:
                built[measurement_id] = measurement_fact(
                    measurement_id, measurements[measurement_id], rules, as_of
                )
        fact = allowance_fact(spec, built, rules, as_of)
        rows.append(_transfer_row(spec["id"], fact, {}, config, as_of))
    return rows


def _freshness_is_stale(fact: Dict[str, Any], config: Dict[str, Any]) -> bool:
    if is_gap(fact):
        return False
    breakdown = fact.get("score_breakdown")
    if not isinstance(breakdown, dict) or "freshness" not in breakdown:
        return False
    return int(breakdown["freshness"]) == int(open_freshness_band(config)["points"])


def _transfer_row(
    row_id: str,
    fact: Dict[str, Any],
    measurement: Dict[str, Any],
    config: Dict[str, Any],
    as_of: date,
) -> Dict[str, Any]:
    gap = is_gap(fact)
    resolved = {
        "kind": "gap" if gap else ("advice" if fact.get("fact_type") == "advice" else "scored"),
        "volatility_class": fact.get("volatility_class"),
        "at_risk": bool(fact.get("at_risk")) and not gap,
        "drops_on": fact.get("drops_on"),
        "owner_prompt": fact.get("owner_prompt"),
        "score_zone": fact.get("score_zone"),
    }
    row = {
        "id": row_id,
        "text": fact.get("text") or "",
        "zone": None if gap else fact.get("zone"),
        "gap": gap,
        "at_risk": bool(fact.get("at_risk")) and not gap,
        "stale": _freshness_is_stale(fact, config),
        "topic": measurement.get("transfer_topic"),
        "volatility_class": fact.get("volatility_class"),
    }
    row.update(auto_check_fields(fact, resolved, config, as_of, category=row["topic"]))
    return row


def summarize_transfers(rows: Sequence[Dict[str, Any]], config: Dict[str, Any]) -> Dict[str, Any]:
    display = config["display"]
    labels = display["transfer_report"]
    titles = display["zone_titles"]
    names = [name for name in display["group_order"] if zone_rank(name, config) is not None]
    counts = {name: 0 for name in names}
    gaps = 0
    at_risk = 0
    stale = 0
    for row in rows:
        if row["gap"]:
            gaps += 1
        elif row.get("zone") in counts:
            counts[row["zone"]] += 1
        if row["at_risk"]:
            at_risk += 1
        if row["stale"]:
            stale += 1
    return {
        "title": labels["title"],
        "by_zone_label": labels["by_zone"],
        "zones": [{"zone": name, "title": titles.get(name) or name, "count": counts[name]} for name in names],
        "at_risk_label": labels["at_risk"],
        "at_risk": at_risk,
        "stale_label": labels["stale"],
        "stale": stale,
        "gap_label": display["gap_label"],
        "gaps": gaps,
        "at_risk_rows": [row for row in rows if row["at_risk"]],
        "stale_rows": [row for row in rows if row["stale"]],
        "gap_rows": [row for row in rows if row["gap"]],
    }


def _route_bundle() -> tuple:
    return (
        load_json(MODEL_DIR / "rules.json"),
        load_json(MODEL_DIR / "measurements.json"),
        load_json(MODEL_DIR / "routes.json"),
    )


def build_report(
    *,
    as_of: Optional[date] = None,
    scope: str = "all",
    country: Optional[str] = None,
    check_http: bool = False,
    bundle: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
    http_by_url: Optional[Dict[str, Dict[str, Any]]] = None,
    route_rules: Optional[Dict[str, Any]] = None,
    route_measurements: Optional[Dict[str, Any]] = None,
    route_definitions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    as_of = as_of or date.today()
    bundle = bundle if bundle is not None else load_json(DATA_PATH)
    config = config if config is not None else load_json(CONFIG_PATH)
    records = list(iter_records(bundle, scope=scope, country=country))
    urls: List[str] = []
    for record in records:
        urls.extend(http_urls(record["fact"]))
    if check_http and http_by_url is None:
        http_by_url = check_urls(urls)
    elif http_by_url is None:
        http_by_url = {}
    facts = [
        assess_fact(
            record["fact"],
            config=config,
            as_of=as_of,
            scope=record["scope"],
            country=record["country"],
            category=record["category"],
            instruction_id=record["instruction_id"],
            section_key=record.get("section_key"),
            subsection=record.get("subsection"),
            http_by_url=http_by_url,
            check_http=check_http,
        )
        for record in records
    ]
    names = {slug: (bundle.get("countries") or {}).get(slug, {}).get("name") or slug for slug in COUNTRY_ORDER}
    summary = _summary(facts)
    if route_rules is None or route_measurements is None or route_definitions is None:
        loaded_rules, loaded_measurements, loaded_routes = _route_bundle()
        route_rules = loaded_rules if route_rules is None else route_rules
        route_measurements = loaded_measurements if route_measurements is None else route_measurements
        route_definitions = loaded_routes if route_definitions is None else route_definitions
    transfer_list = transfer_rows(
        route_rules,
        route_measurements,
        route_definitions,
        config,
        as_of,
        scope=scope,
        country=country,
    )
    transfers = summarize_transfers(transfer_list, config)
    transfers["auto_check"] = summarize_auto_checks(transfer_list, config)
    scope_label = "все страны" if scope == "all" else names.get(country or "", country or "")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "as_of": as_of.isoformat(),
        "scope": scope,
        "country": country,
        "scope_label": scope_label,
        "http_checked": bool(check_http),
        "rules": "config/trust_config.json",
        "upgrade_rule": {
            "downgrade": "automatic",
            "yellow_min_independent_confirmations": int(config["upgrade"]["yellow_min_independent_confirmations"]),
            "yellow": "automatic when independent fresh confirmations reach yellow_min_independent_confirmations",
            "green": "automatic only when an official publisher page opens and content_confirmed is true",
            "traveler_green": "owner_decision, prompt '{n} подтверждений, поднять до зелёного?'",
            "early_warning_share": config["early_warning"]["share"],
            "refresh_action": config["early_warning"]["refresh_action"],
        },
        "summary": summary,
        "auto_check": summarize_auto_checks(facts, config),
        "facts": facts,
        "transfers": transfers,
    }


def _summary(facts: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    def count(predicate) -> int:
        return sum(1 for fact in facts if predicate(fact))

    return {
        "checked": len(facts),
        "confirmed": count(lambda fact: fact["status"] == "ok"),
        "not_confirmed": count(lambda fact: fact["status"] == "fail"),
        "stale": count(lambda fact: fact["status"] == "stale"),
        "could_not_check": count(lambda fact: fact["status"] == "inconclusive"),
        "needs_owner_decision": count(lambda fact: "decision_needed" in fact["flags"]),
        "needs_owner_manual_check": count(lambda fact: "needs_owner_check" in fact["flags"]),
        "gaps": count(lambda fact: "gap" in fact["flags"]),
        "unknown_zone": count(lambda fact: "unknown_zone" in fact["flags"]),
        "no_public_source": count(lambda fact: "no_public_source" in fact["flags"]),
        "green_prompts": count(lambda fact: bool(fact.get("owner_prompt"))),
        "at_risk": count(lambda fact: fact.get("at_risk")),
        "refresh_search": count(lambda fact: fact.get("suggested_action") == "refresh_search"),
    }


def _yellow_upgrade_sentence(report: Dict[str, Any]) -> str:
    rule = report.get("upgrade_rule") or {}
    needed = rule.get("yellow_min_independent_confirmations")
    if needed is None:
        return ""
    return f"До жёлтого само — только при {needed} независимых свежих подтверждениях. "


def render_text(report: Dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "Отчёт проверки фактов",
        f"Дата расчёта: {report['as_of']}",
        f"Охват: {report['scope_label']}",
        "Данные не менялись. Зона в приложении считается при выдаче, записанная зона — только вход. "
        "Понижение в подсказках автоматическое. "
        + _yellow_upgrade_sentence(report)
        + "До зелёного само — только если сайт банка, оператора или ведомства открылся и текст сверен. "
        "Отзывы сами зелёный не ставят.",
        "",
        "Сводка",
        f"Проверено: {summary['checked']}",
        f"Сошлось: {summary['confirmed']}",
        f"Не сошлось: {summary['not_confirmed']}",
        f"Устарело: {summary['stale']}",
        f"Не смогли проверить: {summary['could_not_check']}",
        f"Нужно решение владельца: {summary['needs_owner_decision']}",
        f"Ручные проверки владельца: {summary['needs_owner_manual_check']}",
        f"Не исследовано: {summary['gaps']}",
        f"Без публичной ссылки: {summary['no_public_source']}",
        f"Внутренние пометки: {summary['unknown_zone']}",
        f"Вопросов «поднять до зелёного»: {summary['green_prompts']}",
        f"Скоро съедут: {summary['at_risk']}",
        f"Обновить поиск источника: {summary['refresh_search']}",
        "",
    ]
    lines.extend(_auto_lines(report.get("auto_check")))
    lines.extend(_transfer_lines(report))
    lines.extend(_section(report, "Не сошлось с формулой", lambda fact: fact["status"] == "fail"))
    lines.extend(_section(report, "Устарело: баллы не держат записанную зону", lambda fact: fact["status"] == "stale"))
    lines.extend(_section(report, "Не исследовано", lambda fact: "gap" in fact["flags"]))
    lines.extend(_section(report, "Без публичной ссылки", lambda fact: "no_public_source" in fact["flags"]))
    lines.extend(_section(report, "Внутренние пометки", lambda fact: "unknown_zone" in fact["flags"]))
    lines.extend(_section(report, "Нужно решение", lambda fact: "decision_needed" in fact["flags"]))
    lines.extend(_risk_lines(report))
    prompts = [fact for fact in report["facts"] if fact.get("owner_prompt")]
    lines.append("Поднять до зелёного?")
    if not prompts:
        lines.append("Таких повышений нет.")
    else:
        for fact in prompts:
            lines.append(f"- {fact['country']} · {fact['owner_prompt']} · {fact['text']}")
    lines.append("")
    refresh = [fact for fact in report["facts"] if fact.get("suggested_action") == "refresh_search"]
    lines.append("Обновить поиск источника")
    if not refresh:
        lines.append("Таких фактов нет.")
    else:
        for fact in refresh:
            lines.append(f"- [{fact['fact_id']}] {fact['country']} · {fact['current_zone']} · {fact['text']}")
    lines.append("")
    manual = [fact for fact in report["facts"] if "needs_owner_check" in fact["flags"]]
    lines.append("Ручные проверки владельца")
    if not manual:
        lines.append("Список пуст.")
    else:
        for index, fact in enumerate(manual, start=1):
            lines.append(
                f"{index}. [{fact['fact_id']}] {fact['country']} · {fact['category']} · {fact['current_zone']} · {fact.get('last_check_date') or 'без даты'}"
            )
            lines.append(f"   {fact['text']}")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _transfer_lines(report: Dict[str, Any]) -> List[str]:
    block = report.get("transfers")
    if not block:
        return []
    lines = [block["title"], block["by_zone_label"]]
    for item in block["zones"]:
        lines.append(f"{item['title']}: {item['count']}")
    lines.append(f"{block['at_risk_label']}: {block['at_risk']}")
    for row in block.get("at_risk_rows") or []:
        lines.append(f"- {row['text']}")
    lines.append(f"{block['stale_label']}: {block['stale']}")
    lines.append(f"{block['gap_label']}: {block['gaps']}")
    for row in block.get("gap_rows") or []:
        extra = row.get("auto_check_text")
        lines.append(f"- {row['text']}" + (f" · {extra}" if extra else ""))
    lines.extend(_auto_lines(block.get("auto_check")))
    if not block.get("auto_check"):
        lines.append("")
    return lines


def _risk_lines(report: Dict[str, Any]) -> List[str]:
    rows = [fact for fact in report["facts"] if fact.get("at_risk")]
    lines = ["Скоро съедут"]
    if not rows:
        lines.append("Таких фактов нет.")
    else:
        for fact in rows:
            shown = fact.get("computed_zone") or fact.get("current_zone")
            lines.append(
                f"- [{fact['fact_id']}] {shown} → {fact.get('next_zone') or '—'} · "
                f"{fact.get('drops_on') or 'без даты'} · {fact.get('at_risk_reason') or ''} · "
                f"{fact.get('auto_check_text') or ''}".rstrip(" ·")
            )
            lines.append(f"   {fact['text']}")
    lines.append("")
    return lines


def _section(report: Dict[str, Any], title: str, predicate) -> List[str]:
    rows = [fact for fact in report["facts"] if predicate(fact)]
    lines = [title]
    if not rows:
        lines.append("Нет.")
    else:
        for fact in rows:
            action = fact.get("suggested_action") or "—"
            suffix = f" · {fact['auto_check_text']}" if fact.get("auto_check_text") else ""
            lines.append(
                f"- {fact['country']} · {fact['category']} · {fact['current_zone']} → {fact.get('computed_zone') or '—'} · {action} · {fact['text']}{suffix}"
            )
    lines.append("")
    return lines


def format_telegram_messages(report: Dict[str, Any], run_url: str = "", *, limit: int = TELEGRAM_LIMIT) -> List[str]:
    summary = report["summary"]
    lines = [
        "Проверка фактов «Умный туризм»",
        f"Дата: {report['as_of']}",
        f"Охват: {report['scope_label']}",
        f"Проверено: {summary['checked']}",
        f"Сошлось: {summary['confirmed']}",
        f"Не сошлось: {summary['not_confirmed']}",
        f"Устарело: {summary['stale']}",
        f"Не смогли проверить: {summary['could_not_check']}",
        f"Нужно решение владельца: {summary['needs_owner_decision']}",
    ]
    lines.extend(line for line in _auto_lines(report.get("auto_check")) if line)
    block = report.get("transfers")
    if block:
        lines.append(block["title"])
        for item in block["zones"]:
            lines.append(f"{item['title']}: {item['count']}")
        lines.append(f"{block['at_risk_label']}: {block['at_risk']}")
        lines.append(f"{block['stale_label']}: {block['stale']}")
        lines.append(f"{block['gap_label']}: {block['gaps']}")
        lines.extend(line for line in _auto_lines(block.get("auto_check")) if line)
    if run_url:
        lines.append(f"Прогон: {run_url}")
    return split_telegram("\n".join(lines), run_url=run_url, limit=limit)


def split_telegram(text: str, *, run_url: str = "", limit: int = TELEGRAM_LIMIT) -> List[str]:
    link = f"Прогон: {run_url}" if run_url else ""
    if len(text) <= limit:
        return [text]
    parts: List[str] = []
    current = ""
    for line in text.split("\n"):
        piece = line if not current else current + "\n" + line
        if len(piece) <= limit:
            current = piece
            continue
        if current:
            parts.append(current)
        while len(line) > limit:
            parts.append(line[:limit])
            line = line[limit:]
        current = line
    if current:
        parts.append(current)
    if link and not any(link in part for part in parts):
        last = parts[-1]
        addition = "\n" + link
        if len(last) + len(addition) <= limit:
            parts[-1] = last + addition
        else:
            room = max(0, limit - len(addition))
            parts[-1] = last[:room].rstrip() + addition
    return parts


def workflow_run_url() -> str:
    explicit = (os.environ.get("FACT_CHECK_RUN_URL") or "").strip()
    if explicit:
        return explicit
    repo = (os.environ.get("GITHUB_REPOSITORY") or "").strip()
    run_id = (os.environ.get("GITHUB_RUN_ID") or "").strip()
    server = (os.environ.get("GITHUB_SERVER_URL") or "https://github.com").rstrip("/")
    if repo and run_id:
        return f"{server}/{repo}/actions/runs/{run_id}"
    return ""


def telegram_note(result: Dict[str, Any]) -> str:
    if result.get("sent"):
        return f"Сообщение отправлено в Telegram, chat_id {result.get('chat_id')}, частей: {result.get('parts')}."
    if result.get("secret"):
        return (
            f"Секрет {result['secret']} не задан. Сообщение владельцу в Telegram не отправлено. "
            f"Добавьте секрет {TELEGRAM_SECRET_NAME} в GitHub Actions: Settings → Secrets and variables → Actions. "
            f"Необязательный секрет {CHAT_SECRET_NAME}; если его нет, используется чат {DEFAULT_OWNER_CHAT_ID}."
        )
    return f"Telegram не отправлен: {result.get('error') or 'неизвестная ошибка'}."


def deliver_telegram(report: Dict[str, Any], *, token: str, chat_id: str, run_url: str, send) -> Dict[str, Any]:
    messages = format_telegram_messages(report, run_url)
    if not (token or "").strip():
        return {"sent": False, "secret": TELEGRAM_SECRET_NAME, "messages": messages}
    target = (chat_id or "").strip() or DEFAULT_OWNER_CHAT_ID
    try:
        for message in messages:
            send(token.strip(), target, message)
    except Exception as exc:  # noqa: BLE001 — delivery must not hide the report
        return {"sent": False, "error": exc.__class__.__name__, "chat_id": target, "messages": messages}
    return {"sent": True, "chat_id": target, "parts": len(messages), "messages": messages}


def send_telegram_message(token: str, chat_id: str, text: str) -> None:
    payload = json.dumps({"chat_id": chat_id, "text": text, "disable_web_page_preview": True}).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        body = json.loads(response.read().decode("utf-8"))
    if not body.get("ok"):
        raise RuntimeError("telegram_not_ok")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only fact-check report")
    parser.add_argument("--scope", default=os.environ.get("FACT_CHECK_SCOPE") or "all", choices=("all", "country"))
    parser.add_argument("--country", default=os.environ.get("FACT_CHECK_COUNTRY") or "")
    parser.add_argument("--as-of", default="")
    parser.add_argument("--json", dest="json_path", default="")
    parser.add_argument("--text", dest="text_path", default="")
    parser.add_argument("--http", dest="check_http", action="store_true")
    parser.add_argument("--no-http", dest="check_http", action="store_false")
    parser.set_defaults(check_http=False)
    parser.add_argument("--send-telegram", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    country = (args.country or "").strip() or None
    if args.scope == "country":
        if not country or not all(char.islower() or char.isdigit() or char == "_" for char in country):
            print("Для scope=country нужен slug страны латиницей, например georgia.", file=sys.stderr)
            return 2
    as_of = parse_date(args.as_of) if args.as_of else date.today()
    if args.as_of and as_of is None:
        print("Дата --as-of должна быть в виде YYYY-MM-DD.", file=sys.stderr)
        return 2
    report = build_report(as_of=as_of, scope=args.scope, country=country, check_http=args.check_http)
    if args.scope == "country" and report["summary"]["checked"] == 0:
        print(f"Страна {country} в справочнике не найдена.", file=sys.stderr)
        return 2
    telegram = {"sent": False, "error": "not_requested"}
    if args.send_telegram:
        telegram = deliver_telegram(
            report,
            token=os.environ.get(TELEGRAM_SECRET_NAME) or "",
            chat_id=os.environ.get(CHAT_SECRET_NAME) or "",
            run_url=workflow_run_url(),
            send=send_telegram_message,
        )
    text = render_text(report)
    if args.send_telegram:
        text = text + "\nTelegram\n" + telegram_note(telegram) + "\n"
    sys.stdout.write(text)
    if args.text_path:
        Path(args.text_path).write_text(text, encoding="utf-8")
    if args.json_path:
        Path(args.json_path).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
