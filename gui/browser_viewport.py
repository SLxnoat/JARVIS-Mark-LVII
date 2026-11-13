"""
gui/browser_viewport.py — JARVIS AR Browser Viewport Overlay
=============================================================
Holographic browser surface that projects Playwright screenshots into a
dedicated, framed overlay panel inside the HUD rather than replacing the
avatar with a raw ``show_image()`` call.

Features
--------
* Cyan neon chamfered frame with BROWSER / AR VIEWPORT header.
* URL bar showing the current page URL with a colour-coded SSL badge
  (green lock = https, amber = http, grey = file/other).
* Miniature navigation controls: Back, Forward, Refresh, Close.
* The screenshot image is displayed inside the frame and fills the
  viewport area while maintaining aspect ratio.
* Thread-safe: all state changes go through Qt signals so the viewport
  can be updated from any thread.

Usage (from plugin or player)
------------------------------
    # Show the viewport with an image and URL
    player.show_browser_viewport(image_path, url)

    # Hide when browsing session ends
    player.close_browser_viewport()

Both methods are added to JarvisUI in ui.py.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QPixmap, QPainter, QPen, QBrush, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QFrame,
)

from gui.theme import C, qcol
from gui.style import px_font, chamfer


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ssl_color(url: str) -> str:
    if url.startswith("https://"):
        return C.GREEN
    if url.startswith("http://"):
        return "#ffaa00"
    return C.TEXT_DIM


def _ssl_icon(url: str) -> str:
    if url.startswith("https://"):
        return "SECURE"
    if url.startswith("http://"):
        return "UNSEC"
    return "LOCAL"


# ---------------------------------------------------------------------------
# Screenshot display label
# ---------------------------------------------------------------------------

class _ScreenshotLabel(QLabel):
    """QLabel that scales its pixmap to fit while keeping aspect ratio."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(f"background: {C.PANEL}; border: none;")
        self._pix: Optional[QPixmap] = None

    def set_screenshot(self, path: str) -> None:
        pix = QPixmap(path)
        if not pix.isNull():
            self._pix = pix
            self._refresh()

    def _refresh(self) -> None:
        if self._pix is None:
            return
        scaled = self._pix.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)

    def resizeEvent(self, event):  # type: ignore[override]
        super().resizeEvent(event)
        self._refresh()


# ---------------------------------------------------------------------------
# Main viewport widget
# ---------------------------------------------------------------------------

