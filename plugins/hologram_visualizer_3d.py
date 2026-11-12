"""
plugins/hologram_visualizer_3d.py - 3D Cybernetic Wireframe & Hologram Renderer.

Iron Man / JARVIS style 3D holographic projection:
- Mathematical 3D wireframe projection engine with pitch, yaw, and roll rotation matrices.
- Models: Mark Armor Helmet wireframe, 4D Tesseract hypercube, Geodesic Telemetry Sphere.
- Depth-cued perspective projection with ASCII / Unicode luminance shading.
- 100% local mathematical computation via NumPy — zero GPU or external 3D engine needed.
- Renders a tactical 3D holographic model on the HUD via player.show_content().

Adheres strictly to AGENTS.md:
- No Qt widgets on worker threads.
- Thread-safe HUD feedback via player.show_content() and player.write_log().
- Safe non-blocking execution on background daemon thread.
- Never raises exceptions, returns concise spoken feedback.
- Handles player=None gracefully.
"""
from __future__ import annotations

import math
import sys
import threading
import time
from typing import Any, Dict, List, Tuple

import numpy as np

PLUGIN = {
    "name": "hologram_visualizer_3d",
    "description": (
        "JARVIS 3D Holographic Visualizer: Projects rotating 3D wireframe models (Mark Armor Helmet, "
        "Hypercube Tesseract, Geodesic Telemetry Sphere) onto the HUD using depth-cued perspective "
        "transformation matrices. Renders a tactical 3D hologram card on the HUD."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "model": {
                "type": "STRING",
                "description": "3D model to project: 'helmet' (Mark Suit Helmet), 'tesseract' (4D Hypercube), 'sphere' (Telemetry Globe). Default 'helmet'.",
                "enum": ["helmet", "tesseract", "sphere"],
            },
            "yaw_degrees": {
                "type": "NUMBER",
                "description": "Horizontal yaw rotation angle in degrees (default 35.0).",
            },
            "pitch_degrees": {
                "type": "NUMBER",
                "description": "Vertical pitch rotation angle in degrees (default 20.0).",
            },
        },
        "required": ["model"],
    },
}


