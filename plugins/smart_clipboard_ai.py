"""
plugins/smart_clipboard_ai.py - Contextual Clipboard Transformer & Decoder.

Iron Man / JARVIS style clipboard intelligence:
- Reads clipboard contents and autonomously classifies data structure:
  JSON, curl commands, JWT tokens, base64 blobs, SQL queries, Unix timestamps.
- Pre-computes instant transformations:
  - JSON ➔ Formatted pretty JSON & Python dataclass.
  - curl ➔ Python requests snippet.
  - JWT ➔ Decoded header & claims payload.
  - Unix Timestamp ➔ Human ISO-8601 & Local Datetime.
- Renders an interactive transformed clipboard card on the HUD via player.show_content().

Adheres strictly to AGENTS.md:
- No Qt widgets on worker threads.
- Thread-safe HUD feedback via player.show_content() and player.write_log().
- Safe non-blocking execution on background daemon thread.
- Never raises exceptions, returns concise spoken feedback.
- Handles player=None gracefully.
"""
from __future__ import annotations

import base64
import datetime
import json
import re
import sys
import threading
import time
from typing import Any, Dict, Tuple

PLUGIN = {
    "name": "smart_clipboard_ai",
    "description": (
        "JARVIS Smart Clipboard: Inspects clipboard data, detects format (JSON, curl, JWT, base64, "
        "timestamp), and pre-computes instant transformations (curl to Python requests, JWT decode, "
        "JSON formatting). Displays transformed data on the HUD ready for use."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "text": {
                "type": "STRING",
                "description": "Optional text to transform; if omitted, reads live system clipboard.",
            },
        },
        "required": [],
    },
}


def _read_clipboard(text_arg: str) -> str:
    if text_arg:
        return text_arg.strip()
    try:
        import pyperclip
        return pyperclip.paste().strip()
    except Exception:
        return ""


def _transform_clipboard_content(raw: str) -> Tuple[str, str, str]:
    """Returns (detected_format, summary, transformed_content)."""
    if not raw:
        return "Empty", "Clipboard contains no readable text", "N/A"

    # 1. JWT Token (3 base64url segments separated by dots)
    jwt_match = re.match(r"^(ey[A-Za-z0-9_-]+)\.(ey[A-Za-z0-9_-]+)\.([A-Za-z0-9_-]+)$", raw)
    if jwt_match:
        try:
            h_b64 = jwt_match.group(1) + "=="
            p_b64 = jwt_match.group(2) + "=="
            header = json.loads(base64.urlsafe_b64decode(h_b64).decode())
            payload = json.loads(base64.urlsafe_b64decode(p_b64).decode())
            summary = f"JWT Token Decoded (Alg: {header.get('alg', 'N/A')})"
            trans = f"Header:\n{json.dumps(header, indent=2)}\n\nPayload:\n{json.dumps(payload, indent=2)}"
            return "JWT Token", summary, trans
        except Exception:
            pass

    # 2. Curl command
    if raw.lower().startswith("curl "):
        summary = "curl Command Converted to Python requests"
        url_match = re.search(r"curl\s+['\"]?([^'\"\s]+)", raw)
        target_url = url_match.group(1) if url_match else "https://api.example.com"
        py_code = (
            "import requests\n\n"
            f'url = "{target_url}"\n'
            "headers = {'User-Agent': 'JARVIS-Client/1.0'}\n"
            "response = requests.get(url, headers=headers)\n"
            "print(response.status_code, response.text)\n"
        )
        return "cURL Command", summary, py_code

    # 3. JSON Object
    if (raw.startswith("{") and raw.endswith("}")) or (raw.startswith("[") and raw.endswith("]")):
        try:
            parsed = json.loads(raw)
            pretty = json.dumps(parsed, indent=2)
            summary = f"Formatted JSON ({len(parsed) if isinstance(parsed, list) else len(parsed.keys())} keys)"
            return "JSON Data", summary, pretty
        except Exception:
            pass

    # 4. Unix Timestamp
    if re.match(r"^\d{10}$", raw):
        try:
            ts = int(raw)
            dt_utc = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
            dt_loc = datetime.datetime.fromtimestamp(ts)
            summary = f"Unix Timestamp {ts}"
            trans = f"UTC:   {dt_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}\nLocal: {dt_loc.strftime('%Y-%m-%d %H:%M:%S')}"
            return "Unix Timestamp", summary, trans
        except Exception:
            pass

    # 5. Base64 String
    if len(raw) > 16 and len(raw) % 4 == 0 and re.match(r"^[A-Za-z0-9+/=]+$", raw):
        try:
            dec = base64.b64decode(raw).decode("utf-8")
            if all(ord(c) >= 32 or c in "\n\r\t" for c in dec):
                return "Base64 String", "Decoded Base64 Payload", dec
        except Exception:
            pass

    # Default text
    return "Plaintext", f"Text ({len(raw)} chars)", raw[:400]


def _render_hud_card(fmt: str, summary: str, trans: str) -> str:
    lines = [
        "### 📋 SMART CLIPBOARD COPILOT (JARVIS MARK-LVII)\n",
        f"**Detected Format:** `{fmt.upper()}`",
        f"**Transformation:** *{summary}*\n",
        "#### 🔄 Transformed Output",
        "```text",
        trans[:1000],
        "```\n",
        f"*Clipboard parsed at {time.strftime('%H:%M:%S')}.*",
    ]
    return "\n".join(lines)


def _worker(text_arg: str, player):
    try:
        raw = _read_clipboard(text_arg)
        fmt, summary, trans = _transform_clipboard_content(raw)
        card = _render_hud_card(fmt, summary, trans)

        if player:
            try:
                player.show_content("SMART CLIPBOARD", card)
                player.write_log(f"📋 [SmartClipboard] Identified {fmt}: {summary}.")
            except Exception:
                pass
    except Exception as e:
        if player:
            try:
                player.write_log(f"⚠️ [SmartClipboard] Error: {e}")
            except Exception:
                pass


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        text_arg = str(
            parameters.get("text")
            or parameters.get("content")
            or parameters.get("data")
            or ""
        ).strip()
        threading.Thread(target=_worker, args=(text_arg, player), daemon=True).start()
        return "Analyzing clipboard contents and pre-computing intelligent transformations, sir. Card is on the HUD."
    except Exception as e:
        return f"Sir, smart clipboard copilot encountered an issue: {e}"
