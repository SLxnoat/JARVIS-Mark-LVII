"""
tests/test_daily_productivity_plugins.py - Comprehensive Unit Tests for Group 4 Daily Workstation Productivity Plugins.

Covers:
1. plugins/smart_desktop_cleaner.py
2. plugins/workspace_health_summary.py
3. plugins/smart_reminder_snoozer.py
4. plugins/weather_astronomy_briefing.py
5. plugins/smart_unit_converter.py
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from plugins import (
    smart_desktop_cleaner,
    workspace_health_summary,
    smart_reminder_snoozer,
    weather_astronomy_briefing,
    smart_unit_converter,
)


class MockPlayer:
    def __init__(self):
        self.logs = []
        self.contents = []
        self.spoken = []

    def write_log(self, text):
        self.logs.append(text)

    def show_content(self, title, text):
        self.contents.append((title, text))

    def request_say(self, text):
        self.spoken.append(text)


class TestDailyProductivityPlugins(unittest.TestCase):
    def setUp(self):
        self.player = MockPlayer()
        self.test_dir = tempfile.mkdtemp(prefix="jarvis_cleaner_test_")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    # 1. Smart Desktop Cleaner Tests
    def test_smart_desktop_cleaner_scan_and_organize(self):
        # Create dummy files
        dpath = Path(self.test_dir)
        (dpath / "report.pdf").write_text("dummy doc")
        (dpath / "photo.png").write_text("dummy img")
        (dpath / "photo (1).png").write_text("dummy duplicate")
        (dpath / "script.py").write_text("print('hi')")
        (dpath / "package.zip").write_text("dummy zip")

        # Scan
        res_scan = smart_desktop_cleaner.run(
            {"target_dir": str(dpath), "action": "scan"},
            player=self.player,
        )
        self.assertIn("scan complete", res_scan.lower())
        self.assertGreater(len(self.player.contents), 0)

        # Find Duplicates
        res_dup = smart_desktop_cleaner.run(
            {"target_dir": str(dpath), "action": "find_duplicates"},
            player=self.player,
        )
        self.assertIn("duplicate", res_dup.lower())

        # Dry Run Organize
        res_dry = smart_desktop_cleaner.run(
            {"target_dir": str(dpath), "action": "organize", "dry_run": True},
            player=self.player,
        )
        self.assertIn("dry-run", res_dry.lower())

        # Actual Organize
        res_org = smart_desktop_cleaner.run(
            {"target_dir": str(dpath), "action": "organize", "dry_run": False},
            player=self.player,
        )
        self.assertIn("successfully organized", res_org.lower())
        self.assertTrue((dpath / "Documents" / "report.pdf").exists())
        self.assertTrue((dpath / "Images").exists())
        self.assertTrue((dpath / "Code" / "script.py").exists())

    # 2. Workspace Health Summary Tests
    def test_workspace_health_summary(self):
        res = workspace_health_summary.run(
            {"include_git": True, "include_agenda": True, "include_system": True},
            player=self.player,
        )
        self.assertIsInstance(res, str)
        self.assertIn("sir", res.lower())
        self.assertGreater(len(self.player.contents), 0)

        # Test with player=None
        res_none = workspace_health_summary.run({}, player=None)
        self.assertIsInstance(res_none, str)

    # 3. Smart Reminder Snoozer Tests
    def test_smart_reminder_snoozer(self):
        # Set timer
        res_set = smart_reminder_snoozer.run(
            {"action": "set", "duration": "1s", "message": "Test Toast"},
            player=self.player,
        )
        self.assertIn("timer", res_set.lower())
        self.assertIn("test toast", res_set.lower())

        # List timers
        res_list = smart_reminder_snoozer.run(
            {"action": "list"},
            player=self.player,
        )
        self.assertIn("countdown timer", res_list.lower())

        # Snooze timer
        res_snooze = smart_reminder_snoozer.run(
            {"action": "snooze", "snooze_minutes": 2},
            player=self.player,
        )
        self.assertIn("snoozed", res_snooze.lower())

        # Cancel timer
        res_cancel = smart_reminder_snoozer.run(
            {"action": "cancel"},
            player=self.player,
        )
        self.assertIn("canceled", res_cancel.lower())

    # 4. Weather Astronomy Briefing Tests
    def test_weather_astronomy_briefing(self):
        # Test with London (should handle both online and fallback)
        res = weather_astronomy_briefing.run(
            {"city": "London", "hourly": True, "astronomy": True},
            player=self.player,
        )
        self.assertIsInstance(res, str)
        self.assertTrue(len(res) > 0)

        # Test with invalid city or empty
        res_unknown = weather_astronomy_briefing.run(
            {"city": "NonExistentCity12345XYZ"},
            player=None,
        )
        self.assertIsInstance(res_unknown, str)

    # 5. Smart Unit Converter Tests
    def test_smart_unit_converter(self):
        # Data rate conversion
        res_rate = smart_unit_converter.run(
            {"value": 500, "from_unit": "mbps", "to_unit": "gb/h"},
            player=self.player,
        )
        self.assertIn("225", res_rate)

        # Storage conversion
        res_stor = smart_unit_converter.run(
            {"value": 1, "from_unit": "tib", "to_unit": "gb"},
            player=self.player,
        )
        self.assertIn("1,100", res_stor)

        # Temperature conversion
        res_temp = smart_unit_converter.run(
            {"value": 100, "from_unit": "celsius", "to_unit": "fahrenheit"},
            player=self.player,
        )
        self.assertIn("212", res_temp)

        # Download time estimate
        res_dl = smart_unit_converter.run(
            {"calculation_type": "download_time", "file_size_gb": 50, "speed_mbps": 100},
            player=self.player,
        )
        self.assertIn("downloading", res_dl.lower())
        self.assertIn("minute", res_dl.lower())


if __name__ == "__main__":
    unittest.main()
