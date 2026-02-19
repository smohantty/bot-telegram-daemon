"""Bot Telegram Daemon — Entry Point.

Standalone daemon that monitors trading bots via WebSocket and sends
status updates to Telegram.

Usage:
    python main.py configs/production.yaml
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal

from src.config import load_config
from src.logging_utils import configure_logging
from src.monitor import Monitor
from src.telegram_bot import TelegramBot

logger = logging.getLogger(__name__)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Trading Bot Telegram Monitor Daemon"
    )
    parser.add_argument(
        "config_file",
        help="Path to the YAML configuration file",
    )
    args = parser.parse_args()

    # Load config
    config = load_config(args.config_file)
    configure_logging("INFO")

    logger.info(
        "Starting bot-telegram-daemon with %d bot(s)...", len(config.bots)
    )

    # Create components
    telegram_bot = TelegramBot(config.telegram)
    monitor = Monitor(config, telegram_bot)
    telegram_bot.set_monitor(monitor)

    # Signal handling for graceful shutdown
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("Shutdown signal received...")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    # Start Telegram bot
    await telegram_bot.start()

    # Start monitor (runs WebSocket clients + periodic reporter)
    monitor_task = asyncio.create_task(monitor.run())

    # Wait for shutdown signal
    await stop_event.wait()

    # Graceful shutdown
    logger.info("Shutting down...")
    await monitor.stop()

    # Give monitor tasks a moment to clean up
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass

    await telegram_bot.stop()
    logger.info("Daemon stopped.")


if __name__ == "__main__":
    asyncio.run(main())
