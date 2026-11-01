from db.supabase import get_supabase
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class ChatsRepository:
    def __init__(self):
        self.table = "chats"

    async def get(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """Get chat by ID."""
        sb = get_supabase()
        result = sb.table(self.table).select("*").eq("chat_id", chat_id).limit(1).execute()
        return result.data[0] if result.data else None

    async def get_or_create(self, chat_id: int, title: str = None) -> Dict[str, Any]:
        """Get existing chat or create new one."""
        chat = await self.get(chat_id)
        if chat:
            return chat
        return await self.create(chat_id, title)

    async def create(self, chat_id: int, title: str = None) -> Dict[str, Any]:
        """Create new chat record."""
        sb = get_supabase()
        data = {"chat_id": chat_id, "title": title or f"Chat {chat_id}"}
        result = sb.table(self.table).upsert(data, on_conflict="chat_id").execute()
        return result.data[0] if result.data else None

    async def update(self, chat_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update chat fields."""
        sb = get_supabase()
        result = sb.table(self.table).update(data).eq("chat_id", chat_id).execute()
        return result.data[0] if result.data else None

    async def set_active(self, chat_id: int, is_active: bool) -> bool:
        """Activate/deactivate chat."""
        result = await self.update(chat_id, {"is_active": is_active})
        return result is not None

    async def update_settings(self, chat_id: int, settings: Dict[str, Any]) -> bool:
        """Update chat settings (merged with existing)."""
        chat = await self.get(chat_id)
        if not chat:
            return False
        current = dict(chat.get("settings") or {})
        current.update(settings)
        result = await self.update(chat_id, {"settings": current})
        return result is not None

    async def get_active_chats(self) -> List[Dict[str, Any]]:
        """Get all active chats."""
        sb = get_supabase()
        result = sb.table(self.table).select("*").eq("is_active", True).execute()
        return result.data or []

    async def bind_group(self, chat_id: int, group_id: int) -> bool:
        """Bind chat to a group."""
        sb = get_supabase()
        await self.get_or_create(chat_id)
        binding = sb.table("chat_group_bindings").upsert({
            "chat_id": chat_id,
            "group_id": group_id
        }).execute()
        # Update chat's group_id
        result = await self.update(chat_id, {"group_id": group_id})
        return bool(result and binding.data)

    async def unbind_group(self, chat_id: int) -> bool:
        """Unbind chat from group."""
        sb = get_supabase()
        result = await self.update(chat_id, {"group_id": None})
        if result:
            sb.table("chat_group_bindings").delete().eq("chat_id", chat_id).execute()
        return result is not None