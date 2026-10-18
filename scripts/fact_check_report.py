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
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.knowledge_base import SECTION_ORDER, public_source_url  # noqa: E402
from database.miniapp_catalog import _fact_id  # noqa: E402

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
ZONE_RANK = {"black": 0, "red": 1, "yellow": 2, "green": 3}
ACTIONS = (
    "downgrade",
    "fix_link",
    "upgrade_candidate",
    "rerun",
    "owner_decision",
    "owner_manual_check",
)

# Hosts that count as a bank, operator, or government site for a green upgrade.
# A source_kind of "official" is not enough: guide sites were tagged that way.
_PUBLISHER_SUFFIXES = (
    "rshb.ru",
    "atb.su",
    "vtb.ru",
    "tbank.ru",
    "tinkoff.ru",
    "sberbank.ru",
    "tbcbank.ge",
    "octopus.com.hk",
    "mts.ru",
    "magticom.ge",
    "wechat.com",
    "tencent.com",
    "qq.com",
    "alipay.com",
    "true.th",
    "rta.ae",
    "planetpayment.ae",
    "planettaxfree.ae",
    "taxfree.weareplanet.com",
    "istairport.com",
    "tbilisiairport.com",
    "cbr.ru",
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


def fresh_limit_days(config: Dict[str, Any]) -> int:
    finite = [band["max_days"] for band in config["freshness_points"] if band.get("max_days") is not None]
    return min(finite) if finite else 30


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


def host_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def is_official_publisher(url: str) -> bool:
    """Bank, operator, or government site. Guide blogs do not qualify."""
    host = host_of(url)
    if not host:
        return False
    if host.endswith(".gov") or ".gov." in f".{host}" or host.endswith(".go.th") or host.endswith(".go.jp"):
        return True
    bare = host[4:] if host.startswith("www.") else host
    return any(bare == suffix or bare.endswith("." + suffix) for suffix in _PUBLISHER_SUFFIXES)


def http_urls(fact: Dict[str, Any]) -> List[str]:
    found: List[str] = []
    source = fact.get("source")
    if isinstance(source, str):
        for token in source.split():
            if token.startswith("http://") or token.startswith("https://"):
                found.append(token)
    seen = set()
    unique = []
    for url in found:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


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


def confirmation_stats(fact: Dict[str, Any], as_of: date, fresh_days: int) -> Dict[str, Any]:
    """Count distinct fresh confirmations.

    A bare `reports` integer is not proof that the people or outlets differ.
    """
    items = fact.get("confirmations")
    reports = fact.get("reports") if isinstance(fact.get("reports"), int) else 0
    if not isinstance(items, list) or not items:
        moment = fact_date(fact)
        age = age_days(moment, as_of)
        fresh = age is not None and 0 <= age <= fresh_days
        return {"count": reports, "fresh_count": reports if fresh else 0, "independent": False}
    keys = []
    fresh_keys = []
    for item in items:
        if not isinstance(item, dict):
            continue
        key = _outlet_key(item)
        if key is None:
            continue
        keys.append(key)
        moment = parse_date(item.get("date"))
        age = age_days(moment, as_of)
        if age is not None and 0 <= age <= fresh_days:
            fresh_keys.append(key)
    distinct = list(dict.fromkeys(keys))
    fresh_distinct = list(dict.fromkeys(fresh_keys))
    return {"count": len(distinct), "fresh_count": len(fresh_distinct), "independent": True}


def _rank(zone: Optional[str]) -> Optional[int]:
    if zone not in ZONE_RANK:
        return None
    return ZONE_RANK[zone]


def assess_fact(
    fact: Dict[str, Any],
    *,
    config: Dict[str, Any],
    as_of: date,
    scope: str,
    country: str,
    category: str,
    instruction_id: Optional[str] = None,
    http_by_url: Optional[Dict[str, Dict[str, Any]]] = None,
    check_http: bool = False,
) -> Dict[str, Any]:
    text = fact.get("text") or ""
    current = fact.get("zone")
    kind = fact.get("source_kind")
    agreement = fact.get("agreement")
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
        "flags": flags,
    }

    if gap:
        base["reason"] = "Не исследовано: балл не ставится."
        base["suggested_action"] = "owner_decision"
        return _finalize_http(base, flags)
    if fact.get("fact_type") == "advice" or current == "advice-unsupported":
        base["reason"] = "Совет: зона берётся из опор, формула баллов к нему не применяется."
        if fact.get("needs_owner_check"):
            base["suggested_action"] = "owner_manual_check"
        elif fact.get("decision_needed"):
            base["suggested_action"] = "owner_decision"
        return _finalize_http(base, flags)

    points = source_points(kind if isinstance(kind, str) else None, fact.get("reports"), config)
    if points is None or agreement not in ("agree", "conflict"):
        base["reason"] = "Не хватает типа источника или пометки согласия, зону по формуле не посчитать."
        base["suggested_action"] = "rerun"
        return _finalize_http(base, flags)

    fresh = freshness_points(days, config)
    agree_points = int(config["agreement_points"][agreement])
    score = points + fresh + agree_points
    score_zone = zone_for_score(score, config)
    computed = score_zone
    if fact.get("refuted"):
        computed = config["refuted_zone"]
    elif fact.get("contradicted_by_own"):
        cap = config["contradicted_by_own_zone"]
        if _rank(score_zone) is not None and _rank(cap) is not None and _rank(score_zone) > _rank(cap):
            computed = cap
    elif fact.get("verified_by_us"):
        limit = int(config["verified_by_us_max_days"])
        if days is not None and 0 <= days <= limit:
            computed = config["verified_by_us_zone"]
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

    current_rank = _rank(current)
    computed_rank = _rank(computed)
    score_rank = _rank(score_zone)
    if current_rank is None or computed_rank is None:
        base["status"] = "inconclusive"
        base["reason"] = "Записанная зона вне шкалы green/yellow/red/black."
        base["suggested_action"] = "rerun"
        return _finalize_http(base, flags)
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
    base["suggested_action"] = action
    base["automatic"] = automatic
    base["upgrade_to"] = upgrade_to
    base["owner_prompt"] = prompt
    base["reason"] = reason
    if action == "owner_decision" and prompt:
        flags.append("traveler_green_needs_owner")
    return _finalize_http(base, flags)


