"""Apply community rules to stored reviews and the public catalog."""

from __future__ import annotations

import base64
import copy
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from database.community import (
    apply_community_state,
    apply_owner_action,
    author_level_weight,
    badge_weight,
    clean_review_fields,
    community_badge,
    confirmation_items,
    due_recheck_reminders,
    estimate_tg_age_days,
    freshness_window,
    helped_count,
    level_row,
    links_replacing,
    message,
    plan_intake,
    public_community_form,
    recheck_award,
    refute_spike,
    require_community,
    suggest_facts,
    telegram_nick,
    verdict_for_result,
)
from database.community_photo import redact_bytes
from database.community_store import get_community_store, new_id
from database.config_error import ConfigError
from database.knowledge_base import fact_on_request, is_gap, load_trust_config
from database.miniapp_catalog import find_fact, known_country_slugs, source_facts_by_id
from database.repositories.users import UserRepository
from database.trust_zones import resolve_zone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> date:
    return date.today()


def _state(store: Any) -> Dict[str, List[Dict[str, Any]]]:
    return store.snapshot()


def _fact_samples(state: Dict[str, Any], fact_id: Optional[str], field: str) -> List[Any]:
    if not fact_id:
        return []
    by_review = {row.get("id"): row for row in state["reviews"]}
    values = []
    for link in state["links"]:
        if link.get("fact_id") != fact_id or not link.get("counted"):
            continue
        review = by_review.get(link.get("review_id"))
        if review and review.get(field) is not None:
            values.append(review.get(field))
    return values


def _history(state: Dict[str, Any], user_id: Any) -> List[Dict[str, Any]]:
    links_by_review: Dict[Any, List[Dict[str, Any]]] = {}
    for link in state["links"]:
        links_by_review.setdefault(link.get("review_id"), []).append(link)
    rows = []
    for review in state["reviews"]:
        if str(review.get("user_id")) != str(user_id):
            continue
        copy_row = dict(review)
        linked = links_by_review.get(review.get("id")) or []
        if linked:
            copy_row["fact_id"] = linked[0].get("fact_id")
        rows.append(copy_row)
    return rows


def _voters(state: Dict[str, Any], fact_id: Optional[str]) -> List[Any]:
    if not fact_id:
        return []
    found = []
    for link in state["links"]:
        if link.get("fact_id") == fact_id and link.get("counted"):
            found.append(link.get("user_id"))
    return found


