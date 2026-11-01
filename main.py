"""Main entry point for the VK bot."""

import asyncio
import logging

from aiohttp import web

from bot.dispatcher import bot
from config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def healthz(request: web.Request) -> web.Response:
    """Health check endpoint for Render."""
    return web.Response(text="OK")


async def enable_message_event() -> None:
    """Enable Long Poll updates required by inline callback buttons."""
    try:
        enabled = await bot.api.groups.set_long_poll_settings(
            group_id=config.group_id,
            message_event=True,
        )
    except Exception:
        logger.exception(
            "Could not enable VK message_event updates; enable them in community "
            "Long Poll settings to make inline buttons work"
        )
        return
    if not enabled:
        logger.error(
            "VK did not enable message_event updates; enable them in community "
            "Long Poll settings to make inline buttons work"
        )
        return
    logger.info("VK message_event updates enabled")


async def main() -> None:
    """Run VK bot via Long Poll with a lightweight health server."""
    logging.info("VK bot starting")
    await enable_message_event()
    app = web.Application()
    app.router.add_get("/healthz", healthz)
    app.router.add_get("/health", healthz)
    app.router.add_get("/", healthz)
    app.router.add_get("/ping", healthz)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.port)
    await site.start()
    logging.info("Health server started on port %s", config.port)
    await bot.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
