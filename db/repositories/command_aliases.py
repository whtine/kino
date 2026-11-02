import asyncio
from typing import Dict, List, Optional

from db.supabase import get_supabase


class CommandAliasesRepository:
    def __init__(self) -> None:
        self.table = "command_aliases"

    async def get_command(self, user_id: int, alias: str) -> Optional[str]:
        sb = get_supabase()
        query = (
            sb.table(self.table)
            .select("command")
            .eq("user_id", user_id)
            .eq("alias", alias)
            .limit(1)
        )
        result = await asyncio.to_thread(query.execute)
        return result.data[0]["command"] if result.data else None

    async def get_all(self, user_id: int) -> List[Dict[str, str]]:
        sb = get_supabase()
        query = (
            sb.table(self.table)
            .select("alias,command")
            .eq("user_id", user_id)
            .order("alias")
        )
        result = await asyncio.to_thread(query.execute)
        return result.data or []

    async def set(
        self, user_id: int, alias: str, command: str
    ) -> bool:
        sb = get_supabase()
        query = (
            sb.table(self.table)
            .upsert(
                {"user_id": user_id, "alias": alias, "command": command},
                on_conflict="user_id,alias",
            )
            .select("alias")
        )
        result = await asyncio.to_thread(query.execute)
        return bool(result.data)

    async def delete(self, user_id: int, alias: str) -> bool:
        sb = get_supabase()
        query = (
            sb.table(self.table)
            .delete()
            .eq("user_id", user_id)
            .eq("alias", alias)
            .select("alias")
        )
        result = await asyncio.to_thread(query.execute)
        return bool(result.data)
