"""
Tests for plugins/task_planner.py - Autonomous Goal Planner & Tool Combiner.
"""
import unittest
from unittest.mock import MagicMock, patch
from plugins import task_planner


class DummyPlayer:
    def __init__(self):
        self.logs = []
        self.contents = []
        self.speeches = []
        self.tools_run = []

    def write_log(self, text: str):
        self.logs.append(text)

    def show_content(self, title: str, text: str):
        self.contents.append((title, text))

    def request_say(self, text: str):
        self.speeches.append(text)

    def tool_catalog(self):
        return [
            {
                "name": "systemd_sentinel",
                "brief": "Check Linux service units and journal logs",
                "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING"}, "unit": {"type": "STRING"}}},
            },
            {
                "name": "network_topology",
                "brief": "Tactical network topology radar",
                "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING"}, "target_ip": {"type": "STRING"}}},
            },
            {
                "name": "obsidian_vault",
                "brief": "Search and append notes to Obsidian vault",
                "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING"}, "text": {"type": "STRING"}}},
            },
            {
                "name": "task_planner",
                "brief": "Recursive tool that must be filtered out",
                "parameters": {"type": "OBJECT", "properties": {"goal": {"type": "STRING"}}},
            },
        ]

    def run_tool(self, name: str, parameters: dict):
        self.tools_run.append((name, parameters))
        if name == "systemd_sentinel":
            return "Active: failed (Result: exit-code). nginx.service failed on port 80."
        elif name == "network_topology":
            return "Port 80: OPEN. Banner: Apache/2.4.52."
        elif name == "obsidian_vault":
            return "Appended incident report to daily note."
        return "Tool executed."


class TestTaskPlanner(unittest.TestCase):
    def test_catalog_filtering_and_anti_recursion(self):
        player = DummyPlayer()
        catalog = task_planner._get_tool_catalog(player)
        names = [t["name"] for t in catalog]
        self.assertIn("systemd_sentinel", names)
        self.assertIn("network_topology", names)
        self.assertNotIn("task_planner", names, "task_planner must be excluded from its own catalog")

    def test_format_tool_catalog(self):
        catalog = [
            {
                "name": "dummy_tool",
                "brief": "A sample testing tool",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {"ip": {"type": "STRING"}, "port": {"type": "INTEGER"}},
                    "required": ["ip"],
                },
            }
        ]
        formatted = task_planner._format_tool_catalog(catalog)
        self.assertIn("dummy_tool", formatted)
        self.assertIn("ip*", formatted)
        self.assertIn("port: INTEGER", formatted)

    def test_empty_goal_handling(self):
        result = task_planner.run({"goal": ""})
        self.assertIn("Please provide a specific goal", result)

    @patch("core.gemini.as_json")
    def test_synchronous_multi_step_planning(self, mock_as_json):
        player = DummyPlayer()

        # Step 1: LLM selects systemd_sentinel
        # Step 2: LLM selects network_topology based on port 80 failure
        # Step 3: LLM declares done with summary
        mock_as_json.side_effect = [
            {
                "done": False,
                "thought": "Check systemd service logs for nginx",
                "tool": "systemd_sentinel",
                "parameters": {"action": "logs", "unit": "nginx"},
            },
            {
                "done": False,
                "thought": "Check what is using port 80",
                "tool": "network_topology",
                "parameters": {"action": "service_check", "target_ip": "127.0.0.1"},
            },
            {
                "done": True,
                "thought": "Incident diagnosed",
                "summary": "Port 80 is conflicted between Apache and Nginx.",
                "spoken_response": "Nginx failed because Apache is holding port 80, sir.",
            },
        ]

        result = task_planner.run(
            {"goal": "Find out why nginx failed and fix the port issue", "sync": True},
            player=player,
        )

        self.assertEqual(result, "Nginx failed because Apache is holding port 80, sir.")
        self.assertEqual(len(player.tools_run), 2)
        self.assertEqual(player.tools_run[0][0], "systemd_sentinel")
        self.assertEqual(player.tools_run[1][0], "network_topology")
        self.assertEqual(len(player.contents), 1)
        self.assertEqual(player.contents[0][0], "AUTONOMOUS TASK PLANNER")
        self.assertIn("Port 80 is conflicted", player.contents[0][1])

    @patch("core.gemini.as_json")
    def test_infinite_loop_prevention(self, mock_as_json):
        player = DummyPlayer()

        # Simulate LLM repeatedly calling the exact same tool and params
        mock_as_json.side_effect = [
            {"done": False, "thought": "Check again", "tool": "network_topology", "parameters": {"action": "scan"}},
            {"done": False, "thought": "Check again", "tool": "network_topology", "parameters": {"action": "scan"}},
            {"done": False, "thought": "Check again", "tool": "network_topology", "parameters": {"action": "scan"}},
            {"summary": "Stagnation recovery synthesis", "spoken_response": "I detected a loop and concluded."},
        ]

        result = task_planner.run(
            {"goal": "Scan LAN repeatedly", "sync": True, "max_steps": 5},
            player=player,
        )

        self.assertIn("concluded", result.lower())
        # Should have broken before hitting max 5 steps
        self.assertLessEqual(len(player.tools_run), 3)

    def test_background_thread_execution(self):
        player = DummyPlayer()
        response = task_planner.run({"goal": "Investigate network in background", "sync": False}, player=player)
        self.assertIn("Understood, sir", response)
        self.assertIn("Formulating an autonomous plan", response)


if __name__ == "__main__":
    unittest.main()
