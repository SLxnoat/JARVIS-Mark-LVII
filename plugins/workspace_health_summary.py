"""
plugins/workspace_health_summary.py - Morning Workstation Readiness & Executive Briefing.

Aggregates system vitals (CPU, RAM, disk storage, battery, uptime), uncommitted Git repositories,
and today's agenda/calendar into a unified executive dashboard on the HUD and concise spoken briefing.

Adheres strictly to AGENTS.md:
- Never instantiates Qt widgets on worker threads.
- Thread-safe HUD updates via player.show_content() and player.write_log().
- Fast returns; non-blocking; never raises unhandled exceptions.
- Handles player=None gracefully.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil

PLUGIN: Dict[str, Any] = {
    "name": "workspace_health_summary",
    "description": (
        "Generates a unified executive morning workstation readiness briefing. "
        "Synthesizes system vitals (CPU load, RAM usage, disk storage, battery, uptime), "
        "uncommitted Git repositories, and today's calendar schedule into a high-density "
        "HUD dashboard and crisp verbal summary."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "include_git": {
                "type": "BOOLEAN",
                "description": "Whether to check uncommitted changes in current Git workspace (default true).",
            },
            "include_agenda": {
                "type": "BOOLEAN",
                "description": "Whether to include today's calendar appointments from memory/calendar.json (default true).",
            },
            "include_system": {
                "type": "BOOLEAN",
                "description": "Whether to include CPU, RAM, disk, and battery vitals (default true).",
            },
        },
    },
}


def _format_bytes(bytes_val: float) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_val < 1024.0:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.1f} PB"


def _format_uptime(seconds: float) -> str:
    mins, secs = divmod(int(seconds), 60)
    hours, mins = divmod(mins, 60)
    days, hours = divmod(hours, 24)
    if days > 0:
        return f"{days}d {hours}h {mins}m"
    return f"{hours}h {mins}m"


def _get_git_status() -> Dict[str, Any]:
    try:
        # Check current working directory
        res_branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if res_branch.returncode != 0:
            return {"is_git": False, "branch": "None", "modified": 0, "untracked": 0}

        branch = res_branch.stdout.strip()
        res_status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        lines = [l for l in res_status.stdout.splitlines() if l.strip()]
        modified = sum(1 for l in lines if not l.startswith("??"))
        untracked = sum(1 for l in lines if l.startswith("??"))
        return {
            "is_git": True,
            "branch": branch,
            "modified": modified,
            "untracked": untracked,
            "clean": len(lines) == 0,
        }
    except Exception:
        return {"is_git": False, "branch": "None", "modified": 0, "untracked": 0, "clean": True}


def _get_today_agenda() -> List[Dict[str, Any]]:
    today_str = datetime.now().strftime("%Y-%m-%d")
    cal_path = Path("memory") / "calendar.json"
    if not cal_path.exists():
        return []

    try:
        with open(cal_path, "r", encoding="utf-8") as f:
            events = json.load(f)
            today_events = []
            for ev in events:
                start = ev.get("start", "")
                if start.startswith(today_str):
                    today_events.append(ev)
            return sorted(today_events, key=lambda x: x.get("start", ""))
    except Exception:
        return []


def run(parameters: dict | None = None, player=None, session_memory=None) -> str:
    try:
        params = parameters or {}
        include_git = params.get("include_git", True)
        include_agenda = params.get("include_agenda", True)
        include_system = params.get("include_system", True)

        # 1. System Vitals
        cpu_pct = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(os.getcwd())
        uptime_sec = time.time() - psutil.boot_time()
        uptime_str = _format_uptime(uptime_sec)

        battery = psutil.sensors_battery()
        bat_str = f"{battery.percent:.0f}% ({'Charging' if battery.power_plugged else 'Battery'})" if battery else "AC Line Powered"

        # 2. Git Status
        git_info = _get_git_status() if include_git else None

        # 3. Agenda
        agenda = _get_today_agenda() if include_agenda else []

        # 4. Synthesize Status
        system_health = "OPTIMAL" if cpu_pct < 80 and mem.percent < 85 and disk.percent < 90 else "HIGH LOAD"

        # Spoken summary construction
        spoken_parts = [f"Good morning, sir. System status is {system_health} at {cpu_pct:.0f}% CPU and {mem.percent:.0f}% memory usage."]
        spoken_parts.append(f"Storage has {_format_bytes(disk.free)} free.")

        if git_info and git_info.get("is_git"):
            if git_info.get("clean"):
                spoken_parts.append(f"Current repository is clean on branch '{git_info['branch']}'.")
            else:
                total_changes = git_info["modified"] + git_info["untracked"]
                spoken_parts.append(f"You have {total_changes} uncommitted file change(s) on branch '{git_info['branch']}'.")

        if agenda:
            spoken_parts.append(f"You have {len(agenda)} event(s) scheduled on today's calendar.")
        else:
            spoken_parts.append("Your calendar schedule is clear for today.")

        spoken_summary = " ".join(spoken_parts)

        # Markdown HUD Card
        git_section = ""
        if git_info and git_info.get("is_git"):
            git_badge = "🟢 CLEAN" if git_info.get("clean") else f"🟡 {git_info['modified']} modified, {git_info['untracked']} untracked"
            git_section = (
                f"### 🌿 Git Workspace Status\n\n"
                f"- **Active Branch:** `{git_info['branch']}`\n"
                f"- **Working Tree:** {git_badge}\n"
                f"- **Repository Path:** `{os.getcwd()}`\n\n"
            )

        agenda_section = ""
        if include_agenda:
            if agenda:
                ev_rows = "\n".join(
                    f"| {ev.get('start', '').split(' ')[-1]} | **{ev.get('title', 'Event')}** | {ev.get('description', '')} |"
                    for ev in agenda
                )
                agenda_section = (
                    f"### 📅 Today's Agenda ({len(agenda)} Events)\n\n"
                    f"| Time | Title | Details |\n"
                    f"|:---|:---|:---|\n"
                    f"{ev_rows}\n\n"
                )
            else:
                agenda_section = (
                    f"### 📅 Today's Agenda\n\n"
                    f"No scheduled appointments in calendar for today.\n\n"
                )

        md = (
            f"## ☀️ Workstation Readiness Briefing\n\n"
            f"> **System Health:** `{system_health}` &nbsp;|&nbsp; **Uptime:** `{uptime_str}` &nbsp;|&nbsp; **Power:** `{bat_str}`\n\n"
            f"### 💻 System Telemetry\n\n"
            f"| Metric | Utilization | Capacity Details |\n"
            f"|:---|:---|:---|\n"
            f"| **CPU Usage** | `{cpu_pct:.1f}%` | {psutil.cpu_count(logical=True)} logical cores |\n"
            f"| **RAM Memory** | `{mem.percent:.1f}%` | {_format_bytes(mem.used)} / {_format_bytes(mem.total)} |\n"
            f"| **Disk Space** | `{disk.percent:.1f}%` | {_format_bytes(disk.free)} free / {_format_bytes(disk.total)} |\n"
            f"| **Host Platform** | `{platform.system()} {platform.release()}` | {platform.node()} |\n\n"
            f"{git_section}"
            f"{agenda_section}"
            f"--- \n*Briefing compiled at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        )

        if player:
            player.show_content("Workstation Health", md)
            player.write_log(f"Briefing: System {system_health} (CPU {cpu_pct:.0f}%, RAM {mem.percent:.0f}%)")

        return spoken_summary

    except Exception as e:
        err_msg = f"Workspace briefing error: {e}"
        if player:
            player.write_log(err_msg)
        return f"Sir, I was unable to complete the workstation health summary: {e}"
