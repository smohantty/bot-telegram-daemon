"""WebSocket client with auto-reconnect for a single bot endpoint.

Connects to a bot's WebSocket server, receives JSON events, and dispatches
them to a callback. Handles reconnection with exponential backoff.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable

import websockets
from websockets.exceptions import ConnectionClosed

from .config import ConnectionConfig

logger = logging.getLogger(__name__)


class BotWebSocketClient:
    """WebSocket client for a single bot endpoint."""

    def __init__(
        self,
        label: str,
        url: str,
        on_event: Callable[[str, str, Any], Awaitable[None]],
        on_connect: Callable[[str], Awaitable[None]],
        on_disconnect: Callable[[str], Awaitable[None]],
        connection_config: ConnectionConfig,
    ):
        self.label = label
        self.url = url
        self._on_event = on_event
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._config = connection_config
        self._delay = connection_config.reconnect_delay_seconds
        self._stopped = False

    async def run(self) -> None:
        """Main loop: connect, receive messages, reconnect on failure."""
        while not self._stopped:
            try:
                logger.info(
                    "Connecting to %s at %s...", self.label, self.url
                )
                async with websockets.connect(
                    self.url,
                    ping_interval=self._config.ping_interval_seconds,
                    ping_timeout=20,
                ) as ws:
                    # Reset backoff on successful connection
                    self._delay = self._config.reconnect_delay_seconds
                    await self._on_connect(self.label)
                    logger.info("Connected to %s", self.label)

                    async for raw_message in ws:
                        if self._stopped:
                            break
                        try:
                            msg = json.loads(raw_message)
                            event_type = msg.get("event_type")
                            data = msg.get("data")
                            if event_type and data is not None:
                                await self._on_event(self.label, event_type, data)
                        except json.JSONDecodeError as e:
                            logger.warning(
                                "Invalid JSON from %s: %s", self.label, e
                            )

            except (ConnectionClosed, ConnectionError, OSError) as e:
                logger.warning(
                    "WS disconnected from %s: %s", self.label, e
                )
            except Exception as e:
                logger.error(
                    "Unexpected error in WS client %s: %s", self.label, e
                )

            # Notify disconnect and wait before reconnecting
            if not self._stopped:
                await self._on_disconnect(self.label)
                logger.info(
                    "Reconnecting to %s in %ds...", self.label, self._delay
                )
                await asyncio.sleep(self._delay)
                # Exponential backoff capped at max
                self._delay = min(
                    self._delay * 2,
                    self._config.max_reconnect_delay_seconds,
                )

    async def stop(self) -> None:
        """Signal the client to stop."""
        self._stopped = True
