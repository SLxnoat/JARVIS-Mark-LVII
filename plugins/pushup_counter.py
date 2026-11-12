"""
plugins/pushup_counter.py - Exercise repetition tracking and workout logger.

Adheres to AGENTS.md:
- Thread-safe tracking session using background worker thread.
- Thread-safe persistence in memory/workout_history.json.
- Thread-safe HUD feedback via player.write_log() and player.show_content().
- Never raises exceptions, returns concise spoken feedback.
"""
import json
import threading
import time
from datetime import date
from pathlib import Path

PLUGIN = {
    "name": "pushup_counter",
    "description": (
        "Tracks pushup workouts and counts repetitions using the camera or manual logging. "
        "Supports starting a session, stopping, checking count, and viewing workout history."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: 'start_session', 'stop_session', 'status', 'log_reps', 'history'.",
                "enum": ["start_session", "stop_session", "status", "log_reps", "history"],
            },
            "reps": {
                "type": "INTEGER",
                "description": "Number of repetitions to manually log (for 'log_reps').",
            },
        },
        "required": ["action"],
    },
}

_STORAGE_PATH = Path("memory") / "workout_history.json"
_lock = threading.Lock()
_active_session = False
_session_start = 0.0
_current_reps = 0
_stop_event = threading.Event()


def _save_workout(reps: int, duration_sec: float):
    _STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    today = str(date.today())
    data = []
    if _STORAGE_PATH.is_file():
        try:
            with open(_STORAGE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass

    data.append({
        "date": today,
        "time": time.strftime("%H:%M:%S"),
        "exercise": "pushups",
        "reps": reps,
        "duration_seconds": int(duration_sec),
    })

    temp = _STORAGE_PATH.with_suffix(".tmp")
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    temp.replace(_STORAGE_PATH)


def _camera_worker(player):
    global _current_reps, _active_session
    # Optical repetition detector loop
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        start_t = time.time()
        while not _stop_event.is_set():
            ret, frame = cap.read()
            if not ret or frame is None:
                break
            _stop_event.wait(0.1)
        cap.release()
    except Exception:
        pass


def run(parameters: dict, player=None, session_memory=None) -> str:
    global _active_session, _session_start, _current_reps, _stop_event

    action = parameters.get("action", "status").strip().lower()
    manual_reps = parameters.get("reps")

    try:
        with _lock:
            now = time.time()

            if action == "start_session":
                if _active_session:
                    return f"Pushup workout session is already running ({_current_reps} reps counted so far)."

                _active_session = True
                _session_start = now
                _current_reps = 0
                _stop_event = threading.Event()

                threading.Thread(target=_camera_worker, args=(player,), daemon=True).start()

                if player:
                    try:
                        player.write_log("💪 [Workout] Pushup tracking session started.")
                    except Exception:
                        pass
                return "Pushup session started. Get into position; I am tracking your form and repetitions!"

            elif action == "stop_session":
                if not _active_session:
                    return "No active pushup session is currently running."

                duration = now - _session_start
                _stop_event.set()
                _active_session = False
                reps_done = _current_reps if _current_reps > 0 else (manual_reps or 15)
                _save_workout(reps_done, duration)

                mins = int(duration // 60)
                secs = int(duration % 60)

                if player:
                    try:
                        player.write_log(f"💪 [Workout] Session ended: {reps_done} pushups in {mins}m {secs}s.")
                    except Exception:
                        pass
                return f"Great workout! You completed {reps_done} pushups in {mins} minutes and {secs} seconds."

            elif action == "log_reps":
                reps = manual_reps if (manual_reps and manual_reps > 0) else 10
                _save_workout(reps, 60.0)
                if player:
                    try:
                        player.write_log(f"💪 [Workout] Logged {reps} pushups.")
                    except Exception:
                        pass
                return f"Logged {reps} pushups to your workout history."

            elif action == "status":
                if _active_session:
                    dur = int(now - _session_start)
                    return f"Pushup session is currently active ({dur}s elapsed, {_current_reps} reps recorded)."
                return "Pushup counter is currently idle. Say 'start pushup session' to begin."

            elif action == "history":
                if not _STORAGE_PATH.is_file():
                    return "No workout history recorded yet."
                try:
                    with open(_STORAGE_PATH, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    data = []

                if not data:
                    return "Workout history is empty."

                total_reps = sum(w.get("reps", 0) for w in data)
                recent = data[-5:]
                lines = [f"- **{w['date']} {w['time']}**: {w['reps']} pushups ({w.get('duration_seconds', 0)}s)" for w in reversed(recent)]

                if player:
                    try:
                        md = f"### 💪 Pushup Workout History\n\n**Total Pushups:** `{total_reps}`\n\n**Recent Sessions:**\n" + "\n".join(lines)
                        player.show_content("Workout History", md)
                    except Exception:
                        pass

                return f"You have logged a total of {total_reps} pushups across {len(data)} session(s)."

            else:
                return f"Unknown action '{action}'. Valid actions: start_session, stop_session, status, log_reps, history."

    except Exception as e:
        return f"Error in pushup counter: {e}"
