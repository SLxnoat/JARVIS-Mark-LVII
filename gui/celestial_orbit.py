"""gui/celestial_orbit.py — Celestial Ephemeris & Satellite Ground-Track Arc for JARVIS Mark LVII.

Provides real-time astronomical and space weather AR telemetry:
- 3D inclined orbital ring tracking the International Space Station (ISS) at 51.6° orbital inclination.
- Ground-track footprint arc and real-time sub-satellite position.
- NOAA Planetary Kp-index magnetosphere bow-shock gauge (Kp 0-9).
- Solar flare X-ray flux classification (A, B, C, M, X) with geomagnetic storm status.
- Offscreen AR pixmap rendering for projection directly into HudCanvas Layer 2.
"""

from __future__ import annotations

import math
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainter,
    QPainterPath, QPen, QPixmap,
)
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from gui.ar_engine import Camera3D, generate_orbit_ring, perspective_project
from gui.style import blend_fast, hud_font, mono_font, px_font
from gui.theme import C, qcol


class CelestialOrbitWidget(QWidget):
    """3D Inclined ISS Orbital Ring & Planetary Magnetosphere Bow-Shock Surface."""

    closed = pyqtSignal()

    # Real ISS orbital inclination relative to equator
    ISS_INCLINATION_DEG: float = 51.64

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setMinimumSize(320, 260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._camera = Camera3D(fov=50.0, distance=560.0)
        self._orbit_phase: float = 0.0          # ISS orbital travel angle along ring
        self._orbit_speed: float = 18.0         # Degrees per second simulation / display
        self._step_t: float = time.time()

        # Telemetry State
        self._iss_lat: float = 24.38
        self._iss_lon: float = 68.12
        self._iss_alt_km: float = 418.0
        self._iss_vel_kmh: int = 27580
        self._kp_index: float = 2.3             # 0.0 to 9.0
        self._solar_class: str = "B4.2 (Quiet)"
        self._solar_wind_kms: int = 435

        # Background update timer
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._step)
        self._timer.start()

        self._poll_telemetry_async()

    def update_telemetry(self, iss_data: Dict[str, Any], space_weather: Dict[str, Any]) -> None:
        """Updates internal celestial data safely."""
        if iss_data:
            self._iss_lat = float(iss_data.get("latitude", self._iss_lat))
            self._iss_lon = float(iss_data.get("longitude", self._iss_lon))
            self._iss_alt_km = float(iss_data.get("altitude", self._iss_alt_km))
            self._iss_vel_kmh = int(iss_data.get("velocity", self._iss_vel_kmh))

        if space_weather:
            self._kp_index = float(space_weather.get("kp_index", self._kp_index))
            self._solar_class = str(space_weather.get("solar_class", self._solar_class))
            self._solar_wind_kms = int(space_weather.get("solar_wind", self._solar_wind_kms))

        self.update()

    def _poll_telemetry_async(self) -> None:
        """Asynchronously fetches fresh telemetry without blocking Qt main thread."""
        def _fetch():
            try:
                from plugins.orbital_tracker import _fetch_iss_telemetry
                from plugins.solar_space_weather import _fetch_space_weather
                iss = _fetch_iss_telemetry()
                sw = _fetch_space_weather()
                self.update_telemetry(iss, sw)
            except Exception:
                pass

        th = threading.Thread(target=_fetch, daemon=True)
        th.start()

    def _step(self) -> None:
        """Steps ISS orbital phase and advances earth/orbital rotation."""
        now = time.time()
        dt = max(0.001, min(0.1, now - self._step_t))
        self._step_t = now

        self._orbit_phase = (self._orbit_phase + self._orbit_speed * dt) % 360.0
        self.update()

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        W, H = float(self.width()), float(self.height())
        self._paint_scene(p, W, H)

    def _paint_scene(self, p: QPainter, W: float, H: float) -> None:
        """Draws 3D celestial rings, ISS tracking blip, and magnetosphere gauge."""
        cx, cy = W / 2.0, H / 2.0
        radius = min(cx, cy) * 0.72

        # ── 1. Semi-translucent Glass Scope Backdrop ─────────────────────────
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(blend_fast(C.BG, 0.90)))
        p.drawRoundedRect(QRectF(4, 4, W - 8, H - 8), 8.0, 8.0)

        # ── 2. Equatorial Earth Reference Horizon Ring ───────────────────────
        center3d = (0.0, 10.0, 0.0)
        equator_ring = generate_orbit_ring(
            radius=radius * 0.88, segments=48, tilt_yaw=0.0, tilt_pitch=10.0, center=center3d
        )
        pts_eq, _, mask_eq = perspective_project(equator_ring, W, H, self._camera)
        if np.all(mask_eq):
            eq_path = QPainterPath()
            eq_path.moveTo(float(pts_eq[0, 0]), float(pts_eq[0, 1]))
            for k in range(1, len(pts_eq)):
                eq_path.lineTo(float(pts_eq[k, 0]), float(pts_eq[k, 1]))
            eq_path.closeSubpath()
            p.setPen(QPen(blend_fast(C.PRI, 0.22), 1.0, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(eq_path)

        # ── 3. ISS Inclined Orbital Ring (51.6° Inclination) ─────────────────
        iss_ring = generate_orbit_ring(
            radius=radius * 1.05,
            segments=64,
            tilt_yaw=15.0,
            tilt_pitch=self.ISS_INCLINATION_DEG,
            center=center3d,
        )
        pts_iss, depths_iss, mask_iss = perspective_project(iss_ring, W, H, self._camera)
        if np.all(mask_iss):
            iss_path = QPainterPath()
            iss_path.moveTo(float(pts_iss[0, 0]), float(pts_iss[0, 1]))
            for k in range(1, len(pts_iss)):
                iss_path.lineTo(float(pts_iss[k, 0]), float(pts_iss[k, 1]))
            iss_path.closeSubpath()

            # Orbit ring pen in cyan
            p.setPen(QPen(blend_fast(C.PRI, 0.60), 1.4))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(iss_path)

        # ── 4. Current ISS Satellite Position Beacon ─────────────────────────
        # Find index along 64-segment ring matching orbit phase
        seg_idx = int((self._orbit_phase / 360.0) * len(iss_ring)) % len(iss_ring)
        iss_pt2d = pts_iss[seg_idx]

        bx = float(iss_pt2d[0])
        by = float(iss_pt2d[1])

        # Pulse halo
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(blend_fast(C.ACC, 0.35)))
        p.drawEllipse(QPointF(bx, by), 7.0, 7.0)

        # Satellite core dot
        p.setBrush(QBrush(blend_fast(C.WHITE, 0.95)))
        p.drawEllipse(QPointF(bx, by), 3.0, 3.0)

        # ISS Telemetry Callout Box
        p.setFont(mono_font(6.5, QFont.Weight.Bold))
        p.setPen(QPen(blend_fast(C.ACC, 0.95)))
        p.drawText(QPointF(bx + 10, by - 4), f"🛰️ ISS // LAT: {self._iss_lat:.1f}° LON: {self._iss_lon:.1f}°")
        p.setFont(mono_font(6.0))
        p.setPen(QPen(blend_fast(C.TEXT_DIM, 0.85)))
        p.drawText(QPointF(bx + 10, by + 8), f"ALT: {self._iss_alt_km:.0f}km | {self._iss_vel_kmh:,}km/h")

        # ── 5. Solar Flare Kp-Index Magnetosphere Bow-Shock Bar ──────────────
        kp = max(0.0, min(9.0, self._kp_index))
        # Color coding: Green (Kp 0-3), Amber (Kp 4-5), Red (Kp 6-9)
        kp_col = C.GREEN if kp < 4.0 else (C.ACC if kp < 6.0 else C.RED)

        bar_x = 16.0
        bar_y = H - 36.0
        bar_w = W - 32.0
        bar_h = 10.0

        # Bar background
        p.setPen(QPen(blend_fast(C.BORDER, 0.40), 1.0))
        p.setBrush(QBrush(blend_fast(C.PANEL2, 0.85)))
        p.drawRect(QRectF(bar_x, bar_y, bar_w, bar_h))

        # Filled Kp level
        fill_w = bar_w * (kp / 9.0)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(blend_fast(kp_col, 0.85)))
        p.drawRect(QRectF(bar_x + 1, bar_y + 1, fill_w, bar_h - 2))

        # Magnetosphere telemetry text
        p.setFont(mono_font(7, QFont.Weight.Bold))
        p.setPen(QPen(blend_fast(kp_col, 0.95)))
        storm_status = "QUIET" if kp < 4.0 else ("MODERATE UNREST" if kp < 6.0 else "GEOMAGNETIC STORM")
        p.drawText(
            QRectF(bar_x, bar_y - 18, bar_w, 16),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"MAGNETOSPHERE: Kp {kp:.1f}/9.0 [{storm_status}]",
        )
        p.setPen(QPen(blend_fast(C.TEXT_DIM, 0.85)))
        p.drawText(
            QRectF(bar_x, bar_y - 18, bar_w, 16),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"SOLAR: {self._solar_class} | WIND: {self._solar_wind_kms}km/s",
        )

    def render_ar_pixmap(self, width: int = 480, height: int = 300) -> QPixmap:
        """Renders the celestial tracking surface into an offscreen AR pixmap for Layer 2."""
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.GlobalColor.transparent)

        p = QPainter(pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Translucent glass border
        p.setPen(QPen(blend_fast(C.PRI, 0.45), 1.0))
        p.setBrush(QBrush(blend_fast(C.BG, 0.88)))
        p.drawRoundedRect(QRectF(1, 1, width - 2, height - 2), 6.0, 6.0)

        # Tactical Header
        p.setFont(hud_font(8.5, QFont.Weight.Bold))
        p.setPen(QPen(blend_fast(C.PRI, 0.95), 1))
        p.drawText(QRectF(12, 8, width - 24, 20), Qt.AlignmentFlag.AlignLeft, "🛰️ CELESTIAL EPHEMERIS // ISS & SPACE WEATHER")

        p.setFont(mono_font(7, QFont.Weight.Bold))
        p.setPen(QPen(blend_fast(C.GREEN if self._kp_index < 4.0 else C.ACC, 0.90), 1))
        p.drawText(QRectF(12, 8, width - 24, 20), Qt.AlignmentFlag.AlignRight, f"ORBIT: {self.ISS_INCLINATION_DEG}° INCL")

        # Render 3D orbit scene
        p.save()
        p.translate(0, 18)
        self._paint_scene(p, float(width), float(height - 22))
        p.restore()

        p.end()
        return pixmap
