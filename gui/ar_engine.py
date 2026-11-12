"""gui/ar_engine.py — High-Performance Zero-GPU Vectorized 3D Spatial AR Engine for JARVIS Mark LVII.

Provides 3D spatial transformations, perspective projections, frustum clipping,
back-face culling, and camera matrix operations using vectorized NumPy routines.
Operates with sub-millisecond overhead to power the 4 depth layers of the
AR Holographic Workstation.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple, Union

import numpy as np


class Camera3D:
    """3D Camera model with Euler rotation, target focal tracking, and 4x4 matrix computation."""

    def __init__(
        self,
        fov: float = 55.0,
        distance: float = 650.0,
        yaw: float = 0.0,
        pitch: float = 0.0,
        roll: float = 0.0,
        target: Optional[Union[List[float], np.ndarray]] = None,
        near: float = 10.0,
        far: float = 3000.0,
    ) -> None:
        self.fov = float(fov)
        self.distance = float(distance)
        self.yaw = float(yaw)          # Degrees around Y axis (horizontal)
        self.pitch = float(pitch)      # Degrees around X axis (vertical)
        self.roll = float(roll)        # Degrees around Z axis (tilt)
        self.near = float(near)
        self.far = float(far)
        
        self.target = np.array(target if target is not None else [0.0, 0.0, 0.0], dtype=np.float32)
        self.up_ref = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        
        # Parallax and gaze offsets (smoothed)
        self.gaze_x: float = 0.0
        self.gaze_y: float = 0.0

    @property
    def eye_position(self) -> np.ndarray:
        """Computes the eye position in 3D Cartesian world space from spherical/Euler coordinates."""
        rad_yaw = math.radians(self.yaw + self.gaze_x)
        rad_pitch = math.radians(self.pitch + self.gaze_y)
        
        # Spherical to Cartesian calculation
        x = self.target[0] + self.distance * math.sin(rad_yaw) * math.cos(rad_pitch)
        y = self.target[1] + self.distance * math.sin(rad_pitch)
        z = self.target[2] + self.distance * math.cos(rad_yaw) * math.cos(rad_pitch)
        return np.array([x, y, z], dtype=np.float32)

    def set_gaze(self, normalized_x: float, normalized_y: float, factor: float = 12.0) -> None:
        """Sets gaze parallax offset from normalized screen coordinates (-1.0 to +1.0)."""
        self.gaze_x = float(normalized_x * factor)
        self.gaze_y = float(-normalized_y * (factor * 0.75))

    def get_view_matrix(self) -> np.ndarray:
        """Constructs a 4x4 View Matrix (Look-At)."""
        eye = self.eye_position
        target = self.target
        up = self.up_ref

        # Forward vector (normalized)
        forward = target - eye
        f_norm = np.linalg.norm(forward)
        if f_norm < 1e-6:
            forward = np.array([0.0, 0.0, -1.0], dtype=np.float32)
        else:
            forward = forward / f_norm

        # Right vector (normalized)
        right = np.cross(forward, up)
        r_norm = np.linalg.norm(right)
        if r_norm < 1e-6:
            right = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        else:
            right = right / r_norm

        # True Up vector
        true_up = np.cross(right, forward)

        # Build Look-At View Matrix
        view = np.identity(4, dtype=np.float32)
        view[0, :3] = right
        view[1, :3] = true_up
        view[2, :3] = -forward  # Camera looks along -Z in standard view space
        view[0, 3] = -np.dot(right, eye)
        view[1, 3] = -np.dot(true_up, eye)
        view[2, 3] = np.dot(forward, eye)

        # Optional Roll rotation around Z
        if abs(self.roll) > 1e-4:
            rad_roll = math.radians(self.roll)
            cos_r = math.cos(rad_roll)
            sin_r = math.sin(rad_roll)
            roll_m = np.identity(4, dtype=np.float32)
            roll_m[0, 0] = cos_r
            roll_m[0, 1] = -sin_r
            roll_m[1, 0] = sin_r
            roll_m[1, 1] = cos_r
            view = roll_m @ view

        return view

    def get_projection_matrix(self, aspect: float) -> np.ndarray:
        """Constructs a standard 4x4 Perspective Projection Matrix."""
        aspect = max(1e-4, float(aspect))
        fov_rad = math.radians(self.fov)
        f = 1.0 / math.tan(fov_rad / 2.0)
        
        proj = np.zeros((4, 4), dtype=np.float32)
        proj[0, 0] = f / aspect
        proj[1, 1] = f
        proj[2, 2] = (self.far + self.near) / (self.near - self.far)
        proj[2, 3] = (2.0 * self.far * self.near) / (self.near - self.far)
        proj[3, 2] = -1.0
        return proj


def perspective_project(
    points3d: np.ndarray,
    width: float,
    height: float,
    camera: Camera3D,
    model_matrix: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Projects 3D points in world space onto 2D screen coordinates using 4x4 matrix vectorization.

    Parameters:
        points3d: Array-like of shape (N, 3) representing 3D coordinates.
        width: Screen/canvas pixel width.
        height: Screen/canvas pixel height.
        camera: Camera3D instance providing view and projection matrices.
        model_matrix: Optional 4x4 model transformation matrix.

    Returns:
        (points2d, depths, visible_mask):
            points2d: ndarray of shape (N, 2) with screen pixel coordinates (X, Y).
            depths: ndarray of shape (N,) with view-space Z depths (higher = further away).
            visible_mask: boolean ndarray of shape (N,) indicating points in front of near plane
                          and within normalized device coordinate (NDC) frustum limits.
    """
    pts = np.asarray(points3d, dtype=np.float32)
    n_points = pts.shape[0]
    if n_points == 0:
        return (
            np.zeros((0, 2), dtype=np.float32),
            np.zeros((0,), dtype=np.float32),
            np.zeros((0,), dtype=bool),
        )

    # Convert to homogeneous coordinates (N, 4)
    if pts.shape[1] == 3:
        homo = np.hstack([pts, np.ones((n_points, 1), dtype=np.float32)])
    else:
        homo = pts

    # Compute View and Projection matrices
    aspect = width / max(1.0, height)
    view = camera.get_view_matrix()
    proj = camera.get_projection_matrix(aspect)

    # Combined transformation: M_proj @ M_view @ [M_model]
    if model_matrix is not None:
        mv = view @ model_matrix
    else:
        mv = view
    
    mvp = proj @ mv

    # Vectorized transform: (N, 4) @ MVP.T -> (N, 4)
    clip = homo @ mvp.T

    # W component in clip space
    w = clip[:, 3]
    visible_mask = (w > camera.near) & (w < camera.far)

    # Safe division avoiding divide-by-zero
    w_safe = np.where(visible_mask, w, 1.0)[:, np.newaxis]
    ndc = clip[:, :3] / w_safe

    # Screen coordinates:
    # X_screen = (X_ndc + 1.0) * 0.5 * width
    # Y_screen = (1.0 - Y_ndc) * 0.5 * height (Qt screen Y coordinates point down)
    x_screen = (ndc[:, 0] + 1.0) * 0.5 * width
    y_screen = (1.0 - ndc[:, 1]) * 0.5 * height
    points2d = np.column_stack([x_screen, y_screen])

    # Frustum clip test in NDC bounds [-1.0, +1.0] with a small margin for aesthetics
    frustum_mask = (
        visible_mask
        & (ndc[:, 0] >= -1.2)
        & (ndc[:, 0] <= 1.2)
        & (ndc[:, 1] >= -1.2)
        & (ndc[:, 1] <= 1.2)
    )

    depths = w.copy()
    return points2d, depths, frustum_mask


