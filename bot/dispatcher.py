from vkbottle import Bot

from config import config
from bot.utils.vk_api import init_vk_api

bot = Bot(token=config.vk_token)
bot.polling.group_id = config.group_id
init_vk_api(bot.api)

from bot.handlers.activation import bp as activation_blueprint
from bot.handlers.commands import bp as commands_blueprint
from bot.middlewares.activation import ActivationMiddleware
from bot.middlewares.role_check import OwnerCheckMiddleware, RoleCheckMiddleware
from bot.middlewares.stats import StatsMiddleware

bot.labeler.message_view.register_middleware(ActivationMiddleware)
bot.labeler.message_view.register_middleware(RoleCheckMiddleware)
bot.labeler.message_view.register_middleware(OwnerCheckMiddleware)
bot.labeler.message_view.register_middleware(StatsMiddleware)

bot.labeler.load(activation_blueprint.labeler)
bot.labeler.load(commands_blueprint.labeler)
