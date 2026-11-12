"""gui/style.py — the Mark LVII look: type, colour mixing, shapes, button styles.

Everything visual that more than one panel needs lives here, so the HUD has
one voice instead of forty slightly different ones.

Type. No font files ship with the app, and none are downloaded: each role
names a list of families and Qt takes the first one the system has. Windows
has Bahnschrift, a DIN-style face that suits a HUD; macOS and Linux fall
through to their own sans. Numbers use a monospace so they do not jitter
while they change.

Colour. Stylesheets only ever use the palette's own hex values, because the
live re-theme (theme.retheme_all_widgets) works by replacing those exact
strings. Anything mixed or translucent is painted, and painting reads the
palette at paint time, so it re-themes for free.
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QColor, QFont, QPolygonF

from gui.theme import C

DISPLAY_FAMILIES = ["Bahnschrift", "Segoe UI", "SF Pro Display", "Helvetica Neue",
                    "Noto Sans", "DejaVu Sans"]
MONO_FAMILIES = ["Cascadia Mono", "Consolas", "SF Mono", "Menlo", "DejaVu Sans Mono",
                 "Courier New"]
DISPLAY_CSS = ("'Bahnschrift', 'Segoe UI', 'SF Pro Display', 'Helvetica Neue', "
               "'Noto Sans', 'DejaVu Sans', sans-serif")
MONO_CSS = "'Cascadia Mono', 'Consolas', 'SF Mono', 'Menlo', 'DejaVu Sans Mono', monospace"


def _apply_weight(f: QFont, weight) -> None:
    if weight is None:
        return
    try:
        if int(getattr(weight, "value", weight)) < 0:
            return
    except (TypeError, ValueError):
        return
    f.setWeight(weight)


def hud_font(size: float, weight=None, italic: bool = False) -> QFont:
    """The display face at a point size — the drop-in for the old
    QFont("Courier New", size, weight). One point larger, because Courier
    New's letters are wide and light and the same size reads bigger."""
    f = QFont()
    f.setFamilies(DISPLAY_FAMILIES)
    f.setPointSizeF(float(size) + 1.0)
    _apply_weight(f, weight)
    f.setItalic(bool(italic))
    return f


def mono_font(size: float, weight=None) -> QFont:
    """A monospace at a point size, for keys, codes and columns of figures."""
    f = QFont()
    f.setFamilies(MONO_FAMILIES)
    f.setPointSizeF(float(size))
    _apply_weight(f, weight)
    return f


def px_font(px: float, weight=QFont.Weight.Normal, mono: bool = False,
            spacing: float = 0.0) -> QFont:
    """A face at a pixel size, for painted widgets that lay text out by pixel."""
    f = QFont()
    f.setFamilies(MONO_FAMILIES if mono else DISPLAY_FAMILIES)
    f.setPixelSize(max(1, int(px)))
    _apply_weight(f, weight)
    if spacing:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, float(spacing))
    return f


_HEX_RGB_CACHE: dict[str, tuple[int, int, int]] = {}
_BLEND_CACHE: dict[tuple[int, int, int, int, int, int, int], QColor] = {}


