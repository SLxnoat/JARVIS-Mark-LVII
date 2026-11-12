"""gui/mission_capsules.py — 2D Mission Control Task Capsules for JARVIS Mark LVII.

Provides real-time monitoring and report review for autonomous background tasks:
- Displays autonomous agents: Coder Agent, Researcher Agent, General Agent.
- Animated circular step progress rings and status badges.
- One-click Markdown report preview emission.
- Pure 2D vector rendering with zero 3D math overhead.
"""

from __future__ import annotations

import math
import time
from typing import List, Optional

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainter,
    QPainterPath, QPen, QRadialGradient,
)
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget,
)

from gui.style import blend_fast, draw_corner_brackets, draw_tech_badge, mono_font, px_font
from gui.theme import C, qcol


class TaskCapsule:
    """An autonomous agent task entry."""

    def __init__(self, agent_id: str, title: str, status: str,
                 progress: float, current_step: str, report_md: str = "") -> None:
        self.agent_id: str = agent_id
        self.title: str = title
        self.status: str = status  # "RUNNING", "COMPLETED", "IDLE", "PAUSED"
        self.progress: float = progress  # 0.0 -> 1.0
        self.current_step: str = current_step
        self.report_md: str = report_md


class MissionControlCapsules(QWidget):
    """2D Mission Control status capsules for autonomous task agents."""

    report_requested = pyqtSignal(str, str)  # (title, markdown)
    closed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(380, 240)

        self._tasks: List[TaskCapsule] = []
        self._hovered_idx: Optional[int] = None
        self._seed_default_tasks()

        self.setMouseTracking(True)
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self.update)
        self._tmr.start(32)

    def _seed_default_tasks(self) -> None:
        self._tasks = [
            TaskCapsule("coder", "Dev Agent // Codebase Sandbox", "IDLE", 1.0,
                        "Harness checks passed. Ready for instructions.",
                        "# Dev Agent Status\nAll system check passes verified."),
            TaskCapsule("researcher", "Deep Research Agent", "RUNNING", 0.65,
                        "Synthesizing offline documentation...",
                        "# Research Report\nDocument analysis in progress."),
            TaskCapsule("general", "Executive Planner", "COMPLETED", 1.0,
                        "Plan finalized and locked.",
                        "# Mission Plan\nAll tactical milestones aligned."),
        ]

    def update_agent_status(self, agent_id: str, status: str, progress: float, step: str, report: str = "") -> None:
        """Updates or registers an agent's active execution progress."""
        for t in self._tasks:
            if t.agent_id == agent_id:
                t.status = status
                t.progress = max(0.0, min(1.0, progress))
                t.current_step = step
                if report:
                    t.report_md = report
                self.update()
                return
        self._tasks.append(TaskCapsule(agent_id, f"Agent // {agent_id.upper()}", status, progress, step, report))
        self.update()

    def mouseMoveEvent(self, e) -> None:
        mpos = e.position()
        W = self.width()
        card_h = 58.0
        start_y = 44.0
        hovered = None
        for i in range(len(self._tasks)):
            cy = start_y + i * (card_h + 8.0)
            rect = QRectF(16, cy, W - 32, card_h)
            if rect.contains(mpos):
                hovered = i
                break
        if hovered != self._hovered_idx:
            self._hovered_idx = hovered
            self.update()
        super().mouseMoveEvent(e)

    def mousePressEvent(self, e) -> None:
        if self._hovered_idx is not None and 0 <= self._hovered_idx < len(self._tasks):
            task = self._tasks[self._hovered_idx]
            self.report_requested.emit(task.title, task.report_md or f"# {task.title}\n{task.current_step}")
        super().mousePressEvent(e)

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        W, H = self.width(), self.height()
        draw_corner_brackets(p, QRectF(10, 10, W - 20, H - 20), size=10.0, color=blend_fast(C.GREEN, 0.40))
        draw_tech_badge(p, 16, 14, "TASKS // MISSION CONTROL", C.GREEN)

        card_h = 58.0
        start_y = 44.0
        card_w = W - 32.0

        for i, task in enumerate(self._tasks):
            cy = start_y + i * (card_h + 8.0)
            rect = QRectF(16, cy, card_w, card_h)
            is_hover = (i == self._hovered_idx)

            # Card background
            p.setPen(QPen(blend_fast(C.GREEN if is_hover else C.BORDER_A, 0.8 if is_hover else 0.4), 1.0))
            p.setBrush(QBrush(blend_fast(C.PANEL2, 0.85 if not is_hover else 0.95)))
            p.drawRoundedRect(rect, 4.0, 4.0)

            # Circular Progress Ring on left of card
            ring_cx = 44.0
            ring_cy = cy + card_h / 2.0
            ring_r = 16.0

            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(blend_fast(C.PANEL, 0.8), 2.5))
            p.drawEllipse(QPointF(ring_cx, ring_cy), ring_r, ring_r)

            prog_angle = int(task.progress * 360.0 * 16)
            col_hex = C.GREEN if task.status == "COMPLETED" else (C.ACC if task.status == "RUNNING" else C.TEXT_DIM)
            p.setPen(QPen(blend_fast(col_hex, 0.95), 2.5))
            p.drawArc(QRectF(ring_cx - ring_r, ring_cy - ring_r, ring_r * 2, ring_r * 2),
                      90 * 16, -prog_angle)

            # Percentage inside ring
            p.setFont(mono_font(6.0, QFont.Weight.Bold))
            p.setPen(QPen(blend_fast(C.WHITE, 0.95)))
            pct_txt = f"{int(task.progress * 100)}%"
            p.drawText(QRectF(ring_cx - ring_r, ring_cy - ring_r, ring_r * 2, ring_r * 2),
                       Qt.AlignmentFlag.AlignCenter, pct_txt)

            # Task title
            p.setFont(px_font(8.5, QFont.Weight.Bold, mono=True))
            p.setPen(QPen(blend_fast(C.WHITE if is_hover else C.TEXT, 0.95)))
            p.drawText(QPointF(72, cy + 20), task.title)

            # Step description
            p.setFont(mono_font(6.5))
            p.setPen(QPen(blend_fast(C.TEXT_DIM, 0.85)))
            p.drawText(QPointF(72, cy + 36), task.current_step)

            # Status pill on right
            draw_tech_badge(p, W - 92, cy + 14, task.status, col_hex, filled=(task.status == "RUNNING"))
