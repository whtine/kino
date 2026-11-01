"""Helpers for extracting context from VK message events."""

from typing import Any, Optional

# VK chat peer ids start from 2000000000 (2000000000 + user/chat index)
VK_CHAT_ID_OFFSET = 2000000000


def get_chat_id(message: Any) -> Optional[int]:
    """Return VK chat peer_id (2000000000+) or None for private/group messages."""
    peer_id = getattr(message, "peer_id", None)
    if peer_id is None:
        return None
    peer_id = int(peer_id)
    if peer_id <= VK_CHAT_ID_OFFSET:
        # private message (peer_id == from_id) or group message (peer_id < 0)
        return None
    return peer_id


def get_user_id(message: Any) -> Optional[int]:
    """Return VK user id from the message author, or None."""
    user_id = getattr(message, "from_id", None)
    if not user_id:
        return None
    user_id = int(user_id)
    if user_id < 0:
        # negative id means the message is from the group itself
        return None
    return user_id


def get_command(message: Any) -> Optional[str]:
    """Extract normalized command name from message text (e.g. '/kick user' -> 'kick')."""
    text = getattr(message, "text", None) or ""
    text = text.strip()
    if not text or not text.startswith("/"):
        return None
    parts = text.split()
    command = parts[0].split("@", 1)[0].lstrip("/").lower()
    return command or None
