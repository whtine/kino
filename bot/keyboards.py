"""Keyboards for the VK bot."""

import json

from vkbottle import Callback, Keyboard, KeyboardButtonColor, Text

from bot.utils.permissions import ROLE_NAMES


def get_staff_keyboard() -> dict:
    """One-time keyboard with staff refresh button."""
    return Keyboard(one_time=True).add(Text("Обновить", {"cmd": "staff_refresh"})).get_json()


def get_help_keyboard(user_role: int, selected_level: int = 0) -> str:
    """Build inline callback buttons for the help level selector."""
    keyboard = Keyboard(one_time=False, inline=True)
    for level in range(max(0, min(6, user_role)) + 1):
        keyboard.add(
            Callback(
                f"{level} · {ROLE_NAMES[level]}",
                json.dumps(
                    {"cmd": "help_level", "level": level},
                    ensure_ascii=False,
                ),
            ),
            color=(
                KeyboardButtonColor.POSITIVE
                if level == selected_level
                else KeyboardButtonColor.SECONDARY
            ),
        )
        if level % 4 == 3:
            keyboard.row()
    return keyboard.get_json()
