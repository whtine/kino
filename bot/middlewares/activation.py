import logging
import re

from vkbottle import BaseMiddleware
from vkbottle.bot import Message

from bot.utils.vk_api import vk_api
from config import config
from db.repositories.chats import ChatsRepository
from db.repositories.members import MembersRepository

logger = logging.getLogger(__name__)
chats_repo = ChatsRepository()
members_repo = MembersRepository()
ALLOWED_WITHOUT_ACTIVATION = {"activate", "start", "help"}


class ActivationMiddleware(BaseMiddleware[Message]):
    """Persist new chats and guard messages in inactive, muted, or locked chats."""

    warned_chats: set[int] = set()

    async def pre(self):
        message = self.event
        chat_id = message.peer_id
        if chat_id < 2_000_000_000:
            return

        action = getattr(message, "action", None)
        action_type = getattr(action, "type", None)
        if action_type in {"chat_invite_user", "chat_invite_user_by_link"}:
            details = await vk_api.get_chat_info(chat_id) if vk_api else None
            chat = await chats_repo.get_or_create(
                chat_id, details.get("title") if details else None
            )
            member_id = getattr(action, "member_id", 0)
            if member_id and member_id > 0:
                from db.supabase import get_supabase
                supabase = get_supabase()
                banned = supabase.table("chat_bans").select("user_id").eq(
                    "chat_id", chat_id
                ).eq("user_id", member_id).limit(1).execute().data
                if not banned and chat.get("group_id"):
                    banned = supabase.table("global_bans").select("user_id").eq(
                        "group_id", chat["group_id"]
                    ).eq("user_id", member_id).limit(1).execute().data
                if banned and vk_api and not await vk_api.kick_user(chat_id, member_id):
                    logger.error("Failed to remove banned user %s from chat %s", member_id, chat_id)
            return

        text = (message.text or "").strip()
        command = text.split()[0][1:].lower().split("@", 1)[0] if text.startswith("/") else None
        activation = text == config.activation_command or text == "*"
        if activation or command in ALLOWED_WITHOUT_ACTIVATION:
            return

        chat = await chats_repo.get(chat_id)
        if not chat or not chat.get("is_active"):
            warned_chats = self.warned_chats
            if chat_id not in warned_chats:
                warned_chats.add(chat_id)
                await message.answer(
                    f"🤖 Бот не активирован. Администратор беседы должен отправить "
                    f"«{config.activation_command}» (или «*»)."
                )
            self.stop()

        if message.from_id > 0 and await members_repo.is_muted(chat_id, message.from_id):
            await self._delete_message(message, chat_id)
            self.stop()

        settings = chat.get("settings") or {}
        if settings.get("timeout") and not text.startswith("/"):
            await self._delete_message(message, chat_id)
            self.stop()

        restricted = {int(value) for value in (settings.get("antitag_users") or [])}
        mentioned = {int(value) for value in re.findall(r"(?:\[id|@id)(\d+)", text)}
        if settings.get("antitag") and mentioned.intersection(restricted):
            await self._delete_message(message, chat_id)
            self.stop()

    async def _delete_message(self, message: Message, chat_id: int) -> None:
        message_id = getattr(message, "conversation_message_id", None)
        if message_id and vk_api:
            if not await vk_api.delete_message(chat_id, [message_id]):
                logger.error("Failed to enforce chat restriction in chat %s", chat_id)
