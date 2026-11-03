"""Statistics middleware: tracks regular message statistics in active chats."""

import asyncio
import logging

from vkbottle import BaseMiddleware
from vkbottle.bot import Message

from bot.utils.context import get_chat_id
from bot.utils.vk_api import remember_chat_message
from db.repositories.chats import ChatsRepository
from db.repositories.stats import StatsRepository

logger = logging.getLogger(__name__)
chats_repo = ChatsRepository()
stats_repo = StatsRepository()
_background_tasks: set[asyncio.Task[None]] = set()


async def _increment_stats(chat_id: int, user_id: int) -> None:
    try:
        await stats_repo.increment(chat_id, user_id)
    except Exception:
        logger.exception(
            "Could not increment message statistics for user %s in chat %s",
            user_id,
            chat_id,
        )


class StatsMiddleware(BaseMiddleware[Message]):
    """Track regular (non-command) messages in active group chats."""

    async def pre(self) -> None:
        message = self.event
        chat_id = get_chat_id(message)
        user_id = getattr(message, "from_id", None)

        if chat_id is None or not user_id:
            return

        if getattr(message, "action", None):
            return
        cmid = getattr(message, "conversation_message_id", None)
        if cmid is not None:
            remember_chat_message(chat_id, cmid, user_id)
        if user_id < 0:
            return
        if (getattr(message, "text", None) or "").strip().startswith("/"):
            return

        chat = await chats_repo.get(chat_id)
        if not chat or not chat.get("is_active"):
            return

        task = asyncio.create_task(_increment_stats(chat_id, user_id))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)


__all__ = ("StatsMiddleware",)
