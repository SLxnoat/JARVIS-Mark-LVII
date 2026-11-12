"""
plugins/pomodoro.py - Pomodoro focus timer with interval tracking.

Adheres strictly to AGENTS.md:
- No Qt widgets instantiated on worker threads.
- Thread-safe notifications via player.write_log().
- Fast returns; never raises exceptions.
"""
import time
import threading

PLUGIN = {
    "name": "pomodoro",
    "description": (
        "Controls a Pomodoro focus timer. Supports starting a 25-minute focus session, "
        "short/long breaks, pausing, resuming, stopping, and querying current status."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action to perform: 'start', 'pause', 'resume', 'stop', 'status', 'break'.",
                "enum": ["start", "pause", "resume", "stop", "status", "break"],
            },
            "duration_minutes": {
                "type": "INTEGER",
                "description": "Optional custom duration in minutes (defaults to 25 for focus, 5 for break).",
            },
        },
        "required": ["action"],
    },
}

# Module-level state protected by a lock
_lock = threading.Lock()
_state = "IDLE"  # IDLE, RUNNING, PAUSED
_mode = "FOCUS"  # FOCUS, BREAK
_end_time = 0.0
_remaining = 0.0
_completed_sessions = 0
_timer_thread = None
_stop_event = threading.Event()


def _timer_worker(target_end: float, mode_name: str, player):
    while not _stop_event.is_set():
        remaining = target_end - time.time()
        if remaining <= 0:
            break
        _stop_event.wait(min(remaining, 1.0))

    if not _stop_event.is_set():
        with _lock:
            global _state, _completed_sessions
            _state = "IDLE"
            if mode_name == "FOCUS":
                _completed_sessions += 1
                msg = f"Pomodoro completed! You have finished {_completed_sessions} session(s) today. Time for a break!"
            else:
                msg = "Break is over! Ready to start the next Pomodoro session."

        if player:
            try:
                player.write_log(f"⏰ [Pomodoro] {msg}")
            except Exception:
                pass


def run(parameters: dict, player=None, session_memory=None) -> str:
    global _state, _mode, _end_time, _remaining, _completed_sessions, _timer_thread, _stop_event

    action = parameters.get("action", "status").strip().lower()
    custom_minutes = parameters.get("duration_minutes")

    try:
        with _lock:
            now = time.time()

            if action == "start":
                duration_min = custom_minutes if (custom_minutes and custom_minutes > 0) else 25
                _stop_event.set()
                _stop_event = threading.Event()
                _state = "RUNNING"
                _mode = "FOCUS"
                _end_time = now + (duration_min * 60)
                _remaining = duration_min * 60

                _timer_thread = threading.Thread(
                    target=_timer_worker,
                    args=(_end_time, "FOCUS", player),
                    daemon=True,
                )
                _timer_thread.start()

                if player:
                    try:
                        player.write_log(f"⏰ [Pomodoro] Started {duration_min}-minute focus session.")
                    except Exception:
                        pass
                return f"Started a {duration_min}-minute Pomodoro focus session. Stay focused!"

            elif action == "break":
                duration_min = custom_minutes if (custom_minutes and custom_minutes > 0) else 5
                _stop_event.set()
                _stop_event = threading.Event()
                _state = "RUNNING"
                _mode = "BREAK"
                _end_time = now + (duration_min * 60)
                _remaining = duration_min * 60

                _timer_thread = threading.Thread(
                    target=_timer_worker,
                    args=(_end_time, "BREAK", player),
                    daemon=True,
                )
                _timer_thread.start()

                if player:
                    try:
                        player.write_log(f"☕ [Pomodoro] Started {duration_min}-minute break.")
                    except Exception:
                        pass
                return f"Started a {duration_min}-minute break. Relax and step away from the screen."

            elif action == "pause":
                if _state != "RUNNING":
                    return f"No active timer to pause (currently {_state.lower()})."
                _remaining = max(0.0, _end_time - now)
                _stop_event.set()
                _state = "PAUSED"
                mins_left = int(_remaining // 60)
                secs_left = int(_remaining % 60)
                return f"Pomodoro paused with {mins_left}m {secs_left}s remaining."

            elif action == "resume":
                if _state != "PAUSED":
                    return f"Cannot resume because timer is {_state.lower()}."
                _stop_event = threading.Event()
                _state = "RUNNING"
                _end_time = now + _remaining
                _timer_thread = threading.Thread(
                    target=_timer_worker,
                    args=(_end_time, _mode, player),
                    daemon=True,
                )
                _timer_thread.start()
                mins_left = int(_remaining // 60)
                return f"Resumed {_mode.lower()} session with {mins_left} minutes remaining."

            elif action == "stop":
                if _state == "IDLE":
                    return "Pomodoro timer is already idle."
                _stop_event.set()
                _state = "IDLE"
                return "Pomodoro timer stopped."

            elif action == "status":
                if _state == "RUNNING":
                    secs = max(0.0, _end_time - now)
                    mins = int(secs // 60)
                    return f"Pomodoro is currently in {_mode.lower()} mode with {mins} minutes remaining ({_completed_sessions} completed today)."
                elif _state == "PAUSED":
                    mins = int(_remaining // 60)
                    return f"Pomodoro is paused with {mins} minutes remaining in {_mode.lower()} mode."
                else:
                    return f"Pomodoro timer is idle. {_completed_sessions} session(s) completed today."

            else:
                return f"Unknown action '{action}'. Valid actions are start, pause, resume, stop, break, or status."

    except Exception as e:
        return f"Error controlling Pomodoro: {e}"
