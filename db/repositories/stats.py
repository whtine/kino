from db.supabase import get_supabase
from typing import Optional, Dict, Any, List


class StatsRepository:
    def __init__(self):
        self.table = "message_stats"

    async def increment(self, chat_id: int, user_id: int) -> int:
        """Increment message count for user in chat, return new count."""
        sb = get_supabase()
        result = sb.rpc("increment_message_stat", {
            "p_chat_id": chat_id,
            "p_user_id": user_id,
        }).execute()
        return int(result.data)

    async def get_count(self, chat_id: int, user_id: int) -> int:
        """Get message count for user in chat."""
        sb = get_supabase()
        result = sb.table(self.table).select("count").eq("chat_id", chat_id).eq("user_id", user_id).limit(1).execute()
        return result.data[0]["count"] if result.data else 0

    async def get_top(self, chat_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top users by message count in chat."""
        sb = get_supabase()
        result = sb.table(self.table).select("*").eq("chat_id", chat_id).order("count", desc=True).limit(limit).execute()
        return result.data or []

    async def get_user_stats(self, chat_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Get full stats for user in chat."""
        sb = get_supabase()
        result = sb.table(self.table).select("*").eq("chat_id", chat_id).eq("user_id", user_id).limit(1).execute()
        return result.data[0] if result.data else None