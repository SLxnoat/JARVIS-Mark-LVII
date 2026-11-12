"""Unit tests for ambient lighting system and AI visualizations."""
from __future__ import annotations

import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage, QPainter, QColor

from gui.ambient import AmbientLighting, AIWaveformVisualizer, CognitiveTelemetry
from gui.hud import HudCanvas


class TestAmbientLighting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_ambient_lighting_transitions(self):
        amb = AmbientLighting()
        # Test stepping in idle
        amb.step(0.016, "IDLE", False, False, 0.0)
        c1 = amb.current_color
        self.assertIsInstance(c1, QColor)

        # Step into listening
        for _ in range(30):
            amb.step(0.016, "LISTENING", False, False, 0.3)
        c2 = amb.current_color
        # In listening, green channel should rise towards green
        self.assertGreater(c2.green(), 100)

        # Step into speaking
        for _ in range(30):
            amb.step(0.016, "SPEAKING", True, False, 0.8)
        c3 = amb.current_color
        self.assertIsInstance(c3, QColor)

        # Step into thinking
        for _ in range(30):
            amb.step(0.016, "THINKING", False, False, 0.0)
        c4 = amb.current_color
        self.assertIsInstance(c4, QColor)

        # Step into muted
        for _ in range(30):
            amb.step(0.016, "IDLE", False, True, 0.0)
        c5 = amb.current_color
        self.assertIsInstance(c5, QColor)

    def test_visualizer_ballistics_and_modes(self):
        vis = AIWaveformVisualizer()
        self.assertEqual(len(vis._levels), AIWaveformVisualizer.BANDS)
        self.assertEqual(len(vis._peaks), AIWaveformVisualizer.BANDS)

        # Test speaking physics
        vis.step(0.016, "SPEAKING", True, False, 0.7)
        self.assertTrue(any(lv > 1.5 for lv in vis._levels))

        # Test thinking neural flow
        vis.step(0.016, "THINKING", False, False, 0.0)
        self.assertTrue(any(lv > 2.0 for lv in vis._levels))

        # Test muted
        for _ in range(40):
            vis.step(0.016, "IDLE", False, True, 0.0)
        # Levels decay towards 0 in muted
        self.assertTrue(all(lv <= 1.0 for lv in vis._levels))

    def test_cognitive_telemetry(self):
        tel = CognitiveTelemetry()
        a0 = tel._angle
        tel.step(0.1, "THINKING", False)
        self.assertNotEqual(tel._angle, a0)

    def test_hud_canvas_paint_with_ambient(self):
        canvas = HudCanvas(face_path="")
        canvas.resize(640, 480)
        img = QImage(640, 480, QImage.Format.Format_ARGB32_Premultiplied)
        p = QPainter(img)

        # Render idle frame
        canvas._step()
        canvas.render(p)

        # Test speaking frame
        canvas.speaking = True
        canvas.set_audio_level(0.65)
        canvas._step()
        canvas.render(p)

        # Test thinking frame
        canvas.speaking = False
        canvas.state = "THINKING"
        canvas._step()
        canvas.render(p)

        # Test listening frame
        canvas.state = "LISTENING"
        canvas.set_audio_level(0.4)
        canvas._step()
        canvas.render(p)

        p.end()


if __name__ == "__main__":
    unittest.main()
