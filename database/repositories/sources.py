from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from database.client import db

class SourceRepository:
    """Repository for managing sources, health checks, and incoming raw posts."""

    @staticmethod
    async def get_or_create_source(url: str, source_type: str, trust_score: int) -> Optional[Dict[str, Any]]:
        existing = await db.select("sources", {"url": f"eq.{url}"})
        if existing:
            return existing[0]
        return await db.insert("sources", {
            "url": url,
            "type": source_type,
            "trust_score": trust_score,
            "status": "active"
        })

    @staticmethod
    async def record_success(source_id: str):
        now = datetime.now(timezone.utc).isoformat()
        await db.update("sources", {"last_parsed_at": now}, {"id": f"eq.{source_id}"})
        
        health = await db.select("source_health", {"source_id": f"eq.{source_id}"})
        if health:
            await db.update(
                "source_health",
                {"status": "healthy", "error_count": 0, "last_success_at": now},
                {"source_id": f"eq.{source_id}"}
            )
        else:
            await db.insert("source_health", {
                "source_id": source_id,
                "status": "healthy",
                "error_count": 0,
                "last_success_at": now
            })

    @staticmethod
    async def record_failure(source_id: str, error_msg: str) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        health_records = await db.select("source_health", {"source_id": f"eq.{source_id}"})
        
        error_count = 1
        new_status = "degraded"
        
        if health_records:
            h = health_records[0]
            error_count = (h.get("error_count") or 0) + 1
            if error_count >= 5:
                new_status = "down"
            await db.update(
                "source_health",
                {"status": new_status, "error_count": error_count, "last_failure_at": now},
                {"source_id": f"eq.{source_id}"}
            )
        else:
            await db.insert("source_health", {
                "source_id": source_id,
                "status": new_status,
                "error_count": error_count,
                "last_failure_at": now
            })
            
        await db.update("sources", {"status": new_status}, {"id": f"eq.{source_id}"})
        return {"status": new_status, "error_count": error_count, "last_failure_at": now}

    @staticmethod
    async def save_raw_post(source_id: str, text: str) -> Optional[Dict[str, Any]]:
        return await db.insert("raw_posts", {
            "source_id": source_id,
            "text": text,
            "processed": False
        })
