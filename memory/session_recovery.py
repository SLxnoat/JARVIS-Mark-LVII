"""
Session Recovery & Crash Marker Engine for JARVIS (Hermes session_auto_continue pattern).

Records active turn and task markers to allow automatic state recovery and HUD notification
if the application or backend restarts unexpectedly mid-task.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
MARKER_FILE = Path.home() / ".jarvis_session_marker.json"
FRESHNESS_WINDOW_SECS = 15 * 60  # 15 minutes


def write_turn_marker(prompt: str, tool_name: str = "") -> None:
    """Record an active in-flight task or turn."""
    try:
        MARKER_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "prompt": str(prompt or ""),
            "tool_name": str(tool_name or ""),
            "started_at": time.time(),
            "pid": os.getpid(),
            "status": "in_progress",
        }
        MARKER_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def clear_turn_marker() -> None:
    """Drop the crash marker at turn completion."""
    try:
        if MARKER_FILE.exists():
            MARKER_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def check_recovery_marker() -> Optional[dict]:
    """Check if an interrupted turn exists from a prior process crash."""
    try:
        if not MARKER_FILE.exists():
            return None
        data = json.loads(MARKER_FILE.read_text(encoding="utf-8"))
        age = time.time() - float(data.get("started_at", 0))
        # Clear if stale (>15 mins)
        if age > FRESHNESS_WINDOW_SECS or age < 0:
            clear_turn_marker()
            return None
        # Valid recovery marker found: clear file so it only recovers once
        clear_turn_marker()
        return data
    except Exception:
        return None
