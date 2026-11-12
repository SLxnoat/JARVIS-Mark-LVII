"""
plugins/printer_control.py - 3D printer telemetry and control (OctoPrint / Moonraker / Klipper).

Adheres to AGENTS.md:
- Thread-safe HTTP/REST communication via httpx.
- Thread-safe HUD feedback via player.show_content().
- Never raises exceptions, returns concise spoken feedback.
"""
import os
import httpx
from memory.config_manager import get_plugin_config

PLUGIN = {
    "name": "printer_control",
    "description": (
        "Monitors and controls 3D printers running OctoPrint, Moonraker, or Klipper. "
        "Allows checking nozzle and bed temperatures, print progress, pausing, and resuming jobs."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: 'status', 'temperatures', 'pause', 'resume', 'cancel'.",
                "enum": ["status", "temperatures", "pause", "resume", "cancel"],
            },
            "api_url": {
                "type": "STRING",
                "description": "Optional OctoPrint or Moonraker endpoint URL (e.g. 'http://octopi.local').",
            },
            "api_key": {
                "type": "STRING",
                "description": "Optional API Key for OctoPrint.",
            },
        },
        "required": [],
    },
    "PLUGIN_SETTINGS": {
        "fields": [
            {"key": "url", "label": "Printer URL", "type": "string", "default": "http://octopi.local"},
            {"key": "api_key", "label": "API Key", "type": "password"},
            {"key": "type", "label": "Server Type", "type": "string", "default": "octoprint"},
        ]
    },
}


def _get_config(custom_url=None, custom_key=None):
    cfg = get_plugin_config("printer_control") or {}
    url = custom_url or cfg.get("url") or os.environ.get("PRINTER_URL") or "http://octopi.local"
    key = custom_key or cfg.get("api_key") or os.environ.get("OCTOPRINT_API_KEY")
    ptype = cfg.get("type", "octoprint").lower()
    return url.rstrip("/"), key, ptype


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or parameters.get("mode") or "status").strip().lower()
    custom_url = parameters.get("api_url")
    custom_key = parameters.get("api_key")

    base_url, api_key, server_type = _get_config(custom_url, custom_key)
    headers = {"X-Api-Key": api_key} if api_key else {}

    try:
        with httpx.Client(timeout=6.0) as client:
            if action in ("status", "temperatures"):
                # Try OctoPrint printer endpoint first
                resp = client.get(f"{base_url}/api/printer", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    temp = data.get("temperature", {})
                    tool0 = temp.get("tool0", {})
                    bed = temp.get("bed", {})
                    actual_tool = tool0.get("actual", 0)
                    target_tool = tool0.get("target", 0)
                    actual_bed = bed.get("actual", 0)
                    target_bed = bed.get("target", 0)

                    # Get Job progress
                    job_resp = client.get(f"{base_url}/api/job", headers=headers)
                    job_text = "Idle"
                    pct = 0.0
                    if job_resp.status_code == 200:
                        job_data = job_resp.json()
                        job_text = job_data.get("state", "Operational")
                        progress = job_data.get("progress", {})
                        pct = progress.get("completion") or 0.0

                    hud_md = (
                        f"### 🖨️ 3D Printer Status (`{job_text}`)\n\n"
                        f"- **Nozzle (Tool 0):** `{actual_tool}°C / {target_tool}°C`\n"
                        f"- **Heated Bed:** `{actual_bed}°C / {target_bed}°C`\n"
                        f"- **Print Completion:** `{pct:.1f}%`\n"
                    )
                    if player:
                        try:
                            player.show_content("3D Printer Telemetry", hud_md)
                        except Exception:
                            pass

                    if pct > 0:
                        return f"Printer is currently {job_text} at {pct:.1f}% completion. Nozzle is {actual_tool}°C, Bed is {actual_bed}°C."
                    return f"Printer is {job_text}. Nozzle is at {actual_tool}°C and Bed is at {actual_bed}°C."

                # Try Moonraker/Klipper fallback
                klipper_resp = client.get(f"{base_url}/printer/info")
                if klipper_resp.status_code == 200:
                    k_data = klipper_resp.json().get("result", {})
                    state = k_data.get("state_message", "Klipper ready")
                    return f"Klipper 3D printer status: {state}."

                if not api_key:
                    return f"Printer returned HTTP {resp.status_code}. If running OctoPrint, ensure your API key is configured."
                return f"Could not fetch printer telemetry from {base_url} (HTTP {resp.status_code})."

            elif action in ("pause", "resume", "cancel"):
                command_map = {
                    "pause": {"command": "pause", "action": "pause"},
                    "resume": {"command": "pause", "action": "resume"},
                    "cancel": {"command": "cancel"},
                }
                cmd = command_map.get(action)
                resp = client.post(f"{base_url}/api/job", headers=headers, json=cmd)
                if resp.status_code in (200, 204):
                    if player:
                        try:
                            player.write_log(f"🖨️ [Printer] Executed job command: {action}")
                        except Exception:
                            pass
                    return f"Successfully sent '{action}' command to 3D printer."
                return f"Printer rejected '{action}' command (HTTP {resp.status_code})."

            else:
                return f"Unknown action '{action}'. Valid actions: status, temperatures, pause, resume, cancel."

    except httpx.ConnectError:
        return f"Could not connect to 3D printer at {base_url}. Ensure the printer server is powered on and accessible on your local network."
    except Exception as e:
        return f"Error communicating with 3D printer: {e}"
