"""Activation middleware: allows activation commands and guards inactive chats."""

import logging
import re

from vkbottle import BaseMiddleware
from vkbottle.bot import Message

from bot.utils.context import get_chat_id
from bot.utils.vk_api import vk_api
from config import config
from db.repositories.chats import ChatsRepository
from db.repositories.global_bans import GlobalBansRepository
from db.repositories.members import MembersRepository

logger = logging.getLogger(__name__)
chats_repo = ChatsRepository()
members_repo = MembersRepository()
global_bans_repo = GlobalBansRepository()
ALLOWED_COMMANDS = {"activate", "start"}


def _is_antitag_violation(settings: dict, text: str) -> bool:
    if not settings.get("antitag"):
        return False
    mentioned = {int(value) for value in re.findall(r"(?:\[id|@id)(\d+)", text)}
    if not mentioned:
        return False
    restricted = {int(value) for value in (settings.get("antitag_users") or [])}
    return not restricted or bool(mentioned & restricted)


class ActivationMiddleware(BaseMiddleware[Message]):
    """Allow activation commands and block processing in inactive chats."""

    async def pre(self) -> None:
        message = self.event
        chat_id = get_chat_id(message)
        if chat_id is None:
            # Private messages have no activation state
            return

        text = (getattr(message, "text", None) or "").strip()
        action = getattr(message, "action", None)
        action_type = getattr(action, "type", None)
        if action_type is not None and str(getattr(action_type, "value", action_type)) in {
            "chat_invite_user",
            "chat_invite_user_by_link",
            "chat_invite_user_by_message_request",
        }:
            return

        command = (
            text.split()[0].split("@", 1)[0].lstrip("/").lower()
            if text.startswith("/")
            else None
        )
        activation_command = (
            str(config.activation_command or "/activate")
            .strip()
            .lstrip("/")
            .split("@", 1)[0]
            .lower()
        )

        chat = await chats_repo.get(chat_id)
        if chat is None or not chat.get("is_active"):
            if command in ALLOWED_COMMANDS or command == activation_command or text == "*":
                return
            self.send({"denied": True, "reason": "chat_not_activated"})
            self.stop(f"Чат {chat_id} не активирован")
        if command in ALLOWED_COMMANDS or command == activation_command or text == "*":
            return

        if message.from_id > 0:
            if await members_repo.is_muted(chat_id, message.from_id):
                await self._delete_message(message, chat_id)
                self.stop(f"Пользователь {message.from_id} замучен")
                return

            group_id = chat.get("group_id")
            is_banned = await chats_repo.is_banned(chat_id, message.from_id)
            if group_id:
                is_banned = is_banned or bool(
                    await global_bans_repo.is_banned(group_id, message.from_id)
                )
            if is_banned:
                await self._delete_message(message, chat_id)
                if vk_api and not await vk_api.kick_user(chat_id, message.from_id):
                    logger.error(
                        "Could not enforce active ban for user %s in chat %s",
                        message.from_id,
                        chat_id,
                    )
                self.stop(f"Пользователь {message.from_id} заблокирован в беседе")
                return

        settings = chat.get("settings") or {}
        if settings.get("timeout") and not (getattr(message, "text", None) or "").strip().startswith("/"):
            await self._delete_message(message, chat_id)
            self.stop(f"Тихий режим активен в чате {chat_id}")

        if _is_antitag_violation(settings, text):
            await self._delete_message(message, chat_id)
            self.stop(f"Анти-тег активен в чате {chat_id}")

    async def _delete_message(self, message: Message, chat_id: int) -> None:
        message_id = getattr(message, "conversation_message_id", None)
        if message_id and vk_api:
            if not await vk_api.delete_message(chat_id, [message_id]):
                logger.error("Failed to delete restricted message %s in chat %s", message_id, chat_id)


__all__ = ("ActivationMiddleware",)