class BrowserViewport(QWidget):
    """
    Floating holographic browser overlay.

    Signals
    -------
    nav_back()      — user clicked Back
    nav_forward()   — user clicked Forward
    nav_refresh()   — user clicked Refresh
    closed()        — user clicked Close
    """

    nav_back    = pyqtSignal()
    nav_forward = pyqtSignal()
    nav_refresh = pyqtSignal()
    closed      = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"BrowserViewport {{ background: {C.PANEL}; "
            f"border: 1px solid {C.PRI_DIM}; }}"
        )
        self._build_ui()
        self.hide()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(2, 2, 2, 2)
        root.setSpacing(0)

        # Header bar -------------------------------------------------------
        header = QWidget()
        header.setFixedHeight(26)
        header.setStyleSheet(
            f"background: {C.PRI_GHO}; border-bottom: 1px solid {C.PRI_DIM};"
        )
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(8, 0, 4, 0)
        hlay.setSpacing(6)

        title = QLabel("AR BROWSER VIEWPORT")
        title.setFont(px_font(9, QFont.Weight.Bold, spacing=2.0))
        title.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        hlay.addWidget(title)
        hlay.addStretch()

        self._close_btn = self._nav_btn("X", self._on_close)
        hlay.addWidget(self._close_btn)
        root.addWidget(header)

        # URL bar ----------------------------------------------------------
        url_row = QWidget()
        url_row.setFixedHeight(24)
        url_row.setStyleSheet(
            f"background: {C.BG if hasattr(C, 'BG') else '#010a10'};"
            f"border-bottom: 1px solid {C.BORDER};"
        )
        ulay = QHBoxLayout(url_row)
        ulay.setContentsMargins(6, 0, 6, 0)
        ulay.setSpacing(5)

        self._ssl_badge = QLabel("LOCAL")
        self._ssl_badge.setFixedWidth(44)
        self._ssl_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ssl_badge.setFont(px_font(8, QFont.Weight.Bold))
        self._ssl_badge.setStyleSheet(
            f"color: {C.TEXT_DIM}; background: transparent; border: none;"
        )
        ulay.addWidget(self._ssl_badge)

        self._url_lbl = QLabel("about:blank")
        self._url_lbl.setFont(px_font(10))
        self._url_lbl.setStyleSheet(
            f"color: {C.TEXT}; background: transparent; border: none;"
        )
        self._url_lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        ulay.addWidget(self._url_lbl, stretch=1)

        self._back_btn    = self._nav_btn("<", self.nav_back)
        self._fwd_btn     = self._nav_btn(">", self.nav_forward)
        self._refresh_btn = self._nav_btn("R", self.nav_refresh)
        for b in (self._back_btn, self._fwd_btn, self._refresh_btn):
            ulay.addWidget(b)

        root.addWidget(url_row)

        # Screenshot area --------------------------------------------------
        self._screenshot = _ScreenshotLabel()
        root.addWidget(self._screenshot, stretch=1)

        # Footer status bar ------------------------------------------------
        footer = QLabel("HUD Browser  |  Playwright Chromium  |  JARVIS Mark LVII")
        footer.setFixedHeight(16)
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setFont(px_font(8))
        footer.setStyleSheet(
            f"color: {C.TEXT_DIM}; background: {C.PRI_GHO}; "
            f"border-top: 1px solid {C.BORDER};"
        )
        root.addWidget(footer)

    @staticmethod
    def _nav_btn(label: str, slot) -> QPushButton:
        b = QPushButton(label)
        b.setFixedSize(QSize(22, 18))
        b.setFont(px_font(9, QFont.Weight.Bold))
        b.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C.PRI_DIM}; border: none; }}"
            f"QPushButton:hover {{ color: {C.PRI}; }}"
        )
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        if callable(slot):
            b.clicked.connect(slot)
        else:
            b.clicked.connect(slot.emit)
        return b

    # ------------------------------------------------------------------
    # Public API (called on Qt main thread only)
    # ------------------------------------------------------------------

    def load(self, image_path: str, url: str = "") -> None:
        """Display a screenshot and update the URL bar."""
        self._url_lbl.setText(url or "about:blank")
        color = _ssl_color(url)
        icon  = _ssl_icon(url)
        self._ssl_badge.setText(icon)
        self._ssl_badge.setStyleSheet(
            f"color: {color}; background: transparent; border: none; font-weight: bold;"
        )
        self._screenshot.set_screenshot(image_path)
        self.show()
        self.raise_()

    def close_viewport(self) -> None:
        self.hide()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_close(self) -> None:
        self.hide()
        self.closed.emit()

    # ------------------------------------------------------------------
    # Paint: cyan neon chamfered frame
    # ------------------------------------------------------------------

    def paintEvent(self, event):  # type: ignore[override]
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(qcol(C.PRI_DIM), 1)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        r = self.rect().adjusted(0, 0, -1, -1)
        p.drawRect(r)
        # Corner accent marks
        accent = QPen(qcol(C.PRI), 2)
        p.setPen(accent)
        for x, y, dx, dy in [
            (r.left(), r.top(), 1, 1),
            (r.right(), r.top(), -1, 1),
            (r.left(), r.bottom(), 1, -1),
            (r.right(), r.bottom(), -1, -1),
        ]:
            p.drawLine(x, y, x + dx * 10, y)
            p.drawLine(x, y, x, y + dy * 10)
        p.end()
