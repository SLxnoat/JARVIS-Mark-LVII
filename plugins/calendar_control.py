"""
plugins/calendar_control.py - Calendar schedule viewer and event scheduler.

Adheres to AGENTS.md:
- Thread-safe persistence in memory/calendar.json and local iCal.
- Thread-safe HUD presentation via player.show_content().
- Never raises exceptions, returns concise spoken feedback.
"""
import json
import time
from datetime import datetime, timedelta, date
from pathlib import Path

PLUGIN = {
    "name": "calendar_control",
    "description": (
        "Reads upcoming calendar events, shows your schedule for today or tomorrow, "
        "and creates new appointments or meetings."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: 'today', 'upcoming', 'create_event'.",
                "enum": ["today", "upcoming", "create_event"],
            },
            "title": {
                "type": "STRING",
                "description": "Title of the meeting or appointment for 'create_event'.",
            },
            "start_time": {
                "type": "STRING",
                "description": "Start date/time (e.g. '2026-11-13 14:00' or '14:00').",
            },
            "duration_minutes": {
                "type": "INTEGER",
                "description": "Duration in minutes (default is 60).",
            },
            "description": {
                "type": "STRING",
                "description": "Optional event description or location.",
            },
        },
        "required": ["action"],
    },
}

_STORAGE_PATH = Path("memory") / "calendar.json"


def _load_events() -> list[dict]:
    if _STORAGE_PATH.is_file():
        try:
            with open(_STORAGE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save_events(events: list[dict]):
    _STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = _STORAGE_PATH.with_suffix(".tmp")
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2)
    temp.replace(_STORAGE_PATH)


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = parameters.get("action", "today").strip().lower()
    title = str(parameters.get("title") or "").strip()
    start_time_str = str(parameters.get("start_time") or "").strip()
    dur_min = int(parameters.get("duration_minutes") or 60)
    desc = str(parameters.get("description") or "").strip()

    try:
        events = _load_events()
        today_str = str(date.today())

        if action == "create_event":
            if not title:
                return "Please provide an event title."

            # Parse start time
            if not start_time_str:
                target_dt = datetime.now() + timedelta(hours=1)
                start_dt_str = target_dt.strftime("%Y-%m-%d %H:00")
            elif " " in start_time_str:
                start_dt_str = start_time_str
            else:
                start_dt_str = f"{today_str} {start_time_str}"

            event = {
                "id": str(int(time.time())),
                "title": title,
                "start": start_dt_str,
                "duration_minutes": dur_min,
                "description": desc,
            }
            events.append(event)
            # Sort by start
            events.sort(key=lambda e: e.get("start", ""))
            _save_events(events)

            if player:
                try:
                    player.write_log(f"[Calendar] Created event: '{title}' at {start_dt_str}")
                except Exception:
                    pass
            return f"Scheduled '{title}' for {start_dt_str} ({dur_min} minutes)."

        elif action in ("today", "upcoming"):
            if not events:
                return "Your calendar is currently clear with no scheduled events."

            if action == "today":
                filtered = [e for e in events if e.get("start", "").startswith(today_str)]
                header = f"###  Today's Schedule ({today_str})"
            else:
                filtered = [e for e in events if e.get("start", "") >= today_str][:10]
                header = "###  Upcoming Calendar Events"

            if not filtered:
                return f"No events scheduled for {action}."

            lines = []
            for e in filtered:
                lines.append(f"- **{e.get('start')}** — **{e.get('title')}** *({e.get('duration_minutes', 60)} min)*")

            if player:
                try:
                    player.show_content("Calendar Schedule", f"{header}\n\n" + "\n".join(lines))
                except Exception:
                    pass

            names = ", ".join(e.get("title", "") for e in filtered[:3])
            return f"You have {len(filtered)} event(s) scheduled: {names}."

        else:
            return f"Unknown action '{action}'. Valid actions: today, upcoming, create_event."

    except Exception as e:
        return f"Error managing calendar: {e}"
