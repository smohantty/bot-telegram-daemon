"""Monitor orchestrator — manages WebSocket clients and aggregates bot state.

Creates one BotWebSocketClient per configured endpoint, routes events to
update BotState caches, and triggers Telegram alerts and periodic reports.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from .bot_state import BotState
from .config import DaemonConfig
from .models import (
    parse_perp_grid_summary,
    parse_spot_grid_summary,
    parse_strategy_config,
    parse_system_info,
)
from .telegram_bot import TelegramBot
from .ws_client import BotWebSocketClient

logger = logging.getLogger(__name__)


class Monitor:
    """Orchestrates WebSocket clients and manages bot state."""

    def __init__(self, config: DaemonConfig, telegram: TelegramBot) -> None:
        self._config = config
        self._telegram = telegram
        self.bots: dict[str, BotState] = {}
        self._clients: list[BotWebSocketClient] = []
        self._error_cooldowns: dict[str, datetime] = {}

    def get_all_states(self) -> dict[str, BotState]:
        """Return all bot states (used by Telegram /status command)."""
        return self.bots

    async def run(self) -> None:
        """Start all WS clients and the periodic reporter as concurrent tasks."""
        tasks: list[asyncio.Task] = []

        # Create a client for each configured bot
        for endpoint in self._config.bots:
            state = BotState(label=endpoint.label, url=endpoint.url)
            self.bots[endpoint.label] = state

            client = BotWebSocketClient(
                label=endpoint.label,
                url=endpoint.url,
                on_event=self._handle_event,
                on_connect=self._handle_connect,
                on_disconnect=self._handle_disconnect,
                connection_config=self._config.connection,
            )
            self._clients.append(client)
            tasks.append(asyncio.create_task(client.run()))

        # Start periodic reporting if enabled
        interval = self._config.reporting.periodic_interval_minutes
        if interval > 0:
            tasks.append(asyncio.create_task(self._periodic_report_loop()))

        # Send startup notification
        if self._config.reporting.startup_notification:
            labels = [b.label for b in self._config.bots]
            await self._telegram.send_startup_message(labels)

        # Wait for all tasks (they run forever until stopped)
        await asyncio.gather(*tasks, return_exceptions=True)

    async def stop(self) -> None:
        """Stop all WebSocket clients."""
        for client in self._clients:
            await client.stop()

    # --- Event Handlers ---

    async def _handle_event(
        self, label: str, event_type: str, data: Any
    ) -> None:
        """Route an incoming WebSocket event to update bot state."""
        state = self.bots.get(label)
        if not state:
            return

        try:
            if event_type == "info":
                state.info = parse_system_info(data)
            elif event_type == "config":
                state.config = parse_strategy_config(data)
            elif event_type == "spot_grid_summary":
                state.summary = parse_spot_grid_summary(data)
                state.last_summary_at = datetime.now()
            elif event_type == "perp_grid_summary":
                state.summary = parse_perp_grid_summary(data)
                state.last_summary_at = datetime.now()
            elif event_type == "error":
                error_msg = data if isinstance(data, str) else str(data)
                state.last_error = error_msg
                state.last_error_at = datetime.now()
                await self._maybe_send_error_alert(label, error_msg)
            # market_update, order_update, grid_state: ignored (not needed)
        except Exception as e:
            logger.error(
                "Failed to process %s event from %s: %s", event_type, label, e
            )

    async def _handle_connect(self, label: str) -> None:
        """Handle a successful WebSocket connection."""
        state = self.bots.get(label)
        if state:
            state.connected = True
            state.last_connected_at = datetime.now()
            logger.info("Bot %s connected", label)

    async def _handle_disconnect(self, label: str) -> None:
        """Handle a WebSocket disconnection."""
        state = self.bots.get(label)
        if state:
            state.connected = False
            logger.info("Bot %s disconnected", label)

    # --- Error Alerting with Cooldown ---

    async def _maybe_send_error_alert(
        self, label: str, error_msg: str
    ) -> None:
        """Send an error alert if not in cooldown."""
        now = datetime.now()
        last_sent = self._error_cooldowns.get(label)
        cooldown = timedelta(
            seconds=self._config.reporting.error_cooldown_seconds
        )

        if last_sent and (now - last_sent) < cooldown:
            logger.debug(
                "Error alert for %s suppressed (cooldown)", label
            )
            return

        self._error_cooldowns[label] = now
        await self._telegram.send_error_alert(label, error_msg)

    # --- Periodic Reporting ---

    async def _periodic_report_loop(self) -> None:
        """Periodically send consolidated summaries."""
        interval = self._config.reporting.periodic_interval_minutes * 60
        while True:
            await asyncio.sleep(interval)
            logger.info("Sending periodic summary...")
            await self._telegram.send_periodic_summary(self.bots)
