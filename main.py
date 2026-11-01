"""Main entry point for the VK bot."""

import asyncio
import logging

from bot.dispatcher import bot
from bot.health_server import start_health_server
from config import config

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    """Run VK Long Poll alongside the HTTP health endpoint."""
    server = await start_health_server(config.port)
    addresses = ", ".join(str(sock.getsockname()) for sock in server.sockets or [])
    logging.info("Health server listening on %s", addresses)
    logging.info("VK bot starting")
    try:
        async with server:
            await bot.run_polling()
    finally:
        server.close()
        await server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
