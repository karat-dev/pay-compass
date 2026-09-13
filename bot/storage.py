import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from aiogram.fsm.storage.base import BaseStorage, StorageKey, StateType
from database.client import db

logger = logging.getLogger(__name__)

class SupabaseStorage(BaseStorage):
    """
    Persistent FSM storage implementation for aiogram 3.x backed by Supabase (user_states table).
    Ensures that conversation states and context persist safely across bot restarts.
    """

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        state_str = state.state if hasattr(state, "state") else state
        now = datetime.now(timezone.utc).isoformat()
        
        await db.upsert(
            table="user_states",
            data={
                "user_id": key.user_id,
                "state": state_str,
                "updated_at": now
            },
            on_conflict="user_id"
        )

    async def get_state(self, key: StorageKey) -> Optional[str]:
        records = await db.select("user_states", {"user_id": f"eq.{key.user_id}"})
        if records:
            return records[0].get("state")
        return None

    async def set_data(self, key: StorageKey, data: Dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await db.upsert(
            table="user_states",
            data={
                "user_id": key.user_id,
                "data": data,
                "updated_at": now
            },
            on_conflict="user_id"
        )

    async def get_data(self, key: StorageKey) -> Dict[str, Any]:
        records = await db.select("user_states", {"user_id": f"eq.{key.user_id}"})
        if records:
            data = records[0].get("data")
            if isinstance(data, dict):
                return data
            if isinstance(data, str):
                try:
                    return json.loads(data)
                except Exception:
                    return {}
        return {}

    async def get_updated_at(self, user_id: int) -> Optional[datetime]:
        """Returns the last state update timestamp for soft resume calculation (>24h)."""
        records = await db.select("user_states", {"user_id": f"eq.{user_id}"})
        if records and records[0].get("updated_at"):
            raw_ts = records[0]["updated_at"]
            try:
                # Handle ISO timestamps with timezone
                return datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
            except Exception:
                return None
        return None

    async def close(self) -> None:
        await db.close()
