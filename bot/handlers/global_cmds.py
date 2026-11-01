"""Global commands: /zov, /gzov, /antitag, /pin, /unpin, /gban, /gunban, /gsnick, /grnick."""

from vkbottle.bot import Message

from bot.dispatcher import bot
from bot.repositories import ChatsRepository, GlobalBansRepository, PunishmentsRepository
from bot.utils import vk_api
from bot.utils.context import get_chat_id, get_user_id
from config import config


@bot.on.chat_message(text=["/zov", "/zov <user>"])
async def zov_handler(message: Message, user: str = None):
    """Call on user (mention)."""
    chat_id = get_chat_id(message)
    user_id = get_user_id(message)
    target_id = int(user) if user and user.isdigit() else user_id

    await message.answer(f"⚠️ ZOV: {target_id}")
    return


@bot.on.chat_message(text=["/gzov"])
async def gzov_handler(message: Message):
    """Global call on all group users."""
    await message.answer("⚠️ GZOV: все участники группы")


@bot.on.chat_message(text=["/antitag", "/antitag <user>"])
async def antitag_handler(message: Message, user: str = None):
    """Set antitag (prevent mentioning specific users)."""
    chat_id = get_chat_id(message)
    user_id = get_user_id(message)
    target_id = int(user) if user and user.isdigit() else user_id

    chats = ChatsRepository()
    chat = await chats.get(chat_id)
    settings = chat.get("settings") if chat else {}
    settings["antitag"] = target_id
    await chats.update_settings(chat_id, {"antitag": target_id})
    await message.answer(f"Анти-тег установлен для пользователя {target_id}")


@bot.on.chat_message(text=["/pin", "/pin <message_id>"])
async def pin_handler(message: Message, message_id: str = None):
    """Pin message."""
    chat_id = get_chat_id(message)
    mid = int(message_id) if message_id and message_id.isdigit() else None
    if mid is None:
        await message.answer("Использование: /pin <message_id>")
        return
    await vk_api.pin_message(bot, chat_id, mid)
    await message.answer("Сообщение закреплено")


@bot.on.chat_message(text=["/unpin", "/unpin <message_id>"])
async def unpin_handler(message: Message, message_id: str = None):
    """Unpin message."""
    chat_id = get_chat_id(message)
    mid = int(message_id) if message_id and message_id.isdigit() else None
    if mid is None:
        await message.answer("Использование: /unpin <message_id>")
        return
    await vk_api.unpin_message(bot, chat_id, mid)
    await message.answer("Сообщение откреплено")


@bot.on.chat_message(text=["/gban", "/gban <user>"])
async def gban_handler(message: Message, user: str = None):
    """Global ban user."""
    chat_id = get_chat_id(message)
    moderator_id = get_user_id(message)
    target_id = int(user) if user and user.isdigit() else moderator_id

    await PunishmentsRepository().add(chat_id, target_id, moderator_id, type="gban", reason=user or "gban")
    await vk_api.ban_user(bot, config.group_id, target_id, reason=user or "gban")
    await message.answer(f"Пользователь {target_id} забанен (global)")


@bot.on.chat_message(text=["/gunban", "/gunban <user>"])
async def gunban_handler(message: Message, user: str = None):
    """Global unban user."""
    chat_id = get_chat_id(message)
    moderator_id = get_user_id(message)
    target_id = int(user) if user and user.isdigit() else moderator_id

    await PunishmentsRepository().add(chat_id, target_id, moderator_id, type="gunban", reason=user or "gunban")
    await vk_api.unban_user(bot, config.group_id, target_id)
    await message.answer(f"Пользователь {target_id} разбанен (global)")


@bot.on.chat_message(text=["/gsnick"])
async def gsnick_handler(message: Message, user: str = None):
    """Set global nickname: /gsnick <user> <nick>."""
    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.answer("Использование: /gsnick <user> <nick>")
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
