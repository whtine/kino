import asyncio
from db.supabase import get_supabase
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class ChatsRepository:
    def __init__(self):
        self.table = "chats"

    async def get(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """Get chat by ID."""
        sb = get_supabase()
        result = await asyncio.to_thread(
            sb.table(self.table)
            .select("*")
            .eq("chat_id", chat_id)
            .limit(1)
            .execute
        )
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
        sb.table(self.table).upsert(data := {"chat_id": chat_id, "title": title or f"Chat {chat_id}"}, on_conflict="chat_id").execute()
        return await self.get(chat_id)

    async def update(self, chat_id: int, data: Dict[str, Any]) -> bool:
        """Update chat fields."""
        sb = get_supabase()
        result = (
            sb.table(self.table).update(data).eq("chat_id", chat_id)
            .select("chat_id").execute()
        )
        return bool(result.data)

    async def set_active(self, chat_id: int, is_active: bool) -> bool:
        """Activate/deactivate chat."""
        return await self.update(chat_id, {"is_active": is_active})

    async def update_settings(self, chat_id: int, settings: Dict[str, Any]) -> bool:
        """Update chat settings (merged with existing)."""
        chat = await self.get(chat_id)
        if not chat:
            return False
        current = dict(chat.get("settings") or {})
        current.update(settings)
        return await self.update(chat_id, {"settings": current})

    async def get_active_chats(self) -> List[Dict[str, Any]]:
        """Get all active chats."""
        sb = get_supabase()
        result = sb.table(self.table).select("*").eq("is_active", True).execute()
        return result.data or []

    async def is_banned(self, chat_id: int, user_id: int) -> bool:
        """Check whether a local chat ban is still active."""
        return bool(await self.get_ban(chat_id, user_id))

    async def get_ban(
        self, chat_id: int, user_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get an active local ban for one user."""
        sb = get_supabase()
        result = (
            sb.table("chat_bans").select("*")
            .eq("chat_id", chat_id).eq("user_id", user_id).limit(1)
        )
        result = await asyncio.to_thread(result.execute)
        if not result.data:
            return None
        ban = result.data[0]
        expires_at = ban.get("expires_at")
        if not expires_at:
            return ban
        expiration = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if expiration.tzinfo is None:
            expiration = expiration.replace(tzinfo=timezone.utc)
        return ban if expiration > datetime.now(timezone.utc) else None

    async def get_banned_list(self, chat_id: int) -> List[Dict[str, Any]]:
        """Get active local bans in a chat."""
        sb = get_supabase()
        result = (
            sb.table("chat_bans").select("*").eq("chat_id", chat_id).execute()
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

    async def bind_group(self, chat_id: int, group_id: int) -> bool:
        """Bind chat to a group."""
        sb = get_supabase()
        await self.get_or_create(chat_id)
        binding = sb.table("chat_group_bindings").upsert({
            "chat_id": chat_id,
            "group_id": group_id
        }).select("chat_id").execute()
        if not binding.data:
            return False
        updated = await self.update(chat_id, {"group_id": group_id})
        if not updated:
            (
                sb.table("chat_group_bindings").delete()
                .eq("chat_id", chat_id).eq("group_id", group_id).execute()
            )
            return False
        sb.table("chat_group_bindings").delete().eq("chat_id", chat_id).neq(
            "group_id", group_id
        ).execute()
        return True

    async def unbind_group(self, chat_id: int) -> bool:
        """Unbind chat from group."""
        sb = get_supabase()
        updated = await self.update(chat_id, {"group_id": None})
        sb.table("chat_group_bindings").delete().eq("chat_id", chat_id).execute()
        return updated