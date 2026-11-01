"""Keyboards for the VK bot."""

import json

from vkbottle import Callback, Keyboard, KeyboardButtonColor, Text

def get_staff_keyboard() -> dict:
    """One-time keyboard with staff refresh button."""
    return Keyboard(one_time=True).add(Text("Обновить", {"cmd": "staff_refresh"})).get_json()


def get_activation_keyboard() -> str:
    keyboard = Keyboard(one_time=False, inline=True)
    keyboard.add(Callback("Активировать", {"cmd": "activate_chat"}))
    return keyboard.get_json()


def get_help_keyboard(user_role: int, selected_level: int = 0) -> str:
    """Build inline callback buttons for the help level selector."""
    keyboard = Keyboard(one_time=False, inline=True)
    for level in range(max(0, min(6, user_role)) + 1):
        keyboard.add(
            Callback(
                f"{level} уровень",
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
        if level % 2 == 1:
            keyboard.row()
    return keyboard.get_json()