def submit_review(
    *,
    user_id: Any,
    init_data: str,
    payload: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
    as_of: Optional[date] = None,
    store: Any = None,
) -> Dict[str, Any]:
    config = config or load_trust_config()
    community = require_community(config)
    store = store or get_community_store()
    as_of = as_of or _today()
    fields = clean_review_fields(payload, config, as_of)
    if fields["country"] not in known_country_slugs():
        raise ValueError(message(config, "bad_field"))
    source = None
    if fields["fact_id"]:
        source = source_facts_by_id().get(fields["fact_id"])
        if source is None or find_fact(fields["fact_id"]) is None:
            raise ValueError(message(config, "fact_missing"))
    photo = _take_photo(payload, config, store)
    state = _state(store)
    window = None
    if source:
        window = freshness_window(source["fact"], config, **_context(source))
    review = {
        "id": new_id(),
        "user_id": user_id,
        "nick": telegram_nick(init_data, config),
        "photo_path": photo.get("path"),
        "photo_redaction_status": photo.get("status"),
        "antifraud_flags": [],
        "created_at": _now(),
        "moderated_at": None,
        "recheck_reminded_at": None,
        "status": community["statuses"]["pending"],
        **fields,
    }
    age = estimate_tg_age_days(user_id, config, as_of)
    from database.community import linked_voters

    voters = _voters(state, fields["fact_id"])
    linked = linked_voters(user_id, community["antifraud"]["linked_account_groups"], voters)
    flags = []
    from database.community import antifraud_flags

    flags = antifraud_flags(
        review,
        _history(state, user_id),
        config,
        as_of=as_of,
        age_days=age,
        window_days=window,
        linked_user_ids=voters,
        amount_samples=_fact_samples(state, fields["fact_id"], "amount"),
        fee_samples=_fact_samples(state, fields["fact_id"], "fee"),
    )
    if linked:
        flag_name = community["antifraud"]["flag_names"]["linked"]
        if flag_name not in flags:
            flags.append(flag_name)
    review["antifraud_flags"] = flags
    verdict = verdict_for_result(fields["result"], config) if fields["fact_id"] else None
    tentative_counted = not flags and community["moderation"]["mode"] == community["moderation"]["disputes_only_mode"]
    link = None
    if fields["fact_id"] and verdict:
        link = {
            "id": new_id(),
            "review_id": review["id"],
            "fact_id": fields["fact_id"],
            "user_id": user_id,
            "verdict": verdict,
            "verdict_source": community["verdict_sources"]["auto"],
            "counted": tentative_counted,
            "weight": badge_weight(review, verdict, config),
            "not_counted_reason": None,
            "created_at": review["created_at"],
        }
    projected_links = links_replacing(state["links"], link, config) if link else list(state["links"])
    projected_reviews = list(state["reviews"]) + [review]
    spike = False
    conflict = False
    if link and tentative_counted and source:
        applied = apply_community_state(
            source["fact"],
            projected_links,
            projected_reviews,
            config,
            fact_id=fields["fact_id"],
            as_of=as_of,
            window_days=window,
        )
        conflict = applied["conflict"]
        spike = refute_spike(
            projected_links,
            projected_reviews,
            config,
            fact_id=fields["fact_id"],
            as_of=as_of,
        )
    intake = plan_intake(
        has_fact=bool(fields["fact_id"]),
        flags=flags,
        spike=spike,
        official_conflict=conflict,
        config=config,
    )
    review["status"] = intake["status"]
    if intake["counted"]:
        review["moderated_at"] = review["created_at"]
    if link:
        link["counted"] = bool(intake["counted"])
        link["not_counted_reason"] = None if intake["counted"] else intake["reason"]
        if intake["counted"]:
            for previous in links_replacing(state["links"], link, config):
                if previous.get("id") == link["id"]:
                    continue
                if previous.get("not_counted_reason") == community["not_counted_reasons"]["replaced"]:
                    store.update_link(previous["id"], {
                        "counted": False,
                        "not_counted_reason": previous["not_counted_reason"],
                    })
    store.insert_review(_stored_review(review))
    if link:
        store.insert_link(link)
    open_status = community["queue"]["statuses"]["open"]
    for item in intake["queue"]:
        store.insert_queue({
            "id": new_id(),
            "kind": item["kind"],
            "trigger": item["trigger"],
            "target_id": review["id"],
            "status": open_status,
            "decision": None,
            "decided_at": None,
        })
    notices = []
    if intake["counted"] and link and fields["fact_id"]:
        notices.extend(_after_counted(store, review, fields["fact_id"], config, as_of))
    for item in intake["queue"]:
        notices.append({
            "kind": "moderation_queue",
            "text": message(config, "moderation_queue").format(
                kind=item["kind"] or "",
                trigger=item["trigger"] or "",
            ),
            "screen": "moderation",
        })
    _deliver(notices)
    return _public_review(review, link, config, photo_note=photo.get("note"))


def _after_counted(store: Any, review: Dict[str, Any], fact_id: str, config: Dict[str, Any], as_of: date) -> List[Dict[str, Any]]:
    state = _state(store)
    notices = []
    award = recheck_award(review, state["reviews"], state["links"], config, fact_id=fact_id)
    if award:
        stored = store.insert_achievement({
            "user_id": award["user_id"],
            "code": award["code"],
            "scope": award["scope"],
            "review_id": award["review_id"],
            "awarded_at": _now(),
        })
        if stored.get("review_id") == review.get("id"):
            notices.append({
                "kind": "achievement",
                "user_id": review.get("user_id"),
                "text": message(config, "achievement").format(title=award["title"]),
                "screen": "profile",
            })
    source = source_facts_by_id().get(fact_id)
    if source:
        window = freshness_window(source["fact"], config, **_context(source))
        applied = apply_community_state(
            source["fact"],
            state["links"],
            state["reviews"],
            config,
            fact_id=fact_id,
            as_of=as_of,
            window_days=window,
        )
        open_status = config["community"]["queue"]["statuses"]["open"]
        for item in applied["disputes"]:
            store.insert_queue({
                "id": new_id(),
                "kind": item["kind"],
                "trigger": item["trigger"],
                "target_id": review["id"],
                "status": open_status,
                "decision": None,
                "decided_at": None,
            })
            notices.append({
                "kind": "moderation_queue",
                "text": message(config, "moderation_queue").format(
                    kind=item["kind"] or "",
                    trigger=item["trigger"] or "",
                ),
                "screen": "moderation",
            })
    fresh = _state(store)
    row = level_row(review.get("user_id"), fresh["reviews"], fresh["links"], fresh["views"], config, now=_now())
    store.upsert_level(row)
    if row["helped_count"]:
        notices.append({
            "kind": "helped",
            "user_id": review.get("user_id"),
            "text": message(config, "helped").format(n=row["helped_count"]),
            "screen": "profile",
        })
    return notices


