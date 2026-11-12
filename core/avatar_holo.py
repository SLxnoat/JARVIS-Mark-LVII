"""
Hologram furniture around the dotted head: horizontal data streams, drifting
particles, rotating telemetry orbits, calibration brackets and the dotted
projection ring under the chin.

Everything here is drawn with QPainter and numpy — no OpenGL — and takes its
colours as arguments on every paint, so the whole hologram retints live when the
theme wheel changes `C.PRI` / `C.ACC`.

Lengths are in head half-heights (`r`), so the furniture scales with the head
and the HUD only has to ask for `TOP` / `BOT` to lay it out.
"""
from __future__ import annotations

import math

import numpy as np
from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QLinearGradient, QBrush, QPainter, QPen, QPolygonF

# How far the furniture reaches above the crown and below the chin, in `r`.
TOP = 1.15
BOT = 1.15

# Base projection ring: centre below the head centre, ellipse flattening.
_RING_Y = 1.30
_RING_FLAT = 0.20


def _c(col: QColor, a: float) -> QColor:
    q = QColor(col)
    q.setAlpha(int(max(0.0, min(255.0, a))))
    return q


def poly(xs, ys) -> QPolygonF:
    """QPolygonF from two float arrays."""
    return QPolygonF([QPointF(float(x), float(y)) for x, y in zip(xs, ys)])


def draw_dots(p: QPainter, xs, ys, size, alpha, col: QColor,
              levels: int = 5, size_bins: int = 3, glow: float = 0.0) -> None:
    """Batched additive dots. `size` is px, `alpha` 0..1, both per-dot arrays or
    scalars. Dots are bucketed by (size, alpha) so each bucket is one
    `drawPoints` call, which is what keeps ten thousand dots inside a frame."""
    xs = np.asarray(xs, dtype=np.float64)
    ys = np.asarray(ys, dtype=np.float64)
    n = xs.shape[0]
    if n == 0:
        return
    size = np.broadcast_to(np.asarray(size, dtype=np.float64), (n,))
    alpha = np.broadcast_to(np.asarray(alpha, dtype=np.float64), (n,))
    keep = np.flatnonzero(alpha > 0.035)
    if keep.size == 0:
        return
    xs, ys, size, alpha = xs[keep], ys[keep], size[keep], alpha[keep]

    ab = np.minimum((alpha * levels).astype(np.int32), levels - 1)
    smin, smax = float(size.min()), float(size.max())
    if smax - smin < 1e-6:
        sb = np.zeros(size.shape, dtype=np.int32)
    else:
        sb = np.minimum(((size - smin) / (smax - smin) * size_bins).astype(np.int32),
                        size_bins - 1)
    key = sb * levels + ab
    order = np.argsort(key, kind="stable")
    key = key[order]
    bounds = np.searchsorted(key, np.arange(levels * size_bins + 1))
    xs, ys, size = xs[order], ys[order], size[order]

    pen = QPen()
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    for k in range(levels * size_bins):
        lo, hi = int(bounds[k]), int(bounds[k + 1])
        if hi <= lo:
            continue
        a_lvl = (k % levels + 0.5) / levels
        w = float(size[lo:hi].mean())
        pg = poly(xs[lo:hi], ys[lo:hi])
        if glow > 0.0 and a_lvl > 0.45:
            pen.setWidthF(w * 3.1)
            pen.setColor(_c(col, 255.0 * a_lvl * glow))
            p.setPen(pen)
            p.drawPoints(pg)
        pen.setWidthF(max(0.9, w))
        pen.setColor(_c(col, 255.0 * min(1.0, a_lvl * 1.25)))
        p.setPen(pen)
        p.drawPoints(pg)


def resample(xs, ys, n: int, closed: bool = False):
    """`n` points evenly spaced along a polyline (screen space)."""
    xs = np.asarray(xs, dtype=np.float64)
    ys = np.asarray(ys, dtype=np.float64)
    if closed:
        xs = np.append(xs, xs[0])
        ys = np.append(ys, ys[0])
    seg = np.hypot(np.diff(xs), np.diff(ys))
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    total = cum[-1]
    if total < 1e-6:
        return np.full(n, xs[0]), np.full(n, ys[0])
    t = np.linspace(0.0, total, n, endpoint=not closed)
    return np.interp(t, cum, xs), np.interp(t, cum, ys)


