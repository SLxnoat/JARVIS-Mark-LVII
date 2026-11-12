"""tests/test_fast_lut_and_lod.py — Unit Tests for blend_fast LUT and Dynamic LOD Governor."""

import os
import time
import unittest
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication

from gui.style import blend_fast, _BLEND_CACHE, _HEX_RGB_CACHE
from gui.theme import C
from gui.hud import HudCanvas


class TestFastLUTAndLOD(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.app = QApplication.instance() or QApplication(["-platform", "offscreen"])

    def test_blend_fast_color_accuracy(self):
        # col = white (#ffffff), base = black (#000000)
        # At alpha 0.0 -> black
        c0 = blend_fast("#ffffff", 0.0, base="#000000")
        self.assertEqual(c0.red(), 0)
        self.assertEqual(c0.green(), 0)
        self.assertEqual(c0.blue(), 0)

        # At alpha 1.0 -> white
        c1 = blend_fast("#ffffff", 1.0, base="#000000")
        self.assertEqual(c1.red(), 255)
        self.assertEqual(c1.green(), 255)
        self.assertEqual(c1.blue(), 255)

        # At alpha 0.5 -> ~127-128
        c_mid = blend_fast("#ffffff", 0.5, base="#000000")
        self.assertAlmostEqual(c_mid.red(), 127, delta=2)
        self.assertAlmostEqual(c_mid.green(), 127, delta=2)
        self.assertAlmostEqual(c_mid.blue(), 127, delta=2)

    def test_blend_fast_cache_efficiency(self):
        _BLEND_CACHE.clear()
        _HEX_RGB_CACHE.clear()

        # First call populates cache
        c1 = blend_fast("#00f2fe", 0.45)
        self.assertGreater(len(_BLEND_CACHE), 0)
        self.assertGreater(len(_HEX_RGB_CACHE), 0)

        # Second call with same parameters must hit cache and return exact object
        c2 = blend_fast("#00f2fe", 0.45)
        self.assertIs(c1, c2)

    def test_blend_fast_benchmark_10k_calls(self):
        # Warmup
        blend_fast(C.PRI, 0.3)

        start = time.perf_counter()
        for i in range(10000):
            # Vary alpha slightly to hit varied buckets
            alpha = (i % 50) / 50.0
            blend_fast(C.PRI, alpha)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        print(f"\n[blend_fast Benchmark] 10,000 calls executed in: {elapsed_ms:.3f} ms")
        self.assertLess(elapsed_ms, 15.0, "blend_fast took longer than 15ms for 10k calls!")

    def test_dynamic_lod_governor_active_idle_and_occluded(self):
        hud = HudCanvas(face_path="", assistant_name="JARVIS")
        try:
            # Force _on_screen to return True for testing active vs idle
            hud._on_screen = lambda: True

            # 1. Active state (speaking=True) -> Should set 16ms (60 FPS)
            hud.speaking = True
            hud._step()
            self.assertEqual(hud._tmr.interval(), 16)

            # 2. Idle state (speaking=False, amp=0.0, state="IDLE", cursor=None) -> Should set 42ms (24 FPS)
            hud.speaking = False
            hud._amp_disp = 0.0
            hud.state = "IDLE"
            hud._cursor_pos = None
            hud._step()
            self.assertEqual(hud._tmr.interval(), 42)

            # 3. Interactive state (mouse hovering inside) -> Should set 16ms (60 FPS)
            hud._cursor_pos = QPointF(100.0, 100.0)
            hud._step()
            self.assertEqual(hud._tmr.interval(), 16)

            # 4. Occluded / Minimized state (_on_screen = False) -> Should set 500ms (0 FPS render)
            hud._on_screen = lambda: False
            hud._step()
            self.assertEqual(hud._tmr.interval(), 500)
        finally:
            hud._tmr.stop()


if __name__ == "__main__":
    unittest.main()