def decide(
    *,
    owner_id: Any,
    queue_id: str,
    action: str,
    verdict: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    as_of: Optional[date] = None,
    store: Any = None,
) -> Dict[str, Any]:
    config = config or load_trust_config()
    require_community(config)
    if not UserRepository.is_admin(int(owner_id)):
        raise PermissionError(message(config, "not_owner"))
    store = store or get_community_store()
    as_of = as_of or _today()
    state = _state(store)
    item = next((row for row in state["queue"] if str(row.get("id")) == str(queue_id)), None)
    if item is None or item.get("status") != config["community"]["queue"]["statuses"]["open"]:
        raise ValueError(message(config, "queue_missing"))
    review = next((row for row in state["reviews"] if str(row.get("id")) == str(item.get("target_id"))), None)
    if review is None:
        raise ValueError(message(config, "queue_missing"))
    result = apply_owner_action(review, state["links"], action, config, now=_now(), verdict=verdict)
    store.update_review(review["id"], {
        "status": result["review"]["status"],
        "moderated_at": result["review"].get("moderated_at"),
    })
    for link in result["links"]:
        store.update_link(link["id"], {
            "counted": link.get("counted"),
            "verdict": link.get("verdict"),
            "verdict_source": link.get("verdict_source"),
            "not_counted_reason": link.get("not_counted_reason"),
            "weight": link.get("weight"),
        })
    store.update_queue(item["id"], {
        "status": config["community"]["queue"]["statuses"]["closed"],
        "decision": result["decision"],
        "decided_at": _now(),
    })
    notices = []
    counted_link = next((link for link in result["links"] if link.get("counted")), None)
    if counted_link:
        notices.extend(_after_counted(store, result["review"], counted_link["fact_id"], config, as_of))
    _deliver(notices)
    return {"queue_id": item["id"], "decision": result["decision"], "status": result["review"]["status"]}


def list_queue(*, owner_id: Any, config: Optional[Dict[str, Any]] = None, store: Any = None) -> Dict[str, Any]:
    config = config or load_trust_config()
    require_community(config)
    if not UserRepository.is_admin(int(owner_id)):
        raise PermissionError(message(config, "not_owner"))
    store = store or get_community_store()
    state = _state(store)
    open_status = config["community"]["queue"]["statuses"]["open"]
    reviews = {row.get("id"): row for row in state["reviews"]}
    cards = []
    for item in state["queue"]:
        if item.get("status") != open_status:
            continue
        review = reviews.get(item.get("target_id"))
        if not review:
            continue
        links = [link for link in state["links"] if link.get("review_id") == review.get("id")]
        fact = None
        fact_text = ""
        if links:
            fact = find_fact(links[0].get("fact_id"))
            fact_text = (fact or {}).get("text") or ""
        elif review.get("fact_id"):
            fact = find_fact(review.get("fact_id"))
            fact_text = (fact or {}).get("text") or ""
        cards.append({
            "id": item.get("id"),
            "kind": item.get("kind"),
            "trigger": item.get("trigger"),
            "verdict": links[0].get("verdict") if links else None,
            "flags": list(review.get("antifraud_flags") or []),
            "fact_text": fact_text,
            "fact_id": links[0].get("fact_id") if links else review.get("fact_id"),
            "review": _owner_review(review),
            "actions": dict(config["community"]["actions"]),
            "verdicts": list(config["community"]["verdicts"]),
        })
    return {"items": cards, "mode": config["community"]["moderation"]["mode"]}


