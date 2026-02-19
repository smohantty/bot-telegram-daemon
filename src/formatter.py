"""HTML message formatting for Telegram.

Ported from hyperliquid-trading-bot/src/reporter/telegram.rs.
All functions produce HTML strings suitable for Telegram's HTML parse mode.
"""

from __future__ import annotations

from .bot_state import BotState
from .models import PerpGridSummary, SpotGridSummary


def format_bot_status(label: str, state: BotState) -> str:
    """Format a single bot's status for Telegram HTML."""
    if not state.connected:
        return f"\u26aa <b>{label}</b> \u2014 Disconnected"

    if state.summary is None:
        return f"\u23f3 <b>{label}</b> \u2014 No summary yet"

    if isinstance(state.summary, SpotGridSummary):
        return _format_spot_summary(state)
    elif isinstance(state.summary, PerpGridSummary):
        return _format_perp_summary(state)

    return f"\u2753 <b>{label}</b> \u2014 Unknown summary type"


def _format_spot_summary(state: BotState) -> str:
    """Format spot grid summary — mirrors Rust CachedSummary::SpotGrid."""
    s = state.summary
    assert isinstance(s, SpotGridSummary)

    network = state.info.network.upper() if state.info else "?"
    spacing = _format_spacing(s.grid_spacing_pct)

    pnl_emoji = "\U0001f7e2" if s.total_profit >= 0 else "\U0001f534"
    pnl_sign = "+" if s.total_profit >= 0 else ""

    # Config-derived values
    investment = state.config.total_investment if state.config else 0
    trigger = state.config.trigger_price if state.config else None
    trigger_str = f"${trigger:.2f}" if trigger is not None else "None"

    init_entry = f"${s.initial_entry_price:.2f}" if s.initial_entry_price is not None else "-"

    return (
        f"<b>\U0001f4ca SPOT GRID: {s.symbol} ({network})</b>\n"
        f"\u23f1\ufe0f Running for {s.uptime}\n"
        f"\U0001f504 Matched Trades: <code>{s.roundtrips}</code>\n\n"
        f"<b>\U0001f4b0 PROFIT & LOSS</b>\n"
        f"Total: {pnl_emoji} <b>{pnl_sign}{s.total_profit:.2f}</b>\n"
        f"Matched: <b>{s.matched_profit:.2f}</b>\n"
        f"Fees: <code>${s.total_fees:.2f}</code>\n\n"
        f"<b>\U0001f4e6 POSITION</b>\n"
        f"Base: <code>{s.position_size:.4f}</code>\n"
        f"Quote: <code>${s.quote_balance:.2f}</code>\n"
        f"Init Entry: <code>{init_entry}</code>\n\n"
        f"<b>\U0001f4d0 GRID CONFIG</b>\n"
        f"Range: <code>${_format_price(s.range_low)} - ${_format_price(s.range_high)}</code>\n"
        f"Zones: <code>{s.grid_count}</code> ({spacing} spacing)\n"
        f"Trigger: <code>{trigger_str}</code>\n"
        f"Invest: <code>${investment:.2f}</code>"
    )


