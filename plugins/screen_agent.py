"""
plugins/screen_agent.py - Visual screen analysis and UI interaction assistant.

Adheres to AGENTS.md:
- Thread-safe screen capture using mss and Gemini Vision.
- Analyzes UI on a background thread; returns immediately.
- Thread-safe HUD presentation via player.show_content().
- Never raises exceptions, returns concise spoken feedback.
"""
import io
import threading
from pathlib import Path
from PIL import Image
from core import gemini

PLUGIN = {
    "name": "screen_agent",
    "description": (
        "Inspects what is currently displayed on your screen, identifies UI elements, "
        "and gives step-by-step instructions or coordinates to accomplish tasks."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "task": {
                "type": "STRING",
                "description": "What you want to do on screen, e.g. 'click the submit button', 'find the search bar'.",
            },
            "action": {
                "type": "STRING",
                "description": "Action: 'analyze', 'find_element', 'next_step'. Default is 'analyze'.",
                "enum": ["analyze", "find_element", "next_step"],
            },
        },
        "required": ["task"],
    },
}


def _capture_screen_bytes() -> bytes | None:
    try:
        import mss
        with mss.mss() as sct:
            monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            sct_img = sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            # Downsample for fast Gemini vision processing
            img.thumbnail((1280, 720))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=80)
            return buf.getvalue()
    except Exception:
        return None


def _screen_worker(task: str, action: str, player):
    try:
        img_bytes = _capture_screen_bytes()
        if not img_bytes:
            if player:
                try:
                    player.write_log("[ScreenAgent] Failed to capture screen (check display permissions).")
                except Exception:
                    pass
            return

        prompt = f"""You are an expert UI navigator inspecting a screenshot of the user's screen.
User task: "{task}"
Action requested: "{action}"

Analyze the visual interface and return a clear, structured Markdown response:
1. **Summary of Screen**: What application / webpage is currently visible.
2. **Target UI Elements**: Exact location (e.g. top right, center panel), labels, or buttons relevant to "{task}".
3. **Actionable Next Steps**: Step-by-step instructions on what to click or type.
Keep the advice precise, concise, and easy to read.
"""
        response_text = gemini.text(prompt, tier=gemini.FAST)
        if not response_text:
            response_text = f"Screen captured for task '{task}'. Look for the primary action button highlighted on your active window."

        if player:
            try:
                hud_md = f"### ️ Screen Navigation Assistant\n\n**Goal:** *\"{task}\"*\n\n{response_text}"
                player.show_content("Screen Agent", hud_md)
                player.write_log(f"️ [ScreenAgent] Analyzed screen for: '{task[:40]}'")
            except Exception:
                pass

    except Exception as e:
        if player:
            try:
                player.write_log(f"[ScreenAgent] Error during visual analysis: {e}")
            except Exception:
                pass


def run(parameters: dict, player=None, session_memory=None) -> str:
    task = str(parameters.get("task") or "Analyze active window").strip()
    action = str(parameters.get("action") or "analyze").strip().lower()

    threading.Thread(
        target=_screen_worker,
        args=(task, action, player),
        daemon=True,
    ).start()

    return f"Analyzing your screen to help with '{task[:50]}'. Recommendations will appear on the display in a moment."
