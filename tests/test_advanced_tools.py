"""
Tests for Advanced Tools architecture, progressive disclosure plugins, arg coercion, and dispatch hooks.
"""
import unittest
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from plugins._arg_coerce import coerce_params
from plugins._result_cache import get_cached, set_cached, cached_tool_call
import plugins.list_plugins as list_plugins
import plugins.plugin_describe as plugin_describe
import plugins.tool_chain as tool_chain


class MockPlayer:
    def __init__(self):
        self.logs = []
        self.content_cards = []

    def write_log(self, msg: str):
        self.logs.append(msg)

    def show_content(self, title: str, text: str):
        self.content_cards.append((title, text))


class TestAdvancedTools(unittest.TestCase):
    def test_arg_coercion_types(self):
        raw = {
            "is_active": "true",
            "is_false": "False",
            "count": "100",
            "ratio": "0.75",
            "none_val": "null",
            "string_val": "unmodified text",
        }
        coerced = coerce_params(raw)
        self.assertIs(coerced["is_active"], True)
        self.assertIs(coerced["is_false"], False)
        self.assertEqual(coerced["count"], 100)
        self.assertAlmostEqual(coerced["ratio"], 0.75)
        self.assertIsNone(coerced["none_val"])
        self.assertEqual(coerced["string_val"], "unmodified text")

    def test_result_cache_storage(self):
        set_cached("mock:tool_1", {"status": "ok"})
        val = get_cached("mock:tool_1", ttl_seconds=5.0)
        self.assertEqual(val, {"status": "ok"})

        val_expired = get_cached("mock:tool_1", ttl_seconds=-1.0)
        self.assertIsNone(val_expired)

    def test_list_plugins_all_and_category(self):
        player = MockPlayer()
        res_all = list_plugins.run({}, player=player)
        self.assertIn("Sir", res_all)
        self.assertTrue(len(player.content_cards) >= 1)

        player_cat = MockPlayer()
        res_cat = list_plugins.run({"category": "code"}, player=player_cat)
        self.assertIn("Sir", res_cat)

    def test_plugin_describe(self):
        player = MockPlayer()
        res = plugin_describe.run({"name": "list_plugins"}, player=player)
        self.assertIn("Sir", res)
        self.assertTrue(any("Schema: list_plugins" in c[0] for c in player.content_cards))

        res_missing = plugin_describe.run({"name": "non_existent_tool_xyz"})
        self.assertIn("could not find", res_missing.lower())

    def test_tool_chain(self):
        player = MockPlayer()
        res = tool_chain.run(
            {"goal": "Self Diagnostic", "steps": ["list_plugins"]},
            player=player
        )
        self.assertIn("Sir", res)
        self.assertIn("pipeline", res.lower())


if __name__ == "__main__":
    unittest.main()
