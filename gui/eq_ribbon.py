"""gui/eq_ribbon.py — Concentric Orbital Circular Audio Equalizer for JARVIS Mark LVII.

Provides real-time circular audio frequency reactivity around the avatar jawline:
- 32-point concentric circular equalizer orbiting the avatar core.
- Inward ripples (contracting cyan waves) during microphone input (LISTENING).
- Outward ripples (expanding electric cyan / amber waves) during Gemini Live output (SPEAKING).
- Ballistic decay envelopes for studio-grade audio fidelity and zero jitter.
"""

from __future__ import annotations

import math
from typing import List, Optional

import numpy as np
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen

from gui.style import blend_fast, px_font
from gui.theme import C, qcol


class ConcentricAudioEqualizer:
    """32-Point Concentric Circular Audio Frequency Ribbon with inward/outward ripples."""

    POINTS: int = 32

    def __init__(self) -> None:
        self._levels: np.ndarray = np.zeros(self.POINTS, dtype=np.float32)
        self._peaks: np.ndarray = np.zeros(self.POINTS, dtype=np.float32)
        self._phase: float = 0.0

        # Ripple simulation: list of [radius_offset, alpha, velocity_direction]
        # direction = -1.0 for inward (mic), +1.0 for outward (speaker)
        self._ripples: List[List[float]] = []

    def step(self, dt: float, state: str, speaking: bool, muted: bool, amp: float) -> None:
        """Updates circular equalizer harmonic physics and ripple dynamics."""
        dt = max(0.001, min(0.1, dt))
        self._phase += dt * 3.5
        st = (state or "").upper()

        # Generate 32 harmonic amplitudes around the perimeter
        for i in range(self.POINTS):
            theta = 2.0 * math.pi * i / self.POINTS
            if muted:
                target = 0.0
            elif speaking:
                # Active harmonic vocal formants
                h1 = math.sin(self._phase * 4.5 + theta * 3.0)
                h2 = math.cos(self._phase * 8.2 - theta * 5.0)
                shimmer = 0.50 + 0.35 * h1 + 0.15 * h2
                target = amp * 28.0 * shimmer
            elif st == "LISTENING":
                # Microphone sensitivity inward wave
                w = math.sin(self._phase * 5.0 + theta * 4.0)
                target = max(1.5, amp * 18.0 * (0.6 + 0.4 * w))
            elif st in ("THINKING", "PROCESSING"):
                # Smooth cognitive rotation
                w = math.sin(self._phase * 2.8 + theta * 2.0)
                target = 3.0 + 2.5 * w
            else:
                # Idle quantum breathing tide
                target = 1.0 + 0.8 * math.sin(self._phase * 1.2 + theta * 2.0)

            # Ballistic attack and decay
            if target > self._levels[i]:
                self._levels[i] += (target - self._levels[i]) * 0.48  # Fast attack
            else:
                self._levels[i] += (target - self._levels[i]) * 0.18  # Smooth decay

            if self._levels[i] > self._peaks[i]:
                self._peaks[i] = self._levels[i]
            else:
                self._peaks[i] = max(0.0, self._peaks[i] - dt * 14.0)

        # Spawn audio ripple waves on prominent sound peaks
        if speaking and amp > 0.12 and len(self._ripples) < 6:
            if not self._ripples or abs(self._ripples[-1][0]) > 14.0:
                # Outward ripple (+1.0 direction)
                self._ripples.append([0.0, 0.85, 1.0])
        elif st == "LISTENING" and amp > 0.08 and len(self._ripples) < 6:
            if not self._ripples or abs(self._ripples[-1][0]) > 14.0:
                # Inward ripple (-1.0 direction)
                self._ripples.append([40.0, 0.75, -1.0])

        # Step and advance active ripples
        surviving = []
        for r_offset, alpha, direction in self._ripples:
            if direction > 0:
                # Outward expansion
                new_offset = r_offset + dt * 42.0
                new_alpha = alpha - dt * 1.2
                if new_alpha > 0.02 and new_offset < 65.0:
                    surviving.append([new_offset, new_alpha, direction])
            else:
                # Inward contraction
                new_offset = r_offset - dt * 38.0
                new_alpha = alpha - dt * 1.0
                if new_alpha > 0.02 and new_offset > -15.0:
                    surviving.append([new_offset, new_alpha, direction])
        self._ripples = surviving

    def paint(
        self,
        p: QPainter,
        cx: float,
        cy: float,
        base_radius: float,
        speaking: bool,
        state: str,
        muted: bool,
    ) -> None:
        """Renders 32-point circular audio equalizer & concentric ripple waves."""
        if base_radius <= 8.0:
            return

        st = (state or "").upper()
        if muted:
            main_col = C.MUTED_C
        elif speaking:
            main_col = C.ACC  # Amber/cyan vocal radiance
        elif st == "LISTENING":
            main_col = C.GREEN
        elif st in ("THINKING", "PROCESSING"):
            main_col = C.ACC2
        else:
            main_col = C.PRI

        # ── 1. Concentric Audio Ripples (Inward / Outward) ───────────────────
        for r_offset, alpha, direction in self._ripples:
            rip_r = base_radius + r_offset
            if rip_r > 5.0:
                rip_pen = QPen(blend_fast(main_col, alpha), 1.2)
                p.setPen(rip_pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(cx, cy), rip_r, rip_r)

        # ── 2. 32 Radial Equalizer Needles ───────────────────────────────────
        p.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(self.POINTS):
            theta = 2.0 * math.pi * i / self.POINTS
            cos_t = math.cos(theta)
            sin_t = math.sin(theta)

            level = float(self._levels[i])
            peak = float(self._peaks[i])

            # Needle start at base radius, extends outward
            r1 = base_radius
            r2 = base_radius + level
            r_peak = base_radius + peak + 1.5

            x1 = cx + r1 * cos_t
            y1 = cy + r1 * sin_t
            x2 = cx + r2 * cos_t
            y2 = cy + r2 * sin_t

            # Main needle
            needle_col = blend_fast(main_col, 0.45 + min(0.55, level / 20.0))
            p.setPen(QPen(needle_col, 1.4))
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

            # Peak hold dot
            if peak > 2.0:
                px = cx + r_peak * cos_t
                py = cy + r_peak * sin_t
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(blend_fast(C.WHITE, 0.85)))
                p.drawEllipse(QPointF(px, py), 1.0, 1.0)
