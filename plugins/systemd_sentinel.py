"""
plugins/systemd_sentinel.py — Linux systemd service & journalctl log inspector for JARVIS.

Inspects background service statuses, queries recently failed units, and analyzes
journalctl diagnostic logs on Linux. Zero external dependencies.
"""
from __future__ import annotations

import re
import subprocess
from typing import Any

PLUGIN = {
    "name": "systemd_sentinel",
    "description": (
        "Inspect, check status, or diagnose Linux systemd services and daemons (e.g. docker, "
        "ollama, bluetooth, nginx, cups, NetworkManager). Can check if a service is running, "
        "inspect recent error logs via journalctl, or list failed system units. "
        "Use this tool when the user asks about background services, crashed daemons, or server logs."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action to perform: 'status', 'logs', 'list_failed', 'restart'",
            },
            "service": {
                "type": "STRING",
                "description": "The service or daemon name, e.g. 'docker', 'ollama', 'bluetooth', 'nginx'",
            },
        },
        "required": ["action"],
    },
}


def _clean_service_name(raw: str) -> str:
    name = (raw or "").strip().lower()
    name = re.sub(r"[^a-z0-9_.-]", "", name)
    if name and not name.endswith(".service") and not name.endswith(".socket"):
        name = f"{name}.service"
    return name


def _run_cmd(cmd: list[str], timeout: int = 4) -> tuple[int, str]:
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return r.returncode, (r.stdout or r.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return -1, "Command timed out."
    except Exception as e:
        return -1, str(e)


def run(parameters: dict, player: Any = None, session_memory: Any = None) -> str:
    action = str(parameters.get("action", "status")).strip().lower()
    raw_service = parameters.get("service", "")
    service = _clean_service_name(raw_service)

    try:
        if action == "list_failed":
            code, out = _run_cmd(["systemctl", "--failed", "--no-legend"])
            if not out or code != 0:
                msg = "All systemd units are currently operating normally with zero failed services, Sir."
                if player and hasattr(player, "show_content"):
                    player.show_content("Systemd Units", "✅ All system services running normally.")
                return msg

            lines = [l.strip() for l in out.splitlines() if l.strip()]
            failed_names = []
            for l in lines:
                parts = [p for p in l.split() if p not in ("●", "*", "-")]
                if parts:
                    name = parts[0].strip()
                    if name:
                        failed_names.append(name)

            failed_str = ", ".join(failed_names[:4])
            count = len(failed_names)
            msg = f"Found {count} failed service{'s' if count > 1 else ''}: {failed_str}."
            if player and hasattr(player, "show_content"):
                player.show_content("Failed Systemd Units", "\n".join(f"• {f}" for f in failed_names))
            return msg

        elif action in ("logs", "log", "journal"):
            if not service:
                return "Please specify which service you would like to inspect logs for, Sir."

            # Fetch last 15 lines from journalctl
            code, out = _run_cmd(["journalctl", "-u", service, "-n", "15", "--no-pager"])
            if not out:
                return f"No recent journal logs found for {service}."

            lines = out.splitlines()
            last_lines = "\n".join(lines[-10:])
            # Filter error clues
            errors = [l for l in lines if any(w in l.lower() for w in ("error", "fail", "warn", "critical", "fatal"))]
            error_hint = f" Notable message: {errors[-1].split(': ', 1)[-1][:80]}" if errors else ""

            msg = f"Retrieved recent logs for {service}.{error_hint}"
            if player and hasattr(player, "show_content"):
                player.show_content(f"Logs: {service}", last_lines)
            return msg

        elif action == "restart":
            if not service:
                return "Please state which service you want to restart."
            # Attempt user service restart first
            code, out = _run_cmd(["systemctl", "--user", "restart", service])
            if code == 0:
                return f"User service {service} restarted successfully."
            # If system service, requires elevation or confirmation
            return f"Restarting system service {service} requires administrator privileges. Please run sudo systemctl restart {service} in your terminal."

        else:  # Default: 'status'
            if not service:
                # Fallback to failed check if no service specified
                return run({"action": "list_failed"}, player=player, session_memory=session_memory)

            code, out = _run_cmd(["systemctl", "is-active", service])
            status_word = out.strip().lower() or "unknown"

            # Detailed property lookup
            code2, out2 = _run_cmd(["systemctl", "show", service, "--property=ActiveState,SubState,MainPID"])
            props = dict(line.split("=", 1) for line in out2.splitlines() if "=" in line)
            substate = props.get("SubState", status_word)
            pid = props.get("MainPID", "0")

            if status_word == "active":
                msg = f"The {service} daemon is active and running (PID {pid}, substate {substate})."
            elif status_word == "inactive":
                msg = f"The {service} daemon is currently stopped and inactive."
            elif status_word == "failed":
                msg = f"The {service} daemon has failed. You can ask me to inspect its logs."
            else:
                msg = f"The {service} daemon status is currently {status_word} ({substate})."

            if player and hasattr(player, "show_content"):
                content = f"Unit: {service}\nActive: {status_word}\nSubstate: {substate}\nMain PID: {pid}"
                player.show_content(f"Service: {service}", content)
            return msg

    except Exception as e:
        return f"Could not inspect systemd service: {e}"
