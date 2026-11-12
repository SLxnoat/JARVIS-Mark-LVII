"""
plugins/smart_reminder_snoozer.py - In-Session Countdown Timer & Snooze Engine.

Manages short-term countdown timers, reminders, and alerts with natural duration parsing,
active countdown tracking, HUD display, and snooze capabilities.

Adheres strictly to AGENTS.md:
- Never instantiates Qt widgets on worker threads.
- Thread-safe HUD updates via player.show_content() and player.write_log().
- Fast returns; non-blocking; never raises unhandled exceptions.
- Handles player=None gracefully.
"""
from __future__ import annotations

import re
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

PLUGIN: Dict[str, Any] = {
    "name": "smart_reminder_snoozer",
    "description": (
        "In-session countdown timer and snooze manager. Sets quick voice-activated countdown "
        "timers (seconds, minutes, hours), lists active timers on the HUD, alerts upon completion, "
        "and supports snoozing active or expired timers."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: 'set' (new timer), 'list' (view all active timers), 'cancel' (cancel a timer), 'snooze' (extend timer).",
                "enum": ["set", "list", "cancel", "snooze"],
            },
            "duration": {
                "type": "STRING",
                "description": "Duration string e.g. '10m', '30s', '1h', or '15' (defaults to minutes if unstated).",
            },
            "message": {
                "type": "STRING",
                "description": "Label or reminder description (e.g. 'Check oven', 'Team standup').",
            },
            "timer_id": {
                "type": "STRING",
                "description": "Timer identifier (e.g. 'T1') for 'cancel' or 'snooze'.",
            },
            "snooze_minutes": {
                "type": "INTEGER",
                "description": "Minutes to snooze/extend the timer (default 5).",
            },
        },
        "required": ["action"],
    },
}

_lock = threading.Lock()
_timer_counter = 1
_active_timers: Dict[str, Dict[str, Any]] = {}


def _parse_duration_seconds(duration_str: str | int | float | None) -> int:
    if duration_str is None:
        return 300  # Default 5 minutes

    if isinstance(duration_str, (int, float)):
        return max(1, int(duration_str * 60))

    s = str(duration_str).strip().lower()
    if not s:
        return 300

    # Match format like '1h30m', '10m', '45s', '2h'
    total_seconds = 0
    matches = re.findall(r"(\d+(?:\.\d+)?)\s*([smh]?)", s)
    found_any = False

    for val_str, unit in matches:
        if not val_str:
            continue
        val = float(val_str)
        found_any = True
        if unit == "s":
            total_seconds += int(val)
        elif unit == "h":
            total_seconds += int(val * 3600)
        else:  # 'm' or no unit default to minutes
            total_seconds += int(val * 60)

    if not found_any or total_seconds <= 0:
        try:
            return max(1, int(float(s) * 60))
        except ValueError:
            return 300

    return max(1, total_seconds)


def _format_time_left(seconds_left: float) -> str:
    if seconds_left <= 0:
        return "Expired"
    mins, secs = divmod(int(seconds_left), 60)
    hours, mins = divmod(mins, 60)
    if hours > 0:
        return f"{hours}h {mins:02d}m {secs:02d}s"
    return f"{mins}m {secs:02d}s"


def _fire_timer(t_id: str, message: str, player=None):
    with _lock:
        if t_id not in _active_timers:
            return
        timer_info = _active_timers[t_id]
        if timer_info["status"] != "running":
            return
        timer_info["status"] = "expired"

    alert_text = f"⏰ TIMER COMPLETE [{t_id}]: {message}"
    if player:
        try:
            player.write_log(alert_text)
            if hasattr(player, "request_say") and callable(player.request_say):
                player.request_say(f"Sir, your timer for '{message}' has finished.")
        except Exception:
            pass


