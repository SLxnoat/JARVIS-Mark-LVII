"""
plugins/code_debugger_sandbox.py - In-Memory Self-Repairing Code Execution Sandbox.

Iron Man / JARVIS style autonomous code engineering:
- Executes Python scripts in an isolated, timeout-guarded subprocess sandbox.
- Intercepts tracebacks (SyntaxError, NameError, TypeError, IndexError).
- Uses core.gemini in an autonomous self-healing loop: analyzes the error, patches code, and re-runs.
- Tracks execution output, return codes, and iterative repairs.
- Renders an autonomous debugging timeline on the HUD via player.show_content().

Adheres strictly to AGENTS.md:
- No Qt widgets on worker threads.
- Thread-safe HUD feedback via player.show_content() and player.write_log().
- Safe non-blocking execution on background daemon thread.
- Never raises exceptions, returns concise spoken feedback.
- Handles player=None gracefully.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

from core import gemini

PLUGIN = {
    "name": "code_debugger_sandbox",
    "description": (
        "JARVIS Autonomous Code Sandbox: Executes Python snippets in an isolated sandbox. "
        "Intercepts runtime tracebacks and autonomously patches and repairs code errors "
        "in a self-healing loop. Renders the execution trace and repaired code on the HUD."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "code": {
                "type": "STRING",
                "description": "Python code snippet to execute, debug, and self-repair.",
            },
            "max_repair_attempts": {
                "type": "INTEGER",
                "description": "Maximum autonomous self-repair attempts if errors occur (default 2, max 3).",
            },
        },
        "required": ["code"],
    },
}


def _execute_snippet(code: str, timeout: int = 5) -> Tuple[int, str, str]:
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code)
        temp_path = f.name

    try:
        r = subprocess.run(
            [sys.executable, temp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Execution timed out (5s limit exceeded)."
    except Exception as e:
        return -1, "", str(e)
    finally:
        try:
            Path(temp_path).unlink(missing_ok=True)
        except Exception:
            pass


def _repair_code_with_gemini(original_code: str, stderr: str) -> str | None:
    prompt = (
        "You are JARVIS's Autonomous Python Code Repair Engine.\n"
        f"Original Code:\n```python\n{original_code}\n```\n\n"
        f"Execution Traceback Error:\n```text\n{stderr}\n```\n\n"
        "Fix the code cleanly. Output ONLY the repaired Python code within markdown ```python fences. "
        "Do not include conversational preamble."
    )
    resp = gemini.text(prompt, tier=gemini.SMART, default="")
    if "```python" in resp:
        return resp.split("```python")[1].split("```")[0].strip()
    elif "```" in resp:
        return resp.split("```")[1].split("```")[0].strip()
    return resp.strip() if resp else None


def _render_hud_card(
    initial_code: str,
    final_code: str,
    stdout: str,
    stderr: str,
    repairs_done: int,
    success: bool,
) -> str:
    status_badge = "EXECUTION SUCCESSFUL 🟢" if success else "EXECUTION FAILED 🔴"
    lines = [
        "### ⚡ AUTONOMOUS CODE DEBUGGER & SANDBOX (JARVIS MARK-LVII)\n",
        f"**Sandbox Status:** `{status_badge}`",
        f"**Self-Repair Iterations:** `{repairs_done}`\n",
        "#### 🖥️ Sandbox Execution Output (stdout)",
    ]

    if stdout.strip():
        lines.append("```text")
        lines.append(stdout.strip()[:600])
        lines.append("```\n")
    else:
        lines.append("- *(No standard output produced)*\n")

    if stderr.strip() and not success:
        lines.append("#### ⚠️ Unresolved Traceback (stderr)")
        lines.append("```text")
        lines.append(stderr.strip()[:400])
        lines.append("```\n")

    if repairs_done > 0:
        lines.append("#### 🛠️ Repaired Python Code")
        lines.append("```python")
        lines.append(final_code[:600])
        lines.append("```\n")

    lines.append(f"*Sandbox completed at {time.strftime('%H:%M:%S')}.*")
    return "\n".join(lines)


def _worker(code: str, max_repairs: int, player):
    try:
        current_code = code
        repairs_done = 0
        success = False
        last_stdout = ""
        last_stderr = ""

        for attempt in range(max_repairs + 1):
            ret, stdout, stderr = _execute_snippet(current_code)
            last_stdout = stdout
            last_stderr = stderr

            if ret == 0:
                success = True
                break

            if attempt < max_repairs:
                if player:
                    try:
                        player.write_log(f"⚡ [Sandbox] Intercepted traceback on attempt {attempt + 1}. Auto-repairing via Gemini...")
                    except Exception:
                        pass
                repaired = _repair_code_with_gemini(current_code, stderr)
                if repaired:
                    current_code = repaired
                    repairs_done += 1
                else:
                    break

        card = _render_hud_card(code, current_code, last_stdout, last_stderr, repairs_done, success)

        if player:
            try:
                player.show_content("AUTONOMOUS CODE SANDBOX", card)
                res_tag = "Passed" if success else "Failed"
                player.write_log(f"⚡ [Sandbox] Execution finished: {res_tag} ({repairs_done} repairs).")
            except Exception:
                pass
    except Exception as e:
        if player:
            try:
                player.write_log(f"⚠️ [Sandbox] Error: {e}")
            except Exception:
                pass


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        code = str(parameters.get("code") or "").strip()
        if not code:
            return "Please provide Python code to execute and debug in the sandbox, sir."

        max_rep = int(parameters.get("max_repair_attempts", 2))
        max_rep = min(3, max(0, max_rep))

        threading.Thread(target=_worker, args=(code, max_rep, player), daemon=True).start()

        return "Executing code in isolated sandbox with autonomous self-healing error recovery, sir. Trace is on the HUD."
    except Exception as e:
        return f"Sir, code debugger sandbox encountered an issue: {e}"
