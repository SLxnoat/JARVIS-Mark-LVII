"""gui/radial_menu.py — AR Radial Command Wheel for JARVIS Mark LVII.

Provides rapid gesture and keyboard workspace navigation:
- 6 primary tactical workspace nodes arranged in a circular pie menu.
- Smooth hover highlighting with angular slice math.
- Center telemetry hub with real-time node title, description, and shortcuts.
- Activated via Tab hold, right-click gesture, or middle-click.
- Release-to-activate mechanism for rapid, sub-second workspace transitions.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

from PyQt6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainter,
    QPainterPath, QPen, QRadialGradient,
)
from PyQt6.QtWidgets import QSizePolicy, QWidget

from gui.style import blend_fast, hud_font, mono_font, px_font
from gui.theme import C, qcol


class RadialNode:
    """A slice node in the AR Radial Command Wheel."""

    def __init__(self, node_id: str, title: str, subtitle: str, color_hex: str, icon: str) -> None:
        self.node_id: str = node_id
        self.title: str = title
        self.subtitle: str = subtitle
        self.color_hex: str = color_hex
        self.icon: str = icon


class RadialCommandWheel(QWidget):
    """Circular pie menu centered around HUD avatar with release-to-activate."""

    node_activated = pyqtSignal(str)   # Emits node_id when selected

    NODES: List[RadialNode] = [
        RadialNode("browser", "BROWSER", "Floating AR Playwright Surface", "#00f2fe", "🌐"),
        RadialNode("defense", "DEFENSE", "Polar Radar & Perimeter Sentry", "#ff1744", "🛡️"),
        RadialNode("neuro", "NEURO-CORTEX", "Cognitive Synaptic Constellation", "#ffd700", "🧠"),
        RadialNode("code", "SANDBOX", "Autonomous Dev Agent & Terminal", "#00e676", "💻"),
        RadialNode("celestial", "CELESTIAL", "ISS Orbit & Space Weather", "#00b0ff", "🛰️"),
        RadialNode("tasks", "MISSION TASKS", "Mission Control Agent Capsules", "#d500f9", "🚀"),
    ]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.hide()

        self._r_inner: float = 46.0
        self._r_outer: float = 138.0
        self._hovered_idx: int = -1
        self._center_pos: QPointF = QPointF(150.0, 150.0)

    def show_at(self, global_pos: QPoint) -> None:
        """Presents the radial wheel centered at the requested point."""
        size = int(self._r_outer * 2 + 50)
        self.resize(size, size)
        self._center_pos = QPointF(size / 2.0, size / 2.0)

        # Center widget over target point
        if self.parentWidget():
            local_pos = self.parentWidget().mapFromGlobal(global_pos)
            self.move(int(local_pos.x() - size / 2.0), int(local_pos.y() - size / 2.0))
        else:
            self.move(int(global_pos.x() - size / 2.0), int(global_pos.y() - size / 2.0))

        self._hovered_idx = -1
        self.show()
        self.raise_()
        self.setFocus()

    def _get_slice_index(self, pos: QPointF) -> int:
        """Calculates slice index from cursor position using polar coordinates."""
        dx = pos.x() - self._center_pos.x()
        dy = pos.y() - self._center_pos.y()
        dist = math.hypot(dx, dy)

        if dist < self._r_inner or dist > self._r_outer + 25.0:
            return -1

        # Calculate angle in [0, 2*pi) with 0 at the top (-pi/2)
        angle = math.atan2(dy, dx) + math.pi / 2.0
        if angle < 0:
            angle += 2.0 * math.pi

        n_slices = len(self.NODES)
        slice_arc = 2.0 * math.pi / n_slices

        # Offset by half a slice so slice 0 is centered directly at top
        angle_shifted = (angle + slice_arc / 2.0) % (2.0 * math.pi)
        return int(angle_shifted / slice_arc)

    def mouseMoveEvent(self, e) -> None:
        idx = self._get_slice_index(e.position())
        if idx != self._hovered_idx:
            self._hovered_idx = idx
            self.update()

    def mouseReleaseEvent(self, e) -> None:
        self._confirm_selection()

    def keyReleaseEvent(self, e) -> None:
        if e.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Alt):
            self._confirm_selection()
        elif e.key() == Qt.Key.Key_Escape:
            self.hide()

    def _confirm_selection(self) -> None:
        """Emits selected node action and closes wheel."""
        if 0 <= self._hovered_idx < len(self.NODES):
            selected = self.NODES[self._hovered_idx]
            self.node_activated.emit(selected.node_id)
        self.hide()

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        cx, cy = self._center_pos.x(), self._center_pos.y()
        n_slices = len(self.NODES)
        slice_arc_deg = 360.0 / n_slices
        slice_arc_rad = 2.0 * math.pi / n_slices

        # ── 1. Outer Dark Blur Backdrop ──────────────────────────────────────
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(blend_fast(C.BG, 0.70)))
        p.drawEllipse(self._center_pos, self._r_outer + 20.0, self._r_outer + 20.0)

        # ── 2. Render Each Slice ─────────────────────────────────────────────
        for i, node in enumerate(self.NODES):
            is_hover = (i == self._hovered_idx)
            r_out = self._r_outer + (10.0 if is_hover else 0.0)

            # Center angle of slice (slice 0 at 90 deg / top)
            center_angle_deg = 90.0 - i * slice_arc_deg
            start_angle_deg = center_angle_deg - slice_arc_deg / 2.0

            # Build annular sector path
            path = QPainterPath()
            path.arcMoveTo(QRectF(cx - r_out, cy - r_out, r_out * 2, r_out * 2), start_angle_deg)
            path.arcTo(QRectF(cx - r_out, cy - r_out, r_out * 2, r_out * 2), start_angle_deg, slice_arc_deg)

            # Arc back along inner radius
            path.arcTo(QRectF(cx - self._r_inner, cy - self._r_inner, self._r_inner * 2, self._r_inner * 2),
                       start_angle_deg + slice_arc_deg, -slice_arc_deg)
            path.closeSubpath()

            # Fill color
            fill_alpha = 0.85 if is_hover else 0.40
            slice_col = blend_fast(node.color_hex if is_hover else C.PANEL2, fill_alpha)
            p.setBrush(QBrush(slice_col))

            border_col = blend_fast(node.color_hex, 0.95 if is_hover else 0.35)
            p.setPen(QPen(border_col, 1.8 if is_hover else 1.0))
            p.drawPath(path)

            # Draw Node Icon & Short Label
            mid_rad = math.radians(center_angle_deg)
            lbl_r = (self._r_inner + r_out) / 2.0
            lx = cx + lbl_r * math.cos(mid_rad)
            ly = cy - lbl_r * math.sin(mid_rad)

            p.setFont(px_font(12 if is_hover else 10, QFont.Weight.Bold))
            p.setPen(QPen(blend_fast(C.WHITE, 0.95 if is_hover else 0.75)))
            p.drawText(QRectF(lx - 25, ly - 14, 50, 16), Qt.AlignmentFlag.AlignCenter, node.icon)

            p.setFont(mono_font(6.5, QFont.Weight.Bold))
            p.drawText(QRectF(lx - 32, ly + 2, 64, 12), Qt.AlignmentFlag.AlignCenter, node.title)

        # ── 3. Central Telemetry Hub ─────────────────────────────────────────
        hub_r = self._r_inner - 2.0
        p.setPen(QPen(blend_fast(C.PRI, 0.80), 1.5))
        p.setBrush(QBrush(blend_fast(C.BG, 0.95)))
        p.drawEllipse(self._center_pos, hub_r, hub_r)

        # Center info text
        if 0 <= self._hovered_idx < len(self.NODES):
            sel = self.NODES[self._hovered_idx]
            p.setFont(hud_font(7.5, QFont.Weight.Bold))
            p.setPen(QPen(blend_fast(sel.color_hex, 0.95)))
            p.drawText(QRectF(cx - hub_r, cy - 14, hub_r * 2, 14), Qt.AlignmentFlag.AlignCenter, sel.title)

            p.setFont(mono_font(5.5))
            p.setPen(QPen(blend_fast(C.TEXT_DIM, 0.85)))
            p.drawText(QRectF(cx - hub_r + 4, cy + 1, (hub_r - 4) * 2, 22), Qt.AlignmentFlag.AlignCenter, sel.subtitle[:24])
        else:
            p.setFont(mono_font(6.5, QFont.Weight.Bold))
            p.setPen(QPen(blend_fast(C.PRI_DIM, 0.75)))
            p.drawText(QRectF(cx - hub_r, cy - 8, hub_r * 2, 16), Qt.AlignmentFlag.AlignCenter, "◈ WORKSPACE")
