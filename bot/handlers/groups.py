"""Group handlers: /mygroups, /creategroup, /delgroup, /bind, /bindlist, /chat, /async."""

from vkbottle.bot import Message

from bot.dispatcher import bot
from bot.repositories import ChatsRepository, GroupsRepository
from bot.utils.context import get_chat_id, get_user_id
from config import config


@bot.on.chat_message(text="/mygroups")
async def mygroups_handler(message: Message):
    """Show groups owned by user."""
    owner_id = get_user_id(message)
    groups = await GroupsRepository().get_by_owner(owner_id)
    lines = [f"• {g.get('id')} — {g.get('name')}" for g in groups]
    await message.answer("Ваши группы:\n" + ("\n".join(lines) if lines else "Нет групп"))


@bot.on.chat_message(text=["/creategroup", "/creategroup <name>"])
async def creategroup_handler(message: Message, name: str = None):
    """Create new group."""
    owner_id = get_user_id(message)
    group_name = name or "Group"
    group = await GroupsRepository().create(group_name, owner_id)
    await message.answer(f"Группа создана: {group.get('id') if group else group_name}")


@bot.on.chat_message(text="/delgroup")
async def delgroup_handler(message: Message):
    """Delete group."""
    group_id = int(message.text.split()[1]) if len(message.text.split()) > 1 and message.text.split()[1].isdigit() else config.group_id
    deleted = await GroupsRepository().delete(group_id)
    await message.answer(f"Группа {group_id} удалена: {deleted}")


@bot.on.chat_message(text=["/bind", "/bind <chat_id> <group_id>"])
async def bind_handler(message: Message, chat_id: str = None, group_id: str = None):
    """Bind chat to group."""
    target_chat = int(chat_id) if chat_id and chat_id.isdigit() else get_chat_id(message)
    gid = int(group_id) if group_id and group_id.isdigit() else config.group_id
    if target_chat is None:
        await message.answer("Не удалось определить чат")
        return
    ok = await ChatsRepository().bind_group(target_chat, gid)
    await message.answer(f"Чат {target_chat} привязан к группе {gid}: {ok}")


@bot.on.chat_message(text="/bindlist")
async def bindlist_handler(message: Message):
    """List chat-group bindings."""
    group_id = config.group_id
    chat_ids = await GroupsRepository().get_bound_chats(group_id)
    await message.answer(f"Привязанные чаты группы {group_id}: {chat_ids}")


@bot.on.chat_message(text=["/chat", "/chat <chat_id>"])
async def chat_handler(message: Message, chat_id: str = None):
    """Show or activate chat."""
    target_chat = int(chat_id) if chat_id and chat_id.isdigit() else get_chat_id(message)
    if target_chat is None:
        await message.answer("Не удалось определить чат")
        return
    chat = await ChatsRepository().get(target_chat)
    await message.answer(f"Чат {target_chat}: активен={chat.get('is_active') if chat else None}")


@bot.on.chat_message(text="/async")
async def async_handler(message: Message):
    """Async actions placeholder."""
    await message.answer("ASYNC режим: обработка действий")
