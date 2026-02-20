"""Shared test fixtures for bot-telegram-daemon tests."""

from __future__ import annotations

import pytest

from src.bot_state import BotState
from src.models import (
    PerpGridSummary,
    SpotGridSummary,
    StrategyConfig,
    SystemInfo,
)


@pytest.fixture
def system_info() -> SystemInfo:
    return SystemInfo(network="mainnet", exchange="hyperliquid")


@pytest.fixture
def spot_config() -> StrategyConfig:
    return StrategyConfig(
        type="spot_grid",
        symbol="ETH/USDC",
        raw={
            "type": "spot_grid",
            "symbol": "ETH/USDC",
            "grid_range_high": 4000.0,
            "grid_range_low": 3000.0,
            "grid_type": "geometric",
            "grid_count": 10,
            "total_investment": 1000.0,
            "trigger_price": 3500.0,
        },
    )


@pytest.fixture
def perp_config() -> StrategyConfig:
    return StrategyConfig(
        type="perp_grid",
        symbol="HYPE",
        raw={
            "type": "perp_grid",
            "symbol": "HYPE",
            "leverage": 5,
            "grid_range_high": 30.0,
            "grid_range_low": 20.0,
            "grid_type": "geometric",
            "grid_count": 20,
            "total_investment": 5000.0,
            "grid_bias": "long",
            "trigger_price": None,
            "is_isolated": False,
        },
    )


@pytest.fixture
def spot_summary() -> SpotGridSummary:
    return SpotGridSummary(
        symbol="ETH/USDC",
        state="Running",
        uptime="2d 14h 30m",
        position_size=1.5,
        matched_profit=45.23,
        total_profit=52.10,
        total_fees=3.12,
        grid_count=10,
        grid_range_low=3000.0,
        grid_range_high=4000.0,
        grid_spacing_pct=(1.05, 1.05),
        roundtrips=12,
        base_balance=1.5,
        quote_balance=500.0,
        initial_entry_price=3500.0,
    )


@pytest.fixture
def perp_summary() -> PerpGridSummary:
    return PerpGridSummary(
        symbol="HYPE",
        state="Running",
        uptime="1d 8h 15m",
        position_size=100.0,
        position_side="Long",
        matched_profit=120.50,
        total_profit=135.20,
        total_fees=8.30,
        leverage=5,
        grid_bias="long",
        grid_count=20,
        grid_range_low=20.0,
        grid_range_high=30.0,
        grid_spacing_pct=(0.5, 0.5),
        roundtrips=8,
        margin_balance=1135.20,
        initial_entry_price=25.0,
        avg_entry_price=24.8,
        unrealized_pnl=23.0,
    )


@pytest.fixture
def connected_spot_state(
    system_info: SystemInfo,
    spot_config: StrategyConfig,
    spot_summary: SpotGridSummary,
) -> BotState:
    return BotState(
        label="Test-Spot",
        url="ws://localhost:9001",
        connected=True,
        info=system_info,
        config=spot_config,
        summary=spot_summary,
    )


@pytest.fixture
def connected_perp_state(
    system_info: SystemInfo,
    perp_config: StrategyConfig,
    perp_summary: PerpGridSummary,
) -> BotState:
    return BotState(
        label="Test-Perp",
        url="ws://localhost:9000",
        connected=True,
        info=system_info,
        config=perp_config,
        summary=perp_summary,
    )


@pytest.fixture
def disconnected_state() -> BotState:
    return BotState(
        label="Test-Disconnected",
        url="ws://localhost:9002",
        connected=False,
    )
