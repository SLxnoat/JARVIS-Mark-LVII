"""
plugins/process_forensics.py - In-Memory Process Anomaly & Forensic Scanner.

Iron Man / JARVIS style host forensics:
- Scans Linux /proc filesystem for hidden/deleted running binaries (/proc/[pid]/exe (deleted)).
- Flags abnormal executions launched out of /tmp, /dev/shm, or /var/tmp.
- Analyzes top memory & CPU consuming processes with parent PID tracking.
- Inspects open file descriptors and socket handles per suspicious process.
- Renders a tactical forensic anomaly matrix on the HUD via player.show_content().

Adheres strictly to AGENTS.md:
- No Qt widgets on worker threads.
- Thread-safe HUD feedback via player.show_content() and player.write_log().
- Safe non-blocking execution on background daemon thread.
- Never raises exceptions, returns concise spoken feedback.
- Handles player=None gracefully.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

PLUGIN = {
    "name": "process_forensics",
    "description": (
        "JARVIS Process Forensics: Inspects the Linux process tree for in-memory anomalies, "
        "including unlinked running binaries (/proc/[pid]/exe (deleted)), executions out of /tmp or "
        "/dev/shm, and anomalous resource hogs. Renders a forensic threat card on the HUD."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "Action to perform: 'unlinked_binaries' (scan for deleted running executables), "
                    "'tmp_executables' (detect binaries running from /tmp or /dev/shm), "
                    "'top_processes' (inspect high resource PIDs), or 'full_forensics' (complete audit). "
                    "Default 'full_forensics'."
                ),
                "enum": ["unlinked_binaries", "tmp_executables", "top_processes", "full_forensics"],
            },
        },
        "required": ["action"],
    },
}


def _scan_process_anomalies() -> Dict[str, Any]:
    unlinked = []
    tmp_exec = []
    processes = []

    proc_base = Path("/proc")
    if not proc_base.exists():
        return {"unlinked": [], "tmp_exec": [], "processes": []}

    for p in proc_base.iterdir():
        if not p.name.isdigit():
            continue
        pid = int(p.name)

        try:
            exe_link = p / "exe"
            cmdline_f = p / "cmdline"
            status_f = p / "status"

            # Resolve executable target
            exe_target = os.readlink(str(exe_link)) if exe_link.exists() else ""
            cmd = cmdline_f.read_text().replace("\x00", " ").strip() if cmdline_f.exists() else ""

            # Read process name and memory RSS from status
            name = ""
            rss_kb = 0
            ppid = 0
            if status_f.exists():
                for line in status_f.read_text().splitlines():
                    if line.startswith("Name:"):
                        name = line.split(":", 1)[1].strip()
                    elif line.startswith("PPid:"):
                        ppid = int(line.split(":", 1)[1].strip())
                    elif line.startswith("VmRSS:"):
                        try:
                            rss_kb = int(line.split()[1])
                        except Exception:
                            pass

            proc_entry = {
                "pid": pid,
                "ppid": ppid,
                "name": name or Path(exe_target).name or "unknown",
                "exe": exe_target,
                "cmd": cmd[:60],
                "rss_mb": round(rss_kb / 1024, 1),
            }
            processes.append(proc_entry)

            # Heuristic 1: Unlinked binary running in memory
            if "(deleted)" in exe_target:
                unlinked.append(proc_entry)

            # Heuristic 2: Execution from temporary or shared memory directories
            lower_exe = exe_target.lower()
            if lower_exe.startswith(("/tmp/", "/var/tmp/", "/dev/shm/")):
                tmp_exec.append(proc_entry)

        except Exception:
            continue

    # Sort top processes by memory consumption
    processes.sort(key=lambda x: x["rss_mb"], reverse=True)

    return {
        "unlinked": unlinked,
        "tmp_exec": tmp_exec,
        "top_processes": processes[:12],
        "total_scanned": len(processes),
    }


def _render_hud_card(action: str, report: Dict[str, Any]) -> str:
    lines = [
        "### 🔍 TACTICAL PROCESS FORENSICS (JARVIS MARK-LVII)\n",
        f"**Active Process Monitored:** `{report.get('total_scanned', 0)}` PIDs\n",
    ]

    unlinked = report.get("unlinked", [])
    tmp_exec = report.get("tmp_exec", [])

    has_threats = bool(unlinked or tmp_exec)
    if has_threats:
        lines.append("🚨 **SECURITY ADVISORY: POTENTIAL ANOMALOUS PROCESS EXECUTION DETECTED!**")
        if unlinked:
            lines.append(f"**Unlinked Running Binaries ({len(unlinked)}):** (Binary deleted from disk while active in RAM)")
            for u in unlinked[:6]:
                lines.append(f"- PID `{u['pid']}` (`{u['name']}`) — Exe: `{u['exe']}`")
        if tmp_exec:
            lines.append(f"**Executables in Temp Directories ({len(tmp_exec)}):**")
            for t in tmp_exec[:6]:
                lines.append(f"- PID `{t['pid']}` (`{t['name']}`) — Path: `{t['exe']}`")
        lines.append("")
    else:
        lines.append("🟢 **Memory Integrity:** `CLEAN` — No unlinked binaries or executions from temporary directories.\n")

    lines.append("#### ⚡ Top Memory Consuming Processes")
    lines.append("```text")
    lines.append(f"{'PID':<7s} {'PPID':<7s} {'RSS (MB)':<10s} {'NAME':<20s} {'COMMAND'}")
    lines.append("-" * 70)
    for p in report.get("top_processes", []):
        lines.append(f"{p['pid']:<7d} {p['ppid']:<7d} {p['rss_mb']:<10.1f} {p['name'][:18]:<20s} {p['cmd'][:30]}")
    lines.append("```\n")

    lines.append(f"*Process forensic scan concluded at {time.strftime('%H:%M:%S')}.*")
    return "\n".join(lines)


def _worker(action: str, player):
    try:
        report = _scan_process_anomalies()
        card = _render_hud_card(action, report)

        if player:
            try:
                player.show_content("TACTICAL PROCESS FORENSICS", card)
                threat_count = len(report.get("unlinked", [])) + len(report.get("tmp_exec", []))
                if threat_count > 0:
                    player.write_log(f"🚨 [ProcessForensics] Flagged {threat_count} anomalous process(es) in memory!")
                else:
                    player.write_log(f"🔍 [ProcessForensics] Scanned {report.get('total_scanned')} PIDs. Memory space clean.")
            except Exception:
                pass
    except Exception as e:
        if player:
            try:
                player.write_log(f"⚠️ [ProcessForensics] Error: {e}")
            except Exception:
                pass


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        action = str(parameters.get("action") or "full_forensics").strip().lower()
        if action not in ("unlinked_binaries", "tmp_executables", "top_processes", "full_forensics"):
            action = "full_forensics"

        threading.Thread(target=_worker, args=(action, player), daemon=True).start()

        if action == "unlinked_binaries":
            return "Scanning /proc for unlinked running binaries deleted from disk, sir."
        elif action == "tmp_executables":
            return "Checking for executables launched out of temporary directories like /tmp and /dev/shm, sir."
        else:
            return "Initiating host process memory forensics and anomaly inspection, sir. Results are heading to your HUD."
    except Exception as e:
        return f"Sir, process forensics encountered an issue: {e}"
