"""gui/radial_wheel.py — 2D Radial Quick Wheel for JARVIS Mark LVII.

Provides rapid gesture and keyboard workspace navigation:
- 6 primary tactical workspace nodes arranged in a circular pie menu.
- Smooth hover highlighting with angular slice math.
- Center telemetry hub with real-time node title, description, and status.
- Activated via Tab hold or right-click gesture.
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


class RadialSlice:
    """A slice node in the 2D Radial Quick Wheel."""

    def __init__(self, node_id: str, title: str, subtitle: str, color_hex: str, icon: str) -> None:
        self.node_id: str = node_id
        self.title: str = title
        self.subtitle: str = subtitle
        self.color_hex: str = color_hex
        self.icon: str = icon


class RadialQuickWheel(QWidget):
    """Circular pie menu centered around cursor or avatar with release-to-activate."""

    node_activated = pyqtSignal(str)   # Emits node_id when selected
    closed = pyqtSignal()

    NODES: List[RadialSlice] = [
        RadialSlice("radar", "TACTICAL RADAR", "Perimeter Sentry & Sockets", C.RED, "🛡️"),
        RadialSlice("synaptic", "SYNAPTIC BOARD", "Cognitive Rules & Sparks", C.ACC2, "🧠"),
        RadialSlice("tasks", "MISSION TASKS", "Autonomous Agent Capsules", C.GREEN, "🚀"),
        RadialSlice("browser", "WEB BROWSER", "Playwright Surface & DOM", C.PRI, "🌐"),
        RadialSlice("terminal", "DEV SANDBOX", "Terminal & Dev Agent", "#00e676", "💻"),
        RadialSlice("settings", "SYSTEM HUD", "Providers & Palette Themes", "#b388ff", "⚙️"),
    ]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.hide()

        self._r_inner: float = 48.0
        self._r_outer: float = 130.0
        self._center_pos: QPointF = QPointF(150.0, 150.0)
        self._hovered_idx: int = -1

    def show_at(self, global_pos: QPoint) -> None:
        """Presents the radial wheel centered around cursor position."""
        if self.parentWidget():
            parent_pos = self.parentWidget().mapFromGlobal(global_pos)
            sz = int(self._r_outer * 2 + 50.0)
            self.resize(sz, sz)
            self._center_pos = QPointF(sz / 2.0, sz / 2.0)
            self.move(parent_pos.x() - sz // 2, parent_pos.y() - sz // 2)
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
            self.closed.emit()

    def _confirm_selection(self) -> None:
        """Emits selected node action and closes wheel."""
        if 0 <= self._hovered_idx < len(self.NODES):
            selected = self.NODES[self._hovered_idx]
            self.node_activated.emit(selected.node_id)
        self.hide()
        self.closed.emit()

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        cx, cy = self._center_pos.x(), self._center_pos.y()
        n_slices = len(self.NODES)
        slice_arc_deg = 360.0 / n_slices
        slice_arc_rad = 2.0 * math.pi / n_slices

        # 1. Outer Dark Blur Backdrop
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(blend_fast(C.BG, 0.75)))
        p.drawEllipse(self._center_pos, self._r_outer + 20.0, self._r_outer + 20.0)

        # 2. Render Each Slice
        for i, node in enumerate(self.NODES):
            is_hovered = (i == self._hovered_idx)
            start_angle_deg = -90.0 - slice_arc_deg / 2.0 + i * slice_arc_deg

            # Slice path
            path = QPainterPath()
            outer_rect = QRectF(cx - self._r_outer, cy - self._r_outer, self._r_outer * 2, self._r_outer * 2)
            inner_rect = QRectF(cx - self._r_inner, cy - self._r_inner, self._r_inner * 2, self._r_inner * 2)

            path.arcMoveTo(outer_rect, -start_angle_deg)
            path.arcTo(outer_rect, -start_angle_deg, -slice_arc_deg)
            path.arcTo(inner_rect, -start_angle_deg - slice_arc_deg, slice_arc_deg)
            path.closeSubpath()

            # Fill & Stroke
            col_hex = node.color_hex
            if is_hovered:
                p.setPen(QPen(blend_fast(col_hex, 0.95), 1.8))
                p.setBrush(QBrush(blend_fast(col_hex, 0.35)))
            else:
                p.setPen(QPen(blend_fast(C.BORDER_A, 0.40), 1.0))
                p.setBrush(QBrush(blend_fast(C.PANEL2, 0.85)))
            p.drawPath(path)

            # Node icon & text
            mid_angle_rad = math.radians(start_angle_deg + slice_arc_deg / 2.0)
            label_r = (self._r_inner + self._r_outer) / 2.0
            lx = cx + math.cos(mid_angle_rad) * label_r
            ly = cy + math.sin(mid_angle_rad) * label_r

            p.setFont(px_font(9.5 if is_hovered else 8.0, QFont.Weight.Bold, mono=True))
            p.setPen(QPen(blend_fast(C.WHITE if is_hovered else C.TEXT, 0.95)))
            p.drawText(QRectF(lx - 40, ly - 8, 80, 16), Qt.AlignmentFlag.AlignCenter, f"{node.icon} {node.title}")

        # 3. Center Telemetry Hub
        p.setPen(QPen(blend_fast(C.PRI, 0.8), 1.5))
        p.setBrush(QBrush(blend_fast(C.PANEL, 0.95)))
        p.drawEllipse(self._center_pos, self._r_inner - 2, self._r_inner - 2)

        if 0 <= self._hovered_idx < len(self.NODES):
            hovered_node = self.NODES[self._hovered_idx]
            p.setFont(mono_font(6.5, QFont.Weight.Bold))
            p.setPen(QPen(blend_fast(hovered_node.color_hex, 0.95)))
            p.drawText(QRectF(cx - 40, cy - 14, 80, 14), Qt.AlignmentFlag.AlignCenter, hovered_node.title)
            p.setFont(px_font(6.0, mono=True))
            p.setPen(QPen(blend_fast(C.TEXT_DIM, 0.85)))
            p.drawText(QRectF(cx - 42, cy + 2, 84, 14), Qt.AlignmentFlag.AlignCenter, "RELEASE ACTIVATE")
        else:
            p.setFont(px_font(7.0, QFont.Weight.Bold, mono=True))
            p.setPen(QPen(blend_fast(C.TEXT_MED, 0.7)))
            p.drawText(QRectF(cx - 35, cy - 8, 70, 16), Qt.AlignmentFlag.AlignCenter, "QUICK NAV")
