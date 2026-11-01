from db.supabase import get_supabase
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class PunishmentsRepository:
    def __init__(self):
        self.table = "punishments"

    async def add(self, chat_id: int, target_id: int, moderator_id: int, 
                  type: str, reason: str = None, duration: Optional[timedelta] = None) -> Optional[Dict[str, Any]]:
        """Add punishment record."""
        sb = get_supabase()
        data = {
            "chat_id": chat_id,
            "target_id": target_id,
            "moderator_id": moderator_id,
            "type": type,
            "reason": reason,
        }
        if duration:
            data["duration"] = str(duration)
        result = sb.table(self.table).insert(data).select("*").execute()
        return result.data[0] if result.data else None

    async def get_by_id(self, chat_id: int, punishment_id: int) -> Optional[Dict[str, Any]]:
        sb = get_supabase()
        result = (
            sb.table(self.table).select("*").eq("chat_id", chat_id)
            .eq("id", punishment_id).limit(1).execute()
        )
        return result.data[0] if result.data else None

    async def get_latest_by_type(
        self, chat_id: int, target_id: int, punishment_type: str
    ) -> Optional[Dict[str, Any]]:
        sb = get_supabase()
        result = (
            sb.table(self.table).select("*").eq("chat_id", chat_id)
            .eq("target_id", target_id).eq("type", punishment_type)
            .order("created_at", desc=True).limit(1).execute()
        )
        return result.data[0] if result.data else None

    async def delete_warn_by_id(
        self, chat_id: int, target_id: int, punishment_id: int
    ) -> bool:
        sb = get_supabase()
        result = (
            sb.table(self.table).delete().eq("chat_id", chat_id)
            .eq("target_id", target_id).eq("id", punishment_id)
            .eq("type", "warn").select("id").execute()
        )
        return bool(result.data)

    async def get_history(self, chat_id: int, target_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get punishment history for user in chat."""
        sb = get_supabase()
        result = sb.table(self.table).select("*").eq("chat_id", chat_id).eq("target_id", target_id).order("created_at", desc=True).limit(limit).execute()
        return result.data or []

    async def get_user_history(self, target_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all punishments for user across chats."""
        sb = get_supabase()
        result = sb.table(self.table).select("*").eq("target_id", target_id).order("created_at", desc=True).limit(limit).execute()
        return result.data or []

    async def get_active_warns(self, chat_id: int, target_id: int) -> List[Dict[str, Any]]:
        """Get active (not unwarned) warnings for user."""
        sb = get_supabase()
        result = (
            sb.table(self.table).select("*").eq("chat_id", chat_id)
            .eq("target_id", target_id).eq("type", "warn")
            .order("created_at").execute()
        )
        warns = result.data or []
        from db.repositories.members import MembersRepository
        active_count = (await MembersRepository().get(chat_id, target_id) or {}).get("warns", 0)
        return warns[-active_count:] if active_count else []

    async def get_mute_list(self, chat_id: int) -> List[Dict[str, Any]]:
        """Get latest mute records for users whose mute is still active."""
        sb = get_supabase()
        result = sb.table(self.table).select("*").eq("chat_id", chat_id).eq("type", "mute").execute()
        records = result.data or []
        latest = {}
        for record in records:
            target_id = record["target_id"]
            if target_id not in latest or record["created_at"] > latest[target_id]["created_at"]:
                latest[target_id] = record
        from db.repositories.members import MembersRepository
        member_repo = MembersRepository()
        active = []
        for target_id, record in latest.items():
            if await member_repo.is_muted(chat_id, target_id):
                active.append(record)
        return active

    async def get_warn_list(self, chat_id: int) -> List[Dict[str, Any]]:
        """Get all users with active warnings."""
        from db.repositories.members import MembersRepository
        repo = MembersRepository()
        member_rows = await repo.get_all_in_chat(chat_id)
        warnings = []
        for member in member_rows:
            if member.get("warns", 0):
                warnings.extend(await self.get_active_warns(chat_id, member["user_id"]))
        return warnings

    async def get_recent_logs(self, chat_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent punishment logs for chat."""
        sb = get_supabase()
        result = sb.table(self.table).select("*").eq("chat_id", chat_id).order("created_at", desc=True).limit(limit).execute()
        return result.data or []