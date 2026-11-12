"""gui/synaptic_board.py — 2D Cognitive Synaptic Board for JARVIS Mark LVII.

Provides an interactive 2D node-graph visualizer for self-learning memory & rules:
- Interactive nodes representing learned habits, safety rules, and memory concepts.
- Golden dopaminergic feedback sparks traveling along synaptic edges on learning triggers.
- Click to inspect rule trigger conditions and confidence levels.
- Pure 2D vector rendering with zero 3D math overhead.
"""

from __future__ import annotations

import math
import random
import time
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainter,
    QPainterPath, QPen, QRadialGradient,
)
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from gui.style import blend_fast, draw_corner_brackets, draw_tech_badge, mono_font, px_font
from gui.theme import C, qcol


class SynapticNode:
    """A cognitive rule or concept node in the synaptic board."""

    def __init__(self, node_id: str, label: str, category: str, x: float, y: float,
                 confidence: float = 0.85, trigger: str = "") -> None:
        self.node_id: str = node_id
        self.label: str = label
        self.category: str = category  # "core", "rules", "habits", "memory", "defense"
        self.pos: QPointF = QPointF(x, y)
        self.target_pos: QPointF = QPointF(x, y)
        self.confidence: float = confidence
        self.trigger: str = trigger
        self.activity: float = 0.0  # glow boost when activated


class SynapticSpark:
    """A dopaminergic pulse spark animating along an edge."""

    def __init__(self, src: QPointF, dst: QPointF, color_hex: str = C.ACC2) -> None:
        self.src: QPointF = src
        self.dst: QPointF = dst
        self.progress: float = 0.0  # 0.0 -> 1.0
        self.color_hex: str = color_hex
        self.speed: float = 1.4     # progress / second


