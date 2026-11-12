"""
plugins/_whatsapp_core.py - Shared cross-platform WhatsApp driver (Desktop & Web).

Prefixed with an underscore so plugin_loader skips it as a standalone plugin.
Shared by plugins/whatsapp_call.py, plugins/whatsapp_guard.py, etc.

Adheres to AGENTS.md:
- No Qt widgets.
- Safe subprocess calls with timeouts.
- Cross-platform support for Linux, macOS, and Windows.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path

_CONTACTS_PATH = Path("memory") / "contacts.json"


def normalize_phone(phone: str) -> str:
    """Strip all non-digit characters except leading plus."""
    phone = phone.strip()
    digits = re.sub(r"[^\d+]", "", phone)
    if digits.startswith("+"):
        return digits[1:]
    return digits


def resolve_contact_phone(query: str) -> str | None:
    """Check memory/contacts.json or clean digits."""
    clean_digits = normalize_phone(query)
    if clean_digits.isdigit() and len(clean_digits) >= 7:
        return clean_digits

    if _CONTACTS_PATH.is_file():
        try:
            with open(_CONTACTS_PATH, "r", encoding="utf-8") as f:
                contacts = json.load(f)
            q_lower = query.lower()
            for name, phone in contacts.items():
                if q_lower in name.lower():
                    return normalize_phone(phone)
        except Exception:
            pass
    return None


def is_whatsapp_running() -> bool:
    """Check if WhatsApp desktop client process is running."""
    try:
        import psutil
        for proc in psutil.process_iter(["name"]):
            name = (proc.info.get("name") or "").lower()
            if "whatsapp" in name:
                return True
    except Exception:
        pass
    return False


def open_whatsapp_target(uri_or_url: str) -> bool:
    """Open desktop protocol URI or web URL via OS default handler."""
    try:
        if sys.platform == "win32":
            os.startfile(uri_or_url)
            return True
        elif sys.platform == "darwin":
            subprocess.run(["open", uri_or_url], check=True, timeout=5)
            return True
        else:
            # Linux xdg-open
            subprocess.run(["xdg-open", uri_or_url], check=True, timeout=5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
    except Exception:
        return False


def open_chat(phone_or_contact: str, message: str = "") -> tuple[bool, str]:
    """Launch WhatsApp conversation with contact or phone."""
    phone = resolve_contact_phone(phone_or_contact)
    encoded_msg = urllib.parse.quote(message) if message else ""

    if phone:
        # Try native app URI first
        app_uri = f"whatsapp://send?phone={phone}"
        if encoded_msg:
            app_uri += f"&text={encoded_msg}"

        if open_whatsapp_target(app_uri):
            return True, f"Opened WhatsApp chat with {phone_or_contact}."

        # Fallback to web URL
        web_url = f"https://web.whatsapp.com/send?phone={phone}"
        if encoded_msg:
            web_url += f"&text={encoded_msg}"
        if open_whatsapp_target(web_url):
            return True, f"Opened WhatsApp Web chat with {phone_or_contact} in browser."

    # If contact not found as phone, open general app
    if open_whatsapp_target("whatsapp://"):
        return True, "Opened WhatsApp desktop application."
    open_whatsapp_target("https://web.whatsapp.com")
    return True, "Opened WhatsApp Web in your browser."