def cull_backfaces(
    vertices: np.ndarray,
    faces: np.ndarray,
    camera_pos: np.ndarray,
) -> np.ndarray:
    """Computes back-face culling for 3D triangle meshes using vectorized normal dot products.

    Parameters:
        vertices: ndarray of shape (V, 3) containing 3D vertex positions.
        faces: ndarray of shape (F, 3) containing integer vertex indices for each triangle.
        camera_pos: ndarray of shape (3,) with the camera world position.

    Returns:
        boolean ndarray of shape (F,) where True indicates front-facing (visible) triangles.
    """
    v = np.asarray(vertices, dtype=np.float32)
    f = np.asarray(faces, dtype=np.int32)
    if f.size == 0 or v.size == 0:
        return np.zeros((0,), dtype=bool)

    # Triangles: v0, v1, v2 for each face
    v0 = v[f[:, 0]]
    v1 = v[f[:, 1]]
    v2 = v[f[:, 2]]

    # Surface edge vectors
    edge1 = v1 - v0
    edge2 = v2 - v0

    # Cross product -> Face normals (F, 3)
    normals = np.cross(edge1, edge2)

    # Vector from camera to face vertices
    cam_pos = np.asarray(camera_pos, dtype=np.float32)
    view_vecs = v0 - cam_pos

    # Vectorized dot product between normal and view vector
    # Front-facing if dot product < 0 (pointing towards camera in standard winding)
    dot_products = np.einsum("ij,ij->i", normals, view_vecs)
    return dot_products < 0.0


