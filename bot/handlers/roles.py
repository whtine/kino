"""Role management handlers: /staff, /olist, /check, /addmlmoderator, /delmlmoderator, /addmoderator, /addstmoderator, /addadmin, /giveowner, /chat, /settings, /bind, /bindlist, /mygroups, /creategroup, /delgroup."""

from vkbottle.bot import Message

from bot.dispatcher import bot
from bot.repositories import ChatsRepository, GroupsRepository, MembersRepository
from bot.utils.context import get_chat_id, get_user_id
from config import config


@bot.on.chat_message(text="/staff")
async def staff_handler(message: Message):
    """Show staff members in chat."""
    chat_id = get_chat_id(message)
    staff = await MembersRepository().get_staff(chat_id, min_role=1)
    lines = [f"• {m.get('user_id')} — {m.get('nickname') or 'без ника'} (уровень {m.get('role')})" for m in staff]
    await message.answer("Статусы модераторов:\n" + ("\n".join(lines) if lines else "Нет модераторов"))


@bot.on.chat_message(text="/olist")
async def olist_handler(message: Message):
    """Show moderators list."""
    chat_id = get_chat_id(message)
    staff = await MembersRepository().get_staff(chat_id, min_role=2)
    lines = [f"• {m.get('user_id')} — {m.get('nickname') or 'без ника'}" for m in staff]
    await message.answer("Список модераторов:\n" + ("\n".join(lines) if lines else "Нет модераторов"))


@bot.on.chat_message(text=["/check", "/check <user>"])
async def check_handler(message: Message, user: str = None):
    """Check user state: warns / mute."""
    chat_id = get_chat_id(message)
    user_id = get_user_id(message)
    target_id = int(user) if user and user.isdigit() else user_id

    member = await MembersRepository().get(chat_id, target_id)
    warns = member.get("warns", 0) if member else 0
    muted = member.get("is_muted", False) if member else False
    await message.answer(f"Пользователь {target_id}: warns={warns}, muted={muted}")


@bot.on.chat_message(text=["/addmlmoderator", "/addmlmoderator <user>"])
async def addmlmoderator_handler(message: Message, user: str = None):
    """Add junior moderator."""
    chat_id = get_chat_id(message)
    moderator_id = get_user_id(message)
    target_id = int(user) if user and user.isdigit() else moderator_id

    await MembersRepository().set_role(chat_id, target_id, 1)
    await message.answer(f"Пользователю {target_id} назначен уровень: Младший модератор")


@bot.on.chat_message(text=["/delmlmoderator", "/delmlmoderator <user>"])
async def delmlmoderator_handler(message: Message, user: str = None):
    """Remove junior moderator."""
    chat_id = get_chat_id(message)
    moderator_id = get_user_id(message)
    target_id = int(user) if user and user.isdigit() else moderator_id

    await MembersRepository().set_role(chat_id, target_id, 0)
    await message.answer(f"Права модератора сняты у {target_id}")


@bot.on.chat_message(text=["/addmoderator", "/addmoderator <user>"])
async def addmoderator_handler(message: Message, user: str = None):
    """Add moderator."""
    chat_id = get_chat_id(message)
    moderator_id = get_user_id(message)
    target_id = int(user) if user and user.isdigit() else moderator_id

    await MembersRepository().set_role(chat_id, target_id, 2)
    await message.answer(f"Пользователю {target_id} назначен уровень: Модератор")


@bot.on.chat_message(text=["/addstmoderator", "/addstmoderator <user>"])
async def addstmoderator_handler(message: Message, user: str = None):
    """Add senior moderator."""
    chat_id = get_chat_id(message)
    moderator_id = get_user_id(message)
    target_id = int(user) if user and user.isdigit() else moderator_id

    await MembersRepository().set_role(chat_id, target_id, 3)
    await message.answer(f"Пользователю {target_id} назначен уровень: Старший модератор")


@bot.on.chat_message(text=["/addadmin", "/addadmin <user>"])
async def addadmin_handler(message: Message, user: str = None):
    """Add admin."""
    chat_id = get_chat_id(message)
    moderator_id = get_user_id(message)
    target_id = int(user) if user and user.isdigit() else moderator_id

    await MembersRepository().set_role(chat_id, target_id, 4)
    await message.answer(f"Пользователю {target_id} назначен уровень: Администратор")