def _finalize_http(row: Dict[str, Any], flags: List[str]) -> Dict[str, Any]:
    for result in row["http_results"]:
        code = result.get("status_code")
        error = result.get("error")
        if error and error != "not_checked":
            flags.append("http_inconclusive")
        elif isinstance(code, int) and code >= 400 and code not in (401, 403):
            flags.append("http_failed")
        elif isinstance(code, int) and code in (401, 403):
            flags.append("http_blocked")
    row["flags"] = sorted(set(flags))
    if row["suggested_action"] is not None and row["suggested_action"] not in ACTIONS:
        raise RuntimeError(f"unexpected action {row['suggested_action']}")
    return row


def _page_opened(results: Sequence[Dict[str, Any]]) -> bool:
    return any(isinstance(item.get("status_code"), int) and 200 <= item["status_code"] < 300 for item in results)


def _page_confirms(results: Sequence[Dict[str, Any]]) -> bool:
    return any(item.get("content_confirmed") and isinstance(item.get("status_code"), int) and 200 <= item["status_code"] < 300 for item in results)


def _http_broken(results: Sequence[Dict[str, Any]]) -> bool:
    return any(isinstance(item.get("status_code"), int) and item["status_code"] in (404, 410) for item in results)


def _http_retry(results: Sequence[Dict[str, Any]]) -> bool:
    for item in results:
        code = item.get("status_code")
        error = item.get("error")
        if error and error != "not_checked":
            return True
        if isinstance(code, int) and (code >= 500 or code == 429):
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
    current_rank = _rank(current)
    computed_rank = _rank(computed)
    fresh_days = fresh_limit_days(config)
    stats = confirmation_stats(fact, as_of, fresh_days)
    official_urls = [url for url in urls if is_official_publisher(url)]
    traveler_only = fact.get("source_kind") == "traveler" and not official_urls
    count_for_prompt = stats["fresh_count"] if stats["independent"] else stats["count"]
    green_prompt = f"{count_for_prompt} подтверждений, поднять до зелёного?"

    if current_rank is not None and computed_rank is not None and current_rank > computed_rank:
        return (
            "downgrade",
            True,
            None,
            None,
            f"Записана зона {current}, формула на {as_of.isoformat()} даёт {computed}. Понижение автоматическое.",
        )

    raise_green = traveler_only and score_zone == "green" and current_rank is not None and current_rank < ZONE_RANK["green"]
    auto_yellow = (
        stats["independent"]
        and stats["fresh_count"] >= 3
        and current_rank is not None
        and current_rank < ZONE_RANK["yellow"]
        and _rank(score_zone) is not None
        and _rank(score_zone) >= ZONE_RANK["yellow"]
    )
    if raise_green and auto_yellow:
        return (
            "upgrade_candidate",
            True,
            "yellow",
            green_prompt,
            "Три независимых свежих подтверждения позволяют поднять только до жёлтого. "
            + green_prompt,
        )
    if raise_green:
        why = "Независимость людей и площадок в данных не размечена, поэтому жёлтый сам не ставится. " if not stats["independent"] else ""
        return ("owner_decision", False, None, green_prompt, why + green_prompt)

    if official_urls and score_zone == "green" and current_rank is not None and current_rank < ZONE_RANK["green"]:
        if _page_confirms(http_results):
            return (
                "upgrade_candidate",
                True,
                "green",
                None,
                "Официальная страница открылась и сверка текста разрешена. Повышение до зелёного автоматическое.",
            )
        if check_http and _page_opened(http_results):
            return (
                "owner_manual_check",
                False,
                None,
                None,
                "Официальная страница открылась. Текст факта со страницей не сверен, до зелёного автоматически не поднимаем.",
            )
        if check_http and _http_broken(http_results):
            return ("fix_link", False, None, None, "Официальная ссылка не открывается.")
        if check_http and _http_retry(http_results):
            return ("rerun", False, None, None, "Официальную страницу не удалось прочитать, прогон нужно повторить.")
        if not check_http:
            return ("rerun", False, None, None, "Чтобы решить зелёный, нужно открыть официальную страницу. В этом прогоне HTTP выключен.")

    if (
        stats["independent"]
        and stats["fresh_count"] >= 3
        and current_rank is not None
        and current_rank < ZONE_RANK["yellow"]
        and _rank(score_zone) is not None
        and _rank(score_zone) >= ZONE_RANK["yellow"]
    ):
        return (
            "upgrade_candidate",
            True,
            "yellow",
            None,
            "Три независимых свежих подтверждения. Повышение до жёлтого автоматическое. До зелёного этот порог не дотягивает.",
        )

    if traveler_only and current == "green" and score_zone == "green":
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
    if fact.get("verified_by_us") and _rank(score_zone) is not None and current_rank is not None and _rank(score_zone) < current_rank:
        return (
            "owner_manual_check",
            False,
            None,
            None,
            f"По баллам зона {score_zone} (сумма без надбавки). В файле {current} из-за «проверено нами».",
        )
    if not public_source_url(fact) and current in ("green", "yellow") and fact.get("source_kind") != "internal":
        return ("fix_link", False, None, None, "На карточке, которую видно сразу, нет публичной ссылки.")
    if _http_broken(http_results):
        return ("fix_link", False, None, None, "Ссылка источника отвечает 404 или 410.")
    if _http_retry(http_results):
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
                            "instruction_id": None,
                        }
        for instruction_id in sorted(instructions):
            instruction = instructions[instruction_id]
            if slug not in (instruction.get("countries") or []):
                continue
            section_key = {
                "mts_tr_qr": "2_pay_on_site",
                "tbank_qr_abroad": "2_pay_on_site",
                "mts_china_wallets": "3_local_wallets_cards",
                "vtb_china_wallets": "3_local_wallets_cards",
                "wechat_pay": "3_local_wallets_cards",
                "alipay": "3_local_wallets_cards",
                "tbc_georgia": "3_local_wallets_cards",
            }.get(instruction_id, "pay_on_site")
            for index, step in enumerate(instruction.get("steps") or [], start=1):
                if not isinstance(step, dict):
                    continue
                step_n = step.get("n") or index
                yield {
                    "fact": step,
                    "country": slug,
                    "category": SECTION_CATEGORY.get(section_key, section_key),
                    "scope": f"instruction/{instruction_id}/{step_n}",
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


def build_report(
    *,
    as_of: Optional[date] = None,
    scope: str = "all",
    country: Optional[str] = None,
    check_http: bool = False,
    bundle: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
    http_by_url: Optional[Dict[str, Dict[str, Any]]] = None,
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
            http_by_url=http_by_url,
            check_http=check_http,
        )
        for record in records
    ]
    names = {slug: (bundle.get("countries") or {}).get(slug, {}).get("name") or slug for slug in COUNTRY_ORDER}
    summary = _summary(facts)
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
            "yellow": "automatic when at least 3 independent fresh confirmations",
            "green": "automatic only when an official publisher page opens and content_confirmed is true",
            "traveler_green": "owner_decision, prompt '{n} подтверждений, поднять до зелёного?'",
        },
        "summary": summary,
        "facts": facts,
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
    }


