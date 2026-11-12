"""
plugins/telegram_remote.py - Telegram remote companion management and status interface.

Adheres to AGENTS.md:
- Interacts with plugins.telegram_bridge and config/telegram_paired.json.
- Thread-safe HUD presentation via player.show_content().
- Never raises exceptions, returns concise spoken feedback.
"""
import json
from pathlib import Path
from plugins import telegram_bridge

PLUGIN = {
    "name": "telegram_remote",
    "description": (
        "Checks pairing status and manages remote control over Telegram. "
        "Allows generating pairing QR codes, revoking pairings, and checking connection status."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: 'status', 'pair', 'unpair', 'send_message'.",
                "enum": ["status", "pair", "unpair", "send_message"],
            },
            "message": {
                "type": "STRING",
                "description": "Message to send to the paired Telegram user.",
            },
        },
        "required": ["action"],
    },
}

_PAIRED_FILE = Path("config") / "telegram_paired.json"


def _get_paired_info() -> dict | None:
    if _PAIRED_FILE.is_file():
        try:
            with open(_PAIRED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data and data.get("chat_id"):
                return data
        except Exception:
            pass
    return None


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = parameters.get("action", "status").strip().lower()
    msg = str(parameters.get("message") or "").strip()

    try:
        paired = _get_paired_info()

        if action == "status":
            if paired:
                user_label = f"@{paired.get('username')}" if paired.get("username") else f"ID {paired.get('chat_id')}"
                return f"Telegram Remote is active and securely paired with {user_label}."
            return "Telegram Remote is active, but no phone is currently paired. Pair using the QR code on screen."

        elif action == "pair":
            bridge = getattr(telegram_bridge, "_bridge_instance", None)
            if bridge:
                bridge._trigger_qr_pairing()
                return "Generated new Telegram pairing QR code on the display."
            return "Telegram Bridge is initializing. Scan the QR code displayed on startup."

        elif action == "unpair":
            if _PAIRED_FILE.is_file():
                _PAIRED_FILE.unlink(missing_ok=True)
            bridge = getattr(telegram_bridge, "_bridge_instance", None)
            if bridge:
                bridge._clear_paired()
                bridge._trigger_qr_pairing()
            return "Disconnected paired Telegram device. A fresh pairing QR code has been generated."

        elif action == "send_message":
            if not msg:
                return "Please provide a message text to send to Telegram."
            if not paired:
                return "No paired Telegram device to send to. Scan the pairing QR code first."
            return telegram_bridge.run({"message": msg}, player=player, session_memory=session_memory)

        else:
            return f"Unknown action '{action}'. Valid actions: status, pair, unpair, send_message."

    except Exception as e:
        return f"Error managing Telegram Remote: {e}"
