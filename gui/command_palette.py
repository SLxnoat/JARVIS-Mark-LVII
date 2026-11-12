"""gui/command_palette.py — Universal Command Spotlight for JARVIS Mark LVII.

Provides instant fuzzy search and execution across all 69 plugins and system actions:
- Modal glassmorphic spotlight dialog triggered via Ctrl+K.
- Sub-millisecond fuzzy matching across command names, categories, and descriptions.
- Smooth keyboard navigation (Up / Down / Enter / Escape).
- Dispatches tool actions or transitions AR surfaces with zero friction.
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

from gui.style import blend_fast, hud_font, mono_font, px_font
from gui.theme import C, qcol


class PaletteCommand:
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


class CommandPalette(QWidget):
    """Universal Command Spotlight dialog with fuzzy search across 69 plugins."""

    command_executed = pyqtSignal(str, str)  # (cmd_id, title)
    closed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.WindowType.SubWindow | Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(540, 360)

        self._all_commands: List[PaletteCommand] = []
        self._filtered_commands: List[PaletteCommand] = []

        self._init_ui()
        self._build_command_catalog()

    def _init_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)

        # ── Glassmorphic Frame ───────────────────────────────────────────────
        self._frame = QFrame()
        self._frame.setStyleSheet(f"""
            QFrame {{
                background: {blend_fast(C.BG, 0.94).name()};
                border: 1px solid {blend_fast(C.BORDER, 0.80).name()};
                border-top: 2px solid {blend_fast(C.PRI, 0.90).name()};
                border-radius: 8px;
            }}
        """)
        frame_layout = QVBoxLayout(self._frame)
        frame_layout.setContentsMargins(8, 8, 8, 8)
        frame_layout.setSpacing(6)

        # Search Bar Row
        search_row = QHBoxLayout()
        lbl_icon = QLabel("🔍")
        lbl_icon.setFont(mono_font(9))
        lbl_icon.setStyleSheet("border: none; background: transparent;")
        search_row.addWidget(lbl_icon)

        self._txt_search = QLineEdit()
        self._txt_search.setPlaceholderText("Type a command or search plugins (Ctrl+K)...")
        self._txt_search.setFont(mono_font(8.5))
        self._txt_search.setStyleSheet(f"""
            QLineEdit {{
                background: {blend_fast(C.PANEL2, 0.90).name()};
                color: {C.WHITE};
                border: 1px solid {blend_fast(C.PRI_DIM, 0.45).name()};
                padding: 4px 8px;
                border-radius: 4px;
            }}
            QLineEdit:focus {{
                border: 1px solid {C.PRI};
            }}
        """)
        self._txt_search.textChanged.connect(self._on_search_text_changed)
        search_row.addWidget(self._txt_search, stretch=1)

        lbl_esc = QLabel("ESC TO EXIT")
        lbl_esc.setFont(mono_font(6.5))
        lbl_esc.setStyleSheet(f"color: {C.TEXT_DIM}; border: none; background: transparent; padding-right: 4px;")
        search_row.addWidget(lbl_esc)

        frame_layout.addLayout(search_row)

        # Command Results List
        self._list = QListWidget()
        self._list.setFont(mono_font(8))
        self._list.setStyleSheet(f"""
            QListWidget {{
                background: transparent;
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                padding: 6px 8px;
                border-bottom: 1px solid {blend_fast(C.BORDER, 0.35).name()};
                color: {C.WHITE};
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
        """Indexes core workspaces, AR panels, and all plugin files in plugins/."""
        self._all_commands.clear()

        # 1. Primary Workspaces & AR Panels
        core_actions = [
            ("ar_browser", "Open AR Browser Holo-Surface", "AR WORKSPACE", "Launch floating angled Playwright browser", "🌐"),
            ("defense_radar", "Open Polar Defense Radar", "DEFENSE", "360-degree perimeter sweep & socket inspection", "🛡️"),
            ("neuro_cortex", "Open Cognitive Neuro-Cortex", "MEMORY", "3D synaptic constellation & dopaminergic sparks", "🧠"),
            ("celestial_orbit", "Open Celestial Ephemeris", "EPHEMERIS", "Track ISS orbit and solar flare weather", "🛰️"),
            ("mission_control", "Open Mission Control Tasks", "TASKS", "Autonomous background task agent capsules", "🚀"),
            ("holodeck_mode", "Toggle Fullscreen Holodeck Mode (F11)", "VIEWPORT", "Expand AR canvas to 100% display area", "⛶"),
            ("reader_mode", "Toggle Web Reader Mode", "BROWSER", "Slide-out translucent extracted article view", "📖"),
            ("toggle_focus", "Toggle Center-Stage Expansion (Ctrl+B)", "WORKSPACE", "Dock avatar to orbit and focus active pane", "🗖"),
        ]
        for cid, title, cat, desc, icon in core_actions:
            self._all_commands.append(PaletteCommand(cid, title, cat, desc, icon))

        # 2. Dynamic Discovery of All Installed Plugins
        plugins_dir = Path(__file__).resolve().parent.parent / "plugins"
        if plugins_dir.exists():
            for py_file in sorted(plugins_dir.glob("*.py")):
                if py_file.stem.startswith("_"):
                    continue
                cmd_name = py_file.stem.replace("_", " ").title()
                desc = f"Execute tactical plugin {py_file.stem}"
                self._all_commands.append(
                    PaletteCommand(
                        f"plugin:{py_file.stem}",
                        f"Run {cmd_name}",
                        "PLUGIN",
                        desc,
                        "🧩",
                    )
                )

        self._lbl_status.setText(f"{len(self._all_commands)} COMMANDS & PLUGINS INDEXED")
        self._populate_list(self._all_commands)

    def _populate_list(self, commands: List[PaletteCommand]) -> None:
        self._filtered_commands = commands
        self._list.clear()

        for cmd in commands[:25]:
            item = QListWidgetItem()
            item.setText(f"{cmd.icon}  {cmd.title}  [{cmd.category}]\n     {cmd.description}")
            item.setData(Qt.ItemDataRole.UserRole, cmd)
            self._list.addItem(item)

        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    def _on_search_text_changed(self, text: str) -> None:
        q = text.strip().lower()
        if not q:
            self._populate_list(self._all_commands)
            return

        # Fuzzy matching and keyword scoring
        scored: List[Tuple[float, PaletteCommand]] = []
        for cmd in self._all_commands:
            haystack = f"{cmd.title} {cmd.category} {cmd.description} {cmd.cmd_id}".lower()
            if q in haystack:
                # Substring match gets high priority
                score = 1.0 + (1.0 if q in cmd.title.lower() else 0.0)
                scored.append((score, cmd))
            else:
                # Fuzzy ratio
                ratio = difflib.SequenceMatcher(None, q, cmd.title.lower()).ratio()
                if ratio > 0.35:
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
        cmd: PaletteCommand = cur_item.data(Qt.ItemDataRole.UserRole)
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
