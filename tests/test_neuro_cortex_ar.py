"""tests/test_neuro_cortex_ar.py — Unit Tests for Cognitive Neuro-Cortex Constellation & AR Surface."""

import os
import unittest
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor, QImage, QPixmap
from PyQt6.QtWidgets import QApplication

from gui.neuro_panel import (
    NeuralNode3D, NeuroMeshCanvas, HabitDeckWidget,
    ChromaSearchDrawer, NeuroCortexPanel,
)
from gui.window import MainWindow
from ui import JarvisUI
import plugins.cognitive_neuro_cortex as cortex


class TestNeuroCortexAR(unittest.TestCase):
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

    def test_neuro_mesh_canvas_node_distribution(self):
        canvas = NeuroMeshCanvas()
        self.assertGreater(len(canvas._nodes), 15)
        self.assertGreater(len(canvas._edges), 20)

        # Check node positions are 3D
        for node in canvas._nodes:
            self.assertEqual(node.pos3d.shape, (3,))
            self.assertIn(node.category, ("core", "rules", "habits", "memory", "defense"))

        canvas._timer.stop()

    def test_trigger_learning_spark_ignites_arc(self):
        canvas = NeuroMeshCanvas()
        self.assertFalse(canvas._spark_active)

        canvas.trigger_learning_spark(rule_id="R-101", trigger="Git commit formatting", confidence=0.95)
        self.assertTrue(canvas._spark_active)
        self.assertEqual(canvas._spark_timer, 1.0)
        self.assertGreaterEqual(len(canvas._spark_path), 2)
        self.assertIn("R-101", canvas._last_rule_text)

        canvas._timer.stop()

    def test_habit_deck_refresh(self):
        deck = HabitDeckWidget()
        deck.refresh_data()
        self.assertIsNotNone(deck._cards_layout)

    def test_chroma_search_drawer_search(self):
        drawer = ChromaSearchDrawer()
        drawer._txt_search.setText("python")
        drawer._on_search()
        self.assertIsNotNone(drawer._results_layout)

    def test_neuro_cortex_panel_render_ar_pixmap(self):
        panel = NeuroCortexPanel()
        pix = panel.render_ar_pixmap(480, 300)
        self.assertIsNotNone(pix)
        self.assertFalse(pix.isNull())
        self.assertEqual(pix.width(), 480)
        self.assertEqual(pix.height(), 300)
        panel.constellation._timer.stop()

    def test_signals_and_bridge_methods(self):
        self.assertTrue(hasattr(self.win, "_neuro_learn_sig"))
        self.assertTrue(hasattr(self.win, "_neuro_show_sig"))
        self.assertTrue(hasattr(self.player, "spark_neuro_learning"))
        self.assertTrue(hasattr(self.player, "show_ar_neuro_cortex"))

    def test_spark_neuro_learning_projects_to_hud(self):
        self.player.spark_neuro_learning(rule_id="R-105", trigger="Safe file move", confidence=0.98)
        QApplication.processEvents()

        self.assertIn("neuro", self.win.hud._active_holo_panes)
        pane = self.win.hud._active_holo_panes["neuro"]
        self.assertIn("Neuro-Cortex", pane["title"])
        self.assertIsNotNone(pane["pixmap"])
        self.assertFalse(pane["pixmap"].isNull())

    def test_show_ar_neuro_cortex_projects_to_hud(self):
        self.player.show_ar_neuro_cortex()
        QApplication.processEvents()

        self.assertIn("neuro", self.win.hud._active_holo_panes)
        pane = self.win.hud._active_holo_panes["neuro"]
        self.assertEqual(pane["yaw"], 18.0)

    def test_cortex_plugin_sparks_player_on_learn(self):
        sparks = []

        class MockPlayer:
            def write_log(self, text):
                pass
            def show_content(self, title, text):
                pass
            def spark_neuro_learning(self, rule_id, trigger, conf):
                sparks.append((rule_id, trigger, conf))
            def show_ar_neuro_cortex(self):
                pass

        mp = MockPlayer()
        res = cortex.run(
            {"action": "learn_rule", "rule_trigger": "When writing python code", "rule_behavior": "Follow PEP 8"},
            player=mp,
        )
        self.assertIn("Learned behavioral rule", res)
        self.assertGreater(len(sparks), 0)
        self.assertEqual(sparks[0][1], "When writing python code")
