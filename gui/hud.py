"""gui/hud.py — The centre of the HUD: the avatar or the reactor core, the state line and the waveform.

Split out of ui.py in Mark LVII; behaviour unchanged."""
from __future__ import annotations

import json
import math
import os
import platform
import random
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil

from PyQt6.QtCore import (
    QEasingCurve, QLineF, QMimeData, QObject, QParallelAnimationGroup, QPointF,
    QPoint, QPropertyAnimation, QRect, QRectF, QSize, QSizeF, Qt, QTimer,
    QUrl, pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush, QColor, QConicalGradient, QDragEnterEvent, QDropEvent, QFont,
    QFontDatabase, QKeySequence, QLinearGradient, QMouseEvent, QPainter, QPainterPath,
    QPen, QPixmap, QRadialGradient, QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPushButton, QScrollArea, QSizePolicy, QSplitter,
    QGraphicsScene, QGraphicsView, QGraphicsPixmapItem,
    QStackedWidget, QTextEdit, QVBoxLayout, QWidget, QProgressBar, QSlider,
)

import numpy as np

from gui.theme import (
    C,
    HoloAvatar,
    qcol,
)

from gui.style import blend, chamfer, px_font, with_alpha
from gui.ambient import AmbientLighting, AIWaveformVisualizer, CognitiveTelemetry
from gui.eq_ribbon import ConcentricAudioEqualizer
from gui.ar_engine import (
    Camera3D,
    generate_orbit_ring,
    generate_spatial_grid,
    perspective_project,
    project_holo_pane,
)

try:
    from gui.reactor import Reactor3D
except Exception:      # pragma: no cover — the classic core still draws
    Reactor3D = None


# Which hud_style values draw the avatar (as opposed to the reactor core).
_FACE_STYLES = ("face", "face_solid", "face_holo", "face_hologram", "face_matrix", "matrix", "hologram")


