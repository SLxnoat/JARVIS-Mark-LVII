"""gui/neuro_panel.py — Cognitive Neuro-Cortex Synaptic Constellation for JARVIS Mark LVII.

Provides real-time visualization of JARVIS's cognitive memory, dopaminergic learning,
procedural habit mining, and ChromaDB vector embeddings:
- 3D Spherical Neural Mesh with concept clustering and pulsing synaptic connections.
- Dopaminergic Learning Feedback Spark (golden high-voltage electrical arcs).
- Auto-Mined Habit & Learned Rules Registry Cards with active toggle controls.
- ChromaDB Semantic Vector Search Drawer with cosine distance scoring.
- Offscreen AR pixmap rendering for projection directly into HudCanvas Layer 2.
"""

from __future__ import annotations

import math
import random
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PyQt6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath,
    QPen, QPixmap, QPolygonF,
)
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
    QSizePolicy, QSplitter, QStackedWidget, QTextEdit, QVBoxLayout, QWidget,
)

from gui.ar_engine import Camera3D, perspective_project
from gui.style import blend_fast, chamfer, hud_font, mono_font, px_font
from gui.theme import C, qcol


# ── Concept Node Taxonomy & Palette ──────────────────────────────────────────

_CONCEPT_TAXONOMY = [
    # Core OS & Vision
    ("Core Matrix", "core", "#00f2fe"),
    ("Visual Cortex", "core", "#00d2ff"),
    ("Audio Visemes", "core", "#00c6ff"),
    ("System Telemetry", "core", "#38ef7d"),
    ("Task Engine", "core", "#11998e"),
    # Learned Behavioral Rules (Dopaminergic)
    ("Safety Overrides", "rules", "#ffd700"),
    ("Code Guidelines", "rules", "#ffb300"),
    ("Git Commit Style", "rules", "#ffa000"),
    ("User Directives", "rules", "#ffc107"),
    ("File Hygiene", "rules", "#ff9800"),
    # Basal Ganglia Habits
    ("Morning Briefing", "habits", "#b388ff"),
    ("Dev Workspace Prep", "habits", "#7c4dff"),
    ("Nightly Prune", "habits", "#651fff"),
    ("Build & Test Cycle", "habits", "#6200ea"),
    # Semantic Memory & ChromaDB
    ("User Identity", "memory", "#00e5ff"),
    ("Preferences", "memory", "#00b0ff"),
    ("Episodic History", "memory", "#80d8ff"),
    ("Research Knowledge", "memory", "#40c4ff"),
    ("Project Architecture", "memory", "#0091ea"),
    # Cybersecurity & Defense
    ("Port Sentry", "defense", "#ff5252"),
    ("USB Sentinel", "defense", "#ff1744"),
    ("Threat Analysis", "defense", "#d50000"),
]


class NeuralNode3D:
    """A 3D synaptic node in the spherical neuro-cortex constellation."""

    def __init__(self, name: str, category: str, color_hex: str, pos3d: np.ndarray) -> None:
        self.name: str = name
        self.category: str = category
        self.color_hex: str = color_hex
        self.pos3d: np.ndarray = pos3d.astype(np.float32)  # [x, y, z]
        self.activity: float = random.uniform(0.1, 0.4)
        self.target_activity: float = self.activity
        self.pulse_phase: float = random.uniform(0.0, math.pi * 2.0)
        self.spark_energy: float = 0.0


