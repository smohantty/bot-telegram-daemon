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
        return f"\u23f3 <b>{label}</b> \u2014 Waiting for data..."

    if isinstance(state.summary, SpotGridSummary):
        return _format_spot_summary(label, state)
    elif isinstance(state.summary, PerpGridSummary):
        return _format_perp_summary(label, state)

    return f"\u2753 <b>{label}</b> \u2014 Unknown summary type"


def _format_spot_summary(label: str, state: BotState) -> str:
    """Format spot grid summary with clean aligned layout."""
    s = state.summary
    assert isinstance(s, SpotGridSummary)

    network = state.info.network.upper() if state.info else "?"
    exchange = state.info.exchange.capitalize() if state.info else "?"
    spacing = _format_spacing(s.grid_spacing_pct)

    pnl_emoji = "\U0001f7e2" if s.total_profit >= 0 else "\U0001f534"
    pnl_sign = "+" if s.total_profit >= 0 else ""

    # Config-derived values
    investment = state.config.total_investment if state.config else 0
    trigger = state.config.trigger_price if state.config else None
    trigger_str = f"${_format_price(trigger)}" if trigger is not None else "\u2014"

    entry_price = (
        f"${_format_price(s.initial_entry_price)}"
        if s.initial_entry_price is not None
        else "\u2014"
    )

    return (
        f"\U0001f4ca <b>SPOT GRID \u2022 {s.symbol}</b>\n"
        f"<code>    {exchange} \u2022 {network} \u2022 {label}</code>\n"
        f"\n"
        f"\u23f1 Uptime           <code>{s.uptime}</code>\n"
        f"\U0001f504 Completed Trades  <code>{s.roundtrips}</code>\n"
        f"\n"
        f"\U0001f4b0 <b>Profit & Loss</b>\n"
        f"    Net Profit     {pnl_emoji} <b>{pnl_sign}{s.total_profit:.2f}</b>\n"
        f"    Matched P/L    <code>{s.matched_profit:+.2f}</code>\n"
        f"    Trading Fees   <code>{s.total_fees:.2f}</code>\n"
        f"\n"
        f"\U0001f4e6 <b>Position</b>\n"
        f"    Base Balance   <code>{s.base_balance:.4f}</code>\n"
        f"    Quote Balance  <code>${_format_price(s.quote_balance)}</code>\n"
        f"    Entry Price    <code>{entry_price}</code>\n"
        f"\n"
        f"\U0001f4d0 <b>Grid Settings</b>\n"
        f"    Price Range    <code>${_format_price(s.range_low)} \u2013 ${_format_price(s.range_high)}</code>\n"
        f"    Grid Zones     <code>{s.grid_count}</code>  ({spacing})\n"
        f"    Trigger Price  <code>{trigger_str}</code>\n"
        f"    Investment     <code>${_format_price(investment)}</code>"
    )


def _format_perp_summary(label: str, state: BotState) -> str:
    """Format perp grid summary with clean aligned layout."""
    s = state.summary
    assert isinstance(s, PerpGridSummary)

    network = state.info.network.upper() if state.info else "?"
    exchange = state.info.exchange.capitalize() if state.info else "?"
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
    trigger_str = f"${_format_price(trigger)}" if trigger is not None else "\u2014"
    is_isolated = state.config.is_isolated if state.config else False
    margin_mode = "Isolated" if is_isolated else "Cross"

    entry_price = (
        f"${_format_price(s.initial_entry_price)}"
        if s.initial_entry_price is not None
        else "\u2014"
    )

    return (
        f"\U0001f4ca <b>PERP GRID \u2022 {s.symbol}</b>\n"
        f"<code>    {exchange} \u2022 {network} \u2022 {label}</code>\n"
        f"    {bias_emoji} {s.grid_bias.upper()} bias \u2022 {s.leverage}x leverage\n"
        f"\n"
        f"\u23f1 Uptime           <code>{s.uptime}</code>\n"
        f"\U0001f504 Completed Trades  <code>{s.roundtrips}</code>\n"
        f"\n"
        f"\U0001f4b0 <b>Profit & Loss</b>\n"
        f"    Net Profit     {pnl_emoji} <b>{pnl_sign}{total_pnl:.2f}</b>\n"
        f"    Realized P/L   <code>{s.matched_profit:+.2f}</code>\n"
        f"    Unrealized P/L <code>{s.unrealized_pnl:+.2f}</code>\n"
        f"    Trading Fees   <code>{s.total_fees:.2f}</code>\n"
        f"\n"
        f"\U0001f4e6 <b>Position</b>\n"
        f"    {pos_emoji} <b>{s.position_side}</b>  <code>{abs(s.position_size):.4f}</code>\n"
        f"    Entry Price    <code>{entry_price}</code>\n"
        f"    Avg Entry      <code>${_format_price(s.avg_entry_price)}</code>\n"
        f"    Margin Balance <code>${_format_price(s.margin_balance)}</code>\n"
        f"\n"
        f"\U0001f4d0 <b>Grid Settings</b>\n"
        f"    Price Range    <code>${_format_price(s.range_low)} \u2013 ${_format_price(s.range_high)}</code>\n"
        f"    Grid Zones     <code>{s.grid_count}</code>  ({spacing})\n"
        f"    Trigger Price  <code>{trigger_str}</code>\n"
        f"    Margin Mode    <code>{margin_mode}</code>\n"
        f"    Investment     <code>${_format_price(investment)}</code>"
    )


def format_error_alert(label: str, error_msg: str) -> str:
    """Format an error alert message."""
    return (
        f"\U0001f6a8 <b>ERROR \u2022 {label}</b>\n"
        f"\n"
        f"<code>{error_msg}</code>"
    )


def format_startup_message(labels: list[str]) -> str:
    """Format the daemon startup notification."""
    bot_lines = "\n".join(f"    \u2022 {lbl}" for lbl in labels)
    return (
        f"\U0001f7e2 <b>Bot Monitor Started</b>\n"
        f"\n"
        f"Watching {len(labels)} bot(s):\n"
        f"{bot_lines}"
    )


def format_disconnected_alert(label: str) -> str:
    """Format a disconnection alert."""
    return f"\u26a0\ufe0f <b>{label}</b> \u2014 Connection lost"


# --- Helper functions ---


def _format_price(price: float) -> str:
    """Format price with thousands separator and smart decimal places."""
    if price >= 1000.0:
        whole = int(price)
        frac = round((price - whole) * 100)
        formatted = f"{whole:,}"
        if frac > 0:
            return f"{formatted}.{frac:02d}"
        return formatted
    elif price >= 1.0:
        return f"{price:.2f}"
    elif price >= 0.01:
        return f"{price:.4f}"
    else:
        return f"{price:.6f}"


def _format_spacing(spacing: tuple[float, float]) -> str:
    """Format grid spacing percentage.

    Shows single value for geometric (equal min/max), range for arithmetic.
    """
    min_s, max_s = spacing
    decimals = 3 if min_s < 1.0 else 2
    relative_diff = abs(max_s - min_s) / max(max_s, min_s) if max(max_s, min_s) > 0 else 0

    if relative_diff < 0.01:
        return f"{min_s:.{decimals}f}%"
    else:
        return f"{min_s:.{decimals}f}% \u2013 {max_s:.{decimals}f}%"
