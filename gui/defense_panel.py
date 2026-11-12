"""gui/defense_panel.py — Polar Defense Radar & Cybersecurity Sentinel Surface for JARVIS Mark LVII.

Provides real-time perimeter defense visualization:
- 360-degree sweeping polar radar with phosphor decay trails.
- Real-time listening TCP/UDP port mapping (from firewall_warden.py).
- BadUSB / Rubber Ducky hardware alerts (from usb_sentinel.py).
- In-memory process anomaly and unlinked binary alerts (from process_forensics.py).
- Pulsating crimson threat rings on perimeter breach.
- Offscreen AR pixmap rendering for projection directly into HudCanvas Layer 2.
"""

from __future__ import annotations

import math
import random
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QConicalGradient, QFont, QLinearGradient,
    QPainter, QPainterPath, QPen, QPixmap, QRadialGradient,
)
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QSizePolicy, QSplitter, QVBoxLayout, QWidget,
)

from gui.style import blend_fast, hud_font, mono_font, px_font
from gui.theme import C, qcol


class RadarBlip:
    """A tracked port or host socket entity displayed on the polar radar."""

    def __init__(self, port: int, ip: str = "0.0.0.0", proto: str = "TCP", is_public: bool = False, label: str = "") -> None:
        self.port: int = port
        self.ip: str = ip
        self.proto: str = proto
        self.is_public: bool = is_public
        self.label: str = label or f"{proto}:{port}"
        self.is_threat: bool = False
        self.threat_desc: str = ""

        # Compute fixed polar coordinates (Golden angle distribution for clean spread)
        # Radius mapped logarithmically across port space [1, 65535]
        norm_r = 0.22 + 0.72 * (math.log10(max(1, port)) / math.log10(65536.0))
        self.radius_norm: float = min(0.94, max(0.20, norm_r))
        self.angle_deg: float = (port * 137.507) % 360.0

        # Phosphor brightness (1.0 = freshly swept, decays to 0.15)
        self.brightness: float = 0.20
        self.last_swept_t: float = 0.0


