"""
plugins/telegram_bridge.py — Advanced Telegram Bot Bridge for JARVIS Mark-LVII.

HERMES-STYLE SECURITY & PAIRING:
  - Cryptographically secure one-time QR code pairing (ASCII in terminal, PNG on HUD).
  - Strict chat authorization: silently drops/ignores all unauthorized senders.
  - One-tap /unpair to invalidate credentials and re-open QR pairing flow.

MULTIMODAL INTELLIGENCE:
  - Inbound Photos & Images: Vision analysis powered by Gemini Vision.
  - Inbound Voice Messages: Audio speech understanding via Gemini audio pipeline.
  - Inbound Documents: Remote file ingestion saved to downloads/ with automatic summaries.

REMOTE DESKTOP VISION & HARDWARE:
  - /screen: Live desktop screenshot returned as a Telegram photo.
  - /camera: Webcam frame snapshot returned as a Telegram photo.
  - /status: Live CPU %, RAM %, engine state, and active tasks.
  - /mute & /unmute: Remote audio toggle.
  - /volume <0-100>: Master volume control.
  - /playpause, /next, /prev: Remote media controls.

AUTONOMOUS TASKS & RESEARCH REPORTS:
  - /tasks: Live overview of background tasks, agents, and run states.
  - /task <goal>: Start an autonomous background research task.
  - /steer <id> <note>: Steer an in-flight background task.
  - /cancel <id>: Cancel a running task.
  - /reports: Browse generated deep research reports.
  - /report <name_or_number>: Deliver the report file directly as a Telegram document.

EXECUTIVE BRIEFINGS & QUICK CONTROLS:
  - /brief: On-demand executive briefing synthesizing schedule, news, tasks, and system health.
  - /menu: Interactive quick-action keypad for one-tap controls.
  - Native command palette registration via setMyCommands.
  - Safety confirmation gate: Destructive actions (shutdown, restart, WiFi) prompt inline [Approve] / [Deny] keyboards.

Zero new dependencies: Uses only httpx and qrcode (already in requirements.txt).
"""

from __future__ import annotations

import base64
import html
import io
import json
import os
import re
import secrets
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

import httpx
import qrcode

# ── Paths ────────────────────────────────────────────────────────────────────
_BASE_DIR = Path(__file__).resolve().parent.parent
_CONFIG_DIR = _BASE_DIR / "config"
_DOWNLOADS_DIR = _BASE_DIR / "downloads"
_REPORTS_DIR = _BASE_DIR / "reports"
_PAIRED_FILE = _CONFIG_DIR / "telegram_paired.json"
_QR_IMAGE_FILE = _CONFIG_DIR / "telegram_qr.png"

# ── Plugin Declaration ───────────────────────────────────────────────────────
PLUGIN = {
    "name": "telegram_bridge",
    "description": (
        "Send proactive push messages, alerts, or reports to the user's paired Telegram phone. "
        "Use this tool when you want to send a text notification, update, or link to the user on Telegram."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "message": {
                "type": "STRING",
                "description": "The message text to send to the user's paired Telegram.",
            }
        },
        "required": ["message"],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "telegram_bridge",
    "title": "Telegram Bot Bridge",
    "fields": [
        {
            "key": "telegram_bot_token",
            "label": "Bot Token",
            "type": "password",
            "placeholder": "123456789:ABCdefGHIjklMNOpqrSTUvwxYZ",
            "secret": True,
        }
    ],
}


# ── Utility Functions ────────────────────────────────────────────────────────
def _get_bot_token() -> str:
    try:
        from memory.config_manager import load_api_keys
        cfg = load_api_keys()
        token = (
            cfg.get("telegram_bot_token")
            or (cfg.get("telegram") or {}).get("bot_token")
            or (cfg.get("plugins") or {}).get("telegram_bridge", {}).get("telegram_bot_token")
            or (cfg.get("plugins") or {}).get("telegram_bridge", {}).get("bot_token")
            or os.environ.get("TELEGRAM_BOT_TOKEN")
            or ""
        )
        return str(token).strip()
    except Exception:
        return ""


def _chunk_text(text: str, max_chars: int = 4000) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks = []
    rem = text
    while rem:
        if len(rem) <= max_chars:
            chunks.append(rem)
            break
        split_idx = rem.rfind("\n\n", 0, max_chars)
        if split_idx == -1:
            split_idx = rem.rfind("\n", 0, max_chars)
        if split_idx == -1:
            split_idx = rem.rfind(" ", 0, max_chars)
        if split_idx == -1:
            split_idx = max_chars
        chunks.append(rem[:split_idx].strip())
        rem = rem[split_idx:].strip()
    return chunks


def _format_telegram_html(text: str) -> str:
    escaped = html.escape(text)
    # Fenced code blocks
    escaped = re.sub(
        r"```([a-zA-Z0-9_-]*)\n?(.*?)```",
        r"<pre><code>\2</code></pre>",
        escaped,
        flags=re.DOTALL,
    )
    # Inline code
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    # Bold
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", escaped)
    # Italic
    escaped = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", escaped)
    return escaped


