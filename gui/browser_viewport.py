"""gui/browser_viewport.py — Floating AR Inbuilt Browser Holo-Surface for JARVIS Mark LVII.

Provides the dedicated AR Web Browser Viewport widget:
- Angled 3D projection pane (-18° yaw with cyan neon edge framing).
- Glassmorphic top navigation bar with SSL padlock badge, page title, and latency metric pill.
- Cybernetic navigation controls: Back, Forward, Reload, Reader Mode, Pop-out, and Close.
- Interactive laser-beacon click indicator overlay.
- Offscreen AR pixmap rendering for projection directly into HudCanvas Layer 2.
"""

from __future__ import annotations

import time
from typing import Callable, Optional, Tuple
from urllib.parse import urlparse

from PyQt6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath,
    QPen, QPixmap, QPolygonF,
)
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy,
    QStackedWidget, QTextEdit, QVBoxLayout, QWidget,
)

from gui.style import blend_fast, chamfer, hud_font, mono_font, px_font
from gui.theme import C, qcol


class BrowserViewport(QWidget):
    """Floating AR Browser Holo-Surface and interactive viewport widget."""

    navigate_requested = pyqtSignal(str)          # Emits URL to navigate
    action_requested   = pyqtSignal(str, dict)    # Emits (action, params) e.g. ("click", {"selector": ...})
    closed             = pyqtSignal()             # Emits when browser is closed by operator

    # Default 3D spatial orientation for Layer 2 floating projection
    DEFAULT_YAW: float   = -18.0
    DEFAULT_PITCH: float = 6.0
    DEFAULT_CENTER: Tuple[float, float, float] = (180.0, 30.0, -40.0)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(420, 280)

        self._current_url: str = "https://www.google.com"
        self._page_title: str = "JARVIS Tactical Web"
        self._is_secure: bool = True
        self._latency_ms: int = 18
        self._viewport_pixmap: Optional[QPixmap] = None
        self._reader_text: str = ""
        self._reader_active: bool = False

        # Laser beacon highlight state for clicks/inputs
        self._beacon_pos: Optional[QPointF] = None
        self._beacon_radius: float = 0.0
        self._beacon_alpha: float = 0.0
        self._beacon_timer = QTimer(self)
        self._beacon_timer.setInterval(20)
        self._beacon_timer.timeout.connect(self._step_beacon)

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # ── Glassmorphic Tactical Navigation Bar ──────────────────────────────
        self._nav_bar = QWidget()
        self._nav_bar.setFixedHeight(34)
        self._nav_bar.setStyleSheet(f"""
            QWidget {{
                background: {blend_fast(C.BG, 0.85).name()};
                border: 1px solid {blend_fast(C.BORDER, 0.70).name()};
                border-bottom: 2px solid {blend_fast(C.PRI, 0.80).name()};
            }}
        """)
        nav_layout = QHBoxLayout(self._nav_bar)
        nav_layout.setContentsMargins(6, 2, 6, 2)
        nav_layout.setSpacing(6)

        # Navigation Buttons (Back, Forward, Reload)
        self._btn_back = self._create_nav_btn("◀", "Go Back", self._on_back)
        self._btn_fwd  = self._create_nav_btn("▶", "Go Forward", self._on_fwd)
        self._btn_reload = self._create_nav_btn("⟳", "Reload Page", self._on_reload)
        nav_layout.addWidget(self._btn_back)
        nav_layout.addWidget(self._btn_fwd)
        nav_layout.addWidget(self._btn_reload)

        # SSL Padlock & Protocol Badge
        self._lbl_ssl = QLabel("🔒 HTTPS")
        self._lbl_ssl.setFont(mono_font(8, QFont.Weight.Bold))
        self._lbl_ssl.setStyleSheet(f"color: {C.GREEN}; background: transparent; border: none; padding: 0 4px;")
        nav_layout.addWidget(self._lbl_ssl)

        # Monospace URL Address Bar
        self._txt_url = QLineEdit(self._current_url)
        self._txt_url.setFont(mono_font(8.5))
        self._txt_url.setStyleSheet(f"""
            QLineEdit {{
                background: {blend_fast(C.PANEL2, 0.90).name()};
                color: {C.WHITE};
                border: 1px solid {blend_fast(C.PRI_DIM, 0.50).name()};
                padding: 2px 8px;
            }}
            QLineEdit:focus {{
                border: 1px solid {C.PRI};
                background: {blend_fast(C.PANEL, 0.95).name()};
            }}
        """)
        self._txt_url.returnPressed.connect(self._on_url_entered)
        nav_layout.addWidget(self._txt_url, stretch=1)

        # Latency Metric Pill
        self._lbl_latency = QLabel(f"⚡ {self._latency_ms}ms | 1080p")
        self._lbl_latency.setFont(mono_font(8, QFont.Weight.Medium))
        self._lbl_latency.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
        nav_layout.addWidget(self._lbl_latency)

        # Action Buttons (Reader Mode, Close)
        self._btn_reader = self._create_nav_btn("📖", "Toggle Reader Mode", self._toggle_reader)
        self._btn_close  = self._create_nav_btn("✕", "Close Browser Surface", self._on_close)
        nav_layout.addWidget(self._btn_reader)
        nav_layout.addWidget(self._btn_close)

        layout.addWidget(self._nav_bar)

        # ── Viewport Stack (Web Viewport / Reader Mode) ──────────────────────
        self._stack = QStackedWidget()
        
        # Page 0: Rendered Web Frame Display
        self._web_display = QLabel()
        self._web_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._web_display.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._web_display.setStyleSheet(f"background: {blend_fast(C.BG, 0.95).name()}; border: none;")
        self._stack.addWidget(self._web_display)

        # Page 1: Reader Mode Slide-Out / Text Panel
        self._txt_reader = QTextEdit()
        self._txt_reader.setReadOnly(True)
        self._txt_reader.setFont(hud_font(10))
        self._txt_reader.setStyleSheet(f"""
            QTextEdit {{
                background: {blend_fast(C.BG, 0.92).name()};
                color: {C.WHITE};
                border: 1px solid {blend_fast(C.PRI, 0.40).name()};
                padding: 12px;
                line-height: 1.5;
            }}
        """)
        self._stack.addWidget(self._txt_reader)

        layout.addWidget(self._stack, stretch=1)

    def _create_nav_btn(self, icon: str, tooltip: str, callback: Callable[[], None]) -> QPushButton:
        btn = QPushButton(icon)
        btn.setToolTip(tooltip)
        btn.setFixedSize(24, 22)
        btn.setFont(hud_font(8, QFont.Weight.Bold))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {blend_fast(C.PANEL, 0.80).name()};
                color: {C.PRI};
                border: 1px solid {blend_fast(C.BORDER, 0.60).name()};
                padding: 0;
            }}
            QPushButton:hover {{
                background: {blend_fast(C.PRI_GHO, 0.90).name()};
                color: {C.WHITE};
                border-color: {C.PRI};
            }}
            QPushButton:pressed {{
                background: {C.PRI};
                color: {C.BG};
            }}
        """)
        btn.clicked.connect(callback)
        return btn

    def set_viewport_frame(self, pixmap: QPixmap, url: str = "", title: str = "", latency_ms: int = 18) -> None:
        """Updates the active web viewport with a fresh frame from Playwright."""
        self._viewport_pixmap = pixmap
        if url:
            self._current_url = url
            self._txt_url.setText(url)
            self._update_ssl_badge(url)
        if title:
            self._page_title = title
        self._latency_ms = max(1, latency_ms)
        self._lbl_latency.setText(f"⚡ {self._latency_ms}ms | 1080p")

        # Scale pixmap smoothly to fit web display area
        w, h = self._web_display.width(), self._web_display.height()
        if w > 20 and h > 20 and not pixmap.isNull():
            scaled = pixmap.scaled(
                w, h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._web_display.setPixmap(scaled)
        else:
            self._web_display.setPixmap(pixmap)

    def trigger_interaction_beacon(self, normalized_x: float, normalized_y: float) -> None:
        """Fires an expanding laser beacon at normalized web coordinates (0.0 to 1.0)."""
        w, h = float(self._web_display.width()), float(self._web_display.height())
        px = normalized_x * w
        py = normalized_y * h
        self._beacon_pos = QPointF(px, py)
        self._beacon_radius = 4.0
        self._beacon_alpha = 1.0
        self._beacon_timer.start()

    def set_reader_content(self, title: str, markdown_content: str) -> None:
        """Populates reader mode with extracted article text."""
        self._reader_text = markdown_content
        self._txt_reader.setMarkdown(f"# {title}\n\n{markdown_content}")
        self._stack.setCurrentIndex(1)
        self._reader_active = True

    def _step_beacon(self) -> None:
        self._beacon_radius += 2.5
        self._beacon_alpha -= 0.08
        if self._beacon_alpha <= 0.0 or self._beacon_radius > 45.0:
            self._beacon_timer.stop()
            self._beacon_pos = None
        self._web_display.update()

    def _update_ssl_badge(self, url: str) -> None:
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        host = (parsed.hostname or "").lower()

        if host in ("localhost", "127.0.0.1") or host.startswith("192.168."):
            self._lbl_ssl.setText("🔌 LOCAL")
            self._lbl_ssl.setStyleSheet(f"color: {C.ACC}; background: transparent; border: none;")
        elif scheme == "https":
            self._lbl_ssl.setText("🔒 HTTPS")
            self._lbl_ssl.setStyleSheet(f"color: {C.GREEN}; background: transparent; border: none;")
        else:
            self._lbl_ssl.setText("⚠️ HTTP")
            self._lbl_ssl.setStyleSheet(f"color: {C.RED}; background: transparent; border: none;")

    def _on_url_entered(self) -> None:
        url = self._txt_url.text().strip()
        if not url:
            return
        if not (url.startswith("http://") or url.startswith("https://") or url.startswith("file://")):
            url = f"https://{url}"
        self._current_url = url
        self._txt_url.setText(url)
        self.navigate_requested.emit(url)

    def _on_back(self) -> None:
        self.action_requested.emit("back", {})

    def _on_fwd(self) -> None:
        self.action_requested.emit("forward", {})

    def _on_reload(self) -> None:
        self.action_requested.emit("reload", {})

    def _toggle_reader(self) -> None:
        if self._reader_active:
            self._stack.setCurrentIndex(0)
            self._reader_active = False
        else:
            if self._reader_text:
                self._stack.setCurrentIndex(1)
                self._reader_active = True
            else:
                self.action_requested.emit("read_content", {})

    def _on_close(self) -> None:
        self.closed.emit()

    def render_ar_pixmap(self, width: int = 480, height: int = 300) -> QPixmap:
        """Renders the browser viewport into an offscreen AR pixmap for 3D Layer 2 projection."""
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.GlobalColor.transparent)

        p = QPainter(pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Background chamfered glass slab
        rect = QRectF(2, 2, width - 4, height - 4)
        poly = chamfer(rect, cut=8.0, corners=("tl", "br"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(blend_fast(C.BG, 0.88)))
        p.drawPolygon(poly)

        # 2. Glowing cyan neon frame
        neon_col = blend_fast(C.PRI, 0.85)
        p.setPen(QPen(neon_col, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPolygon(poly)

        # 3. Mini Header Bar with SSL & URL
        hdr_rect = QRectF(4, 4, width - 8, 22)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(blend_fast(C.PANEL2, 0.90)))
        p.drawRect(hdr_rect)

        # SSL dot & URL text
        p.setFont(mono_font(7, QFont.Weight.Bold))
        ssl_col = qcol(C.GREEN) if "https" in self._current_url else qcol(C.ACC)
        p.setBrush(QBrush(ssl_col))
        p.drawEllipse(QPointF(12, 15), 3, 3)

        p.setPen(QPen(qcol(C.WHITE), 1))
        display_url = self._current_url[:48] + ("…" if len(self._current_url) > 48 else "")
        p.drawText(QRectF(22, 5, width - 80, 20), Qt.AlignmentFlag.AlignVCenter, display_url)

        # Latency
        p.setFont(mono_font(6.5))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(width - 70, 5, 62, 20), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{self._latency_ms}ms")

        # 4. Viewport image content
        content_rect = QRect(6, 28, width - 12, height - 34)
        if self._viewport_pixmap is not None and not self._viewport_pixmap.isNull():
            scaled = self._viewport_pixmap.scaled(
                content_rect.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            # Clip to content box
            p.save()
            p.setClipRect(content_rect)
            # Center cropped
            dx = (content_rect.width() - scaled.width()) // 2
            dy = (content_rect.height() - scaled.height()) // 2
            p.drawPixmap(content_rect.x() + dx, content_rect.y() + dy, scaled)
            p.restore()
        else:
            # Idle placeholder grid
            p.setPen(QPen(blend_fast(C.PRI_DIM, 0.20), 1))
            for y_line in range(content_rect.top() + 15, content_rect.bottom(), 20):
                p.drawLine(content_rect.left(), y_line, content_rect.right(), y_line)
            p.setFont(mono_font(8, QFont.Weight.Medium))
            p.setPen(QPen(blend_fast(C.PRI, 0.70), 1))
            p.drawText(content_rect, Qt.AlignmentFlag.AlignCenter, "◈  AWAITING PLAYWRIGHT VIEWPORT STREAM  ◈")

        # 5. Laser beacon if active
        if self._beacon_pos is not None:
            bx = (self._beacon_pos.x() / max(1.0, float(self._web_display.width()))) * float(content_rect.width()) + content_rect.left()
            by = (self._beacon_pos.y() / max(1.0, float(self._web_display.height()))) * float(content_rect.height()) + content_rect.top()
            beacon_col = blend_fast(C.ACC, self._beacon_alpha)
            p.setPen(QPen(beacon_col, 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(bx, by), self._beacon_radius * 0.7, self._beacon_radius * 0.7)

        p.end()
        return pixmap
