"""Settings handlers: /settings."""

from vkbottle.bot import Message

from bot.dispatcher import bot
from bot.repositories import ChatsRepository
from bot.utils.context import get_chat_id, get_user_id


@bot.on.chat_message(text=["/settings", "/settings <key> <value>"])
async def settings_handler(message: Message, key: str = None, value: str = None):
    """Show or update chat settings."""
    chat_id = get_chat_id(message)
    user_id = get_user_id(message)

    chats = ChatsRepository()
    chat = await chats.get(chat_id)
    if chat is None:
        await message.answer("Чат не найден")
        return

    settings = chat.get("settings") or {}
    if key:
        settings[key] = value
        await chats.update_settings(chat_id, {key: value})

    await message.answer(f"Настройки чата {chat_id}:\n" + "\n".join(f"{k}: {v}" for k, v in settings.items()))
