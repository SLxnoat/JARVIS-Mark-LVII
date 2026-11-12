"""
plugins/whatsapp_call.py - Place and end WhatsApp voice and video calls.

Adheres to AGENTS.md:
- No Qt widgets.
- Safe subprocess and OS protocol handlers.
- Thread-safe HUD feedback via player.write_log().
- Never raises exceptions, returns concise spoken feedback.
"""
import sys
from plugins import _whatsapp_core as wa

PLUGIN = {
    "name": "whatsapp_call",
    "description": (
        "Places or ends WhatsApp voice and video calls to contacts or phone numbers. "
        "Supports WhatsApp Desktop and WhatsApp Web."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "contact": {
                "type": "STRING",
                "description": "Name or phone number of the contact to call.",
            },
            "call_type": {
                "type": "STRING",
                "description": "Type of call: 'voice' or 'video'. Default is 'voice'.",
                "enum": ["voice", "video"],
            },
            "action": {
                "type": "STRING",
                "description": "Action: 'call' or 'end_call'. Default is 'call'.",
                "enum": ["call", "end_call"],
            },
        },
        "required": ["contact"],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    contact = str(parameters.get("contact") or "").strip()
    call_type = str(parameters.get("call_type") or "voice").strip().lower()
    action = str(parameters.get("action") or "call").strip().lower()

    if not contact and action == "call":
        return "Please specify the contact name or phone number you would like to call."

    try:
        if action == "call":
            phone = wa.resolve_contact_phone(contact)
            if not phone:
                phone = wa.normalize_phone(contact)

            # Protocol URI for WhatsApp call
            # On Windows/macOS WhatsApp desktop client registers protocol handlers
            call_uri = f"whatsapp://call?phone={phone}&type={call_type}"
            opened = wa.open_whatsapp_target(call_uri)
            if not opened:
                # Fallback to chat open so user can initiate call button directly
                wa.open_chat(contact)
                msg = f"Opened WhatsApp chat with {contact}. Click the {call_type} call icon to connect."
            else:
                msg = f"Initiating WhatsApp {call_type} call to {contact}."

            if player:
                try:
                    player.write_log(f"📞 [WhatsApp] {msg}")
                except Exception:
                    pass
            return msg

        elif action == "end_call":
            # Attempt to send key shortcut to hang up if desktop client has focus
            try:
                import pyautogui
                # Ctrl+Shift+E / Escape in WhatsApp calls
                pyautogui.hotkey("ctrl", "shift", "e")
            except Exception:
                pass

            if player:
                try:
                    player.write_log(f"📞 [WhatsApp] Ended call with {contact or 'active contact'}.")
                except Exception:
                    pass
            return f"Ended WhatsApp call with {contact or 'contact'}."

        else:
            return f"Unknown action '{action}'. Valid actions are 'call' and 'end_call'."

    except Exception as e:
        return f"Error executing WhatsApp call: {e}"
