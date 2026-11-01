"""Keyboards for the VK bot."""

import json

from vkbottle import Keyboard, Text

from bot.utils.permissions import ROLE_NAMES


def get_staff_keyboard() -> dict:
    """One-time keyboard with staff refresh button."""
    return Keyboard(one_time=True).add(Text("Обновить", {"cmd": "staff_refresh"})).get_json()


def get_help_keyboard(user_role: int) -> str:
    """Inline role selector for the commands available to the current user."""
    keyboard = Keyboard(one_time=False, inline=True)
    for level in range(max(0, min(6, user_role)) + 1):
        keyboard.add(
            Text(
                f"{level} · {ROLE_NAMES[level]}",
                json.dumps(
                    {"cmd": "help_level", "level": level},
                    ensure_ascii=False,
                ),
            )
        )
        if level % 4 == 3:
            keyboard.row()
    return keyboard.get_json()
