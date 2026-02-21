"""Report card image generator for Telegram updates.

Provides two card styles:
- Status card (780×dynamic, light or dark theme) for /status command
- Compact periodic card (540×340, light or dark theme) for periodic updates
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

# Blended bg tints (alpha-blended approximations on C_BG)
C_GREEN_BG  = (14,  30,  18)
C_RED_BG    = (30,  14,  14)
C_CYAN_BG   = (6,   30,  26)
C_GOLD_BG   = (32,  24,  6)

# ---------------------------------------------------------------------------
# Light theme palette — for /status card
# ---------------------------------------------------------------------------
L_BG        = (255, 255, 255)     # white background
L_SECTION   = (248, 250, 252)     # light gray sections (slate-50)
L_BORDER    = (226, 232, 240)     # light border (slate-200)
L_ACCENT    = (37,  99,  235)     # blue-600 accent
L_ACCENT_DIM = (147, 180, 236)   # blue bar fill
L_GREEN     = (22,  163, 74)     # green-600 (darker for white bg)
L_RED       = (220, 38,  38)     # red-600
L_GOLD      = (202, 138, 4)     # amber-600
L_TEXT_PRI  = (15,  23,  42)     # slate-900
L_TEXT_SEC  = (71,  85,  105)    # slate-500
L_TEXT_MUT  = (148, 163, 184)    # slate-400
L_GREEN_BG  = (240, 253, 244)   # green-50 tint
L_RED_BG    = (254, 242, 242)   # red-50 tint
L_ACCENT_BG = (239, 246, 255)   # blue-50 tint

# Light status card geometry
_LS_W = 780
_LS_PAD = 40

# ---------------------------------------------------------------------------
# Font management
# ---------------------------------------------------------------------------
# Linux font dirs
_UBUNTU_DIR = "/usr/share/fonts/truetype/ubuntu/"
_DEJAVU_DIR = "/usr/share/fonts/truetype/dejavu/"
# macOS font dirs
_MAC_SUPP_DIR = "/System/Library/Fonts/Supplemental/"
_MAC_SYS_DIR  = "/System/Library/Fonts/"

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


_STATUS_FONT_CACHE: dict | None = None


def _status_fonts() -> dict:
    """Font cache scaled for 1080px-wide light status card."""
    global _STATUS_FONT_CACHE
    if _STATUS_FONT_CACHE:
        return _STATUS_FONT_CACHE

    bold_paths = [
        _UBUNTU_DIR + "Ubuntu-B.ttf", _DEJAVU_DIR + "DejaVuSans-Bold.ttf",
        _MAC_SUPP_DIR + "Arial Bold.ttf", _MAC_SYS_DIR + "Helvetica.ttc",
    ]
    reg_paths = [
        _UBUNTU_DIR + "Ubuntu-R.ttf", _DEJAVU_DIR + "DejaVuSans.ttf",
        _MAC_SUPP_DIR + "Arial.ttf", _MAC_SYS_DIR + "Helvetica.ttc",
    ]
    mono_paths = [
        _UBUNTU_DIR + "UbuntuMono-R.ttf", _DEJAVU_DIR + "DejaVuSansMono.ttf",
        _MAC_SUPP_DIR + "Courier New.ttf",
    ]

    _STATUS_FONT_CACHE = {
        "b14": _load_any(bold_paths, 14),
        "b16": _load_any(bold_paths, 16),
        "b20": _load_any(bold_paths, 20),
        "b28": _load_any(bold_paths, 28),
        "b48": _load_any(bold_paths, 48),
        "r14": _load_any(reg_paths,  14),
        "r16": _load_any(reg_paths,  16),
        "r18": _load_any(reg_paths,  18),
        "mn14": _load_any(mono_paths, 14),
        "mn16": _load_any(mono_paths, 16),
    }
    return _STATUS_FONT_CACHE


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
        return f"{price:.3f}"
    else:
        return f"{price:.2f}"


def _signed(value: float) -> str:
    """Format value as +$X.XX or -$X.XX."""
    sign = "+" if value >= 0 else "-"
    return f"{sign}${_fp(abs(value))}"


def _format_spacing(spacing: tuple[float, float]) -> str:
    min_s, max_s = spacing
    decimals = 3 if min_s < 1.0 else 2
    diff_ratio = abs(max_s - min_s) / max(max_s, min_s) if max(max_s, min_s) > 0 else 0
    if diff_ratio < 0.01:
        return f"{min_s:.{decimals}f}%"
    return f"{min_s:.{decimals}f}%–{max_s:.{decimals}f}%"


# ---------------------------------------------------------------------------
# Compact periodic card — Binance PnL-share style, dark theme
# ---------------------------------------------------------------------------

# Binance-style dark palette
_P_BG        = (24, 26, 32)       # slightly lighter than pure black for Telegram visibility
_P_CARD_EDGE = (40, 44, 52)       # subtle card border
_P_DIVIDER   = (40, 44, 52)
_P_WHITE     = (234, 236, 239)
_P_GREY      = (148, 158, 172)    # labels — brighter for readability
_P_GREEN     = (14,  203, 129)    # Binance green
_P_RED       = (246, 70,  93)     # Binance red

# Compact canvas — tight fit for periodic content
_PC_W = 540
_PC_H = 340


def _lp_color(value: float) -> tuple:
    return _P_GREEN if value >= 0 else _P_RED


_PERIODIC_FONT_CACHE: dict | None = None


def _periodic_fonts() -> dict:
    global _PERIODIC_FONT_CACHE
    if _PERIODIC_FONT_CACHE:
        return _PERIODIC_FONT_CACHE

    bold_paths = [
        _UBUNTU_DIR + "Ubuntu-B.ttf", _DEJAVU_DIR + "DejaVuSans-Bold.ttf",
        _MAC_SUPP_DIR + "Arial Bold.ttf", _MAC_SYS_DIR + "Helvetica.ttc",
    ]
    reg_paths = [
        _UBUNTU_DIR + "Ubuntu-R.ttf", _DEJAVU_DIR + "DejaVuSans.ttf",
        _MAC_SUPP_DIR + "Arial.ttf", _MAC_SYS_DIR + "Helvetica.ttc",
    ]

    _PERIODIC_FONT_CACHE = {
        "hero":  _load_any(bold_paths, 60),
        "b34":   _load_any(bold_paths, 34),
        "b28":   _load_any(bold_paths, 28),
        "b20":   _load_any(bold_paths, 20),
        "r22":   _load_any(reg_paths,  22),
        "r18":   _load_any(reg_paths,  18),
        "r16":   _load_any(reg_paths,  16),
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
    img = Image.new("RGB", (_PC_W, _PC_H), _P_BG)
    draw = ImageDraw.Draw(img)
    pf = _periodic_fonts()
    pad = 34

    pnl_color = _lp_color(total_profit)

    # ── Subtle card border for Telegram dark mode visibility ──
    draw.rectangle([(0, 0), (_PC_W - 1, _PC_H - 1)], outline=_P_CARD_EDGE, width=2)

    # ── Symbol + Strategy type ──
    _text(draw, pad, 20, f"{symbol}  {strategy_type}", pf["b34"], _P_WHITE)
    # ── Label | Uptime ──
    _text(draw, pad, 52, f"{label}  |  {uptime}", pf["r18"], _P_GREY)

    # ── Hero profit number ──
    pnl_str = _signed(total_profit)
    _text(draw, pad, 82, pnl_str, pf["hero"], pnl_color)

    # ── Delta this period ──
    delta_str = f"{_signed(delta_profit)} this period"
    _text(draw, pad, 142, delta_str, pf["r22"], _lp_color(delta_profit))

    # ── Bottom metrics: two columns ──
    col1_x = pad
    col2_x = _PC_W // 2 + 10
    label_y = 192
    value_y = 214

    _text(draw, col1_x, label_y, "Matched Trades", pf["r18"], _P_GREY)
    trades_val = str(roundtrips)
    if delta_roundtrips > 0:
        trades_val = f"{roundtrips}  (+{delta_roundtrips})"
    _text(draw, col1_x, value_y, trades_val, pf["b28"], _P_WHITE)

    _text(draw, col2_x, label_y, "Net Earned", pf["r18"], _P_GREY)
    _text(draw, col2_x, value_y, _signed(delta_profit), pf["b28"], _lp_color(delta_profit))

    # ── Footer ──
    foot_y = _PC_H - 42
    draw.line([(pad, foot_y), (_PC_W - pad, foot_y)], fill=_P_DIVIDER, width=1)
    fy = foot_y + 12
    dot_cx = pad + 8
    dot_cy = fy + 8
    draw.ellipse([(dot_cx - 5, dot_cy - 5), (dot_cx + 5, dot_cy + 5)], fill=_P_GREEN)
    _text(draw, dot_cx + 16, fy, "LIVE", pf["b20"], _P_GREEN)
    ts = datetime.now().strftime("%H:%M  %b %d")
    _text_right(draw, _PC_W - pad, fy, ts, pf["r16"], _P_GREY)

    return img


def _render_periodic_card_light(
    label: str,
    symbol: str,
    strategy_type: str,
    total_profit: float,
    roundtrips: int,
    delta_roundtrips: int,
    delta_profit: float,
    uptime: str,
) -> Image.Image:
    """Light-theme periodic card — white/blue palette, same layout as dark."""
    img = Image.new("RGB", (_PC_W, _PC_H), L_BG)
    draw = ImageDraw.Draw(img)
    pf = _periodic_fonts()
    pad = 34

    pnl_color = _pal_pnl_color(total_profit, _LIGHT_PAL)

    # ── Top accent bar (3px blue) + subtle border ──
    draw.rectangle([(0, 0), (_PC_W, 3)], fill=L_ACCENT)
    draw.rectangle([(0, 0), (_PC_W - 1, _PC_H - 1)], outline=L_BORDER, width=2)

    # ── Symbol + Strategy type ──
    _text(draw, pad, 20, f"{symbol}  {strategy_type}", pf["b34"], L_TEXT_PRI)

    # ── Label | Uptime ──
    _text(draw, pad, 52, f"{label}  |  {uptime}", pf["r18"], L_TEXT_SEC)

    # ── Hero PnL number on tinted background ──
    hero_y = 76
    hero_h = 68
    pnl_bg = _pal_pnl_bg(total_profit, _LIGHT_PAL)
    draw.rounded_rectangle(
        [(pad - 12, hero_y), (_PC_W - pad + 12, hero_y + hero_h)],
        radius=10, fill=pnl_bg,
    )

    pnl_str = _signed(total_profit)
    bb = _textsize(draw, pnl_str, pf["hero"])
    pnl_text_h = bb[3] - bb[1]
    pnl_y = hero_y + (hero_h - pnl_text_h) // 2
    _text(draw, pad, pnl_y, pnl_str, pf["hero"], pnl_color)

    # ── Delta this period ──
    delta_str = f"{_signed(delta_profit)} this period"
    _text(draw, pad, hero_y + hero_h + 10, delta_str, pf["r22"], _pal_pnl_color(delta_profit, _LIGHT_PAL))

    # ── Bottom metrics: two columns ──
    col1_x = pad
    col2_x = _PC_W // 2 + 10
    label_y = 192
    value_y = 214

    _text(draw, col1_x, label_y, "Matched Trades", pf["r18"], L_TEXT_MUT)
    trades_val = str(roundtrips)
    if delta_roundtrips > 0:
        trades_val = f"{roundtrips}  (+{delta_roundtrips})"
    _text(draw, col1_x, value_y, trades_val, pf["b28"], L_TEXT_PRI)

    _text(draw, col2_x, label_y, "Net Earned", pf["r18"], L_TEXT_MUT)
    _text(draw, col2_x, value_y, _signed(delta_profit), pf["b28"], _pal_pnl_color(delta_profit, _LIGHT_PAL))

    # ── Footer ──
    foot_y = _PC_H - 42
    draw.line([(pad, foot_y), (_PC_W - pad, foot_y)], fill=L_BORDER, width=1)
    fy = foot_y + 12
    dot_cx = pad + 8
    dot_cy = fy + 8
    draw.ellipse([(dot_cx - 5, dot_cy - 5), (dot_cx + 5, dot_cy + 5)], fill=L_GREEN)
    _text(draw, dot_cx + 16, fy, "LIVE", pf["b20"], L_GREEN)
    ts = datetime.now().strftime("%H:%M  %b %d")
    _text_right(draw, _PC_W - pad, fy, ts, pf["r16"], L_TEXT_MUT)

    return img


def build_periodic_card(label: str, state: "BotState", theme: str = "dark") -> io.BytesIO:
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

    renderer = _render_periodic_card_light if theme == "light" else _render_periodic_card
    img = renderer(
        label=label,
        symbol=state.summary.symbol,
        strategy_type=stype,
        total_profit=state.summary.matched_profit,
        roundtrips=state.summary.roundtrips,
        delta_roundtrips=delta_roundtrips,
        delta_profit=delta_profit,
        uptime=state.summary.uptime,
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Light-theme status card — /status command
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Theme palettes for status card (shared layout, different colours)
# ---------------------------------------------------------------------------

_LIGHT_PAL = {
    "bg": L_BG, "section": L_SECTION, "border": L_BORDER,
    "accent": L_ACCENT, "accent_dim": L_ACCENT_DIM, "accent_bg": L_ACCENT_BG,
    "green": L_GREEN, "red": L_RED, "gold": L_GOLD,
    "text_pri": L_TEXT_PRI, "text_sec": L_TEXT_SEC, "text_mut": L_TEXT_MUT,
    "green_bg": L_GREEN_BG, "red_bg": L_RED_BG, "gold_bg": (255, 251, 235),
}

_DARK_PAL = {
    "bg": C_BG, "section": C_SECTION, "border": C_BORDER,
    "accent": C_CYAN, "accent_dim": C_CYAN_DIM, "accent_bg": C_CYAN_BG,
    "green": C_GREEN, "red": C_RED, "gold": C_GOLD,
    "text_pri": C_TEXT_PRI, "text_sec": C_TEXT_SEC, "text_mut": C_TEXT_MUT,
    "green_bg": C_GREEN_BG, "red_bg": C_RED_BG, "gold_bg": C_GOLD_BG,
}


def _pal_pnl_color(value: float, p: dict) -> tuple:
    return p["green"] if value >= 0 else p["red"]


def _pal_pnl_bg(value: float, p: dict) -> tuple:
    return p["green_bg"] if value >= 0 else p["red_bg"]


def _ls_divider(draw: ImageDraw.ImageDraw, y: int, p: dict) -> None:
    draw.line([(0, y), (_LS_W, y)], fill=p["border"], width=1)


def _ls_vdivider(draw: ImageDraw.ImageDraw, x: int, y: int, h: int, p: dict) -> None:
    draw.line([(x, y), (x, y + h)], fill=p["border"], width=1)


def _ls_draw_background(img: Image.Image, draw: ImageDraw.ImageDraw, h: int, p: dict) -> None:
    draw.rectangle([(0, 0), (_LS_W, h)], fill=p["bg"])
    draw.rectangle([(0, 0), (_LS_W, 4)], fill=p["accent"])


def _ls_draw_header(
    draw: ImageDraw.ImageDraw, y: int, label: str, exchange: str, network: str, p: dict,
) -> int:
    """Draw header row. Returns next Y."""
    f = _status_fonts()
    h = 64

    _text_vcenter(draw, _LS_PAD, y, h, label, f["b20"], p["text_pri"])

    mf = f["mn14"]
    exch_u = exchange.upper()
    net_u = network.upper()
    exch_color = p["accent"] if exchange.lower() == "hyperliquid" else p["gold"]
    net_color = p["green"] if network.lower() == "mainnet" else (139, 92, 246)

    exch_w = _tw(draw, exch_u, mf)
    sep_w = _tw(draw, " \u00b7 ", mf)
    net_w = _tw(draw, net_u, mf)
    total_w = exch_w + sep_w + net_w
    cx_start = (_LS_W - total_w) // 2

    bb = _textsize(draw, exch_u, mf)
    th = bb[3] - bb[1]
    ty = y + (h - th) // 2

    _text(draw, cx_start, ty, exch_u, mf, exch_color)
    _text(draw, cx_start + exch_w, ty, " \u00b7 ", mf, p["text_mut"])
    _text(draw, cx_start + exch_w + sep_w, ty, net_u, mf, net_color)

    ts = datetime.now().strftime("%H:%M")
    _text_vcenter_right(draw, _LS_W - _LS_PAD, y, h, ts, f["mn14"], p["text_mut"])

    end_y = y + h
    _ls_divider(draw, end_y, p)
    return end_y + 1


def _ls_draw_symbol_row(
    draw: ImageDraw.ImageDraw,
    y: int,
    symbol: str,
    grid_type: str,
    uptime: str,
    p: dict,
    grid_bias: str | None = None,
    leverage: int | None = None,
) -> int:
    """Draw symbol row with badges. Returns next Y."""
    f = _status_fonts()
    h = 60

    sym_font = f["b28"]
    bb = _textsize(draw, symbol, sym_font)
    sym_h = bb[3] - bb[1]
    sym_y = y + (h - sym_h) // 2
    _text(draw, _LS_PAD, sym_y, symbol, sym_font, p["text_pri"])
    sym_w = bb[2] - bb[0]

    badge_x = _LS_PAD + sym_w + 12
    badge_y = y + h // 2 - 12
    if grid_type == "SPOT":
        badge_color, badge_bg = p["accent"], p["accent_bg"]
    else:
        badge_color, badge_bg = p["gold"], p["gold_bg"]
    next_x = _badge(draw, badge_x, badge_y, grid_type, badge_color, badge_bg, f["b14"])

    if grid_type == "PERP" and grid_bias and leverage is not None:
        if grid_bias.lower() == "long":
            bias_color, bias_bg = p["green"], p["green_bg"]
        elif grid_bias.lower() == "short":
            bias_color, bias_bg = p["red"], p["red_bg"]
        else:
            bias_color, bias_bg = p["accent"], p["accent_bg"]
        _badge(draw, next_x + 8, badge_y, f"{grid_bias.upper()} {leverage}\u00d7",
               bias_color, bias_bg, f["b14"])

    uptime_str = f"uptime  {uptime}"
    _text_vcenter_right(draw, _LS_W - _LS_PAD, y, h, uptime_str, f["r16"], p["text_sec"])

    end_y = y + h
    _ls_divider(draw, end_y, p)
    return end_y + 1


def _ls_draw_pnl_section(
    draw: ImageDraw.ImageDraw,
    y: int,
    net_profit: float,
    matched_profit: float,
    total_fees: float,
    roundtrips: int,
    p: dict,
    unrealized_pnl: float | None = None,
) -> int:
    """Draw PnL section: hero number left, breakdown right. Returns next Y."""
    f = _status_fonts()
    h = 150
    mid_x = _LS_W // 2

    draw.rectangle([(0, y), (mid_x - 1, y + h)], fill=_pal_pnl_bg(net_profit, p))
    draw.rectangle([(mid_x, y), (_LS_W, y + h)], fill=p["section"])
    _ls_vdivider(draw, mid_x, y, h, p)

    label_y = y + 24
    _text(draw, _LS_PAD, label_y, "NET PROFIT", f["r14"], p["text_mut"])

    pnl_text = _signed(net_profit)
    pnl_font = f["b48"]
    pnl_y = label_y + 26
    _text(draw, _LS_PAD, pnl_y, pnl_text, pnl_font, _pal_pnl_color(net_profit, p))

    if unrealized_pnl is not None:
        pbb = _textsize(draw, pnl_text, pnl_font)
        unreal_y = pnl_y + (pbb[3] - pbb[1]) + 10
        unreal_str = f"unrealized  {_signed(unrealized_pnl)}"
        _text(draw, _LS_PAD, unreal_y, unreal_str, f["r14"], _pal_pnl_color(unrealized_pnl, p))

    rx = mid_x + _LS_PAD
    row_y = y + 24
    row_gap = 32

    if unrealized_pnl is not None:
        _text(draw, rx, row_y, "REALIZED", f["r14"], p["text_mut"])
        _text_right(draw, _LS_W - _LS_PAD, row_y, _signed(matched_profit), f["b16"], _pal_pnl_color(matched_profit, p))
        row_y += row_gap
        _text(draw, rx, row_y, "UNREALIZED", f["r14"], p["text_mut"])
        _text_right(draw, _LS_W - _LS_PAD, row_y, _signed(unrealized_pnl), f["b16"], _pal_pnl_color(unrealized_pnl, p))
    else:
        _text(draw, rx, row_y, "MATCHED", f["r14"], p["text_mut"])
        _text_right(draw, _LS_W - _LS_PAD, row_y, _signed(matched_profit), f["b16"], _pal_pnl_color(matched_profit, p))

    row_y += row_gap
    _text(draw, rx, row_y, "FEES", f["r14"], p["text_mut"])
    _text_right(draw, _LS_W - _LS_PAD, row_y, f"-${_fp(total_fees)}", f["b16"], p["red"])

    row_y += row_gap
    _text(draw, rx, row_y, "TRADES", f["r14"], p["text_mut"])
    _text_right(draw, _LS_W - _LS_PAD, row_y, str(roundtrips), f["b16"], p["text_pri"])

    end_y = y + h
    _ls_divider(draw, end_y, p)
    return end_y + 1


def _ls_draw_metric_row(
    draw: ImageDraw.ImageDraw,
    y: int,
    cells: list[tuple[str, str, tuple]],
    p: dict,
) -> int:
    """Three equal-width metric cells: label on top, bold value below. Returns next Y."""
    f = _status_fonts()
    h = 96
    col_w = _LS_W // 3

    for i, (label, value, color) in enumerate(cells):
        x_start = i * col_w
        cx = x_start + col_w // 2

        if i > 0:
            _ls_vdivider(draw, x_start, y, h, p)

        _text_centered(draw, cx, y + 20, label.upper(), f["r14"], p["text_mut"])
        _text_centered(draw, cx, y + 48, value, f["b20"], color)

    end_y = y + h
    _ls_divider(draw, end_y, p)
    return end_y + 1


def _ls_draw_grid_section(
    draw: ImageDraw.ImageDraw,
    y: int,
    grid_range_low: float,
    grid_range_high: float,
    grid_count: int,
    grid_spacing_pct: tuple[float, float],
    trigger: float | None,
    investment: float,
    p: dict,
) -> int:
    """Draw grid range bar + zones/spacing + trigger + investment. Returns next Y."""
    f = _status_fonts()
    h = 112

    draw.rectangle([(0, y), (_LS_W, y + h)], fill=p["section"])

    _text(draw, _LS_PAD, y + 16, "GRID RANGE", f["r14"], p["text_mut"])

    mf = f["mn16"]
    zf = f["r16"]
    content_y = y + 42

    low_str = f"${_fp(grid_range_low)}"
    high_str = f"${_fp(grid_range_high)}"
    zones_str = f"{grid_count} zones \u00b7 {_format_spacing(grid_spacing_pct)}"

    low_w = _tw(draw, low_str, mf)
    high_w = _tw(draw, high_str, mf)
    zones_w = _tw(draw, zones_str, zf)

    BAR_GAP = 14
    bar_x1 = _LS_PAD + low_w + BAR_GAP
    bar_x2 = _LS_W - _LS_PAD - zones_w - BAR_GAP - high_w - BAR_GAP

    _text(draw, _LS_PAD, content_y, low_str, mf, p["text_sec"])
    _text(draw, bar_x2 + BAR_GAP, content_y, high_str, mf, p["text_sec"])

    bb = _textsize(draw, low_str, mf)
    bar_h = 8
    bar_y = content_y + (bb[3] - bb[1]) // 2 - bar_h // 2
    if bar_x2 > bar_x1 + 10:
        draw.rounded_rectangle([(bar_x1, bar_y), (bar_x2, bar_y + bar_h)],
                                radius=4, fill=p["border"])
        draw.rounded_rectangle([(bar_x1 + 1, bar_y + 1), (bar_x2 - 1, bar_y + bar_h - 1)],
                                radius=3, fill=p["accent_dim"])

    _text(draw, _LS_W - _LS_PAD - zones_w, content_y, zones_str, zf, p["text_sec"])

    bottom_y = content_y + 30
    trigger_str = f"Trigger: ${_fp(trigger)}" if trigger is not None else "Trigger: \u2014"
    invest_str = f"Investment: ${_fp(investment)}"
    _text(draw, _LS_PAD, bottom_y, trigger_str, f["r14"], p["text_sec"])
    _text_right(draw, _LS_W - _LS_PAD, bottom_y, invest_str, f["r14"], p["text_sec"])

    end_y = y + h
    _ls_divider(draw, end_y, p)
    return end_y + 1


def _ls_draw_footer(draw: ImageDraw.ImageDraw, y: int, state: str, p: dict) -> int:
    """Draw footer with status dot + state label + date. Returns next Y."""
    f = _status_fonts()
    h = 52

    dot_color = p["green"] if state.lower() == "running" else p["gold"]
    dot_cx = _LS_PAD + 8
    dot_cy = y + h // 2
    draw.ellipse([(dot_cx - 5, dot_cy - 5), (dot_cx + 5, dot_cy + 5)], fill=dot_color)
    _text_vcenter(draw, dot_cx + 14, y, h, state.upper(), f["r16"], dot_color)

    ts = datetime.now().strftime("%b %d")
    _text_vcenter_right(draw, _LS_W - _LS_PAD, y, h, ts, f["r14"], p["text_mut"])

    return y + h


# ---------------------------------------------------------------------------
# Status card builders (shared layout, theme-driven palette)
# ---------------------------------------------------------------------------

def _render_spot_status_card(
    label: str,
    exchange: str,
    network: str,
    summary: "SpotGridSummary",
    trigger: float | None,
    investment: float,
    p: dict,
) -> Image.Image:
    max_h = 900
    img = Image.new("RGB", (_LS_W, max_h), p["bg"])
    draw = ImageDraw.Draw(img)

    _ls_draw_background(img, draw, max_h, p)

    y = 4
    y = _ls_draw_header(draw, y, label, exchange, network, p)
    y = _ls_draw_symbol_row(draw, y, summary.symbol, "SPOT", summary.uptime, p)

    net_profit = summary.total_profit
    y = _ls_draw_pnl_section(
        draw, y, net_profit, summary.matched_profit,
        summary.total_fees, summary.roundtrips, p,
    )

    entry_str = f"${_fp(summary.initial_entry_price)}" if summary.initial_entry_price else "\u2014"
    y = _ls_draw_metric_row(draw, y, [
        ("Base Balance", f"{summary.base_balance:.4f}", p["text_pri"]),
        ("Quote Balance", f"${_fp(summary.quote_balance)}", p["text_sec"]),
        ("Entry Price", entry_str, p["text_sec"]),
    ], p)

    y = _ls_draw_grid_section(
        draw, y, summary.grid_range_low, summary.grid_range_high,
        summary.grid_count, summary.grid_spacing_pct, trigger, investment, p,
    )

    y = _ls_draw_footer(draw, y, summary.state, p)

    return img.crop((0, 0, _LS_W, y))


def _render_perp_status_card(
    label: str,
    exchange: str,
    network: str,
    summary: "PerpGridSummary",
    trigger: float | None,
    investment: float,
    is_isolated: bool,
    p: dict,
) -> Image.Image:
    max_h = 900
    img = Image.new("RGB", (_LS_W, max_h), p["bg"])
    draw = ImageDraw.Draw(img)

    _ls_draw_background(img, draw, max_h, p)

    y = 4
    y = _ls_draw_header(draw, y, label, exchange, network, p)
    y = _ls_draw_symbol_row(
        draw, y, summary.symbol, "PERP", summary.uptime, p,
        grid_bias=summary.grid_bias, leverage=summary.leverage,
    )

    net_profit = summary.matched_profit + summary.unrealized_pnl - summary.total_fees
    y = _ls_draw_pnl_section(
        draw, y, net_profit, summary.matched_profit,
        summary.total_fees, summary.roundtrips, p,
        unrealized_pnl=summary.unrealized_pnl,
    )

    side = summary.position_side.lower()
    pos_color = p["green"] if side == "long" else p["red"] if side == "short" else p["text_mut"]
    pos_text = f"{summary.position_side}  {abs(summary.position_size):.4f}"
    margin_mode = "isolated" if is_isolated else "cross"

    y = _ls_draw_metric_row(draw, y, [
        ("Position", pos_text, pos_color),
        ("Margin Balance", f"${_fp(summary.margin_balance)}", p["text_sec"]),
        ("Avg Entry", f"${_fp(summary.avg_entry_price)}", p["text_sec"]),
    ], p)

    f = _status_fonts()
    mode_h = 36
    _text_vcenter(draw, _LS_PAD, y, mode_h, f"Margin: {margin_mode}", f["r14"], p["text_mut"])
    _ls_divider(draw, y + mode_h, p)
    y = y + mode_h + 1

    y = _ls_draw_grid_section(
        draw, y, summary.grid_range_low, summary.grid_range_high,
        summary.grid_count, summary.grid_spacing_pct, trigger, investment, p,
    )

    y = _ls_draw_footer(draw, y, summary.state, p)

    return img.crop((0, 0, _LS_W, y))


def build_status_card(label: str, state: "BotState", theme: str = "light") -> io.BytesIO:
    """Generate a PNG status card from bot state.

    theme="light" uses white/blue palette; theme="dark" uses dark palette.
    Both share the same layout. Returns BytesIO seeked to 0.
    Raises ValueError if state.summary is None.
    """
    from .models import PerpGridSummary, SpotGridSummary

    if state.summary is None:
        raise ValueError(f"No summary data available for {label!r}")

    p = _DARK_PAL if theme == "dark" else _LIGHT_PAL

    exchange = state.info.exchange if state.info else "unknown"
    network = state.info.network if state.info else "unknown"

    trigger = state.config.trigger_price if state.config else None
    investment = state.config.total_investment if state.config else 0.0

    if isinstance(state.summary, SpotGridSummary):
        img = _render_spot_status_card(
            label, exchange, network, state.summary, trigger, investment, p,
        )
    elif isinstance(state.summary, PerpGridSummary):
        is_isolated = state.config.is_isolated if state.config else False
        img = _render_perp_status_card(
            label, exchange, network, state.summary,
            trigger, investment, is_isolated, p,
        )
    else:
        raise ValueError(f"Unknown summary type for {label!r}: {type(state.summary)}")

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
