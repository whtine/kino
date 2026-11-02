"""Activation handlers: activation via '*' command or /activate."""

import logging

from vkbottle import Keyboard
from vkbottle.bot import Blueprint, Message, MessageEvent
from vkbottle.dispatch.rules.base import ChatActionRule

from bot.keyboards import get_activation_keyboard
from bot.utils.formatters import format_user_mention
from bot.utils.vk_api import vk_api
from bot.utils.permissions import get_role_name
from config import config
from db.repositories.chats import ChatsRepository
from db.repositories.members import MembersRepository
from db.repositories.punishments import PunishmentsRepository

logger = logging.getLogger(__name__)
bp = Blueprint("activation")
chats_repo = ChatsRepository()
members_repo = MembersRepository()
punishments_repo = PunishmentsRepository()

START_GREETING = (
    "Ура, вы меня добавили сюда! Я вам очень благодарен. "
    "Я бот, созданный именно для киностудии, чтобы выполнять задачи модерации. "
    "Нажмите снизу кнопку «Активировать», чтобы я начал работать в беседе."
)


async def _activate_chat(chat_id: int, user_id: int) -> tuple[bool, str]:
    if chat_id < 2_000_000_000:
        return False, "❌ Активация доступна только в беседах."
    try:
        is_admin = bool(vk_api and await vk_api.is_chat_admin(chat_id, user_id))
    except Exception:
        logger.exception("Could not check admin rights for activation in chat %s", chat_id)
        return False, "❌ Не удалось проверить права администратора."
    if not is_admin:
        return False, "❌ Только администратор беседы может активировать бота."

    try:
        chat = await chats_repo.get_or_create(chat_id)
        if not chat:
            raise RuntimeError("Не удалось создать запись беседы.")
        if chat.get("is_active"):
            return True, "✅ Бот уже активирован в этой беседе."
        details = await vk_api.get_chat_info(chat_id) if vk_api else None
        if details and details.get("title"):
            if not await chats_repo.update(chat_id, {"title": details["title"]}):
                raise RuntimeError("Не удалось сохранить название беседы.")
        if not await members_repo.set_role(chat_id, user_id, 4):
            raise RuntimeError("Не удалось назначить роль владельца.")
        role_log = await punishments_repo.add(
            chat_id,
            user_id,
            user_id,
            "role_change",
            f"Роль: назначено → {get_role_name(4)} (4)",
        )
        if not role_log:
            raise RuntimeError("Не удалось сохранить дату назначения роли.")
        if not await chats_repo.set_active(chat_id, True):
            raise RuntimeError("Не удалось сохранить статус активации.")
    except Exception:
        logger.exception("Could not activate chat %s", chat_id)
        return False, "❌ Не удалось активировать беседу. Попробуйте позже."

    names = await vk_api.get_member_names(chat_id, [user_id]) if vk_api else {}
    return True, (
        f"✅ Бот активирован!\nАдминистратор "
        f"{format_user_mention(user_id, names.get(user_id) or f'ID {user_id}')}"
        " получил роль 4 для первоначальной настройки.\nНапишите /help."
    )


async def _activate_in_chat(message: Message) -> None:
    succeeded, response = await _activate_chat(message.peer_id, message.from_id)
    await message.answer(response)


@bp.on.chat_message(command="start")
async def start_chat(message: Message):
    chat_id = message.peer_id
    if chat_id < 2_000_000_000:
        await message.answer(START_GREETING, keyboard=get_activation_keyboard())
        return
    chat = await chats_repo.get(chat_id)
    if not chat or not chat.get("is_active"):
        await message.answer(START_GREETING, keyboard=get_activation_keyboard())
        return
    await message.answer("Бот уже активирован в этой беседе. Список команд: /help")


@bp.on.chat_message(
    ChatActionRule(
        [
            "chat_invite_user",
            "chat_invite_user_by_link",
            "chat_invite_user_by_message_request",
        ]
    )
)
async def welcome_new_chat_member(message: Message):
    action = getattr(message, "action", None)
    action_type = getattr(action, "type", None)
    action_type = getattr(action_type, "value", action_type)
    if action_type not in {
        "chat_invite_user",
        "chat_invite_user_by_link",
        "chat_invite_user_by_message_request",
    }:
        return
    member_id = getattr(action, "member_id", None)
    if message.peer_id < 2_000_000_000 or not member_id:
        return
    if member_id == -config.group_id:
        await message.answer(
            START_GREETING,
            keyboard=get_activation_keyboard(),
        )
        return
    if member_id < 0:
        return

    names = await vk_api.get_member_names(message.peer_id, [member_id]) if vk_api else {}
    name = names.get(member_id) or f"ID {member_id}"
    await message.answer(
        f"{name}, добро пожаловать в беседу!\n"
        "Не забудь прочитать закреплённое сообщение!\n"
        "Посмотреть ссылки на официальные ресурсы отдела: /info"
    )


@bp.on.chat_message(ChatActionRule(["chat_kick_user"]))
async def clear_removed_member_role(message: Message):
    action = getattr(message, "action", None)
    action_type = getattr(action, "type", None)
    action_type = getattr(action_type, "value", action_type)
    member_id = getattr(action, "member_id", None)
    if (
        action_type != "chat_kick_user"
        or message.peer_id < 2_000_000_000
        or not isinstance(member_id, int)
        or member_id <= 0
    ):
        return

    previous_role = await members_repo.clear_role(message.peer_id, member_id)
    if previous_role is None:
        return

    actor_id = getattr(message, "from_id", None)
    if not isinstance(actor_id, int) or actor_id == 0:
        actor_id = member_id
    record = await punishments_repo.add(
        message.peer_id,
        member_id,
        actor_id,
        "role_change",
        f"Роль снята при исключении из беседы: "
        f"{get_role_name(previous_role)} ({previous_role}) → "
        f"{get_role_name(0)} (0)",
    )
    if not record:
        logger.error(
            "Could not log role removal for user %s in chat %s",
            member_id,
            message.peer_id,
        )


@bp.on.raw_event("message_event", MessageEvent, blocking=False)
async def activation_button(event: MessageEvent):
    if not isinstance(event.payload, dict) or event.payload.get("cmd") != "activate_chat":
        return
    succeeded, response = await _activate_chat(event.peer_id, event.user_id)
    if not succeeded:
        await event.show_snackbar(response)
        return
    await event.edit_message(
        message=response,
        keyboard=Keyboard(one_time=False, inline=True).get_json(),
    )
    await event.send_empty_answer()


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
    if await members_repo.get_role(chat_id, message.from_id) < 4:
        await message.answer("⛔ Требуется роль 4.")
        return
    if not await chats_repo.set_active(chat_id, False):
        await message.answer("❌ Не удалось сохранить статус деактивации.")
        return
    await message.answer("✅ Бот деактивирован в этой беседе.")
