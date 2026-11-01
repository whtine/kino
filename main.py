"""Main entry point for the VK bot."""

import asyncio
import logging

from bot.dispatcher import bot

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    """Run the VK bot via Long Poll."""
    logging.info("VK bot starting")
    await bot.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
