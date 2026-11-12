"""gui/command_spotlight.py — Universal Command Spotlight for JARVIS Mark LVII.

Provides instant fuzzy search and execution across all 69 plugins and system actions:
- Modal glassmorphic spotlight dialog triggered via Ctrl+K.
- Sub-millisecond fuzzy matching across command names, categories, and descriptions.
- Smooth keyboard navigation (Up / Down / Enter / Escape).
- Dispatches tool actions or transitions workspaces with zero friction.
"""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from PyQt6.QtCore import QEvent, QPoint, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QKeyEvent, QPainter, QPen,
)
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QSizePolicy, QVBoxLayout, QWidget,
)

from gui.style import blend_fast, draw_corner_brackets, draw_tech_badge, mono_font, px_font
from gui.theme import C, qcol


class SpotlightCommand:
    """A command entry in the universal spotlight palette."""

    def __init__(
        self,
        cmd_id: str,
        title: str,
        category: str,
        description: str,
        icon: str = "◈",
        action: Optional[Callable[[], None]] = None,
    ) -> None:
        self.cmd_id: str = cmd_id
        self.title: str = title
        self.category: str = category
        self.description: str = description
        self.icon: str = icon
        self.action: Optional[Callable[[], None]] = action


class CommandSpotlight(QWidget):
    """Universal Command Spotlight dialog with fuzzy search across 69 plugins."""

    command_executed = pyqtSignal(str, str)  # (cmd_id, title)
    closed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.WindowType.SubWindow | Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(540, 360)

        self._all_commands: List[SpotlightCommand] = []
        self._filtered_commands: List[SpotlightCommand] = []

        self._init_ui()
        self._build_command_catalog()
        self._populate_list(self._all_commands)
        self.hide()

    def _init_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        self._frame = QFrame(self)
        self._frame.setStyleSheet(f"""
            QFrame {{
                background-color: {C.PANEL};
                border: 1px solid {C.PRI_DIM};
                border-top: 2px solid {C.PRI};
                border-radius: 4px;
            }}
        """)
        frame_layout = QVBoxLayout(self._frame)
        frame_layout.setContentsMargins(16, 14, 16, 12)
        frame_layout.setSpacing(10)

        # Header Search Row
        search_row = QHBoxLayout()
        lbl_icon = QLabel("🔍")
        lbl_icon.setStyleSheet("border: none; background: transparent; font-size: 14px;")
        search_row.addWidget(lbl_icon)

        self._txt_search = QLineEdit()
        self._txt_search.setPlaceholderText("TYPE TO SEARCH 69 PLUGINS & COMMANDS (ESC TO CLOSE)...")
        self._txt_search.setFont(px_font(9.0, QFont.Weight.Medium, mono=True))
        self._txt_search.setStyleSheet(f"""
            QLineEdit {{
                background: {C.PANEL2};
                color: {C.WHITE};
                border: 1px solid {C.BORDER};
                border-radius: 2px;
                padding: 6px 10px;
            }}
            QLineEdit:focus {{
                border: 1px solid {C.PRI};
            }}
        """)
        self._txt_search.textChanged.connect(self._on_search_changed)
        search_row.addWidget(self._txt_search, stretch=1)
        frame_layout.addLayout(search_row)

        # Commands List
        self._list = QListWidget()
        self._list.setStyleSheet(f"""
            QListWidget {{
                background: transparent;
                border: 1px solid {C.BORDER_A};
                color: {C.TEXT};
                outline: none;
            }}
            QListWidget::item {{
                padding: 6px 10px;
                border-bottom: 1px solid {blend_fast(C.BORDER, 0.30).name()};
            }}
            QListWidget::item:selected {{
                background: {blend_fast(C.PRI, 0.20).name()};
                border-left: 3px solid {C.PRI};
                color: {C.WHITE};
            }}
            QListWidget::item:hover {{
                background: {blend_fast(C.PANEL, 0.50).name()};
            }}
        """)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        frame_layout.addWidget(self._list, stretch=1)

        # Footer Status Bar
        footer_row = QHBoxLayout()
        self._lbl_status = QLabel("69 PLUGINS & WORKSPACES INDEXED")
        self._lbl_status.setFont(mono_font(6.5, QFont.Weight.Medium))
        self._lbl_status.setStyleSheet(f"color: {C.TEXT_DIM}; border: none; background: transparent;")
        footer_row.addWidget(self._lbl_status)
        footer_row.addStretch()

        lbl_nav = QLabel("↑↓ NAVIGATE  •  ENTER SELECT")
        lbl_nav.setFont(mono_font(6.5))
        lbl_nav.setStyleSheet(f"color: {C.TEXT_DIM}; border: none; background: transparent;")
        footer_row.addWidget(lbl_nav)

        frame_layout.addLayout(footer_row)
        outer_layout.addWidget(self._frame)

    def _build_command_catalog(self) -> None:
        """Indexes core workspaces and all plugin files in plugins/."""
        self._all_commands.clear()

        # 1. Primary Workspaces
        core_actions = [
            ("tactical_radar", "Open Tactical Sentry Radar", "SECURITY", "360-degree perimeter sweep & socket inspection", "🛡️"),
            ("synaptic_board", "Open Cognitive Synaptic Board", "NEURO", "Interactive self-learning rules & dopaminergic sparks", "🧠"),
            ("mission_control", "Open Mission Control Tasks", "TASKS", "Autonomous agent task capsules & reports", "🚀"),
            ("holodeck_mode", "Toggle Fullscreen Holodeck (F11)", "VIEWPORT", "Expand HUD canvas to 100% display area", "⛶"),
            ("toggle_drawers", "Toggle Tactical Drawers (Ctrl+[ / Ctrl+])", "WORKSPACE", "Collapse or expand left and right columns", "◫"),
        ]
        for cid, title, cat, desc, icon in core_actions:
            self._all_commands.append(SpotlightCommand(cid, title, cat, desc, icon))

        # 2. Dynamic Discovery of All Installed Plugins
        plugins_dir = Path(__file__).resolve().parent.parent / "plugins"
        if plugins_dir.exists():
            for py_file in sorted(plugins_dir.glob("*.py")):
                if py_file.name.startswith("_"):
                    continue
                cmd_id = f"plugin_{py_file.stem}"
                title = py_file.stem.replace("_", " ").title()
                cat = "PLUGIN"
                desc = f"Execute {title} plugin"
                icon = "⚙️"
                self._all_commands.append(SpotlightCommand(cmd_id, title, cat, desc, icon))

    def _populate_list(self, commands: List[SpotlightCommand]) -> None:
        self._list.clear()
        for cmd in commands[:35]:
            item = QListWidgetItem()
            display_text = f"{cmd.icon}  {cmd.title}  [{cmd.category}]\n    {cmd.description}"
            item.setText(display_text)
            item.setData(Qt.ItemDataRole.UserRole, cmd)
            self._list.addItem(item)
        if self._list.count() > 0:
            self._list.setCurrentRow(0)
        self._lbl_status.setText(f"{len(commands)} RESULTS FOUND")

    def _on_search_changed(self, query: str) -> None:
        query = query.strip().lower()
        if not query:
            self._populate_list(self._all_commands)
            return

        scored: List[Tuple[float, SpotlightCommand]] = []
        for cmd in self._all_commands:
            target = f"{cmd.title} {cmd.category} {cmd.description}".lower()
            if query in target:
                score = 2.0 if query in cmd.title.lower() else 1.0
                scored.append((score, cmd))
            else:
                ratio = difflib.SequenceMatcher(None, query, cmd.title.lower()).ratio()
                if ratio > 0.45:
                    scored.append((ratio, cmd))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [cmd for _, cmd in scored]
        self._populate_list(results)

    def keyPressEvent(self, e: QKeyEvent) -> None:
        if e.key() == Qt.Key.Key_Escape:
            self.hide()
            self.closed.emit()
        elif e.key() in (Qt.Key.Key_Down, Qt.Key.Key_Tab):
            cur = self._list.currentRow()
            if cur < self._list.count() - 1:
                self._list.setCurrentRow(cur + 1)
        elif e.key() == Qt.Key.Key_Up:
            cur = self._list.currentRow()
            if cur > 0:
                self._list.setCurrentRow(cur - 1)
        elif e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._execute_selected()
        else:
            super().keyPressEvent(e)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        self._execute_selected()

    def _execute_selected(self) -> None:
        cur_item = self._list.currentItem()
        if not cur_item:
            return
        cmd: SpotlightCommand = cur_item.data(Qt.ItemDataRole.UserRole)
        if cmd:
            self.command_executed.emit(cmd.cmd_id, cmd.title)
            if cmd.action:
                cmd.action()
        self.hide()
        self.closed.emit()

    def show_centered(self) -> None:
        """Presents the spotlight search in the center of the main window."""
        if self.parentWidget():
            pw = self.parentWidget().width()
            ph = self.parentWidget().height()
            self.move((pw - self.width()) // 2, max(60, (ph - self.height()) // 3))
        self._txt_search.clear()
        self._txt_search.setFocus()
        self.show()
        self.raise_()
