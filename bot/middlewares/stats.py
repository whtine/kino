import logging

from vkbottle import BaseMiddleware
from vkbottle.bot import Message

from db.repositories.chats import ChatsRepository
from db.repositories.stats import StatsRepository

logger = logging.getLogger(__name__)
stats_repo = StatsRepository()
chats_repo = ChatsRepository()


class StatsMiddleware(BaseMiddleware[Message]):
    """Track non-command messages in active group chats."""

    async def pre(self):
        message = self.event
        if message.peer_id < 2_000_000_000 or message.from_id <= 0:
            return
        if (message.text or "").strip().startswith("/"):
            return
        chat = await chats_repo.get(message.peer_id)
        if not chat or not chat.get("is_active"):
            return
        try:
            await stats_repo.increment(message.peer_id, message.from_id)
        except Exception:
            logger.exception(
                "Could not increment message statistics for user %s in chat %s",
                message.from_id,
                message.peer_id,
            )
