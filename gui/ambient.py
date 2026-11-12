"""gui/ambient.py — State-driven ambient lighting and AI visualization engine.

Engineered specifically for an AI assistant UI:
- State-reactive ambient illumination: soft breathing aura, dynamic floor horizon spill,
  and chamfered perimeter frame reflections that adapt smoothly to AI cognitive states
  (STANDBY, LISTENING, THINKING, SPEAKING, MUTED, ERROR).
- Studio-grade AI audio spectrum & cognitive flow visualizer: 48-band harmonic spectrum
  with physics-based ballistic decay, peak needles, mirrored glass floor reflections,
  and dedicated modes for speech articulation, microphone listening, and neural flow.
- Minimal aerospace telemetry arcs: crisp, low-noise orbital reticles with degree
  graduations and state data.

Zero external dependencies beyond PyQt6 and standard library math/time.
"""
from __future__ import annotations

import math
import random
import time
from typing import Sequence

from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient,
)

from gui.theme import C, qcol
from gui.style import blend, chamfer, px_font, with_alpha


class AmbientLighting:
    """Dynamic ambient lighting model reflecting AI cognition and voice states.

    Smoothly interpolates color, radiant bloom, and horizon illumination
    to ground the holographic interface with natural cinematic depth.
    """

    def __init__(self) -> None:
        self._curr_r = 0.0
        self._curr_g = 212.0
        self._curr_b = 255.0
        self._curr_intensity = 0.12
        self._curr_radius_scale = 1.0

        self._target_r = 0.0
        self._target_g = 212.0
        self._target_b = 255.0
        self._target_intensity = 0.12
        self._target_radius_scale = 1.0

        self._phase = 0.0
        self._shimmer = 0.0
        self._last_t = time.time()

    def step(self, dt: float, state: str, speaking: bool, muted: bool, amp: float) -> None:
        """Advance ambient light dynamics by dt seconds."""
        dt = max(0.001, min(0.1, dt))
        self._phase += dt

        # Resolve state color and lighting characteristics
        st = (state or "").upper()
        if muted:
            tc = qcol(C.MUTED_C)
            tgt_int = 0.06
            tgt_rad = 0.90
            phase_speed = 0.6
        elif speaking:
            # Warm acoustic radiance coupling primary cyan with orange accent
            tc = qcol(C.ACC) if amp > 0.15 else qcol(C.PRI)
            tgt_int = 0.22 + min(0.28, amp * 0.45)
            tgt_rad = 1.15 + min(0.35, amp * 0.50)
            phase_speed = 2.4
        elif st in ("THINKING", "PROCESSING"):
            # Amber / neural golden-cyan hue with active cognitive tide
            tc = qcol(C.ACC2)
            tgt_int = 0.18 + 0.06 * math.sin(self._phase * 3.0)
            tgt_rad = 1.08 + 0.08 * math.cos(self._phase * 2.5)
            phase_speed = 3.2
        elif st == "LISTENING":
            # Receptive emerald / mint glow dilating with microphone activity
            tc = qcol(C.GREEN)
            tgt_int = 0.16 + min(0.20, amp * 0.6)
            tgt_rad = 1.05 + min(0.25, amp * 0.4)
            phase_speed = 1.8
        elif st in ("ERROR", "FAILED"):
            tc = qcol(C.RED)
            tgt_int = 0.18
            tgt_rad = 1.0
            phase_speed = 1.0
        else:
            # Standby / Idle: deep, tranquil cyan breathing
            tc = qcol(C.PRI)
            breathe = 0.5 + 0.5 * math.sin(self._phase * 0.9)
            tgt_int = 0.10 + 0.05 * breathe
            tgt_rad = 0.98 + 0.06 * breathe
            phase_speed = 0.9

        self._target_r = float(tc.red())
        self._target_g = float(tc.green())
        self._target_b = float(tc.blue())
        self._target_intensity = tgt_int
        self._target_radius_scale = tgt_rad

        # Smooth exponential easing
        k = 1.0 - math.exp(-6.5 * dt)
        self._curr_r += (self._target_r - self._curr_r) * k
        self._curr_g += (self._target_g - self._curr_g) * k
        self._curr_b += (self._target_b - self._curr_b) * k
        self._curr_intensity += (self._target_intensity - self._curr_intensity) * k
        self._curr_radius_scale += (self._target_radius_scale - self._curr_radius_scale) * k
        self._shimmer += dt * phase_speed

    @property
    def current_color(self) -> QColor:
        return QColor(int(self._curr_r), int(self._curr_g), int(self._curr_b))

    def paint_aura(self, p: QPainter, cx: float, cy: float, base_r: float) -> None:
        """Paint soft volumetric ambient radiance behind the avatar/core."""
        rad = base_r * 1.75 * self._curr_radius_scale
        if rad <= 2.0:
            return

        col = self.current_color
        intensity = self._curr_intensity

        g = QRadialGradient(cx, cy, rad)
        g.setColorAt(0.0, with_alpha(col, intensity * 0.85))
        g.setColorAt(0.28, with_alpha(col, intensity * 0.45))
        g.setColorAt(0.65, with_alpha(col, intensity * 0.12))
        g.setColorAt(1.0, with_alpha(col, 0.0))

        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(cx, cy), rad, rad)
        p.restore()

    def paint_horizon_glow(self, p: QPainter, W: float, H: float, hy: float) -> None:
        """Paint atmospheric ambient floor illumination and horizon light spill."""
        col = self.current_color
        intensity = self._curr_intensity

        # Soft vertical spread along horizon
        spread = 28.0 * self._curr_radius_scale
        vg = QLinearGradient(0, hy - spread, 0, hy + spread * 1.5)
        vg.setColorAt(0.0, with_alpha(col, 0.0))
        vg.setColorAt(0.38, with_alpha(col, intensity * 0.40))
        vg.setColorAt(0.50, with_alpha(col, intensity * 0.75))
        vg.setColorAt(0.65, with_alpha(col, intensity * 0.35))
        vg.setColorAt(1.0, with_alpha(col, 0.0))

        p.save()
        p.fillRect(QRectF(0, hy - spread, W, spread * 2.5), QBrush(vg))

        # Precision lit horizon line
        hg = QLinearGradient(0, hy, W, hy)
        hg.setColorAt(0.0, with_alpha(col, 0.0))
        hg.setColorAt(0.25, with_alpha(col, intensity * 0.50))
        hg.setColorAt(0.50, with_alpha(C.WHITE, intensity * 0.90))
        hg.setColorAt(0.75, with_alpha(col, intensity * 0.50))
        hg.setColorAt(1.0, with_alpha(col, 0.0))

        p.setPen(QPen(QBrush(hg), 1.2))
        p.drawLine(QLineF(0, hy, W, hy))
        p.restore()

    def paint_edge_illumination(self, p: QPainter, W: float, H: float) -> None:
        """Subtle ambient edge lighting along the HUD perimeter frame."""
        col = self.current_color
        intensity = self._curr_intensity
        m, cut, arm = 6, 16, 46

        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Gentle ambient border pulse
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(with_alpha(col, 0.15 + intensity * 0.35), 1.0))
        p.drawPolygon(chamfer(QRectF(m, m, W - 2 * m, H - 2 * m), cut, ("tl", "tr", "br", "bl")))

        # Lit corner brackets catching ambient light
        corner_pen = QPen(with_alpha(col, 0.45 + intensity * 0.55), 1.8)
        p.setPen(corner_pen)
        for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            x0 = m if sx > 0 else W - m
            y0 = m if sy > 0 else H - m
            p.drawLine(QLineF(x0, y0 + sy * (cut + arm), x0, y0 + sy * cut))
            p.drawLine(QLineF(x0, y0 + sy * cut, x0 + sx * cut, y0))

        p.restore()


