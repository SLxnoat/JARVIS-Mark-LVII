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
from core.plugin_loader import _HUDCaptureProxy
import plugins.list_plugins as list_plugins
import plugins.plugin_describe as plugin_describe
import plugins.tool_chain as tool_chain
import plugins.docker_sentinel as docker_sentinel
import plugins.firewall_warden as firewall_warden
import plugins.crypto_vault_sentinel as crypto_vault_sentinel
import plugins.multilingual_live_translator as translator
import plugins.pci_hardware_radar as pci_radar
import plugins.celestial_ephemeris as celestial
from memory.session_recovery import write_turn_marker, check_recovery_marker, clear_turn_marker


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

    def test_hud_capture_proxy(self):
        player = MockPlayer()
        proxy = _HUDCaptureProxy(player)
        proxy.show_content("TEST TITLE", "Telemetry data 12345")
        title, content = proxy.wait_captured(timeout=0.1)
        self.assertEqual(title, "TEST TITLE")
        self.assertIn("Telemetry data 12345", content)
        self.assertEqual(len(player.content_cards), 1)

    def test_docker_sentinel_factual_return(self):
        player = MockPlayer()
        res = docker_sentinel.run({}, player=player)
        self.assertIn("Sir", res)
        self.assertTrue("Docker" in res or "container" in res.lower())
        self.assertTrue(len(player.content_cards) >= 1)

    def test_firewall_warden_factual_return(self):
        player = MockPlayer()
        res = firewall_warden.run({}, player=player)
        self.assertIn("Sir", res)
        self.assertIn("firewall", res.lower())
        self.assertTrue(len(player.content_cards) >= 1)

    def test_crypto_vault_sentinel_factual_return(self):
        player = MockPlayer()
        res = crypto_vault_sentinel.run({}, player=player)
        self.assertIn("Sir", res)
        self.assertIn("SSH", res)
        self.assertTrue(len(player.content_cards) >= 1)

    def test_translator_direct_return(self):
        player = MockPlayer()
        res = translator.run({"text": "Hello world", "target_language": "Spanish"}, player=player)
        self.assertIn("Spanish", res)
        self.assertIn("is:", res)
        self.assertTrue(len(player.content_cards) >= 1)

    def test_pci_radar_factual_return(self):
        player = MockPlayer()
        res = pci_radar.run({}, player=player)
        self.assertIn("Sir", res)
        self.assertIn("PCIe", res)
        self.assertTrue(len(player.content_cards) >= 1)

    def test_celestial_ephemeris_factual_return(self):
        player = MockPlayer()
        res = celestial.run({}, player=player)
        self.assertIn("Sir", res)
        self.assertIn("moon", res.lower())
        self.assertTrue(len(player.content_cards) >= 1)

    def test_tool_chain_structured_steps(self):
        player = MockPlayer()
        steps = [
            {"tool": "list_plugins", "params": {"category": "security"}},
            {"tool": "plugin_describe", "params": {"name": "firewall_warden"}},
        ]
        res = tool_chain.run({"goal": "Security audit pipeline", "steps": steps}, player=player)
        self.assertIn("Sir", res)
        self.assertIn("pipeline", res.lower())

    def test_session_recovery_markers(self):
        write_turn_marker(prompt="Audit container fleet", tool_name="docker_sentinel")
        marker = check_recovery_marker()
        self.assertIsNotNone(marker)
        self.assertEqual(marker["tool_name"], "docker_sentinel")
        # Ensure it was cleared after recovery
        marker_again = check_recovery_marker()
        self.assertIsNone(marker_again)


if __name__ == "__main__":
    unittest.main()


class TestSkillLoader(unittest.TestCase):
    """Verifies Anthropic/Hermes Agent Skills system integration."""

    def test_skill_loader_list(self):
        import plugins.skill_loader as sl
        output = sl.run({"action": "list"})
        self.assertIn("Available JARVIS Skills", output)
        self.assertIn("systematic-debugging", output)
        self.assertIn("test-driven-development", output)
        self.assertIn("computer-use", output)

    def test_skill_loader_read(self):
        import plugins.skill_loader as sl
        output = sl.run({"action": "read", "skill_name": "systematic-debugging"})
        self.assertIn("Systematic Debugging", output)
        self.assertIn("NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST", output)

    def test_skill_loader_missing(self):
        import plugins.skill_loader as sl
        output = sl.run({"action": "read", "skill_name": "non_existent_skill_xyz"})
        self.assertIn("not found", output.lower())
