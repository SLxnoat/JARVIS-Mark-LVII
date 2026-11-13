"""
plugins/ai_meeting_summarizer.py - Meeting Scribe & Action-Item Extractor.

Iron Man / JARVIS style executive intelligence:
- Analyzes meeting transcripts, rough meeting notes, or spoken discussion transcripts.
- Extracts structured executive takeaways: Key Decisions, Topic Summary, and Assigned Action Items.
- Detects deadlines, owners, and critical deliverables.
- Uses core.gemini (SMART tier) for high-fidelity executive briefing synthesis.
- Renders an executive meeting briefing card on the HUD via player.show_content().

Adheres strictly to AGENTS.md:
- No Qt widgets on worker threads.
- Thread-safe HUD feedback via player.show_content() and player.write_log().
- Safe non-blocking execution on background daemon thread.
- Never raises exceptions, returns concise spoken feedback.
- Handles player=None gracefully.
"""
from __future__ import annotations

import sys
import threading
import time
from typing import Any, Dict

from core import gemini

PLUGIN = {
    "name": "ai_meeting_summarizer",
    "description": (
        "JARVIS Meeting Scribe: Processes meeting transcripts or rough discussion notes. "
        "Extracts structured Key Decisions, Topic Summaries, and Assigned Action Items with deadlines. "
        "Displays an executive meeting card on the HUD."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "transcript_or_notes": {
                "type": "STRING",
                "description": "Meeting transcript, rough notes, or discussion points to summarize.",
            },
            "meeting_title": {
                "type": "STRING",
                "description": "Optional title or topic of the meeting (e.g. 'Sprint Planning', 'Client Sync').",
            },
        },
        "required": ["transcript_or_notes"],
    },
}


def _summarize_meeting(text: str, title: str) -> str:
    prompt = (
        "You are JARVIS's Executive Meeting Scribe.\n"
        f"Meeting Title: {title or 'Executive Discussion'}\n\n"
        f"Raw Meeting Transcript / Notes:\n{text}\n\n"
        "Generate a structured executive briefing with:\n"
        "1.  Executive Overview (2 sentences)\n"
        "2.  Key Decisions Agreed Upon (bullet points)\n"
        "3.  Action Items & Deliverables (Action, Owner, Deadline)\n"
        "4.  Blockers & Follow-Up Questions\n\n"
        "Return clean, concise markdown."
    )
    res = gemini.text(prompt, tier=gemini.SMART, default="")
    return res.strip() or "Meeting summary could not be generated."


def _render_hud_card(title: str, summary_md: str) -> str:
    lines = [
        f"###  EXECUTIVE MEETING SCRIBE: {title.upper()} (JARVIS MARK-LVII)\n",
        summary_md,
        f"\n*Executive brief transcribed at {time.strftime('%H:%M:%S')}.*",
    ]
    return "\n".join(lines)


def _worker(text: str, title: str, player):
    try:
        summary_md = _summarize_meeting(text, title)
        card = _render_hud_card(title or "Executive Brief", summary_md)

        if player:
            try:
                player.show_content("MEETING BRIEFING", card)
                player.write_log(f"[MeetingScribe] Generated executive brief for '{title or 'Discussion'}'.")
            except Exception:
                pass
    except Exception as e:
        if player:
            try:
                player.write_log(f"[MeetingScribe] Error: {e}")
            except Exception:
                pass


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        notes = str(
            parameters.get("transcript_or_notes")
            or parameters.get("transcript")
            or parameters.get("notes")
            or parameters.get("meeting_notes")
            or parameters.get("text")
            or ""
        ).strip()
        if not notes:
            return "Please provide meeting notes or a transcript for me to extract action items, sir."

        title = str(parameters.get("meeting_title") or parameters.get("title") or "Executive Discussion").strip()
        threading.Thread(target=_worker, args=(notes, title, player), daemon=True).start()

        return f"Synthesizing executive briefing and action items for '{title}', sir. Summary is on the HUD."
    except Exception as e:
        return f"Sir, meeting summarizer encountered an issue: {e}"