class AIWaveformVisualizer:
    """Studio-grade 48-band harmonic spectrum analyzer & cognitive wave visualizer.

    Features:
    - Audio-reactive harmonic spectrum with ballistic envelope (instant attack, gravity decay).
    - Peak hold needles for audio clarity and fidelity.
    - Smooth mirrored studio glass reflection with vertical gradient falloff.
    - Specialized visualization modes:
        * SPEAKING: Vocal spectrum with harmonic formant distribution.
        * LISTENING: Fine microphone sensitivity wave in reactive emerald.
        * THINKING / PROCESSING: Smooth, elegant dual-phase cognitive flow wave.
        * IDLE / STANDBY: Tranquil quantum ambient tide.
        * MUTED: Calibrated datum baseline.
    """

    BANDS = 48

    def __init__(self) -> None:
        self._levels = [0.0] * self.BANDS
        self._peaks = [0.0] * self.BANDS
        self._peak_decay = [0.0] * self.BANDS
        self._phase = 0.0
        self._mid = (self.BANDS - 1) / 2.0

    def step(self, dt: float, state: str, speaking: bool, muted: bool, amp: float) -> None:
        """Update visualizer physics and ballistic envelopes."""
        dt = max(0.001, min(0.1, dt))
        self._phase += dt
        st = (state or "").upper()

        mid = self._mid
        for i in range(self.BANDS):
            # Calculate target height for this band
            dist = abs(i - mid) / mid
            env = max(0.0, 1.0 - dist) ** 0.65     # Vocal formant center-weighted bell curve

            if muted:
                target = 0.0
            elif speaking:
                # Active synthetic voice harmonics
                h1 = math.sin(self._phase * 7.5 + i * 0.52)
                h2 = math.cos(self._phase * 12.0 - i * 0.38)
                h3 = math.sin(self._phase * 4.2 + i * 0.95)
                shimmer = 0.45 + 0.35 * h1 + 0.15 * h2 + 0.05 * h3
                idle_floor = 1.5 + 1.0 * math.sin(self._phase * 1.5 + i * 0.4)
                target = max(1.5, idle_floor + amp * 23.0 * env * shimmer)
            elif st == "LISTENING":
                # Microphone sensitivity wave
                mic_wave = math.sin(self._phase * 8.0 + i * 0.7) * 0.4 + 0.6
                mic_floor = 2.0 + 1.2 * math.cos(self._phase * 2.0 + i * 0.5)
                target = max(1.5, mic_floor + amp * 19.0 * env * mic_wave)
            elif st in ("THINKING", "PROCESSING"):
                # Neural cognitive flow wave: dual harmonic sine ribbon
                wave1 = math.sin(self._phase * 3.8 + i * 0.28)
                wave2 = math.sin(self._phase * 2.2 - i * 0.21 + 1.2)
                combined = (wave1 * 0.6 + wave2 * 0.4) * env
                target = max(2.0, 4.0 + combined * 10.0)
            else:
                # Idle / Standby: gentle breathing tide
                tide = math.sin(self._phase * 1.4 + i * 0.35) * 0.5 + 0.5
                target = 1.8 + tide * 1.6 * env

            # Ballistics: instant rise (attack), exponential decay (release)
            cur = self._levels[i]
            if target > cur:
                self._levels[i] = target
            else:
                decay_rate = 14.0 if muted else (9.0 if speaking else 6.0)
                self._levels[i] += (target - cur) * (1.0 - math.exp(-decay_rate * dt))

            # Peak needles with gravity decay
            if muted:
                self._peaks[i] = self._levels[i]
                self._peak_decay[i] = 0.0
            elif self._levels[i] >= self._peaks[i]:
                self._peaks[i] = self._levels[i]
                self._peak_decay[i] = 0.0
            else:
                self._peak_decay[i] += 38.0 * dt
                self._peaks[i] = max(self._levels[i], self._peaks[i] - self._peak_decay[i] * dt)

    def paint(self, p: QPainter, cx: float, wy: float, max_w: float,
              state: str, speaking: bool, muted: bool, amp: float,
              ambient_col: QColor) -> None:
        """Render the 48-band spectrum with reflections and floating peak caps."""
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        N = self.BANDS
        span = min(max_w, 440.0)
        bw = span / N
        bar_w = max(1.8, bw - 2.0)
        wx0 = cx - span / 2.0
        st = (state or "").upper()

        # Primary coloration depending on mode
        if muted:
            base_col = qcol(C.MUTED_C)
            cap_col = qcol(C.MUTED_C)
        elif speaking:
            base_col = blend(C.PRI, 0.45)
            cap_col = qcol(C.ACC) if amp > 0.08 else qcol(C.WHITE)
        elif st == "LISTENING":
            base_col = blend(C.GREEN, 0.40)
            cap_col = qcol(C.GREEN)
        elif st in ("THINKING", "PROCESSING"):
            base_col = blend(C.ACC2, 0.35)
            cap_col = qcol(C.ACC2)
        else:
            base_col = blend(C.PRI, 0.28)
            cap_col = blend(C.PRI, 0.70)

        mid = self._mid
        for i in range(N):
            hgt = max(1.5, min(26.0, self._levels[i]))
            pk = max(hgt, min(27.0, self._peaks[i]))
            x = wx0 + i * bw

            dist = abs(i - mid) / mid
            env = max(0.0, 1.0 - dist)

            # Gradient bar
            bg = QLinearGradient(x, wy - hgt, x, wy)
            if speaking or st == "LISTENING":
                top_col = ambient_col if amp > 0.04 else base_col
                bg.setColorAt(0.0, top_col)
                bg.setColorAt(0.7, base_col)
                bg.setColorAt(1.0, with_alpha(base_col, 0.65))
            else:
                bg.setColorAt(0.0, blend(ambient_col, 0.65))
                bg.setColorAt(1.0, with_alpha(base_col, 0.45))

            # Main upper bar (soft rounded top)
            bar_rect = QRectF(x, wy - hgt, bar_w, hgt)
            p.fillRect(bar_rect, QBrush(bg))

            # Floating peak needle / cap
            if pk > hgt + 0.8 and not muted:
                p.setPen(QPen(with_alpha(cap_col, 0.85), 1.0))
                p.drawLine(QLineF(x, wy - pk, x + bar_w, wy - pk))

            # Studio glass floor reflection (35% height, fading into darkness)
            ref_hgt = hgt * 0.45
            if ref_hgt > 0.8:
                rg = QLinearGradient(x, wy + 2.0, x, wy + 2.0 + ref_hgt)
                rg.setColorAt(0.0, with_alpha(base_col, 0.35))
                rg.setColorAt(1.0, with_alpha(base_col, 0.0))
                p.fillRect(QRectF(x, wy + 2.0, bar_w, ref_hgt), QBrush(rg))

        # Precision horizontal datum line
        datum_pen = QPen(with_alpha(base_col, 0.50), 1.0)
        p.setPen(datum_pen)
        p.drawLine(QLineF(wx0 - 4.0, wy + 1.0, wx0 + span + 4.0, wy + 1.0))

        p.restore()


