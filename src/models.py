"""Data models for WebSocket events received from trading bots.

These mirror the definitions in bot-ws-schema/schema/events.json.
The daemon only needs summary-related types (not GridState, OrderEvent, etc.)
since it's a monitoring tool, not a full dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SystemInfo:
    """System information event data."""

    network: str
    exchange: str


@dataclass
class SpotGridSummary:
    """Spot grid strategy summary."""

    symbol: str
    state: str  # "Initializing", "Running", "AcquiringAssets", "WaitingForTrigger"
    uptime: str  # Human-readable, e.g. "2d 14h 30m"

    # Position
    position_size: float  # Base asset inventory

    # PnL
    matched_profit: float
    total_profit: float
    total_fees: float

    # Grid metrics
    grid_count: int
    grid_range_low: float
    grid_range_high: float
    grid_spacing_pct: tuple[float, float]  # (min%, max%)
    roundtrips: int

    # Wallet balances
    base_balance: float
    quote_balance: float

    # Optional
    initial_entry_price: float | None = None


@dataclass
class PerpGridSummary:
    """Perp grid strategy summary."""

    symbol: str
    state: str
    uptime: str

    # Position
    position_size: float  # Positive = Long, Negative = Short
    position_side: str  # "Long", "Short", "Flat"

    # PnL
    matched_profit: float
    total_profit: float
    total_fees: float

    # Grid/Perp specific
    leverage: int
    grid_bias: str  # "long", "short", "neutral"
    grid_count: int
    grid_range_low: float
    grid_range_high: float
    grid_spacing_pct: tuple[float, float]
    roundtrips: int

    # Wallet
    margin_balance: float

    # Optional
    initial_entry_price: float | None = None
    avg_entry_price: float = 0.0
    unrealized_pnl: float = 0.0


@dataclass
class StrategyConfig:
    """Parsed strategy configuration from config event.

    We only extract the fields needed for Telegram formatting.
    The full config dict is kept in `raw` for any additional lookups.
    """

    type: str  # "spot_grid" or "perp_grid"
    symbol: str
    raw: dict = field(default_factory=dict)

    @property
    def total_investment(self) -> float:
        return float(self.raw.get("total_investment", 0))

    @property
    def trigger_price(self) -> float | None:
        v = self.raw.get("trigger_price")
        return float(v) if v is not None else None

    @property
    def is_isolated(self) -> bool:
        return bool(self.raw.get("is_isolated", False))


def parse_spot_grid_summary(data: dict) -> SpotGridSummary:
    """Parse a spot_grid_summary event data dict into a SpotGridSummary."""
    spacing = data.get("grid_spacing_pct", [0, 0])
    return SpotGridSummary(
        symbol=data["symbol"],
        state=data["state"],
        uptime=data["uptime"],
        position_size=data["position_size"],
        matched_profit=data["matched_profit"],
        total_profit=data["total_profit"],
        total_fees=data["total_fees"],
        grid_count=data["grid_count"],
        grid_range_low=data["grid_range_low"],
        grid_range_high=data["grid_range_high"],
        grid_spacing_pct=(spacing[0], spacing[1]),
        roundtrips=data["roundtrips"],
        base_balance=data["base_balance"],
        quote_balance=data["quote_balance"],
        initial_entry_price=data.get("initial_entry_price"),
    )


def parse_perp_grid_summary(data: dict) -> PerpGridSummary:
    """Parse a perp_grid_summary event data dict into a PerpGridSummary."""
    spacing = data.get("grid_spacing_pct", [0, 0])
    return PerpGridSummary(
        symbol=data["symbol"],
        state=data["state"],
        uptime=data["uptime"],
        position_size=data["position_size"],
        position_side=data["position_side"],
        matched_profit=data["matched_profit"],
        total_profit=data["total_profit"],
        total_fees=data["total_fees"],
        leverage=data["leverage"],
        grid_bias=data["grid_bias"],
        grid_count=data["grid_count"],
        grid_range_low=data["grid_range_low"],
        grid_range_high=data["grid_range_high"],
        grid_spacing_pct=(spacing[0], spacing[1]),
        roundtrips=data["roundtrips"],
        margin_balance=data["margin_balance"],
        initial_entry_price=data.get("initial_entry_price"),
        avg_entry_price=data.get("avg_entry_price", 0.0),
        unrealized_pnl=data.get("unrealized_pnl", 0.0),
    )


def parse_strategy_config(data: dict) -> StrategyConfig:
    """Parse a config event data dict into a StrategyConfig."""
    return StrategyConfig(
        type=data.get("type", "unknown"),
        symbol=data.get("symbol", "unknown"),
        raw=data,
    )


def parse_system_info(data: dict) -> SystemInfo:
    """Parse an info event data dict into a SystemInfo."""
    return SystemInfo(
        network=data["network"],
        exchange=data["exchange"],
    )
