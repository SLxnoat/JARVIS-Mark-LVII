"""
plugins/whatsapp_guard.py - WhatsApp incoming call screener and auto-reply guard.

Adheres to AGENTS.md:
- Thread-safe configuration in memory/whatsapp_guard.json.
- Thread-safe HUD feedback via player.write_log().
- Never raises exceptions, returns concise spoken feedback.
"""
import json
from pathlib import Path
from plugins import _whatsapp_core as wa

PLUGIN = {
    "name": "whatsapp_guard",
    "description": (
        "Screens incoming WhatsApp calls and manages auto-reply rules. "
        "Allows toggling modes (accept_all, whitelist_only, do_not_disturb) and sending automated responses."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: 'status', 'set_mode', 'whitelist_add', 'whitelist_remove', 'auto_reply'.",
                "enum": ["status", "set_mode", "whitelist_add", "whitelist_remove", "auto_reply"],
            },
            "mode": {
                "type": "STRING",
                "description": "Guard mode: 'accept_all', 'whitelist_only', 'do_not_disturb'. Required for 'set_mode'.",
                "enum": ["accept_all", "whitelist_only", "do_not_disturb"],
            },
            "contact": {
                "type": "STRING",
                "description": "Contact name or phone number for whitelist or auto-reply.",
            },
            "message": {
                "type": "STRING",
                "description": "Custom auto-reply message text.",
            },
        },
        "required": ["action"],
    },
}

_STORAGE_PATH = Path("memory") / "whatsapp_guard.json"


def _load_guard() -> dict:
    if _STORAGE_PATH.is_file():
        try:
            with open(_STORAGE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "mode": "accept_all",
        "whitelist": [],
        "default_reply": "I am currently unavailable and will get back to you shortly.",
    }


def _save_guard(data: dict):
    _STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = _STORAGE_PATH.with_suffix(".tmp")
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    temp.replace(_STORAGE_PATH)


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = parameters.get("action", "status").strip().lower()
    mode = str(parameters.get("mode") or "").strip().lower()
    contact = str(parameters.get("contact") or "").strip()
    msg = str(parameters.get("message") or "").strip()

    try:
        data = _load_guard()

        if action == "status":
            wl = ", ".join(data.get("whitelist", [])) or "None"
            return f"WhatsApp Guard is in '{data.get('mode')}' mode. Whitelist: {wl}."

        elif action == "set_mode":
            if mode not in ("accept_all", "whitelist_only", "do_not_disturb"):
                return "Invalid mode. Valid options: accept_all, whitelist_only, do_not_disturb."
            data["mode"] = mode
            _save_guard(data)
            if player:
                try:
                    player.write_log(f"🛡️ [WhatsAppGuard] Mode updated to {mode}.")
                except Exception:
                    pass
            return f"WhatsApp Guard mode updated to '{mode}'."

        elif action == "whitelist_add":
            if not contact:
                return "Please provide a contact to add to the whitelist."
            if contact not in data["whitelist"]:
                data["whitelist"].append(contact)
                _save_guard(data)
            return f"Added '{contact}' to WhatsApp whitelist."

        elif action == "whitelist_remove":
            if not contact:
                return "Please provide a contact to remove from the whitelist."
            if contact in data["whitelist"]:
                data["whitelist"].remove(contact)
                _save_guard(data)
                return f"Removed '{contact}' from WhatsApp whitelist."
            return f"'{contact}' was not in the whitelist."

        elif action == "auto_reply":
            if not contact:
                return "Please specify the contact to send an auto-reply to."
            reply_text = msg or data.get("default_reply")
            wa.open_chat(contact, reply_text)
            return f"Sent auto-reply to {contact}: \"{reply_text}\"."

        else:
            return f"Unknown action '{action}'. Valid actions: status, set_mode, whitelist_add, whitelist_remove, auto_reply."

    except Exception as e:
        return f"Error in WhatsApp Guard: {e}"
