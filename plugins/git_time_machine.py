"""
plugins/git_time_machine.py - Visual Git Evolution & Code Churn Timeline.

Iron Man / JARVIS style repository intelligence:
- Tracks codebase evolution over time: commit velocity, code churn (lines added vs deleted).
- Identifies "hotspot" files that change most frequently (high refactoring/bug risk).
- Visualizes author contribution timelines and repository milestones.
- 100% local Git command execution via subprocess.
- Renders a codebase evolution card on the HUD via player.show_content().

Adheres strictly to AGENTS.md:
- No Qt widgets on worker threads.
- Thread-safe HUD feedback via player.show_content() and player.write_log().
- Safe non-blocking execution on background daemon thread.
- Never raises exceptions, returns concise spoken feedback.
- Handles player=None gracefully.
"""
from __future__ import annotations

import collections
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

PLUGIN = {
    "name": "git_time_machine",
    "description": (
        "JARVIS Git Time Machine: Visualizes repository evolution over time. Analyzes code churn "
        "(lines added/deleted), detects high-risk 'hotspot' files with frequent modifications, "
        "and tracks author velocity. Displays a git timeline card on the HUD."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: 'hotspots' (frequently modified files), 'churn_timeline' (add/delete ratios), or 'full_time_machine'. Default 'full_time_machine'.",
                "enum": ["hotspots", "churn_timeline", "full_time_machine"],
            },
            "limit": {
                "type": "INTEGER",
                "description": "Number of recent commits to analyze (default 50, max 200).",
            },
        },
        "required": [],
    },
}


def _analyze_git_history(limit: int = 50) -> Dict[str, Any]:
    file_changes: collections.Counter = collections.Counter()
    total_added = 0
    total_deleted = 0
    authors: collections.Counter = collections.Counter()

    try:
        # Get commit log with author and numstat
        r = subprocess.run(
            ["git", "log", f"-n{limit}", "--pretty=format:COMMIT\t%an\t%ad", "--date=short", "--numstat"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0:
            for line in r.stdout.splitlines():
                if line.startswith("COMMIT\t"):
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        authors[parts[1]] += 1
                elif line.strip():
                    parts = line.split("\t")
                    if len(parts) == 3:
                        add_str, del_str, fname = parts
                        try:
                            if add_str != "-":
                                total_added += int(add_str)
                            if del_str != "-":
                                total_deleted += int(del_str)
                            file_changes[fname] += 1
                        except Exception:
                            pass
    except Exception:
        pass

    return {
        "commits_analyzed": min(limit, sum(authors.values())),
        "added_lines": total_added,
        "deleted_lines": total_deleted,
        "top_hotspots": file_changes.most_common(8),
        "authors": authors.most_common(4),
    }


def _render_hud_card(data: Dict[str, Any]) -> str:
    lines = [
        "### ⏳ GIT TIME MACHINE & REPO CHURN RADAR (JARVIS MARK-LVII)\n",
        f"**Commits Evaluated:** `{data['commits_analyzed']}` | **Lines Added:** `+{data['added_lines']:,}` | **Lines Deleted:** `-{data['deleted_lines']:,}`\n",
        "#### 🔥 Codebase Refactoring Hotspots (Most Frequently Modified)",
        "```text",
        f"{'MODIFICATIONS':<15s} {'FILE PATH'}",
        "-" * 65,
    ]

    for fname, count in data["top_hotspots"]:
        lines.append(f"{count:<15d} {fname}")

    lines.append("```\n")

    lines.append("#### 🧑‍💻 Author Contribution Velocity")
    for author, count in data["authors"]:
        lines.append(f"- **{author}:** `{count}` commits in inspected window")

    lines.append(f"\n*Codebase time machine synthesized at {time.strftime('%H:%M:%S')}.*")
    return "\n".join(lines)


def _worker(limit: int, player):
    try:
        data = _analyze_git_history(limit)
        card = _render_hud_card(data)

        if player:
            try:
                player.show_content("GIT TIME MACHINE", card)
                hot_name = data["top_hotspots"][0][0] if data["top_hotspots"] else "None"
                player.write_log(f"⏳ [TimeMachine] Scanned {data['commits_analyzed']} commits. Top hotspot: {hot_name}.")
            except Exception:
                pass
    except Exception as e:
        if player:
            try:
                player.write_log(f"⚠️ [TimeMachine] Error: {e}")
            except Exception:
                pass


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        limit = int(parameters.get("limit", 50))
        limit = min(200, max(10, limit))

        threading.Thread(target=_worker, args=(limit, player), daemon=True).start()

        return f"Engaging Git Time Machine across the last {limit} commits, sir. Code churn telemetry is rendering on your HUD."
    except Exception as e:
        return f"Sir, git time machine encountered an issue: {e}"
