"""Report card image generator for Telegram updates.

Provides two card styles:
- Full detail card (dark theme, 800×480) for on-demand /status
- Compact periodic card (light theme, 600×280) highlighting trades & profit
"""

from __future__ import annotations

import io
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from .bot_state import BotState
    from .models import PerpGridSummary, SpotGridSummary

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Colour palette — matches bot-dashboard CSS design tokens
# ---------------------------------------------------------------------------
C_BG        = (8,   12,  18)    # --bg-primary
C_SECTION   = (11,  16,  24)    # cell background (slightly lighter)
C_BORDER    = (30,  45,  61)    # --border-color
C_CYAN      = (0,   245, 212)   # --accent-primary
C_CYAN_DIM  = (0,   140, 122)   # dimmed accent for bar fills
C_GREEN     = (74,  222, 128)   # --color-buy-bright
C_RED       = (248, 113, 113)   # --color-sell-bright
C_GOLD      = (240, 185, 11)    # --accent-gold
C_TEXT_PRI  = (244, 246, 248)   # --text-primary
C_TEXT_SEC  = (148, 163, 184)   # --text-secondary
C_TEXT_MUT  = (100, 116, 139)   # --text-muted
C_TEXT_DIM  = (60,  75,  95)    # very dim text

# Blended bg tints (alpha-blended approximations on C_BG)
C_GREEN_BG  = (14,  30,  18)
C_RED_BG    = (30,  14,  14)
C_CYAN_BG   = (6,   30,  26)
C_GOLD_BG   = (32,  24,  6)

# ---------------------------------------------------------------------------
# Card geometry
# ---------------------------------------------------------------------------
CARD_W = 800
CARD_H = 480
PAD    = 26   # horizontal padding

# Section heights
_H_ACCENT = 3
_H_HEADER = 54
_H_SYMBOL = 44
_H_PNL    = 112
_H_ROW    = 80
_H_GRID   = 64

# Y start positions (each section is separated by a 1px divider)
_Y_HEADER = _H_ACCENT
_Y_SYMBOL = _Y_HEADER + _H_HEADER + 1
_Y_PNL    = _Y_SYMBOL + _H_SYMBOL + 1
_Y_ROW1   = _Y_PNL    + _H_PNL   + 1
_Y_GRID   = _Y_ROW1   + _H_ROW   + 1
_Y_ROW2   = _Y_GRID   + _H_GRID  + 1
_Y_FOOTER = _Y_ROW2   + _H_ROW   + 1
_H_FOOTER = CARD_H - _Y_FOOTER   # remaining space (~37px)

# ---------------------------------------------------------------------------
# Font management
# ---------------------------------------------------------------------------
_UBUNTU_DIR = "/usr/share/fonts/truetype/ubuntu/"
_DEJAVU_DIR = "/usr/share/fonts/truetype/dejavu/"

_FONT_CACHE: dict | None = None


def _try_font(path: str, size: int) -> ImageFont.FreeTypeFont | None:
    try:
        return ImageFont.truetype(path, size)
    except (OSError, IOError):
        return None


def _load_any(paths: list[str], size: int) -> ImageFont.FreeTypeFont:
    for path in paths:
        f = _try_font(path, size)
        if f is not None:
            return f
    return ImageFont.load_default()


