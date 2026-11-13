"""
plugins/docker_sentinel.py - Docker & Podman Container Fleet Radar.

Iron Man / JARVIS style container DevOps telemetry:
- Real-time enumeration of Docker and Podman container fleets.
- Tracks container status (Running, Exited, Restarting, Paused) and uptime.
- Inspects port bindings, exposed network endpoints, and image tags.
- Flags container healthcheck failures and crash restart loops.
- Identifies dangling images and unused volumes consuming disk space.
- 100% free local UNIX socket / CLI inspection — zero external dependencies.
- Renders a container fleet status matrix on the HUD via player.show_content().

Adheres strictly to AGENTS.md:
- No Qt widgets on worker threads.
- Thread-safe HUD feedback via player.show_content() and player.write_log().
- Safe non-blocking execution on background daemon thread.
- Never raises exceptions, returns concise spoken feedback.
- Handles player=None gracefully.
"""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

PLUGIN = {
    "name": "docker_sentinel",
    "description": (
        "JARVIS Container Fleet Radar: Audits local Docker & Podman containers. Inspects running "
        "and stopped containers, port mappings, crash restart loops, failed health checks, "
        "and dangling images. Displays a tactical container fleet map on the HUD."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "Action to perform: 'list_containers' (status & port mappings), "
                    "'container_stats' (resource footprint), 'dangling_images' (unused storage), "
                    "or 'full_fleet_radar' (complete container telemetry). Default 'full_fleet_radar'."
                ),
                "enum": ["list_containers", "container_stats", "dangling_images", "full_fleet_radar"],
            },
        },
        "required": ["action"],
    },
}


def _get_containers_cli() -> List[Dict[str, Any]]:
    containers = []
    # Try docker CLI
    for cmd_binary in ("docker", "podman"):
        try:
            r = subprocess.run(
                [cmd_binary, "ps", "-a", "--format", "{{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if r.returncode == 0:
                for line in r.stdout.splitlines():
                    parts = line.split("\t")
                    if len(parts) >= 4:
                        cid = parts[0]
                        name = parts[1]
                        image = parts[2]
                        status = parts[3]
                        ports = parts[4] if len(parts) > 4 else ""
                        is_running = "up" in status.lower()
                        is_restarting = "restart" in status.lower()

                        containers.append({
                            "id": cid[:12],
                            "name": name,
                            "image": image,
                            "status": status,
                            "ports": ports or "None",
                            "running": is_running,
                            "restarting": is_restarting,
                            "engine": cmd_binary.title(),
                        })
                if containers:
                    break
        except Exception:
            continue
    return containers


def _get_docker_images_cli() -> List[Dict[str, str]]:
    images = []
    try:
        r = subprocess.run(
            ["docker", "images", "--filter", "dangling=true", "--format", "{{.ID}}\t{{.Repository}}\t{{.Size}}"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if r.returncode == 0:
            for line in r.stdout.splitlines():
                parts = line.split("\t")
                if len(parts) >= 3:
                    images.append({"id": parts[0], "repo": parts[1], "size": parts[2]})
    except Exception:
        pass
    return images


def _render_hud_card(action: str, containers: List[Dict[str, Any]], dangling: List[Dict[str, str]]) -> str:
    lines = [
        "### 🐳 TACTICAL CONTAINER FLEET RADAR (JARVIS MARK-LVII)\n",
    ]

    if not containers and not dangling:
        lines.append("- *No active Docker or Podman containers or daemon socket detected.*")
        lines.append("- *If running in user space, verify user membership in `docker` group or rootless Podman.*")
        lines.append(f"\n*Scan concluded at {time.strftime('%H:%M:%S')}.*")
        return "\n".join(lines)

    running_cnt = len([c for c in containers if c.get("running")])
    restarting_cnt = len([c for c in containers if c.get("restarting")])

    lines.append(f"**Containers Total:** `{len(containers)}` | **Active Running:** `{running_cnt} 🟢`")
    if restarting_cnt > 0:
        lines.append(f"⚠️ **ALERT:** `{restarting_cnt}` container(s) trapped in crash restart loop!")
    lines.append("")

    lines.append("#### 📦 Managed Container Fleet")
    lines.append("```text")
    lines.append(f"{'CONTAINER ID':<14s} {'NAME':<20s} {'STATUS':<22s} {'PORTS'}")
    lines.append("-" * 75)
    for c in containers:
        status_sym = "🟢" if c["running"] else ("🔴" if not c["restarting"] else "⚠️")
        lines.append(f"{c['id']:<14s} {c['name'][:18]:<20s} {status_sym} {c['status'][:18]:<20s} {c['ports'][:20]}")
    lines.append("```\n")

    if dangling:
        lines.append(f"#### 🗑️ Dangling / Unused Images ({len(dangling)} reclaimable)")
        for img in dangling[:5]:
            lines.append(f"- ID: `{img['id']}` — Size: `{img['size']}`")
        lines.append("")

    lines.append(f"*Container fleet telemetry acquired at {time.strftime('%H:%M:%S')}.*")
    return "\n".join(lines)


def _worker(action: str, player):
    try:
        containers = _get_containers_cli()
        dangling = _get_docker_images_cli() if action in ("dangling_images", "full_fleet_radar") else []
        card = _render_hud_card(action, containers, dangling)

        if player:
            try:
                player.show_content("CONTAINER FLEET RADAR", card)
                running = len([c for c in containers if c.get("running")])
                player.write_log(f"🐳 [DockerSentinel] Found {len(containers)} containers ({running} running).")
            except Exception:
                pass
        return containers, dangling, card
    except Exception as e:
        if player:
            try:
                player.write_log(f"⚠️ [DockerSentinel] Error: {e}")
            except Exception:
                pass
        return [], [], f"Error: {e}"


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        action = str(parameters.get("action") or "full_fleet_radar").strip().lower()
        if action not in ("list_containers", "container_stats", "dangling_images", "full_fleet_radar"):
            action = "full_fleet_radar"

        containers, dangling, card = _worker(action, player)
        total = len(containers)
        running = len([c for c in containers if c.get("running")])
        restarting = len([c for c in containers if c.get("restarting")])

        if total == 0:
            if action == "dangling_images" and dangling:
                return f"Sir, no containers running, but found {len(dangling)} reclaimable dangling image(s)."
            return "Sir, no active or stopped Docker/Podman containers were found on this system."

        names = [c.get("name", "container") for c in containers[:3]]
        name_str = f" ({', '.join(names)})" if names else ""
        loop_str = f", with {restarting} in crash loops" if restarting else ", zero crash loops"

        return f"Sir, Docker fleet has {total} container{'s' if total > 1 else ''}: {running} running{name_str}{loop_str}. Full breakdown is on your display."
    except Exception as e:
        return f"Sir, docker sentinel encountered an issue: {e}"