def record_view(
    *,
    user_id: Any,
    fact_id: str,
    config: Optional[Dict[str, Any]] = None,
    store: Any = None,
) -> Dict[str, Any]:
    config = config or load_trust_config()
    require_community(config)
    if find_fact(fact_id) is None:
        raise ValueError(message(config, "fact_missing"))
    store = store or get_community_store()
    store.insert_view({
        "fact_id": fact_id,
        "user_id": user_id,
        "first_seen_at": _now(),
    })
    state = _state(store)
    authors = set()
    for link in state["links"]:
        if link.get("fact_id") != fact_id or not link.get("counted"):
            continue
        review = next((row for row in state["reviews"] if row.get("id") == link.get("review_id")), None)
        if review:
            authors.add(review.get("user_id"))
    for author in authors:
        row = level_row(author, state["reviews"], state["links"], state["views"], config, now=_now())
        store.upsert_level(row)
    return {"ok": True}


def author_public(user_id: Any, config: Optional[Dict[str, Any]] = None, store: Any = None) -> Dict[str, Any]:
    config = config or load_trust_config()
    community = require_community(config)
    store = store or get_community_store()
    state = _state(store)
    helped = helped_count(user_id, state["reviews"], state["links"], state["views"], config)
    title = community["achievements"]["recheck_month"]["title"]
    code = community["achievements"]["recheck_month"]["code"]
    achievements = []
    for row in state["achievements"]:
        if str(row.get("user_id")) != str(user_id):
            continue
        achievements.append({
            "code": row.get("code"),
            "scope": row.get("scope"),
            "title": title if row.get("code") == code else row.get("code"),
        })
    template = community.get("helped_template") or ""
    return {
        "helped_count": helped,
        "helped_text": template.format(n=helped) if template else str(helped),
        "achievements": achievements,
        "is_owner": UserRepository.is_admin(int(user_id)),
    }


def my_reviews(user_id: Any, store: Any = None) -> List[Dict[str, Any]]:
    store = store or get_community_store()
    state = _state(store)
    rows = []
    for review in state["reviews"]:
        if str(review.get("user_id")) != str(user_id):
            continue
        link = next((item for item in state["links"] if item.get("review_id") == review.get("id")), None)
        rows.append(_public_review(review, link, load_trust_config()))
    return rows


