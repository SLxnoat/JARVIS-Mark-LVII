"""tests/test_ar_browser_stream.py — Unit Tests for Playwright to AR Browser Viewport Streaming."""

import os
import unittest
from pathlib import Path
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor, QImage, QPixmap
from PyQt6.QtWidgets import QApplication

from gui.window import MainWindow
from ui import JarvisUI
from plugins.inbuilt_hud_browser import _dispatch_frame_to_player


class TestARBrowserStream(unittest.TestCase):
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

    def test_signals_and_bridge_methods_exist(self):
        self.assertTrue(hasattr(self.win, "_browser_holo_sig"))
        self.assertTrue(hasattr(self.win, "_browser_close_sig"))
        self.assertTrue(hasattr(self.win, "_browser_beacon_sig"))
        self.assertTrue(hasattr(self.win, "_browser_reader_sig"))

        self.assertTrue(hasattr(self.player, "show_ar_browser"))
        self.assertTrue(hasattr(self.player, "close_ar_browser"))
        self.assertTrue(hasattr(self.player, "highlight_ar_browser_beacon"))
        self.assertTrue(hasattr(self.player, "show_ar_reader"))

    def test_show_ar_browser_projects_to_hud_layer2(self):
        # Create a small dummy png
        img = QImage(320, 200, QImage.Format.Format_ARGB32)
        img.fill(QColor("cyan"))
        from PyQt6.QtCore import QBuffer, QIODevice
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buf, "PNG")
        raw_bytes = buf.data().data()

        # Call thread-safe bridge method
        self.player.show_ar_browser(
            url="https://news.ycombinator.com",
            image_bytes=raw_bytes,
            title="Hacker News",
        )

        # Allow Qt event loop to process the signal
        QApplication.processEvents()

        # Verify pane registered in HudCanvas
        self.assertIn("browser", self.win.hud._active_holo_panes)
        pane = self.win.hud._active_holo_panes["browser"]
        self.assertIn("Hacker News", pane["title"])
        self.assertIsNotNone(pane["pixmap"])
        self.assertFalse(pane["pixmap"].isNull())

    def test_laser_beacon_highlight(self):
        self.player.highlight_ar_browser_beacon(0.5, 0.5)
        QApplication.processEvents()
        if self.win._browser_viewport is not None:
            self.assertIsNotNone(self.win._browser_viewport._beacon_pos)

    def test_close_ar_browser_unregisters_from_hud(self):
        self.player.close_ar_browser()
        QApplication.processEvents()
        self.assertNotIn("browser", self.win.hud._active_holo_panes)
        self.assertEqual(self.win.hud._avatar_tgt_dock, 0.0)

    def test_toggle_ar_browser_focus_docks_avatar(self):
        # Register a browser pane first
        self.player.show_ar_browser(
            url="https://example.com",
            image_bytes=b"dummy",
            title="Example",
        )
        QApplication.processEvents()

        # Toggle focus to True
        self.player.toggle_ar_browser_focus(True)
        QApplication.processEvents()

        self.assertEqual(self.win.hud._avatar_tgt_dock, 1.0)
        self.assertIn("browser", self.win.hud._active_holo_panes)
        self.assertEqual(self.win.hud._active_holo_panes["browser"]["tgt_focus"], 1.0)

        # Toggle focus back to False
        self.player.toggle_ar_browser_focus(False)
        QApplication.processEvents()

        self.assertEqual(self.win.hud._avatar_tgt_dock, 0.0)
        self.assertEqual(self.win.hud._active_holo_panes["browser"]["tgt_focus"], 0.0)

    def test_playwright_uninstalled_fallback(self):
        from unittest.mock import patch
        import plugins.inbuilt_hud_browser as ib

        with patch.object(ib, "PLAYWRIGHT_AVAILABLE", False):
            msg = ib.run({"action": "open", "url": "https://example.com"})
            self.assertIn("Playwright browser engine is not installed", msg)

    def test_show_ar_reader_renders_reader_mode(self):
        self.player.show_ar_reader(
            title="Quantum Computing Article",
            markdown="# Quantum Supremacy\n\nRecent advances show superconducting qubits achieve exponential speedup."
        )
        QApplication.processEvents()

        self.assertIn("browser", self.win.hud._active_holo_panes)
        pane = self.win.hud._active_holo_panes["browser"]
        self.assertIn("Quantum Computing Article", pane["title"])
        self.assertIsNotNone(pane["pixmap"])
        self.assertFalse(pane["pixmap"].isNull())

    def test_dispatch_frame_to_player_helper(self):
        test_file = Path("screenshots") / "test_frame.png"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        img = QImage(200, 100, QImage.Format.Format_ARGB32)
        img.fill(QColor("magenta"))
        img.save(str(test_file))

        try:
            calls = []
            class MockPlayer:
                def show_ar_browser(self, url, image_bytes, title):
                    calls.append((url, len(image_bytes), title))

            mock_p = MockPlayer()
            _dispatch_frame_to_player(mock_p, str(test_file), "https://example.org", "Example Title")

            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][0], "https://example.org")
            self.assertGreater(calls[0][1], 0)
            self.assertEqual(calls[0][2], "Example Title")
        finally:
            if test_file.exists():
                test_file.unlink()


if __name__ == "__main__":
    unittest.main()