class CognitiveTelemetry:
    """Aerospace-grade minimalist telemetry arcs and cognitive bus status.

    Framing elements designed for HUD interfaces without visual clutter.
    """

    def __init__(self) -> None:
        self._angle = 0.0

    def step(self, dt: float, state: str, speaking: bool) -> None:
        """Step rotation according to cognitive load."""
        st = (state or "").upper()
        if st in ("THINKING", "PROCESSING"):
            rate = 0.32
        elif speaking:
            rate = 0.18
        else:
            rate = 0.06
        self._angle = (self._angle + rate * dt) % (2.0 * math.pi)

    def paint_arcs(self, p: QPainter, cx: float, cy: float, r: float,
                   state: str, speaking: bool, ambient_col: QColor) -> None:
        """Paint subtle framing telemetry arcs around avatar / core."""
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        st = (state or "").upper()
        arc_col = with_alpha(ambient_col, 0.22 if not speaking else 0.42)
        p.setPen(QPen(arc_col, 1.0))

        # Outer framing brackets
        deg = math.degrees(self._angle)
        rect = QRectF(cx - r, cy - r, r * 2.0, r * 2.0)

        # 4 subtle quadrant arcs with gaps
        p.drawArc(rect, int((deg + 15) * 16), int(60 * 16))
        p.drawArc(rect, int((deg + 105) * 16), int(60 * 16))
        p.drawArc(rect, int((deg + 195) * 16), int(60 * 16))
        p.drawArc(rect, int((deg + 285) * 16), int(60 * 16))

        # Precision tick marks at quadrant intervals
        tick_len = 4.0
        p.setPen(QPen(with_alpha(ambient_col, 0.35), 1.0))
        for i in range(8):
            a = self._angle + i * (math.pi / 4.0)
            ca, sa = math.cos(a), math.sin(a)
            p.drawLine(QLineF(cx + ca * (r - tick_len), cy + sa * (r - tick_len),
                             cx + ca * (r + tick_len), cy + sa * (r + tick_len)))

        p.restore()
