"""Per-bot state cache.

Each monitored bot has a BotState instance that tracks its connection status,
latest configuration, system info, and most recent summary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .models import PerpGridSummary, SpotGridSummary, StrategyConfig, SystemInfo


@dataclass
class BotState:
    """Mutable state container for a single monitored bot."""

    label: str
    url: str

    # Connection status
    connected: bool = False
    last_connected_at: datetime | None = None

    # Cached data from WS events
    info: SystemInfo | None = None
    config: StrategyConfig | None = None
    summary: SpotGridSummary | PerpGridSummary | None = None
    last_summary_at: datetime | None = None

    # Error tracking
    last_error: str | None = None
    last_error_at: datetime | None = None

    # Periodic tracking — snapshots at last report, for computing deltas
    prev_roundtrips: int = 0
    prev_matched_profit: float = 0.0
    prev_total_fees: float = 0.0
    initial_summary_sent: bool = False
