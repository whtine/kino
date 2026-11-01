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
        if not conversation_message_ids:
            return False
        try:
            result = await self.api.messages.delete(
                peer_id=chat_id,
                cmids=conversation_message_ids,
                delete_for_all=delete_for_all,
            )
            if not isinstance(result, list):
                return bool(result)

            failed = []
            for requested_cmid, item in zip(conversation_message_ids, result):
                deleted = (
                    item.get("response") if isinstance(item, dict)
                    else getattr(item, "response", None)
                )
                if deleted is not True:
                    error = (
                        item.get("error") if isinstance(item, dict)
                        else getattr(item, "error", None)
                    )
                    failed.append((requested_cmid, error))
            if failed or len(result) != len(conversation_message_ids):
                logger.error(
                    "VK rejected message deletion in chat %s; failed items: %s",
                    chat_id,
                    failed or "response count did not match request",
                )
                return False
            return True
        except Exception:
            logger.exception(
                "Could not delete messages %s in chat %s",
                conversation_message_ids,
                chat_id,
            )
            return False

    async def clear_recent_messages(
        self, chat_id: int, amount: int, exclude_cmid: Optional[int] = None
    ) -> bool:
        try:
            history = await self.api.messages.get_history(
                peer_id=chat_id,
                count=amount + (1 if exclude_cmid else 0),
            )
            items = getattr(history, "items", None) or []
            ids = [
                item.conversation_message_id
                for item in items
                if getattr(item, "conversation_message_id", None) is not None
                and item.conversation_message_id != exclude_cmid
            ][:amount]
            return await self.delete_message(chat_id, ids) if ids else False
        except Exception as exc:
            error_code = getattr(exc, "code", getattr(exc, "error_code", "unknown"))
            error_message = getattr(exc, "error_msg", str(exc))
            logger.exception(
                "Could not read recent messages in chat %s (VK error %s: %s)",
                chat_id,
                error_code,
                error_message,
            )
            return False

    async def pin_message(self, chat_id: int, conversation_message_id: int) -> bool:
        try:
            await self.api.messages.pin(
                peer_id=chat_id,
                cmid=conversation_message_id,
            )
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
            return list(getattr(result, "items", None) or [])
        except Exception:
            logger.exception("Could not retrieve members of chat %s", chat_id)
            raise

    async def get_member_profiles(self, chat_id: int) -> List[Any]:
        """Return user profiles of conversation members."""
        try:
            result = await self.api.messages.get_conversation_members(
                peer_id=chat_id,
                extended=True,
            )
            return list(getattr(result, "profiles", None) or [])
        except Exception:
            logger.exception("Could not retrieve profiles of chat %s", chat_id)
            return []

    async def is_chat_admin(self, chat_id: int, user_id: int) -> bool:
        try:
            members = await self.get_conversation_members(chat_id)
        except Exception:
            logger.exception("Could not retrieve members of chat %s", chat_id)
            return False
        for member in members:
            member_id = member.get("member_id") if isinstance(member, dict) else member.member_id
            is_admin = member.get("is_admin") if isinstance(member, dict) else member.is_admin
            if member_id == user_id:
                return bool(is_admin)
        return False

    async def get_member_names(self, chat_id: int, user_ids: List[int]) -> Dict[int, str]:
        profiles = await self.get_member_profiles(chat_id)
        names: Dict[int, str] = {}
        wanted = set(user_ids or [])
        for profile in profiles:
            profile_id = profile.get("id") if isinstance(profile, dict) else profile.id
            if profile_id is None or profile_id not in wanted:
                continue
            first_name = (
                profile.get("first_name") if isinstance(profile, dict) else profile.first_name
            ) or ""
            last_name = (
                profile.get("last_name") if isinstance(profile, dict) else profile.last_name
            ) or ""
            names[profile_id] = f"{first_name} {last_name}".strip()
        return names

    async def mention_all(self, chat_id: int, max_mentions: int = 100) -> str:
        profiles = await self.get_member_profiles(chat_id)
        names: Dict[int, str] = {}
        for profile in profiles:
            profile_id = profile.get("id") if isinstance(profile, dict) else profile.id
            if profile_id is None:
                continue
            first_name = (
                profile.get("first_name") if isinstance(profile, dict) else profile.first_name
            ) or ""
            last_name = (
                profile.get("last_name") if isinstance(profile, dict) else profile.last_name
            ) or ""
            names[profile_id] = f"{first_name} {last_name}".strip()

        members = await self.get_conversation_members(chat_id)
        mentions: List[str] = []
        seen = set()
        for member in members:
            member_id = member.get("member_id") if isinstance(member, dict) else member.member_id
            if not member_id or member_id <= 0 or member_id in seen:
                continue
            if len(mentions) >= max_mentions:
                break
            name = names.get(member_id)
            if not name:
                continue
            first_name = name.split(" ")[0] if name else ""
            last_name = name.split(" ")[1] if len(name.split(" ")) > 1 else ""
            suffix = f" {last_name[0]}." if last_name else ""
            mentions.append(f"[id{member_id}|{first_name}{suffix}]")
            seen.add(member_id)
        return " ".join(mentions)

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_to: Optional[int] = None,
        keyboard: Optional[str] = None,
    ) -> bool:
        try:
            result = await self.api.messages.send(
                peer_id=chat_id,
                message=text,
                random_id=0,
                reply_to=reply_to,
                keyboard=keyboard,
            )
            return True
        except Exception:
            logger.exception("Could not send message to chat %s", chat_id)
            return False

    async def get_chat_info(self, chat_id: int) -> Optional[Dict[str, Any]]:
        try:
            result = await self.api.messages.get_conversations_by_id(peer_ids=[chat_id])
            items = getattr(result, "items", None) or []
            if not items:
                return None
            settings = getattr(items[0], "chat_settings", None)
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
