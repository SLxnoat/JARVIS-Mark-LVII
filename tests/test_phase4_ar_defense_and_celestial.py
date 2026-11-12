"""tests/test_phase4_ar_defense_and_celestial.py — Unit Tests for Phase 4 AR Defense Radar, Celestial Orbit & Task Capsules."""

import os
import time
import unittest
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor, QImage, QPixmap
from PyQt6.QtWidgets import QApplication

from gui.defense_panel import DefensePanel, PolarRadarWidget, RadarBlip
from gui.eq_ribbon import ConcentricAudioEqualizer
from gui.celestial_orbit import CelestialOrbitWidget
from gui.task_capsules import MissionControlDeck, TaskAgentCapsule
from gui.window import MainWindow
from ui import JarvisUI


class TestPhase4ARDefenseAndCelestial(unittest.TestCase):
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

    def test_polar_radar_blip_math(self):
        blip = RadarBlip(port=443, ip="0.0.0.0", proto="TCP", is_public=True, label="HTTPS")
        self.assertGreater(blip.radius_norm, 0.2)
        self.assertLessEqual(blip.radius_norm, 1.0)
        self.assertGreaterEqual(blip.angle_deg, 0.0)
        self.assertLess(blip.angle_deg, 360.0)

    def test_polar_radar_1000_sweeps_benchmark(self):
        radar = PolarRadarWidget()
        start = time.perf_counter()
        for _ in range(1000):
            radar._step()
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        print(f"\n[Polar Radar Benchmark] 1,000 sweep steps executed in: {elapsed_ms:.3f} ms")
        self.assertLess(elapsed_ms, 80.0, "1,000 radar sweeps took longer than 80ms!")
        radar._timer.stop()

    def test_defense_panel_threat_trigger_and_ar_pixmap(self):
        panel = DefensePanel()
        panel.set_threat("BadUSB Injection", "Unauthorized HID keyboard on Bus 001")
        self.assertTrue(panel.radar._threat_active)
        self.assertIn("BADUSB", panel.radar._threat_type.upper())

        # Render AR pixmap
        pix = panel.render_ar_pixmap(480, 300)
        self.assertIsNotNone(pix)
        self.assertFalse(pix.isNull())
        self.assertEqual(pix.width(), 480)
        self.assertEqual(pix.height(), 300)
        panel.radar._timer.stop()

    def test_concentric_audio_equalizer_ripples(self):
        eq = ConcentricAudioEqualizer()
        self.assertEqual(len(eq._levels), 32)

        # 1. Test inward ripples on mic input
        eq.step(dt=0.033, state="LISTENING", speaking=False, muted=False, amp=0.55)
        self.assertGreater(len(eq._ripples), 0)
        self.assertEqual(eq._ripples[0][2], -1.0)  # Inward direction

        # 2. Test outward ripples on speaker output
        eq._ripples.clear()
        eq.step(dt=0.033, state="SPEAKING", speaking=True, muted=False, amp=0.75)
        self.assertGreater(len(eq._ripples), 0)
        self.assertEqual(eq._ripples[0][2], 1.0)   # Outward direction

    def test_celestial_orbit_iss_projection_and_pixmap(self):
        celestial = CelestialOrbitWidget()
        celestial.update_telemetry(
            iss_data={"latitude": 14.5, "longitude": 80.2, "altitude": 420.0, "velocity": 27600},
            space_weather={"kp_index": 3.8, "solar_class": "C1.4", "solar_wind": 410},
        )
        self.assertEqual(celestial._iss_lat, 14.5)
        self.assertEqual(celestial._kp_index, 3.8)

        pix = celestial.render_ar_pixmap(480, 300)
        self.assertIsNotNone(pix)
        self.assertFalse(pix.isNull())
        self.assertEqual(pix.width(), 480)
        celestial._timer.stop()

    def test_mission_control_deck_capsules_and_pixmap(self):
        deck = MissionControlDeck()
        deck.refresh_tasks()
        self.assertGreaterEqual(len(deck._tasks), 2)

        pix = deck.render_ar_pixmap(480, 300)
        self.assertIsNotNone(pix)
        self.assertFalse(pix.isNull())
        self.assertEqual(pix.width(), 480)

    def test_signals_and_bridge_methods_exist(self):
        self.assertTrue(hasattr(self.win, "_defense_alert_sig"))
        self.assertTrue(hasattr(self.win, "_defense_show_sig"))
        self.assertTrue(hasattr(self.win, "_celestial_show_sig"))
        self.assertTrue(hasattr(self.win, "_mission_control_show_sig"))

        self.assertTrue(hasattr(self.player, "trigger_defense_alert"))
        self.assertTrue(hasattr(self.player, "show_ar_defense_radar"))
        self.assertTrue(hasattr(self.player, "show_ar_celestial_orbit"))
        self.assertTrue(hasattr(self.player, "show_ar_mission_control"))

    def test_defense_alert_projects_to_hud_layer2(self):
        self.player.trigger_defense_alert("Unlinked Binary", "PID 1337 running from /tmp")
        QApplication.processEvents()

        self.assertIn("defense", self.win.hud._active_holo_panes)
        pane = self.win.hud._active_holo_panes["defense"]
        self.assertIn("ALERT", pane["title"])
        self.assertIsNotNone(pane["pixmap"])
        self.assertFalse(pane["pixmap"].isNull())

    def test_celestial_and_mission_control_project_to_hud(self):
        self.player.show_ar_celestial_orbit()
        self.player.show_ar_mission_control()
        QApplication.processEvents()

        self.assertIn("celestial", self.win.hud._active_holo_panes)
        self.assertIn("mission_control", self.win.hud._active_holo_panes)
