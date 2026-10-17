"""HTTP API for the Mini App. Catalog is public. Writes require initData."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, Mapping, Optional
from urllib.parse import parse_qs, urlparse

from api.telegram_auth import AuthError, validate_init_data
from config.settings import bot_token, bot_url, bot_username, settings, telegram_bot_token_configured
from database.knowledge_base import INSTRUCTIONS, SECTION_KEYS
from database.miniapp_catalog import (
    find_fact,
    get_catalog,
    known_bank_ids,
    known_city_ids,
    known_country_slugs,
)
from database.miniapp_store import StoreError, get_store

logger = logging.getLogger(__name__)

READ_ROUTES = {"catalog", "miniapp/config"}
WRITE_ROUTES = {
    "miniapp/session",
    "miniapp/profile",
    "miniapp/trip",
    "miniapp/progress",
    "miniapp/report",
    "miniapp/onboarding",
    "miniapp/intro",
}
MAX_BODY = 100_000


def extract_route(raw_path: str) -> str:
    parsed = urlparse(raw_path or "")
    query = parse_qs(parsed.query)
    forwarded = (query.get("path") or [""])[0].strip("/")
    if forwarded:
        return forwarded
    path = parsed.path.strip("/")
    if path.startswith("api/"):
        path = path[4:]
    if path.endswith("index.py"):
        return ""
    return path


def _error(status: int, message: str) -> tuple:
    return status, {"error": message}


def _parse_date(value: Any, field: str) -> Optional[str]:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError(f"Поле {field} заполнено неверно.")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("Дата указана неверно.") from exc
    return value


def _clean_profile(payload: Mapping[str, Any], *, require_complete: bool) -> Dict[str, Any]:
    bank_id = payload.get("bank_id")
    city_id = payload.get("departure_city_id")
    if bank_id not in known_bank_ids():
        raise ValueError("Выберите банк.")
    if city_id not in known_city_ids():
        raise ValueError("Выберите город вылета.")
    favorites = payload.get("favorite_countries") or []
    if not isinstance(favorites, list):
        raise ValueError("Список стран заполнен неверно.")
    slugs = known_country_slugs()
    clean_favorites = []
    for slug in favorites:
        if slug in slugs and slug not in clean_favorites:
            clean_favorites.append(slug)
    consent = bool(payload.get("consent_given"))
    completed = bool(payload.get("onboarding_completed"))
    if require_complete and completed and not consent:
        raise ValueError("Нужно согласие на обработку данных.")
    return {
        "bank_id": bank_id,
        "departure_city_id": city_id,
        "favorite_countries": clean_favorites[:6],
        "notify_checklist": bool(payload.get("notify_checklist", True)),
        "notify_trip": bool(payload.get("notify_trip", True)),
        "notify_alerts": bool(payload.get("notify_alerts", False)),
        "consent_given": consent,
        "onboarding_completed": completed,
        "intro_seen": bool(payload.get("intro_seen")),
    }


def _clean_trip(payload: Mapping[str, Any], fallback_city: Optional[str] = None) -> Dict[str, Any]:
    slug = payload.get("destination_slug")
    if slug not in known_country_slugs():
        raise ValueError("Выберите страну.")
    depart = _parse_date(payload.get("depart_date"), "depart_date")
    ret = _parse_date(payload.get("return_date"), "return_date")
    if depart and ret and ret < depart:
        raise ValueError("Дата возвращения раньше вылета.")
    city = payload.get("departure_city_id") or fallback_city
    if city is not None and city not in known_city_ids():
        raise ValueError("Выберите город вылета.")
    return {
        "destination_slug": slug,
        "departure_city_id": city,
        "depart_date": depart,
        "return_date": ret,
    }


def _identity(headers: Mapping[str, str], body: Mapping[str, Any]) -> Dict[str, Any]:
    header_map = {str(key).lower(): value for key, value in headers.items()}
    init_data = header_map.get("x-telegram-init-data") or body.get("init_data") or ""
    return validate_init_data(
        str(init_data),
        bot_token=bot_token(),
        dev_auth=bool(settings.MINIAPP_DEV_AUTH),
        max_age_seconds=int(settings.MINIAPP_INITDATA_MAX_AGE_SECONDS),
    )


def normalize_screen(raw: str) -> str:
    """Deep-link target. Unknown values fall back to the trip tab."""
    value = (raw or "").strip()
    if value in {"trip", "guide", "sos", "profile", "search"}:
        return value
    slugs = known_country_slugs()
    if value.startswith("guide_"):
        slug = value[len("guide_"):]
        if slug in slugs:
            return value
    if value.startswith("instruction_"):
        instruction_id = value[len("instruction_"):]
        if instruction_id in INSTRUCTIONS:
            return value
    if value.startswith("section_"):
        rest = value[len("section_"):]
        for key in SECTION_KEYS:
            suffix = f"_{key}"
            if rest.endswith(suffix):
                slug = rest[: -len(suffix)]
                if slug in slugs:
                    return value
    return "trip"


async def _remember_user(identity: Dict[str, Any]) -> None:
    if identity.get("dev"):
        return
    try:
        from database.repositories.users import UserRepository

        await UserRepository.get_or_create_user(identity["telegram_id"])
    except Exception as exc:
        logger.warning("miniapp user sync skipped: %s", exc)


async def _mark_consent(identity: Dict[str, Any], profile: Dict[str, Any]) -> None:
    if identity.get("dev") or not profile.get("consent_given"):
        return
    try:
        from database.repositories.users import UserRepository

        await UserRepository.give_consent(identity["telegram_id"])
    except Exception as exc:
        logger.warning("miniapp consent sync skipped: %s", exc)


async def _handle(method: str, route: str, body: bytes, headers: Mapping[str, str]) -> tuple:
    if route == "catalog" and method == "GET":
        return 200, get_catalog()
    if route == "miniapp/config" and method == "GET":
        return 200, {
            "dev_auth": bool(settings.MINIAPP_DEV_AUTH),
            "miniapp_url": settings.MINIAPP_URL,
            "storage": "supabase" if _uses_supabase() else "local-file",
            "bot_username": bot_username(),
            "bot_url": bot_url(),
            "token_configured": telegram_bot_token_configured(),
        }
    if route not in WRITE_ROUTES:
        if route in READ_ROUTES:
            return _error(405, "Метод не поддерживается.")
        return _error(404, "Не найдено.")
    if method != "POST":
        return _error(405, "Метод не поддерживается.")
    if len(body) > MAX_BODY:
        return _error(413, "Слишком большой запрос.")
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _error(400, "Некорректный запрос.")
    if not isinstance(payload, dict):
        return _error(400, "Некорректный запрос.")

    try:
        identity = _identity(headers, payload)
    except AuthError as exc:
        return _error(exc.status, exc.message)

    store = get_store()
    telegram_id = identity["telegram_id"]
    try:
        await _remember_user(identity)
        if route == "miniapp/session":
            bundle = await store.get_bundle(telegram_id)
            bundle["telegram_id"] = telegram_id
            bundle["intro_seen"] = bool(bundle.get("intro_seen"))
            raw_screen = identity.get("start_param") or payload.get("screen") or ""
            bundle["screen"] = normalize_screen(raw_screen) if raw_screen else None
            return 200, bundle
        if route == "miniapp/intro":
            marked = await store.mark_intro_seen(telegram_id)
            return 200, marked
        if route == "miniapp/profile":
            fields = _clean_profile(payload, require_complete=True)
            profile = await store.save_profile(telegram_id, fields)
            await _mark_consent(identity, profile)
            return 200, {"profile": profile}
        if route == "miniapp/trip":
            trip = await store.save_trip(telegram_id, _clean_trip(payload))
            return 200, {"trip": trip}
        if route == "miniapp/onboarding":
            profile_fields = _clean_profile(payload.get("profile") or {}, require_complete=True)
            if not profile_fields["consent_given"] or not profile_fields["onboarding_completed"]:
                raise ValueError("Нужно согласие на обработку данных.")
            trip_fields = _clean_trip(payload.get("trip") or {}, profile_fields["departure_city_id"])
            if profile_fields["departure_city_id"] and not trip_fields.get("departure_city_id"):
                trip_fields["departure_city_id"] = profile_fields["departure_city_id"]
            trip = await store.save_trip(telegram_id, trip_fields)
            profile = await store.save_profile(telegram_id, profile_fields)
            await _mark_consent(identity, profile)
            return 200, {"profile": profile, "trip": trip}
        if route == "miniapp/progress":
            item_id = payload.get("item_id")
            fact = find_fact(str(item_id or ""))
            if not fact:
                return _error(404, "Пункт не найден.")
            kind = payload.get("kind") or ("checklist" if fact.get("section_key") == "1_checklist" and not fact.get("instruction_id") else "step")
            if kind not in {"step", "checklist"}:
                raise ValueError("Некорректный прогресс.")
            saved = await store.save_progress(telegram_id, {
                "item_id": fact["id"],
                "instruction_id": fact.get("instruction_id"),
                "kind": kind,
                "completed": bool(payload.get("completed")),
            })
            return 200, {"progress": saved}
        if route == "miniapp/report":
            fact = find_fact(str(payload.get("fact_id") or ""))
            if not fact:
                return _error(404, "Факт не найден.")
            comment = payload.get("comment") or ""
            if not isinstance(comment, str):
                raise ValueError("Комментарий заполнен неверно.")
            comment = comment.strip()[:1000]
            saved = await store.add_report(telegram_id, {
                "fact_id": fact["id"],
                "country_slug": fact.get("country_slug"),
                "section_key": fact.get("section_key"),
                "instruction_id": fact.get("instruction_id"),
                "fact_text": fact.get("text") or "",
                "comment": comment,
            })
            return 200, {"report": saved}
    except ValueError as exc:
        return _error(400, str(exc))
    except StoreError as exc:
        logger.warning("miniapp store: %s", exc)
        return _error(503, str(exc))
    return _error(404, "Не найдено.")


def _uses_supabase() -> bool:
    from database.miniapp_store import supabase_is_configured

    return supabase_is_configured()


def dispatch(method: str, route: str, body: bytes, headers: Optional[Mapping[str, str]] = None) -> tuple:
    return asyncio.run(_handle(method.upper(), route.strip("/"), body or b"", headers or {}))