def make_transform_matrix(
    translation: Optional[Tuple[float, float, float]] = None,
    rotation_euler: Optional[Tuple[float, float, float]] = None,
    scale: Optional[Union[float, Tuple[float, float, float]]] = None,
) -> np.ndarray:
    """Constructs a 4x4 affine model transformation matrix (Scale * Rotation * Translation)."""
    m = np.identity(4, dtype=np.float32)

    # Translation
    if translation is not None:
        m[0, 3] = float(translation[0])
        m[1, 3] = float(translation[1])
        m[2, 3] = float(translation[2])

    # Rotation (Euler angles in degrees: yaw(Y), pitch(X), roll(Z))
    if rotation_euler is not None:
        rx, ry, rz = [math.radians(float(a)) for a in rotation_euler]
        
        # Rx
        cx, sx = math.cos(rx), math.sin(rx)
        rot_x = np.array([
            [1, 0, 0, 0],
            [0, cx, -sx, 0],
            [0, sx, cx, 0],
            [0, 0, 0, 1]
        ], dtype=np.float32)
        
        # Ry
        cy, sy = math.cos(ry), math.sin(ry)
        rot_y = np.array([
            [cy, 0, sy, 0],
            [0, 1, 0, 0],
            [-sy, 0, cy, 0],
            [0, 0, 0, 1]
        ], dtype=np.float32)
        
        # Rz
        cz, sz = math.cos(rz), math.sin(rz)
        rot_z = np.array([
            [cz, -sz, 0, 0],
            [sz, cz, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ], dtype=np.float32)
        
        rot = rot_y @ rot_x @ rot_z
        m = m @ rot

    # Scaling
    if scale is not None:
        if isinstance(scale, (int, float)):
            sx, sy, sz = float(scale), float(scale), float(scale)
        else:
            sx, sy, sz = float(scale[0]), float(scale[1]), float(scale[2])
        scale_m = np.identity(4, dtype=np.float32)
        scale_m[0, 0] = sx
        scale_m[1, 1] = sy
        scale_m[2, 2] = sz
        m = m @ scale_m

    return m


def generate_spatial_grid(
    width: float = 1200.0,
    depth: float = 1200.0,
    spacing: float = 80.0,
    y_floor: float = -220.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Generates Layer 0 deep spatial perspective grid line segments.

    Returns:
        (line_start_points, line_end_points) as (N, 3) arrays ready for perspective projection.
    """
    x_steps = int(width / spacing)
    z_steps = int(depth / spacing)
    
    half_w = width / 2.0
    half_d = depth / 2.0

    lines_start = []
    lines_end = []

    # Parallel lines along Z
    for i in range(-x_steps // 2, x_steps // 2 + 1):
        x = i * spacing
        lines_start.append([x, y_floor, -half_d])
        lines_end.append([x, y_floor, half_d])

    # Parallel lines along X
    for j in range(-z_steps // 2, z_steps // 2 + 1):
        z = j * spacing
        lines_start.append([-half_w, y_floor, z])
        lines_end.append([half_w, y_floor, z])

    return np.array(lines_start, dtype=np.float32), np.array(lines_end, dtype=np.float32)


def generate_orbit_ring(
    radius: float,
    segments: int = 48,
    tilt_yaw: float = 0.0,
    tilt_pitch: float = 0.0,
    center: Optional[Tuple[float, float, float]] = None,
) -> np.ndarray:
    """Generates 3D coordinates for Layer 1 telemetry orbital rings.

    Returns:
        (segments, 3) array of connected vertices forming a smooth 3D circle.
    """
    angles = np.linspace(0, 2 * np.pi, segments, endpoint=False, dtype=np.float32)
    x = radius * np.cos(angles)
    y = np.zeros_like(x)
    z = radius * np.sin(angles)

    ring = np.column_stack([x, y, z])

    # Apply tilts
    rot = make_transform_matrix(
        translation=center if center is not None else (0.0, 0.0, 0.0),
        rotation_euler=(tilt_pitch, tilt_yaw, 0.0),
    )

    homo = np.hstack([ring, np.ones((segments, 1), dtype=np.float32)])
    transformed = (homo @ rot.T)[:, :3]
    return transformed


def project_holo_pane(
    center: Tuple[float, float, float],
    width: float,
    height: float,
    yaw: float,
    pitch: float,
    screen_w: float,
    screen_h: float,
    camera: Camera3D,
) -> Tuple[np.ndarray, bool]:
    """Calculates 3D corners and projects a floating AR rectangular pane (Layer 2).

    Returns:
        (quad_points2d, is_visible):
            quad_points2d: (4, 2) array containing [Top-Left, Top-Right, Bottom-Right, Bottom-Left].
            is_visible: True if all 4 corners are in front of the camera.
    """
    half_w = width / 2.0
    half_h = height / 2.0

    # Local 2D pane quad in XY space
    local_quad = np.array([
        [-half_w,  half_h, 0.0],  # Top-Left
        [ half_w,  half_h, 0.0],  # Top-Right
        [ half_w, -half_h, 0.0],  # Bottom-Right
        [-half_w, -half_h, 0.0],  # Bottom-Left
    ], dtype=np.float32)

    # Transformation to world space
    rot = make_transform_matrix(translation=center, rotation_euler=(pitch, yaw, 0.0))
    homo = np.hstack([local_quad, np.ones((4, 1), dtype=np.float32)])
    world_quad = (homo @ rot.T)[:, :3]

    pts2d, depths, mask = perspective_project(world_quad, screen_w, screen_h, camera)
    all_visible = bool(np.all(mask))
    return pts2d, all_visible
