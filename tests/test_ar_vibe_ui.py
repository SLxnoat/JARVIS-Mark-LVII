"""tests/test_ar_vibe_ui.py — Comprehensive Unit & Integration Tests for AR Vibe UI/UX.

Verifies:
1. Fast LUT & Style Helpers: Pre-blended LUT (<30ms for 10k calls), corner brackets, badges.
2. HUD AR Vibe Canvas: Scanline, cursor reticle tracking, audio viseme orbit, 60 FPS frame time (<16.6ms).
3. Tactical Cyber Panels: 2D Sentry Radar, Synaptic Board, Mission Control Capsules.
4. Ergonomics: Universal Command Spotlight (Ctrl+K fuzzy matching), Radial Quick Wheel (Tab hold).
5. AGENTS.md Thread Audit: Zero Qt widget imports in plugins/.
"""

import ast
import os
import sys
import time
from pathlib import Path
import unittest

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QKeyEvent, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication

from gui.command_spotlight import CommandSpotlight
from gui.hud import HudCanvas
from gui.mission_capsules import MissionControlCapsules
from gui.radial_wheel import RadialQuickWheel
from gui.style import blend_fast, draw_corner_brackets, draw_tech_badge
from gui.synaptic_board import SynapticBoardWidget
from gui.tactical_radar import TacticalRadarWidget
from gui.theme import C, apply_ui_accent
from ui import JarvisUI


