"""Persistence for community reviews.

Production uses the existing Supabase project. Local runs without a service-role
key use a JSON file. The browser never receives that key.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx

from config.settings import settings
from database.miniapp_store import supabase_is_configured

ROOT = Path(__file__).resolve().parents[1]
LOCAL_PATH = ROOT / "miniapp" / ".local-data" / "community.json"
PHOTO_DIR = ROOT / "miniapp" / ".local-data" / "photos"


def empty_state() -> Dict[str, List[Dict[str, Any]]]:
    return {
        "reviews": [],
        "links": [],
        "achievements": [],
        "levels": [],
        "views": [],
        "queue": [],
    }


class CommunityStoreError(Exception):
    pass


class FileCommunityStore:
    def __init__(self, path: Path = LOCAL_PATH, photo_dir: Path = PHOTO_DIR):
        self.path = path
        self.photo_dir = photo_dir
        self._lock = threading.Lock()

    def snapshot(self) -> Dict[str, List[Dict[str, Any]]]:
        with self._lock:
            return self._read()

    def insert_review(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return self._append("reviews", row)

    def insert_link(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return self._append("links", row)

    def insert_achievement(self, row: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            data = self._read()
            for item in data["achievements"]:
                if item.get("user_id") == row.get("user_id") and item.get("code") == row.get("code") and item.get("scope") == row.get("scope"):
                    return item
            data["achievements"].append(row)
            self._write(data)
        return row

    def insert_view(self, row: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            data = self._read()
            for item in data["views"]:
                if str(item.get("fact_id")) == str(row.get("fact_id")) and str(item.get("user_id")) == str(row.get("user_id")):
                    return item
            data["views"].append(row)
            self._write(data)
        return row

    def insert_queue(self, row: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            data = self._read()
            for item in data["queue"]:
                if (
                    item.get("status") == row.get("status")
                    and item.get("kind") == row.get("kind")
                    and item.get("trigger") == row.get("trigger")
                    and str(item.get("target_id")) == str(row.get("target_id"))
                ):
                    return item
            data["queue"].append(row)
            self._write(data)
        return row

    def update_review(self, review_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        return self._update("reviews", review_id, fields)

    def update_link(self, link_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        return self._update("links", link_id, fields)

    def update_queue(self, queue_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        return self._update("queue", queue_id, fields)

    def upsert_level(self, row: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            data = self._read()
            kept = [item for item in data["levels"] if str(item.get("user_id")) != str(row.get("user_id"))]
            kept.append(row)
            data["levels"] = kept
            self._write(data)
        return row

    def save_photo(self, photo_id: str, image: bytes) -> str:
        self.photo_dir.mkdir(parents=True, exist_ok=True)
        dest = self.photo_dir / f"{photo_id}.jpg"
        dest.write_bytes(image)
        return str(dest)

    def read_photo(self, path: str) -> Optional[bytes]:
        target = Path(path)
        if not target.is_file():
            return None
        return target.read_bytes()

    def delete_user(self, user_id: Any) -> None:
        key = str(user_id)
        with self._lock:
            data = self._read()
            review_ids = {row.get("id") for row in data["reviews"] if str(row.get("user_id")) == key}
            data["reviews"] = [row for row in data["reviews"] if str(row.get("user_id")) != key]
            data["links"] = [
                row for row in data["links"]
                if str(row.get("user_id")) != key and row.get("review_id") not in review_ids
            ]
            data["achievements"] = [row for row in data["achievements"] if str(row.get("user_id")) != key]
            data["levels"] = [row for row in data["levels"] if str(row.get("user_id")) != key]
            data["views"] = [row for row in data["views"] if str(row.get("user_id")) != key]
            data["queue"] = [row for row in data["queue"] if row.get("target_id") not in review_ids]
            self._write(data)

    def _append(self, bucket: str, row: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            data = self._read()
            data[bucket].append(row)
            self._write(data)
        return row

    def _update(self, bucket: str, row_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            data = self._read()
            found = None
            for row in data[bucket]:
                if str(row.get("id")) == str(row_id):
                    row.update(fields)
                    found = row
                    break
            if found is None:
                raise CommunityStoreError("Запись не найдена.")
            self._write(data)
        return found

    def _read(self) -> Dict[str, List[Dict[str, Any]]]:
        if not self.path.exists():
            return empty_state()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        state = empty_state()
        for key in state:
            if isinstance(data.get(key), list):
                state[key] = data[key]
        return state

    def _write(self, data: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.path)


class SupabaseCommunityStore:
    def __init__(self, url: str, key: str):
        self.rest = url.rstrip("/") + "/rest/v1"
        self.storage = url.rstrip("/") + "/storage/v1"
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        self.client = httpx.Client()

    def snapshot(self) -> Dict[str, List[Dict[str, Any]]]:
        state = empty_state()
        state["reviews"] = self._select("reviews")
        state["links"] = self._select("review_fact_links")
        state["achievements"] = self._select("achievements")
        state["levels"] = self._select("user_levels")
        state["views"] = self._select("fact_views")
        state["queue"] = self._select("moderation_queue")
        return state

    def insert_review(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return self._insert("reviews", _review_columns(row))

    def insert_link(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return self._insert("review_fact_links", _link_columns(row))

    def insert_achievement(self, row: Dict[str, Any]) -> Dict[str, Any]:
        existing = self._select("achievements", {
            "user_id": f"eq.{row['user_id']}",
            "code": f"eq.{row['code']}",
            "scope": f"eq.{row['scope']}",
        })
        if existing:
            return existing[0]
        return self._insert("achievements", row)

    def insert_view(self, row: Dict[str, Any]) -> Dict[str, Any]:
        existing = self._select("fact_views", {
            "user_id": f"eq.{row['user_id']}",
            "fact_id": f"eq.{row['fact_id']}",
        })
        if existing:
            return existing[0]
        return self._insert("fact_views", row)

    def insert_queue(self, row: Dict[str, Any]) -> Dict[str, Any]:
        params = {
            "target_id": f"eq.{row['target_id']}",
            "kind": f"eq.{row['kind']}",
            "status": f"eq.{row['status']}",
        }
        if row.get("trigger"):
            params["trigger"] = f"eq.{row['trigger']}"
        existing = self._select("moderation_queue", params)
        for item in existing:
            if item.get("trigger") == row.get("trigger"):
                return item
        return self._insert("moderation_queue", row)

    def update_review(self, review_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        return self._patch("reviews", review_id, _review_columns(fields))

    def update_link(self, link_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        return self._patch("review_fact_links", link_id, _link_columns(fields))

    def update_queue(self, queue_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        return self._patch("moderation_queue", queue_id, fields)

    def upsert_level(self, row: Dict[str, Any]) -> Dict[str, Any]:
        headers = dict(self.headers)
        headers["Prefer"] = "resolution=merge-duplicates,return=representation"
        response = self.client.post(
            self.rest + "/user_levels",
            params={"on_conflict": "user_id"},
            headers=headers,
            json=row,
        )
        if not response.is_success:
            raise CommunityStoreError("Не удалось сохранить уровень автора.")
        payload = response.json()
        if isinstance(payload, list) and payload:
            return payload[0]
        return row

    def save_photo(self, photo_id: str, image: bytes) -> str:
        name = f"{photo_id}.jpg"
        headers = {
            "apikey": self.headers["apikey"],
            "Authorization": self.headers["Authorization"],
            "Content-Type": "image/jpeg",
        }
        response = self.client.post(
            self.storage + "/object/community-photos/" + name,
            headers=headers,
            content=image,
        )
        if not response.is_success:
            raise CommunityStoreError("Не удалось сохранить обработанное фото. Нужен бакет community-photos.")
        return "community-photos/" + name

    def read_photo(self, path: str) -> Optional[bytes]:
        response = self.client.get(
            self.storage + "/object/authenticated/" + path.lstrip("/"),
            headers=self.headers,
        )
        if not response.is_success:
            return None
        return response.content

    def delete_user(self, user_id: Any) -> None:
        reviews = self._select("reviews", {"user_id": f"eq.{user_id}"})
        ids = [row.get("id") for row in reviews if row.get("id")]
        self._delete("review_fact_links", {"user_id": f"eq.{user_id}"})
        self._delete("reviews", {"user_id": f"eq.{user_id}"})
        self._delete("achievements", {"user_id": f"eq.{user_id}"})
        self._delete("user_levels", {"user_id": f"eq.{user_id}"})
        self._delete("fact_views", {"user_id": f"eq.{user_id}"})
        for review_id in ids:
            self._delete("moderation_queue", {"target_id": f"eq.{review_id}"})

    def _select(self, table: str, params: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        query = dict(params or {})
        query.setdefault("select", "*")
        response = self.client.get(self.rest + "/" + table, params=query, headers=self.headers)
        if not response.is_success:
            raise CommunityStoreError("Не удалось прочитать " + table + ".")
        payload = response.json()
        return payload if isinstance(payload, list) else []

    def _insert(self, table: str, row: Dict[str, Any]) -> Dict[str, Any]:
        headers = dict(self.headers)
        headers["Prefer"] = "return=representation"
        response = self.client.post(self.rest + "/" + table, headers=headers, json=row)
        if not response.is_success:
            raise CommunityStoreError("Не удалось записать " + table + ".")
        payload = response.json()
        if isinstance(payload, list) and payload:
            return payload[0]
        return row

    def _patch(self, table: str, row_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        headers = dict(self.headers)
        headers["Prefer"] = "return=representation"
        response = self.client.patch(
            self.rest + "/" + table,
            params={"id": f"eq.{row_id}"},
            headers=headers,
            json=fields,
        )
        if not response.is_success:
            raise CommunityStoreError("Не удалось обновить " + table + ".")
        payload = response.json()
        if isinstance(payload, list) and payload:
            return payload[0]
        return fields

    def _delete(self, table: str, params: Dict[str, str]) -> None:
        response = self.client.delete(self.rest + "/" + table, params=params, headers=self.headers)
        if not response.is_success:
            raise CommunityStoreError("Не удалось удалить данные в " + table + ".")


def _review_columns(row: Dict[str, Any]) -> Dict[str, Any]:
    keys = {
        "id", "user_id", "nick", "country", "city", "trip_date_start", "trip_date_end",
        "topic", "action_text", "result", "changed_text", "amount", "currency", "fee",
        "fee_kind", "duration_min", "place_type", "place_name", "citizenship",
        "payment_method", "photo_path", "photo_redaction_status", "ready_to_recheck",
        "is_anonymous", "status", "antifraud_flags", "created_at", "moderated_at",
        "recheck_reminded_at",
    }
    return {key: row[key] for key in keys if key in row}


def _link_columns(row: Dict[str, Any]) -> Dict[str, Any]:
    keys = {
        "id", "review_id", "fact_id", "user_id", "verdict", "verdict_source",
        "counted", "weight", "not_counted_reason", "created_at",
    }
    return {key: row[key] for key in keys if key in row}


_store: Any = None


def build_community_store() -> Any:
    if supabase_is_configured():
        return SupabaseCommunityStore(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    return FileCommunityStore()


def get_community_store() -> Any:
    global _store
    if _store is None:
        _store = build_community_store()
    return _store


def set_community_store(store: Any) -> None:
    global _store
    _store = store


def new_id() -> str:
    return str(uuid4())
