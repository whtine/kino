import asyncio
from db.supabase import get_supabase
from db.cache import repository_cache
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone


class GlobalBansRepository:
    def __init__(self):
        self.bans_table = "global_bans"
        self.nicks_table = "global_nicknames"

    # Global Bans
    async def ban(
        self,
        group_id: int,
        user_id: int,
        reason: str,
        banned_by: int,
        duration: Optional[timedelta] = None,
    ) -> Optional[Dict[str, Any]]:
        """Add global ban."""
        sb = get_supabase()
        data = {
            "group_id": group_id,
            "user_id": user_id,
            "reason": reason,
            "banned_by": banned_by,
            "expires_at": (
                (datetime.now(timezone.utc) + duration).isoformat()
                if duration
                else None
            ),
        }
        result = await asyncio.to_thread(
            sb.table(self.bans_table).upsert(data).select("user_id").execute
        )
        repository_cache.invalidate(("global_ban", group_id, user_id))
        return result.data[0] if result.data else None

    async def unban(self, group_id: int, user_id: int) -> bool:
        """Remove global ban."""
        sb = get_supabase()
        result = await asyncio.to_thread(
            sb.table(self.bans_table).delete().eq("group_id", group_id)
            .eq("user_id", user_id).select("user_id").execute
        )
        repository_cache.invalidate(("global_ban", group_id, user_id))
        return bool(result.data)

    async def is_banned(self, group_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Check if user is globally banned in group."""
        key = ("global_ban", group_id, user_id)
        cached, ban = repository_cache.get(key)
        if cached:
            return self._active_ban(ban)
        sb = get_supabase()
        query = (
            sb.table(self.bans_table).select("*").eq("group_id", group_id)
            .eq("user_id", user_id).limit(1)
        )
        result = await asyncio.to_thread(query.execute)
        if not result.data:
            repository_cache.set(key, None)
            return None
        ban = result.data[0]
        repository_cache.set(key, ban)
        return self._active_ban(ban)

    @staticmethod
    def _active_ban(ban: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not ban:
            return None
        expires_at = ban.get("expires_at")
        if expires_at:
            expiration = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if expiration.tzinfo is None:
                expiration = expiration.replace(tzinfo=timezone.utc)
            if expiration <= datetime.now(timezone.utc):
                return None
        return ban

    async def get_banned_list(self, group_id: int) -> List[Dict[str, Any]]:
        """Get all global bans in group."""
        sb = get_supabase()
        result = await asyncio.to_thread(
            sb.table(self.bans_table).select("*").eq("group_id", group_id).execute
        )
        now = datetime.now(timezone.utc)
        active = []
        for ban in result.data or []:
            expires_at = ban.get("expires_at")
            if not expires_at:
                active.append(ban)
                continue
            expiration = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if expiration.tzinfo is None:
                expiration = expiration.replace(tzinfo=timezone.utc)
            if expiration > now:
                active.append(ban)
        return active

    # Global Nicknames
    async def set_nickname(
        self, group_id: int, user_id: int, nickname: str, set_by: int
    ) -> Optional[Dict[str, Any]]:
        """Set global nickname."""
        sb = get_supabase()
        result = await asyncio.to_thread(sb.table(self.nicks_table).upsert({
            "group_id": group_id,
            "user_id": user_id,
            "nickname": nickname,
            "set_by": set_by
        }).select("user_id").execute)
        return result.data[0] if result.data else None

    async def remove_nickname(self, group_id: int, user_id: int) -> bool:
        """Remove global nickname."""
        sb = get_supabase()
        result = await asyncio.to_thread(
            sb.table(self.nicks_table).delete().eq("group_id", group_id)
            .eq("user_id", user_id).select("user_id").execute
        )
        return bool(result.data)

    async def get_nickname(self, group_id: int, user_id: int) -> Optional[str]:
        """Get global nickname."""
        sb = get_supabase()
        result = await asyncio.to_thread(
            sb.table(self.nicks_table).select("nickname").eq("group_id", group_id)
            .eq("user_id", user_id).limit(1).execute
        )
        return result.data[0]["nickname"] if result.data else None

    async def get_all_nicknames(self, group_id: int) -> List[Dict[str, Any]]:
        """Get all global nicknames in group."""
        sb = get_supabase()
        result = await asyncio.to_thread(
            sb.table(self.nicks_table).select("*").eq("group_id", group_id).execute
        )
        return result.data or []