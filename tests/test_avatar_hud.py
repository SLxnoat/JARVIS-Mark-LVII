"""
Unit tests for JARVIS Cybernetic Face Matrix and Avatar HUD.
"""

import sys
import unittest
import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QGuiApplication

from core import avatar_mesh
from core import avatar_holo
from core.avatar import HoloAvatar


class TestAvatarFaceMatrix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Offscreen application for headless rendering
        if QGuiApplication.instance() is None:
            cls.app = QGuiApplication(sys.argv)
        else:
            cls.app = QGuiApplication.instance()

    def test_mesh_neck_removed(self):
        """Verify the neck has been completely removed from the head mesh."""
        mesh = avatar_mesh.get_head_mesh()
        self.assertEqual(mesh["verts"].shape[0], 684, "Verts should only contain cranial + face geometry (684).")
        self.assertEqual(mesh["faces"].shape[0], 1330, "Faces should match cranial + face geometry (1330).")
        self.assertEqual(mesh["span"], (1.0, -1.0), "Head span should be exactly crown (+1.0) to chin (-1.0) with no neck.")

        # Check landmarks
        landmarks = mesh["landmarks"]
        self.assertIn("jawline", landmarks, "Jawline landmark must be present for sculpted chin rendering.")
        self.assertIn("nose", landmarks, "Nose landmark must be present.")
        self.assertIn("eye_l", landmarks)
        self.assertIn("eye_r", landmarks)
        self.assertIn("lips_in", landmarks)
        self.assertIn("lips_out", landmarks)

        # Check point cloud neck flag
        pc = avatar_mesh.get_point_cloud()
        self.assertEqual(int(pc["neck"].sum()), 0, "No neck dots should exist in point cloud.")

    def test_furniture_dimensions(self):
        """Verify furniture bounds are balanced without neck padding."""
        self.assertEqual(avatar_holo.TOP, 1.15)
        self.assertEqual(avatar_holo.BOT, 1.15)

    def test_avatar_lifecycle_and_step(self):
        """Verify HoloAvatar step animation works across speech, listening, and idle states."""
        av = HoloAvatar()
        self.assertEqual(av.TOP, 1.15)
        self.assertEqual(av.BOT, 1.15)
        self.assertEqual(av.SPAN, 2.30)

        # Step during speaking
        av.step(0.016, amp=0.8, speaking=True, muted=False)
        self.assertGreater(av._mouth, 0.0)
        self.assertGreater(av._glow, 0.0)

        # Step during muted/idle
        av.step(0.016, amp=0.0, speaking=False, muted=True)
        self.assertIsNotNone(av._gaze)

    def test_face_matrix_rendering_headless(self):
        """Verify face matrix renders cleanly without crashing in QPainter."""
        av = HoloAvatar()
        av.mode = "points"
        av.step(0.016, amp=0.5, speaking=True, muted=False)

        img = QImage(400, 400, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.black)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        try:
            av.paint(p, 200, 200, 120, QColor(0, 240, 255), QColor(255, 180, 0), QColor(5, 10, 20), half_w=180)
        finally:
            p.end()

        # Check that something was rendered (not a blank black image)
        non_zero = False
        for y in range(150, 250, 10):
            for x in range(150, 250, 10):
                pixel = img.pixelColor(x, y)
                if pixel.red() > 0 or pixel.green() > 0 or pixel.blue() > 0:
                    non_zero = True
                    break
            if non_zero:
                break
        self.assertTrue(non_zero, "Rendered image should contain luminous face matrix pixels.")

    def test_solid_mode_rendering_headless(self):
        """Verify solid mode also renders without neck cleanly."""
        av = HoloAvatar()
        av.mode = "solid"
        av.step(0.016, amp=0.2, speaking=False, muted=False)

        img = QImage(400, 400, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.black)
        p = QPainter(img)
        try:
            av.paint(p, 200, 200, 120, QColor(0, 240, 255), QColor(255, 180, 0), QColor(5, 10, 20), half_w=180)
        finally:
            p.end()


if __name__ == "__main__":
    unittest.main()
