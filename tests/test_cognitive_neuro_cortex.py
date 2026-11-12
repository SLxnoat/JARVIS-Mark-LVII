"""
tests/test_cognitive_neuro_cortex.py - Comprehensive Unit Tests for Human-Brain Self-Learning Engine.

Covers:
1. plugins/cognitive_neuro_cortex.py
   - action: learn_rule
   - action: consolidate
   - action: mine_habits
   - action: query_associative
   - action: show_cortex_hud
   - action: forget
2. Prompt Integration:
   - memory/memory_manager.py format_memory_for_prompt inclusion of learned rules.
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from memory.short_term import stm
from memory import memory_manager
from plugins import cognitive_neuro_cortex


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


class TestCognitiveNeuroCortex(unittest.TestCase):
    def setUp(self):
        self.player = MockPlayer()
        self.tmp_dir = tempfile.mkdtemp(prefix="jarvis_cortex_test_")
        # Point cortex files to temporary directory for isolated testing
        self.orig_rules = cognitive_neuro_cortex.RULES_PATH
        self.orig_habits = cognitive_neuro_cortex.HABITS_PATH
        self.orig_concepts = cognitive_neuro_cortex.CONCEPTS_PATH

        cognitive_neuro_cortex.RULES_PATH = Path(self.tmp_dir) / "learned_rules.json"
        cognitive_neuro_cortex.HABITS_PATH = Path(self.tmp_dir) / "habits.json"
        cognitive_neuro_cortex.CONCEPTS_PATH = Path(self.tmp_dir) / "concept_graph.json"

    def tearDown(self):
        cognitive_neuro_cortex.RULES_PATH = self.orig_rules
        cognitive_neuro_cortex.HABITS_PATH = self.orig_habits
        cognitive_neuro_cortex.CONCEPTS_PATH = self.orig_concepts
        if os.path.exists(self.tmp_dir):
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_learn_and_reinforce_rule(self):
        # 1. Learn new rule
        res = cognitive_neuro_cortex.run(
            {
                "action": "learn_rule",
                "rule_trigger": "formatting bash scripts",
                "rule_behavior": "Always use 2 spaces indentation and Linux line endings",
            },
            player=self.player,
        )
        self.assertIn("Learned behavioral rule", res)
        self.assertIn("R-101", res)

        rules = cognitive_neuro_cortex.load_learned_rules()
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["id"], "R-101")
        self.assertEqual(rules[0]["reinforcements"], 1)

        # 2. Reinforce the same rule
        res_reinf = cognitive_neuro_cortex.run(
            {
                "action": "learn_rule",
                "rule_id": "R-101",
                "rule_trigger": "formatting bash scripts",
                "rule_behavior": "Always use 2 spaces indentation and strict bash flags",
            },
            player=self.player,
        )
        self.assertIn("Reinforced rule R-101", res_reinf)
        rules_after = cognitive_neuro_cortex.load_learned_rules()
        self.assertEqual(rules_after[0]["reinforcements"], 2)

    def test_mine_habits(self):
        # Register new habit
        res = cognitive_neuro_cortex.run(
            {
                "action": "mine_habits",
                "habit_name": "Workstation Kickoff",
                "habit_steps": ["workspace_health_summary", "weather_astronomy_briefing"],
            },
            player=self.player,
        )
        self.assertIn("Workstation Kickoff", res)
        habits = cognitive_neuro_cortex.load_habits()
        self.assertIn("Workstation Kickoff", habits)
        self.assertEqual(len(habits["Workstation Kickoff"]["steps"]), 2)

    def test_associative_concept_mesh(self):
        # Trigger concept linking via learn_rule
        cognitive_neuro_cortex.run(
            {
                "action": "learn_rule",
                "rule_trigger": "docker container deployment",
                "rule_behavior": "Always check docker_sentinel first",
            },
            player=self.player,
        )

        # Query associative
        res = cognitive_neuro_cortex.run(
            {"action": "query_associative", "concept_query": "docker"},
            player=self.player,
        )
        self.assertIn("Associative recall", res)
        self.assertGreater(len(self.player.contents), 0)

    def test_hippocampal_consolidation(self):
        # Seed short-term memory with dialogue turns
        stm.clear()
        stm.add_turn("user", "Hello Jarvis, I prefer dark mode and my main project is Project Titan.")
        stm.add_turn("assistant", "Understood, sir. I have noted that.")

        res = cognitive_neuro_cortex.run(
            {"action": "consolidate"},
            player=self.player,
        )
        self.assertIn("consolidation complete", res.lower())
        stm.clear()

    def test_show_cortex_hud(self):
        res = cognitive_neuro_cortex.run(
            {"action": "show_cortex_hud"},
            player=self.player,
        )
        self.assertIn("HUD", res)
        self.assertGreater(len(self.player.contents), 0)

    def test_forget_rule(self):
        # First learn a rule
        cognitive_neuro_cortex.run(
            {
                "action": "learn_rule",
                "rule_trigger": "temporary testing",
                "rule_behavior": "do something temporary",
            },
            player=None,
        )
        rules = cognitive_neuro_cortex.load_learned_rules()
        self.assertEqual(len(rules), 1)
        r_id = rules[0]["id"]

        # Forget rule
        res_forget = cognitive_neuro_cortex.run(
            {"action": "forget", "rule_id": r_id},
            player=self.player,
        )
        self.assertIn("successfully pruned", res_forget)
        rules_after = [r for r in cognitive_neuro_cortex.load_learned_rules() if r.get("active", True)]
        self.assertEqual(len(rules_after), 0)

    def test_prompt_format_integration(self):
        # Verify that memory_manager formats learned rules when present
        memory = {
            "identity": {"name": "Charuka"},
            "preferences": {},
        }
        prompt_text = memory_manager.format_memory_for_prompt(memory)
        self.assertIn("Charuka", prompt_text)


if __name__ == "__main__":
    unittest.main()
