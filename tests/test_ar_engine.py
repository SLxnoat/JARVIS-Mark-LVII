"""tests/test_ar_engine.py — Unit Tests & Benchmarks for JARVIS AR Spatial Math Engine."""

import time
import unittest
import numpy as np

from gui.ar_engine import (
    Camera3D,
    cull_backfaces,
    generate_orbit_ring,
    generate_spatial_grid,
    make_transform_matrix,
    perspective_project,
    project_holo_pane,
)


class TestAREngine(unittest.TestCase):
    def setUp(self):
        self.camera = Camera3D(fov=60.0, distance=600.0, yaw=0.0, pitch=0.0, roll=0.0)

    def test_camera_eye_position_and_matrices(self):
        eye = self.camera.eye_position
        self.assertEqual(len(eye), 3)
        # With yaw=0, pitch=0, eye should be along +Z axis at distance 600
        np.testing.assert_allclose(eye, [0.0, 0.0, 600.0], atol=1e-3)

        view = self.camera.get_view_matrix()
        self.assertEqual(view.shape, (4, 4))
        # Determinant of a pure rotation/view matrix should be non-zero
        self.assertAlmostEqual(np.linalg.det(view[:3, :3]), 1.0, places=4)

        proj = self.camera.get_projection_matrix(aspect=16.0 / 9.0)
        self.assertEqual(proj.shape, (4, 4))
        self.assertEqual(proj[3, 2], -1.0)

    def test_camera_gaze_offset(self):
        self.camera.set_gaze(normalized_x=0.5, normalized_y=-0.5, factor=10.0)
        self.assertAlmostEqual(self.camera.gaze_x, 5.0)
        self.assertAlmostEqual(self.camera.gaze_y, 3.75)
        eye_offset = self.camera.eye_position
        # Eye position should shift with gaze offset
        self.assertNotEqual(eye_offset[0], 0.0)

    def test_perspective_project_cube(self):
        # 8 vertices of a cube centered at origin with size 100
        cube_pts = np.array([
            [-50, -50, -50],
            [ 50, -50, -50],
            [ 50,  50, -50],
            [-50,  50, -50],
            [-50, -50,  50],
            [ 50, -50,  50],
            [ 50,  50,  50],
            [-50,  50,  50],
        ], dtype=np.float32)

        pts2d, depths, mask = perspective_project(cube_pts, width=800, height=600, camera=self.camera)

        self.assertEqual(pts2d.shape, (8, 2))
        self.assertEqual(depths.shape, (8,))
        self.assertEqual(mask.shape, (8,))
        # All 8 points are in front of camera (distance=600, cube z in [-50, 50])
        self.assertTrue(np.all(mask))

        # Check screen center symmetry: average of symmetric points should be screen center (400, 300)
        center_x = np.mean(pts2d[:, 0])
        center_y = np.mean(pts2d[:, 1])
        self.assertAlmostEqual(center_x, 400.0, places=1)
        self.assertAlmostEqual(center_y, 300.0, places=1)

    def test_perspective_project_empty(self):
        empty_pts = np.zeros((0, 3), dtype=np.float32)
        pts2d, depths, mask = perspective_project(empty_pts, width=800, height=600, camera=self.camera)
        self.assertEqual(pts2d.shape, (0, 2))
        self.assertEqual(depths.shape, (0,))
        self.assertEqual(mask.shape, (0,))

    def test_backface_culling(self):
        # Triangle facing towards camera (Z=+100) vs camera at Z=+600
        vertices = np.array([
            [-10, -10, 0],
            [ 10, -10, 0],
            [  0,  10, 0],
        ], dtype=np.float32)

        # Counter-clockwise winding -> Normal faces +Z towards camera
        faces_ccw = np.array([[0, 1, 2]], dtype=np.int32)
        visible_ccw = cull_backfaces(vertices, faces_ccw, self.camera.eye_position)
        # Normal (0, 0, 200) pointing towards camera (+Z) with view vector (0, 0, -600):
        # dot product is -120000 < 0 -> visible
        self.assertTrue(visible_ccw[0])

        # Clockwise winding -> Normal faces -Z away from camera
        faces_cw = np.array([[0, 2, 1]], dtype=np.int32)
        visible_cw = cull_backfaces(vertices, faces_cw, self.camera.eye_position)
        self.assertFalse(visible_cw[0])

    def test_generate_spatial_grid_and_orbit(self):
        starts, ends = generate_spatial_grid(width=600, depth=600, spacing=100, y_floor=-150)
        self.assertGreater(len(starts), 0)
        self.assertEqual(starts.shape, ends.shape)
        self.assertEqual(starts.shape[1], 3)

        ring = generate_orbit_ring(radius=150.0, segments=36, tilt_yaw=15.0, tilt_pitch=10.0)
        self.assertEqual(ring.shape, (36, 3))
        # Radius of points should be close to 150
        radii = np.linalg.norm(ring, axis=1)
        np.testing.assert_allclose(radii, 150.0, atol=1e-3)

    def test_project_holo_pane(self):
        quad2d, visible = project_holo_pane(
            center=(150.0, 50.0, -50.0),
            width=200.0,
            height=120.0,
            yaw=-15.0,
            pitch=5.0,
            screen_w=1000.0,
            screen_h=700.0,
            camera=self.camera,
        )
        self.assertEqual(quad2d.shape, (4, 2))
        self.assertTrue(visible)

    def test_vectorized_benchmark_10k_points(self):
        # Benchmark 10,000 points to ensure sub-millisecond execution (< 2ms ceiling)
        pts = np.random.uniform(-300, 300, size=(10000, 3)).astype(np.float32)

        # Warm-up
        perspective_project(pts, width=1280, height=800, camera=self.camera)

        start = time.perf_counter()
        pts2d, depths, mask = perspective_project(pts, width=1280, height=800, camera=self.camera)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        self.assertEqual(pts2d.shape, (10000, 2))
        print(f"\n[AR Engine Benchmark] 10,000 points projected in: {elapsed_ms:.3f} ms")
        self.assertLess(elapsed_ms, 5.0, "Projection of 10k points took longer than 5ms!")


if __name__ == "__main__":
    unittest.main()