def _parse_rgb(c) -> tuple[int, int, int]:
    """Fast RGB tuple extraction bypassing repeated QColor instantiation."""
    if isinstance(c, tuple) and len(c) == 3:
        return c
    if isinstance(c, QColor):
        return (c.red(), c.green(), c.blue())
    s = str(c).strip().lstrip("#")
    cached = _HEX_RGB_CACHE.get(s)
    if cached is not None:
        return cached
    if len(s) == 6:
        try:
            rgb = (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
        except ValueError:
            qc = QColor(c)
            rgb = (qc.red(), qc.green(), qc.blue())
    elif len(s) == 3:
        try:
            rgb = (int(s[0] * 2, 16), int(s[1] * 2, 16), int(s[2] * 2, 16))
        except ValueError:
            qc = QColor(c)
            rgb = (qc.red(), qc.green(), qc.blue())
    else:
        qc = QColor(c)
        rgb = (qc.red(), qc.green(), qc.blue())
    _HEX_RGB_CACHE[s] = rgb
    return rgb


def blend_fast(col, a: float, base=None) -> QColor:
    """High-performance pre-blended color LUT bypassing runtime QColor parsing."""
    k_int = int(round(max(0.0, min(1.0, float(a))) * 255.0))
    r1, g1, b1 = _parse_rgb(col)
    r0, g0, b0 = _parse_rgb(base if base is not None else C.BG)
    key = (r1, g1, b1, r0, g0, b0, k_int)
    cached = _BLEND_CACHE.get(key)
    if cached is not None:
        return cached

    inv_k = 255 - k_int
    r = (r0 * inv_k + r1 * k_int) // 255
    g = (g0 * inv_k + g1 * k_int) // 255
    b = (b0 * inv_k + b1 * k_int) // 255
    res = QColor(r, g, b)
    if len(_BLEND_CACHE) > 4096:
        _BLEND_CACHE.clear()
    _BLEND_CACHE[key] = res
    return res


def blend(col, a: float, base=None) -> QColor:
    """`col` mixed onto the background (or `base`) by `a` — opaque, so it is
    drawn on the raster engine's fast path."""
    return blend_fast(col, a, base)


def with_alpha(col, a: float) -> QColor:
    c = QColor(col)
    c.setAlphaF(max(0.0, min(1.0, float(a))))
    return c


def chamfer(r: QRectF, cut: float, corners=("tl", "br")) -> QPolygonF:
    """A rectangle with the named corners cut at 45° — the HUD's panel shape."""
    x0, y0, x1, y1 = r.left(), r.top(), r.right(), r.bottom()
    pts = [QPointF(x0 + cut, y0)] if "tl" in corners else [QPointF(x0, y0)]
    pts += ([QPointF(x1 - cut, y0), QPointF(x1, y0 + cut)] if "tr" in corners
            else [QPointF(x1, y0)])
    pts += ([QPointF(x1, y1 - cut), QPointF(x1 - cut, y1)] if "br" in corners
            else [QPointF(x1, y1)])
    pts += ([QPointF(x0 + cut, y1), QPointF(x0, y1 - cut)] if "bl" in corners
            else [QPointF(x0, y1)])
    if "tl" in corners:
        pts.append(QPointF(x0, y0 + cut))
    return QPolygonF(pts)


def btn_css(kind: str = "dim", align: str = "left") -> str:
    """Stylesheet for a drawer/panel button.

    kind: "primary" (the main action), "dim" (ordinary), "on" / "off" (a switch),
    "choice" (one of two equal options — neither reads as disabled)."""
    pad = "padding: 0 10px;" if align == "left" else "padding: 0 6px;"
    base = f"text-align: {align}; {pad} border-radius: 0px;"
    if kind == "primary":
        return f"""
            QPushButton {{ background: {C.PRI_GHO}; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-left: 3px solid {C.PRI}; {base} }}
            QPushButton:hover {{ border-color: {C.PRI}; color: {C.WHITE}; }}
            QPushButton:disabled {{ color: {C.TEXT_DIM}; border-color: {C.BORDER}; }}"""
    if kind == "on":
        return f"""
            QPushButton {{ background: {C.PANEL2}; color: {C.GREEN};
                border: 1px solid {C.GREEN_D}; border-left: 3px solid {C.GREEN}; {base} }}
            QPushButton:hover {{ border-color: {C.GREEN}; }}
            QPushButton:disabled {{ color: {C.TEXT_DIM}; border-color: {C.BORDER}; }}"""
    if kind == "choice":
        return f"""
            QPushButton {{ background: {C.PANEL2}; color: {C.PRI};
                border: 1px solid {C.BORDER_A}; border-left: 3px solid {C.PRI_DIM}; {base} }}
            QPushButton:hover {{ color: {C.WHITE}; border-color: {C.BORDER_B}; }}"""
    # "dim" and "off"
    return f"""
        QPushButton {{ background: {C.PANEL}; color: {C.TEXT_MED if kind == 'dim' else C.TEXT_DIM};
            border: 1px solid {C.BORDER}; border-left: 3px solid {C.BORDER_A}; {base} }}
        QPushButton:hover {{ color: {C.PRI}; border-color: {C.BORDER_B};
            border-left: 3px solid {C.PRI_DIM}; }}
        QPushButton:disabled {{ color: {C.TEXT_DIM}; border-color: {C.BORDER}; }}"""


def scroll_css() -> str:
    return f"""
        QScrollBar:vertical {{ background: transparent; width: 6px; border: none; margin: 2px 0; }}
        QScrollBar::handle:vertical {{ background: {C.BORDER_B}; min-height: 20px; }}
        QScrollBar::handle:vertical:hover {{ background: {C.PRI_DIM}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; border: none; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        QScrollBar:horizontal {{ height: 0; }}"""
