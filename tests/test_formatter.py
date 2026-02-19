"""Tests for Telegram HTML message formatting."""

from __future__ import annotations

from src.bot_state import BotState
from src.formatter import (
    _format_price,
    _format_spacing,
    format_bot_status,
    format_error_alert,
    format_startup_message,
)
from src.models import PerpGridSummary, SpotGridSummary


class TestFormatPrice:
    """Test the price formatting helper."""

    def test_small_price(self) -> None:
        assert _format_price(1.50) == "1.50"
        assert _format_price(99.99) == "99.99"

    def test_tiny_price(self) -> None:
        assert _format_price(0.50) == "0.5000"
        assert _format_price(0.005) == "0.005000"

    def test_thousands(self) -> None:
        assert _format_price(1000.0) == "1,000"
        assert _format_price(3500.50) == "3,500.50"

    def test_large_price(self) -> None:
        assert _format_price(25000.0) == "25,000"
        assert _format_price(100000.75) == "100,000.75"


class TestFormatSpacing:
    """Test the grid spacing formatting helper."""

    def test_geometric_equal(self) -> None:
        """Same min/max -> single value."""
        result = _format_spacing((1.05, 1.05))
        assert result == "1.05%"

    def test_arithmetic_range(self) -> None:
        """Different min/max -> range."""
        result = _format_spacing((1.80, 3.20))
        assert "1.80%" in result
        assert "3.20%" in result

    def test_small_spacing(self) -> None:
        """Spacing < 1% uses 3 decimals."""
        result = _format_spacing((0.500, 0.500))
        assert result == "0.500%"


class TestFormatBotStatus:
    """Test the main bot status formatter."""

    def test_disconnected(self, disconnected_state: BotState) -> None:
        result = format_bot_status("Test", disconnected_state)
        assert "Disconnected" in result

    def test_no_summary(self) -> None:
        state = BotState(label="Test", url="ws://x", connected=True)
        result = format_bot_status("Test", state)
        assert "Waiting for data" in result

    def test_spot_summary(self, connected_spot_state: BotState) -> None:
        result = format_bot_status("Test-Spot", connected_spot_state)
        assert "SPOT GRID" in result
        assert "ETH/USDC" in result
        assert "MAINNET" in result
        assert "Profit & Loss" in result
        assert "Position" in result
        assert "Grid Settings" in result
        assert "52.10" in result  # total_profit
        assert "45.23" in result  # matched_profit
        assert "12" in result  # roundtrips
        assert "Entry Price" in result
        assert "Test-Spot" in result  # label in header

    def test_perp_summary(self, connected_perp_state: BotState) -> None:
        result = format_bot_status("Test-Perp", connected_perp_state)
        assert "PERP GRID" in result
        assert "HYPE" in result
        assert "LONG" in result  # bias uppercased
        assert "5x" in result  # leverage
        assert "Profit & Loss" in result
        assert "Realized" in result
        assert "Unrealized" in result
        assert "Long" in result  # position_side
        assert "Margin Mode" in result
        assert "Test-Perp" in result  # label in header

    def test_positive_pnl_emoji(self, connected_spot_state: BotState) -> None:
        """Positive PnL shows green emoji."""
        result = format_bot_status("Test", connected_spot_state)
        assert "\U0001f7e2" in result  # green circle
        assert "+" in result

    def test_negative_pnl_emoji(self, connected_spot_state: BotState) -> None:
        """Negative PnL shows red emoji."""
        assert isinstance(connected_spot_state.summary, SpotGridSummary)
        connected_spot_state.summary.total_profit = -10.0
        result = format_bot_status("Test", connected_spot_state)
        assert "\U0001f534" in result  # red circle

    def test_label_in_spot_output(self, connected_spot_state: BotState) -> None:
        """Bot label appears in the formatted output."""
        result = format_bot_status("MyCustomLabel", connected_spot_state)
        assert "MyCustomLabel" in result

    def test_exchange_in_output(self, connected_perp_state: BotState) -> None:
        """Exchange name appears in the formatted output."""
        result = format_bot_status("Test", connected_perp_state)
        assert "Hyperliquid" in result  # capitalized exchange name


class TestFormatErrorAlert:
    def test_error_format(self) -> None:
        result = format_error_alert("MyBot", "Connection lost")
        assert "MyBot" in result
        assert "Connection lost" in result
        assert "ERROR" in result

    def test_error_has_label(self) -> None:
        result = format_error_alert("HL-Bot", "timeout")
        assert "HL-Bot" in result


class TestFormatStartupMessage:
    def test_startup_format(self) -> None:
        result = format_startup_message(["Bot1", "Bot2"])
        assert "Bot Monitor Started" in result
        assert "Bot1" in result
        assert "Bot2" in result

    def test_startup_shows_count(self) -> None:
        result = format_startup_message(["A", "B", "C"])
        assert "3" in result