def run(parameters: dict | None = None, player=None, session_memory=None) -> str:
    global _timer_counter
    try:
        params = parameters or {}
        action = params.get("action", "set")
        duration_arg = params.get("duration", "5m")
        label = params.get("message") or "Timer Alert"
        target_id = params.get("timer_id", "").strip().upper()
        snooze_mins = params.get("snooze_minutes", 5)

        with _lock:
            if action == "set":
                secs = _parse_duration_seconds(duration_arg)
                t_id = f"T{_timer_counter}"
                _timer_counter += 1

                end_time = time.time() + secs
                t_obj = threading.Timer(secs, _fire_timer, args=[t_id, label, player])
                t_obj.daemon = True
                t_obj.start()

                _active_timers[t_id] = {
                    "id": t_id,
                    "label": label,
                    "duration_sec": secs,
                    "end_time": end_time,
                    "status": "running",
                    "thread": t_obj,
                    "created_at": datetime.now().strftime("%H:%M:%S"),
                }

                dur_disp = _format_time_left(secs)
                if player:
                    player.write_log(f"Timer {t_id} set for {dur_disp}: {label}")
                    _show_hud_timers(player)
                return f"Timer {t_id} set for {dur_disp}: {label}, sir."

            elif action == "cancel":
                if not target_id:
                    # Cancel latest running timer if not specified
                    running = [tid for tid, d in _active_timers.items() if d["status"] == "running"]
                    if not running:
                        return "There are no active timers to cancel, sir."
                    target_id = running[-1]

                if target_id not in _active_timers:
                    return f"Timer {target_id} not found, sir."

                info = _active_timers[target_id]
                if info["status"] == "running":
                    try:
                        info["thread"].cancel()
                    except Exception:
                        pass
                    info["status"] = "canceled"
                    if player:
                        player.write_log(f"Timer {target_id} canceled: {info['label']}")
                        _show_hud_timers(player)
                    return f"Timer {target_id} ({info['label']}) has been canceled, sir."
                return f"Timer {target_id} is already {info['status']}, sir."

            elif action == "snooze":
                if not target_id:
                    # Snooze latest expired or running timer
                    candidates = [tid for tid, d in _active_timers.items() if d["status"] in ("expired", "running")]
                    if not candidates:
                        return "There are no timers to snooze, sir."
                    target_id = candidates[-1]

                if target_id not in _active_timers:
                    return f"Timer {target_id} not found, sir."

                info = _active_timers[target_id]
                # Cancel existing thread if running
                if info["status"] == "running":
                    try:
                        info["thread"].cancel()
                    except Exception:
                        pass

                secs = snooze_mins * 60
                end_time = time.time() + secs
                t_obj = threading.Timer(secs, _fire_timer, args=[target_id, info["label"], player])
                t_obj.daemon = True
                t_obj.start()

                info["thread"] = t_obj
                info["end_time"] = end_time
                info["status"] = "running"

                dur_disp = f"{snooze_mins} minutes"
                if player:
                    player.write_log(f"Timer {target_id} snoozed for {dur_disp}")
                    _show_hud_timers(player)
                return f"Timer {target_id} ({info['label']}) snoozed for {dur_disp}, sir."

            elif action == "list":
                _show_hud_timers(player)
                running_count = sum(1 for d in _active_timers.values() if d["status"] == "running")
                return f"You have {running_count} active countdown timer(s) on the board, sir."

            return "Unrecognized timer action, sir."

    except Exception as e:
        err = f"Timer error: {e}"
        if player:
            player.write_log(err)
        return f"Sir, I encountered an error managing the timer: {e}"


def _show_hud_timers(player=None):
    if not player:
        return
    try:
        now = time.time()
        rows = []
        for tid, t in sorted(_active_timers.items(), key=lambda x: x[1]["end_time"]):
            remaining = t["end_time"] - now
            status_badge = (
                f"🟢 `{_format_time_left(remaining)}`" if t["status"] == "running"
                else ("🔴 EXPIRED" if t["status"] == "expired" else "⚪ CANCELED")
            )
            rows.append(f"| **{tid}** | {t['label']} | {status_badge} | {t['created_at']} |")

        md = (
            "## ⏱️ Active Countdown Timers & Alerts\n\n"
            "| ID | Reminder Label | Remaining | Created |\n"
            "|:---|:---|:---|:---|\n"
            + ("\n".join(rows) if rows else "| - | No active timers running | - | - |\n")
            + "\n\n> *Voice controls: 'Jarvis, snooze timer T1' or 'Jarvis, cancel timer T1'*"
        )
        player.show_content("Active Timers", md)
    except Exception:
        pass