class PolarRadarWidget(QWidget):
    """360-degree tactical polar radar with phosphor decay sweep and threat rings."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setMinimumSize(280, 280)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._sweep_angle: float = 0.0        # Degrees [0, 360)
        self._sweep_speed: float = 85.0        # Degrees per second
        self._last_t: float = time.time()

        self._blips: List[RadarBlip] = []
        self._threat_active: bool = False
        self._threat_type: str = ""
        self._threat_details: str = ""
        self._threat_pulse: float = 0.0        # Expanding crimson ring [0.0, 1.0]

        # Seed with initial common open ports
        self._seed_default_sockets()

        # Sweep animation timer (30 FPS)
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._step)
        self._timer.start()

    def _seed_default_sockets(self) -> None:
        """Seed baseline active ports from system or common safe defaults."""
        common_ports = [
            (22, "127.0.0.1", "TCP", False, "SSH Sentry"),
            (80, "0.0.0.0", "TCP", True, "HTTP Web"),
            (443, "0.0.0.0", "TCP", True, "HTTPS TLS"),
            (53, "127.0.0.53", "UDP", False, "DNS Resolver"),
            (8000, "127.0.0.1", "TCP", False, "Local Dev Server"),
            (5432, "127.0.0.1", "TCP", False, "PostgreSQL"),
        ]
        self._blips = [RadarBlip(p, ip, proto, pub, lbl) for p, ip, proto, pub, lbl in common_ports]

    def set_sockets(self, socket_data: List[Dict[str, Any]]) -> None:
        """Updates radar blips from live firewall_warden.py sockets scan."""
        new_blips = []
        for s in socket_data:
            port = int(s.get("port", 0))
            if port > 0:
                ip = s.get("ip", "0.0.0.0")
                proto = s.get("proto", "TCP")
                pub = bool(s.get("public", False))
                lbl = f"{proto}:{port}"
                new_blips.append(RadarBlip(port, ip, proto, pub, lbl))
        if new_blips:
            self._blips = new_blips
        self.update()

    def trigger_threat_alert(self, threat_type: str, details: str, is_critical: bool = True) -> None:
        """Triggers a high-priority pulsating crimson warning ring on perimeter breach."""
        self._threat_active = True
        self._threat_type = threat_type
        self._threat_details = details
        self._threat_pulse = 0.0

        # Mark or create a threat blip in the outer defense ring
        threat_blip = RadarBlip(port=random.randint(40000, 60000), ip="ALERT", proto="ATTK", is_public=True, label=f"! {threat_type}")
        threat_blip.is_threat = True
        threat_blip.threat_desc = details
        threat_blip.brightness = 1.0
        self._blips.append(threat_blip)

        self.update()

    def clear_threat_alerts(self) -> None:
        """Resets threat state back to green/cyan perimeter posture."""
        self._threat_active = False
        self._threat_type = ""
        self._threat_details = ""
        self._threat_pulse = 0.0
        self._blips = [b for b in self._blips if not b.is_threat]
        self.update()

    def _step(self) -> None:
        """Advances radar sweep beam and updates blip phosphor decay."""
        now = time.time()
        dt = max(0.001, min(0.1, now - self._last_t))
        self._last_t = now

        prev_angle = self._sweep_angle
        self._sweep_angle = (self._sweep_angle + self._sweep_speed * dt) % 360.0

        # Check which blips were illuminated by the sweep arm this frame
        for blip in self._blips:
            b_ang = blip.angle_deg
            # Check if b_ang lies between prev_angle and sweep_angle
            swept = False
            if prev_angle <= self._sweep_angle:
                swept = (prev_angle <= b_ang <= self._sweep_angle)
            else:
                swept = (b_ang >= prev_angle or b_ang <= self._sweep_angle)

            if swept:
                blip.brightness = 1.0
                blip.last_swept_t = now
            else:
                # Exponential decay of phosphor trail
                blip.brightness = max(0.18, blip.brightness - dt * 0.45)

        # Advance threat ring expansion
        if self._threat_active:
            self._threat_pulse = (self._threat_pulse + dt * 0.85) % 1.0

        self.update()

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        W, H = float(self.width()), float(self.height())
        cx, cy = W / 2.0, H / 2.0
        radius = min(cx, cy) - 16.0
        self.paint_radar_on(p, QPointF(cx, cy), radius)

    def paint_radar_on(self, p: QPainter, center: QPointF, radius: float) -> None:
        """Renders polar radar display into any target QPainter context."""
        if radius <= 10.0:
            return

        cx, cy = center.x(), center.y()
        main_col = blend_fast(C.RED if self._threat_active else C.PRI, 0.85)
        dim_col = blend_fast(C.BORDER, 0.40)

        # ── 1. Semi-translucent Circular Scope Glass ─────────────────────────
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(blend_fast(C.BG, 0.90)))
        p.drawEllipse(center, radius, radius)

        # ── 2. Concentric Range Rings (25%, 50%, 75%, 100%) ──────────────────
        for frac in (0.25, 0.50, 0.75, 1.0):
            r_ring = radius * frac
            ring_pen = QPen(dim_col, 1.0, Qt.PenStyle.DashLine if frac < 1.0 else Qt.PenStyle.SolidLine)
            p.setPen(ring_pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(center, r_ring, r_ring)

        # ── 3. Crosshair Cardinal Axes & Azimuth Ticks ───────────────────────
        axis_pen = QPen(dim_col, 1.0)
        p.setPen(axis_pen)
        p.drawLine(QPointF(cx - radius, cy), QPointF(cx + radius, cy))
        p.drawLine(QPointF(cx, cy - radius), QPointF(cx, cy + radius))

        # Diagonal guidelines at 45°, 135°, 225°, 315°
        diag_pen = QPen(blend_fast(C.BORDER, 0.22), 1.0, Qt.PenStyle.DotLine)
        p.setPen(diag_pen)
        diag_dist = radius * 0.7071
        p.drawLine(QPointF(cx - diag_dist, cy - diag_dist), QPointF(cx + diag_dist, cy + diag_dist))
        p.drawLine(QPointF(cx - diag_dist, cy + diag_dist), QPointF(cx + diag_dist, cy - diag_dist))

        # Azimuth labels (000°, 090°, 180°, 270°)
        p.setFont(mono_font(6.5, QFont.Weight.Bold))
        p.setPen(QPen(blend_fast(C.TEXT_DIM, 0.70)))
        p.drawText(QRectF(cx - 20, cy - radius - 14, 40, 12), Qt.AlignmentFlag.AlignCenter, "000°")
        p.drawText(QRectF(cx + radius + 2, cy - 6, 36, 12), Qt.AlignmentFlag.AlignLeft, "090°")
        p.drawText(QRectF(cx - 20, cy + radius + 2, 40, 12), Qt.AlignmentFlag.AlignCenter, "180°")
        p.drawText(QRectF(cx - radius - 38, cy - 6, 36, 12), Qt.AlignmentFlag.AlignRight, "270°")

        # ── 4. Pulsating Crimson Threat Anomaly Ring ─────────────────────────
        if self._threat_active:
            pulse_r = radius * (0.20 + 0.80 * self._threat_pulse)
            pulse_alpha = max(0.0, 1.0 - self._threat_pulse)
            threat_col = blend_fast(C.RED, pulse_alpha)
            p.setPen(QPen(threat_col, 2.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(center, pulse_r, pulse_r)

            # Warning text
            p.setFont(hud_font(8.0, QFont.Weight.Bold))
            p.setPen(QPen(blend_fast(C.RED, 0.95)))
            p.drawText(QRectF(cx - 90, cy - 24, 180, 20), Qt.AlignmentFlag.AlignCenter, f"⚠️ {self._threat_type.upper()}")

        # ── 5. Sweeping Radar Beam & Phosphor Decay Fan ──────────────────────
        beam_rad = math.radians(self._sweep_angle)
        sweep_x = cx + radius * math.cos(beam_rad)
        sweep_y = cy + radius * math.sin(beam_rad)

        # Conical phosphor decay fan (55-degree tail)
        fan_grad = QConicalGradient(cx, cy, -self._sweep_angle)
        sweep_theme_col = qcol(C.RED if self._threat_active else C.PRI)
        fan_grad.setColorAt(0.0, blend_fast(sweep_theme_col, 0.40))
        fan_grad.setColorAt(55.0 / 360.0, blend_fast(sweep_theme_col, 0.0))
        fan_grad.setColorAt(1.0, blend_fast(sweep_theme_col, 0.0))

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(fan_grad))
        p.drawPie(QRectF(cx - radius, cy - radius, radius * 2, radius * 2), int(-self._sweep_angle * 16), int(55 * 16))

        # Leading sweep needle
        needle_pen = QPen(blend_fast(C.WHITE, 0.95), 1.6)
        p.setPen(needle_pen)
        p.drawLine(center, QPointF(sweep_x, sweep_y))

        # ── 6. Socket Blips with Real Phosphor Illumination ──────────────────
        for blip in self._blips:
            b_rad = math.radians(blip.angle_deg)
            r_dist = radius * blip.radius_norm
            bx = cx + r_dist * math.cos(b_rad)
            by = cy + r_dist * math.sin(b_rad)

            # Color selection: Crimson for threat/public exposure, Green/Cyan for safe
            if blip.is_threat:
                base_c = C.RED
            elif blip.is_public:
                base_c = C.ACC  # Amber for public open socket
            else:
                base_c = C.GREEN if blip.proto == "TCP" else C.PRI

            dot_col = blend_fast(base_c, blip.brightness)
            sz = 3.2 if blip.brightness > 0.6 else 2.4

            # Blip aura
            if blip.brightness > 0.5:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(blend_fast(base_c, blip.brightness * 0.35)))
                p.drawEllipse(QPointF(bx, by), sz * 2.5, sz * 2.5)

            # Blip core
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(dot_col))
            p.drawEllipse(QPointF(bx, by), sz, sz)

            # Blip text label when illuminated
            if blip.brightness > 0.65 or blip.is_threat:
                p.setFont(mono_font(6.5, QFont.Weight.Bold if blip.is_threat else QFont.Weight.Normal))
                p.setPen(QPen(blend_fast(base_c, blip.brightness)))
                p.drawText(QPointF(bx + 5, by + 3), blip.label)

        # ── 7. Perimeter Frame & Heading Readout ─────────────────────────────
        p.setPen(QPen(main_col, 1.8))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(center, radius, radius)

        # Radar telemetry pill
        p.setFont(mono_font(7, QFont.Weight.Bold))
        p.setPen(QPen(blend_fast(C.PRI, 0.90)))
        status_txt = "SECURE // 0 ANOMALIES" if not self._threat_active else f"PERIMETER BREACH: {self._threat_type}"
        p.drawText(QRectF(cx - 100, cy + radius - 18, 200, 16), Qt.AlignmentFlag.AlignCenter, f"RADAR: {int(self._sweep_angle):03d}° | {status_txt}")


class DefensePanel(QWidget):
    """Full master Cybersecurity Sentinel panel combining Polar Radar, Sockets, and Alerts."""

    closed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setMinimumSize(480, 320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # ── Tactical Header Bar ──────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(34)
        hdr.setStyleSheet(f"""
            QWidget {{
                background: {blend_fast(C.BG, 0.85).name()};
                border: 1px solid {blend_fast(C.BORDER, 0.70).name()};
                border-bottom: 2px solid {blend_fast(C.PRI, 0.80).name()};
            }}
        """)
        hdr_l = QHBoxLayout(hdr)
        hdr_l.setContentsMargins(8, 2, 8, 2)
        hdr_l.setSpacing(8)

        lbl_title = QLabel("🛡️ TACTICAL DEFENSE MATRIX // POLAR RADAR")
        lbl_title.setFont(hud_font(8.5, QFont.Weight.Bold))
        lbl_title.setStyleSheet(f"color: {C.PRI}; border: none; background: transparent;")
        hdr_l.addWidget(lbl_title, stretch=1)

        self._lbl_status = QLabel("SHIELD INTEGRITY: 100% [NOMINAL]")
        self._lbl_status.setFont(mono_font(8, QFont.Weight.Medium))
        self._lbl_status.setStyleSheet(f"color: {C.GREEN}; border: none; background: transparent;")
        hdr_l.addWidget(self._lbl_status)

        btn_close = QPushButton("✕")
        btn_close.setFont(hud_font(8.5, QFont.Weight.Bold))
        btn_close.setFixedSize(22, 22)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                color: {C.TEXT_DIM}; background: transparent; border: none;
            }}
            QPushButton:hover {{ color: {C.RED}; }}
        """)
        btn_close.clicked.connect(self.closed.emit)
        hdr_l.addWidget(btn_close)

        layout.addWidget(hdr)

        # ── Main Content Splitter: Radar & Threat Telemetry ──────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background: {blend_fast(C.BORDER, 0.50).name()};
            }}
        """)

        # Left / Center: Polar Radar Scope
        self.radar = PolarRadarWidget(self)
        splitter.addWidget(self.radar)

        # Right: Sockets & Anomaly Deck
        right_container = QWidget()
        right_v = QVBoxLayout(right_container)
        right_v.setContentsMargins(4, 4, 4, 4)
        right_v.setSpacing(6)

        lbl_sockets_hdr = QLabel("⚡ LISTENING SOCKETS & ENDPOINTS")
        lbl_sockets_hdr.setFont(hud_font(8.0, QFont.Weight.Bold))
        lbl_sockets_hdr.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        right_v.addWidget(lbl_sockets_hdr)

        self._scroll_sockets = QScrollArea()
        self._scroll_sockets.setWidgetResizable(True)
        self._scroll_sockets.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: 1px solid {blend_fast(C.BORDER, 0.60).name()};
            }}
        """)
        self._sockets_box = QWidget()
        self._sockets_box.setStyleSheet(f"background: {blend_fast(C.BG, 0.90).name()};")
        self._sockets_layout = QVBoxLayout(self._sockets_box)
        self._sockets_layout.setContentsMargins(4, 4, 4, 4)
        self._sockets_layout.setSpacing(4)
        self._scroll_sockets.setWidget(self._sockets_box)
        right_v.addWidget(self._scroll_sockets, stretch=1)

        splitter.addWidget(right_container)
        splitter.setSizes([320, 220])

        layout.addWidget(splitter, stretch=1)
        self.refresh_sockets_list()

    def refresh_sockets_list(self) -> None:
        """Populates the side list with current socket entries."""
        while self._sockets_layout.count():
            item = self._sockets_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for b in self.radar._blips[:10]:
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background: {blend_fast(C.PANEL2, 0.85).name()};
                    border: 1px solid {blend_fast(C.PRI, 0.30).name()};
                    padding: 2px 4px;
                }}
            """)
            c_layout = QHBoxLayout(card)
            c_layout.setContentsMargins(4, 2, 4, 2)

            proto_col = C.RED if b.is_threat else (C.ACC if b.is_public else C.GREEN)
            lbl_proto = QLabel(f"[{b.proto}] {b.port}")
            lbl_proto.setFont(mono_font(7.5, QFont.Weight.Bold))
            lbl_proto.setStyleSheet(f"color: {proto_col}; border: none; background: transparent;")
            c_layout.addWidget(lbl_proto)

            lbl_ip = QLabel(b.ip)
            lbl_ip.setFont(mono_font(7))
            lbl_ip.setStyleSheet(f"color: {C.TEXT_DIM}; border: none; background: transparent;")
            c_layout.addWidget(lbl_ip, stretch=1)

            lbl_tag = QLabel("PUB" if b.is_public else "LOCAL")
            lbl_tag.setFont(mono_font(6.5, QFont.Weight.Bold))
            lbl_tag.setStyleSheet(f"color: {proto_col}; border: none; background: transparent;")
            c_layout.addWidget(lbl_tag)

            self._sockets_layout.addWidget(card)

        self._sockets_layout.addStretch()

    def set_threat(self, threat_type: str, details: str) -> None:
        """Sets threat alert on radar and header."""
        self.radar.trigger_threat_alert(threat_type, details)
        self._lbl_status.setText(f"DEFENSE BREACH: {threat_type.upper()}")
        self._lbl_status.setStyleSheet(f"color: {C.RED}; border: none; background: transparent;")
        self.refresh_sockets_list()

    def render_ar_pixmap(self, width: int = 480, height: int = 300) -> QPixmap:
        """Renders the polar defense radar into an offscreen AR pixmap for 3D Layer 2 projection."""
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.GlobalColor.transparent)

        p = QPainter(pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Translucent glass panel frame
        p.setPen(QPen(blend_fast(C.RED if self.radar._threat_active else C.PRI, 0.45), 1.0))
        p.setBrush(QBrush(blend_fast(C.BG, 0.88)))
        p.drawRoundedRect(QRectF(1, 1, width - 2, height - 2), 6.0, 6.0)

        # Header Title
        p.setFont(hud_font(8.5, QFont.Weight.Bold))
        p.setPen(QPen(blend_fast(C.PRI, 0.95), 1))
        p.drawText(QRectF(12, 8, width - 24, 20), Qt.AlignmentFlag.AlignLeft, "🛡️ TACTICAL DEFENSE // POLAR RADAR")

        p.setFont(mono_font(7, QFont.Weight.Bold))
        p.setPen(QPen(blend_fast(C.RED if self.radar._threat_active else C.GREEN, 0.90), 1))
        p.drawText(QRectF(12, 8, width - 24, 20), Qt.AlignmentFlag.AlignRight, self._lbl_status.text())

        # Render radar scope centered in available height
        scope_r = min(width * 0.40, (height - 36) * 0.46)
        scope_cx = width * 0.38
        scope_cy = 28.0 + (height - 36) / 2.0
        self.radar.paint_radar_on(p, QPointF(scope_cx, scope_cy), scope_r)

        # Quick sockets summary on right flank of AR pane
        p.setFont(mono_font(7, QFont.Weight.Bold))
        p.setPen(QPen(blend_fast(C.PRI, 0.85)))
        p.drawText(QRectF(width * 0.68, 34, width * 0.30, 16), Qt.AlignmentFlag.AlignLeft, "OPEN PORTS:")

        y_off = 54.0
        for b in self.radar._blips[:7]:
            p.setFont(mono_font(6.5))
            col = C.RED if b.is_threat else (C.ACC if b.is_public else C.GREEN)
            p.setPen(QPen(blend_fast(col, 0.85)))
            p.drawText(QRectF(width * 0.68, y_off, width * 0.30, 14), Qt.AlignmentFlag.AlignLeft, f"◈ {b.proto}:{b.port} ({b.ip})")
            y_off += 16.0

        p.end()
        return pixmap
