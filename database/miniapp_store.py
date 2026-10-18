"""Mini App profile, trip, checklist progress and inaccuracy reports.

Production writes go to the existing Supabase project with the service-role key.
Local runs without that key use a JSON file so the app still works against the
real country data. The browser never receives the service-role key.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol
from uuid import uuid4

import httpx

from config.settings import settings

ROOT = Path(__file__).resolve().parents[1]
LOCAL_STORE_PATH = ROOT / "miniapp" / ".local-data" / "store.json"


class StoreError(Exception):
    pass


def supabase_is_configured() -> bool:
    url = (settings.SUPABASE_URL or "").strip().lower()
    key = (settings.SUPABASE_KEY or "").strip()
    if not url.startswith("https://"):
        return False
    if any(token in url for token in ("localhost", "127.0.0.1", "your-project", "example.com")):
        return False
    if not key or key.startswith("mock") or "your-" in key or "your_" in key:
        return False
    return True


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def citizenship_value(fields: Dict[str, Any]) -> str:
    """Only a Russian passport is offered. Missing values stay on that default."""
    value = fields.get("citizenship") or "ru"
    if value != "ru":
        raise ValueError("Пока доступно только гражданство РФ.")
    return "ru"


def profile_row(telegram_id: int, fields: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "telegram_id": telegram_id,
        "bank_id": fields["bank_id"],
        "departure_city_id": fields["departure_city_id"],
        "favorite_countries": list(fields.get("favorite_countries") or []),
        "notify_checklist": bool(fields.get("notify_checklist", True)),
        "notify_trip": bool(fields.get("notify_trip", True)),
        "notify_alerts": bool(fields.get("notify_alerts", False)),
        "consent_given": bool(fields.get("consent_given")),
        "onboarding_completed": bool(fields.get("onboarding_completed")),
        "intro_seen": bool(fields.get("intro_seen")),
        "citizenship": citizenship_value(fields),
        "updated_at": _now(),
    }


def trip_row(telegram_id: int, fields: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "telegram_id": telegram_id,
        "destination_slug": fields["destination_slug"],
        "departure_city_id": fields.get("departure_city_id"),
        "depart_date": fields.get("depart_date"),
        "return_date": fields.get("return_date"),
        "updated_at": _now(),
    }


def progress_row(telegram_id: int, fields: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "telegram_id": telegram_id,
        "item_id": fields["item_id"],
        "instruction_id": fields.get("instruction_id"),
        "kind": fields.get("kind") or "step",
        "completed": bool(fields.get("completed")),
        "updated_at": _now(),
    }


def public_profile(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    favorites = row.get("favorite_countries") or []
    if isinstance(favorites, str):
        try:
            favorites = json.loads(favorites)
        except json.JSONDecodeError:
            favorites = []
    return {
        "bank_id": row.get("bank_id"),
        "departure_city_id": row.get("departure_city_id"),
        "favorite_countries": list(favorites),
        "notify_checklist": bool(row.get("notify_checklist", True)),
        "notify_trip": bool(row.get("notify_trip", True)),
        "notify_alerts": bool(row.get("notify_alerts", False)),
        "consent_given": bool(row.get("consent_given")),
        "onboarding_completed": bool(row.get("onboarding_completed")),
        "intro_seen": bool(row.get("intro_seen")),
        "citizenship": row.get("citizenship") or "ru",
    }


def public_trip(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "destination_slug": row.get("destination_slug"),
        "departure_city_id": row.get("departure_city_id"),
        "depart_date": row.get("depart_date"),
        "return_date": row.get("return_date"),
    }


def public_progress(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items = []
    for row in rows:
        items.append({
            "item_id": row.get("item_id"),
            "instruction_id": row.get("instruction_id"),
            "kind": row.get("kind") or "step",
            "completed": bool(row.get("completed")),
        })
    return items


class Rest(Protocol):
    async def select(self, table: str, params: Dict[str, str]) -> List[Dict[str, Any]]:
        ...

    async def upsert(self, table: str, data: Dict[str, Any], on_conflict: str) -> Dict[str, Any]:
        ...

    async def insert(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        ...

    async def delete(self, table: str, params: Dict[str, str]) -> List[Dict[str, Any]]:
        ...


class HttpxRest:
    def __init__(self, url: str, key: str):
        self.rest = url.rstrip("/") + "/rest/v1"
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    async def select(self, table: str, params: Dict[str, str]) -> List[Dict[str, Any]]:
        return await self._request("GET", table, params=params)

    async def upsert(self, table: str, data: Dict[str, Any], on_conflict: str) -> Dict[str, Any]:
        headers = dict(self.headers)
        headers["Prefer"] = "resolution=merge-duplicates,return=representation"
        rows = await self._request(
            "POST",
            table,
            params={"on_conflict": on_conflict},
            json_body=data,
            headers=headers,
        )
        if isinstance(rows, list) and rows:
            return rows[0]
        return data

    async def insert(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        headers = dict(self.headers)
        headers["Prefer"] = "return=representation"
        rows = await self._request("POST", table, json_body=data, headers=headers)
        if isinstance(rows, list) and rows:
            return rows[0]
        return data

    async def delete(self, table: str, params: Dict[str, str]) -> List[Dict[str, Any]]:
        headers = dict(self.headers)
        headers["Prefer"] = "return=minimal"
        await self._request("DELETE", table, params=params, headers=headers)
        return []

    async def _request(
        self,
        method: str,
        table: str,
        *,
        params: Optional[Dict[str, str]] = None,
        json_body: Any = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                response = await client.request(
                    method,
                    f"{self.rest}/{table}",
                    params=params,
                    json=json_body,
                    headers=headers or self.headers,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise StoreError("Не удалось сохранить данные. Проверьте миграцию Supabase и ключ.") from exc
        if not response.content:
            return []
        return response.json()


class SupabaseMiniappStore:
    def __init__(self, rest: Rest):
        self.rest = rest

    async def get_bundle(self, telegram_id: int) -> Dict[str, Any]:
        eq = {"telegram_id": f"eq.{telegram_id}"}
        profiles = await self.rest.select("miniapp_profiles", eq)
        trips = await self.rest.select("miniapp_trips", eq)
        progress = await self.rest.select("miniapp_progress", eq)
        profile = public_profile(profiles[0] if profiles else None)
        return {
            "profile": profile,
            "trip": public_trip(trips[0] if trips else None),
            "progress": public_progress(progress),
            "intro_seen": bool(profile and profile.get("intro_seen")),
        }

    async def save_profile(self, telegram_id: int, fields: Dict[str, Any]) -> Dict[str, Any]:
        fields = dict(fields)
        existing = await self.rest.select("miniapp_profiles", {"telegram_id": f"eq.{telegram_id}"})
        if existing and existing[0].get("intro_seen"):
            fields["intro_seen"] = True
        row = profile_row(telegram_id, fields)
        saved = await self.rest.upsert("miniapp_profiles", row, "telegram_id")
        return public_profile(saved) or public_profile(row)

    async def mark_intro_seen(self, telegram_id: int) -> Dict[str, Any]:
        existing = await self.rest.select("miniapp_profiles", {"telegram_id": f"eq.{telegram_id}"})
        if existing:
            fields = dict(existing[0])
            fields["intro_seen"] = True
        else:
            fields = {
                "bank_id": None,
                "departure_city_id": None,
                "favorite_countries": [],
                "notify_checklist": True,
                "notify_trip": True,
                "notify_alerts": False,
                "consent_given": False,
                "onboarding_completed": False,
                "intro_seen": True,
            }
        row = profile_row(telegram_id, fields)
        saved = await self.rest.upsert("miniapp_profiles", row, "telegram_id")
        profile = public_profile(saved) or public_profile(row)
        return {"intro_seen": True, "profile": profile}

    async def save_trip(self, telegram_id: int, fields: Dict[str, Any]) -> Dict[str, Any]:
        row = trip_row(telegram_id, fields)
        saved = await self.rest.upsert("miniapp_trips", row, "telegram_id")
        return public_trip(saved) or public_trip(row)

    async def save_progress(self, telegram_id: int, fields: Dict[str, Any]) -> Dict[str, Any]:
        row = progress_row(telegram_id, fields)
        saved = await self.rest.upsert("miniapp_progress", row, "telegram_id,item_id")
        return public_progress([saved])[0]

    async def add_report(self, telegram_id: int, fields: Dict[str, Any]) -> Dict[str, Any]:
        row = {
            "id": str(uuid4()),
            "telegram_id": telegram_id,
            "fact_id": fields["fact_id"],
            "country_slug": fields.get("country_slug"),
            "section_key": fields.get("section_key"),
            "instruction_id": fields.get("instruction_id"),
            "fact_text": fields.get("fact_text") or "",
            "comment": fields.get("comment") or "",
            "created_at": _now(),
        }
        saved = await self.rest.insert("miniapp_fact_reports", row)
        return {"id": saved.get("id") or row["id"], "fact_id": row["fact_id"]}

    async def delete_user(self, telegram_id: int) -> None:
        eq = {"telegram_id": f"eq.{telegram_id}"}
        await self.rest.delete("miniapp_progress", eq)
        await self.rest.delete("miniapp_fact_reports", eq)
        await self.rest.delete("miniapp_trips", eq)
        await self.rest.delete("miniapp_profiles", eq)


class FileMiniappStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

    def _read(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"profiles": {}, "trips": {}, "progress": {}, "reports": []}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise StoreError("Локальное хранилище повреждено.") from exc

    def _write(self, data: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    async def get_bundle(self, telegram_id: int) -> Dict[str, Any]:
        key = str(telegram_id)
        with self._lock:
            data = self._read()
        profile = public_profile(data["profiles"].get(key))
        return {
            "profile": profile,
            "trip": public_trip(data["trips"].get(key)),
            "progress": public_progress(list((data["progress"].get(key) or {}).values())),
            "intro_seen": bool(profile and profile.get("intro_seen")),
        }

    async def save_profile(self, telegram_id: int, fields: Dict[str, Any]) -> Dict[str, Any]:
        fields = dict(fields)
        key = str(telegram_id)
        with self._lock:
            data = self._read()
            previous = data["profiles"].get(key) or {}
            if previous.get("intro_seen"):
                fields["intro_seen"] = True
            row = profile_row(telegram_id, fields)
            data["profiles"][key] = row
            self._write(data)
        return public_profile(row)

    async def mark_intro_seen(self, telegram_id: int) -> Dict[str, Any]:
        key = str(telegram_id)
        with self._lock:
            data = self._read()
            previous = data["profiles"].get(key)
            if previous:
                previous["intro_seen"] = True
                previous["updated_at"] = _now()
                row = previous
            else:
                row = profile_row(telegram_id, {
                    "bank_id": None,
                    "departure_city_id": None,
                    "favorite_countries": [],
                    "consent_given": False,
                    "onboarding_completed": False,
                    "intro_seen": True,
                })
            data["profiles"][key] = row
            self._write(data)
        return {"intro_seen": True, "profile": public_profile(row)}

    async def save_trip(self, telegram_id: int, fields: Dict[str, Any]) -> Dict[str, Any]:
        row = trip_row(telegram_id, fields)
        key = str(telegram_id)
        with self._lock:
            data = self._read()
            data["trips"][key] = row
            self._write(data)
        return public_trip(row)

    async def save_progress(self, telegram_id: int, fields: Dict[str, Any]) -> Dict[str, Any]:
        row = progress_row(telegram_id, fields)
        key = str(telegram_id)
        with self._lock:
            data = self._read()
            bucket = data["progress"].setdefault(key, {})
            bucket[row["item_id"]] = row
            self._write(data)
        return public_progress([row])[0]

    async def add_report(self, telegram_id: int, fields: Dict[str, Any]) -> Dict[str, Any]:
        row = {
            "id": str(uuid4()),
            "telegram_id": telegram_id,
            "fact_id": fields["fact_id"],
            "country_slug": fields.get("country_slug"),
            "section_key": fields.get("section_key"),
            "instruction_id": fields.get("instruction_id"),
            "fact_text": fields.get("fact_text") or "",
            "comment": fields.get("comment") or "",
            "created_at": _now(),
        }
        with self._lock:
            data = self._read()
            data["reports"].append(row)
            self._write(data)
        return {"id": row["id"], "fact_id": row["fact_id"]}

    async def delete_user(self, telegram_id: int) -> None:
        key = str(telegram_id)
        with self._lock:
            data = self._read()
            data["profiles"].pop(key, None)
            data["trips"].pop(key, None)
            data["progress"].pop(key, None)
            data["reports"] = [row for row in data["reports"] if str(row.get("telegram_id")) != key]
            self._write(data)

    def raw_reports(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._read()["reports"])


_store: Any = None


def build_default_store() -> Any:
    if supabase_is_configured():
        return SupabaseMiniappStore(HttpxRest(settings.SUPABASE_URL, settings.SUPABASE_KEY))
    return FileMiniappStore(LOCAL_STORE_PATH)


def get_store() -> Any:
    global _store
    if _store is None:
        _store = build_default_store()
    return _store


def set_store(store: Any) -> None:
    global _store
    _store = store


async def delete_miniapp_user(telegram_id: int) -> None:
    try:
        await get_store().delete_user(telegram_id)
        from database.community_service import delete_community_user

        delete_community_user(telegram_id)
    except StoreError:
        raise
    except Exception as exc:
        raise StoreError("Не удалось удалить данные Mini App.") from exc
