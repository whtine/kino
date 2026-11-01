"""Statistics middleware: tracks regular message statistics in active chats."""

import logging

from vkbottle import BaseMiddleware
from vkbottle.bot import Message

from bot.utils.context import get_chat_id
from db.repositories.chats import ChatsRepository
from db.repositories.stats import StatsRepository

logger = logging.getLogger(__name__)
chats_repo = ChatsRepository()
stats_repo = StatsRepository()


class StatsMiddleware(BaseMiddleware[Message]):
    """Track regular (non-command) messages in active group chats."""

    async def pre(self) -> None:
        message = self.event
        chat_id = get_chat_id(message)
        user_id = getattr(message, "from_id", None)

        if chat_id is None or not user_id or user_id <= 0:
            return
        if (getattr(message, "text", None) or "").strip().startswith("/"):
            return

        chat = await chats_repo.get(chat_id)
        if not chat or not chat.get("is_active"):
            return

        try:
            await stats_repo.increment(chat_id, user_id)
        except Exception:
            logger.exception(
                "Could not increment message statistics for user %s in chat %s",
                user_id,
                chat_id,
            )


__all__ = ("StatsMiddleware",)