def _format_perp_summary(state: BotState) -> str:
    """Format perp grid summary — mirrors Rust CachedSummary::PerpGrid."""
    s = state.summary
    assert isinstance(s, PerpGridSummary)

    network = state.info.network.upper() if state.info else "?"
    spacing = _format_spacing(s.grid_spacing_pct)

    total_pnl = s.matched_profit + s.unrealized_pnl - s.total_fees
    pnl_emoji = "\U0001f7e2" if total_pnl >= 0 else "\U0001f534"
    pnl_sign = "+" if total_pnl >= 0 else ""

    bias_emoji = {
        "long": "\U0001f7e2",
        "short": "\U0001f534",
    }.get(s.grid_bias.lower(), "\u26aa")

    pos_emoji = {
        "Long": "\U0001f4c8",
        "Short": "\U0001f4c9",
    }.get(s.position_side, "\u2796")

    # Config-derived values
    investment = state.config.total_investment if state.config else 0
    trigger = state.config.trigger_price if state.config else None
    trigger_str = f"${trigger:.2f}" if trigger is not None else "None"
    is_isolated = state.config.is_isolated if state.config else False
    margin_mode = "Isolated" if is_isolated else "Cross"

    init_entry = f"${s.initial_entry_price:.2f}" if s.initial_entry_price is not None else "-"

    return (
        f"<b>\U0001f4ca PERP GRID: {s.symbol} ({network})</b>\n"
        f"{bias_emoji} <b>{s.grid_bias}</b> ({s.leverage}x)\n"
        f"\u23f1\ufe0f Running for {s.uptime}\n"
        f"\U0001f504 Matched Trades: <code>{s.roundtrips}</code>\n\n"
        f"<b>\U0001f4b0 PROFIT & LOSS</b>\n"
        f"Total: {pnl_emoji} <b>{pnl_sign}{total_pnl:.2f}</b>\n"
        f"Realized: <b>{s.matched_profit:.2f}</b>\n"
        f"Unrealized: <b>{s.unrealized_pnl:.2f}</b>\n"
        f"Fees: <code>${s.total_fees:.2f}</code>\n\n"
        f"<b>\U0001f4e6 POSITION</b>\n"
        f"{pos_emoji} <b>{s.position_side}</b>\n"
        f"Size: <code>{abs(s.position_size):.4f}</code>\n"
        f"Init Entry: <code>{init_entry}</code>\n"
        f"Avg Entry: <code>${s.avg_entry_price:.2f}</code>\n"
        f"Margin: <code>${s.margin_balance:.2f}</code>\n\n"
        f"<b>\U0001f4d0 GRID CONFIG</b>\n"
        f"Range: <code>${_format_price(s.range_low)} - ${_format_price(s.range_high)}</code>\n"
        f"Zones: <code>{s.grid_count}</code> ({spacing} spacing)\n"
        f"Trigger: <code>{trigger_str}</code>\n"
        f"Mode: <code>{margin_mode}</code>\n"
        f"Invest: <code>${investment:.2f}</code>"
    )


def format_error_alert(label: str, error_msg: str) -> str:
    """Format an error alert message."""
    return f"\U0001f534 <b>Bot Stopped (Error): {label}</b>\nREASON: <code>{error_msg}</code>"


def format_startup_message(labels: list[str]) -> str:
    """Format the daemon startup notification."""
    bot_list = ", ".join(labels)
    return f"\U0001f7e2 <b>Bot Monitor Started</b>\nWatching: {bot_list}"


def format_disconnected_alert(label: str) -> str:
    """Format a disconnection alert."""
    return f"\u26a0\ufe0f <b>{label}</b> \u2014 Connection lost"


# --- Helper functions ---


def _format_price(price: float) -> str:
    """Format price with thousands separator.

    Ported from Rust format_price() in telegram.rs.
    """
    if price >= 1000.0:
        whole = int(price)
        frac = round((price - whole) * 100)
        # Add thousands separators
        formatted = f"{whole:,}"
        if frac > 0:
            return f"{formatted}.{frac:02d}"
        return formatted
    else:
        return f"{price:.2f}"


def _format_spacing(spacing: tuple[float, float]) -> str:
    """Format grid spacing percentage.

    Ported from Rust format_spacing() in telegram.rs.
    Shows single value for geometric (equal min/max), range for arithmetic.
    """
    min_s, max_s = spacing
    decimals = 3 if min_s < 1.0 else 2
    relative_diff = abs(max_s - min_s) / max(max_s, min_s) if max(max_s, min_s) > 0 else 0

    if relative_diff < 0.01:
        return f"{min_s:.{decimals}f}%"
    else:
        return f"{min_s:.{decimals}f}% - {max_s:.{decimals}f}%"
