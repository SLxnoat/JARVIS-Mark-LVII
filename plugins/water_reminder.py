"""
plugins/water_reminder.py - Daily hydration tracker and reminder status.

Adheres to AGENTS.md:
- Thread-safe persistence in memory/hydration.json.
- Thread-safe UI updates via player.write_log().
- Never raises exceptions, fast string return.
"""
import json
import time
from datetime import date
from pathlib import Path

PLUGIN = {
    "name": "water_reminder",
    "description": (
        "Logs daily water intake and checks hydration progress towards a daily goal (e.g. 2500 ml). "
        "Allows logging a glass of water, checking status, updating goals, or resetting."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Hydration action: 'log', 'status', 'set_goal', 'reset'.",
                "enum": ["log", "status", "set_goal", "reset"],
            },
            "amount_ml": {
                "type": "INTEGER",
                "description": "Amount in milliliters to log or set as goal (e.g. 250 for a glass, 500 for a bottle).",
            },
        },
        "required": ["action"],
    },
}

_STORAGE_PATH = Path("memory") / "hydration.json"
_DEFAULT_GOAL = 2500


def _load_data() -> dict:
    today_str = str(date.today())
    if _STORAGE_PATH.is_file():
        try:
            with open(_STORAGE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("date") == today_str:
                return data
        except Exception:
            pass

    # Fresh day default
    return {
        "date": today_str,
        "consumed_ml": 0,
        "goal_ml": _DEFAULT_GOAL,
        "entries": [],
    }


def _save_data(data: dict) -> None:
    _STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = _STORAGE_PATH.with_suffix(".tmp")
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    temp.replace(_STORAGE_PATH)


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = parameters.get("action", "status").strip().lower()
    amount = parameters.get("amount_ml")

    try:
        data = _load_data()

        if action == "log":
            ml = amount if (amount and amount > 0) else 250
            data["consumed_ml"] += ml
            data["entries"].append({
                "time": time.strftime("%H:%M:%S"),
                "amount_ml": ml,
            })
            _save_data(data)

            pct = int((data["consumed_ml"] / max(1, data["goal_ml"])) * 100)
            remaining = max(0, data["goal_ml"] - data["consumed_ml"])
            msg = f"Logged {ml} ml of water. Total today: {data['consumed_ml']}/{data['goal_ml']} ml ({pct}% of goal, {remaining} ml remaining)."

            if player:
                try:
                    player.write_log(f"[Hydration] +{ml} ml ({data['consumed_ml']} / {data['goal_ml']} ml)")
                except Exception:
                    pass
            return msg

        elif action == "set_goal":
            if not amount or amount <= 0:
                return "Please specify a positive amount in ml for your new daily goal."
            data["goal_ml"] = amount
            _save_data(data)
            return f"Updated daily hydration goal to {amount} ml."

        elif action == "reset":
            data["consumed_ml"] = 0
            data["entries"] = []
            _save_data(data)
            return "Reset today's water intake to 0 ml."

        elif action == "status":
            pct = int((data["consumed_ml"] / max(1, data["goal_ml"])) * 100)
            remaining = max(0, data["goal_ml"] - data["consumed_ml"])
            if remaining == 0:
                return f"You reached your hydration goal! You have consumed {data['consumed_ml']} ml today ({pct}%)."
            return f"You have drank {data['consumed_ml']} ml of water today ({pct}% of {data['goal_ml']} ml goal). {remaining} ml left to reach your target."

        else:
            return f"Unknown action '{action}'. Valid actions are: log, status, set_goal, reset."

    except Exception as e:
        return f"Error managing hydration: {e}"
