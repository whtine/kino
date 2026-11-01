"""Role check middlewares: role based permissions and owner-only commands."""

import logging

from vkbottle import BaseMiddleware
from vkbottle.bot import Message

from bot.utils.permissions import (
    COMMAND_PERMISSIONS,
    check_permission,
    get_required_role,
    get_role_name,
)
from config import config
from db.repositories.members import MembersRepository

logger = logging.getLogger(__name__)
members_repo = MembersRepository()


def _command_name(message: Message) -> str:
    text = (getattr(message, "text", None) or "").strip()
    if not text.startswith("/"):
        return ""
    return text.split()[0].split("@", 1)[0].lstrip("/").lower()


class RoleCheckMiddleware(BaseMiddleware[Message]):
    """Reject commands that require a higher role than the sender has."""

    async def pre(self) -> None:
        message = self.event
        text = (getattr(message, "text", None) or "").strip()
        if message.peer_id < 2_000_000_000 or not text.startswith("/"):
            return

        command = _command_name(message)
        activation_command = str(config.activation_command or "*").strip().lstrip("/").split("@", 1)[0].lower()
        if command in {"activate", activation_command} or command in {"start", "help"}:
            return
        if command not in COMMAND_PERMISSIONS:
            return

        role = await members_repo.get_role(message.peer_id, message.from_id)
        required = get_required_role(command)
        if not check_permission(role, command):
            await message.answer(
                f"⛔ Недостаточно прав для /{command}.\n"
                f"Требуется: {get_role_name(required)} ({required}); "
                f"ваша роль: {get_role_name(role)} ({role})."
            )
            self.stop(f"Недостаточно прав для /{command}")


class OwnerCheckMiddleware(BaseMiddleware[Message]):
    """Require a VK chat administrator for group ownership operations."""

    OWNER_COMMANDS = {"creategroup", "bind", "async", "giveowner"}

    async def pre(self) -> None:
        message = self.event
        text = (getattr(message, "text", None) or "").strip()
        if message.peer_id < 2_000_000_000 or not text.startswith("/"):
            return
        command = _command_name(message)
        if command not in self.OWNER_COMMANDS:
            return
        from bot.utils.vk_api import vk_api

        try:
            if not vk_api or not await vk_api.is_chat_admin(message.peer_id, message.from_id):
                await message.answer("⛔ Команда доступна только администратору беседы.")
                self.stop(f"Команда /{command} доступна только администратору беседы.")
        except Exception:
            logger.exception("Could not verify chat admin for /%s", command)
            await message.answer("❌ Не удалось проверить права администратора.")
            self.stop(f"Ошибка проверки прав администратора для /{command}")


__all__ = ("OwnerCheckMiddleware", "RoleCheckMiddleware")
