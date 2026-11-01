"""User level commands: /id, /stats, /top, /chatid, /rep, /help."""

from vkbottle.bot import Bot, Message

from bot.dispatcher import bot
from bot.repositories import MembersRepository, StatsRepository
from bot.utils.context import get_chat_id, get_user_id
from bot.utils.formatters import format_top
from bot.utils.permissions import COMMAND_PERMISSIONS, get_role_name


@bot.on.chat_message(text=["/id", "/id <user>"])
async def id_handler(message: Message, user: str = None):
    """Get user info by id or show current user."""
    target_id = int(user) if user and user.isdigit() else get_user_id(message)
    if target_id is None:
        await message.answer("Не удалось определить пользователя")
        return

    users = await bot.api.users.get(user_ids=target_id)
    user_data = users[0] if users else {}
    text = (
        f"ID: {user_data.get('id')}\n"
        f"Имя: {user_data.get('first_name')}\n"
        f"Фамилия: {user_data.get('last_name')}"
    )
    await message.answer(text)


@bot.on.chat_message(text=["/stats", "/stats <user>"])
async def stats_handler(message: Message, user: str = None):
    """Show statistics of user in current chat."""
    chat_id = get_chat_id(message)
    user_id = get_user_id(message)
    target_id = int(user) if user and user.isdigit() else user_id

    stats_text = "Нет данных"
    if chat_id and target_id:
        stats = await StatsRepository().get_user_stats(chat_id, target_id)
        if stats:
            stats_text = f"Сообщений: {stats.get('count')}\nПоследнее: {stats.get('last_message_at')}"

        member = await MembersRepository().get(chat_id, target_id)
        warns = member.get("warns", 0) if member else 0
        stats_text += f"\nПредупреждений: {warns}"

    await message.answer(f"Статистика пользователя {target_id}:\n{stats_text}")


@bot.on.chat_message(text="/top")
async def top_handler(message: Message):
    """Show top users by messages in chat."""
    chat_id = get_chat_id(message)
    top = await StatsRepository().get_top(chat_id, limit=10)
    text = "Топ пользователей по количеству сообщений:\n" + format_top(top, [])
    await message.answer(text)


@bot.on.chat_message(text="/chatid")
async def chatid_handler(message: Message):
    """Show current chat id."""
    chat_id = get_chat_id(message)
    await message.answer(f"Chat ID: {chat_id}")


@bot.on.chat_message(text=["/rep", "/rep <user>"])
async def rep_handler(message: Message, user: str = None):
    """Show user reputation (warns count)."""
    chat_id = get_chat_id(message)
    user_id = get_user_id(message)
    target_id = int(user) if user and user.isdigit() else user_id

    member = await MembersRepository().get(chat_id, target_id) if chat_id and target_id else None
    warns = member.get("warns", 0) if member else 0
    await message.answer(f"Предупреждений у пользователя {target_id}: {warns}")


@bot.on.chat_message(text="/help")
async def help_handler(message: Message):
    """Show help message with available commands."""
    lines = []
    for command, required in sorted(COMMAND_PERMISSIONS.items(), key=lambda x: x[1]):
        lines.append(f"/{command} — {get_role_name(required)}")
    await message.answer("Доступные команды:\n" + "\n".join(lines))
