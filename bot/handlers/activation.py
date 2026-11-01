"""Activation handlers: activation via '*' command or /activate."""

import logging

from vkbottle.bot import Blueprint, Message

from bot.utils.formatters import format_user_mention
from bot.utils.vk_api import vk_api
from config import config
from db.repositories.chats import ChatsRepository
from db.repositories.members import MembersRepository

logger = logging.getLogger(__name__)
bp = Blueprint("activation")
chats_repo = ChatsRepository()
members_repo = MembersRepository()


async def _activate_in_chat(message: Message) -> None:
    """Shared activation routine for /activate and * commands."""
    chat_id = message.peer_id
    user_id = message.from_id
    if chat_id < 2_000_000_000:
        await message.answer("❌ Активация доступна только в беседах.")
        return
    try:
        is_admin = bool(vk_api and await vk_api.is_chat_admin(chat_id, user_id))
    except Exception:
        await message.answer("❌ Не удалось проверить права администратора.")
        return
    if not is_admin:
        await message.answer("❌ Только администратор беседы может активировать бота.")
        return

    try:
        chat = await chats_repo.get_or_create(chat_id)
        if not chat:
            raise RuntimeError("Не удалось создать запись беседы.")
        if chat.get("is_active"):
            await message.answer("✅ Бот уже активирован в этой беседе.")
            return
        details = await vk_api.get_chat_info(chat_id) if vk_api else None
        if details and details.get("title"):
            if not await chats_repo.update(chat_id, {"title": details["title"]}):
                raise RuntimeError("Не удалось сохранить название беседы.")
        if not await members_repo.set_role(chat_id, user_id, 6):
            raise RuntimeError("Не удалось назначить роль владельца.")
        if not await chats_repo.set_active(chat_id, True):
            raise RuntimeError("Не удалось сохранить статус активации.")
    except Exception:
        logger.exception("Could not activate chat %s", chat_id)
        await message.answer("❌ Не удалось активировать беседу. Попробуйте позже.")
        return

    await message.answer(
        f"✅ Бот активирован!\nАдминистратор {format_user_mention(user_id)} "
        "получил роль 6 для первоначальной настройки.\nНапишите /help."
    )


@bp.on.chat_message(command="activate")
async def activate_chat(message: Message):
    """Activate chat: /activate"""
    await _activate_in_chat(message)


_configured_activation_command = (
    str(config.activation_command or "/activate")
    .strip()
    .lstrip("/")
    .split("@", 1)[0]
    .lower()
)
if _configured_activation_command and _configured_activation_command != "activate":
    bp.on.chat_message(command=_configured_activation_command)(_activate_in_chat)


@bp.on.chat_message(regex=r"^\*$")
async def activate_star_handler(message: Message):
    """Activate chat: *"""
    await _activate_in_chat(message)


@bp.on.chat_message(command="deactivate")
async def deactivate_chat(message: Message):
    """Deactivate chat: /deactivate"""
    chat_id = message.peer_id
    if chat_id < 2_000_000_000:
        await message.answer("❌ Деактивация доступна только в беседах.")
        return
    if await members_repo.get_role(chat_id, message.from_id) < 6:
        await message.answer("⛔ Требуется роль 6.")
        return
    if not await chats_repo.set_active(chat_id, False):
        await message.answer("❌ Не удалось сохранить статус деактивации.")
        return
    await message.answer("✅ Бот деактивирован в этой беседе.")
