"""Telegram bot for command handling and message sending.

Handles /status and /help commands from Telegram users, and provides
a sender interface for the Monitor to push periodic summaries and error alerts.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from .config import TelegramConfig
from .formatter import (
    format_bot_status,
    format_error_alert,
    format_startup_message,
)

if TYPE_CHECKING:
    from .bot_state import BotState

logger = logging.getLogger(__name__)

# Telegram message length limit
MAX_MESSAGE_LENGTH = 4096


class TelegramBot:
    """Telegram bot with command handlers and message sending capabilities."""

    def __init__(self, config: TelegramConfig) -> None:
        self._chat_id = int(config.chat_id)
        self._monitor = None  # Set via set_monitor() to break circular dep
        self._app = Application.builder().token(config.bot_token).build()
        self._app.add_handler(CommandHandler("status", self._cmd_status))
        self._app.add_handler(CommandHandler("help", self._cmd_help))

    def set_monitor(self, monitor: object) -> None:
        """Wire the monitor reference (called after both are constructed)."""
        self._monitor = monitor

    async def start(self) -> None:
        """Start the Telegram bot polling loop."""
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling()
        logger.info("Telegram bot polling started")

    async def stop(self) -> None:
        """Stop the Telegram bot."""
        try:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
            logger.info("Telegram bot stopped")
        except Exception as e:
            logger.error("Error stopping Telegram bot: %s", e)

    # --- Command Handlers ---

    async def _cmd_status(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /status command. Optionally takes a bot label argument."""
        if not self._monitor or not update.message:
            return

        args = context.args or []
        states: dict[str, BotState] = self._monitor.get_all_states()

        if args:
            # /status <label> — single bot
            label = args[0]
            if label in states:
                msg = format_bot_status(label, states[label])
            else:
                available = ", ".join(states.keys())
                msg = f"Unknown bot: <code>{label}</code>\nAvailable: {available}"
        else:
            # /status — all bots consolidated
            if not states:
                msg = "No bots configured."
            else:
                sections = [
                    format_bot_status(lbl, st) for lbl, st in states.items()
                ]
                msg = "\n\n" + "\u2500" * 20 + "\n\n"
                msg = msg.join(sections)

        await self._send_safe(update.message.chat_id, msg)

    async def _cmd_help(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /help command."""
        if not update.message:
            return

        msg = (
            "<b>Trading Bot Monitor</b>\n\n"
            "/status \u2014 Status of all bots\n"
            "/status &lt;label&gt; \u2014 Status of a specific bot\n"
            "/help \u2014 This message"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

    # --- Sender Interface (called by Monitor) ---

    async def send_startup_message(self, labels: list[str]) -> None:
        """Send a startup notification to the configured chat."""
        msg = format_startup_message(labels)
        await self._send_safe(self._chat_id, msg)

    async def send_error_alert(self, label: str, error_msg: str) -> None:
        """Send an immediate error alert."""
        msg = format_error_alert(label, error_msg)
        await self._send_safe(self._chat_id, msg)

    async def send_periodic_summary(
        self, bots: dict[str, BotState]
    ) -> None:
        """Send a consolidated periodic summary of all bots."""
        if not bots:
            return

        sections = [format_bot_status(lbl, st) for lbl, st in bots.items()]
        separator = "\n\n" + "\u2500" * 20 + "\n\n"
        msg = separator.join(sections)
        await self._send_safe(self._chat_id, msg)

    # --- Internal Helpers ---

    async def _send_safe(self, chat_id: int, text: str) -> None:
        """Send a message, splitting if it exceeds Telegram's limit."""
        if len(text) <= MAX_MESSAGE_LENGTH:
            try:
                await self._app.bot.send_message(
                    chat_id, text, parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error("Failed to send Telegram message: %s", e)
        else:
            # Split into chunks at section boundaries
            chunks = self._split_message(text)
            for chunk in chunks:
                try:
                    await self._app.bot.send_message(
                        chat_id, chunk, parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    logger.error("Failed to send Telegram chunk: %s", e)

    @staticmethod
    def _split_message(text: str) -> list[str]:
        """Split a long message into chunks that fit Telegram's limit."""
        chunks: list[str] = []
        current = ""

        for line in text.split("\n"):
            if len(current) + len(line) + 1 > MAX_MESSAGE_LENGTH:
                if current:
                    chunks.append(current.rstrip())
                current = line + "\n"
            else:
                current += line + "\n"

        if current.strip():
            chunks.append(current.rstrip())

        return chunks if chunks else [text[:MAX_MESSAGE_LENGTH]]
