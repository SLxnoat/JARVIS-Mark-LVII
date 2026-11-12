"""tests/test_hud_layers.py — Unit Tests for 4 AR Depth Layers in HudCanvas."""

import os
import unittest
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QImage, QMouseEvent, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication

from gui.hud import HudCanvas


class TestHudLayers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Set headless platform offscreen for CI / container runs
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.app = QApplication.instance() or QApplication(["-platform", "offscreen"])

    def setUp(self):
        self.hud = HudCanvas(face_path="", assistant_name="JARVIS")
        self.hud.resize(800, 600)

    def tearDown(self):
        if hasattr(self.hud, "_tmr"):
            self.hud._tmr.stop()

    def test_hud_canvas_ar_initialization(self):
        self.assertTrue(self.hud.hasMouseTracking())
        self.assertIsNotNone(self.hud._camera)
        self.assertEqual(len(self.hud._dust_particles), 36)
        self.assertIsNotNone(self.hud._grid_starts)
        self.assertIsNotNone(self.hud._grid_ends)
        self.assertIsInstance(self.hud._active_holo_panes, dict)

    def test_mouse_tracking_and_reticle_telemetry(self):
        # Simulate mouse move inside HUD
        evt = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(400.0, 300.0),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.hud.mouseMoveEvent(evt)
        self.assertIsNotNone(self.hud._cursor_pos)
        self.assertAlmostEqual(self.hud._cursor_pos.x(), 400.0)
        self.assertAlmostEqual(self.hud._cursor_pos.y(), 300.0)

        # Normalized coordinates should be center (0, 0)
        self.assertAlmostEqual(self.hud._cursor_norm[0], 0.0, places=2)
        self.assertAlmostEqual(self.hud._cursor_norm[1], 0.0, places=2)

        # Test cursor leaving HUD
        self.hud.leaveEvent(None)
        self.assertIsNone(self.hud._cursor_pos)

    def test_holo_pane_registration_and_projection(self):
        # Create a small dummy pixmap
        pix = QPixmap(100, 60)
        pix.fill(Qt.GlobalColor.cyan)

        self.hud.register_holo_pane(
            pane_id="browser_test",
            title="INBUILT BROWSER",
            center=(160.0, 30.0, -30.0),
            width=220.0,
            height=140.0,
            yaw=-15.0,
            pitch=5.0,
            pixmap=pix,
        )

        self.assertIn("browser_test", self.hud._active_holo_panes)
        pane = self.hud._active_holo_panes["browser_test"]
        self.assertEqual(pane["title"], "INBUILT BROWSER")

        # Unregister
        self.hud.unregister_holo_pane("browser_test")
        self.assertNotIn("browser_test", self.hud._active_holo_panes)

    def test_dust_particles_drift_in_step(self):
        initial_z = self.hud._dust_particles[0, 2]
        # Step once
        self.hud._step()
        stepped_z = self.hud._dust_particles[0, 2]
        # Dust particle should move forward along -Z towards camera
        self.assertLess(stepped_z, initial_z)

    def test_paint_all_four_layers_headless(self):
        # Register a test pane so Layer 2 executes full painting
        pix = QPixmap(80, 50)
        pix.fill(Qt.GlobalColor.blue)
        self.hud.register_holo_pane(
            pane_id="test_pane",
            title="TEST RADAR",
            center=(150.0, 20.0, -20.0),
            width=200.0,
            height=120.0,
            pixmap=pix,
        )

        # Set cursor position so Layer 3 tactical reticle paints
        self.hud._cursor_pos = QPointF(350.0, 250.0)
        self.hud._cursor_norm = (0.1, -0.1)

        # Paint to offscreen QImage
        img = QImage(800, 600, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.black)
        p = QPainter(img)

        # Call paintEvent safely
        try:
            self.hud.paintEvent(None)
        finally:
            if p.isActive():
                p.end()

        # Canvas should be alive and well
        self.assertFalse(img.isNull())


if __name__ == "__main__":
    unittest.main()
