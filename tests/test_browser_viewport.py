"""tests/test_browser_viewport.py — Unit Tests for AR Browser Viewport."""

import os
import unittest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication

from gui.browser_viewport import BrowserViewport


class TestBrowserViewport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.app = QApplication.instance() or QApplication(["-platform", "offscreen"])

    def setUp(self):
        self.browser = BrowserViewport()
        self.browser.resize(800, 500)

    def tearDown(self):
        if hasattr(self.browser, "_beacon_timer"):
            self.browser._beacon_timer.stop()

    def test_browser_initialization(self):
        self.assertEqual(self.browser.DEFAULT_YAW, -18.0)
        self.assertEqual(self.browser.DEFAULT_PITCH, 6.0)
        self.assertIsNotNone(self.browser._txt_url)
        self.assertIsNotNone(self.browser._lbl_ssl)
        self.assertIsNotNone(self.browser._lbl_latency)

    def test_set_viewport_frame_and_ssl_detection(self):
        pix = QPixmap(640, 400)
        pix.fill(Qt.GlobalColor.darkBlue)

        # 1. Test HTTPS
        self.browser.set_viewport_frame(pix, url="https://github.com", title="GitHub", latency_ms=22)
        self.assertEqual(self.browser._current_url, "https://github.com")
        self.assertEqual(self.browser._page_title, "GitHub")
        self.assertIn("HTTPS", self.browser._lbl_ssl.text())

        # 2. Test Localhost
        self.browser.set_viewport_frame(pix, url="http://localhost:3000/dashboard", title="Local Dev", latency_ms=4)
        self.assertIn("LOCAL", self.browser._lbl_ssl.text())

        # 3. Test HTTP insecure
        self.browser.set_viewport_frame(pix, url="http://example.com", title="Example", latency_ms=45)
        self.assertIn("HTTP", self.browser._lbl_ssl.text())

    def test_beacon_trigger_and_decay(self):
        self.browser.trigger_interaction_beacon(0.5, 0.5)
        self.assertIsNotNone(self.browser._beacon_pos)
        self.assertGreater(self.browser._beacon_radius, 0.0)
        self.assertEqual(self.browser._beacon_alpha, 1.0)

        # Step beacon multiple times until decay
        for _ in range(20):
            self.browser._step_beacon()
        self.assertIsNone(self.browser._beacon_pos)

    def test_reader_mode_toggle(self):
        self.browser.set_reader_content("Test Article", "This is extracted article content.")
        self.assertTrue(self.browser._reader_active)
        self.assertEqual(self.browser._stack.currentIndex(), 1)
        self.assertIn("Test Article", self.browser._txt_reader.toPlainText())

        # Toggle back to web
        self.browser._toggle_reader()
        self.assertFalse(self.browser._reader_active)
        self.assertEqual(self.browser._stack.currentIndex(), 0)

    def test_render_ar_pixmap(self):
        pix = QPixmap(640, 400)
        pix.fill(Qt.GlobalColor.black)
        self.browser.set_viewport_frame(pix, url="https://news.ycombinator.com")

        ar_pix = self.browser.render_ar_pixmap(width=480, height=300)
        self.assertFalse(ar_pix.isNull())
        self.assertEqual(ar_pix.width(), 480)
        self.assertEqual(ar_pix.height(), 300)

    def test_signals_emit_on_actions(self):
        nav_emitted = []
        action_emitted = []
        closed_emitted = []

        self.browser.navigate_requested.connect(lambda url: nav_emitted.append(url))
        self.browser.action_requested.connect(lambda act, p: action_emitted.append(act))
        self.browser.closed.connect(lambda: closed_emitted.append(True))

        # Enter URL
        self.browser._txt_url.setText("https://python.org")
        self.browser._on_url_entered()
        self.assertEqual(nav_emitted, ["https://python.org"])

        # Navigation buttons
        self.browser._on_back()
        self.browser._on_fwd()
        self.browser._on_reload()
        self.assertEqual(action_emitted, ["back", "forward", "reload"])

        # Close
        self.browser._on_close()
        self.assertEqual(closed_emitted, [True])


if __name__ == "__main__":
    unittest.main()