def _fonts() -> dict:
    global _FONT_CACHE
    if _FONT_CACHE:
        return _FONT_CACHE

    bold_paths = [_UBUNTU_DIR + "Ubuntu-B.ttf",     _DEJAVU_DIR + "DejaVuSans-Bold.ttf"]
    reg_paths  = [_UBUNTU_DIR + "Ubuntu-R.ttf",     _DEJAVU_DIR + "DejaVuSans.ttf"]
    mono_paths = [_UBUNTU_DIR + "UbuntuMono-R.ttf", _DEJAVU_DIR + "DejaVuSansMono.ttf"]

    _FONT_CACHE = {
        "b11": _load_any(bold_paths, 11),
        "b13": _load_any(bold_paths, 13),
        "b15": _load_any(bold_paths, 15),
        "b18": _load_any(bold_paths, 18),
        "b22": _load_any(bold_paths, 22),
        "b38": _load_any(bold_paths, 38),
        "r11": _load_any(reg_paths,  11),
        "r12": _load_any(reg_paths,  12),
        "r13": _load_any(reg_paths,  13),
        "r14": _load_any(reg_paths,  14),
        "mn12": _load_any(mono_paths, 12),
        "mn13": _load_any(mono_paths, 13),
    }
    return _FONT_CACHE


# ---------------------------------------------------------------------------
# Low-level drawing helpers
# ---------------------------------------------------------------------------

def _textsize(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int, int, int]:
    """Return textbbox (left, top, right, bottom)."""
    return draw.textbbox((0, 0), text, font=font)


def _tw(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    """Text pixel width."""
    bb = _textsize(draw, text, font)
    return bb[2] - bb[0]


def _text(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
) -> None:
    """Draw text at (x, y) with bbox-offset correction so (x,y) is true top-left."""
    bb = _textsize(draw, text, font)
    draw.text((x - bb[0], y - bb[1]), text, font=font, fill=fill)


def _text_centered(
    draw: ImageDraw.ImageDraw,
    cx: int,
    y: int,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
) -> None:
    """Draw text horizontally centered around cx, top at y."""
    bb = _textsize(draw, text, font)
    x = cx - (bb[2] - bb[0]) // 2
    _text(draw, x, y, text, font, fill)


def _text_right(
    draw: ImageDraw.ImageDraw,
    rx: int,
    y: int,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
) -> None:
    """Draw text right-aligned at rx, top at y."""
    bb = _textsize(draw, text, font)
    x = rx - (bb[2] - bb[0])
    _text(draw, x, y, text, font, fill)


def _text_vcenter(
    draw: ImageDraw.ImageDraw,
    x: int,
    sec_y: int,
    sec_h: int,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
) -> None:
    """Draw text left-aligned at x, vertically centered in section."""
    bb = _textsize(draw, text, font)
    h = bb[3] - bb[1]
    y = sec_y + (sec_h - h) // 2
    _text(draw, x, y, text, font, fill)


def _text_vcenter_right(
    draw: ImageDraw.ImageDraw,
    rx: int,
    sec_y: int,
    sec_h: int,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
) -> None:
    """Draw text right-aligned at rx, vertically centered in section."""
    bb = _textsize(draw, text, font)
    w = bb[2] - bb[0]
    h = bb[3] - bb[1]
    x = rx - w
    y = sec_y + (sec_h - h) // 2
    _text(draw, x, y, text, font, fill)


def _divider(draw: ImageDraw.ImageDraw, y: int) -> None:
    draw.line([(0, y), (CARD_W, y)], fill=C_BORDER, width=1)


def _vdivider(draw: ImageDraw.ImageDraw, x: int, y: int, h: int) -> None:
    draw.line([(x, y), (x, y + h)], fill=C_BORDER, width=1)


def _badge(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    text_color: tuple,
    bg_color: tuple,
    font: ImageFont.FreeTypeFont,
    h_pad: int = 8,
    v_pad: int = 4,
) -> int:
    """Draw a rounded pill badge. Returns right edge x."""
    bb = _textsize(draw, text, font)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]
    w = tw + 2 * h_pad
    h = th + 2 * v_pad
    draw.rounded_rectangle([(x, y), (x + w, y + h)], radius=4, fill=bg_color)
    # Text inside badge with offset correction
    tx = x + h_pad - bb[0]
    ty = y + v_pad - bb[1]
    draw.text((tx, ty), text, font=font, fill=text_color)
    return x + w


# ---------------------------------------------------------------------------
# Price / value formatting
# ---------------------------------------------------------------------------