class HoloFx:
    """State and drawing for everything around the head."""

    N_PART = 150

    def __init__(self) -> None:
        rng = np.random.default_rng(23)
        self._rng = rng
        self.phase = 0.0                  # integrated, never absolute time
        self._t = 0.0
        self._level = 0.0                 # smoothed energy 0..1

        # Particles live in head units: x, y, velocity, life 0..1 (1 = just born).
        n = self.N_PART
        self._side = rng.choice([-1.0, 1.0], n)
        self._px = self._side * rng.uniform(0.85, 2.6, n)
        self._py = rng.uniform(-0.60, 0.55, n)
        self._pv = rng.uniform(0.04, 0.20, n)
        self._pvy = rng.uniform(-0.025, 0.025, n)
        self._life = rng.uniform(0.0, 1.0, n)
        self._rate = rng.uniform(0.10, 0.32, n)
        self._psize = rng.uniform(0.8, 2.3, n)

        # Streams: fixed layout per side, so a stream is the same stream every frame.
        m = 12
        self._sy = np.linspace(-0.46, 0.46, m)
        self._s_len = rng.uniform(1.25, 2.6, m)
        self._s_speed = rng.uniform(0.18, 0.55, m)
        self._s_off = rng.random((2, m, 3))
        self._s_node = rng.random(m) < 0.4

    # ── animation ───────────────────────────────────────────────────────────
    def step(self, dt: float, amp: float, speaking: bool, muted: bool,
             asleep: bool) -> None:
        dt = max(0.001, min(0.10, dt))
        self._t += dt
        # Calmer when asleep or muted, livelier with the voice. The rate is
        # integrated so a state change never jumps the pattern.
        target = 0.10 if (asleep or muted) else (0.35 + 0.65 * amp if speaking
                                                 else 0.30 + 0.5 * amp)
        self._level += (target - self._level) * min(1.0, dt * 6.0)
        self.phase += dt * (0.35 + 1.6 * self._level)

        boost = 1.0 + 2.2 * self._level
        self._px += self._side * self._pv * boost * dt
        self._py += self._pvy * dt
        self._life -= self._rate * dt * (1.0 + 0.6 * self._level)
        dead = np.flatnonzero((self._life <= 0.0) | (np.abs(self._px) > 3.4))
        if dead.size:
            rng = self._rng
            self._life[dead] = rng.uniform(0.7, 1.0, dead.size)
            self._px[dead] = self._side[dead] * rng.uniform(0.75, 1.15, dead.size)
            self._py[dead] = rng.uniform(-0.62, 0.55, dead.size)

    # ── helpers ─────────────────────────────────────────────────────────────
    def _ellipse(self, cx, cy, rx, ry, tilt, n, phase=0.0, only=None):
        a = np.linspace(0.0, 2.0 * math.pi, n, endpoint=False) + phase
        ex, ey = np.cos(a) * rx, np.sin(a) * ry
        ct, st = math.cos(tilt), math.sin(tilt)
        x = cx + ex * ct - ey * st
        y = cy + ex * st + ey * ct
        depth = np.sin(a)                         # >0 = near the viewer
        if only == "back":
            m = depth < 0
        elif only == "front":
            m = depth >= 0
        else:
            m = np.ones(n, dtype=bool)
        return x[m], y[m], a[m], depth[m]

    # ── behind the head ─────────────────────────────────────────────────────
    def paint_back(self, p: QPainter, cx: float, cy: float, r: float,
                   half_w: float, primary: QColor, accent: QColor,
                   amp: float) -> None:
        p.save()
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._paint_streams(p, cx, cy, r, half_w, primary, accent)
        p.restore()

    # ── in front of the head ────────────────────────────────────────────────
    def paint_front(self, p: QPainter, cx: float, cy: float, r: float,
                    half_w: float, primary: QColor, accent: QColor,
                    amp: float) -> None:
        p.save()
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._paint_brackets(p, cx, cy, r, primary)
        p.restore()

    # ── streams ─────────────────────────────────────────────────────────────
    def _paint_streams(self, p, cx, cy, r, half_w, primary, accent):
        lvl = self._level
        reach_max = max(r, half_w - 10.0)
        pen = QPen()
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)

        # A bright band across the eyes: the glow the reference spills sideways.
        for sgn in (-1.0, 1.0):
            x0 = cx + sgn * r * 0.55
            x1 = cx + sgn * min(reach_max, r * 2.4)
            g = QLinearGradient(x0, 0.0, x1, 0.0)
            g.setColorAt(0.0, _c(accent, 55 + 70 * lvl))
            g.setColorAt(0.55, _c(primary, 22 + 30 * lvl))
            g.setColorAt(1.0, _c(primary, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(g))
            h = r * (0.020 + 0.012 * lvl)
            p.drawRect(QRectF(min(x0, x1), cy - h, abs(x1 - x0), 2.0 * h))

        dash: dict[int, list] = {}
        for si, sgn in enumerate((-1.0, 1.0)):
            for i, y in enumerate(self._sy):
                yy = cy + y * r
                x0 = cx + sgn * r * (0.78 + 0.05 * math.sin(i))
                x1 = cx + sgn * min(reach_max, r * self._s_len[i] + r * 0.4)
                weight = 1.0 - abs(y) / 0.55            # centre lines are brighter
                g = QLinearGradient(x0, 0.0, x1, 0.0)
                g.setColorAt(0.0, _c(primary, (26 + 52 * lvl) * (0.5 + weight)))
                g.setColorAt(1.0, _c(primary, 0))
                pen.setBrush(QBrush(g))
                pen.setWidthF(1.0)
                p.setPen(pen)
                p.drawLine(QLineF(x0, yy, x1, yy))

                span = x1 - x0
                for k in range(3):                      # travelling dashes
                    t = (self.phase * self._s_speed[i] + self._s_off[si, i, k]) % 1.0
                    xa = x0 + span * t
                    ln = abs(span) * 0.07
                    a = (1.0 - t) ** 1.3 * (0.35 + 0.65 * weight) * (0.55 + 0.6 * lvl)
                    b = min(3, int(a * 4.0))
                    dash.setdefault(b, []).append(
                        QLineF(xa, yy, xa + math.copysign(ln, span), yy))
                if self._s_node[i]:
                    dash.setdefault(2, []).append(QLineF(x1, yy, x1 + sgn * 1.2, yy))

        pen.setBrush(QBrush(Qt.GlobalColor.white))
        pen.setWidthF(1.6)
        for b, lines in dash.items():
            pen.setColor(_c(accent if b >= 2 else primary, 255.0 * (b + 1) / 4.0))
            p.setPen(pen)
            p.drawLines(lines)

    # ── orbits ──────────────────────────────────────────────────────────────
    _ORBITS = (
        # rx,   ry,   tilt°, spin, dots, size
        (1.34, 0.30, -9.0, 0.55, 150, 1.3),
        (1.12, 0.22, 7.0, -0.80, 120, 1.2),
        (1.50, 0.40, 13.0, 0.30, 180, 1.1),
    )

    def _paint_orbits(self, p, cx, cy, r, half_w, primary, accent, half):
        ocy = cy + 0.10 * r
        for oi, (rx, ry, tilt, spin, n, sz) in enumerate(self._ORBITS):
            rx_px = min(rx * r, half_w - 8.0)
            scale = rx_px / (rx * r)
            ph = self.phase * spin
            x, y, a, depth = self._ellipse(cx, ocy, rx_px, ry * r * scale,
                                           math.radians(tilt), n, 0.0, half)
            # A bright rotating arc; the rest of the orbit is a faint dotted track.
            arc = np.maximum(0.0, np.cos(a - ph)) ** 7
            near = 0.55 + 0.45 * depth
            alpha = (0.14 + 0.86 * arc) * near * (0.45 + 0.4 * self._level)
            draw_dots(p, x, y, sz * (0.9 + 0.5 * arc), alpha, primary,
                      levels=4, size_bins=2, glow=0.35)
            if half == "front" or oi == 0:
                # Telemetry node riding the orbit.
                na = np.array([ph, ph + math.pi * 0.66 * (1 if spin > 0 else -1)])
                ex = np.cos(na) * rx_px
                ey = np.sin(na) * ry * r * scale
                ct, st = math.cos(math.radians(tilt)), math.sin(math.radians(tilt))
                nx = cx + ex * ct - ey * st
                ny = ocy + ex * st + ey * ct
                keep = (np.sin(na) >= 0) if half == "front" else (np.sin(na) < 0)
                if keep.any():
                    draw_dots(p, nx[keep], ny[keep], 3.6, 0.95, accent,
                              levels=2, size_bins=1, glow=0.5)

    # ── calibration brackets ────────────────────────────────────────────────
    def _paint_brackets(self, p, cx, cy, r, primary):
        hw, top, bot = 1.05 * r, 1.10 * r, 1.08 * r
        ln = 0.16 * r
        a = 160 + 75 * self._level
        pen = QPen(_c(primary, a), 1.5)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        p.setPen(pen)
        lines = []
        for sx in (-1.0, 1.0):
            for yy, sy in ((cy - top, 1.0), (cy + bot, -1.0)):
                x = cx + sx * hw
                lines.append(QLineF(x, yy, x, yy + sy * ln))
                lines.append(QLineF(x, yy, x - sx * ln, yy))
            # Elevation scale ladder ticks along the sides
            for step in (-0.6, -0.3, 0.0, 0.3, 0.6):
                tick_y = cy + step * r
                tick_len = (0.05 if step == 0.0 else 0.03) * r
                lines.append(QLineF(cx + sx * hw, tick_y, cx + sx * (hw - tick_len), tick_y))
        p.drawLines(lines)
        # crosshair ticks above and below the head
        pen.setColor(_c(primary, a * 0.75))
        p.setPen(pen)
        p.drawLine(QLineF(cx, cy - top, cx, cy - top + 0.07 * r))
        p.drawLine(QLineF(cx, cy + bot, cx, cy + bot - 0.07 * r))

    # ── base projection ring (retained for backward compatibility) ──────────
    def _paint_ring(self, p, cx, cy, r, primary, accent, half):
        pass

    # ── particles ───────────────────────────────────────────────────────────
    def _paint_particles(self, p, cx, cy, r, half_w, primary, accent):
        # REMOVED: Fancy particles and sparkles eliminated for professional Jarvis face matrix.
        pass