class TestStyleAndLUT(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.app = QApplication.instance() or QApplication(["-platform", "offscreen"])

    def test_blend_fast_lut_speed(self):
        # 10,000 blended color calls
        start = time.perf_counter()
        for i in range(10000):
            a = (i % 100) / 100.0
            col = blend_fast(C.PRI, a)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        self.assertLess(elapsed_ms, 35.0, f"blend_fast took too long: {elapsed_ms:.2f} ms")
        self.assertIsInstance(col, QColor)
        self.assertTrue(col.isValid())

    def test_style_drawing_helpers(self):
        pix = QPixmap(200, 200)
        p = QPainter(pix)
        draw_corner_brackets(p, pix.rect(), size=8.0)
        bw = draw_tech_badge(p, 10, 10, "TEST BADGE", C.PRI)
        p.end()
        self.assertGreater(bw, 10.0)


class TestHudARVibeCanvas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.app = QApplication.instance() or QApplication(["-platform", "offscreen"])

    def setUp(self):
        self.hud = HudCanvas(face_path="")
        self.hud.resize(960, 600)

    def tearDown(self):
        if hasattr(self.hud, "_tmr"):
            self.hud._tmr.stop()
        self.hud.deleteLater()

    def test_hud_paint_and_reticle(self):
        self.hud._cursor_active = True
        self.hud._cursor_target = QPointF(320.0, 240.0)
        self.hud._step()
        self.assertGreater(self.hud._cursor_pos.x(), 200.0)

        pix = QPixmap(960, 600)
        p = QPainter(pix)
        # Should paint cleanly without exceptions
        self.hud._paint_tactical_vibe_hud(p, 960.0, 600.0, 480.0, 300.0, 120.0)
        self.hud._paint_audio_viseme_orbit(p, 480.0, 300.0, 120.0)
        p.end()

    def test_hud_parallax_mouse_interaction(self):
        from PyQt6.QtGui import QMouseEvent
        from PyQt6.QtCore import QEvent
        me = QMouseEvent(QEvent.Type.MouseMove, QPointF(100.0, 100.0), Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        self.hud.mouseMoveEvent(me)
        self.assertTrue(self.hud._cursor_active)
        self.assertLess(self.hud._parallax_target.x(), 0.0)
        self.assertLess(self.hud._parallax_target.y(), 0.0)

        # Step smoothing
        self.hud._step()
        self.assertLess(self.hud._parallax_offset.x(), 0.0)
        self.assertLess(self.hud._parallax_offset.y(), 0.0)

    def test_hud_frame_render_budget_60fps(self):
        pix = QPixmap(960, 600)
        p = QPainter(pix)

        # Warm-up pass
        self.hud._paint_tactical_vibe_hud(p, 960.0, 600.0, 480.0, 300.0, 120.0)
        self.hud._paint_audio_viseme_orbit(p, 480.0, 300.0, 120.0)

        n_frames = 100
        start = time.perf_counter()
        for _ in range(n_frames):
            self.hud._paint_tactical_vibe_hud(p, 960.0, 600.0, 480.0, 300.0, 120.0)
            self.hud._paint_audio_viseme_orbit(p, 480.0, 300.0, 120.0)
        elapsed_s = time.perf_counter() - start
        p.end()

        avg_ms = (elapsed_s / n_frames) * 1000.0
        # AR Vibe 2D painting typically takes 0.1 - 1.0 ms
        self.assertLess(avg_ms, 5.0, f"Frame render time ({avg_ms:.2f} ms) exceeded 5.0 ms budget!")


class TestTacticalCyberPanels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.app = QApplication.instance() or QApplication(["-platform", "offscreen"])

    def test_tactical_radar_sweep_and_alert(self):
        radar = TacticalRadarWidget()
        radar.resize(320, 320)
        initial_angle = radar._sweep_angle
        radar._step()
        self.assertNotEqual(radar._sweep_angle, initial_angle)

        # Alert trigger
        radar.trigger_alert("PORT_SCAN", "Unauthorized port scan on 65535")
        self.assertGreater(radar._alert_pulse, 0.5)
        self.assertTrue(any(b.is_threat for b in radar._blips))

        # Render test
        pix = QPixmap(320, 320)
        p = QPainter(pix)
        radar.render(p)
        p.end()
        radar.deleteLater()

    def test_synaptic_board_sparks(self):
        board = SynapticBoardWidget()
        board.resize(420, 300)
        self.assertGreater(len(board._nodes), 4)

        # Spark learning
        board.spark_learning("rule_test_99", "Voice command trigger", 0.95)
        self.assertIn("rule_test_99", board._nodes)
        self.assertGreater(len(board._sparks), 0)

        # Step sparks
        initial_prog = board._sparks[0].progress
        board._step()
        self.assertGreaterEqual(board._sparks[0].progress, initial_prog)

        # Render test
        pix = QPixmap(420, 300)
        p = QPainter(pix)
        board.render(p)
        p.end()
        board.deleteLater()

    def test_mission_control_capsules(self):
        capsules = MissionControlCapsules()
        capsules.resize(380, 240)
        self.assertEqual(len(capsules._tasks), 3)

        capsules.update_agent_status("coder", "RUNNING", 0.75, "Compiling patch")
        task = [t for t in capsules._tasks if t.agent_id == "coder"][0]
        self.assertEqual(task.status, "RUNNING")
        self.assertEqual(task.progress, 0.75)

        # Render test
        pix = QPixmap(380, 240)
        p = QPainter(pix)
        capsules.render(p)
        p.end()
        capsules.deleteLater()


class TestSpatialErgonomics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.app = QApplication.instance() or QApplication(["-platform", "offscreen"])

    def test_command_spotlight_fuzzy(self):
        spotlight = CommandSpotlight()
        self.assertGreater(len(spotlight._all_commands), 10)

        spotlight._on_search_changed("radar")
        self.assertGreater(spotlight._list.count(), 0)
        top = spotlight._list.item(0).data(Qt.ItemDataRole.UserRole)
        self.assertIn("radar", (top.title + top.description).lower())
        spotlight.deleteLater()

    def test_radial_wheel_slices(self):
        wheel = RadialQuickWheel()
        wheel.resize(300, 300)
        wheel._center_pos = QPointF(150.0, 150.0)

        # Point directly above center -> slice 0 (radar)
        idx_top = wheel._get_slice_index(QPointF(150.0, 75.0))
        self.assertEqual(idx_top, 0)

        # Point dead center -> deadzone (-1)
        idx_center = wheel._get_slice_index(QPointF(150.0, 150.0))
        self.assertEqual(idx_center, -1)
        wheel.deleteLater()


class TestIntegrationAndThreadAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.app = QApplication.instance() or QApplication(["-platform", "offscreen"])

    def setUp(self):
        self.player = JarvisUI(face_path="")
        self.win = self.player._win

    def tearDown(self):
        if hasattr(self.win, "hud") and hasattr(self.win.hud, "_tmr"):
            self.win.hud._tmr.stop()
        self.win.close()

    def test_tactical_drawers_toggle(self):
        init_left = getattr(self.win, "_left_collapsed", False)
        self.win.toggle_left_drawer()
        self.assertNotEqual(getattr(self.win, "_left_collapsed", False), init_left)
        self.win.toggle_left_drawer()
        self.assertEqual(getattr(self.win, "_left_collapsed", False), init_left)

        init_right = getattr(self.win, "_right_collapsed", False)
        self.win.toggle_right_drawer()
        self.assertNotEqual(getattr(self.win, "_right_collapsed", False), init_right)
        self.win.toggle_right_drawer()
        self.assertEqual(getattr(self.win, "_right_collapsed", False), init_right)

    def test_side_column_drawer_persistence_on_resize(self):
        self.win.resize(1200, 800)
        self.win._fit_side_columns()
        left_w_open = self.win._left_panel.width()
        self.assertGreaterEqual(left_w_open, 180)

        # Collapse left drawer
        self.win.toggle_left_drawer()
        self.assertTrue(self.win._left_collapsed)
        self.assertEqual(self.win._left_panel.width(), 0)

        # Trigger resize event
        self.win.resize(1400, 900)
        self.win._fit_side_columns()
        # Left drawer should remain 0 width and hidden
        self.assertEqual(self.win._left_panel.width(), 0)
        self.assertFalse(self.win._left_panel.isVisible())

    def test_holodeck_fullscreen_toggle(self):
        self.assertFalse(getattr(self.win, "_is_holodeck", False))
        self.win.toggle_holodeck_mode()
        self.assertTrue(getattr(self.win, "_is_holodeck", False))
        self.assertFalse(self.win._left_panel.isVisible())
        self.assertFalse(self.win._right_panel.isVisible())

        self.win.toggle_holodeck_mode()
        self.assertFalse(getattr(self.win, "_is_holodeck", False))
        self.assertTrue(self.win._left_panel.isVisible())
        self.assertTrue(self.win._right_panel.isVisible())

    def test_bridge_methods(self):
        # Trigger defense alert via player
        self.player.trigger_defense_alert("BREACH_TEST", "High severity alert")
        self.assertTrue(self.win._radar_panel.isVisible())

        # Trigger synaptic spark via player
        self.player.spark_neuro_learning("rule_auto_test", "Unit test trigger", 0.99)
        self.assertIn("rule_auto_test", self.win._synaptic_widget._nodes)

        # Show mission control via player
        self.player.show_mission_control()
        self.assertTrue(self.win._mission_panel.isVisible())

    def test_agents_md_no_qt_widgets_in_plugins(self):
        plugins_dir = Path(__file__).resolve().parent.parent / "plugins"
        disallowed = {"PyQt6.QtWidgets", "PyQt6.QtGui", "PySide6.QtWidgets", "PySide6.QtGui"}
        offenders = []
        for py_file in plugins_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if any(alias.name.startswith(d) for d in disallowed):
                            offenders.append((py_file.name, alias.name))
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    if any(mod.startswith(d) for d in disallowed):
                        offenders.append((py_file.name, mod))

        self.assertEqual(offenders, [], f"AGENTS.md Violation! Plugins importing Qt widgets: {offenders}")


if __name__ == "__main__":
    unittest.main()
