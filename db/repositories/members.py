import asyncio
from db.supabase import get_supabase
from typing import Optional, Dict, Any, List
import logging

from db.cache import repository_cache

logger = logging.getLogger(__name__)


class MembersRepository:
    def __init__(self):
        self.table = "chat_members"

    async def get(self, chat_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Get member by chat and user ID."""
        key = ("member", chat_id, user_id)
        cached, member = repository_cache.get(key)
        if cached:
            return member
        sb = get_supabase()
        result = await asyncio.to_thread(
            sb.table(self.table)
            .select("*")
            .eq("chat_id", chat_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute
        )
        member = result.data[0] if result.data else None
        repository_cache.set(key, member)
        return member

    async def get_or_create(self, chat_id: int, user_id: int) -> Dict[str, Any]:
        """Get existing member or create with default role 0."""
        member = await self.get(chat_id, user_id)
        if member:
            return member
        return await self.create(chat_id, user_id)

    async def create(self, chat_id: int, user_id: int, role: int = 0) -> Dict[str, Any]:
        """Create new member record."""
        sb = get_supabase()
        await asyncio.to_thread(
            sb.table(self.table).insert({
                "chat_id": chat_id,
                "user_id": user_id,
                "role": role,
            }).execute
        )
        repository_cache.invalidate(("member", chat_id, user_id))
        return await self.get(chat_id, user_id)

    async def update(self, chat_id: int, user_id: int, data: Dict[str, Any]) -> bool:
        """Update member fields."""
        sb = get_supabase()
        result = await asyncio.to_thread(
            sb.table(self.table).update(data).eq("chat_id", chat_id)
            .eq("user_id", user_id).select("user_id").execute
        )
        updated = bool(result.data)
        if updated:
            repository_cache.invalidate(("member", chat_id, user_id))
        return updated

    async def set_role(self, chat_id: int, user_id: int, role: int) -> bool:
        """Set member role (0-4)."""
        if not 0 <= role <= 4:
            raise ValueError("Role must be between 0 and 4")
        await self.get_or_create(chat_id, user_id)
        return await self.update(chat_id, user_id, {"role": role})

    async def clear_role(self, chat_id: int, user_id: int) -> Optional[int]:
        """Clear a member role and return its previous value."""
        member = await self.get(chat_id, user_id)
        previous_role = int(member.get("role", 0)) if member else 0
        if previous_role <= 0:
            return None

        sb = get_supabase()
        result = await asyncio.to_thread(
            sb.table(self.table)
            .update({"role": 0})
            .eq("chat_id", chat_id)
            .eq("user_id", user_id)
            .eq("role", previous_role)
            .select("user_id")
            .execute
        )
        if result.data:
            repository_cache.invalidate(("member", chat_id, user_id))
        return previous_role if result.data else None

    async def get_role(self, chat_id: int, user_id: int) -> int:
        """Get member role, default 0."""
        member = await self.get(chat_id, user_id)
        return member.get("role", 0) if member else 0

    async def set_nickname(self, chat_id: int, user_id: int, nickname: Optional[str]) -> bool:
        """Set or remove local nickname."""
        await self.get_or_create(chat_id, user_id)
        return await self.update(chat_id, user_id, {"nickname": nickname})

    async def get_nickname(self, chat_id: int, user_id: int) -> Optional[str]:
        """Get local nickname."""
        member = await self.get(chat_id, user_id)
        return member.get("nickname") if member else None

    async def add_warn(self, chat_id: int, user_id: int, amount: int = 1) -> int:
        """Increment warns count, return new count."""
        if amount < 1:
            raise ValueError("Warning amount must be positive")
        member = await self.get_or_create(chat_id, user_id)
        new_count = member.get("warns", 0) + amount
        if not await self.update(chat_id, user_id, {"warns": new_count}):
            raise RuntimeError(f"Could not update warnings for user {user_id}")
        return new_count

    async def remove_warn(self, chat_id: int, user_id: int, amount: int = 1) -> int:
        """Decrement warns count, return new count (min 0)."""
        if amount < 1:
            raise ValueError("Warning amount must be positive")
        member = await self.get_or_create(chat_id, user_id)
        new_count = max(0, member.get("warns", 0) - amount)
        if not await self.update(chat_id, user_id, {"warns": new_count}):
            raise RuntimeError(f"Could not update warnings for user {user_id}")
        return new_count

    async def set_warns(self, chat_id: int, user_id: int, count: int) -> bool:
        """Set warns count directly."""
        return await self.update(chat_id, user_id, {"warns": max(0, count)})

    async def set_mute(self, chat_id: int, user_id: int, is_muted: bool, muted_until: Optional[str] = None) -> bool:
        """Set mute status with optional expiration."""
        await self.get_or_create(chat_id, user_id)
        data = {"is_muted": is_muted}
        if muted_until:
            data["muted_until"] = muted_until
        else:
            data["muted_until"] = None
        return await self.update(chat_id, user_id, data)

    async def is_muted(self, chat_id: int, user_id: int) -> bool:
        """Check if user is currently muted."""
        member = await self.get(chat_id, user_id)
        if not member:
            return False
        if not member.get("is_muted"):
            return False
        muted_until = member.get("muted_until")
        if muted_until:
            from datetime import datetime, timezone
            expires_at = datetime.fromisoformat(muted_until.replace('Z', '+00:00'))
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < datetime.now(timezone.utc):
                # Mute expired, auto-unmute
                await self.set_mute(chat_id, user_id, False)
                return False
        return True

    async def get_staff(self, chat_id: int, min_role: int = 1) -> List[Dict[str, Any]]:
        """Get all members with role >= min_role."""
        sb = get_supabase()
        result = await asyncio.to_thread(
            sb.table(self.table).select("*").eq("chat_id", chat_id)
            .gte("role", min_role).order("role", desc=True).execute
        )
        return result.data or []

    async def get_online_staff(self, chat_id: int, online_user_ids: List[int], min_role: int = 1) -> List[Dict[str, Any]]:
        """Get staff members who are currently online."""
        staff = await self.get_staff(chat_id, min_role)
        return [m for m in staff if m["user_id"] in online_user_ids]

    async def get_all_in_chat(self, chat_id: int) -> List[Dict[str, Any]]:
        """Get all members in chat."""
        sb = get_supabase()
        result = await asyncio.to_thread(
            sb.table(self.table).select("*").eq("chat_id", chat_id).execute
        )
        return result.data or []

    async def search_by_nickname(self, chat_id: int, nickname: str) -> List[Dict[str, Any]]:
        """Search members by nickname (ILIKE)."""
        sb = get_supabase()
        result = await asyncio.to_thread(
            sb.table(self.table).select("*").eq("chat_id", chat_id)
            .ilike("nickname", f"%{nickname}%").execute
        )
        return result.data or []