class NeuroMeshCanvas(QWidget):
    """3D Spherical Neural Constellation with Dopaminergic Learning Feedback Sparks."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setMinimumSize(320, 260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._camera = Camera3D(fov=50.0, distance=540.0)
        self._rotation_yaw: float = 0.0
        self._rotation_pitch: float = 14.0
        self._step_t: float = time.time()

        # Generate nodes using Fibonacci spherical distribution
        self._nodes: List[NeuralNode3D] = []
        self._edges: List[Tuple[int, int]] = []
        self._build_constellation()

        # Dopaminergic Learning Spark state
        self._spark_active: bool = False
        self._spark_timer: float = 0.0
        self._spark_path: List[int] = []
        self._spark_points: List[QPointF] = []
        self._last_rule_text: str = ""

        # Internal tick animation timer (30 FPS)
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._step)
        self._timer.start()

    def _build_constellation(self) -> None:
        """Constructs spherical nodes and nearest-neighbor synaptic graph."""
        n_nodes = len(_CONCEPT_TAXONOMY)
        radius = 120.0
        golden_ratio = (1.0 + math.sqrt(5.0)) / 2.0

        for i, (name, cat, col) in enumerate(_CONCEPT_TAXONOMY):
            theta = 2.0 * math.pi * i / golden_ratio
            phi = math.acos(1.0 - 2.0 * (i + 0.5) / n_nodes)

            # Convert spherical coordinates to 3D Cartesian
            x = radius * math.sin(phi) * math.cos(theta)
            y = radius * math.sin(phi) * math.sin(theta) * 0.75  # slightly oblate spheroid
            z = radius * math.cos(phi)

            node = NeuralNode3D(name, cat, col, np.array([x, y, z]))
            self._nodes.append(node)

        # Build synaptic connections based on proximity
        for i in range(len(self._nodes)):
            dists = []
            for j in range(len(self._nodes)):
                if i != j:
                    d = np.linalg.norm(self._nodes[i].pos3d - self._nodes[j].pos3d)
                    dists.append((d, j))
            dists.sort(key=lambda x: x[0])
            # Connect 3 closest synaptic neighbors
            for d, j in dists[:3]:
                edge = tuple(sorted((i, j)))
                if edge not in self._edges:
                    self._edges.append(edge)

    def trigger_learning_spark(self, rule_id: str = "", trigger: str = "", confidence: float = 1.0) -> None:
        """Ignites a golden dopaminergic high-voltage electrical arc across the constellation."""
        self._spark_active = True
        self._spark_timer = 1.0  # Normalized duration decay (1.0 -> 0.0)
        self._last_rule_text = f"{rule_id}: {trigger}" if rule_id else trigger

        # Find rules/habits nodes to ignite
        candidate_indices = [
            i for i, n in enumerate(self._nodes)
            if n.category in ("rules", "habits", "memory")
        ]
        if not candidate_indices:
            candidate_indices = list(range(len(self._nodes)))

        # Pick 4 to 6 connected nodes along the synaptic chain
        chain_len = min(5, len(candidate_indices))
        self._spark_path = random.sample(candidate_indices, chain_len)

        for idx in self._spark_path:
            self._nodes[idx].activity = 1.0
            self._nodes[idx].spark_energy = 1.0

        self.update()

    def _step(self) -> None:
        """Animates 3D rotation, synaptic pulse waves, and spark decay."""
        now = time.time()
        dt = max(0.001, min(0.1, now - self._step_t))
        self._step_t = now

        # Slow ambient rotation around Y axis
        self._rotation_yaw = (self._rotation_yaw + dt * 12.0) % 360.0

        # Step node activities & breathing pulses
        for node in self._nodes:
            node.pulse_phase += dt * 2.2
            base = 0.25 + 0.15 * math.sin(node.pulse_phase)
            if node.spark_energy > 0.01:
                node.spark_energy *= 0.88
                node.activity = max(base, node.spark_energy)
            else:
                node.spark_energy = 0.0
                node.activity = base

        # Step dopaminergic learning spark
        if self._spark_active:
            self._spark_timer -= dt * 1.5
            if self._spark_timer <= 0.0:
                self._spark_active = False
                self._spark_timer = 0.0
                self._spark_path.clear()

        self.update()

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        W, H = float(self.width()), float(self.height())
        self._paint_scene(p, W, H)

    def _paint_scene(self, p: QPainter, W: float, H: float) -> None:
        """Renders the 3D synaptic constellation and golden feedback arc."""
        cx, cy = W / 2.0, H / 2.0

        # Compute 3D rotation matrix (Yaw & Pitch)
        rad_y = math.radians(self._rotation_yaw)
        rad_p = math.radians(self._rotation_pitch)
        cos_y, sin_y = math.cos(rad_y), math.sin(rad_y)
        cos_p, sin_p = math.cos(rad_p), math.sin(rad_p)

        Ry = np.array([[cos_y, 0, sin_y], [0, 1, 0], [-sin_y, 0, cos_y]], dtype=np.float32)
        Rx = np.array([[1, 0, 0], [0, cos_p, -sin_p], [0, sin_p, cos_p]], dtype=np.float32)
        R = Rx @ Ry

        # Transform node positions into camera space
        pts = np.array([n.pos3d for n in self._nodes], dtype=np.float32)
        rotated_pts = (R @ pts.T).T  # Shape: (N, 3)

        # Perspective project onto 2D viewport
        pts2d, depths, mask = perspective_project(rotated_pts, W, H, self._camera)

        # ── 1. Synaptic Axon Connections ──────────────────────────────────────
        synapse_pen = QPen(blend_fast(C.PRI, 0.16), 1.0)
        p.setPen(synapse_pen)
        for i, j in self._edges:
            if mask[i] and mask[j]:
                x1, y1 = float(pts2d[i, 0]), float(pts2d[i, 1])
                x2, y2 = float(pts2d[j, 0]), float(pts2d[j, 1])
                p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        # ── 2. Dopaminergic Learning Feedback Spark (Golden Electric Arc) ──────
        if self._spark_active and len(self._spark_path) >= 2:
            spark_col = blend_fast("#ffd700", max(0.2, self._spark_timer))
            p.setPen(QPen(spark_col, 2.2))
            for k in range(len(self._spark_path) - 1):
                idx1 = self._spark_path[k]
                idx2 = self._spark_path[k + 1]
                if mask[idx1] and mask[idx2]:
                    p1 = QPointF(float(pts2d[idx1, 0]), float(pts2d[idx1, 1]))
                    p2 = QPointF(float(pts2d[idx2, 0]), float(pts2d[idx2, 1]))

                    # Jagged lightning mid-point displacement
                    mid = (p1 + p2) * 0.5
                    jitter_x = random.uniform(-8.0, 8.0) * self._spark_timer
                    jitter_y = random.uniform(-8.0, 8.0) * self._spark_timer
                    mid_jitter = QPointF(mid.x() + jitter_x, mid.y() + jitter_y)

                    path = QPainterPath()
                    path.moveTo(p1)
                    path.lineTo(mid_jitter)
                    path.lineTo(p2)
                    p.drawPath(path)

            # Spark telemetry readout text
            if self._last_rule_text:
                p.setFont(mono_font(7.5, QFont.Weight.Bold))
                p.setPen(QPen(spark_col))
                p.drawText(
                    QRectF(10, H - 24, W - 20, 20),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    f"⚡ DOPAMINE PLASTICITY REINFORCED: {self._last_rule_text[:38]}",
                )

        # ── 3. Synaptic Nodes with Depth Ordering ─────────────────────────────
        order = np.argsort(depths)[::-1]  # Draw back to front
        for idx in order:
            if not mask[idx]:
                continue
            node = self._nodes[idx]
            px = float(pts2d[idx, 0])
            py = float(pts2d[idx, 1])
            depth = float(depths[idx])

            # Scale and alpha attenuation based on depth
            dist_factor = max(0.4, min(1.2, 500.0 / max(1.0, depth)))
            radius = 3.5 * dist_factor * (1.0 + node.activity * 0.8)
            alpha = max(0.2, min(0.95, 0.5 + node.activity * 0.5))

            node_col = blend_fast(node.color_hex, alpha)

            # Halo ring if active/sparked
            if node.spark_energy > 0.1:
                halo_r = radius * 2.8
                p.setPen(QPen(blend_fast("#ffd700", node.spark_energy * 0.7), 1.2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(px, py), halo_r, halo_r)

            # Node core
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(node_col))
            p.drawEllipse(QPointF(px, py), radius, radius)

            # Node label for prominent foreground nodes
            if depth < 520.0 and node.activity > 0.4:
                p.setFont(mono_font(6.5))
                p.setPen(QPen(blend_fast(C.TEXT_DIM, 0.75)))
                p.drawText(QPointF(px + radius + 3, py + 3), node.name)


class HabitDeckWidget(QWidget):
    """Translucent card deck showing learned behavioral rules & auto-mined habits."""

    rule_toggled = pyqtSignal(str, bool)  # (rule_id, is_active)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._rules: List[Dict[str, Any]] = []
        self._habits: Dict[str, Any] = []
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Header Title
        lbl_hdr = QLabel("⚡ LEARNED BEHAVIORS & HABITS")
        lbl_hdr.setFont(hud_font(8.5, QFont.Weight.Bold))
        lbl_hdr.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        layout.addWidget(lbl_hdr)

        # Scroll Area for Rule & Habit Cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: 1px solid {blend_fast(C.BORDER, 0.60).name()};
            }}
        """)
        self._cards_container = QWidget()
        self._cards_container.setStyleSheet(f"background: {blend_fast(C.BG, 0.90).name()};")
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(4, 4, 4, 4)
        self._cards_layout.setSpacing(6)
        scroll.setWidget(self._cards_container)
        layout.addWidget(scroll, stretch=1)

    def refresh_data(self) -> None:
        """Reloads learned rules and habits from JSON storage."""
        try:
            from plugins.cognitive_neuro_cortex import load_habits, load_learned_rules
            self._rules = load_learned_rules()
            self._habits = load_habits()
        except Exception:
            self._rules = []
            self._habits = {}

        # Clear existing cards
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Render Rule Cards
        if not self._rules and not self._habits:
            empty_lbl = QLabel("No learned rules or procedural habits recorded yet.")
            empty_lbl.setFont(mono_font(8))
            empty_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; padding: 12px;")
            self._cards_layout.addWidget(empty_lbl)
            self._cards_layout.addStretch()
            return

        for r in self._rules[:12]:
            rule_id = r.get("id", "R-???")
            trigger = r.get("trigger", "Any trigger")
            behavior = r.get("rule", "")
            active = bool(r.get("active", True))
            confidence = float(r.get("confidence", 0.90))

            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background: {blend_fast(C.PANEL2, 0.85).name()};
                    border: 1px solid {blend_fast(C.PRI, 0.35).name()};
                    padding: 4px;
                }}
            """)
            card_v = QVBoxLayout(card)
            card_v.setContentsMargins(4, 4, 4, 4)
            card_v.setSpacing(2)

            # Top row: ID, Confidence pill, Toggle button
            top_h = QHBoxLayout()
            lbl_id = QLabel(f"◈ {rule_id}")
            lbl_id.setFont(mono_font(8, QFont.Weight.Bold))
            lbl_id.setStyleSheet(f"color: {C.PRI}; border: none; background: transparent;")
            top_h.addWidget(lbl_id)

            lbl_conf = QLabel(f"{confidence:.0%} CONF")
            lbl_conf.setFont(mono_font(7))
            lbl_conf.setStyleSheet(f"color: {C.ACC}; border: none; background: transparent;")
            top_h.addWidget(lbl_conf)
            top_h.addStretch()

            btn_toggle = QPushButton("ACTIVE" if active else "OFF")
            btn_toggle.setFont(mono_font(7, QFont.Weight.Bold))
            btn_toggle.setFixedSize(54, 20)
            btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
            status_col = C.GREEN if active else C.TEXT_DIM
            btn_toggle.setStyleSheet(f"""
                QPushButton {{
                    background: {blend_fast(status_col, 0.20).name()};
                    color: {status_col};
                    border: 1px solid {status_col};
                }}
            """)
            btn_toggle.clicked.connect(lambda ch, rid=rule_id, act=active: self._on_toggle_rule(rid, not act))
            top_h.addWidget(btn_toggle)
            card_v.addLayout(top_h)

            # Trigger condition & override text
            lbl_trig = QLabel(f"IF: {trigger}")
            lbl_trig.setFont(mono_font(7.5, QFont.Weight.Medium))
            lbl_trig.setWordWrap(True)
            lbl_trig.setStyleSheet(f"color: {C.WHITE}; border: none; background: transparent;")
            card_v.addWidget(lbl_trig)

            lbl_rule = QLabel(f"THEN: {behavior}")
            lbl_rule.setFont(mono_font(7))
            lbl_rule.setWordWrap(True)
            lbl_rule.setStyleSheet(f"color: {C.TEXT_DIM}; border: none; background: transparent;")
            card_v.addWidget(lbl_rule)

            self._cards_layout.addWidget(card)

        self._cards_layout.addStretch()

    def _on_toggle_rule(self, rule_id: str, new_state: bool) -> None:
        """Persists active state toggle directly into learned_rules.json."""
        try:
            from plugins.cognitive_neuro_cortex import load_learned_rules, save_learned_rules
            rules = load_learned_rules()
            for r in rules:
                if r.get("id") == rule_id:
                    r["active"] = new_state
                    break
            save_learned_rules(rules)
            self.rule_toggled.emit(rule_id, new_state)
            self.refresh_data()
        except Exception as e:
            print(f"[HabitDeck] Error toggling rule {rule_id}: {e}")


class ChromaSearchDrawer(QWidget):
    """Embedded ChromaDB semantic search drawer with cosine nearest-neighbor cards."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Header Title
        lbl_hdr = QLabel("🔍 CHROMADB SEMANTIC VECTOR SEARCH")
        lbl_hdr.setFont(hud_font(8.5, QFont.Weight.Bold))
        lbl_hdr.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        layout.addWidget(lbl_hdr)

        # Search Query Bar
        self._txt_search = QLineEdit()
        self._txt_search.setPlaceholderText("Query episodic & knowledge vector memories...")
        self._txt_search.setFont(mono_font(8))
        self._txt_search.setStyleSheet(f"""
            QLineEdit {{
                background: {blend_fast(C.PANEL2, 0.90).name()};
                color: {C.WHITE};
                border: 1px solid {blend_fast(C.PRI_DIM, 0.50).name()};
                padding: 4px 8px;
            }}
            QLineEdit:focus {{
                border: 1px solid {C.PRI};
            }}
        """)
        self._txt_search.returnPressed.connect(self._on_search)
        layout.addWidget(self._txt_search)

        # Results Container
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: 1px solid {blend_fast(C.BORDER, 0.60).name()};
            }}
        """)
        self._results_container = QWidget()
        self._results_container.setStyleSheet(f"background: {blend_fast(C.BG, 0.90).name()};")
        self._results_layout = QVBoxLayout(self._results_container)
        self._results_layout.setContentsMargins(4, 4, 4, 4)
        self._results_layout.setSpacing(6)
        scroll.setWidget(self._results_container)
        layout.addWidget(scroll, stretch=1)

    def _on_search(self) -> None:
        query = self._txt_search.text().strip()
        if not query:
            return

        # Clear existing result cards
        while self._results_layout.count():
            item = self._results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        try:
            from memory.vector_store import semantic_search
            results = semantic_search(query=query, n_results=5)
        except Exception as e:
            err_lbl = QLabel(f"Vector search failed: {e}")
            err_lbl.setFont(mono_font(7.5))
            err_lbl.setStyleSheet(f"color: {C.RED}; padding: 8px;")
            self._results_layout.addWidget(err_lbl)
            self._results_layout.addStretch()
            return

        if not results:
            no_lbl = QLabel(f"No semantic matches found for '{query}'.")
            no_lbl.setFont(mono_font(7.5))
            no_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; padding: 8px;")
            self._results_layout.addWidget(no_lbl)
            self._results_layout.addStretch()
            return

        for r in results:
            cat = r.get("category", "knowledge").upper()
            key = r.get("key", "")
            val = r.get("value", "")
            dist = float(r.get("distance", 1.0))
            # Cosine distance to similarity percentage
            sim = max(0.0, min(100.0, (1.0 - dist) * 100.0))

            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background: {blend_fast(C.PANEL2, 0.85).name()};
                    border: 1px solid {blend_fast(C.PRI, 0.35).name()};
                    padding: 4px;
                }}
            """)
            card_v = QVBoxLayout(card)
            card_v.setContentsMargins(4, 4, 4, 4)
            card_v.setSpacing(2)

            top_h = QHBoxLayout()
            lbl_cat = QLabel(f"[{cat}] {key}")
            lbl_cat.setFont(mono_font(7.5, QFont.Weight.Bold))
            lbl_cat.setStyleSheet(f"color: {C.PRI}; border: none; background: transparent;")
            top_h.addWidget(lbl_cat)
            top_h.addStretch()

            lbl_sim = QLabel(f"{sim:.1f}% MATCH")
            lbl_sim.setFont(mono_font(7, QFont.Weight.Bold))
            lbl_sim.setStyleSheet(f"color: {C.GREEN if sim > 60 else C.ACC}; border: none; background: transparent;")
            top_h.addWidget(lbl_sim)
            card_v.addLayout(top_h)

            lbl_val = QLabel(str(val)[:200])
            lbl_val.setFont(mono_font(7))
            lbl_val.setWordWrap(True)
            lbl_val.setStyleSheet(f"color: {C.TEXT_DIM}; border: none; background: transparent;")
            card_v.addWidget(lbl_val)

            self._results_layout.addWidget(card)

        self._results_layout.addStretch()