def _fp(price: float) -> str:
    """Format price with thousands separator and smart decimals."""
    if price >= 1000.0:
        whole = int(price)
        frac = round((price - whole) * 100)
        if frac > 0:
            return f"{whole:,}.{frac:02d}"
        return f"{whole:,}"
    elif price >= 1.0:
        return f"{price:.2f}"
    elif price >= 0.01:
        return f"{price:.4f}"
    else:
        return f"{price:.6f}"


def _signed(value: float) -> str:
    """Format value as +$X.XX or -$X.XX."""
    sign = "+" if value >= 0 else "-"
    return f"{sign}${_fp(abs(value))}"


def _pnl_color(value: float) -> tuple:
    return C_GREEN if value >= 0 else C_RED


def _pnl_bg(value: float) -> tuple:
    return C_GREEN_BG if value >= 0 else C_RED_BG


def _format_spacing(spacing: tuple[float, float]) -> str:
    min_s, max_s = spacing
    decimals = 3 if min_s < 1.0 else 2
    diff_ratio = abs(max_s - min_s) / max(max_s, min_s) if max(max_s, min_s) > 0 else 0
    if diff_ratio < 0.01:
        return f"{min_s:.{decimals}f}%"
    return f"{min_s:.{decimals}f}%–{max_s:.{decimals}f}%"


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------

