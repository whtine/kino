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
    return (message.text or "").strip().split()[0][1:].split("@", 1)[0].lower()


class RoleCheckMiddleware(BaseMiddleware[Message]):
    """Reject commands above the sender's chat role."""

    async def pre(self):
        message = self.event
        text = (message.text or "").strip()
        if message.peer_id < 2_000_000_000 or not text.startswith("/"):
            return
        command = _command_name(message)
        activation_command = config.activation_command.strip().lstrip("/").split("@", 1)[0].lower()
        if command in {"activate", activation_command}:
            return
        if command not in COMMAND_PERMISSIONS:
            return
        role = await members_repo.get_role(message.peer_id, message.from_id)
        required = get_required_role(command)
        if not check_permission(role, required):
            await message.answer(
                f"⛔ Недостаточно прав для /{command}.\n"
                f"Требуется: {get_role_name(required)} ({required}); "
                f"ваша роль: {get_role_name(role)} ({role})."
            )
            self.stop()


class OwnerCheckMiddleware(BaseMiddleware[Message]):
    """Require a VK chat administrator for group ownership operations."""

    OWNER_COMMANDS = {"creategroup", "bind", "async", "giveowner"}

    async def pre(self):
        message = self.event
        text = (message.text or "").strip()
        if message.peer_id < 2_000_000_000 or not text.startswith("/"):
            return
        command = _command_name(message)
        if command not in self.OWNER_COMMANDS:
            return
        from bot.utils.vk_api import vk_api
        try:
            if not vk_api or not await vk_api.is_chat_admin(message.peer_id, message.from_id):
                await message.answer("⛔ Команда доступна только администратору беседы.")
                self.stop()
        except Exception:
            logger.exception("Could not verify chat admin for /%s", command)
            await message.answer("❌ Не удалось проверить права администратора.")
            self.stop()