def _quick_keypad() -> dict:
    return {
        "keyboard": [
            [{"text": "📸 Screen"}, {"text": "👁 Camera"}, {"text": "📊 Status"}],
            [{"text": "📋 Tasks"}, {"text": "📄 Reports"}, {"text": "🎙 Briefing"}],
            [{"text": "🔇 Mute"}, {"text": "🔊 Unmute"}, {"text": "❓ Help"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


# ── TelegramBridge Engine ────────────────────────────────────────────────────
class TelegramBridge:
    def __init__(self):
        self._lock = threading.Lock()
        self._token = ""
        self._bot_username = ""
        self._pairing_token = ""
        self._paired_chat_id: Optional[int] = None
        self._paired_info: dict = {}
        self._player = None
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._last_confirm_msg_id: Optional[int] = None
        self._hooks_installed = False

    def get_player(self):
        if self._player:
            return self._player
        try:
            from core.tasks import desktop as tasks_desktop
            p = getattr(tasks_desktop, "_player", None)
            if p is not None:
                self._player = p
                return p
        except Exception:
            pass
        return None

    def attach_player(self, player) -> None:
        if player is not None and self._player is not player:
            self._player = player
            if not self._paired_chat_id and self._pairing_token and self._bot_username:
                self._show_qr_on_hud()

    # ── Pairing Persistence ──────────────────────────────────────────────────
    def _load_paired(self) -> bool:
        if not _PAIRED_FILE.exists():
            self._paired_chat_id = None
            self._paired_info = {}
            return False
        try:
            data = json.loads(_PAIRED_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "chat_id" in data:
                self._paired_chat_id = int(data["chat_id"])
                self._paired_info = data
                return True
        except Exception as e:
            print(f"[Telegram] Error loading {_PAIRED_FILE.name}: {e}")
        self._paired_chat_id = None
        self._paired_info = {}
        return False

    def _save_paired(self, chat_id: int, username: str = "", first_name: str = "") -> None:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "chat_id": chat_id,
            "username": username,
            "first_name": first_name,
            "paired_at": time.time(),
        }
        _PAIRED_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self._paired_chat_id = chat_id
        self._paired_info = data
        self._pairing_token = ""

    def _clear_paired(self) -> None:
        self._paired_chat_id = None
        self._paired_info = {}
        try:
            if _PAIRED_FILE.exists():
                _PAIRED_FILE.unlink()
        except Exception:
            pass

    # ── QR Code Pairing Display ──────────────────────────────────────────────
    def _trigger_qr_pairing(self) -> None:
        if not self._bot_username:
            return
        self._pairing_token = secrets.token_urlsafe(16)
        deep_link = f"https://t.me/{self._bot_username}?start={self._pairing_token}"

        # 1. ASCII QR in terminal
        try:
            qr = qrcode.QRCode(box_size=1, border=1)
            qr.add_data(deep_link)
            qr.make(fit=True)
            buf = io.StringIO()
            qr.print_ascii(out=buf, invert=True)
            ascii_qr = buf.getvalue()

            print("\n" + "═" * 60)
            print("  JARVIS TELEGRAM BRIDGE — ONE-TIME PAIRING")
            print("═" * 60)
            print(f"Deep link: {deep_link}\n")
            print("Scan this QR code with your phone camera to pair Telegram:")
            print(ascii_qr)
            print("═" * 60 + "\n")
        except Exception as e:
            print(f"[Telegram] Terminal ASCII QR error: {e}")

        # 2. PNG QR image for HUD
        try:
            _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            qr_img = qrcode.QRCode(box_size=6, border=2)
            qr_img.add_data(deep_link)
            qr_img.make(fit=True)
            img = qr_img.make_image(fill_color="black", back_color="white")
            img.save(str(_QR_IMAGE_FILE))
        except Exception as e:
            print(f"[Telegram] PNG QR save error: {e}")

        self._show_qr_on_hud()

    def _show_qr_on_hud(self) -> None:
        p = self.get_player()
        if not p:
            return
        deep_link = f"https://t.me/{self._bot_username}?start={self._pairing_token}"
        try:
            if hasattr(p, "write_log"):
                p.write_log(f"SYS: Telegram pairing ready — connect with @{self._bot_username}")
            if hasattr(p, "show_content"):
                p.show_content(
                    "TELEGRAM PAIRING",
                    f"Scan the QR code to pair JARVIS with @{self._bot_username}:\n\n"
                    f"{deep_link}\n\n"
                    "Tap START in Telegram to complete authorization.",
                )
            if hasattr(p, "show_image") and _QR_IMAGE_FILE.exists():
                p.show_image(str(_QR_IMAGE_FILE.resolve()), "Telegram Pairing QR")
        except Exception as e:
            print(f"[Telegram] HUD QR display error: {e}")

    def _dismiss_qr_from_hud(self) -> None:
        p = self.get_player()
        if not p:
            return
        try:
            if hasattr(p, "stop_video"):
                p.stop_video()
            if hasattr(p, "show_content"):
                user_label = f"@{self._paired_info.get('username')}" if self._paired_info.get("username") else f"ID {self._paired_chat_id}"
                p.show_content("TELEGRAM BRIDGE", f"Bridge active and securely paired with {user_label}.")
        except Exception as e:
            print(f"[Telegram] Dismiss QR HUD error: {e}")

    # ── Telegram API Operations ──────────────────────────────────────────────
    def _api_call(self, endpoint: str, json_data: dict | None = None, timeout: float = 15.0) -> dict | None:
        if not self._token:
            return None
        url = f"https://api.telegram.org/bot{self._token}/{endpoint}"
        try:
            with httpx.Client(timeout=timeout) as client:
                if json_data is not None:
                    resp = client.post(url, json=json_data)
                else:
                    resp = client.get(url)
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 400:
                    return {"ok": False, "error_code": 400, "description": resp.text}
                else:
                    print(f"[Telegram] API {endpoint} returned status {resp.status_code}: {resp.text[:120]}")
                    return None
        except httpx.TimeoutException:
            return None
        except Exception as e:
            print(f"[Telegram] API call {endpoint} failed: {e}")
            return None

    def register_bot_commands(self) -> None:
        commands = [
            {"command": "status", "description": "System health, CPU, RAM & status"},
            {"command": "screen", "description": "Capture live desktop screenshot"},
            {"command": "camera", "description": "Capture webcam frame snapshot"},
            {"command": "tasks", "description": "View & manage background tasks"},
            {"command": "reports", "description": "Browse & download research reports"},
            {"command": "brief", "description": "Executive morning / daily briefing"},
            {"command": "menu", "description": "Show interactive quick control keypad"},
            {"command": "mute", "description": "Mute host audio"},
            {"command": "unmute", "description": "Unmute host audio"},
            {"command": "help", "description": "Detailed command documentation"},
            {"command": "unpair", "description": "Disconnect Telegram pairing"},
        ]
        self._api_call("setMyCommands", {"commands": commands})

    def send_chat_action(self, action: str = "typing") -> None:
        if not self._paired_chat_id or not self._token:
            return
        self._api_call("sendChatAction", {"chat_id": self._paired_chat_id, "action": action})

    def send_push(self, text: str, reply_markup: dict | None = None) -> bool:
        if not self._paired_chat_id or not self._token:
            return False
        chunks = _chunk_text(text, max_chars=4000)
        success = True
        for i, chunk in enumerate(chunks):
            markup = reply_markup if (i == len(chunks) - 1) else None
            html_text = _format_telegram_html(chunk)
            payload = {
                "chat_id": self._paired_chat_id,
                "text": html_text,
                "parse_mode": "HTML",
            }
            if markup:
                payload["reply_markup"] = markup

            res = self._api_call("sendMessage", payload)
            if res and not res.get("ok"):
                payload["text"] = chunk
                payload.pop("parse_mode", None)
                res = self._api_call("sendMessage", payload)

            if not res or not res.get("ok"):
                success = False
        return success

    def send_photo(self, photo_bytes: bytes, caption: str = "", filename: str = "image.jpg") -> bool:
        if not self._paired_chat_id or not self._token:
            return False
        url = f"https://api.telegram.org/bot{self._token}/sendPhoto"
        files = {"photo": (filename, photo_bytes, "image/jpeg")}
        data = {"chat_id": self._paired_chat_id}
        if caption:
            data["caption"] = caption[:1024]
            data["parse_mode"] = "HTML"
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(url, data=data, files=files)
                if resp.status_code == 200 and resp.json().get("ok"):
                    return True
                if resp.status_code == 400:
                    data.pop("parse_mode", None)
                    resp = client.post(url, data=data, files=files)
                    return resp.status_code == 200 and resp.json().get("ok")
                print(f"[Telegram] sendPhoto error: {resp.status_code} {resp.text[:120]}")
        except Exception as e:
            print(f"[Telegram] sendPhoto exception: {e}")
        return False

    def send_document(self, doc_bytes: bytes, filename: str, caption: str = "") -> bool:
        if not self._paired_chat_id or not self._token:
            return False
        url = f"https://api.telegram.org/bot{self._token}/sendDocument"
        files = {"document": (filename, doc_bytes, "application/octet-stream")}
        data = {"chat_id": self._paired_chat_id}
        if caption:
            data["caption"] = caption[:1024]
            data["parse_mode"] = "HTML"
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(url, data=data, files=files)
                if resp.status_code == 200 and resp.json().get("ok"):
                    return True
                if resp.status_code == 400:
                    data.pop("parse_mode", None)
                    resp = client.post(url, data=data, files=files)
                    return resp.status_code == 200 and resp.json().get("ok")
                print(f"[Telegram] sendDocument error: {resp.status_code} {resp.text[:120]}")
        except Exception as e:
            print(f"[Telegram] sendDocument exception: {e}")
        return False

    def download_file(self, file_id: str) -> tuple[bytes, str] | None:
        res = self._api_call("getFile", {"file_id": file_id})
        if not res or not res.get("ok"):
            return None
        file_path = res["result"].get("file_path", "")
        if not file_path:
            return None
        url = f"https://api.telegram.org/file/bot{self._token}/{file_path}"
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    return resp.content, Path(file_path).name
        except Exception as e:
            print(f"[Telegram] Download file {file_id} failed: {e}")
        return None

    def send_from_tool(self, message: str) -> str:
        if not self._paired_chat_id:
            return "Telegram bridge is not paired yet. Please scan the pairing QR code first."
        ok = self.send_push(f"📢 <b>Notification from JARVIS:</b>\n\n{message}")
        return "Message sent to your Telegram." if ok else "Failed to deliver message to Telegram."

    # ── Confirmation Safety Gate ─────────────────────────────────────────────
    def request_confirmation(self, title: str, detail: str) -> None:
        if not self._paired_chat_id:
            return
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ Approve", "callback_data": "confirm:yes"},
                    {"text": "❌ Deny", "callback_data": "confirm:no"},
                ]
            ]
        }
        msg = (
            f"⚠️ <b>CONFIRMATION REQUIRED</b>\n\n"
            f"<b>Action:</b> {html.escape(title)}\n"
            f"<i>{html.escape(detail)}</i>\n\n"
            f"Please tap Approve or Deny."
        )
        res = self._api_call(
            "sendMessage",
            {
                "chat_id": self._paired_chat_id,
                "text": msg,
                "parse_mode": "HTML",
                "reply_markup": keyboard,
            },
        )
        if res and res.get("ok"):
            self._last_confirm_msg_id = res["result"]["message_id"]

    def dismiss_confirmation(self) -> None:
        if not self._paired_chat_id or not self._last_confirm_msg_id:
            return
        msg_id = self._last_confirm_msg_id
        self._last_confirm_msg_id = None
        self._api_call(
            "editMessageReplyMarkup",
            {
                "chat_id": self._paired_chat_id,
                "message_id": msg_id,
                "reply_markup": {"inline_keyboard": []},
            },
        )

    # ── Notification Hooks ───────────────────────────────────────────────────
    def install_hooks(self) -> None:
        if self._hooks_installed:
            return
        self._hooks_installed = True

        # 1. Hook core.confirm
        try:
            from core import confirm

            orig_bind = getattr(confirm, "bind", None)

            def wrapped_bind(show, hide, log=None):
                if orig_bind:
                    orig_bind(show, hide, log)
                _wrap_confirm_callbacks()

            def _wrap_confirm_callbacks():
                orig_show = confirm._show_cb
                orig_hide = confirm._hide_cb

                def hooked_show(title, detail):
                    if orig_show:
                        try:
                            orig_show(title, detail)
                        except Exception:
                            pass
                    self.request_confirmation(title, detail)

                def hooked_hide():
                    if orig_hide:
                        try:
                            orig_hide()
                        except Exception:
                            pass
                    self.dismiss_confirmation()

                confirm._show_cb = hooked_show
                confirm._hide_cb = hooked_hide

            if orig_bind:
                confirm.bind = wrapped_bind
            if confirm._show_cb:
                _wrap_confirm_callbacks()
        except Exception as e:
            print(f"[Telegram] confirm hook error: {e}")

        # 2. Hook core.tasks.desktop._notify
        try:
            from core.tasks import desktop as tasks_desktop

            orig_notify = tasks_desktop._notify

            def hooked_notify(event: str, task: dict | None, text: str):
                orig_notify(event, task, text)
                try:
                    if not task or not self._paired_chat_id:
                        return
                    title = task.get("title") or "Background Task"
                    if event == "done":
                        res = (task.get("result") or "").strip()
                        report = task.get("report") or ""
                        msg = f"📋 <b>Task Completed:</b> {html.escape(title)}\n\n{html.escape(res[:1800])}"
                        if report:
                            msg += f"\n\n📄 <i>Report saved: {html.escape(report)}</i>"
                        self.send_push(msg)
                    elif event == "failed":
                        err = (task.get("error") or "Unknown error").strip()
                        self.send_push(f"⚠️ <b>Task Failed:</b> {html.escape(title)}\n\nError: {html.escape(err[:500])}")
                except Exception as ex:
                    print(f"[Telegram] Tasks notify hook error: {ex}")

            tasks_desktop._notify = hooked_notify
        except Exception as e:
            print(f"[Telegram] tasks hook error: {e}")

        # 3. Hook routine notifications via player.write_log wrapper
        def hook_player_log():
            p = self.get_player()
            if not p or getattr(p, "_telegram_log_hooked", False):
                return
            orig_write_log = p.write_log

            def hooked_write_log(txt: str):
                orig_write_log(txt)
                try:
                    if not self._paired_chat_id:
                        return
                    if "[SYSTEM_ALERT]" in txt or "CRITICAL" in txt:
                        self.send_push(f"🚨 <b>Hardware Alert:</b>\n{html.escape(txt)}")
                    elif "SYS: Routine —" in txt:
                        routine_name = txt.partition("—")[2].strip()
                        self.send_push(f"⏰ <b>Scheduled Routine Fired:</b>\n{html.escape(routine_name)}")
                except Exception:
                    pass

            p.write_log = hooked_write_log
            p._telegram_log_hooked = True

        threading.Thread(target=self._log_hook_watcher, args=(hook_player_log,), daemon=True).start()

    def _log_hook_watcher(self, hook_fn: Callable[[], None]) -> None:
        for _ in range(30):
            if self.get_player():
                hook_fn()
                break
            time.sleep(1.0)

    # ── Advanced Feature Handlers ────────────────────────────────────────────
    def _cmd_screen(self) -> None:
        try:
            from actions.screen_processor import _capture_screen

            png_bytes, mime = _capture_screen()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.send_photo(
                png_bytes,
                caption=f"🖥 <b>Desktop Snapshot</b> — <code>{now_str}</code>",
                filename="desktop_screen.png",
            )
        except Exception as e:
            self.send_push(f"⚠️ Screen capture error: {e}")

    def _cmd_camera(self) -> None:
        try:
            from actions.screen_processor import _capture_camera

            jpg_bytes, mime = _capture_camera()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.send_photo(
                jpg_bytes,
                caption=f"📷 <b>Webcam Snapshot</b> — <code>{now_str}</code>",
                filename="webcam.jpg",
            )
        except Exception as e:
            self.send_push(f"⚠️ Webcam capture error: {e}")

    def _cmd_status(self) -> None:
        import psutil

        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory().percent
        boot = datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")

        # Battery info if available
        battery_line = ""
        try:
            bat = psutil.sensors_battery()
            if bat:
                plugged = "🔌 Plugged In" if bat.power_plugged else "🔋 On Battery"
                battery_line = f"• <b>Battery:</b> {bat.percent:.0f}% ({plugged})\n"
        except Exception:
            pass

        # Background tasks count
        tasks_line = ""
        try:
            from core.tasks import desktop as tasks_desktop

            eng = tasks_desktop.engine()
            if eng:
                active_tasks = [t for t in eng.list(limit=20) if t.get("status") in ("running", "queued")]
                tasks_line = f"• <b>Active Tasks:</b> {len(active_tasks)}\n"
        except Exception:
            pass

        self.send_push(
            f"📊 <b>JARVIS System Status</b>\n\n"
            f"• <b>CPU Load:</b> {cpu:.0f}%\n"
            f"• <b>RAM Usage:</b> {ram:.0f}%\n"
            f"{battery_line}"
            f"• <b>Host Booted:</b> <code>{boot}</code>\n"
            f"{tasks_line}"
            f"• <b>Telegram Bridge:</b> 🟢 Active & Paired\n"
            f"• <b>Authorized User:</b> @{self._paired_info.get('username') or 'Sir'}"
        )

    def _cmd_tasks(self) -> None:
        try:
            from core.tasks import desktop as tasks_desktop

            eng = tasks_desktop.engine()
            if not eng:
                self.send_push("Tasks engine is not initialized.")
                return

            tasks = eng.list(limit=10)
            if not tasks:
                self.send_push("📋 <b>No background tasks found.</b>\n\nStart one with: <code>/task research AI</code>")
                return

            lines = ["📋 <b>Background Tasks (Recent)</b>\n"]
            for t in tasks:
                status = t.get("status", "unknown")
                icon = {
                    "running": "⚡",
                    "queued": "⏳",
                    "done": "✅",
                    "failed": "❌",
                    "cancelled": "🚫",
                }.get(status, "▫️")
                tid = t.get("id", "")
                title = t.get("title", "Untitled")[:40]
                lines.append(f"{icon} <code>{tid}</code> — <b>{html.escape(title)}</b> ({status})")

            lines.append("\n<i>Tip: Use /cancel &lt;id&gt; or /steer &lt;id&gt; &lt;note&gt;</i>")
            self.send_push("\n".join(lines))
        except Exception as e:
            self.send_push(f"⚠️ Error fetching tasks: {e}")

    def _cmd_reports(self, arg: str = "") -> None:
        if not _REPORTS_DIR.exists():
            self.send_push("📄 <b>No research reports generated yet.</b>")
            return

        reports = sorted(_REPORTS_DIR.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not reports:
            self.send_push("📄 <b>No research reports found in memory.</b>")
            return

        arg = arg.strip()
        if arg:
            # User wants a specific report
            target = None
            if arg.isdigit():
                idx = int(arg) - 1
                if 0 <= idx < len(reports):
                    target = reports[idx]
            else:
                for r in reports:
                    if arg.lower() in r.name.lower():
                        target = r
                        break

            if target and target.exists():
                try:
                    content = target.read_bytes()
                    self.send_document(content, filename=target.name, caption=f"📄 <b>Report:</b> {html.escape(target.name)}")
                    return
                except Exception as e:
                    self.send_push(f"⚠️ Failed to send report: {e}")
                    return
            else:
                self.send_push(f"❌ Report '{html.escape(arg)}' not found.")
                return

        # List reports
        lines = ["📄 <b>Available Research Reports:</b>\n"]
        for i, r in enumerate(reports[:10]):
            size_kb = r.stat().st_size / 1024
            mtime = datetime.fromtimestamp(r.stat().st_mtime).strftime("%b %d %H:%M")
            lines.append(f"<b>{i+1}.</b> <code>{html.escape(r.name)}</code> ({size_kb:.1f} KB, {mtime})")

        lines.append("\n<i>Send <code>/report &lt;number&gt;</code> to download a full report.</i>")
        self.send_push("\n".join(lines))

    def _cmd_briefing(self) -> None:
        self.send_push("⏳ <i>Synthesizing executive briefing...</i>")

        def _worker():
            try:
                from core import gemini
                import psutil

                cpu = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory().percent
                now_str = datetime.now().strftime("%A, %B %d, %Y at %H:%M")

                # Fetch news topic
                news_text = ""
                try:
                    from actions import web_search

                    news_text = web_search._gemini_search("top world headlines today")
                except Exception:
                    pass

                prompt = (
                    f"You are {asst_name}, an executive AI assistant communicating with your operator via Telegram.\n"
                    f"Current Date and Time: {now_str}\n"
                    f"Host Telemetry: CPU {cpu:.0f}%, RAM {ram:.0f}%\n"
                    f"World News Context:\n{news_text[:1200]}\n\n"
                    "Provide a crisp, professional, high-level executive briefing. "
                    "Structure into: Greeting & Status, System Health, and Top 3 Key Highlights. "
                    "Tone: composed, dry, understated, addressing the user respectfully as Sir. "
                    "Keep it under 180 words. Use clean Telegram HTML formatting (<b>bold</b> titles, bullet points)."
                )
                briefing_res = gemini.text(prompt, tier=gemini.SMART, timeout_ms=35000)
                if not briefing_res:
                    briefing_res = f"Good day, Sir. It is {now_str}. System load is at {cpu:.0f}% CPU and {ram:.0f}% RAM. All primary modules operating within normal parameters."

                self.send_push(f"☀️ <b>JARVIS Executive Briefing</b>\n\n{briefing_res}")
            except Exception as e:
                self.send_push(f"⚠️ Failed to generate briefing: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def _cmd_mute(self, muted: bool) -> None:
        try:
            from actions import computer_settings

            act = "mute" if muted else "unmute"
            computer_settings.computer_settings({"action": act})
            p = self.get_player()
            if p and hasattr(p, "muted"):
                p.muted = muted
            self.send_push("🔇 <b>Audio muted.</b>" if muted else "🔊 <b>Audio unmuted.</b>")
        except Exception as e:
            self.send_push(f"⚠️ Mute toggle error: {e}")

    def _cmd_volume(self, val_str: str) -> None:
        try:
            from actions import computer_settings

            val = int(re.sub(r"[^\d]", "", val_str) or 50)
            val = max(0, min(100, val))
            computer_settings.computer_settings({"action": "volume_set", "value": str(val)})
            self.send_push(f"🔊 <b>Volume set to {val}%.</b>")
        except Exception as e:
            self.send_push(f"⚠️ Volume error: {e}")

    def _cmd_media(self, action: str) -> None:
        try:
            from actions import computer_settings

            computer_settings.computer_settings({"action": action})
            self.send_push(f"⏯️ Media action executed: <code>{action}</code>")
        except Exception as e:
            self.send_push(f"⚠️ Media action error: {e}")

    def _cmd_help(self) -> None:
        self.send_push(
            "🤖 <b>JARVIS Telegram Command Center</b>\n\n"
            "<b>Vision & Remote Capture:</b>\n"
            "• <code>/screen</code> — Live desktop screenshot\n"
            "• <code>/camera</code> — Webcam frame snapshot\n"
            "• <i>Send any Photo</i> — Gemini Vision visual breakdown\n\n"
            "<b>Voice & Audio:</b>\n"
            "• <i>Send Voice Note</i> — Transcribed & answered via Gemini\n"
            "• <code>/mute</code> | <code>/unmute</code> — Audio mute toggle\n"
            "• <code>/volume &lt;0-100&gt;</code> — Set master volume\n"
            "• <code>/playpause</code>, <code>/next</code>, <code>/prev</code> — Media controls\n\n"
            "<b>Autonomous Tasks & Reports:</b>\n"
            "• <code>/tasks</code> — List background research tasks\n"
            "• <code>/task &lt;goal&gt;</code> — Start new background research task\n"
            "• <code>/steer &lt;id&gt; &lt;note&gt;</code> — Steer running task\n"
            "• <code>/cancel &lt;id&gt;</code> — Cancel background task\n"
            "• <code>/reports</code> — Browse research reports\n"
            "• <code>/report &lt;name|#&gt;</code> — Deliver report file\n\n"
            "<b>Intelligence & System:</b>\n"
            "• <code>/brief</code> — Executive daily briefing\n"
            "• <code>/status</code> — Live host telemetry & load\n"
            "• <code>/menu</code> — Show quick action keypad\n"
            "• <code>/unpair</code> — Disconnect Telegram pairing\n\n"
            "<i>Or simply send any question or text instruction directly!</i>",
            reply_markup=_quick_keypad(),
        )

    # ── Command & Intent Execution ───────────────────────────────────────────
    def _execute_command(self, text: str) -> None:
        p = self.get_player()
        if p and hasattr(p, "write_log"):
            p.write_log(f"[Telegram]: {text}")

        cmd = text.strip()
        cmd_lower = cmd.lower()

        # Keypad / Button aliases & slash commands
        if cmd_lower in ("/menu", "menu", "keypad"):
            self.send_push("🎛 <b>Quick Control Keypad Active</b>", reply_markup=_quick_keypad())
            return

        if cmd_lower in ("/screen", "📸 screen", "screen", "screenshot"):
            self._cmd_screen()
            return

        if cmd_lower in ("/camera", "👁 camera", "camera", "webcam"):
            self._cmd_camera()
            return

        if cmd_lower in ("/status", "📊 status", "status", "system status"):
            self._cmd_status()
            return

        if cmd_lower in ("/tasks", "📋 tasks", "tasks"):
            self._cmd_tasks()
            return

        if cmd_lower in ("/reports", "📄 reports", "reports"):
            self._cmd_reports()
            return

        if cmd_lower.startswith("/report ") or cmd_lower.startswith("report "):
            arg = cmd.partition(" ")[2].strip()
            self._cmd_reports(arg)
            return

        if cmd_lower in ("/brief", "/briefing", "🎙 briefing", "briefing", "morning brief"):
            self._cmd_briefing()
            return

        if cmd_lower in ("/mute", "🔇 mute", "mute"):
            self._cmd_mute(True)
            return

        if cmd_lower in ("/unmute", "🔊 unmute", "unmute"):
            self._cmd_mute(False)
            return

        if cmd_lower.startswith("/volume ") or cmd_lower.startswith("volume "):
            val = cmd.partition(" ")[2].strip()
            self._cmd_volume(val)
            return

        if cmd_lower in ("/playpause", "play/pause", "play pause"):
            self._cmd_media("play_pause")
            return
        if cmd_lower in ("/next", "next track", "next song"):
            self._cmd_media("next_track")
            return
        if cmd_lower in ("/prev", "previous track"):
            self._cmd_media("prev_track")
            return

        if cmd_lower.startswith("/task ") or cmd_lower.startswith("start task "):
            goal = cmd.partition(" ")[2].strip()
            if goal:
                try:
                    from core.tasks import desktop as tasks_desktop

                    tid = tasks_desktop.ensure().start(goal, agent="general", minutes=15, deliver="voice")
                    self.send_push(
                        f"🚀 <b>Background Task Started</b>\n\n"
                        f"• <b>Task ID:</b> <code>{tid}</code>\n"
                        f"• <b>Goal:</b> {html.escape(goal)}\n\n"
                        f"Autonomous agent dispatched. Full report will be pushed when complete."
                    )
                    return
                except Exception as e:
                    self.send_push(f"⚠️ Failed to queue task: {e}")
                    return

        if cmd_lower.startswith("/steer "):
            parts = cmd.partition(" ")[2].strip().partition(" ")
            tid, note = parts[0].strip(), parts[2].strip()
            if tid and note:
                try:
                    from core.tasks import desktop as tasks_desktop

                    ok = tasks_desktop.ensure().steer(tid, note)
                    self.send_push(f"🧭 Steered task <code>{tid}</code>: <i>{html.escape(note)}</i>" if ok else f"❌ Task <code>{tid}</code> not found or already finished.")
                    return
                except Exception as e:
                    self.send_push(f"⚠️ Steer error: {e}")
                    return

        if cmd_lower.startswith("/cancel "):
            tid = cmd.partition(" ")[2].strip()
            if tid:
                try:
                    from core.tasks import desktop as tasks_desktop

                    ok = tasks_desktop.ensure().cancel(tid, finish=True)
                    self.send_push(f"🛑 Cancelled task <code>{tid}</code>." if ok else f"❌ Task <code>{tid}</code> not found.")
                    return
                except Exception as e:
                    self.send_push(f"⚠️ Cancel error: {e}")
                    return

        if cmd_lower in ("/help", "❓ help", "help", "/start"):
            self._cmd_help()
            return

        # Check for dangerous destructive actions
        destructive_keywords = {
            "shutdown": ("Shut this computer down", "Powers off the host computer completely."),
            "power off": ("Shut this computer down", "Powers off the host computer completely."),
            "restart": ("Restart this computer", "Restarts the host system."),
            "reboot": ("Restart this computer", "Restarts the host system."),
            "toggle wifi": ("Switch WiFi", "Toggles wireless network adapter."),
            "turn off wifi": ("Turn WiFi Off", "Disables network connectivity."),
            "disconnect wifi": ("Turn WiFi Off", "Disables network connectivity."),
        }
        for kw, (title, detail) in destructive_keywords.items():
            if kw in cmd_lower:
                try:
                    from core import confirm
                    from actions import computer_settings

                    action = "shutdown" if "shut" in kw or "power" in kw else ("restart" if "re" in kw else "toggle_wifi")
                    func = computer_settings.ACTION_MAP.get(action)
                    if func:
                        confirm.request(
                            key=action,
                            title=title,
                            detail=detail,
                            run=lambda f=func, a=action: (f(), f"{a} done.")[1],
                        )
                        return
                except Exception as e:
                    print(f"[Telegram] Destructive confirmation trigger error: {e}")

        # Direct Main-Session Injection into Live JARVIS Pipeline (All 19 local OS tools)
        p = self.get_player()
        if p and hasattr(p, "dispatch_remote_command") and callable(p.dispatch_remote_command):
            self.send_chat_action("typing")
            reply_evt = threading.Event()
            reply_holder = {"text": ""}

            def _on_live_reply(text_out: str):
                reply_holder["text"] = text_out
                reply_evt.set()

            ok = p.dispatch_remote_command(cmd, origin="Telegram", on_reply=_on_live_reply)
            if ok:
                # Wait up to 35 seconds for the live assistant to execute tools and generate speech/response
                if reply_evt.wait(timeout=35.0) and reply_holder["text"]:
                    self.send_push(reply_holder["text"])
                else:
                    self.send_push("⚡ <i>Command dispatched to JARVIS on host machine.</i>")
                return
            else:
                self.send_push("⚠️ <i>JARVIS main session is currently offline or reconnecting. Please wait a moment.</i>")
                return
        elif p and hasattr(p, "on_text_command") and callable(p.on_text_command):
            # Fallback: Auto-wake and inject via on_text_command
            if hasattr(p, "on_wake_manual") and callable(p.on_wake_manual):
                state = p.wake_get_state() if hasattr(p, "wake_get_state") and callable(p.wake_get_state) else {}
                if state.get("enabled") and not state.get("awake"):
                    p.on_wake_manual()
            p.on_text_command(cmd)
            self.send_push("⚡ <i>Command injected into JARVIS HUD.</i>")
            return

        # Headless fallback if GUI/player is not running
        try:
            from core import gemini

            asst_name = "JARVIS"
            try:
                from memory.config_manager import get_assistant_name

                asst_name = get_assistant_name()
            except Exception:
                pass

            prompt = (
                f"You are {asst_name}, an executive AI assistant communicating with your operator via Telegram.\n"
                f"User command: {cmd}\n\n"
                "You are running directly on their local machine with local tool capabilities. "
                "Reply concisely, accurately, and with your characteristic dry, composed tone in the user's language. "
                "Use clean formatting suitable for mobile display."
            )
            reply = gemini.text(prompt, tier=gemini.SMART, timeout_ms=30000)
            if not reply:
                reply = "I received your message, but the model could not generate a response at this time."

            self.send_push(reply)

            if p and hasattr(p, "write_log"):
                p.write_log(f"{asst_name} (Telegram): {reply[:90]}...")
        except Exception as e:
            self.send_push(f"⚠️ Error executing command: {e}")

    # ── Multimodal Handlers (Photo, Voice, Document) ─────────────────────────
    def _handle_photo(self, photo_list: list, caption: str) -> None:
        self.send_push("🔍 <i>Analyzing image with Gemini Vision...</i>")
        try:
            largest = photo_list[-1]
            file_id = largest.get("file_id")
            downloaded = self.download_file(file_id)
            if not downloaded:
                self.send_push("⚠️ Failed to download photo from Telegram.")
                return

            photo_bytes, fname = downloaded
            b64_data = base64.b64encode(photo_bytes).decode("ascii")

            from core import gemini

            user_caption = caption.strip() or "Analyze this image and identify any key items, text, code, or context."
            system_instruction = (
                f"You are {asst_name}'s high-resolution visual analysis engine. "
                "Examine the image with engineering precision. Structure your response concisely: "
                "1. Brief Overview (1 sentence), "
                "2. Key Visual Details / Extracted Text or Code, "
                "3. Operational Insights / Actionable Takeaway. "
                "Tone: calm, direct, and factual. Avoid generic commentary."
            )
            contents = [
                f"{system_instruction}\n\nUser Request: {user_caption}",
                {"inline_data": {"mime_type": "image/jpeg", "data": b64_data}},
            ]
            analysis = gemini.text(contents, tier=gemini.SMART, timeout_ms=40000)
            if not analysis:
                analysis = "I examined the image but could not generate a description."

            self.send_push(f"👁 <b>Vision Analysis:</b>\n\n{analysis}")
            p = self.get_player()
            if p and hasattr(p, "write_log"):
                p.write_log(f"[Telegram]: Photo analyzed — {user_caption[:50]}")
        except Exception as e:
            self.send_push(f"⚠️ Vision analysis error: {e}")

    def _handle_voice(self, voice_dict: dict) -> None:
        self.send_push("🎙 <i>Transcribing voice message...</i>")
        try:
            file_id = voice_dict.get("file_id")
            downloaded = self.download_file(file_id)
            if not downloaded:
                self.send_push("⚠️ Failed to download voice message.")
                return

            audio_bytes, fname = downloaded
            b64_audio = base64.b64encode(audio_bytes).decode("ascii")

            from core import gemini

            contents = [
                (
                    "Transcribe this voice message accurately into plain text. "
                    "Return ONLY the spoken words verbatim, with no formatting, preamble, or conversational commentary."
                ),
                {"inline_data": {"mime_type": "audio/ogg", "data": b64_audio}},
            ]
            transcribed = (gemini.text(contents, tier=gemini.FAST, timeout_ms=30000) or "").strip()
            if not transcribed:
                self.send_push("⚠️ Could not transcribe the voice message.")
                return

            self.send_push(f"🎙 <i>\"{html.escape(transcribed)}\"</i>")
            # Directly execute the transcribed voice command through the main session!
            self._execute_command(transcribed)
        except Exception as e:
            self.send_push(f"⚠️ Voice processing error: {e}")

    def _handle_document(self, doc_dict: dict, caption: str) -> None:
        file_id = doc_dict.get("file_id")
        fname = doc_dict.get("file_name", "uploaded_file")
        self.send_push(f"📥 <i>Receiving document <code>{html.escape(fname)}</code>...</i>")
        try:
            downloaded = self.download_file(file_id)
            if not downloaded:
                self.send_push(f"⚠️ Failed to download <code>{html.escape(fname)}</code>.")
                return

            doc_bytes, _ = downloaded
            _DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
            save_path = _DOWNLOADS_DIR / fname
            save_path.write_bytes(doc_bytes)

            summary = f"File saved to: <code>{save_path.resolve()}</code> ({len(doc_bytes)/1024:.1f} KB)."

            # If plain text or source code, analyze it
            text_exts = {".txt", ".py", ".md", ".json", ".csv", ".log", ".html", ".css", ".js", ".sh"}
            if save_path.suffix.lower() in text_exts:
                try:
                    text_content = save_path.read_text(encoding="utf-8", errors="replace")[:6000]
                    from core import gemini

                    prompt = (
                        f"The user sent a document named '{fname}'. Caption: '{caption}'. "
                        f"Here is the text content:\n\n{text_content}\n\n"
                        "Summarize the document and explain its purpose or key points concisely."
                    )
                    file_analysis = gemini.text(prompt, tier=gemini.FAST, timeout_ms=30000)
                    if file_analysis:
                        summary += f"\n\n<b>Analysis:</b>\n{file_analysis}"
                except Exception:
                    pass

            self.send_push(f"✅ <b>File Received:</b>\n\n{summary}")
            p = self.get_player()
            if p and hasattr(p, "write_log"):
                p.write_log(f"[Telegram]: Received file {fname}")
        except Exception as e:
            self.send_push(f"⚠️ Document error: {e}")

    # ── Long Polling Worker ──────────────────────────────────────────────────
    def _poll_worker(self) -> None:
        last_update_id = 0

        # 1. Fetch bot profile
        me = self._api_call("getMe")
        if not me or not me.get("ok"):
            print("[Telegram] Failed to connect to Telegram Bot API. Check telegram_bot_token.")
            return

        self._bot_username = me["result"].get("username", "")
        print(f"[Telegram] Connected as @{self._bot_username}")

        # 2. Register bot commands
        try:
            self.register_bot_commands()
        except Exception as e:
            print(f"[Telegram] register_bot_commands error: {e}")

        # 3. Check pairing status
        if not self._load_paired():
            self._trigger_qr_pairing()
        else:
            print(f"[Telegram] Authorized chat_id: {self._paired_chat_id} (@{self._paired_info.get('username')})")

        # 4. Long-polling loop
        while not self._stop_event.is_set():
            params = {"timeout": 25}
            if last_update_id > 0:
                params["offset"] = last_update_id + 1

            res = self._api_call("getUpdates", params, timeout=35.0)
            if not res or not res.get("ok"):
                time.sleep(2.0)
                continue

            updates = res.get("result", [])
            for up in updates:
                up_id = up.get("update_id", 0)
                if up_id > last_update_id:
                    last_update_id = up_id

                # Callback queries (Inline keyboard confirmation)
                cb = up.get("callback_query")
                if cb:
                    self._handle_callback_query(cb)
                    continue

                # Messages
                msg = up.get("message")
                if msg:
                    self._handle_message(msg)

    def _handle_callback_query(self, cb: dict) -> None:
        cb_id = cb.get("id")
        data = cb.get("data", "")
        chat = cb.get("message", {}).get("chat", {})
        chat_id = chat.get("id")
        msg_id = cb.get("message", {}).get("message_id")

        if chat_id != self._paired_chat_id:
            return

        from core import confirm

        if data == "confirm:yes":
            self._api_call("answerCallbackQuery", {"callback_query_id": cb_id, "text": "Action Approved"})
            if msg_id:
                self._api_call(
                    "editMessageText",
                    {
                        "chat_id": chat_id,
                        "message_id": msg_id,
                        "text": "✅ <b>Action Approved</b> — Executing on host computer.",
                        "parse_mode": "HTML",
                    },
                )
            confirm.resolve(True)
        elif data == "confirm:no":
            self._api_call("answerCallbackQuery", {"callback_query_id": cb_id, "text": "Action Denied"})
            if msg_id:
                self._api_call(
                    "editMessageText",
                    {
                        "chat_id": chat_id,
                        "message_id": msg_id,
                        "text": "❌ <b>Action Denied</b> — Cancelled.",
                        "parse_mode": "HTML",
                    },
                )
            confirm.resolve(False)

    def _handle_message(self, msg: dict) -> None:
        chat = msg.get("chat", {})
        chat_id = chat.get("id")
        sender = msg.get("from", {})
        username = sender.get("username", "")
        first_name = sender.get("first_name", "")
        text = str(msg.get("text") or "").strip()
        caption = str(msg.get("caption") or "").strip()

        # CASE 1: UNPAIRED — One-time pairing token verification
        if not self._paired_chat_id:
            if text.startswith("/start"):
                parts = text.split()
                token_arg = parts[1] if len(parts) > 1 else ""
                if token_arg and token_arg == self._pairing_token:
                    self._save_paired(chat_id, username, first_name)
                    self._dismiss_qr_from_hud()
                    p = self.get_player()
                    if p and hasattr(p, "write_log"):
                        p.write_log(f"SYS: Telegram paired with @{username} ({chat_id})")

                    self.send_push(
                        f"🔒 <b>JARVIS Telegram Bridge Paired!</b>\n\n"
                        f"Welcome, {html.escape(first_name or 'Sir')}! This channel is securely linked to your JARVIS Mark-LVII instance.\n\n"
                        f"• Tap any button on the keypad below or type any command.\n"
                        f"• Type <code>/help</code> for full documentation.",
                        reply_markup=_quick_keypad(),
                    )
                else:
                    self._api_call(
                        "sendMessage",
                        {
                            "chat_id": chat_id,
                            "text": "❌ Invalid or expired pairing token. Please scan the QR code displayed on the JARVIS screen.",
                        },
                    )
            return

        # CASE 2: PAIRED — Strict authorization
        if chat_id != self._paired_chat_id:
            return  # Silently drop unauthorized messages

        # Unpair Command
        if text == "/unpair":
            self._clear_paired()
            self._api_call(
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": "🔓 <b>JARVIS Unpaired</b>\n\nThis chat has been disconnected. A new QR code has been generated on the JARVIS screen.",
                    "parse_mode": "HTML",
                },
            )
            p = self.get_player()
            if p and hasattr(p, "write_log"):
                p.write_log("SYS: Telegram unpaired by user.")
            self._trigger_qr_pairing()
            return

        # Multimodal: Photo
        if msg.get("photo"):
            threading.Thread(target=self._handle_photo, args=(msg["photo"], caption), daemon=True).start()
            return

        # Multimodal: Voice Note
        if msg.get("voice"):
            threading.Thread(target=self._handle_voice, args=(msg["voice"],), daemon=True).start()
            return

        # Multimodal: Document / File
        if msg.get("document"):
            threading.Thread(target=self._handle_document, args=(msg["document"], caption), daemon=True).start()
            return

        # Text Command
        if text:
            threading.Thread(target=self._execute_command, args=(text,), daemon=True).start()

    # ── Startup Lifecycle ────────────────────────────────────────────────────
    def start(self) -> None:
        self._token = _get_bot_token()
        if not self._token:
            print("[Telegram] telegram_bot_token not configured in config/api_keys.json; bridge inactive.")
            return

        self.install_hooks()
        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self._poll_worker, name="telegram-bridge-poll", daemon=True)
        self._worker_thread.start()


# ── Global Singleton & Tool Runner ───────────────────────────────────────────
_bridge = TelegramBridge()
_bridge.start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Invoked when Gemini calls the telegram_bridge tool to push a message."""
    if player is not None:
        _bridge.attach_player(player)

    msg = str(parameters.get("message") or "").strip()
    if not msg:
        return "No message specified."
    return _bridge.send_from_tool(msg)