def render_text(report: Dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "Отчёт проверки фактов",
        f"Дата расчёта: {report['as_of']}",
        f"Охват: {report['scope_label']}",
        "Данные не менялись. Понижение в подсказках автоматическое. "
        "До жёлтого само — только при 3 независимых свежих подтверждениях. "
        "До зелёного само — только если сайт банка, оператора или ведомства открылся и текст сверен. "
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
        "",
    ]
    lines.extend(_section(report, "Не сошлось с формулой", lambda fact: fact["status"] == "fail"))
    lines.extend(_section(report, "Устарело: баллы не держат записанную зону", lambda fact: fact["status"] == "stale"))
    lines.extend(_section(report, "Не исследовано", lambda fact: "gap" in fact["flags"]))
    lines.extend(_section(report, "Без публичной ссылки", lambda fact: "no_public_source" in fact["flags"]))
    lines.extend(_section(report, "Внутренние пометки", lambda fact: "unknown_zone" in fact["flags"]))
    lines.extend(_section(report, "Нужно решение", lambda fact: "decision_needed" in fact["flags"]))
    prompts = [fact for fact in report["facts"] if fact.get("owner_prompt")]
    lines.append("Поднять до зелёного?")
    if not prompts:
        lines.append("Таких повышений нет.")
    else:
        for fact in prompts:
            lines.append(f"- {fact['country']} · {fact['owner_prompt']} · {fact['text']}")
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


def _section(report: Dict[str, Any], title: str, predicate) -> List[str]:
    rows = [fact for fact in report["facts"] if predicate(fact)]
    lines = [title]
    if not rows:
        lines.append("Нет.")
    else:
        for fact in rows:
            action = fact.get("suggested_action") or "—"
            lines.append(
                f"- {fact['country']} · {fact['category']} · {fact['current_zone']} → {fact.get('computed_zone') or '—'} · {action} · {fact['text']}"
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
