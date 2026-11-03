import logging
from collections import OrderedDict
from typing import Any, Dict, List, Optional

from vkbottle import API

logger = logging.getLogger(__name__)

_RECENT_MESSAGE_LIMIT = 500
_recent_chat_messages: Dict[int, OrderedDict[int, int]] = {}


def remember_chat_message(chat_id: int, cmid: int, user_id: int) -> None:
    """Keep a bounded in-process message index for chats where history is unavailable."""
    messages = _recent_chat_messages.setdefault(chat_id, OrderedDict())
    messages[cmid] = user_id
    messages.move_to_end(cmid)
    while len(messages) > _RECENT_MESSAGE_LIMIT:
        messages.popitem(last=False)


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

    async def get_message_by_cmid(self, chat_id: int, cmid: int) -> Optional[Any]:
        """Fetch one conversation message by its conversation message ID."""
        try:
            result = await self.api.messages.get_by_conversation_message_id(
                peer_id=chat_id,
                conversation_message_ids=[cmid],
            )
            items = getattr(result, "items", None) or []
            return items[0] if items else None
        except Exception:
            logger.exception(
                "Could not retrieve conversation message %s in chat %s",
                cmid,
                chat_id,
            )
            return None

    async def clear_recent_messages(
        self,
        chat_id: int,
        amount: int,
        exclude_cmid: Optional[int] = None,
        protected_user_ids: Optional[set[int]] = None,
    ) -> bool:
        try:
            history = await self.api.messages.get_history(
                peer_id=chat_id,
                count=min(
                    amount
                    + (1 if exclude_cmid else 0)
                    + len(protected_user_ids or set()),
                    200,
                ),
            )
            items = getattr(history, "items", None) or []
            messages = [
                (
                    getattr(item, "conversation_message_id", None),
                    getattr(item, "from_id", None),
                )
                for item in items
            ]
        except Exception as exc:
            error_code = getattr(exc, "code", getattr(exc, "error_code", "unknown"))
            error_message = getattr(exc, "error_msg", str(exc))
            if error_code == 15:
                logger.warning(
                    "VK denied history access in chat %s (error %s: %s); "
                    "will use cached messages if available",
                    chat_id,
                    error_code,
                    error_message,
                )
            else:
                logger.exception(
                    "Could not read recent messages in chat %s (VK error %s: %s)",
                    chat_id,
                    error_code,
                    error_message,
                )
            if error_code != 15:
                return False
            cached = _recent_chat_messages.get(chat_id)
            if not cached:
                logger.warning(
                    "No cached messages available to clear chat %s after VK denied history access",
                    chat_id,
                )
                return False
            messages = list(reversed(cached.items()))
            logger.warning(
                "Using %s in-process cached messages to clear chat %s; "
                "messages from before this process started are unavailable",
                len(messages),
                chat_id,
            )

        protected = protected_user_ids or set()
        ids = [
            cmid
            for cmid, sender_id in messages
            if cmid is not None
            and cmid != exclude_cmid
            and sender_id not in protected
        ][:amount]
        skipped = sum(
            1
            for cmid, sender_id in messages
            if cmid != exclude_cmid and sender_id in protected
        )
        if skipped:
            logger.info(
                "Skipped %s messages from higher-role users while clearing chat %s",
                skipped,
                chat_id,
            )
        return await self.delete_message(chat_id, ids) if ids else False

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

    async def unpin_message(
        self, chat_id: int, conversation_message_id: Optional[int] = None
    ) -> bool:
        try:
            if conversation_message_id is not None:
                result = await self.api.messages.get_conversations_by_id(
                    peer_ids=[chat_id]
                )
                items = getattr(result, "items", None) or []
                settings = (
                    getattr(items[0], "chat_settings", None) if items else None
                )
                pinned = getattr(settings, "pinned_message", None)
                if (
                    not pinned
                    or getattr(pinned, "conversation_message_id", None)
                    != conversation_message_id
                ):
                    return False
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
            member_id = (
                member.get("member_id")
                if isinstance(member, dict)
                else getattr(member, "member_id", None)
            )
            is_admin = (
                member.get("is_admin")
                if isinstance(member, dict)
                else getattr(member, "is_admin", False)
            )
            is_owner = (
                member.get("is_owner")
                if isinstance(member, dict)
                else getattr(member, "is_owner", False)
            )
            if member_id == user_id:
                return bool(is_admin or is_owner)
        return False

    async def get_member_names(self, chat_id: int, user_ids: List[int]) -> Dict[int, str]:
        wanted = set(user_ids or [])
        if not wanted:
            return {}

        names: Dict[int, str] = {}

        def display_name(profile: Any) -> tuple[Optional[int], str]:
            if isinstance(profile, dict):
                profile_id = profile.get("id")
                first_name = profile.get("first_name") or ""
                last_name = profile.get("last_name") or ""
                screen_name = profile.get("screen_name") or ""
            else:
                profile_id = getattr(profile, "id", None)
                first_name = getattr(profile, "first_name", "") or ""
                last_name = getattr(profile, "last_name", "") or ""
                screen_name = getattr(profile, "screen_name", "") or ""
            name = f"{first_name} {last_name}".strip() or screen_name
            return profile_id, name

        lookup_ids = [user_id for user_id in wanted if user_id > 0]
        if lookup_ids:
            try:
                profiles = await self.api.users.get(user_ids=lookup_ids)
            except Exception:
                logger.exception(
                    "Could not retrieve VK names for users %s in chat %s",
                    lookup_ids,
                    chat_id,
                )
            else:
                for profile in profiles:
                    profile_id, name = display_name(profile)
                    if profile_id in wanted and name:
                        names[profile_id] = name

        profiles = await self.get_member_profiles(chat_id)
        for profile in profiles:
            profile_id, name = display_name(profile)
            if profile_id in wanted and name:
                names.setdefault(profile_id, name)
        return names

    async def resolve_user_id(self, screen_name: str) -> Optional[int]:
        """Resolve a VK profile screen name to a positive user ID."""
        try:
            profiles = await self.api.users.get(user_ids=[screen_name])
        except Exception:
            logger.exception("Could not resolve VK profile %s", screen_name)
            return None
        if not profiles:
            return None
        profile = profiles[0]
        user_id = (
            profile.get("id") if isinstance(profile, dict)
            else getattr(profile, "id", None)
        )
        return int(user_id) if user_id and int(user_id) > 0 else None

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
            mentions.append(
                f"[id{member_id}|{first_name}{suffix} (ID: {member_id})]"
            )
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
