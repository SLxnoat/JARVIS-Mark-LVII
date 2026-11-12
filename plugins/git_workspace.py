"""
plugins/git_workspace.py — Local Git repository & workspace inspector for JARVIS.

Inspects branches, detects uncommitted modifications, displays recent commit histories,
and scans workspace directories for uncommitted changes. Zero external dependencies.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

_BASE_DIR = Path(__file__).resolve().parent.parent

PLUGIN = {
    "name": "git_workspace",
    "description": (
        "Inspect and check local Git repositories across your workspace. "
        "Can check the current branch and uncommitted files ('status'), "
        "view recent commit history ('commits'), summarize uncommitted line changes ('diff'), "
        "or scan all workspace projects for uncommitted files ('scan'). "
        "Use this tool when the user asks about git status, commits, branches, or uncommitted work."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action to run: 'status', 'commits', 'diff', 'scan'",
            },
            "path": {
                "type": "STRING",
                "description": "Optional repository path or project directory. Defaults to the current project.",
            },
        },
        "required": [],
    },
}


def _run_git(cmd: list[str], cwd: Path, timeout: int = 4) -> tuple[int, str]:
    try:
        r = subprocess.run(
            ["git"] + cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return r.returncode, (r.stdout or r.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return -1, "Git command timed out."
    except Exception as e:
        return -1, str(e)


def run(parameters: dict, player: Any = None, session_memory: Any = None) -> str:
    action = str(parameters.get("action", "status")).strip().lower()
    target_path = parameters.get("path", "")
    repo_dir = Path(target_path).resolve() if target_path else _BASE_DIR

    if not (repo_dir / ".git").exists() and action != "scan":
        # Check parent or current directory
        if not (repo_dir / ".git").exists():
            return f"The directory {repo_dir.name} is not a valid Git repository, Sir."

    try:
        if action == "commits":
            code, out = _run_git(["log", "-n", "5", "--oneline"], repo_dir)
            if code != 0 or not out:
                return f"Could not retrieve commit history for {repo_dir.name}."

            lines = out.splitlines()
            top_commit = lines[0] if lines else "None"
            msg = f"Last commit in {repo_dir.name} is {top_commit}. Showing the 5 latest commits on your screen."
            if player and hasattr(player, "show_content"):
                player.show_content(f"Git Commits: {repo_dir.name}", "\n".join(f"• {c}" for c in lines))
            return msg

        elif action == "diff":
            code, out = _run_git(["diff", "--stat"], repo_dir)
            if not out:
                return f"No unstaged line modifications in {repo_dir.name}. Working tree is clean."

            lines = out.splitlines()
            summary_line = lines[-1] if lines else ""
            msg = f"Unstaged changes in {repo_dir.name}: {summary_line}."
            if player and hasattr(player, "show_content"):
                player.show_content(f"Git Diff Stat: {repo_dir.name}", out)
            return msg

        elif action == "scan":
            # Search parent directory for sibling git repositories
            parent = repo_dir.parent
            dirty_repos = []
            clean_repos = []

            for folder in parent.iterdir():
                if folder.is_dir() and (folder / ".git").exists():
                    code, out = _run_git(["status", "-s"], folder, timeout=2)
                    code_b, branch = _run_git(["branch", "--show-current"], folder, timeout=2)
                    bname = branch.strip() or "detached"
                    if out:
                        count = len(out.splitlines())
                        dirty_repos.append(f"{folder.name} ({bname}): {count} uncommitted file{'s' if count > 1 else ''}")
                    else:
                        clean_repos.append(f"{folder.name} ({bname})")

            if dirty_repos:
                msg = f"Scanned workspace. {len(dirty_repos)} project{'s have' if len(dirty_repos) > 1 else ' has'} uncommitted changes: {', '.join(dirty_repos)}."
            else:
                msg = f"All {len(clean_repos)} repositories in your workspace are clean and committed."

            if player and hasattr(player, "show_content"):
                report = "📁 Dirty Repositories:\n" + ("\n".join(f"• {r}" for r in dirty_repos) if dirty_repos else "None")
                report += "\n\n✅ Clean Repositories:\n" + ("\n".join(f"• {r}" for r in clean_repos) if clean_repos else "None")
                player.show_content("Workspace Git Scan", report)
            return msg

        else:  # Default: 'status'
            code_b, branch = _run_git(["branch", "--show-current"], repo_dir)
            branch = branch.strip() or "main"

            code_s, status_out = _run_git(["status", "-s"], repo_dir)
            files = [l.strip() for l in status_out.splitlines() if l.strip()] if status_out else []

            code_u, upstream = _run_git(["status", "-uno"], repo_dir)
            sync_info = "up to date with remote"
            if "ahead" in upstream:
                sync_info = "ahead of remote (commits pending push)"
            elif "behind" in upstream:
                sync_info = "behind remote (needs pull)"

            if files:
                count = len(files)
                msg = f"Repository {repo_dir.name} is on branch '{branch}', {sync_info}, with {count} uncommitted file{'s' if count > 1 else ''}."
            else:
                msg = f"Repository {repo_dir.name} is on branch '{branch}', {sync_info}. Working tree is completely clean."

            if player and hasattr(player, "show_content"):
                content = f"Branch: {branch}\nStatus: {sync_info}\n\nUncommitted files:\n"
                content += "\n".join(f"• {f}" for f in files[:20]) if files else "None (clean)"
                player.show_content(f"Git Status: {repo_dir.name}", content)
            return msg

    except Exception as e:
        return f"Could not check Git status: {e}"
