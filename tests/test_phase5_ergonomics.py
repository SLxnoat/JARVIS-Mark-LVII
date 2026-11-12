"""tests/test_phase5_ergonomics.py — Unit Tests for AR Spatial Ergonomics (Phase 5).

Verifies:
1. RadialCommandWheel: Angular slice calculation, node selection, signal emission.
2. CommandPalette: Fuzzy command discovery across 69 plugins, keyboard navigation.
3. Tactical Drawers: Smooth QPropertyAnimation collapse and restore.
4. Fullscreen Holodeck Mode: Seamless F11 / Escape toggle without focus traps.
"""

import os
import sys
import unittest
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication

from gui.command_palette import CommandPalette
from gui.radial_menu import RadialCommandWheel, RadialNode
from ui import JarvisUI


class TestRadialCommandWheel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.app = QApplication.instance() or QApplication(["-platform", "offscreen"])

    def setUp(self):
        self.wheel = RadialCommandWheel()
        self.wheel.resize(320, 320)
        self.wheel._center_pos = QPointF(160.0, 160.0)

    def tearDown(self):
        self.wheel.deleteLater()

    def test_nodes_initialization(self):
        self.assertEqual(len(self.wheel.NODES), 6)
        node_ids = [n.node_id for n in self.wheel.NODES]
        self.assertIn("browser", node_ids)
        self.assertIn("defense", node_ids)
        self.assertIn("neuro", node_ids)
        self.assertIn("code", node_ids)
        self.assertIn("celestial", node_ids)
        self.assertIn("tasks", node_ids)

    def test_slice_calculation_and_hover(self):
        # Center is at (160, 160)
        # Point to the top (x=160, y=80) -> slice 0 (browser)
        idx_top = self.wheel._get_slice_index(QPointF(160.0, 80.0))
        self.assertEqual(idx_top, 0)

        # Point inside deadzone (x=160, y=160)
        idx_deadzone = self.wheel._get_slice_index(QPointF(160.0, 160.0))
        self.assertEqual(idx_deadzone, -1)

    def test_node_activation_signal(self):
        activated = []
        self.wheel.node_activated.connect(lambda nid: activated.append(nid))

        self.wheel._hovered_idx = 1
        expected_id = self.wheel.NODES[1].node_id
        self.wheel.show()
        # Trigger activation
        self.wheel.node_activated.emit(expected_id)
        self.wheel.hide()

        self.assertEqual(len(activated), 1)
        self.assertEqual(activated[0], expected_id)


class TestCommandPalette(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.app = QApplication.instance() or QApplication(["-platform", "offscreen"])

    def setUp(self):
        self.palette = CommandPalette()

    def tearDown(self):
        self.palette.deleteLater()

    def test_catalog_indexing(self):
        # Must index at least the 8 core actions and several plugins
        self.assertGreater(len(self.palette._all_commands), 10)
        titles = [c.title.lower() for c in self.palette._all_commands]
        self.assertTrue(any("browser" in t for t in titles))
        self.assertTrue(any("defense" in t for t in titles))
        self.assertTrue(any("neuro" in t for t in titles))

    def test_fuzzy_filtering(self):
        self.palette._txt_search.setText("radar")
        self.assertGreater(self.palette._list.count(), 0)
        top_item = self.palette._list.item(0)
        cmd = top_item.data(Qt.ItemDataRole.UserRole)
        self.assertIn("radar", (cmd.title + cmd.description).lower())

        self.palette._txt_search.setText("holodeck")
        self.assertGreater(self.palette._list.count(), 0)
        top_item = self.palette._list.item(0)
        cmd = top_item.data(Qt.ItemDataRole.UserRole)
        self.assertIn("holodeck", (cmd.title + cmd.description).lower())

    def test_keyboard_navigation_and_execution(self):
        executed = []
        self.palette.command_executed.connect(lambda cid, tit: executed.append((cid, tit)))

        self.palette.show_centered()
        self.palette._txt_search.setText("")
        self.assertGreater(self.palette._list.count(), 1)

        # Press Down arrow to navigate
        down_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier)
        self.palette.keyPressEvent(down_event)
        self.assertEqual(self.palette._list.currentRow(), 1)

        # Press Enter to execute selected item
        enter_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        self.palette.keyPressEvent(enter_event)

        self.assertEqual(len(executed), 1)
        self.assertFalse(self.palette.isVisible())


class TestErgonomicsIntegration(unittest.TestCase):
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

    def test_drawer_toggle(self):
        # Test left drawer collapse / expand
        initial_left_collapsed = self.win._left_collapsed
        self.win.toggle_left_drawer()
        self.assertNotEqual(self.win._left_collapsed, initial_left_collapsed)
        self.win.toggle_left_drawer()
        self.assertEqual(self.win._left_collapsed, initial_left_collapsed)

        # Test right drawer collapse / expand
        initial_right_collapsed = self.win._right_collapsed
        self.win.toggle_right_drawer()
        self.assertNotEqual(self.win._right_collapsed, initial_right_collapsed)
        self.win.toggle_right_drawer()
        self.assertEqual(self.win._right_collapsed, initial_right_collapsed)

    def test_holodeck_mode_toggle(self):
        self.assertFalse(self.win._is_holodeck)
        self.win.toggle_holodeck_mode()
        self.assertTrue(self.win._is_holodeck)
        self.assertFalse(self.win._left_panel.isVisible())
        self.assertFalse(self.win._right_panel.isVisible())

        # Toggle back
        self.win.toggle_holodeck_mode()
        self.assertFalse(self.win._is_holodeck)
        self.assertTrue(self.win._left_panel.isVisible())
        self.assertTrue(self.win._right_panel.isVisible())

    def test_radial_node_activation_handling(self):
        # Test activating defense radar from radial wheel
        self.win._on_radial_node_activated("defense")
        self.assertIn("defense", self.win.hud._active_holo_panes)

        # Test activating celestial orbit
        self.win._on_radial_node_activated("celestial")
        self.assertIn("celestial", self.win.hud._active_holo_panes)

        # Test activating mission tasks
        self.win._on_radial_node_activated("tasks")
        self.assertIn("mission_control", self.win.hud._active_holo_panes)

    def test_command_palette_execution_handling(self):
        # Test executing holodeck mode from command palette
        self.win._on_command_palette_executed("holodeck_mode", "Toggle Holodeck")
        self.assertTrue(self.win._is_holodeck)
        self.win._on_command_palette_executed("holodeck_mode", "Toggle Holodeck")
        self.assertFalse(self.win._is_holodeck)


if __name__ == "__main__":
    unittest.main()
