"""Keyboards for the VK bot."""

import json

from vkbottle import Callback, Keyboard, KeyboardButtonColor, Text

from bot.utils.permissions import MAX_HELP_ROLE

def get_staff_keyboard() -> dict:
    """One-time keyboard with staff refresh button."""
    return Keyboard(one_time=True).add(Text("Обновить", {"cmd": "staff_refresh"})).get_json()


def get_activation_keyboard() -> str:
    keyboard = Keyboard(one_time=False, inline=True)
    keyboard.add(Callback("Активировать", {"cmd": "activate_chat"}))
    return keyboard.get_json()


def get_punishment_keyboard(action: str, target_id: int, punishment_id: int | None = None) -> str:
    payload = {"cmd": "revoke_punishment", "action": action, "target_id": target_id}
    if punishment_id is not None:
        payload["punishment_id"] = punishment_id
    labels = {
        "unwarn": "Снять предупреждение",
        "unmute": "Снять мут",
        "unban": "Снять блокировку",
        "restore_kick": "Вернуть в беседу",
    }
    keyboard = Keyboard(one_time=False, inline=True)
    keyboard.add(Callback(labels[action], payload))
    return keyboard.get_json()


def get_help_keyboard(user_role: int, selected_level: int = 0) -> str:
    """Build inline callback buttons for the help level selector."""
    keyboard = Keyboard(one_time=False, inline=True)
    for level in range(max(0, min(MAX_HELP_ROLE, user_role)) + 1):
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


def get_nick_list_keyboard(page: int, page_count: int) -> str:
    """Build inline paging controls for /nlist."""
    keyboard = Keyboard(one_time=False, inline=True)
    if page > 0:
        keyboard.add(
            Callback("← Назад", json.dumps({"cmd": "nlist_page", "page": page - 1}))
        )
    if page + 1 < page_count:
        keyboard.add(
            Callback("Далее →", json.dumps({"cmd": "nlist_page", "page": page + 1}))
        )
    return keyboard.get_json()
