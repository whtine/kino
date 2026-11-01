"""Main entry point for the VK bot."""

import asyncio
import logging

from aiohttp import web

from bot.dispatcher import bot
from config import config

logging.basicConfig(level=logging.INFO)


async def healthz(request: web.Request) -> web.Response:
    """Health check endpoint for Render."""
    return web.Response(text="OK")


async def main() -> None:
    """Run VK bot via Long Poll with a lightweight health server."""
    logging.info("VK bot starting")
    app = web.Application()
    app.router.add_get("/healthz", healthz)
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
