"""Tests for WebSocket event model parsing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.models import (
    PerpGridSummary,
    SpotGridSummary,
    parse_perp_grid_summary,
    parse_spot_grid_summary,
    parse_strategy_config,
    parse_system_info,
)

# Load fixtures from bot-ws-schema
FIXTURES_DIR = Path(__file__).parent.parent / "schema" / "bot-ws-schema" / "fixtures"


def _load_fixture(name: str) -> dict:
    """Load a fixture JSON file and return the data portion."""
    path = FIXTURES_DIR / name
    with open(path) as f:
        event = json.load(f)
    return event


class TestParseSystemInfo:
    def test_from_fixture(self) -> None:
        event = _load_fixture("info.json")
        info = parse_system_info(event["data"])
        assert info.network == "mainnet"
        assert info.exchange in ("hyperliquid", "lighter")


class TestParseStrategyConfig:
    def test_spot_config(self) -> None:
        event = _load_fixture("config_spot.json")
        config = parse_strategy_config(event["data"])
        assert config.type == "spot_grid"
        assert config.symbol is not None
        assert config.total_investment > 0

    def test_perp_config(self) -> None:
        event = _load_fixture("config_perp.json")
        config = parse_strategy_config(event["data"])
        assert config.type == "perp_grid"
        assert config.symbol is not None
        assert config.total_investment > 0
        assert config.raw.get("leverage") is not None


class TestParseSpotGridSummary:
    def test_from_fixture(self) -> None:
        event = _load_fixture("spot_grid_summary.json")
        summary = parse_spot_grid_summary(event["data"])
        assert isinstance(summary, SpotGridSummary)
        assert summary.symbol is not None
        assert summary.state is not None
        assert isinstance(summary.grid_spacing_pct, tuple)
        assert len(summary.grid_spacing_pct) == 2

    def test_optional_fields(self) -> None:
        """initial_entry_price can be null."""
        data = {
            "symbol": "ETH/USDC",
            "state": "Running",
            "uptime": "1h 30m",
            "position_size": 0.5,
            "matched_profit": 10.0,
            "total_profit": 12.0,
            "total_fees": 1.0,
            "grid_count": 5,
            "range_low": 3000.0,
            "range_high": 4000.0,
            "grid_spacing_pct": [2.0, 2.0],
            "roundtrips": 3,
            "base_balance": 0.5,
            "quote_balance": 200.0,
            "initial_entry_price": None,
        }
        summary = parse_spot_grid_summary(data)
        assert summary.initial_entry_price is None


class TestParsePerpGridSummary:
    def test_from_fixture(self) -> None:
        event = _load_fixture("perp_grid_summary.json")
        summary = parse_perp_grid_summary(event["data"])
        assert isinstance(summary, PerpGridSummary)
        assert summary.symbol is not None
        assert summary.grid_bias in ("long", "short", "neutral")
        assert isinstance(summary.grid_spacing_pct, tuple)

    def test_optional_fields_default(self) -> None:
        """avg_entry_price and unrealized_pnl default to 0.0."""
        data = {
            "symbol": "HYPE",
            "state": "Running",
            "uptime": "1h",
            "position_size": 50.0,
            "position_side": "Long",
            "matched_profit": 20.0,
            "total_profit": 25.0,
            "total_fees": 2.0,
            "leverage": 3,
            "grid_bias": "long",
            "grid_count": 10,
            "range_low": 20.0,
            "range_high": 30.0,
            "grid_spacing_pct": [1.0, 1.0],
            "roundtrips": 5,
            "margin_balance": 500.0,
        }
        summary = parse_perp_grid_summary(data)
        assert summary.avg_entry_price == 0.0
        assert summary.unrealized_pnl == 0.0
        assert summary.initial_entry_price is None