def suggest(*, country: str, city: str, topic: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = config or load_trust_config()
    from database.miniapp_catalog import get_catalog

    facts = _flat_facts(get_catalog())
    return {"facts": [
        {"id": fact["id"], "text": fact.get("text") or "", "zone": fact.get("zone")}
        for fact in suggest_facts(facts, config, country=country, city=city, topic=topic)
    ]}


def enrich_catalog(catalog: Dict[str, Any], config: Optional[Dict[str, Any]] = None, store: Any = None, as_of: Optional[date] = None) -> Dict[str, Any]:
    config = config or load_trust_config()
    require_community(config)
    store = store or get_community_store()
    as_of = as_of or _today()
    payload = copy.deepcopy(catalog)
    payload["community"] = public_community_form(config)
    state = _state(store)
    sources = source_facts_by_id()
    links = state["links"]
    reviews = state["reviews"]

    def visit(fact: Dict[str, Any]) -> None:
        fact_id = fact.get("id")
        source = sources.get(fact_id)
        window = None
        if source:
            window = freshness_window(source["fact"], config, **_context(source))
        fact_links = [link for link in links if link.get("fact_id") == fact_id]
        badge = None
        if fact_links and window is not None:
            badge = community_badge(
                fact_links,
                reviews,
                config,
                fact_id=fact_id,
                as_of=as_of,
                window_days=window,
            )
        fact["community_badge"] = badge
        if not source or not any(link.get("counted") for link in fact_links):
            return
        applied = apply_community_state(
            source["fact"],
            fact_links,
            reviews,
            config,
            fact_id=fact_id,
            as_of=as_of,
            window_days=window,
        )
        resolved = resolve_zone(
            applied["fact"],
            config=config,
            as_of=as_of,
            section_key=source.get("section_key"),
            subsection=source.get("subsection"),
            instruction_id=source.get("instruction_id"),
        )
        fact["zone"] = resolved["zone"]
        probe = {"zone": resolved["zone"], "type": source["fact"].get("fact_type"), "fact_type": source["fact"].get("fact_type")}
        fact["hidden"] = False if is_gap(probe) else fact_on_request(probe)

    for country in payload.get("countries") or []:
        for section in country.get("sections") or []:
            for fact in section.get("facts") or []:
                visit(fact)
            for subsection in section.get("subsections") or []:
                for fact in subsection.get("facts") or []:
                    visit(fact)
    for instruction in (payload.get("instructions") or {}).values():
        for step in instruction.get("steps") or []:
            visit(step)
    return payload


def pending_notifications(config: Optional[Dict[str, Any]] = None, store: Any = None, as_of: Optional[date] = None) -> List[Dict[str, Any]]:
    config = config or load_trust_config()
    store = store or get_community_store()
    as_of = as_of or _today()
    state = _state(store)
    notes = []
    for review in due_recheck_reminders(
        state["reviews"], state["achievements"], config, as_of=as_of, links=state["links"]
    ):
        notes.append({
            "kind": "recheck_reminder",
            "user_id": review.get("user_id"),
            "review_id": review.get("id"),
            "text": message(config, "recheck_reminder"),
            "screen": "review",
        })
    return notes


def mark_reminded(review_id: str, store: Any = None) -> None:
    store = store or get_community_store()
    store.update_review(review_id, {"recheck_reminded_at": _now()})


def delete_community_user(user_id: Any, store: Any = None) -> None:
    store = store or get_community_store()
    store.delete_user(user_id)


def _take_photo(payload: Dict[str, Any], config: Dict[str, Any], store: Any) -> Dict[str, Any]:
    encoded = payload.get("photo_base64")
    if not encoded:
        return {"path": None, "status": None, "note": None}
    if not isinstance(encoded, str):
        raise ValueError(message(config, "bad_field"))
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError(message(config, "bad_field")) from exc
    result = redact_bytes(raw, config)
    path = None
    if result["publish"] and result.get("image"):
        path = store.save_photo(new_id(), result["image"])
    note = None if result["publish"] else message(config, "photo_rejected")
    return {"path": path, "status": result["status"], "note": note}


def _stored_review(review: Dict[str, Any]) -> Dict[str, Any]:
    row = dict(review)
    row.pop("fact_id", None)
    return row


def _public_review(review: Dict[str, Any], link: Optional[Dict[str, Any]], config: Dict[str, Any], photo_note: Optional[str] = None) -> Dict[str, Any]:
    community = require_community(config)
    nick = None if review.get("is_anonymous") else review.get("nick")
    return {
        "id": review.get("id"),
        "status": review.get("status"),
        "country": review.get("country"),
        "city": review.get("city"),
        "topic": review.get("topic"),
        "result": review.get("result"),
        "fact_id": None if not link else link.get("fact_id"),
        "counted": bool(link and link.get("counted")),
        "nick": nick,
        "photo_published": review.get("photo_redaction_status") == community["photo"]["clean_status"] and bool(review.get("photo_path")),
        "photo_note": photo_note,
        "ready_to_recheck": bool(review.get("ready_to_recheck")),
    }


def _owner_review(review: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": review.get("id"),
        "nick": review.get("nick"),
        "country": review.get("country"),
        "city": review.get("city"),
        "trip_date_start": review.get("trip_date_start"),
        "trip_date_end": review.get("trip_date_end"),
        "topic": review.get("topic"),
        "action_text": review.get("action_text"),
        "result": review.get("result"),
        "changed_text": review.get("changed_text"),
        "amount": review.get("amount"),
        "currency": review.get("currency"),
        "fee": review.get("fee"),
        "duration_min": review.get("duration_min"),
        "place_type": review.get("place_type"),
        "place_name": review.get("place_name"),
        "citizenship": review.get("citizenship"),
        "payment_method": review.get("payment_method"),
        "is_anonymous": bool(review.get("is_anonymous")),
        "ready_to_recheck": bool(review.get("ready_to_recheck")),
        "status": review.get("status"),
        "photo_redaction_status": review.get("photo_redaction_status"),
    }


def _context(source: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "section_key": source.get("section_key"),
        "subsection": source.get("subsection"),
        "instruction_id": source.get("instruction_id"),
    }


def _flat_facts(catalog: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for country in catalog.get("countries") or []:
        for section in country.get("sections") or []:
            for fact in section.get("facts") or []:
                rows.append(fact)
            for subsection in section.get("subsections") or []:
                for fact in subsection.get("facts") or []:
                    rows.append(fact)
    return rows


def _deliver(notices: List[Dict[str, Any]]) -> None:
    if not notices:
        return
    try:
        from bot.notifications import deliver_community_notices

        deliver_community_notices(notices)
    except Exception:
        return
