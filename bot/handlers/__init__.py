"""VK bot message handlers."""

from bot.handlers import activation, commands  # noqa: F401
from bot.handlers.activation import bp as activation_bp
from bot.handlers.commands import bp as commands_bp

__all__ = [
    "activation",
    "commands",
    "activation_bp",
    "commands_bp",
]
