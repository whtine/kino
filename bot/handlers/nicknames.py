"""Nickname handlers: /getnick, /snick, /rnick, /nlist, /gnick, /grnick."""

from vkbottle.bot import Message

from bot.dispatcher import bot
from bot.repositories import GlobalBansRepository, MembersRepository
from bot.utils.context import get_chat_id, get_user_id
from config import config


@bot.on.chat_message(text=["/getnick", "/getnick <user>"])
async def getnick_handler(message: Message, user: str = None):
    """Get local nickname of user."""
    chat_id = get_chat_id(message)
    user_id = get_user_id(message)
    target_id = int(user) if user and user.isdigit() else user_id

    member = await MembersRepository().get(chat_id, target_id)
    nick = member.get("nickname") if member else None
    await message.answer(f"Ник пользователя {target_id}: {nick or 'не установлен'}")


@bot.on.chat_message(text=["/rnick", "/rnick <user>"])
async def rnick_handler(message: Message, user: str = None):
    """Reset local nickname of user."""
    chat_id = get_chat_id(message)
    user_id = get_user_id(message)
    target_id = int(user) if user and user.isdigit() else user_id

    await MembersRepository().set_nickname(chat_id, target_id, None)
    await message.answer(f"Ник пользователя {target_id} сброшен")


@bot.on.chat_message(text="/nlist")
async def nlist_handler(message: Message):
    """List nicknames in chat."""
    chat_id = get_chat_id(message)
    members = await MembersRepository().get_all_in_chat(chat_id)
    lines = [f"• {m.get('user_id')} — {m.get('nickname') or 'без ника'}" for m in members if m.get("nickname")]
    await message.answer("Ники в чате:\n" + ("\n".join(lines) if lines else "Нет ников"))


@bot.on.chat_message(text=["/snick"])
async def snick_handler(message: Message, user: str = None):
    """Set local nickname: /snick <user> <nick>."""
    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.answer("Использование: /snick <user> <nick>")
        return

    user_id = int(parts[1]) if parts[1].isdigit() else get_user_id(message)
    nickname = parts[2]

    chat_id = get_chat_id(message)
    await MembersRepository().set_nickname(chat_id, user_id, nickname)
    await message.answer(f"Ник пользователя {user_id} установлен: {nickname}")


@bot.on.chat_message(text=["/gnick"])
async def gnick_handler(message: Message, user: str = None):
    """Set global nickname: /gnick <user> <nick>."""
    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.answer("Использование: /gnick <user> <nick>")
        return

    user_id = int(parts[1]) if parts[1].isdigit() else get_user_id(message)
    nickname = parts[2]

    await GlobalBansRepository().set_nickname(config.group_id, user_id, nickname, get_user_id(message))
    await message.answer(f"Глобальный ник для {user_id} установлен: {nickname}")


@bot.on.chat_message(text=["/grnick", "/grnick <user>"])
async def grnick_handler(message: Message, user: str = None):
    """Reset global nickname."""
    chat_id = get_chat_id(message)
    moderator_id = get_user_id(message)
    target_id = int(user) if user and user.isdigit() else moderator_id

    await GlobalBansRepository().remove_nickname(config.group_id, target_id)
    await message.answer(f"Глобальный ник для {target_id} сброшен")
