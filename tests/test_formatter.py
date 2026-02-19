"""Tests for Telegram HTML message formatting."""

from __future__ import annotations

from src.bot_state import BotState
from src.formatter import (
    _fp,
    _format_spacing,
    format_bot_status,
    format_error_alert,
    format_periodic_update,
    format_startup_message,
)
from src.models import PerpGridSummary, SpotGridSummary


class TestFormatPrice:
    """Test the price formatting helper."""

    def test_normal_price(self) -> None:
        assert _fp(1.50) == "1.50"
        assert _fp(99.99) == "99.99"

    def test_tiny_price(self) -> None:
        assert _fp(0.50) == "0.5000"
        assert _fp(0.005) == "0.005000"

    def test_thousands(self) -> None:
        assert _fp(1000.0) == "1,000"
        assert _fp(3500.50) == "3,500.50"

    def test_large_price(self) -> None:
        assert _fp(25000.0) == "25,000"
        assert _fp(100000.75) == "100,000.75"


class TestFormatSpacing:
    def test_geometric_equal(self) -> None:
        assert _format_spacing((1.05, 1.05)) == "1.05%"

    def test_arithmetic_range(self) -> None:
        result = _format_spacing((1.80, 3.20))
        assert "1.80%" in result
        assert "3.20%" in result

    def test_small_spacing(self) -> None:
        assert _format_spacing((0.500, 0.500)) == "0.500%"


class TestFormatBotStatus:
    """Test full status format (/status command)."""

    def test_disconnected(self, disconnected_state: BotState) -> None:
        result = format_bot_status("Test", disconnected_state)
        assert "disconnected" in result

    def test_no_summary(self) -> None:
        state = BotState(label="Test", url="ws://x", connected=True)
        result = format_bot_status("Test", state)
        assert "waiting for data" in result

    def test_spot_summary_content(self, connected_spot_state: BotState) -> None:
        result = format_bot_status("Test-Spot", connected_spot_state)
        assert "spot grid" in result
        assert "ETH/USDC" in result
        assert "pnl" in result
        assert "position" in result
        assert "grid" in result
        assert "52.10" in result  # total_profit
        assert "45.23" in result  # matched_profit
        assert "12" in result  # roundtrips
        assert "entry price" in result

    def test_perp_summary_content(self, connected_perp_state: BotState) -> None:
        result = format_bot_status("Test-Perp", connected_perp_state)
        assert "perp grid" in result
        assert "HYPE" in result
        assert "long" in result
        assert "5x" in result
        assert "realized" in result
        assert "unrealized" in result
        assert "margin" in result

    def test_positive_pnl(self, connected_spot_state: BotState) -> None:
        result = format_bot_status("Test", connected_spot_state)
        assert "+52.10" in result

    def test_negative_pnl(self, connected_spot_state: BotState) -> None:
        assert isinstance(connected_spot_state.summary, SpotGridSummary)
        connected_spot_state.summary.total_profit = -10.0
        result = format_bot_status("Test", connected_spot_state)
        assert "-10.00" in result

    def test_exchange_in_output(self, connected_perp_state: BotState) -> None:
        result = format_bot_status("Test", connected_perp_state)
        assert "hyperliquid" in result


class TestFormatPeriodicUpdate:
    """Test lightweight periodic update format."""

    def test_spot_update(self, connected_spot_state: BotState) -> None:
        connected_spot_state.prev_roundtrips = 10  # was 10, now 12
        result = format_periodic_update("Test-Spot", connected_spot_state)
        assert result is not None
        assert "Test-Spot" in result
        assert "ETH/USDC" in result
        assert "+2" in result  # 12 - 10 = 2 new trades
        assert "52.10" in result  # profit

    def test_perp_update(self, connected_perp_state: BotState) -> None:
        connected_perp_state.prev_roundtrips = 5  # was 5, now 8
        result = format_periodic_update("Test-Perp", connected_perp_state)
        assert result is not None
        assert "Test-Perp" in result
        assert "+3" in result  # 8 - 5 = 3 new trades
        assert "long" in result

    def test_no_new_trades(self, connected_spot_state: BotState) -> None:
        connected_spot_state.prev_roundtrips = 12  # same
        result = format_periodic_update("Test", connected_spot_state)
        assert result is not None
        assert "+0" in result

    def test_disconnected_shows(self, disconnected_state: BotState) -> None:
        result = format_periodic_update("Test", disconnected_state)
        assert result is not None
        assert "disconnected" in result

    def test_no_summary_returns_none(self) -> None:
        state = BotState(label="Test", url="ws://x", connected=True)
        result = format_periodic_update("Test", state)
        assert result is None


class TestFormatErrorAlert:
    def test_error_format(self) -> None:
        result = format_error_alert("MyBot", "Connection lost")
        assert "MyBot" in result
        assert "Connection lost" in result
        assert "error" in result


class TestFormatStartupMessage:
    def test_startup_format(self) -> None:
        result = format_startup_message(["Bot1", "Bot2"])
        assert "monitor started" in result
        assert "Bot1" in result
        assert "Bot2" in result
