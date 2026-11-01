import logging
from typing import Any, Dict, List, Optional

from vkbottle import API

logger = logging.getLogger(__name__)


class VKAPIWrapper:
    """VK API operations used by bot handlers and middleware."""

    def __init__(self, api: API):
        self.api = api

    async def kick_user(self, chat_id: int, user_id: int) -> bool:
        try:
            await self.api.messages.remove_chat_user(
                chat_id=chat_id - 2_000_000_000,
                member_id=user_id,
            )
            return True
        except Exception:
            logger.exception("Could not remove user %s from chat %s", user_id, chat_id)
            return False

    async def add_chat_user(self, chat_id: int, user_id: int) -> bool:
        try:
            await self.api.messages.add_chat_user(
                chat_id=chat_id - 2_000_000_000,
                user_id=user_id,
            )
            return True
        except Exception:
            logger.exception("Could not add user %s to chat %s", user_id, chat_id)
            return False

    async def delete_message(
        self, chat_id: int, conversation_message_ids: List[int], delete_for_all: bool = True
    ) -> bool:
        try:
            result = await self.api.messages.delete(
                peer_id=chat_id,
                cmids=conversation_message_ids,
                delete_for_all=delete_for_all,
            )
            return bool(result)
        except Exception:
            logger.exception("Could not delete messages in chat %s", chat_id)
            return False

    async def clear_recent_messages(self, chat_id: int, amount: int) -> bool:
        try:
            history = await self.api.messages.get_history(peer_id=chat_id, count=amount + 1)
            ids = [
                item.conversation_message_id
                for item in (getattr(history, "items", None) or [])
                if getattr(item, "conversation_message_id", None) is not None
            ][:amount]
            return await self.delete_message(chat_id, ids) if ids else False
        except Exception:
            logger.exception("Could not read recent messages in chat %s", chat_id)
            return False

    async def pin_message(self, chat_id: int, conversation_message_id: int) -> bool:
        try:
            await self.api.messages.pin(peer_id=chat_id, cmid=conversation_message_id)
            return True
        except Exception:
            logger.exception("Could not pin a message in chat %s", chat_id)
            return False

    async def unpin_message(self, chat_id: int) -> bool:
        try:
            await self.api.messages.unpin(peer_id=chat_id)
            return True
        except Exception:
            logger.exception("Could not unpin a message in chat %s", chat_id)
            return False

    async def get_conversation_members(self, chat_id: int) -> List[Any]:
        try:
            result = await self.api.messages.get_conversation_members(
                peer_id=chat_id,
                extended=True,
            )
            return result.profiles or []
        except Exception:
            logger.exception("Could not retrieve members of chat %s", chat_id)
            raise

    async def is_chat_admin(self, chat_id: int, user_id: int) -> bool:
        result = await self.api.messages.get_conversation_members(peer_id=chat_id)
        for member in getattr(result, "items", []) or []:
            member_id = getattr(member, "member_id", None)
            is_admin = getattr(member, "is_admin", False)
            is_owner = getattr(member, "is_owner", False)
            if isinstance(member, dict):
                member_id = member.get("member_id", member_id)
                is_admin = member.get("is_admin", is_admin)
                is_owner = member.get("is_owner", is_owner)
            if member_id == user_id:
                return bool(is_admin or is_owner)
        return False

    async def get_member_names(self, chat_id: int, user_ids: List[int]) -> Dict[int, str]:
        profiles = await self.get_conversation_members(chat_id)
        return {
            profile.id: f"{profile.first_name} {getattr(profile, 'last_name', '') or ''}".strip()
            for profile in profiles
            if profile.id in user_ids
        }

    async def mention_all(self, chat_id: int, max_mentions: int = 100) -> str:
        profiles = await self.get_conversation_members(chat_id)
        mentions = []
        for profile in profiles:
            if profile.id <= 0 or getattr(profile, "is_bot", False):
                continue
            if len(mentions) >= max_mentions:
                break
            last_name = getattr(profile, "last_name", "") or ""
            suffix = f" {last_name[0]}." if last_name else ""
            mentions.append(f"[id{profile.id}|{profile.first_name}{suffix}]")
        return " ".join(mentions)

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_to: Optional[int] = None,
        keyboard: Optional[str] = None,
    ) -> Optional[int]:
        try:
            result = await self.api.messages.send(
                peer_id=chat_id,
                message=text,
                random_id=0,
                reply_to=reply_to,
                keyboard=keyboard,
            )
            return result if isinstance(result, int) else None
        except Exception:
            logger.exception("Could not send message to chat %s", chat_id)
            return None

    async def get_chat_info(self, chat_id: int) -> Optional[Dict[str, Any]]:
        try:
            result = await self.api.messages.get_conversations_by_id(peer_ids=[chat_id])
            if not result.items:
                return None
            settings = result.items[0].chat_settings
            if not settings:
                return None
            return {
                "title": settings.title or "Без названия",
                "members_count": settings.members_count or 0,
            }
        except Exception:
            logger.exception("Could not retrieve chat info for %s", chat_id)
            return None


vk_api: Optional[VKAPIWrapper] = None


def init_vk_api(api: API) -> VKAPIWrapper:
    global vk_api
    vk_api = VKAPIWrapper(api)
    return vk_api
