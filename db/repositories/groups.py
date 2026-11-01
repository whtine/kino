from db.supabase import get_supabase
from typing import Optional, Dict, Any, List


class GroupsRepository:
    def __init__(self):
        self.table = "chat_groups"

    async def create(self, name: str, owner_id: int) -> Dict[str, Any]:
        """Create new chat group."""
        sb = get_supabase()
        result = sb.table(self.table).insert({
            "name": name,
            "owner_id": owner_id
        }).execute()
        return result.data[0] if result.data else None

    async def get(self, group_id: int) -> Optional[Dict[str, Any]]:
        """Get group by ID."""
        sb = get_supabase()
        result = sb.table(self.table).select("*").eq("id", group_id).limit(1).execute()
        return result.data[0] if result.data else None

    async def get_by_owner(self, owner_id: int) -> List[Dict[str, Any]]:
        """Get all groups owned by user."""
        sb = get_supabase()
        result = sb.table(self.table).select("*").eq("owner_id", owner_id).execute()
        return result.data or []

    async def update(self, group_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update group."""
        sb = get_supabase()
        result = sb.table(self.table).update(data).eq("id", group_id).execute()
        return result.data[0] if result.data else None

    async def delete(self, group_id: int) -> bool:
        """Delete group (cascades to bindings, global_bans, global_nicknames)."""
        sb = get_supabase()
        result = sb.table(self.table).delete().eq("id", group_id).execute()
        return len(result.data or []) > 0

    async def get_bound_chats(self, group_id: int) -> List[int]:
        """Get chat_ids bound to this group."""
        sb = get_supabase()
        result = sb.table("chat_group_bindings").select("chat_id").eq("group_id", group_id).execute()
        return [r["chat_id"] for r in result.data or []]

    async def bind_chat(self, chat_id: int, group_id: int) -> bool:
        """Bind chat to group."""
        sb = get_supabase()
        result = sb.table("chat_group_bindings").upsert({
            "chat_id": chat_id,
            "group_id": group_id
        }).execute()
        return len(result.data or []) > 0

    async def unbind_chat(self, chat_id: int, group_id: int) -> bool:
        """Unbind chat from group."""
        sb = get_supabase()
        result = sb.table("chat_group_bindings").delete().eq("chat_id", chat_id).eq("group_id", group_id).execute()
        return len(result.data or []) > 0