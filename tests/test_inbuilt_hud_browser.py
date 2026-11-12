"""
Unit tests for plugins/inbuilt_hud_browser.py
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock

from plugins import inbuilt_hud_browser


class TestInbuiltHudBrowser(unittest.TestCase):
    def setUp(self):
        self.mock_player = MagicMock()
        self.mock_player.show_image = MagicMock()
        self.mock_player.show_content = MagicMock()
        self.mock_player.stop_video = MagicMock()
        self.mock_player.write_log = MagicMock()

    def tearDown(self):
        # Close any lingering browser session after tests
        try:
            inbuilt_hud_browser.run({"action": "close"}, player=self.mock_player)
        except Exception:
            pass

    def test_plugin_metadata(self):
        self.assertEqual(inbuilt_hud_browser.PLUGIN["name"], "inbuilt_hud_browser")
        self.assertIn("parameters", inbuilt_hud_browser.PLUGIN)
        props = inbuilt_hud_browser.PLUGIN["parameters"]["properties"]
        self.assertIn("action", props)
        self.assertIn("url", props)
        self.assertIn("selector", props)
        self.assertIn("text", props)
        self.assertIn("direction", props)
        self.assertIn("scroll_amount", props)
        self.assertEqual(inbuilt_hud_browser.PLUGIN["parameters"]["required"], ["action"])

    def test_missing_action(self):
        res = inbuilt_hud_browser.run({}, player=self.mock_player)
        self.assertIn("Please specify an action", res)

    def test_unrecognized_action(self):
        res = inbuilt_hud_browser.run({"action": "warp_speed"}, player=self.mock_player)
        self.assertIn("Unrecognized HUD browser action", res)

    def test_full_browser_workflow_local_html(self):
        # Create a local test HTML file
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
            f.write(
                """<!DOCTYPE html>
                <html>
                <head><title>JARVIS HUD Portal</title></head>
                <body style="background:#0a1128; color:#00ffff; height:2000px; padding:20px;">
                    <h1>Core Systems Operational</h1>
                    <h2>Diagnostics</h2>
                    <p>All quantum subroutines and neural decoders are functioning within normal operational parameters.</p>
                    <input id="search-box" type="text" placeholder="Search..." />
                    <button id="activate-btn" onclick="document.title='Button Clicked';">Engage</button>
                </body>
                </html>"""
            )
            temp_path = f.name

        try:
            file_url = f"file://{os.path.abspath(temp_path)}"

            # 1. Action: OPEN
            open_res = inbuilt_hud_browser.run(
                {"action": "open", "url": file_url},
                player=self.mock_player,
            )
            self.assertIn("Displaying JARVIS HUD Portal on the HUD", open_res)
            self.mock_player.show_image.assert_called()
            self.mock_player.write_log.assert_called()

            # 2. Action: TYPE
            type_res = inbuilt_hud_browser.run(
                {"action": "type", "selector": "#search-box", "text": "Mark LVII Online"},
                player=self.mock_player,
            )
            self.assertIn("Entered text into '#search-box'", type_res)

            # 3. Action: CLICK
            click_res = inbuilt_hud_browser.run(
                {"action": "click", "selector": "#activate-btn"},
                player=self.mock_player,
            )
            self.assertIn("Clicked '#activate-btn'", click_res)

            # 4. Action: SCROLL
            scroll_res = inbuilt_hud_browser.run(
                {"action": "scroll", "direction": "down", "scroll_amount": 400},
                player=self.mock_player,
            )
            self.assertIn("Scrolled down on the HUD browser", scroll_res)

            # 5. Action: READ_CONTENT
            read_res = inbuilt_hud_browser.run(
                {"action": "read_content"},
                player=self.mock_player,
            )
            self.assertIn("Extracted content", read_res)
            self.mock_player.show_content.assert_called()

            # 6. Action: SCREENSHOT
            shot_res = inbuilt_hud_browser.run(
                {"action": "screenshot"},
                player=self.mock_player,
            )
            self.assertIn("HUD browser frame refreshed", shot_res)

            # 7. Action: CLOSE
            close_res = inbuilt_hud_browser.run(
                {"action": "close"},
                player=self.mock_player,
            )
            self.assertIn("Browser session closed. Restoring avatar", close_res)
            self.mock_player.stop_video.assert_called()

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_missing_selector_click(self):
        res = inbuilt_hud_browser.run({"action": "click"}, player=self.mock_player)
        self.assertIn("Please specify the link text or selector", res)

    def test_missing_text_type(self):
        res = inbuilt_hud_browser.run({"action": "type", "selector": "#input"}, player=self.mock_player)
        self.assertIn("Please specify the text", res)

    def test_non_existent_selector_graceful_handling(self):
        # Even if an invalid selector fails, it must catch the error and not crash
        res = inbuilt_hud_browser.run(
            {"action": "click", "selector": "#non-existent-button-99999"},
            player=self.mock_player,
        )
        self.assertIn("encountered an issue while performing 'click'", res)


if __name__ == "__main__":
    unittest.main()