def _draw_background(img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
    draw.rectangle([(0, 0), (CARD_W, CARD_H)], fill=C_BG)
    draw.rectangle([(0, 0), (CARD_W, _H_ACCENT)], fill=C_CYAN)


def _draw_header(draw: ImageDraw.ImageDraw, label: str, exchange: str, network: str) -> None:
    f = _fonts()
    y = _Y_HEADER
    h = _H_HEADER

    # Label — left
    _text_vcenter(draw, PAD, y, h, label, f["b15"], C_TEXT_PRI)

    # Exchange · Network — center
    exch_u = exchange.upper()
    net_u  = network.upper()
    exch_color = C_CYAN  if exchange.lower() == "hyperliquid" else C_GOLD
    net_color  = C_GREEN if network.lower()  == "mainnet"     else (168, 85, 247)

    mf = f["mn12"]
    exch_w = _tw(draw, exch_u, mf)
    sep_w  = _tw(draw, " · ", mf)
    net_w  = _tw(draw, net_u,  mf)
    total_w = exch_w + sep_w + net_w
    cx_start = (CARD_W - total_w) // 2

    # Measure height for vcenter
    bb = _textsize(draw, exch_u, mf)
    th = bb[3] - bb[1]
    ty = y + (h - th) // 2

    _text(draw, cx_start,                   ty, exch_u, mf, exch_color)
    _text(draw, cx_start + exch_w,          ty, " · ",  mf, C_TEXT_MUT)
    _text(draw, cx_start + exch_w + sep_w,  ty, net_u,  mf, net_color)

    # Timestamp — right
    ts = datetime.now().strftime("%H:%M")
    _text_vcenter_right(draw, CARD_W - PAD, y, h, ts, f["mn12"], C_TEXT_DIM)

    _divider(draw, y + h)


def _draw_symbol_row(
    draw: ImageDraw.ImageDraw,
    symbol: str,
    grid_type: str,
    state: str,
    uptime: str,
    grid_bias: str | None = None,
    leverage: int | None = None,
) -> None:
    f = _fonts()
    y = _Y_SYMBOL
    h = _H_SYMBOL

    # Symbol text
    sym_font = f["b22"]
    bb = _textsize(draw, symbol, sym_font)
    sym_h = bb[3] - bb[1]
    sym_y = y + (h - sym_h) // 2
    _text(draw, PAD, sym_y, symbol, sym_font, C_TEXT_PRI)
    sym_w = bb[2] - bb[0]

    # Type badge
    badge_x = PAD + sym_w + 10
    badge_y = y + h // 2 - 10
    badge_color = C_CYAN  if grid_type == "SPOT" else C_GOLD
    badge_bg    = C_CYAN_BG if grid_type == "SPOT" else C_GOLD_BG
    next_x = _badge(draw, badge_x, badge_y, grid_type, badge_color, badge_bg, f["b11"])

    # Perp: bias + leverage badge
    if grid_type == "PERP" and grid_bias and leverage is not None:
        if grid_bias.lower() == "long":
            bias_color, bias_bg = C_GREEN, C_GREEN_BG
        elif grid_bias.lower() == "short":
            bias_color, bias_bg = C_RED, C_RED_BG
        else:
            bias_color, bias_bg = C_CYAN, C_CYAN_BG
        _badge(draw, next_x + 8, badge_y, f"{grid_bias.upper()} {leverage}×",
               bias_color, bias_bg, f["b11"])

    # Uptime — right
    uptime_str = f"uptime  {uptime}"
    _text_vcenter_right(draw, CARD_W - PAD, y, h, uptime_str, f["r13"], C_TEXT_SEC)

    # State warning pill if not running
    if state.lower() not in ("running",):
        _badge(draw, CARD_W // 2, badge_y, state.upper(), C_GOLD, C_GOLD_BG, f["b11"])

    _divider(draw, y + h)


def _draw_pnl_hero(
    draw: ImageDraw.ImageDraw,
    total_profit: float,
    delta_roundtrips: int,
    delta_matched: float,
    delta_fees: float,
    unrealized_pnl: float | None = None,
) -> None:
    f = _fonts()
    y = _Y_PNL
    h = _H_PNL
    mid_x = CARD_W // 2

    # Left bg tinted by PnL sign
    draw.rectangle([(0, y), (mid_x - 1, y + h)], fill=_pnl_bg(total_profit))
    # Right bg — neutral dark
    draw.rectangle([(mid_x, y), (CARD_W, y + h)], fill=C_SECTION)
    _vdivider(draw, mid_x, y, h)

    # ── Left: Total PnL ──────────────────────────────────────────────────────
    label_y = y + 16
    _text(draw, PAD, label_y, "TOTAL PnL", f["r11"], C_TEXT_MUT)

    pnl_text = _signed(total_profit)
    pnl_font = f["b38"]
    pnl_color = _pnl_color(total_profit)
    pnl_y = label_y + 18
    _text(draw, PAD, pnl_y, pnl_text, pnl_font, pnl_color)

    # Unrealized PnL (perp only)
    if unrealized_pnl is not None:
        pbb = _textsize(draw, pnl_text, pnl_font)
        unreal_y = pnl_y + (pbb[3] - pbb[1]) + 6
        unreal_str = f"unrealized  {_signed(unrealized_pnl)}"
        _text(draw, PAD, unreal_y, unreal_str, f["r12"], _pnl_color(unrealized_pnl))

    # ── Right: Delta block ───────────────────────────────────────────────────
    rx = mid_x + PAD

    delta_label_y = y + 16
    _text(draw, rx, delta_label_y, "SINCE LAST UPDATE", f["r11"], C_TEXT_MUT)

    trades_text = f"+{delta_roundtrips} trades"
    trades_y = delta_label_y + 20
    _text(draw, rx, trades_y, trades_text, f["b18"], C_TEXT_PRI)

    net_earned = delta_matched - delta_fees
    earned_text = _signed(net_earned) + " earned"
    tbb = _textsize(draw, trades_text, f["b18"])
    earned_y = trades_y + (tbb[3] - tbb[1]) + 6
    _text(draw, rx, earned_y, earned_text, f["b18"], _pnl_color(net_earned))

    breakdown_text = f"matched {_signed(delta_matched)}  ·  fees ${_fp(delta_fees)}"
    ebb = _textsize(draw, earned_text, f["b18"])
    breakdown_y = earned_y + (ebb[3] - ebb[1]) + 6
    _text(draw, rx, breakdown_y, breakdown_text, f["r11"], C_TEXT_MUT)

    _divider(draw, y + h)


def _draw_three_col_row(
    draw: ImageDraw.ImageDraw,
    y: int,
    h: int,
    cells: list[tuple[str, str, tuple]],
) -> None:
    """Three equal-width metric cells: small label on top, bold value below.

    cells: list of (label, value_text, value_color)
    """
    f = _fonts()
    col_w = CARD_W // 3
    lf = f["r11"]
    vf = f["b18"]

    for i, (label, value, color) in enumerate(cells):
        x_start = i * col_w
        cx = x_start + col_w // 2

        if i > 0:
            _vdivider(draw, x_start, y, h)

        _text_centered(draw, cx, y + 14, label.upper(), lf, C_TEXT_MUT)
        _text_centered(draw, cx, y + 36, value,         vf, color)

    _divider(draw, y + h)


def _draw_grid_row(
    draw: ImageDraw.ImageDraw,
    grid_range_low: float,
    grid_range_high: float,
    grid_count: int,
    grid_spacing_pct: tuple[float, float],
) -> None:
    f = _fonts()
    y = _Y_GRID
    h = _H_GRID

    low_str   = f"${_fp(grid_range_low)}"
    high_str  = f"${_fp(grid_range_high)}"
    zones_str = f"{grid_count} zones  ·  {_format_spacing(grid_spacing_pct)}"

    mf = f["mn13"]
    zf = f["r13"]

    # "GRID RANGE" label at top
    _text(draw, PAD, y + 10, "GRID RANGE", f["r11"], C_TEXT_MUT)

    # Content row below label
    content_y = y + 28

    low_w   = _tw(draw, low_str,   mf)
    high_w  = _tw(draw, high_str,  mf)
    zones_w = _tw(draw, zones_str, zf)

    BAR_GAP = 12
    bar_x1 = PAD + low_w + BAR_GAP
    bar_x2 = CARD_W - PAD - zones_w - BAR_GAP - high_w - BAR_GAP

    # Low / High prices
    _text(draw, PAD, content_y, low_str, mf, C_TEXT_SEC)
    _text(draw, bar_x2 + BAR_GAP, content_y, high_str, mf, C_TEXT_SEC)

    # Range bar
    bb  = _textsize(draw, low_str, mf)
    bar_h = 6
    bar_y = content_y + (bb[3] - bb[1]) // 2 - bar_h // 2
    if bar_x2 > bar_x1 + 10:
        draw.rounded_rectangle([(bar_x1, bar_y), (bar_x2, bar_y + bar_h)], radius=3, fill=C_BORDER)
        draw.rounded_rectangle([(bar_x1 + 1, bar_y + 1), (bar_x2 - 1, bar_y + bar_h - 1)],
                                radius=2, fill=C_CYAN_DIM)

    # Zones info — right
    _text(draw, CARD_W - PAD - zones_w, content_y, zones_str, zf, C_TEXT_SEC)

    _divider(draw, y + h)


def _draw_footer(draw: ImageDraw.ImageDraw, state: str) -> None:
    f = _fonts()
    y = _Y_FOOTER
    h = _H_FOOTER

    dot_color = C_GREEN if state.lower() == "running" else C_GOLD
    dot_cx = PAD + 8
    dot_cy = y + h // 2
    draw.ellipse([(dot_cx - 4, dot_cy - 4), (dot_cx + 4, dot_cy + 4)], fill=dot_color)
    _text_vcenter(draw, dot_cx + 12, y, h, state.upper(), f["r12"], dot_color)


# ---------------------------------------------------------------------------
# Card builders
# ---------------------------------------------------------------------------

def _render_spot_card(
    label: str,
    exchange: str,
    network: str,
    summary: "SpotGridSummary",
    delta_roundtrips: int,
    delta_matched: float,
    delta_fees: float,
) -> Image.Image:
    img  = Image.new("RGB", (CARD_W, CARD_H), C_BG)
    draw = ImageDraw.Draw(img)

    _draw_background(img, draw)
    _draw_header(draw, label, exchange, network)
    _draw_symbol_row(draw, summary.symbol, "SPOT", summary.state, summary.uptime)
    _draw_pnl_hero(draw, summary.total_profit, delta_roundtrips, delta_matched, delta_fees)
    _draw_three_col_row(draw, _Y_ROW1, _H_ROW, [
        ("Matched Profit", _signed(summary.matched_profit),          _pnl_color(summary.matched_profit)),
        ("Fees Paid",      f"-${_fp(summary.total_fees)}",           C_RED),
        ("Roundtrips",     str(summary.roundtrips),                  C_TEXT_PRI),
    ])
    _draw_grid_row(draw, summary.grid_range_low, summary.grid_range_high,
                   summary.grid_count, summary.grid_spacing_pct)
    _draw_three_col_row(draw, _Y_ROW2, _H_ROW, [
        ("Position",      f"{summary.position_size:.4f}",            C_TEXT_PRI),
        ("Base Balance",  f"{summary.base_balance:.4f}",             C_TEXT_SEC),
        ("Quote Balance", f"${_fp(summary.quote_balance)}",          C_TEXT_SEC),
    ])
    _draw_footer(draw, summary.state)
    return img


def _render_perp_card(
    label: str,
    exchange: str,
    network: str,
    summary: "PerpGridSummary",
    delta_roundtrips: int,
    delta_matched: float,
    delta_fees: float,
) -> Image.Image:
    img  = Image.new("RGB", (CARD_W, CARD_H), C_BG)
    draw = ImageDraw.Draw(img)

    side = summary.position_side.lower()
    pos_color = C_GREEN if side == "long" else C_RED if side == "short" else C_TEXT_MUT
    pos_text = f"{summary.position_side}  {abs(summary.position_size):.4f}"

    _draw_background(img, draw)
    _draw_header(draw, label, exchange, network)
    _draw_symbol_row(draw, summary.symbol, "PERP", summary.state, summary.uptime,
                     grid_bias=summary.grid_bias, leverage=summary.leverage)
    _draw_pnl_hero(draw, summary.total_profit, delta_roundtrips, delta_matched, delta_fees,
                   unrealized_pnl=summary.unrealized_pnl)
    _draw_three_col_row(draw, _Y_ROW1, _H_ROW, [
        ("Matched Profit", _signed(summary.matched_profit),          _pnl_color(summary.matched_profit)),
        ("Fees Paid",      f"-${_fp(summary.total_fees)}",           C_RED),
        ("Roundtrips",     str(summary.roundtrips),                  C_TEXT_PRI),
    ])
    _draw_grid_row(draw, summary.grid_range_low, summary.grid_range_high,
                   summary.grid_count, summary.grid_spacing_pct)
    _draw_three_col_row(draw, _Y_ROW2, _H_ROW, [
        ("Position",       pos_text,                                 pos_color),
        ("Margin Balance", f"${_fp(summary.margin_balance)}",        C_TEXT_SEC),
        ("Avg Entry",      f"${_fp(summary.avg_entry_price)}",       C_TEXT_SEC),
    ])
    _draw_footer(draw, summary.state)
    return img


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_card_from_state(label: str, state: "BotState") -> io.BytesIO:
    """Generate a PNG report card from bot state. Returns BytesIO seeked to 0.

    Raises ValueError if state.summary is None.
    """
    from .models import PerpGridSummary, SpotGridSummary  # avoid circular import

    if state.summary is None:
        raise ValueError(f"No summary data available for {label!r}")

    delta_roundtrips = state.summary.roundtrips   - state.prev_roundtrips
    delta_matched    = state.summary.matched_profit - state.prev_matched_profit
    delta_fees       = state.summary.total_fees   - state.prev_total_fees

    exchange = state.info.exchange if state.info else "unknown"
    network  = state.info.network  if state.info else "unknown"

    if isinstance(state.summary, SpotGridSummary):
        img = _render_spot_card(
            label, exchange, network, state.summary,
            delta_roundtrips, delta_matched, delta_fees,
        )
    elif isinstance(state.summary, PerpGridSummary):
        img = _render_perp_card(
            label, exchange, network, state.summary,
            delta_roundtrips, delta_matched, delta_fees,
        )
    else:
        raise ValueError(f"Unknown summary type for {label!r}: {type(state.summary)}")

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Compact periodic card — Binance PnL-share inspired, light theme
# ---------------------------------------------------------------------------

# Light-theme palette
_L_BG        = (255, 255, 255)
_L_BORDER    = (230, 234, 240)
_L_TEXT_PRI  = (15,  23,  42)
_L_TEXT_SEC  = (80,  95,  116)
_L_TEXT_MUT  = (140, 155, 175)
_L_GREEN     = (14,  203, 129)   # Binance green
_L_GREEN_DK  = (10,  160, 100)   # darker for text on white
_L_GREEN_BG  = (225, 250, 237)
_L_RED       = (246, 70,  93)    # Binance red
_L_RED_BG    = (254, 230, 234)

_PC_W = 420
_PC_H = 240


def _lp_color(value: float) -> tuple:
    return _L_GREEN_DK if value >= 0 else _L_RED


def _lp_accent(value: float) -> tuple:
    return _L_GREEN if value >= 0 else _L_RED


def _lp_bg(value: float) -> tuple:
    return _L_GREEN_BG if value >= 0 else _L_RED_BG


_PERIODIC_FONT_CACHE: dict | None = None


def _periodic_fonts() -> dict:
    """Larger fonts for the compact card so text reads well on mobile."""
    global _PERIODIC_FONT_CACHE
    if _PERIODIC_FONT_CACHE:
        return _PERIODIC_FONT_CACHE

    bold_paths = [_UBUNTU_DIR + "Ubuntu-B.ttf", _DEJAVU_DIR + "DejaVuSans-Bold.ttf"]
    reg_paths  = [_UBUNTU_DIR + "Ubuntu-R.ttf", _DEJAVU_DIR + "DejaVuSans.ttf"]

    _PERIODIC_FONT_CACHE = {
        "hero":  _load_any(bold_paths, 48),
        "b20":   _load_any(bold_paths, 20),
        "b16":   _load_any(bold_paths, 16),
        "b13":   _load_any(bold_paths, 13),
        "r16":   _load_any(reg_paths,  16),
        "r14":   _load_any(reg_paths,  14),
        "r13":   _load_any(reg_paths,  13),
    }
    return _PERIODIC_FONT_CACHE


def _render_periodic_card(
    label: str,
    symbol: str,
    strategy_type: str,
    total_profit: float,
    roundtrips: int,
    delta_roundtrips: int,
    delta_profit: float,
    uptime: str,
) -> Image.Image:
    img = Image.new("RGB", (_PC_W, _PC_H), _L_BG)
    draw = ImageDraw.Draw(img)
    pf = _periodic_fonts()
    pad = 20

    accent = _lp_accent(total_profit)
    pnl_color = _lp_color(total_profit)

    # ── Top accent bar ──
    draw.rectangle([(0, 0), (_PC_W, 4)], fill=accent)

    # ── Row 1: symbol + badge + label ──
    y = 14
    _text(draw, pad, y, symbol, pf["b20"], _L_TEXT_PRI)
    sym_w = _tw(draw, symbol, pf["b20"])
    badge_color = _L_GREEN_DK if strategy_type.startswith("Spot") else (180, 130, 20)
    badge_bg = _L_GREEN_BG if strategy_type.startswith("Spot") else (255, 243, 210)
    _badge(draw, pad + sym_w + 8, y + 2, strategy_type.upper(), badge_color, badge_bg, pf["b13"])
    _text_right(draw, _PC_W - pad, y + 3, label, pf["r13"], _L_TEXT_MUT)

    # ── Hero PnL ──
    pnl_str = _signed(total_profit)
    pnl_y = 48
    _text_centered(draw, _PC_W // 2, pnl_y, pnl_str, pf["hero"], pnl_color)

    # ── Delta pill ──
    delta_str = f"{_signed(delta_profit)} this period"
    pill_color = _lp_color(delta_profit)
    pill_bg = _lp_bg(delta_profit)
    pill_w = _tw(draw, delta_str, pf["r13"]) + 20
    pill_x = (_PC_W - pill_w) // 2
    pill_y = 104
    _badge(draw, pill_x, pill_y, delta_str, pill_color, pill_bg, pf["r13"], h_pad=10, v_pad=4)

    # ── Divider ──
    div_y = 134
    draw.line([(pad, div_y), (_PC_W - pad, div_y)], fill=_L_BORDER, width=1)

    # ── Matched Trades row ──
    row_y = 146
    _text(draw, pad, row_y, "Matched Trades", pf["r16"], _L_TEXT_SEC)
    trades_str = str(roundtrips)
    _text_right(draw, _PC_W - pad, row_y, trades_str, pf["b20"], _L_TEXT_PRI)
    if delta_roundtrips > 0:
        dt_str = f"+{delta_roundtrips}"
        dt_w = _tw(draw, trades_str, pf["b20"])
        _text_right(draw, _PC_W - pad - dt_w - 10, row_y + 2, dt_str, pf["r14"], _L_GREEN_DK)

    # ── Uptime row ──
    row2_y = 176
    _text(draw, pad, row2_y, "Uptime", pf["r16"], _L_TEXT_SEC)
    _text_right(draw, _PC_W - pad, row2_y, uptime, pf["b16"], _L_TEXT_PRI)

    # ── Footer ──
    foot_y = 210
    draw.line([(pad, foot_y), (_PC_W - pad, foot_y)], fill=_L_BORDER, width=1)
    fy = foot_y + 9
    dot_cx = pad + 6
    dot_cy = fy + 6
    draw.ellipse([(dot_cx - 4, dot_cy - 4), (dot_cx + 4, dot_cy + 4)], fill=_L_GREEN)
    _text(draw, dot_cx + 10, fy, "LIVE", pf["b13"], _L_GREEN_DK)
    ts = datetime.now().strftime("%H:%M · %b %d")
    _text_right(draw, _PC_W - pad, fy, ts, pf["r13"], _L_TEXT_MUT)

    return img


def build_periodic_card(label: str, state: "BotState") -> io.BytesIO:
    """Generate a compact periodic PNG card focused on trades & profit.

    Returns BytesIO seeked to 0. Raises ValueError if state.summary is None.
    """
    from .models import PerpGridSummary, SpotGridSummary

    if state.summary is None:
        raise ValueError(f"No summary data available for {label!r}")

    delta_roundtrips = state.summary.roundtrips - state.prev_roundtrips
    delta_profit = (
        (state.summary.matched_profit - state.prev_matched_profit)
        - (state.summary.total_fees - state.prev_total_fees)
    )

    if isinstance(state.summary, SpotGridSummary):
        stype = "Spot Grid"
    elif isinstance(state.summary, PerpGridSummary):
        stype = "Perp Grid"
    else:
        stype = "Grid"

    img = _render_periodic_card(
        label=label,
        symbol=state.summary.symbol,
        strategy_type=stype,
        total_profit=state.summary.total_profit,
        roundtrips=state.summary.roundtrips,
        delta_roundtrips=delta_roundtrips,
        delta_profit=delta_profit,
        uptime=state.summary.uptime,
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
