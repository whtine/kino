"""Ownership handlers: /giveowner, /import."""

from vkbottle.bot import Message

from bot.dispatcher import bot
from bot.repositories import ChatsRepository, GroupsRepository, MembersRepository
from bot.utils.context import get_chat_id, get_user_id
from config import config


@bot.on.chat_message(text=["/giveowner", "/giveowner <user>"])
async def giveowner_handler(message: Message, user: str = None):
    """Give special owner rights."""
    chat_id = get_chat_id(message)
    moderator_id = get_user_id(message)
    target_id = int(user) if user and user.isdigit() else moderator_id

    await MembersRepository().set_role(chat_id, target_id, 6)
    await message.answer(f"Пользователю {target_id} выданы спец. права")


@bot.on.chat_message(text="/import")
async def import_handler(message: Message):
    """Import chat state."""
    await message.answer("Импорт: загрузка состояния из конфигурации")
