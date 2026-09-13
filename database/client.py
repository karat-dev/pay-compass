import httpx
from typing import Optional, Dict, Any, List
import logging
from config.settings import settings

logger = logging.getLogger(__name__)

class AsyncSupabaseClient:
    """
    High-performance async client for Supabase using direct PostgREST REST endpoints.
    Eliminates threadpool overhead and prevents event-loop blocking in aiogram handlers.
    """
    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        self.url = (url or settings.SUPABASE_URL).rstrip("/")
        self.key = key or settings.SUPABASE_KEY
        self.rest_url = f"{self.url}/rest/v1"
        self._headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=self._headers,
                timeout=httpx.Timeout(10.0, connect=5.0)
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def select(self, table: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        client = await self.get_client()
        try:
            resp = await client.get(f"{self.rest_url}/{table}", params=params)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Supabase select error on {table}: {e}")
            return []

    async def insert(self, table: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        client = await self.get_client()
        try:
            resp = await client.post(f"{self.rest_url}/{table}", json=data)
            resp.raise_for_status()
            res = resp.json()
            return res[0] if isinstance(res, list) and res else res
        except Exception as e:
            logger.warning(f"Supabase insert error on {table}: {e}")
            return None

    async def upsert(self, table: str, data: Dict[str, Any], on_conflict: str = "id") -> Optional[Dict[str, Any]]:
        client = await self.get_client()
        headers = dict(self._headers)
        headers["Prefer"] = f"resolution=merge-duplicates,return=representation"
        try:
            resp = await client.post(
                f"{self.rest_url}/{table}",
                params={"on_conflict": on_conflict},
                json=data,
                headers=headers
            )
            resp.raise_for_status()
            res = resp.json()
            return res[0] if isinstance(res, list) and res else res
        except Exception as e:
            logger.warning(f"Supabase upsert error on {table}: {e}")
            return None

    async def update(self, table: str, data: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        client = await self.get_client()
        try:
            resp = await client.patch(f"{self.rest_url}/{table}", params=params, json=data)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Supabase update error on {table}: {e}")
            return []

    async def delete(self, table: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        client = await self.get_client()
        try:
            resp = await client.delete(f"{self.rest_url}/{table}", params=params)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Supabase delete error on {table}: {e}")
            return []

# Singleton instance
db = AsyncSupabaseClient()
