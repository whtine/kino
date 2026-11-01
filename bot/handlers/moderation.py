"""Moderation handlers: kick, mute, warn, clear, ban, timeout and logs."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from vkbottle.bot import Bot, Message

from bot.dispatcher import bot
from bot.repositories import (
    ChatsRepository,
    GlobalBansRepository,
    MembersRepository,
    PunishmentsRepository,
)
from bot.utils import vk_api
from bot.utils.context import get_chat_id, get_user_id
from bot.utils.formatters import format_duration, format_punishments
from config import config


async def resolve_target(chat_id: int, user: Optional[str]) -> Optional[int]:
    """Resolve target user by nick or id."""
    if user and user.isdigit():
        return int(user)

    if user:
        # search by local nickname
        members = await MembersRepository().search_by_nickname(chat_id, user)
        if members:
            return members[0].get("user_id")

        # search by global nickname
        nicknames = await GlobalBansRepository().get_all_nicknames(config.group_id)
        for nick_entry in nicknames:
            if str(nick_entry.get("nickname") or "").lower() == str(user).lower():
                return nick_entry.get("user_id")

    return None


@bot.on.chat_message(text=["/kick", "/kick <user>"])
async def kick_handler(message: Message, user: Optional[str] = None):
    """Kick user from chat."""
    chat_id = get_chat_id(message)
    moderator_id = get_user_id(message)
    target_id = await resolve_target(chat_id, user)
    if target_id is None or moderator_id is None:
        await message.answer("Не удалось найти пользователя")
        return

    await PunishmentsRepository().add(chat_id, target_id, moderator_id, type="kick", reason=user or "kick")
    await vk_api.ban_user(bot, config.group_id, target_id, reason=f"kick:{user or ''}")

    member = await MembersRepository().get(chat_id, target_id)
    if member:
        await MembersRepository().update(chat_id, target_id, {"warns": 0})

    await message.answer(f"Пользователь {target_id} кикнут")


@bot.on.chat_message(text=["/mute", "/mute <user>"])
async def mute_handler(message: Message, user: Optional[str] = None):
    """Mute user in chat."""
    chat_id = get_chat_id(message)
    moderator_id = get_user_id(message)
    target_id = await resolve_target(chat_id, user)
    if target_id is None or moderator_id is None:
        await message.answer("Не удалось найти пользователя")
        return

    until = datetime.now(timezone.utc).timestamp()
    await MembersRepository().set_mute(chat_id, target_id, True, datetime.fromtimestamp(until, timezone.utc).isoformat())
    await PunishmentsRepository().add(
        chat_id, target_id, moderator_id, type="mute", reason=user or "mute", duration=timedelta(minutes=60)
    )
    await message.answer(f"Пользователь {target_id} замучен")


@bot.on.chat_message(text=["/warn", "/warn <user>"])
async def warn_handler(message: Message, user: Optional[str] = None):
    """Warn user in chat."""
    chat_id = get_chat_id(message)
    moderator_id = get_user_id(message)
    target_id = await resolve_target(chat_id, user)
    if target_id is None or moderator_id is None:
        await message.answer("Не удалось найти пользователя")
        return

    warns = await MembersRepository().add_warn(chat_id, target_id)
    await PunishmentsRepository().add(chat_id, target_id, moderator_id, type="warn", reason=user or "warn")
    await message.answer(f"Предупреждение выдано пользователю {target_id}. Всего предупреждений: {warns}")


@bot.on.chat_message(text="/clear")
async def clear_handler(message: Message):
    """Clear bot messages in chat."""
    chat_id = get_chat_id(message)
    history = await vk_api.get_history(bot, chat_id, limit=100)
    message_ids = [m.get("id") for m in history if m.get("id") and m.get("from_id") == -config.group_id]
    await vk_api.delete_messages(bot, chat_id, message_ids)
    await message.answer("Сообщения очищены")


@bot.on.chat_message(text=["/ban", "/ban <user>"])
async def ban_handler(message: Message, user: Optional[str] = None):
    """Ban user."""
    chat_id = get_chat_id(message)
    moderator_id = get_user_id(message)
    target_id = await resolve_target(chat_id, user)
    if target_id is None or moderator_id is None:
        await message.answer("Не удалось найти пользователя")
        return

    await PunishmentsRepository().add(chat_id, target_id, moderator_id, type="ban", reason=user or "ban")
    await vk_api.ban_user(bot, config.group_id, target_id, reason=user or "ban")
    await message.answer(f"Пользователь {target_id} забанен")


@bot.on.chat_message(text=["/unban", "/unban <user>"])
async def unban_handler(message: Message, user: Optional[str] = None):
    """Unban user."""
    chat_id = get_chat_id(message)
    moderator_id = get_user_id(message)
    target_id = await resolve_target(chat_id, user)
    if target_id is None or moderator_id is None:
        await message.answer("Не удалось найти пользователя")
        return

    await PunishmentsRepository().add(chat_id, target_id, moderator_id, type="unban", reason=user or "unban")
    await vk_api.unban_user(bot, config.group_id, target_id)
    await message.answer(f"Пользователь {target_id} разбанен")


@bot.on.chat_message(text=["/timeout", "/timeout <user>"])
async def timeout_handler(message: Message, user: Optional[str] = None):
    """Timeout (mute) user for minutes."""
    chat_id = get_chat_id(message)
    moderator_id = get_user_id(message)
    target_id = await resolve_target(chat_id, user)
    if target_id is None or moderator_id is None:
        await message.answer("Не удалось найти пользователя")
        return

    args = (message.text or "").split()
    minutes = 60
    if len(args) >= 3 and args[1].isdigit():
        minutes = int(args[1])

    until_ts = datetime.now(timezone.utc).timestamp() + minutes * 60
    await MembersRepository().set_mute(
        chat_id, target_id, True, datetime.fromtimestamp(until_ts, timezone.utc).isoformat()
    )
    await PunishmentsRepository().add(
        chat_id,
        target_id,
        moderator_id,
        type="timeout",
        reason=user or "timeout",
        duration=timedelta(minutes=minutes),
    )
    await message.answer(f"Пользователю {target_id} выдан таймаут на {minutes} мин")


@bot.on.chat_message(text=["/unmute", "/unmute <user>"])
async def unmute_handler(message: Message, user: Optional[str] = None):
    """Unmute user."""
    chat_id = get_chat_id(message)
    moderator_id = get_user_id(message)
    target_id = await resolve_target(chat_id, user)
    if target_id is None or moderator_id is None:
        await message.answer("Не удалось найти пользователя")
        return

    await MembersRepository().set_mute(chat_id, target_id, False, None)
    await PunishmentsRepository().add(chat_id, target_id, moderator_id, type="unmute", reason=user or "unmute")
    await message.answer(f"Пользователь {target_id} размучен")


@bot.on.chat_message(text=["/unwarn", "/unwarn <user>"])
async def unwarn_handler(message: Message, user: Optional[str] = None):
    """Remove warn from user."""
    chat_id = get_chat_id(message)
    moderator_id = get_user_id(message)
    target_id = await resolve_target(chat_id, user)
    if target_id is None or moderator_id is None:
        await message.answer("Не удалось найти пользователя")
        return

    remaining = await MembersRepository().remove_warn(chat_id, target_id)
    await PunishmentsRepository().add(chat_id, target_id, moderator_id, type="unwarn", reason=user or "unwarn")
    await message.answer(f"Предупреждений снято, осталось: {remaining}")


@bot.on.chat_message(text="/mutelist")
async def mutelist_handler(message: Message):
    """Show muted users in chat."""
    chat_id = get_chat_id(message)
    mutes = await PunishmentsRepository().get_mute_list(chat_id)
    lines = [f"• {m.get('target_id')} — {m.get('reason') or 'mute'}" for m in mutes]
    await message.answer("Замученные в чате:\n" + ("\n".join(lines) if lines else "Нет замученных"))


@bot.on.chat_message(text="/warnlist")
async def warnlist_handler(message: Message):
    """Show users with active warns in chat."""
    chat_id = get_chat_id(message)
    warns_list = await PunishmentsRepository().get_warn_list(chat_id)
    lines = [f"• {w.get('target_id')} — предупреждений: несколько" for w in warns_list]
    await message.answer("Пользователи с предупреждениями:\n" + ("\n".join(lines) if lines else "Нет активных предупреждений"))


@bot.on.chat_message(text=["/logs", "/logs <user>"])
async def logs_handler(message: Message, user: Optional[str] = None):
    """Show punishment history."""
    chat_id = get_chat_id(message)
    user_id = get_user_id(message)
    target_id = int(user) if user and user.isdigit() else user_id

    history = await PunishmentsRepository().get_history(chat_id, target_id, limit=50)
    text = format_punishments(history)
    await message.answer(text)
