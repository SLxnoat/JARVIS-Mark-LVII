"""gui/tactical_radar.py — 2D Tactical Sentry Radar for JARVIS Mark LVII.

Provides real-time 360-degree perimeter monitoring and socket visualization:
- 2D circular radar ring with sweeping phosphor beam and decaying trail.
- Logarithmic radial socket mapping from firewall_warden.py.
- Pulsating crimson perimeter breach rings triggered by threat anomalies.
- Pure 2D vector rendering with zero 3D math overhead.
"""

from __future__ import annotations

import math
import time
from typing import List, Optional

from PyQt6.QtCore import QLineF, QPointF, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainter,
    QPainterPath, QPen, QRadialGradient,
)
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from gui.style import blend_fast, draw_corner_brackets, draw_tech_badge, mono_font, px_font
from gui.theme import C, qcol


class RadarBlip:
    """Represents a monitored network socket or detected host."""

    def __init__(self, port: int, ip: str = "0.0.0.0", proto: str = "TCP",
                 is_threat: bool = False, label: str = "") -> None:
        self.port: int = port
        self.ip: str = ip
        self.proto: str = proto
        self.is_threat: bool = is_threat
        self.label: str = label or f"{proto}:{port}"

        # Deterministic 2D polar coordinates
        self.radius_norm: float = 0.22 + 0.68 * (math.log10(max(1, port)) / 4.82)
        self.radius_norm = max(0.20, min(0.95, self.radius_norm))
        self.angle_deg: float = (port * 137.508) % 360.0  # Golden angle distribution
        self.last_hit_t: float = 0.0


