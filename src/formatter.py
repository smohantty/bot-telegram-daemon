"""HTML message formatting for Telegram.

Two message styles:
  - format_bot_status():      Full detailed summary (for /status command)
  - format_periodic_update(): Lightweight interval update (for periodic reports)
"""

from __future__ import annotations

from .bot_state import BotState
from .models import PerpGridSummary, SpotGridSummary


# ---------------------------------------------------------------------------
#  Full status (for /status command)
# ---------------------------------------------------------------------------


def format_bot_status(label: str, state: BotState) -> str:
    """Full detailed status for /status command."""
    if not state.connected:
        return f"{label} — disconnected"

    if state.summary is None:
        return f"{label} — waiting for data"

    if isinstance(state.summary, SpotGridSummary):
        return _format_spot_full(label, state)
    elif isinstance(state.summary, PerpGridSummary):
        return _format_perp_full(label, state)

    return f"{label} — unknown summary type"


def _format_spot_full(label: str, state: BotState) -> str:
    s = state.summary
    assert isinstance(s, SpotGridSummary)

    network = state.info.network if state.info else "?"
    exchange = state.info.exchange if state.info else "?"

    investment = state.config.total_investment if state.config else 0
    trigger = state.config.trigger_price if state.config else None
    trigger_str = f"${_fp(trigger)}" if trigger is not None else "—"
    entry = f"${_fp(s.initial_entry_price)}" if s.initial_entry_price is not None else "—"
    spacing = _format_spacing(s.grid_spacing_pct)

    pnl_sign = "+" if s.total_profit >= 0 else ""

    return (
        f"<b>{s.symbol} spot grid</b>  <code>{exchange} · {network}</code>\n"
        f"\n"
        f"uptime           {s.uptime}\n"
        f"trades           {s.roundtrips}\n"
        f"\n"
        f"<b>pnl</b>\n"
        f"  net profit     <b>{pnl_sign}{s.total_profit:.2f}</b>\n"
        f"  matched        {s.matched_profit:+.2f}\n"
        f"  fees           {s.total_fees:.2f}\n"
        f"\n"
        f"<b>position</b>\n"
        f"  base           {s.base_balance:.4f}\n"
        f"  quote          ${_fp(s.quote_balance)}\n"
        f"  entry price    {entry}\n"
        f"\n"
        f"<b>grid</b>\n"
        f"  range          ${_fp(s.grid_range_low)} – ${_fp(s.grid_range_high)}\n"
        f"  zones          {s.grid_count}  ({spacing})\n"
        f"  trigger        {trigger_str}\n"
        f"  investment     ${_fp(investment)}"
    )


def _format_perp_full(label: str, state: BotState) -> str:
    s = state.summary
    assert isinstance(s, PerpGridSummary)

    network = state.info.network if state.info else "?"
    exchange = state.info.exchange if state.info else "?"

    investment = state.config.total_investment if state.config else 0
    trigger = state.config.trigger_price if state.config else None
    trigger_str = f"${_fp(trigger)}" if trigger is not None else "—"
    is_isolated = state.config.is_isolated if state.config else False
    margin_mode = "isolated" if is_isolated else "cross"
    entry = f"${_fp(s.initial_entry_price)}" if s.initial_entry_price is not None else "—"
    spacing = _format_spacing(s.grid_spacing_pct)

    total_pnl = s.matched_profit + s.unrealized_pnl - s.total_fees
    pnl_sign = "+" if total_pnl >= 0 else ""

    return (
        f"<b>{s.symbol} perp grid</b>  <code>{exchange} · {network}</code>\n"
        f"{s.grid_bias} · {s.leverage}x · {margin_mode}\n"
        f"\n"
        f"uptime           {s.uptime}\n"
        f"trades           {s.roundtrips}\n"
        f"\n"
        f"<b>pnl</b>\n"
        f"  net profit     <b>{pnl_sign}{total_pnl:.2f}</b>\n"
        f"  realized       {s.matched_profit:+.2f}\n"
        f"  unrealized     {s.unrealized_pnl:+.2f}\n"
        f"  fees           {s.total_fees:.2f}\n"
        f"\n"
        f"<b>position</b>\n"
        f"  side           {s.position_side.lower()}  {abs(s.position_size):.4f}\n"
        f"  entry price    {entry}\n"
        f"  avg entry      ${_fp(s.avg_entry_price)}\n"
        f"  margin         ${_fp(s.margin_balance)}\n"
        f"\n"
        f"<b>grid</b>\n"
        f"  range          ${_fp(s.grid_range_low)} – ${_fp(s.grid_range_high)}\n"
        f"  zones          {s.grid_count}  ({spacing})\n"
        f"  trigger        {trigger_str}\n"
        f"  investment     ${_fp(investment)}"
    )


# ---------------------------------------------------------------------------
#  Periodic update (lightweight — just what matters between intervals)
# ---------------------------------------------------------------------------


def format_periodic_update(label: str, state: BotState) -> str | None:
    """Lightweight periodic update showing deltas since last report.

    Shows: new trades, matched profit earned, fees paid, net earned.
    Returns None if no data yet.
    """
    if not state.connected:
        return f"{label}  —  disconnected"

    if state.summary is None:
        return None  # no data yet, skip

    s = state.summary
    new_trades = s.roundtrips - state.prev_roundtrips
    matched_delta = s.matched_profit - state.prev_matched_profit
    fees_delta = s.total_fees - state.prev_total_fees
    net_earned = matched_delta - fees_delta

    net_sign = "+" if net_earned >= 0 else ""

    if isinstance(s, SpotGridSummary):
        return (
            f"<b>{label}</b>  {s.symbol}\n"
            f"  trades +{new_trades}  ·  "
            f"earned {net_sign}{net_earned:.2f}  "
            f"(matched {matched_delta:+.2f}, fees {fees_delta:.2f})"
        )
    elif isinstance(s, PerpGridSummary):
        return (
            f"<b>{label}</b>  {s.symbol} {s.grid_bias} {s.leverage}x\n"
            f"  trades +{new_trades}  ·  "
            f"earned {net_sign}{net_earned:.2f}  "
            f"(matched {matched_delta:+.2f}, fees {fees_delta:.2f})"
        )

    return None


# ---------------------------------------------------------------------------
#  Error & startup messages
# ---------------------------------------------------------------------------


def format_error_alert(label: str, error_msg: str) -> str:
    return f"<b>{label} error</b>\n{error_msg}"


def format_startup_message(labels: list[str]) -> str:
    bot_list = ", ".join(labels)
    return f"bot monitor started — watching {bot_list}"


def format_disconnected_alert(label: str) -> str:
    return f"{label} — connection lost"


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------


def _fp(price: float) -> str:
    """Format price with thousands separator and smart decimals."""
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
    """Format grid spacing. Single value for geometric, range for arithmetic."""
    min_s, max_s = spacing
    decimals = 3 if min_s < 1.0 else 2
    relative_diff = abs(max_s - min_s) / max(max_s, min_s) if max(max_s, min_s) > 0 else 0

    if relative_diff < 0.01:
        return f"{min_s:.{decimals}f}%"
    else:
        return f"{min_s:.{decimals}f}% – {max_s:.{decimals}f}%"
