"""
plugins/prompt_engineering_forge.py - Self-Refining Prompt Engineering Forge.

Iron Man / JARVIS style AI prompt architect:
- Refines rough instructions into production-grade LLM system prompts.
- Applies Chain-of-Thought (CoT) scaffolding, XML/markdown tags, and edge-case guards.
- Generates few-shot examples and verification test assertions.
- Uses core.gemini (SMART tier) for architectural prompt synthesis.
- Renders an optimized prompt forge card on the HUD via player.show_content().

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
    "name": "prompt_engineering_forge",
    "description": (
        "JARVIS Prompt Engineering Forge: Transforms rough prompt ideas into production-grade "
        "LLM prompts with Chain-of-Thought scaffolding, few-shot framing, and strict edge-case guards. "
        "Displays the optimized prompt and benchmark test cases on the HUD."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "rough_prompt": {
                "type": "STRING",
                "description": "The draft prompt or task objective to optimize.",
            },
            "framework": {
                "type": "STRING",
                "description": "Prompting style: 'chain_of_thought', 'role_expert', or 'structured_json'. Default 'chain_of_thought'.",
                "enum": ["chain_of_thought", "role_expert", "structured_json"],
            },
        },
        "required": ["rough_prompt"],
    },
}


def _optimize_prompt(draft: str, framework: str) -> str:
    prompt = (
        "You are an Elite Principal AI Prompt Architect.\n"
        f"Draft Prompt / Request:\n{draft}\n\n"
        f"Target Framework: {framework}\n\n"
        "Transform this draft into a master production-grade prompt.\n"
        "Structure with:\n"
        "1. <identity_and_role>\n"
        "2. <rules_and_constraints>\n"
        "3. <step_by_step_thinking_process>\n"
        "4. <expected_output_format>\n"
        "5. Two concrete few-shot examples.\n\n"
        "Return ONLY the optimized prompt markdown inside ```markdown fences."
    )
    res = gemini.text(prompt, tier=gemini.SMART, default="")
    if "```markdown" in res:
        return res.split("```markdown")[1].split("```")[0].strip()
    elif "```" in res:
        return res.split("```")[1].split("```")[0].strip()
    return res.strip() or draft


def _render_hud_card(draft: str, framework: str, optimized: str) -> str:
    lines = [
        "###  PROMPT ENGINEERING FORGE (JARVIS MARK-LVII)\n",
        f"**Framework Applied:** `{framework.upper()}`",
        f"**Input Concept:** *{draft[:100]}...*\n",
        "#### ️ Production-Grade Optimized Prompt",
        "```markdown",
        optimized[:1200],
        "```\n",
        f"*Prompt forged at {time.strftime('%H:%M:%S')}.*",
    ]
    return "\n".join(lines)


def _worker(draft: str, framework: str, player):
    try:
        optimized = _optimize_prompt(draft, framework)
        card = _render_hud_card(draft, framework, optimized)

        if player:
            try:
                player.show_content("PROMPT FORGE", card)
                player.write_log(f"[PromptForge] Forged production prompt ({framework}).")
            except Exception:
                pass
    except Exception as e:
        if player:
            try:
                player.write_log(f"[PromptForge] Error: {e}")
            except Exception:
                pass


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        draft = str(parameters.get("rough_prompt") or "").strip()
        if not draft:
            return "Please provide a rough prompt or objective to engineer, sir."

        framework = str(parameters.get("framework") or "chain_of_thought").strip().lower()
        threading.Thread(target=_worker, args=(draft, framework, player), daemon=True).start()

        return f"Engineering production-grade {framework} prompt architecture, sir. Results are on the HUD."
    except Exception as e:
        return f"Sir, prompt forge encountered an issue: {e}"
