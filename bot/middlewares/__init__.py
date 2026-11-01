"""Middlewares for the VK bot."""

from bot.middlewares.activation import ActivationMiddleware
from bot.middlewares.role_check import RoleCheckMiddleware
from bot.middlewares.stats import StatsMiddleware

__all__ = [
    "ActivationMiddleware",
    "RoleCheckMiddleware",
    "StatsMiddleware",
]