class HudCanvas(QWidget):
    radial_requested = pyqtSignal(QPoint)

    def __init__(self, face_path: str, assistant_name: str = "J.A.R.V.I.S", parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.muted    = False
        self.speaking = False
        self.state    = "INITIALISING"
        self._assistant_name = assistant_name

        # The holographic head that fills the HUD. If it could not be imported
        # we fall back to the old glowing core so the panel is never empty.
        self._avatar = None
        if HoloAvatar is not None:
            try:
                self._avatar = HoloAvatar()
            except Exception:
                self._avatar = None

        # The reactor core in three dimensions (gui/reactor.py). The flat ring
        # stack it replaced is kept whole as _paint_core_classic, and it is
        # what draws if the model could not be built.
        self._reactor = None
        if Reactor3D is not None:
            try:
                self._reactor = Reactor3D()
            except Exception:
                self._reactor = None

        # Which centrepiece to draw. Read once here and changed live by the
        # settings toggle; the avatar object is kept either way so switching
        # back is instant and costs no reload.
        try:
            from memory.config_manager import get_hud_style
            self.hud_style = get_hud_style()
        except Exception:
            self.hud_style = "face"
        self._core_phase = 0.0

        self._tick       = 0
        self._scale      = 1.0
        self._tgt_scale  = 1.0
        self._halo       = 55.0
        self._tgt_halo   = 55.0
        self._last_t     = time.time()
        self._step_t     = time.time()
        self._blink      = True
        self._blink_tick = 0

        # Rescaled-face cache: the smooth rescale is expensive, so we keep the
        # last result and only rebuild it when the (quantised) size changes.

        # Static grid-dot layer, pre-rendered once per size/theme into a pixmap
        # so paintEvent blits it in one call instead of thousands of drawPoint()s.
        self._grid_cache: QPixmap | None = None
        self._grid_key = None
        # Repaint throttle counter (idle frames drop to ~20 Hz — see _step()).
        self._paint_tick = 0

        # Live audio reactivity: _live_amp is written from the audio threads
        # (0.0–1.0), _amp_disp is the smoothed value the paint code reads.
        self._live_amp  = 0.0
        self._amp_disp  = 0.0
        # (frames, start_time, hop) posted by the playback thread — see
        # push_visemes(). None means "no schedule; use the plain level".
        self._visemes = None
        self._vis_i = None        # first schedule frame not yet handed to the mouth
        self._base_scale = 1.0    # slow "breathing" target; amp is added per-frame
        self._base_halo  = 55.0

        # Ambient lighting, dynamic AI audio visualizer & telemetry
        self._ambient = AmbientLighting()
        self._visualizer = AIWaveformVisualizer()
        self._telemetry = CognitiveTelemetry()
        self._eq_ribbon = ConcentricAudioEqualizer()

        # ── 3D AR Holographic Spatial Engine & Depth Layers ──────────────────
        self.setMouseTracking(True)
        self._camera = Camera3D(fov=55.0, distance=650.0)
        self._cursor_pos: Optional[QPointF] = None
        self._cursor_norm = (0.0, 0.0)
        self._active_holo_panes: dict = {}
        self._avatar_dock: float = 0.0
        self._avatar_tgt_dock: float = 0.0

        # Layer 0: Spatial floor grid & drifting 3D space dust particles
        self._grid_starts, self._grid_ends = generate_spatial_grid(
            width=1400.0, depth=1400.0, spacing=90.0, y_floor=-240.0
        )
        self._dust_particles = np.random.uniform(
            low=[-450, -250, 50], high=[450, 250, 550], size=(36, 3)
        ).astype(np.float32)

        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._tmr.start(16)

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        self._cursor_pos = e.position()
        w, h = max(1.0, float(self.width())), max(1.0, float(self.height()))
        nx = (self._cursor_pos.x() / w) * 2.0 - 1.0
        ny = (self._cursor_pos.y() / h) * 2.0 - 1.0
        self._cursor_norm = (nx, ny)
        self._camera.set_gaze(nx, ny, factor=12.0)
        if self._avatar is not None:
            try:
                self._avatar.glance(nx * 0.45, ny * 0.35, hold=0.25)
            except Exception:
                pass

    def leaveEvent(self, e) -> None:
        self._cursor_pos = None
        self._camera.set_gaze(0.0, 0.0, factor=0.0)

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.RightButton:
            self.radial_requested.emit(e.globalPosition().toPoint())
        super().mousePressEvent(e)

    def register_holo_pane(
        self,
        pane_id: str,
        title: str,
        center: Tuple[float, float, float] = (180.0, 30.0, -40.0),
        width: float = 240.0,
        height: float = 150.0,
        yaw: float = -18.0,
        pitch: float = 6.0,
        pixmap: Optional[QPixmap] = None,
        focused: bool = False,
    ) -> None:
        """Registers or updates a floating AR holographic surface in Layer 2."""
        existing = self._active_holo_panes.get(pane_id, {})
        cur_progress = existing.get("focus_progress", 1.0 if focused else 0.0)
        self._active_holo_panes[pane_id] = {
            "title": title,
            "center": center,
            "default_center": center,
            "width": width,
            "default_width": width,
            "height": height,
            "default_height": height,
            "yaw": yaw,
            "default_yaw": yaw,
            "pitch": pitch,
            "default_pitch": pitch,
            "pixmap": pixmap,
            "focused": focused,
            "focus_progress": cur_progress,
            "tgt_focus": 1.0 if focused else 0.0,
        }
        if focused:
            self.set_avatar_docked(True)

    def set_holo_pane_focus(self, pane_id: str, focused: bool) -> None:
        """Smoothly transitions an AR surface between companion mode and center stage."""
        pane = self._active_holo_panes.get(pane_id)
        if pane is not None:
            pane["focused"] = focused
            pane["tgt_focus"] = 1.0 if focused else 0.0
        any_focused = any(p.get("tgt_focus", 0.0) > 0.5 for p in self._active_holo_panes.values())
        self.set_avatar_docked(any_focused)

    def set_avatar_docked(self, docked: bool) -> None:
        """Docks avatar to upper-right orbital node to give center stage to AR workspace."""
        self._avatar_tgt_dock = 1.0 if docked else 0.0

    def unregister_holo_pane(self, pane_id: str) -> None:
        """Removes an AR holographic surface from Layer 2."""
        self._active_holo_panes.pop(pane_id, None)
        any_focused = any(p.get("tgt_focus", 0.0) > 0.5 for p in self._active_holo_panes.values())
        self.set_avatar_docked(any_focused)

    def glance(self, dx: float, dy: float, hold: float = 1.1) -> None:
        """Ask the avatar to look somewhere for a moment (see HoloAvatar.glance)."""
        try:
            if self._avatar is not None:
                self._avatar.glance(dx, dy, hold)
        except Exception:
            pass

    def push_visemes(self, frames, hop: float, at: float) -> None:
        """Thread-safe: hand over a schedule of (level, openness, width) frames.

        The playback thread writes up to 200 ms of audio in one go, so a single
        averaged level would only move the mouth five times a second — enough to
        flap, nowhere near enough to articulate. It instead posts the whole
        slice's worth of 20 ms frames here and `_step()` plays them out against
        the wall clock, in step with the audio going to the speakers.

        `at` is the wall-clock time this batch will *begin to sound*, which the
        caller tracks as a playback cursor. It is not the time of the call, and
        the difference is the whole point: `stream.write` returns once the buffer
        accepts the samples, so consecutive batches are handed over far faster
        than they play. Anchoring each one to "now" made every batch start while
        its predecessor was still sounding, so each schedule replaced the last
        after a couple of frames and the mouth only ever played the opening
        instant of every 200 ms — the reason it did not match the words.

        Successive batches are therefore *appended* into one continuous
        timeline, not swapped in. A paragraph is one schedule; the mouth stops
        falling into a gap at every chunk boundary and having to climb back out.
        """
        try:
            if not frames:
                return
            hop = max(1e-3, float(hop))
            at = float(at)
            new = list(frames)
            cur = self._visemes
            if cur is not None:
                old, t0, ohop = cur
                if abs(ohop - hop) < 1e-6:
                    # Where in the existing timeline does this batch land?
                    i = int(round((at - t0) / hop))
                    if 0 <= i <= len(old) + 1:
                        # Continues (or slightly overlaps) what is already
                        # queued: extend rather than restart. Drop whatever has
                        # already been played so the list cannot grow without
                        # bound over a long reply.
                        merged = old[:i] + new
                        played = int((time.time() - t0) / hop) - 2
                        if played > 60:
                            merged = merged[played:]
                            t0 += played * hop
                            if self._vis_i is not None:
                                self._vis_i = max(0, self._vis_i - played)
                        self._visemes = (merged, t0, hop)
                        return
            self._visemes = (new, at, hop)
            self._vis_i = None
        except Exception:
            pass

    def set_audio_level(self, level: float) -> None:
        """Thread-safe entry point for the audio threads. Stores the louder of
        the incoming level and the current value so brief gaps between chunks
        don't make the waveform stutter; _step() decays it back down."""
        try:
            lv = float(level)
        except (TypeError, ValueError):
            return
        if lv < 0.0:
            lv = 0.0
        elif lv > 1.0:
            lv = 1.0
        if lv > self._live_amp:
            self._live_amp = lv

    def _make_grid(self, W: int, H: int) -> QPixmap:
        """Pre-render the static backdrop — atmosphere, workshop floor, bokeh
        and the screen frame — once per size and theme, so paintEvent blits one
        pixmap instead of redrawing a scene every frame.

        The floor is a perspective grid receding to a horizon with two rows of
        lights along it, after the workshop the HUD is modelled on; the bokeh
        are out-of-focus lights, mostly cool with a few warm. The layout is
        seeded, so it is the same scene on every launch."""
        W, H = max(1, W), max(1, H)
        pm = QPixmap(W, H)
        pm.fill(qcol(C.BG))
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx = W / 2

        g = QRadialGradient(cx, H * 0.42, max(W, H) * 0.62)
        g.setColorAt(0.0, blend(C.PRI, 0.10))
        g.setColorAt(0.55, blend(C.PRI, 0.035))
        g.setColorAt(1.0, qcol(C.BG))
        p.fillRect(QRectF(0, 0, W, H), QBrush(g))

        hy, vy = H * 0.70, H * 0.52
        p.save()
        p.setClipRect(QRectF(0, hy, W, H - hy))
        for i in range(-14, 15):
            x = cx + i * W * 0.11
            p.setPen(QPen(blend(C.PRI, 0.10 * (1 - abs(i) / 16)), 1))
            p.drawLine(QLineF(cx + (x - cx) * 0.05, vy, x, H))
        y, step = hy, 5.0
        while y < H:
            k = (y - hy) / max(1.0, H - hy)
            p.setPen(QPen(blend(C.PRI, 0.03 + 0.09 * k), 1))
            p.drawLine(QLineF(0, y, W, y))
            y += step
            step *= 1.28
        p.setPen(Qt.PenStyle.NoPen)
        for side in (-1, 1):
            for j in range(3, 12):
                t = j / 11
                x = cx + side * (W * 0.16 + t * t * W * 0.26)
                yy = hy + (H - hy) * t * t
                rr = (0.6 + 1.4 * t) * 3
                gg = QRadialGradient(x, yy, rr)
                gg.setColorAt(0.0, with_alpha(C.WHITE, 0.30 * (0.3 + t)))
                gg.setColorAt(0.35, with_alpha(C.PRI, 0.12 * (0.3 + t)))
                gg.setColorAt(1.0, with_alpha(C.PRI, 0.0))
                p.setBrush(QBrush(gg))
                p.drawEllipse(QPointF(x, yy), rr, rr)
        p.restore()

        lg = QLinearGradient(0, 0, W, 0)
        lg.setColorAt(0.0, with_alpha(C.PRI, 0.0))
        lg.setColorAt(0.5, with_alpha(C.PRI, 0.35))
        lg.setColorAt(1.0, with_alpha(C.PRI, 0.0))
        p.setPen(QPen(QBrush(lg), 1))
        p.drawLine(QLineF(0, hy, W, hy))

        rnd = random.Random(57)
        p.setPen(Qt.PenStyle.NoPen)
        for _ in range(int(W * H / 9000)):
            x, yy = rnd.uniform(0, W), rnd.uniform(0, H * 0.72)
            rr = rnd.uniform(0.8, 3.2) * 3
            warm = rnd.random() < 0.12
            c = C.ACC2 if warm else (C.WHITE if rnd.random() < 0.3 else C.PRI)
            a = rnd.uniform(0.08, 0.40)
            gg = QRadialGradient(x, yy, rr)
            gg.setColorAt(0.0, with_alpha(c, a))
            gg.setColorAt(1.0, with_alpha(c, 0.0))
            p.setBrush(QBrush(gg))
            p.drawEllipse(QPointF(x, yy), rr, rr)

        # the screen's edge: a thin chamfered frame with lit corners
        m, cut, arm = 6, 16, 46
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(blend(C.PRI, 0.20), 1))
        p.drawPolygon(chamfer(QRectF(m, m, W - 2 * m, H - 2 * m), cut, ("tl", "tr", "br", "bl")))
        p.setPen(QPen(blend(C.PRI, 0.9), 1.8))
        for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            x0 = m if sx > 0 else W - m
            y0 = m if sy > 0 else H - m
            p.drawLine(QLineF(x0, y0 + sy * (cut + arm), x0, y0 + sy * cut))
            p.drawLine(QLineF(x0, y0 + sy * cut, x0 + sx * cut, y0))
        p.setFont(px_font(10, QFont.Weight.DemiBold, spacing=2.2))
        p.setPen(QPen(blend(C.PRI, 0.55)))
        p.drawText(QRectF(m + 24, m + 8, 260, 16), Qt.AlignmentFlag.AlignVCenter, "VOICE INTERFACE")
        p.end()
        return pm

    def _step(self):
        self._tick += 1
        now = time.time()

        # ── Live audio reactivity ────────────────────────────────────────────
        # A viseme schedule, if one is playing, gives both the level and the
        # mouth shape for this exact instant; otherwise fall back to the peak
        # level the audio threads pushed in.
        v_open = v_wide = v_level = None
        v_seq = None
        sched = self._visemes
        if sched is not None:
            frames, t0, hop = sched
            i = int((now - t0) / hop)
            if 0 <= i < len(frames):
                # Hand over *every* frame since the last tick, not just the one
                # under the cursor. This timer runs at 60 Hz but the paint is
                # throttled and the machine may be busy, so a tick can span two
                # or three 20 ms frames — and a consonant closure is only two
                # frames long. Sampling one and discarding the rest is how the
                # closures between words went missing.
                j = self._vis_i if self._vis_i is not None else i
                v_seq = frames[max(0, j):i + 1]
                self._vis_i = max(j, i + 1)
                v_level, v_open, v_wide = frames[i]
                if v_seq:
                    peak = max(f[0] for f in v_seq)
                    if peak > self._live_amp:
                        self._live_amp = peak
            elif i >= len(frames):
                self._visemes = None        # schedule spent
                self._vis_i = None

        # Audio threads push peaks into _live_amp; decay it toward silence so
        # gaps between chunks fade out instead of freezing, then smooth it.
        self._live_amp *= 0.86
        self._amp_disp += (self._live_amp - self._amp_disp) * 0.45
        amp = self._amp_disp

        # The avatar animates off the very same smoothed level the waveform
        # uses — one audio source, so the mouth can never drift out of sync.
        dt = now - self._step_t
        self._step_t = now
        # Integrated, not derived from absolute time: multiplying wall-clock by
        # a rate that changes with state jumps the rings the instant JARVIS
        # starts talking. Same lesson the head's sway taught.
        self._core_phase += min(0.10, max(0.0, dt))

        if self._avatar is not None and self.hud_style in _FACE_STYLES:
            self._avatar.step(dt, amp, speaking=self.speaking,
                              muted=self.muted, state=self.state,
                              v_open=v_open, v_wide=v_wide or 0.0,
                              v_level=v_level, v_seq=v_seq,
                              v_hop=(sched[2] if sched is not None else 0.02))
        else:
            if self._reactor is not None:
                self._reactor.step(dt, self.speaking,
                                   self.state in ("THINKING", "PROCESSING"), self.muted)
            # Fallback core: slow "breathing" base target, lifted by the level.
            if now - self._last_t > (0.12 if self.speaking else 0.5):
                if self.speaking:
                    self._base_scale = 1.03
                    self._base_halo  = 122.0
                elif self.muted:
                    self._base_scale = random.uniform(0.998, 1.002)
                    self._base_halo  = random.uniform(15, 28)
                else:
                    self._base_scale = random.uniform(1.001, 1.008)
                    self._base_halo  = random.uniform(48, 68)
                self._last_t = now

            if self.muted:
                self._tgt_scale, self._tgt_halo = self._base_scale, self._base_halo
            elif self.speaking:
                self._tgt_scale = self._base_scale + amp * 0.13
                self._tgt_halo  = self._base_halo  + amp * 95.0
            else:
                self._tgt_scale = self._base_scale + amp * 0.06
                self._tgt_halo  = self._base_halo  + amp * 75.0

            sp = 0.38 if self.speaking else (0.30 if amp > 0.02 else 0.15)
            self._scale += (self._tgt_scale - self._scale) * sp
            self._halo  += (self._tgt_halo  - self._halo)  * sp

        # Step ambient lighting, AI spectrum physics, and telemetry
        self._ambient.step(dt, self.state, self.speaking, self.muted, amp)
        self._visualizer.step(dt, self.state, self.speaking, self.muted, amp)
        self._telemetry.step(dt, self.state, self.speaking)
        self._eq_ribbon.step(dt, self.state, self.speaking, self.muted, amp)

        # Step 3D drifting space dust particles (Layer 0)
        if hasattr(self, "_dust_particles") and self._dust_particles is not None:
            self._dust_particles[:, 2] -= 0.65
            reset_mask = self._dust_particles[:, 2] < 20.0
            if np.any(reset_mask):
                cnt = int(np.sum(reset_mask))
                self._dust_particles[reset_mask, 2] = np.random.uniform(420, 550, size=cnt)
                self._dust_particles[reset_mask, 0] = np.random.uniform(-450, 450, size=cnt)
                self._dust_particles[reset_mask, 1] = np.random.uniform(-250, 250, size=cnt)

        # Step Avatar docking transition to orbital node
        if hasattr(self, "_avatar_dock"):
            if abs(self._avatar_dock - self._avatar_tgt_dock) > 1e-4:
                self._avatar_dock += (self._avatar_tgt_dock - self._avatar_dock) * 0.16
                if abs(self._avatar_dock - self._avatar_tgt_dock) < 0.005:
                    self._avatar_dock = self._avatar_tgt_dock

        # Step Layer 2 Holo Panes focus / center-stage transition
        if hasattr(self, "_active_holo_panes"):
            for pane in self._active_holo_panes.values():
                tgt = float(pane.get("tgt_focus", 0.0))
                cur = float(pane.get("focus_progress", 0.0))
                if abs(cur - tgt) > 1e-4:
                    pane["focus_progress"] = cur + (tgt - cur) * 0.16
                    if abs(pane["focus_progress"] - tgt) < 0.005:
                        pane["focus_progress"] = tgt

        self._blink_tick += 1
        if self._blink_tick >= 38:
            self._blink = not self._blink
            self._blink_tick = 0
            _blinked = True
        else:
            _blinked = False

        # ── Dynamic Level of Detail (LOD) Framerate Governor ─────────────────
        # Active: ~60 Hz (16ms) during speaking, listening, thinking, or interaction
        # Idle: ~24 Hz (42ms) during quiet background breathing (saving 60%+ CPU wakeups)
        # Minimized / Occluded: 0 FPS (500ms sleep heartbeat, 0% CPU render overhead)
        on_screen = self._on_screen()
        if not on_screen:
            if self._tmr.interval() != 500:
                self._tmr.setInterval(500)
            return

        active = (
            self.speaking
            or amp > 0.02
            or self.state in ("THINKING", "PROCESSING", "LISTENING")
            or (hasattr(self, "_cursor_pos") and self._cursor_pos is not None)
        )
        desired_interval = 16 if active else 42
        if self._tmr.interval() != desired_interval:
            self._tmr.setInterval(desired_interval)

        self.update()

    def showEvent(self, e) -> None:
        super().showEvent(e)
        if hasattr(self, "_tmr"):
            self._tmr.setInterval(16)
            if not self._tmr.isActive():
                self._tmr.start()

    def hideEvent(self, e) -> None:
        super().hideEvent(e)
        if hasattr(self, "_tmr"):
            self._tmr.setInterval(500)

    def _on_screen(self) -> bool:
        """True only when this canvas can actually be seen by the user."""
        try:
            if not self.isVisible():
                return False
            win = self.window()
            return not (win.isMinimized() or win.isHidden())
        except Exception:
            return True      # never let a visibility check stop the HUD drawing

    # ── reactor core ─────────────────────────────────────────────────────────
    # The centrepiece for anyone who did not want a face looking back at them.
    # Built from the same budget as the head — software QPainter, no GPU — and
    # from the same principle: everything on it means something. The rings turn
    # at a rate the state sets, the spectrum ring is the real audio level, and
    # the core brightens with the voice. Nothing here is decoration that moves
    # for its own sake, which is what made the old glowing orb feel dead.

    def _core_colours(self):
        if self.muted:
            return qcol(C.MUTED_C), qcol(C.MUTED_C)
        if self.speaking:
            return qcol(C.PRI), qcol(C.ACC)
        if self.state in ("THINKING", "PROCESSING"):
            return qcol(C.PRI), qcol(C.ACC2)
        if self.state == "LISTENING":
            return qcol(C.PRI), qcol(C.GREEN)
        return qcol(C.PRI), qcol(C.PRI_DIM)

    def _paint_core(self, p: QPainter, cx: float, cy: float, r: float,
                    W: float = 0.0, H: float = 0.0):
        """Draw the reactor core centred on (cx, cy) with core radius r.

        The 3-D model when it was built, the flat ring stack otherwise. Going
        back to the flat one for good is this method calling
        _paint_core_classic, which is kept whole for exactly that."""
        if self._reactor is None:
            return self._paint_core_classic(p, cx, cy, r, W, H)
        main, acc = self._core_colours()
        amp = self._amp_disp
        live = (self.speaking or amp > 0.04) and not self.muted
        self._reactor.paint(p, cx, cy, r, main, acc, qcol(C.WHITE), amp, live,
                            self._assistant_name or "")

    def _paint_core_classic(self, p: QPainter, cx: float, cy: float, r: float,
                            W: float = 0.0, H: float = 0.0):
        """Draw the reactor at (cx, cy) with outer radius r, using the whole
        canvas (W x H) for the marks that frame it."""
        main, acc = self._core_colours()
        bg = qcol(C.BG)
        amp = self._amp_disp
        t = self._core_phase
        live = (self.speaking or amp > 0.04) and not self.muted

        def blend(col: QColor, a: float) -> QColor:
            """Pre-mix onto the background instead of asking Qt to composite.
            The raster engine's opaque path is several times faster than its
            translucent one, and everything here is a line or an arc."""
            k = max(0.0, min(1.0, a))
            return QColor(int(bg.red()   + (col.red()   - bg.red())   * k),
                          int(bg.green() + (col.green() - bg.green()) * k),
                          int(bg.blue()  + (col.blue()  - bg.blue())  * k))

        p.setBrush(Qt.BrushStyle.NoBrush)

        # 1. The atmosphere. One radial gradient doing what a stack of discs did
        #    badly: a wide, soft body of light that gives the thing presence
        #    before any detail is read. This single element decides whether the
        #    HUD looks vast or looks small, so it is drawn first and drawn big.
        # Concentrated rather than spread: a gradient reaching the outer rim
        # washes the whole disc a flat dim blue and reads as fog. Ending it at
        # two thirds leaves it a body of light with somewhere to fall off to,
        # which is what makes it look lit rather than tinted.
        lift = 1.0 + 0.55 * amp + (0.18 if self.speaking else 0.0)
        p.setPen(Qt.PenStyle.NoPen)
        for gr, a0, a1 in ((r * 0.70, 0.30, 0.0), (r * 0.34, 0.34, 0.0)):
            g = QRadialGradient(cx, cy, gr)
            g.setColorAt(0.00, blend(main, min(0.95, a0 * lift)))
            g.setColorAt(0.45, blend(main, min(0.95, a0 * lift * 0.52)))
            g.setColorAt(0.78, blend(main, min(0.95, a0 * lift * 0.18)))
            g.setColorAt(1.00, blend(main, a1))
            p.setBrush(QBrush(g))
            p.drawEllipse(QRectF(cx - gr, cy - gr, gr * 2, gr * 2))
        p.setBrush(Qt.BrushStyle.NoBrush)

        # 2. Frame marks at the corners of the whole canvas, not of the circle.
        #    They are what set the scale: the eye reads the reactor as filling
        #    the room rather than sitting in the middle of it.
        if W > 40 and H > 40:
            m, arm = min(W, H) * 0.035, min(W, H) * 0.055
            p.setPen(QPen(blend(main, 0.45), 1.4))
            for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
                x = cx + sx * (W / 2 - m)
                y = cy + sy * (H / 2 - m)
                p.drawLine(QLineF(x, y, x - sx * arm, y))
                p.drawLine(QLineF(x, y, x, y - sy * arm))

        # 3. Crosshair across the full canvas, broken around the core so it
        #    frames the reactor rather than crossing it.
        p.setPen(QPen(blend(main, 0.16), 1))
        gap = r * 0.62
        if W > 40:
            p.drawLine(QLineF(cx - W / 2, cy, cx - gap, cy))
            p.drawLine(QLineF(cx + gap, cy, cx + W / 2, cy))
        if H > 40:
            p.drawLine(QLineF(cx, cy - H / 2, cx, cy - gap))
            p.drawLine(QLineF(cx, cy + gap, cx, cy + H / 2))

        # 4. Two thin outer circles. Sparse on purpose — a dense ring reads as a
        #    grey band at this size, and restraint is what made the original
        #    look expensive.
        for rr, a in ((1.00, 0.34), (0.93, 0.16)):
            rad = r * rr
            p.setPen(QPen(blend(main, a), 1))
            p.drawEllipse(QRectF(cx - rad, cy - rad, rad * 2, rad * 2))

        # 5. Long, sparse graduations: 24 majors reaching well in from the rim,
        #    with shorter minors between them.
        major, minor = [], []
        for i in range(72):
            a = math.radians(i * 5.0)
            ca, sa = math.cos(a), math.sin(a)
            if i % 3 == 0:
                major.append(QLineF(cx + ca * r * 0.885, cy + sa * r * 0.885,
                                    cx + ca * r * 0.985, cy + sa * r * 0.985))
            else:
                minor.append(QLineF(cx + ca * r * 0.945, cy + sa * r * 0.945,
                                    cx + ca * r * 0.985, cy + sa * r * 0.985))
        p.setPen(QPen(blend(main, 0.42), 1.3))
        p.drawLines(major)
        p.setPen(QPen(blend(main, 0.18), 1))
        p.drawLines(minor)

        # 6. Sweeping arcs. Long spans, not dashes — the original's grandeur
        #    came from a few big strokes. Speed is the state: idle drifts,
        #    thinking hurries, speaking runs.
        rate = 1.0 + (1.9 if self.state in ("THINKING", "PROCESSING") else 0.0) \
                   + (1.2 if self.speaking else 0.0)
        for k, (rr, span, count, dirn, col, a, wid) in enumerate((
                (0.955, 118, 2, +1, acc,  0.75, 2.0),
                (0.845, 82,  3, -1, main, 0.38, 1.3),
                (0.760, 150, 1, +1, acc,  0.45, 1.6),
                (0.660, 64,  4, -1, main, 0.26, 1.1),
                (0.545, 128, 2, +1, main, 0.30, 1.2))):
            rad = r * rr
            p.setPen(QPen(blend(col, a), wid))
            box = QRectF(cx - rad, cy - rad, rad * 2, rad * 2)
            base = (t * rate * (9 + k * 6) * dirn) % 360.0
            for sgm in range(count):
                p.drawArc(box, int((base + sgm * (360.0 / count)) * 16),
                          int(span * 16))

        # 7. The voice, as a ring of graduations that grow with it. Kept out at
        #    a wide radius so it never crowds the middle.
        n = 60
        ring = r * 0.415
        spikes = []
        for i in range(n):
            a = math.radians(i * (360.0 / n))
            ca, sa = math.cos(a), math.sin(a)
            wob = 0.5 + 0.5 * math.sin(t * 2.3 + i * 0.42)
            idle = 0.018 + 0.012 * math.sin(t * 1.2 + i * 0.7)
            h = r * (idle + (amp * 0.20 * wob if live else 0.0))
            spikes.append(QLineF(cx + ca * ring, cy + sa * ring,
                                 cx + ca * (ring + h), cy + sa * (ring + h)))
        p.setPen(QPen(blend(acc if live else main, 0.25 + 0.5 * amp), 1.6))
        p.drawLines(spikes)

        # 8. The inner ring the name sits in.
        inner = r * 0.355
        p.setPen(QPen(blend(acc, 0.30 + 0.45 * amp), 1.5))
        p.drawEllipse(QRectF(cx - inner, cy - inner, inner * 2, inner * 2))

        # 9. The name, sized from the string rather than from the radius alone:
        #    "J.A.R.V.I.S" and a name someone renamed to "MAX" are very
        #    different widths, and a fixed fraction of r spills one of them past
        #    the ring it is supposed to sit inside.
        name = self._assistant_name or ""
        if name:
            space = max(1.0, r * 0.018)
            fsz = max(8, int(min(r * 0.105,
                                 (inner * 1.75) / max(1, len(name)) * 1.6 - space)))
            f = px_font(fsz * 1.33, QFont.Weight.Bold)
            f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, space)
            p.setFont(f)
            p.setPen(QPen(blend(qcol(C.WHITE), 0.6 + 0.4 * min(1.0, amp * 2)), 1))
            p.drawText(QRectF(cx - r, cy - fsz, r * 2, fsz * 2),
                       Qt.AlignmentFlag.AlignCenter, name)

    # ── 3D AR Spatial Depth Layers ───────────────────────────────────────────

    def _paint_layer0_deep_horizon(self, p: QPainter, W: float, H: float) -> None:
        """Layer 0: Deep Horizon Grid & Drifting Space Dust (Z = -600 to -300)."""
        main = qcol(C.PRI)

        # 1. Perspective grid lines
        if hasattr(self, "_grid_starts") and self._grid_starts is not None:
            p_starts, _, s_mask = perspective_project(self._grid_starts, W, H, self._camera)
            p_ends, _, e_mask = perspective_project(self._grid_ends, W, H, self._camera)
            valid = s_mask & e_mask
            if np.any(valid):
                q_lines = [
                    QLineF(float(p_starts[i, 0]), float(p_starts[i, 1]),
                           float(p_ends[i, 0]), float(p_ends[i, 1]))
                    for i in np.where(valid)[0]
                ]
                grid_pen = QPen(blend(main, 0.09), 1.0)
                p.setPen(grid_pen)
                p.drawLines(q_lines)

        # 2. Drifting 3D space dust particles
        if hasattr(self, "_dust_particles") and self._dust_particles is not None:
            d_pts, d_depths, d_mask = perspective_project(self._dust_particles, W, H, self._camera)
            if np.any(d_mask):
                valid_idx = np.where(d_mask)[0]
                for i in valid_idx:
                    depth = float(d_depths[i])
                    alpha = max(0.08, min(0.65, 1.0 - (depth / 600.0)))
                    sz = 1.0 if depth > 350.0 else 1.8
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QBrush(blend(main, alpha)))
                    p.drawEllipse(QPointF(float(d_pts[i, 0]), float(d_pts[i, 1])), sz, sz)
                p.setBrush(Qt.BrushStyle.NoBrush)

    def _paint_layer1_spatial_gimbals(self, p: QPainter, cx: float, cy: float, r: float) -> None:
        """Layer 1: Central Avatar Matrix & Telemetry Gimbals (Z = -150 to +50)."""
        t = self._core_phase
        main = qcol(C.PRI)
        acc = qcol(C.ACC if self.speaking else C.ACC2)

        dock = float(getattr(self, "_avatar_dock", 0.0))
        center3d = (160.0 * dock, 15.0 - 90.0 * dock, -40.0 * dock)
        ring1 = generate_orbit_ring(
            radius=r * 1.36, segments=40, tilt_yaw=t * 18.0, tilt_pitch=22.0, center=center3d
        )
        ring2 = generate_orbit_ring(
            radius=r * 1.52, segments=44, tilt_yaw=-t * 14.0, tilt_pitch=-18.0, center=center3d
        )

        w, h = float(self.width()), float(self.height())
        for ring_pts, col, alpha, width_px in ((ring1, main, 0.32, 1.3), (ring2, acc, 0.22, 1.0)):
            pts2d, depths, mask = perspective_project(ring_pts, w, h, self._camera)
            if np.all(mask):
                path = QPainterPath()
                path.moveTo(float(pts2d[0, 0]), float(pts2d[0, 1]))
                for k in range(1, len(pts2d)):
                    path.lineTo(float(pts2d[k, 0]), float(pts2d[k, 1]))
                path.closeSubpath()
                p.setPen(QPen(blend(col, alpha), width_px))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(path)

    def _paint_layer2_holo_panes(self, p: QPainter, W: float, H: float) -> None:
        """Layer 2: Floating AR Projection Plane Container (Z = +100 to +300)."""
        if not hasattr(self, "_active_holo_panes") or not self._active_holo_panes:
            return

        main = qcol(C.PRI)
        acc = qcol(C.ACC)
        for pane_id, pane in list(self._active_holo_panes.items()):
            fp = float(pane.get("focus_progress", 0.0))
            def_center = pane.get("default_center", pane.get("center", (180.0, 30.0, -40.0)))
            def_w = float(pane.get("default_width", pane.get("width", 260.0)))
            def_h = float(pane.get("default_height", pane.get("height", 160.0)))
            def_yaw = float(pane.get("default_yaw", pane.get("yaw", -18.0)))
            def_pitch = float(pane.get("default_pitch", pane.get("pitch", 6.0)))

            # Center stage target position: full frontal, centered, expanded
            foc_center = (0.0, 15.0, 50.0)
            foc_w = min(W * 0.74, 460.0)
            foc_h = min(H * 0.64, 290.0)
            foc_yaw = 0.0
            foc_pitch = 0.0

            center = (
                def_center[0] * (1.0 - fp) + foc_center[0] * fp,
                def_center[1] * (1.0 - fp) + foc_center[1] * fp,
                def_center[2] * (1.0 - fp) + foc_center[2] * fp,
            )
            pw = def_w * (1.0 - fp) + foc_w * fp
            ph = def_h * (1.0 - fp) + foc_h * fp
            yaw = def_yaw * (1.0 - fp) + foc_yaw * fp
            pitch = def_pitch * (1.0 - fp) + foc_pitch * fp
            title = pane.get("title", "AR HOLO PANE")
            pixmap = pane.get("pixmap", None)

            pts2d, visible = project_holo_pane(center, pw, ph, yaw, pitch, W, H, self._camera)
            if not visible or len(pts2d) < 4:
                continue

            # Draw translucent glassmorphic quad
            poly = QPainterPath()
            poly.moveTo(float(pts2d[0, 0]), float(pts2d[0, 1]))
            poly.lineTo(float(pts2d[1, 0]), float(pts2d[1, 1]))
            poly.lineTo(float(pts2d[2, 0]), float(pts2d[2, 1]))
            poly.lineTo(float(pts2d[3, 0]), float(pts2d[3, 1]))
            poly.closeSubpath()

            # Fill with subtle tinted glass
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(blend(qcol(C.BG), 0.78)))
            p.drawPath(poly)

            # Draw projected pixmap if available
            if pixmap is not None and not pixmap.isNull():
                p.save()
                p.setClipPath(poly)
                min_x = min(pts2d[:, 0])
                min_y = min(pts2d[:, 1])
                max_x = max(pts2d[:, 0])
                max_y = max(pts2d[:, 1])
                target_rect = QRectF(float(min_x), float(min_y), float(max_x - min_x), float(max_y - min_y))
                p.drawPixmap(target_rect.toRect(), pixmap)
                p.restore()

            # Neon boundary pen
            p.setPen(QPen(blend(acc, 0.65), 1.4))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(poly)

            # Header title
            p.setFont(px_font(9, QFont.Weight.Bold, spacing=1))
            p.setPen(QPen(blend(main, 0.90), 1))
            p.drawText(QPointF(float(pts2d[0, 0]) + 4, float(pts2d[0, 1]) - 6), f"◈ {title.upper()}")

    def _paint_layer3_tactical_reticle(self, p: QPainter, W: float, H: float) -> None:
        """Layer 3: Foreground Tactical Reticle & Targeting Telemetry (Z = +400)."""
        if not hasattr(self, "_cursor_pos") or self._cursor_pos is None:
            return

        cx, cy = float(self._cursor_pos.x()), float(self._cursor_pos.y())
        if cx < 0 or cx > W or cy < 0 or cy > H:
            return

        nx, ny = self._cursor_norm
        telemetry = f"TGT [X: {nx:+05.2f} | Y: {ny:+05.2f} | Z: 1.00]"
        main = qcol(C.PRI)
        acc = qcol(C.ACC)

        p.save()
        # 1. Subtle reticle crosshair
        p.setPen(QPen(blend(main, 0.45), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        r = 14.0
        p.drawEllipse(QPointF(cx, cy), r, r)

        # 4 crosshair ticks
        p.drawLine(QLineF(cx - r - 5, cy, cx - r + 3, cy))
        p.drawLine(QLineF(cx + r - 3, cy, cx + r + 5, cy))
        p.drawLine(QLineF(cx, cy - r - 5, cx, cy - r + 3))
        p.drawLine(QLineF(cx, cy + r - 3, cx, cy + r + 5))

        # Center dot
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(blend(acc, 0.75)))
        p.drawEllipse(QPointF(cx, cy), 1.8, 1.8)

        # 2. Telemetry badge beside cursor
        p.setFont(px_font(8, QFont.Weight.Medium, spacing=1))
        p.setPen(QPen(blend(main, 0.85), 1))
        p.drawText(QPointF(cx + 18, cy + 12), telemetry)
        p.restore()

    def paintEvent(self, _):
        p = QPainter(self)
        if not p.isActive():      # device not ready (e.g. 0-size during layout) — skip cleanly
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # The backdrop is one cached pixmap, rebuilt only when the size or the
        # theme changes — so live re-theming still repaints it.
        key = (W, H, C.PRI, C.BG, C.WHITE)
        if self._grid_cache is None or self._grid_key != key:
            self._grid_cache = self._make_grid(W, H)
            self._grid_key = key
        p.drawPixmap(0, 0, self._grid_cache)

        # ── Dynamic Ambient Lighting: Floor Horizon Spill ─────────────────────
        self._ambient.paint_horizon_glow(p, float(W), float(H), H * 0.70)
        amb_col = self._ambient.current_color

        # ── Layer 0: Deep Horizon Perspective Grid & Space Dust ─────────────
        self._paint_layer0_deep_horizon(p, float(W), float(H))

        cx, cy = W / 2, H / 2
        fw = min(W, H)
        # The state line and the waveform take the bottom of the canvas; the
        # centrepiece gets the band above them, at any window size.
        sy = min(cy + fw * 0.38, H - 74.0)
        band_t = 30.0
        band_h = max(60.0, sy - 14.0 - band_t)

        if self._avatar is not None and self.hud_style in _FACE_STYLES:
            # "face_solid" draws solid head, "face_matrix"/"points" draws points,
            # and "face"/"face_holo"/"hologram" activates the refactored hologram head.
            if self.hud_style == "face_solid":
                self._avatar.mode = "solid"
            elif self.hud_style in ("face_matrix", "matrix", "points"):
                self._avatar.mode = "points"
            else:
                self._avatar.mode = "hologram"

            av = self._avatar
            # The head and everything that hangs off it must fit the band:
            r_head = min(fw * 0.355, band_h / (av.TOP + av.BOT + 0.08))
            head_cy = band_t + (band_h - (av.TOP + av.BOT) * r_head) / 2.0 + av.TOP * r_head

            # Avatar orbital docking transformation when AR surface is in center stage
            dock = float(getattr(self, "_avatar_dock", 0.0))
            scale_mult = 1.0 - 0.58 * dock
            cx_eff = cx + (W * 0.33) * dock
            cy_eff = head_cy - (band_h * 0.28) * dock
            r_head_eff = r_head * scale_mult

            # Ambient aura & telemetry framing behind avatar
            self._ambient.paint_aura(p, cx_eff, cy_eff, r_head_eff)
            self._telemetry.paint_arcs(p, cx_eff, cy_eff, r_head_eff * 1.32, self.state, self.speaking, amb_col)
            self._eq_ribbon.paint(p, cx_eff, cy_eff, r_head_eff * 1.18, self.speaking, self.state, self.muted)
            self._paint_layer1_spatial_gimbals(p, cx_eff, cy_eff, r_head_eff)

            if self.muted:
                main = acc = qcol(C.MUTED_C)
            else:
                # Read from the live palette on every paint, so the colour wheel
                # retints the whole hologram the moment it changes.
                main = qcol(C.PRI)
                if self.speaking:
                    acc = qcol(C.ACC)
                elif self.state in ("ERROR", "FAILED"):
                    acc = qcol(C.RED)
                elif self.state in ("THINKING", "PROCESSING"):
                    acc = qcol(C.ACC2)
                elif self.state == "LISTENING":
                    acc = qcol(C.GREEN)
                else:
                    acc = qcol(C.PRI)
            p.save()
            p.setClipRect(QRectF(0, 0, W, H))
            av.paint(p, cx_eff, cy_eff, r_head_eff, main, acc, qcol(C.BG), half_w=W / 2.0)
            p.restore()
        elif self._reactor is not None:
            ext = Reactor3D.TOP + Reactor3D.BOTTOM
            r = min(W * 0.25, band_h / ext)
            core_cy = band_t + (band_h - ext * r) / 2.0 + Reactor3D.TOP * r
            dock = float(getattr(self, "_avatar_dock", 0.0))
            scale_mult = 1.0 - 0.58 * dock
            cx_eff = cx + (W * 0.33) * dock
            cy_eff = core_cy - (band_h * 0.28) * dock
            r_eff = r * scale_mult
            self._ambient.paint_aura(p, cx_eff, cy_eff, r_eff)
            self._telemetry.paint_arcs(p, cx_eff, cy_eff, r_eff * 1.45, self.state, self.speaking, amb_col)
            self._eq_ribbon.paint(p, cx_eff, cy_eff, r_eff * 1.25, self.speaking, self.state, self.muted)
            self._paint_core(p, cx_eff, cy_eff, r_eff, W, band_h)
        else:
            r = min(W * 0.46, band_h / 2.0)
            dock = float(getattr(self, "_avatar_dock", 0.0))
            scale_mult = 1.0 - 0.58 * dock
            cx_eff = cx + (W * 0.33) * dock
            cy_eff = (band_t + band_h / 2.0) - (band_h * 0.28) * dock
            r_eff = r * scale_mult
            self._ambient.paint_aura(p, cx_eff, cy_eff, r_eff)
            self._telemetry.paint_arcs(p, cx_eff, cy_eff, r_eff * 1.45, self.state, self.speaking, amb_col)
            self._paint_core_classic(p, cx_eff, cy_eff, r_eff, W, band_h)

        # ── Layer 2: Floating AR Holographic Panes Container ─────────────────
        self._paint_layer2_holo_panes(p, float(W), float(H))

        # ── Ambient Edge Lighting along Frame ────────────────────────────────
        self._ambient.paint_edge_illumination(p, float(W), float(H))

        # state line: spaced capitals between two fading rules that pulse
        if self.muted:
            txt, col = "MUTED", qcol(C.MUTED_C)
        elif self.speaking:
            txt, col = "SPEAKING", qcol(C.ACC)
        elif self.state in ("THINKING", "PROCESSING"):
            txt, col = self.state, qcol(C.ACC2)
        elif self.state == "LISTENING":
            txt, col = "LISTENING", qcol(C.GREEN)
        else:
            txt, col = str(self.state), qcol(C.PRI)
        p.setFont(px_font(13, QFont.Weight.DemiBold, spacing=5))
        tw = p.fontMetrics().horizontalAdvance(txt)
        p.setPen(QPen(col))
        p.drawText(QRectF(0, sy, W, 22), Qt.AlignmentFlag.AlignCenter, txt)
        pulse = 0.85 if (self._blink or self.speaking or self.muted) else 0.40
        rule = min(110.0, W * 0.12)
        for sgn in (-1, 1):
            x0 = cx + sgn * (tw / 2 + 14)
            lg = QLinearGradient(x0, 0, x0 + sgn * rule, 0)
            lg.setColorAt(0.0, with_alpha(col, pulse))
            lg.setColorAt(1.0, with_alpha(col, 0.0))
            p.setPen(QPen(QBrush(lg), 1))
            p.drawLine(QLineF(x0, sy + 11, x0 + sgn * rule, sy + 11))

        # ── Studio AI Audio Spectrum & Harmonic Visualizer ────────────────────
        wy = sy + 50.0
        amp = self._amp_disp
        self._visualizer.paint(p, cx, wy, W * 0.60, self.state, self.speaking,
                               self.muted, amp, amb_col)

        # ── Layer 3: Foreground Tactical Reticle & Coordinates ───────────────
        self._paint_layer3_tactical_reticle(p, float(W), float(H))

        p.end()   # end deterministically so the backing store never flushes an active painter