class NeuroCortexPanel(QWidget):
    """Full Master Neuro-Cortex Panel combining Constellation, Habits, and Vector Search."""

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

        # ── Glassmorphic Tactical Header ─────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(34)
        hdr.setStyleSheet(f"""
            QWidget {{
                background: {blend_fast(C.BG, 0.85).name()};
                border: 1px solid {blend_fast(C.BORDER, 0.70).name()};
                border-bottom: 2px solid {blend_fast(C.ACC, 0.80).name()};
            }}
        """)
        hdr_l = QHBoxLayout(hdr)
        hdr_l.setContentsMargins(8, 2, 8, 2)
        hdr_l.setSpacing(8)

        lbl_title = QLabel("🧠 COGNITIVE NEURO-CORTEX // SYNAPTIC CONSTELLATION")
        lbl_title.setFont(hud_font(8.5, QFont.Weight.Bold))
        lbl_title.setStyleSheet(f"color: {C.ACC}; border: none; background: transparent;")
        hdr_l.addWidget(lbl_title, stretch=1)

        self._lbl_plasticity = QLabel("⚡ PLASTICITY: 98.4% [ACTIVE]")
        self._lbl_plasticity.setFont(mono_font(8, QFont.Weight.Medium))
        self._lbl_plasticity.setStyleSheet(f"color: {C.GREEN}; border: none; background: transparent;")
        hdr_l.addWidget(self._lbl_plasticity)

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

        # ── Main Content Splitter: 3D Constellation & Drawers ────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background: {blend_fast(C.BORDER, 0.50).name()};
            }}
        """)

        # Left / Center: 3D Spherical Neural Constellation
        self.constellation = NeuroMeshCanvas(self)
        splitter.addWidget(self.constellation)

        # Right: Tabbed or stacked Deck (Habits & Vector Search)
        right_container = QWidget()
        right_v = QVBoxLayout(right_container)
        right_v.setContentsMargins(0, 0, 0, 0)
        right_v.setSpacing(4)

        self.habit_deck = HabitDeckWidget(self)
        self.search_drawer = ChromaSearchDrawer(self)
        right_v.addWidget(self.habit_deck, stretch=1)
        right_v.addWidget(self.search_drawer, stretch=1)

        splitter.addWidget(right_container)
        splitter.setSizes([340, 260])

        layout.addWidget(splitter, stretch=1)
        self.refresh_telemetry()

    def trigger_spark(self, rule_id: str, trigger: str, confidence: float = 1.0) -> None:
        """Triggers a golden dopaminergic feedback arc and reloads habits."""
        self.constellation.trigger_learning_spark(rule_id, trigger, confidence)
        self.habit_deck.refresh_data()
        self.refresh_telemetry()

    def refresh_telemetry(self) -> None:
        """Updates synaptic plasticity and learned rules count."""
        try:
            from plugins.cognitive_neuro_cortex import load_learned_rules
            rules = [r for r in load_learned_rules() if r.get("active", True)]
            n = len(rules)
            self._lbl_plasticity.setText(f"⚡ PLASTICITY: 98.4% [{n} RULES]")
        except Exception:
            pass

    def render_ar_pixmap(self, width: int = 480, height: int = 300) -> QPixmap:
        """Renders the neuro constellation into an offscreen AR pixmap for 3D Layer 2 projection."""
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.GlobalColor.transparent)

        p = QPainter(pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Semi-translucent glass backdrop
        p.setPen(QPen(blend_fast(C.ACC, 0.40), 1.0))
        p.setBrush(QBrush(blend_fast(C.BG, 0.88)))
        p.drawRoundedRect(QRectF(1, 1, width - 2, height - 2), 6.0, 6.0)

        # Header Title
        p.setFont(hud_font(8.5, QFont.Weight.Bold))
        p.setPen(QPen(blend_fast(C.ACC, 0.95), 1))
        p.drawText(QRectF(12, 8, width - 24, 20), Qt.AlignmentFlag.AlignLeft, "🧠 COGNITIVE NEURO-CORTEX // 3D CONSTELLATION")

        # Plasticity status
        p.setFont(mono_font(7, QFont.Weight.Bold))
        p.setPen(QPen(blend_fast(C.GREEN, 0.90), 1))
        p.drawText(QRectF(12, 8, width - 24, 20), Qt.AlignmentFlag.AlignRight, self._lbl_plasticity.text())

        # Render 3D Constellation in the central area
        p.save()
        p.translate(0, 24)
        self.constellation._paint_scene(p, float(width), float(height - 28))
        p.restore()

        p.end()
        return pixmap
