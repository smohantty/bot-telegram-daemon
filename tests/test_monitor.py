"""Tests for the Monitor orchestrator."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.bot_state import BotState
from src.config import (
    BotEndpoint,
    ConnectionConfig,
    DaemonConfig,
    ReportingConfig,
    TelegramConfig,
)
from src.models import PerpGridSummary, SpotGridSummary, SystemInfo
from src.monitor import Monitor


def _make_config(
    bots: list[dict] | None = None,
    periodic_minutes: int = 0,
    error_cooldown: int = 60,
) -> DaemonConfig:
    """Create a test DaemonConfig."""
    if bots is None:
        bots = [{"label": "TestBot", "url": "ws://localhost:9000"}]
    return DaemonConfig(
        telegram=TelegramConfig(bot_token="tok", chat_id="123"),
        bots=[BotEndpoint(**b) for b in bots],
        reporting=ReportingConfig(
            periodic_interval_minutes=periodic_minutes,
            error_cooldown_seconds=error_cooldown,
            startup_notification=False,
        ),
        connection=ConnectionConfig(),
    )


def _make_telegram_mock() -> MagicMock:
    telegram = MagicMock()
    telegram.send_error_alert = AsyncMock()
    telegram.send_initial_summary = AsyncMock()
    return telegram


class TestEventHandling:
    """Test event routing updates BotState correctly."""

    @pytest.fixture
    def monitor(self) -> Monitor:
        config = _make_config()
        telegram = _make_telegram_mock()
        m = Monitor(config, telegram)
        m.bots["TestBot"] = BotState(label="TestBot", url="ws://localhost:9000")
        return m

    @pytest.mark.asyncio
    async def test_info_event(self, monitor: Monitor) -> None:
        await monitor._handle_event(
            "TestBot", "info", {"network": "mainnet", "exchange": "hyperliquid"}
        )
        assert monitor.bots["TestBot"].info is not None
        assert monitor.bots["TestBot"].info.network == "mainnet"

    @pytest.mark.asyncio
    async def test_config_event(self, monitor: Monitor) -> None:
        await monitor._handle_event(
            "TestBot",
            "config",
            {"type": "spot_grid", "symbol": "ETH/USDC", "total_investment": 1000},
        )
        assert monitor.bots["TestBot"].config is not None
        assert monitor.bots["TestBot"].config.type == "spot_grid"
        assert monitor.bots["TestBot"].config.total_investment == 1000.0

    @pytest.mark.asyncio
    async def test_spot_grid_summary(self, monitor: Monitor) -> None:
        data = {
            "symbol": "ETH/USDC",
            "state": "Running",
            "uptime": "2h",
            "position_size": 1.0,
            "matched_profit": 10.0,
            "total_profit": 12.0,
            "total_fees": 1.0,
            "grid_count": 5,
            "range_low": 3000.0,
            "range_high": 4000.0,
            "grid_spacing_pct": [1.0, 1.0],
            "roundtrips": 3,
            "base_balance": 1.0,
            "quote_balance": 200.0,
        }
        await monitor._handle_event("TestBot", "spot_grid_summary", data)
        assert isinstance(monitor.bots["TestBot"].summary, SpotGridSummary)
        assert monitor.bots["TestBot"].last_summary_at is not None

    @pytest.mark.asyncio
    async def test_perp_grid_summary(self, monitor: Monitor) -> None:
        data = {
            "symbol": "HYPE",
            "state": "Running",
            "uptime": "1h",
            "position_size": 50.0,
            "position_side": "Long",
            "matched_profit": 20.0,
            "total_profit": 25.0,
            "total_fees": 2.0,
            "leverage": 5,
            "grid_bias": "long",
            "grid_count": 10,
            "range_low": 20.0,
            "range_high": 30.0,
            "grid_spacing_pct": [0.5, 0.5],
            "roundtrips": 5,
            "margin_balance": 500.0,
        }
        await monitor._handle_event("TestBot", "perp_grid_summary", data)
        assert isinstance(monitor.bots["TestBot"].summary, PerpGridSummary)

    @pytest.mark.asyncio
    async def test_error_event_sends_alert(self, monitor: Monitor) -> None:
        await monitor._handle_event("TestBot", "error", "Connection lost")
        assert monitor.bots["TestBot"].last_error == "Connection lost"
        monitor._telegram.send_error_alert.assert_called_once_with(
            "TestBot", "Connection lost"
        )

    @pytest.mark.asyncio
    async def test_ignored_events(self, monitor: Monitor) -> None:
        """market_update, order_update, grid_state are silently ignored."""
        await monitor._handle_event("TestBot", "market_update", {"price": 100.0})
        await monitor._handle_event("TestBot", "order_update", {"oid": 1})
        await monitor._handle_event("TestBot", "grid_state", {"zones": []})
        assert monitor.bots["TestBot"].summary is None

    @pytest.mark.asyncio
    async def test_unknown_label_ignored(self, monitor: Monitor) -> None:
        await monitor._handle_event(
            "UnknownBot", "info", {"network": "x", "exchange": "y"}
        )

    @pytest.mark.asyncio
    async def test_connect_disconnect(self, monitor: Monitor) -> None:
        await monitor._handle_connect("TestBot")
        assert monitor.bots["TestBot"].connected is True
        assert monitor.bots["TestBot"].last_connected_at is not None

        await monitor._handle_disconnect("TestBot")
        assert monitor.bots["TestBot"].connected is False


class TestInitialSummary:
    """Test that full summary is sent once on first data."""

    @pytest.mark.asyncio
    async def test_initial_summary_sent_on_first_data(self) -> None:
        config = _make_config()
        telegram = _make_telegram_mock()
        monitor = Monitor(config, telegram)
        state = BotState(label="TestBot", url="ws://x")
        monitor.bots["TestBot"] = state

        # Set info first
        await monitor._handle_event(
            "TestBot", "info", {"network": "mainnet", "exchange": "hyperliquid"}
        )
        # No summary yet — initial not sent
        telegram.send_initial_summary.assert_not_called()

        # Now send summary
        await monitor._handle_event("TestBot", "spot_grid_summary", {
            "symbol": "ETH", "state": "Running", "uptime": "1h",
            "position_size": 1.0, "matched_profit": 10.0,
            "total_profit": 12.0, "total_fees": 1.0, "grid_count": 5,
            "range_low": 3000.0, "range_high": 4000.0,
            "grid_spacing_pct": [1.0, 1.0], "roundtrips": 3,
            "base_balance": 1.0, "quote_balance": 200.0,
        })
        telegram.send_initial_summary.assert_called_once()
        assert state.initial_summary_sent is True

    @pytest.mark.asyncio
    async def test_initial_summary_not_repeated(self) -> None:
        config = _make_config()
        telegram = _make_telegram_mock()
        monitor = Monitor(config, telegram)
        state = BotState(label="TestBot", url="ws://x")
        state.info = SystemInfo(network="mainnet", exchange="test")
        monitor.bots["TestBot"] = state

        data = {
            "symbol": "ETH", "state": "Running", "uptime": "1h",
            "position_size": 1.0, "matched_profit": 10.0,
            "total_profit": 12.0, "total_fees": 1.0, "grid_count": 5,
            "range_low": 3000.0, "range_high": 4000.0,
            "grid_spacing_pct": [1.0, 1.0], "roundtrips": 3,
            "base_balance": 1.0, "quote_balance": 200.0,
        }
        await monitor._handle_event("TestBot", "spot_grid_summary", data)
        await monitor._handle_event("TestBot", "spot_grid_summary", data)
        await monitor._handle_event("TestBot", "spot_grid_summary", data)
        # Only sent once
        assert telegram.send_initial_summary.call_count == 1

    @pytest.mark.asyncio
    async def test_initial_summary_snapshots_all_values(self) -> None:
        config = _make_config()
        telegram = _make_telegram_mock()
        monitor = Monitor(config, telegram)
        state = BotState(label="TestBot", url="ws://x")
        state.info = SystemInfo(network="mainnet", exchange="test")
        monitor.bots["TestBot"] = state

        await monitor._handle_event("TestBot", "spot_grid_summary", {
            "symbol": "ETH", "state": "Running", "uptime": "1h",
            "position_size": 1.0, "matched_profit": 10.0,
            "total_profit": 12.0, "total_fees": 1.5, "grid_count": 5,
            "range_low": 3000.0, "range_high": 4000.0,
            "grid_spacing_pct": [1.0, 1.0], "roundtrips": 7,
            "base_balance": 1.0, "quote_balance": 200.0,
        })
        assert state.prev_roundtrips == 7
        assert state.prev_matched_profit == 10.0
        assert state.prev_total_fees == 1.5


class TestErrorCooldown:
    """Test error alert cooldown logic."""

    @pytest.mark.asyncio
    async def test_first_error_sends(self) -> None:
        config = _make_config(error_cooldown=60)
        telegram = _make_telegram_mock()
        monitor = Monitor(config, telegram)
        monitor.bots["TestBot"] = BotState(label="TestBot", url="ws://x")

        await monitor._maybe_send_error_alert("TestBot", "err")
        telegram.send_error_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_second_error_suppressed_in_cooldown(self) -> None:
        config = _make_config(error_cooldown=60)
        telegram = _make_telegram_mock()
        monitor = Monitor(config, telegram)
        monitor.bots["TestBot"] = BotState(label="TestBot", url="ws://x")

        await monitor._maybe_send_error_alert("TestBot", "err1")
        await monitor._maybe_send_error_alert("TestBot", "err2")
        assert telegram.send_error_alert.call_count == 1

    @pytest.mark.asyncio
    async def test_error_after_cooldown_sends(self) -> None:
        config = _make_config(error_cooldown=60)
        telegram = _make_telegram_mock()
        monitor = Monitor(config, telegram)
        monitor.bots["TestBot"] = BotState(label="TestBot", url="ws://x")

        monitor._error_cooldowns["TestBot"] = datetime.now() - timedelta(seconds=120)
        await monitor._maybe_send_error_alert("TestBot", "err")
        telegram.send_error_alert.assert_called_once()
