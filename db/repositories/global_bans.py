from db.supabase import get_supabase
from typing import Optional, Dict, Any, List


class GlobalBansRepository:
    def __init__(self):
        self.bans_table = "global_bans"
        self.nicks_table = "global_nicknames"

    # Global Bans
    async def ban(
        self, group_id: int, user_id: int, reason: str, banned_by: int
    ) -> Optional[Dict[str, Any]]:
        """Add global ban."""
        sb = get_supabase()
        result = sb.table(self.bans_table).upsert({
            "group_id": group_id,
            "user_id": user_id,
            "reason": reason,
            "banned_by": banned_by
        }).select("user_id").execute()
        return result.data[0] if result.data else None

    async def unban(self, group_id: int, user_id: int) -> bool:
        """Remove global ban."""
        sb = get_supabase()
        result = (
            sb.table(self.bans_table).delete().eq("group_id", group_id)
            .eq("user_id", user_id).select("user_id").execute()
        )
        return bool(result.data)

    async def is_banned(self, group_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Check if user is globally banned in group."""
        sb = get_supabase()
        result = sb.table(self.bans_table).select("*").eq("group_id", group_id).eq("user_id", user_id).limit(1).execute()
        return result.data[0] if result.data else None

    async def get_banned_list(self, group_id: int) -> List[Dict[str, Any]]:
        """Get all global bans in group."""
        sb = get_supabase()
        result = sb.table(self.bans_table).select("*").eq("group_id", group_id).execute()
        return result.data or []

    # Global Nicknames
    async def set_nickname(
        self, group_id: int, user_id: int, nickname: str, set_by: int
    ) -> Optional[Dict[str, Any]]:
        """Set global nickname."""
        sb = get_supabase()
        result = sb.table(self.nicks_table).upsert({
            "group_id": group_id,
            "user_id": user_id,
            "nickname": nickname,
            "set_by": set_by
        }).select("user_id").execute()
        return result.data[0] if result.data else None

    async def remove_nickname(self, group_id: int, user_id: int) -> bool:
        """Remove global nickname."""
        sb = get_supabase()
        result = (
            sb.table(self.nicks_table).delete().eq("group_id", group_id)
            .eq("user_id", user_id).select("user_id").execute()
        )
        return bool(result.data)

    async def get_nickname(self, group_id: int, user_id: int) -> Optional[str]:
        """Get global nickname."""
        sb = get_supabase()
        result = sb.table(self.nicks_table).select("nickname").eq("group_id", group_id).eq("user_id", user_id).limit(1).execute()
        return result.data[0]["nickname"] if result.data else None

    async def get_all_nicknames(self, group_id: int) -> List[Dict[str, Any]]:
        """Get all global nicknames in group."""
        sb = get_supabase()
        result = sb.table(self.nicks_table).select("*").eq("group_id", group_id).execute()
        return result.data or []