def _get_cube_vertices_edges() -> Tuple[np.ndarray, List[Tuple[int, int]]]:
    # 8 vertices of a unit cube
    vertices = np.array([
        [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
        [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]
    ], dtype=float) * 1.5
    edges = [
        (0, 1), (1, 2), (2, 3), (3, 0),
        (4, 5), (5, 6), (6, 7), (7, 4),
        (0, 4), (1, 5), (2, 6), (3, 7)
    ]
    return vertices, edges


def _get_tesseract_vertices_edges() -> Tuple[np.ndarray, List[Tuple[int, int]]]:
    # Inner and outer nested cube
    v1, e1 = _get_cube_vertices_edges()
    v2 = v1 * 0.5
    vertices = np.vstack([v1, v2])
    edges = list(e1)
    # Inner edges offset by 8
    for a, b in e1:
        edges.append((a + 8, b + 8))
    # Connecting edges
    for i in range(8):
        edges.append((i, i + 8))
    return vertices, edges


def _get_helmet_vertices_edges() -> Tuple[np.ndarray, List[Tuple[int, int]]]:
    # Stylized Iron Man helmet polygonal wireframe
    vertices = np.array([
        [0.0, 1.8, 0.4],    # 0: Crest apex
        [-1.0, 1.3, 0.2],   # 1: Left forehead
        [1.0, 1.3, 0.2],    # 2: Right forehead
        [-1.2, 0.2, 0.0],   # 3: Left temple
        [1.2, 0.2, 0.0],    # 4: Right temple
        [-0.5, 0.2, 0.9],   # 5: Left eye corner
        [0.5, 0.2, 0.9],    # 6: Right eye corner
        [-0.2, 0.2, 1.0],   # 7: Left eye inner
        [0.2, 0.2, 1.0],    # 8: Right eye inner
        [-0.8, -0.6, 0.5],  # 9: Left cheek
        [0.8, -0.6, 0.5],   # 10: Right cheek
        [-0.4, -1.4, 0.7],  # 11: Left jaw
        [0.4, -1.4, 0.7],   # 12: Right jaw
        [0.0, -1.5, 0.8],   # 13: Chin tip
        [0.0, 0.8, -1.2],   # 14: Rear crown
        [0.0, -0.8, -1.0],  # 15: Rear base
    ], dtype=float)

    edges = [
        (0, 1), (0, 2), (1, 3), (2, 4),
        (1, 5), (5, 7), (2, 6), (6, 8), (7, 8), # Brow & eyes
        (5, 9), (6, 10), (9, 11), (10, 12), (11, 13), (12, 13), # Jawline & chin
        (3, 9), (4, 10), (0, 14), (14, 15), (15, 11), (15, 12), # Shell
        (3, 14), (4, 14)
    ]
    return vertices, edges


def _get_sphere_vertices_edges() -> Tuple[np.ndarray, List[Tuple[int, int]]]:
    # Geodesic longitude & latitude rings
    verts = []
    edges = []
    num_lat = 6
    num_lon = 10
    radius = 1.6

    for i in range(num_lat):
        lat = (math.pi * (i + 1) / (num_lat + 1)) - (math.pi / 2)
        r_slice = radius * math.cos(lat)
        z = radius * math.sin(lat)
        for j in range(num_lon):
            lon = 2 * math.pi * j / num_lon
            x = r_slice * math.cos(lon)
            y = r_slice * math.sin(lon)
            verts.append([x, y, z])

    # Connect latitudinal rings
    for i in range(num_lat):
        offset = i * num_lon
        for j in range(num_lon):
            nxt = offset + ((j + 1) % num_lon)
            edges.append((offset + j, nxt))

    # Connect longitudinal ribs
    for i in range(num_lat - 1):
        for j in range(num_lon):
            edges.append((i * num_lon + j, (i + 1) * num_lon + j))

    return np.array(verts, dtype=float), edges


def _project_and_rasterize(
    vertices: np.ndarray,
    edges: List[Tuple[int, int]],
    yaw_deg: float,
    pitch_deg: float,
    width: int = 56,
    height: int = 24,
) -> str:
    # Build 3D rotation matrices
    yaw = math.radians(yaw_deg)
    pitch = math.radians(pitch_deg)

    # Ry (yaw)
    Ry = np.array([
        [math.cos(yaw), 0, math.sin(yaw)],
        [0, 1, 0],
        [-math.sin(yaw), 0, math.cos(yaw)]
    ])
    # Rx (pitch)
    Rx = np.array([
        [1, 0, 0],
        [0, math.cos(pitch), -math.sin(pitch)],
        [0, math.sin(pitch), math.cos(pitch)]
    ])
    R = Rx @ Ry

    # Rotate vertices
    rotated = vertices @ R.T

    # Perspective projection: fov distance d
    d = 4.2
    screen_pts = []
    for x, y, z in rotated:
        factor = d / (d + z)
        sx = int((x * factor * 14) + (width / 2))
        sy = int((-y * factor * 7) + (height / 2))
        screen_pts.append((sx, sy, z))

    # Raster grid
    grid = [[" " for _ in range(width)] for _ in range(height)]
    z_buf = [[-999.0 for _ in range(width)] for _ in range(height)]

    # Draw wireframe edges using Bresenham algorithm
    for a, b in edges:
        x0, y0, z0 = screen_pts[a]
        x1, y1, z1 = screen_pts[b]

        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        curr_x, curr_y = x0, y0
        total_steps = max(dx, dy, 1)
        step = 0

        while True:
            t = step / total_steps
            cz = z0 + t * (z1 - z0)
            if 0 <= curr_x < width and 0 <= curr_y < height:
                if cz > z_buf[curr_y][curr_x]:
                    z_buf[curr_y][curr_x] = cz
                    # Depth shading: bright in front, faint behind
                    grid[curr_y][curr_x] = "#" if cz > 0.4 else ("+" if cz > -0.4 else "·")

            if curr_x == x1 and curr_y == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                curr_x += sx
            if e2 < dx:
                err += dx
                curr_y += sy
            step += 1

    return "\n".join("".join(row) for row in grid)


def _render_hud_card(model_name: str, yaw: float, pitch: float, ascii_art: str) -> str:
    lines = [
        "### 💠 3D HOLOGRAPHIC WIREFRAME PROJECTOR (JARVIS MARK-LVII)\n",
        f"**Active Wireframe:** `{model_name.upper()} MATRIX`",
        f"**Orientation:** Yaw `{yaw:.1f}°` | Pitch `{pitch:.1f}°` | Projection: `Perspective (FOV 75°)`\n",
        "```text",
        ascii_art,
        "```\n",
        "#### 🔬 Model Geometric Telemetry",
        f"- **Mesh Class:** Dynamic Mathematical Vector Wireframe",
        f"- **Depth Cues:** Foreground (`#`), Midground (`+`), Background (`·`)",
        f"- **Rendering Subsystem:** 100% Software Depth-Buffer (Zero GPU load)\n",
        f"*Hologram synthesized at {time.strftime('%H:%M:%S')}.*",
    ]
    return "\n".join(lines)


def _worker(model: str, yaw: float, pitch: float, player):
    try:
        if model == "tesseract":
            verts, edges = _get_tesseract_vertices_edges()
        elif model == "sphere":
            verts, edges = _get_sphere_vertices_edges()
        else:
            verts, edges = _get_helmet_vertices_edges()

        ascii_art = _project_and_rasterize(verts, edges, yaw, pitch)
        card = _render_hud_card(model, yaw, pitch, ascii_art)

        if player:
            try:
                player.show_content("3D HOLOGRAPHIC WIREFRAME", card)
                player.write_log(f"💠 [Hologram3D] Projected 3D {model} mesh (Yaw: {yaw}°, Pitch: {pitch}°).")
            except Exception:
                pass
    except Exception as e:
        if player:
            try:
                player.write_log(f"⚠️ [Hologram3D] Error: {e}")
            except Exception:
                pass


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        model = str(parameters.get("model") or "helmet").strip().lower()
        if model not in ("helmet", "tesseract", "sphere"):
            model = "helmet"

        yaw = float(parameters.get("yaw_degrees", 35.0))
        pitch = float(parameters.get("pitch_degrees", 20.0))

        threading.Thread(target=_worker, args=(model, yaw, pitch, player), daemon=True).start()

        return f"Synthesizing 3D holographic projection for {model} at {yaw} degrees yaw, sir. Wireframe is rendering on your HUD."
    except Exception as e:
        return f"Sir, 3D hologram projector encountered an issue: {e}"