class TacticalRadarWidget(QWidget):
    """2D Tactical Sentry Radar Widget with phosphor sweep and socket blips."""

    closed = pyqtSignal()
    threat_detected = pyqtSignal(str, str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(320, 320)

        self._sweep_angle: float = 0.0
        self._sweep_speed: float = 120.0  # degrees / second
        self._last_t: float = time.perf_counter()

        self._blips: List[RadarBlip] = []
        self._alert_pulse: float = 0.0
        self._alert_text: str = ""

        # Default sample sockets
        self._seed_default_blips()

        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._tmr.start(16)

    def _seed_default_blips(self) -> None:
        default_ports = [
            (22, "SSH", False), (53, "DNS", False), (80, "HTTP", False),
            (443, "HTTPS", False), (5353, "mDNS", False), (8080, "HTTP-ALT", False),
        ]
        for p, lbl, thr in default_ports:
            self._blips.append(RadarBlip(port=p, label=lbl, is_threat=thr))

    def update_sockets(self, sockets_data: list) -> None:
        """Updates radar blips from firewall_warden.py scan results."""
        new_blips = []
        for s in sockets_data:
            if isinstance(s, dict):
                p = int(s.get("port", 0))
                proto = str(s.get("proto", "TCP"))
                lbl = str(s.get("service", ""))
                thr = bool(s.get("is_threat", False))
                new_blips.append(RadarBlip(port=p, proto=proto, label=lbl, is_threat=thr))
        if new_blips:
            self._blips = new_blips
        self.update()

    def trigger_alert(self, threat_type: str, details: str) -> None:
        """Triggers a pulsating crimson perimeter breach animation."""
        self._alert_pulse = 1.0
        self._alert_text = f"BREACH // {threat_type}: {details}"
        # Add a threat blip
        self._blips.append(RadarBlip(port=9999, is_threat=True, label=threat_type))
        self.threat_detected.emit(threat_type, details)
        self.update()

    def _step(self) -> None:
        now = time.perf_counter()
        dt = max(0.001, min(0.1, now - self._last_t))
        self._last_t = now

        prev_angle = self._sweep_angle
        self._sweep_angle = (self._sweep_angle + self._sweep_speed * dt) % 360.0

        # Check for beam-blip intersection
        for b in self._blips:
            diff = (self._sweep_angle - b.angle_deg) % 360.0
            if diff < 12.0:
                b.last_hit_t = now

        if self._alert_pulse > 0.0:
            self._alert_pulse = max(0.0, self._alert_pulse - dt * 0.45)

        self.update()

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        W, H = self.width(), self.height()
        cx, cy = W / 2.0, H / 2.0
        r_outer = min(W, H) * 0.44

        # 1. Outer tactical framing
        draw_corner_brackets(p, QRectF(10, 10, W - 20, H - 20), size=10.0, color=blend_fast(C.PRI, 0.40))
        draw_tech_badge(p, 16, 14, "SEC // POLAR RADAR SENTRY", C.PRI)

        # 2. Backdrop Glow
        bg_rad = QRadialGradient(cx, cy, r_outer)
        bg_rad.setColorAt(0.0, blend_fast(C.PRI, 0.08))
        bg_rad.setColorAt(0.70, blend_fast(C.PRI, 0.03))
        bg_rad.setColorAt(1.0, blend_fast(C.BG, 0.95))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(bg_rad))
        p.drawEllipse(QPointF(cx, cy), r_outer, r_outer)

        # 3. Concentric Range Rings
        p.setBrush(Qt.BrushStyle.NoBrush)
        for frac, alpha in ((0.25, 0.20), (0.50, 0.25), (0.75, 0.30), (1.00, 0.50)):
            p.setPen(QPen(blend_fast(C.PRI, alpha), 1.0 if frac < 1.0 else 1.5))
            rr = r_outer * frac
            p.drawEllipse(QPointF(cx, cy), rr, rr)

        # 4. Crosshairs & 45-degree Spokes
        p.setPen(QPen(blend_fast(C.PRI, 0.18), 1.0, Qt.PenStyle.DotLine))
        p.drawLine(QLineF(cx - r_outer, cy, cx + r_outer, cy))
        p.drawLine(QLineF(cx, cy - r_outer, cx, cy + r_outer))

        diag = r_outer * 0.7071
        p.setPen(QPen(blend_fast(C.PRI, 0.10), 1.0, Qt.PenStyle.DotLine))
        p.drawLine(QLineF(cx - diag, cy - diag, cx + diag, cy + diag))
        p.drawLine(QLineF(cx - diag, cy + diag, cx + diag, cy - diag))

        # 5. Sweeping Phosphor Beam Pie Slice
        sweep_rad = math.radians(self._sweep_angle)
        tail_deg = 45.0
        p_path = QPainterPath()
        p_path.moveTo(cx, cy)
        p_path.arcTo(QRectF(cx - r_outer, cy - r_outer, r_outer * 2, r_outer * 2),
                     -self._sweep_angle, tail_deg)
        p_path.closeSubpath()

        beam_grad = QRadialGradient(cx, cy, r_outer)
        beam_col = C.RED if self._alert_pulse > 0.3 else C.PRI
        beam_grad.setColorAt(0.0, blend_fast(beam_col, 0.25))
        beam_grad.setColorAt(0.8, blend_fast(beam_col, 0.12))
        beam_grad.setColorAt(1.0, blend_fast(beam_col, 0.0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(beam_grad))
        p.drawPath(p_path)

        # Leading beam line
        bx = cx + math.cos(sweep_rad) * r_outer
        by = cy + math.sin(sweep_rad) * r_outer
        p.setPen(QPen(blend_fast(C.WHITE if self._alert_pulse < 0.3 else C.RED, 0.85), 1.5))
        p.drawLine(QLineF(cx, cy, bx, by))

        # 6. Socket Blips
        now = time.perf_counter()
        p.setFont(mono_font(6.5, QFont.Weight.Medium))
        for b in self._blips:
            rad = math.radians(b.angle_deg)
            dist = r_outer * b.radius_norm
            bx_pt = cx + math.cos(rad) * dist
            by_pt = cy + math.sin(rad) * dist

            # Phosphor decay
            elapsed = now - b.last_hit_t
            decay = max(0.20, math.exp(-elapsed * 1.8))
            if b.is_threat:
                col_hex = C.RED
                decay = max(decay, 0.75 + 0.25 * math.sin(now * 8.0))
            else:
                col_hex = C.GREEN if b.port in (80, 443) else C.PRI

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(blend_fast(col_hex, decay)))
            pip_r = 3.2 if b.is_threat else 2.4
            p.drawEllipse(QPointF(bx_pt, by_pt), pip_r, pip_r)

            if decay > 0.45 or b.is_threat:
                p.setPen(QPen(blend_fast(C.TEXT_MED if not b.is_threat else C.RED, decay * 0.90)))
                p.drawText(QPointF(bx_pt + 5, by_pt + 3), b.label)

        # 7. Pulsating Crimson Breach Ring
        if self._alert_pulse > 0.05:
            pulse_r = r_outer * (0.4 + 0.6 * (1.0 - self._alert_pulse))
            p.setPen(QPen(blend_fast(C.RED, self._alert_pulse * 0.85), 2.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), pulse_r, pulse_r)

            # Alert text banner
            if self._alert_text:
                draw_tech_badge(p, 20, H - 28, self._alert_text, C.RED, filled=True)
