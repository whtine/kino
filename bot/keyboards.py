"""Keyboards for the VK bot."""

from vkbottle import Keyboard, Text


def get_staff_keyboard() -> dict:
    """One-time keyboard with staff refresh button."""
    return Keyboard(one_time=True).add(Text("Обновить", {"cmd": "staff_refresh"})).get_json()


def get_help_keyboard() -> dict:
    """One-time keyboard with help button."""
    return Keyboard(one_time=True).add(Text("Помощь", {"cmd": "help_refresh"})).get_json()
