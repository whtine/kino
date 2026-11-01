"""VK bot dispatcher: bot instance, middlewares and handler registration."""

from vkbottle import Bot

from config import config
from bot.utils.vk_api import init_vk_api
from bot.middlewares import (
    ActivationMiddleware,
    OwnerCheckMiddleware,
    RoleCheckMiddleware,
    StatsMiddleware,
)

bot = Bot(token=config.vk_token)
bot.polling.group_id = config.group_id
init_vk_api(bot.api)

from bot.handlers import activation_bp, commands_bp  # noqa: E402,F401  pylint: disable=wrong-import-position

bot.router.views["message"].register_middleware(ActivationMiddleware)
bot.router.views["message"].register_middleware(StatsMiddleware)
bot.router.views["message"].register_middleware(RoleCheckMiddleware)
bot.router.views["message"].register_middleware(OwnerCheckMiddleware)

bot.labeler.load(activation_bp.labeler)
bot.labeler.load(commands_bp.labeler)
