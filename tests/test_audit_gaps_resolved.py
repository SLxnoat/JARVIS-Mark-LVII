"""
Tests for new architecture fixes:
- GAP-05: core/thread_pool.py (Hermes cooperative cancellation & worker tracking)
- GAP-06: core/tool_tier.py (dynamic tool tiering: Core 15 + Edge on-demand)
- UI-GAP-03: gui/browser_viewport.py (AR Browser Viewport overlay)
- UI-GAP-05: gui/widgets.py VUMeter
- UI-GAP-06: gui/widgets.py SentinelStatusBar
"""
import os
import sys
import threading
import time
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestThreadPoolRegistry(unittest.TestCase):
    """Verifies GAP-05: centralized worker thread pool and cooperative cancellation."""

    def test_managed_thread_lifecycle_and_cancel(self):
        from core.thread_pool import managed_thread, cancel_all, active_workers, active_tags

        executed = []

        def worker_task(cancel_token: threading.Event):
            while not cancel_token.is_set():
                time.sleep(0.01)
            executed.append("cancelled")

        t = managed_thread(worker_task, tag="test_sensor")
        self.assertTrue(t.is_alive())
        self.assertIn("test_sensor", active_tags())

        # Test cancel_all
        count = cancel_all()
        self.assertGreaterEqual(count, 1)
        t.join(timeout=1.0)
        self.assertFalse(t.is_alive())
        self.assertIn("cancelled", executed)

    def test_cancel_by_tag(self):
        from core.thread_pool import managed_thread, cancel_by_tag

        done = []

        def task_a(cancel: threading.Event):
            while not cancel.is_set():
                time.sleep(0.01)
            done.append("a")

        def task_b(cancel: threading.Event):
            while not cancel.is_set():
                time.sleep(0.01)
            done.append("b")

        ta = managed_thread(task_a, tag="radar_tag")
        tb = managed_thread(task_b, tag="other_tag")

        # Cancel only radar_tag
        cancelled = cancel_by_tag("radar_tag")
        self.assertGreaterEqual(cancelled, 1)
        ta.join(timeout=1.0)
        self.assertFalse(ta.is_alive())
        self.assertIn("a", done)
        self.assertTrue(tb.is_alive())

        # Cleanup tb
        cancel_by_tag("other_tag")
        tb.join(timeout=1.0)


class TestToolTiering(unittest.TestCase):
    """Verifies GAP-06: tool declaration tiering (Core 15 + Edge on-demand)."""

    def test_split_and_budget_declarations(self):
        from core.tool_tier import (
            split_declarations,
            budget_declarations,
            edge_declarations,
            CORE_BUDGET,
            CORE_TOOLS,
        )

        mock_decls = [
            {"name": "list_plugins", "description": "list"},
            {"name": "plugin_describe", "description": "desc"},
            {"name": "custom_edge_tool", "description": "edge 1"},
            {"name": "priority_extra", "description": "tagged", "tier": "core"},
        ]
        # Add 20 dummy tools
        for i in range(20):
            mock_decls.append({"name": f"extra_tool_{i}", "description": f"extra {i}"})

        core, edge = split_declarations(mock_decls)
        self.assertLessEqual(len(core), CORE_BUDGET)
        # Verify self-promoted "priority_extra" is in core
        core_names = [d["name"] for d in core]
        self.assertIn("priority_extra", core_names)
        self.assertIn("list_plugins", core_names)

        # Verify budget_declarations returns core
        budget = budget_declarations(mock_decls)
        self.assertEqual(len(budget), len(core))

        # Verify edge returns non-core
        edge_res = edge_declarations(mock_decls)
        self.assertEqual(len(edge_res), len(edge))
        self.assertNotIn("priority_extra", [d["name"] for d in edge_res])


class TestUIEnhancements(unittest.TestCase):
    """Verifies UI-GAP-03, UI-GAP-05, UI-GAP-06 widgets."""

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(["jarvis-test"])

    def test_vu_meter_level_and_decay(self):
        from gui.widgets import VUMeter
        meter = VUMeter()
        meter.set_level(0.85)
        self.assertAlmostEqual(meter._level, 0.85, places=2)
        self.assertAlmostEqual(meter._peak, 0.85, places=2)

        # Simulate tick decay
        meter._tick()
        self.assertLess(meter._level, 0.85)
        meter.deleteLater()

    def test_sentinel_status_bar(self):
        from gui.widgets import SentinelStatusBar
        bar = SentinelStatusBar()
        bar._refresh()
        # Initial check does not crash
        self.assertIsNotNone(bar)
        bar.deleteLater()

    def test_browser_viewport_widget(self):
        from gui.browser_viewport import BrowserViewport
        vp = BrowserViewport()
        self.assertFalse(vp.isVisible())

        # Load dummy URL
        vp.load(image_path="", url="https://github.com")
        self.assertTrue(vp.isVisible())
        self.assertEqual(vp._ssl_badge.text(), "SECURE")

        vp.close_viewport()
        self.assertFalse(vp.isVisible())
        vp.deleteLater()


if __name__ == "__main__":
    unittest.main()
