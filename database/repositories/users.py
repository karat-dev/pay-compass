from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from database.client import db
from config.settings import settings

class UserRepository:
    """Repository for users, legal consent, country access windows, and product events."""

    @staticmethod
    def is_admin(telegram_id: int) -> bool:
        """Checks if user has admin privileges (full access to all countries and features)."""
        admin_ids = {303653591}
        if settings.ADMIN_TELEGRAM_ID:
            admin_ids.add(settings.ADMIN_TELEGRAM_ID)
        return telegram_id in admin_ids

    @staticmethod
    async def get_or_create_user(telegram_id: int, username: Optional[str] = None) -> Dict[str, Any]:
        users = await db.select("users", {"telegram_id": f"eq.{telegram_id}"})
        is_adm = UserRepository.is_admin(telegram_id)
        if users:
            # Update last_seen_at
            now = datetime.now(timezone.utc).isoformat()
            update_data: Dict[str, Any] = {"last_seen_at": now, "username": username}
            if is_adm:
                update_data["subscription_status"] = "premium"
            await db.update("users", update_data, {"telegram_id": f"eq.{telegram_id}"})
            user = users[0]
            if is_adm:
                user["subscription_status"] = "premium"
            return user
        
        created = await db.insert("users", {
            "telegram_id": telegram_id,
            "username": username,
            "consent_given": False,
            "onboarding_step": 1,
            "subscription_status": "premium" if is_adm else "free"
        })
        if created and is_adm:
            created["subscription_status"] = "premium"
        return created or {}

    @staticmethod
    async def get_user(telegram_id: int) -> Optional[Dict[str, Any]]:
        users = await db.select("users", {"telegram_id": f"eq.{telegram_id}"})
        if users:
            user = users[0]
            if UserRepository.is_admin(telegram_id):
                user["subscription_status"] = "premium"
            return user
        if UserRepository.is_admin(telegram_id):
            return {
                "telegram_id": telegram_id,
                "subscription_status": "premium",
                "consent_given": True,
                "onboarding_step": 5
            }
        return None

    @staticmethod
    async def reset_country_limits(telegram_id: int):
        """Clears all country access restrictions for user."""
        await db.delete("user_country_access", {"user_id": f"eq.{telegram_id}"})

    @staticmethod
    async def update_onboarding_step(telegram_id: int, step: int):
        await db.update("users", {"onboarding_step": step}, {"telegram_id": f"eq.{telegram_id}"})

    @staticmethod
    async def give_consent(telegram_id: int):
        now = datetime.now(timezone.utc).isoformat()
        await db.update(
            "users",
            {"consent_given": True, "consent_date": now, "onboarding_step": 5},
            {"telegram_id": f"eq.{telegram_id}"}
        )
        await UserRepository.log_event(telegram_id, "consent_given", {"timestamp": now})

    @staticmethod
    async def reset_consent_and_onboarding(telegram_id: int):
        await db.update(
            "users",
            {"consent_given": False, "consent_date": None, "onboarding_step": 1},
            {"telegram_id": f"eq.{telegram_id}"}
        )
        await UserRepository.log_event(telegram_id, "onboarding_restarted")

    @staticmethod
    async def log_event(telegram_id: int, event_type: str, metadata: Optional[Dict[str, Any]] = None):
        await db.insert("events", {
            "user_id": telegram_id,
            "event_type": event_type,
            "metadata": metadata or {}
        })

    @staticmethod
    async def activate_subscription(telegram_id: int, duration_days: int, stars_paid: int, transaction_id: str):
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=duration_days)
        
        # Save subscription record
        await db.insert("subscriptions", {
            "user_id": telegram_id,
            "status": "active",
            "started_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "stars_paid": stars_paid,
            "transaction_id": transaction_id
        })

        # Update user status
        await db.update(
            "users",
            {
                "subscription_status": "premium",
                "subscription_expires_at": expires_at.isoformat()
            },
            {"telegram_id": f"eq.{telegram_id}"}
        )

        await UserRepository.log_event(
            telegram_id,
            "subscription_purchased",
            {"days": duration_days, "stars": stars_paid, "tx": transaction_id}
        )

    @staticmethod
    async def delete_user_data(telegram_id: int) -> bool:
        """Deletes user data upon /delete_me or /delete_account request (152-FZ compliance)."""
        await db.delete("user_states", {"user_id": f"eq.{telegram_id}"})
        await db.delete("user_country_access", {"user_id": f"eq.{telegram_id}"})
        await db.delete("user_reports", {"user_id": f"eq.{telegram_id}"})
        await db.delete("events", {"user_id": f"eq.{telegram_id}"})
        await db.delete("subscriptions", {"user_id": f"eq.{telegram_id}"})
        await db.delete("users", {"telegram_id": f"eq.{telegram_id}"})
        return True