class SynapticBoardWidget(QWidget):
    """2D Cognitive Synaptic Board displaying self-learning neural rules and habits."""

    node_selected = pyqtSignal(str, str, str)  # (id, label, trigger)
    closed = pyqtSignal()

    CAT_COLORS = {
        "core": C.PRI,
        "rules": C.ACC2,
        "habits": C.GREEN,
        "memory": "#b388ff",
        "defense": C.RED,
    }

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(420, 300)

        self._nodes: Dict[str, SynapticNode] = {}
        self._edges: List[Tuple[str, str]] = []
        self._sparks: List[SynapticSpark] = []
        self._selected_node_id: Optional[str] = None
        self._hovered_node_id: Optional[str] = None

        self._last_t: float = time.perf_counter()
        self._build_default_graph()

        self.setMouseTracking(True)
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._tmr.start(16)

    def _build_default_graph(self) -> None:
        """Seeds initial cognitive nodes across the 5 core categories."""
        default_nodes = [
            ("core_jarvis", "CORE ORCHESTRATOR", "core", 210, 150, 0.99, "Always Active"),
            ("rule_threading", "Qt Thread Isolation", "rules", 110, 80, 0.95, "action/plugin execution"),
            ("rule_timeout", "Subprocess 5s Deadlines", "rules", 120, 220, 0.92, "shell commands"),
            ("habit_auto_save", "Periodic Config Sync", "habits", 310, 80, 0.88, "every 5 min"),
            ("habit_lod", "Dynamic Framerate LOD", "habits", 320, 220, 0.94, "idle breathing"),
            ("mem_chroma", "Semantic Knowledge Base", "memory", 210, 50, 0.90, "user intent query"),
            ("def_ports", "Port Sentry Monitoring", "defense", 210, 250, 0.96, "unlinked listening sockets"),
        ]
        for nid, lbl, cat, x, y, conf, trig in default_nodes:
            self._nodes[nid] = SynapticNode(nid, lbl, cat, x, y, conf, trig)

        self._edges = [
            ("core_jarvis", "rule_threading"),
            ("core_jarvis", "rule_timeout"),
            ("core_jarvis", "habit_auto_save"),
            ("core_jarvis", "habit_lod"),
            ("core_jarvis", "mem_chroma"),
            ("core_jarvis", "def_ports"),
            ("rule_threading", "def_ports"),
            ("habit_lod", "def_ports"),
        ]

    def spark_learning(self, rule_id: str, trigger: str, confidence: float = 0.9) -> None:
        """Emits a dopaminergic spark from core to rule node on positive reinforcement."""
        if rule_id not in self._nodes:
            # Dynamically add newly learned rule
            rx = random.uniform(80, max(280, self.width() - 80))
            ry = random.uniform(60, max(200, self.height() - 60))
            self._nodes[rule_id] = SynapticNode(rule_id, rule_id.replace("_", " ").upper(),
                                                "rules", rx, ry, confidence, trigger)
            self._edges.append(("core_jarvis", rule_id))

        target = self._nodes[rule_id]
        target.activity = 1.0
        target.confidence = max(target.confidence, confidence)

        core_node = self._nodes.get("core_jarvis")
        if core_node:
            self._sparks.append(SynapticSpark(core_node.pos, target.pos, C.ACC2))
        self.update()

    def _step(self) -> None:
        now = time.perf_counter()
        dt = max(0.001, min(0.1, now - self._last_t))
        self._last_t = now

        # Advance sparks
        remaining_sparks = []
        for s in self._sparks:
            s.progress += s.speed * dt
            if s.progress < 1.0:
                remaining_sparks.append(s)
        self._sparks = remaining_sparks

        # Decay node activity glows
        for n in self._nodes.values():
            if n.activity > 0.0:
                n.activity = max(0.0, n.activity - dt * 0.8)

        self.update()

    def mouseMoveEvent(self, e) -> None:
        mpos = e.position()
        hovered = None
        for nid, n in self._nodes.items():
            dx = mpos.x() - n.pos.x()
            dy = mpos.y() - n.pos.y()
            if math.hypot(dx, dy) < 16.0:
                hovered = nid
                break
        if hovered != self._hovered_node_id:
            self._hovered_node_id = hovered
            self.update()
        super().mouseMoveEvent(e)

    def mousePressEvent(self, e) -> None:
        if self._hovered_node_id and self._hovered_node_id in self._nodes:
            self._selected_node_id = self._hovered_node_id
            sel = self._nodes[self._selected_node_id]
            self.node_selected.emit(sel.node_id, sel.label, sel.trigger)
            self.update()
        super().mousePressEvent(e)

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        W, H = self.width(), self.height()
        draw_corner_brackets(p, QRectF(10, 10, W - 20, H - 20), size=10.0, color=blend_fast(C.ACC2, 0.40))
        draw_tech_badge(p, 16, 14, "NEURO // SYNAPTIC BOARD", C.ACC2)

        # 1. Synaptic Edges
        for u_id, v_id in self._edges:
            if u_id in self._nodes and v_id in self._nodes:
                p0 = self._nodes[u_id].pos
                p1 = self._nodes[v_id].pos
                p.setPen(QPen(blend_fast(C.PRI, 0.18), 1.2))
                p.drawLine(p0, p1)

        # 2. Sparks
        for s in self._sparks:
            t = s.progress
            sx = s.src.x() + (s.dst.x() - s.src.x()) * t
            sy = s.src.y() + (s.dst.y() - s.src.y()) * t
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(blend_fast(s.color_hex, 0.95)))
            p.drawEllipse(QPointF(sx, sy), 3.2, 3.2)
            # Spark aura
            p.setBrush(QBrush(blend_fast(s.color_hex, 0.35)))
            p.drawEllipse(QPointF(sx, sy), 6.5, 6.5)

        # 3. Nodes
        p.setFont(mono_font(6.5, QFont.Weight.Medium))
        for nid, n in self._nodes.items():
            col_hex = self.CAT_COLORS.get(n.category, C.PRI)
            is_hovered = (nid == self._hovered_node_id)
            is_selected = (nid == self._selected_node_id)
            r_node = 9.0 if nid == "core_jarvis" else 6.5
            if is_hovered or is_selected:
                r_node += 2.5

            # Glow
            if n.activity > 0.05 or is_hovered or is_selected:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(blend_fast(col_hex, 0.25 + 0.5 * n.activity)))
                p.drawEllipse(n.pos, r_node * 1.8, r_node * 1.8)

            p.setPen(QPen(blend_fast(C.WHITE if is_selected else col_hex, 0.95), 1.5))
            p.setBrush(QBrush(blend_fast(col_hex, 0.35 if not is_selected else 0.85)))
            p.drawEllipse(n.pos, r_node, r_node)

            # Node label
            p.setPen(QPen(blend_fast(C.WHITE if is_selected else C.TEXT_MED, 0.85)))
            p.drawText(QPointF(n.pos.x() + r_node + 4, n.pos.y() + 3), n.label)

        # 4. Inspector card at bottom-left if node is selected
        if self._selected_node_id and self._selected_node_id in self._nodes:
            sel = self._nodes[self._selected_node_id]
            card_rect = QRectF(16, H - 55, min(280, W - 32), 42)
            p.setPen(QPen(blend_fast(C.ACC2, 0.6), 1.0))
            p.setBrush(QBrush(blend_fast(C.PANEL2, 0.92)))
            p.drawRoundedRect(card_rect, 3.0, 3.0)

            p.setFont(px_font(7.5, QFont.Weight.Bold, mono=True))
            p.setPen(QPen(blend_fast(C.WHITE, 0.95)))
            p.drawText(QPointF(24, H - 38), f"NODE: {sel.label}")

            p.setFont(mono_font(6.5))
            p.setPen(QPen(blend_fast(C.TEXT_DIM, 0.85)))
            p.drawText(QPointF(24, H - 24), f"CONFIDENCE: {int(sel.confidence * 100)}% | TRIGGER: {sel.trigger}")
