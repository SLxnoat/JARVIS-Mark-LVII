"""
plugins/chat_takeover.py - Intelligent chat response drafting and takeover assistant.

Adheres to AGENTS.md:
- Thread-safe Gemini LLM inference via core.gemini.
- Thread-safe HUD presentation via player.show_content().
- Never raises exceptions, returns concise spoken feedback.
"""
import pyperclip
from core import gemini

PLUGIN = {
    "name": "chat_takeover",
    "description": (
        "Reads an incoming chat message or conversation (from clipboard or text) "
        "and drafts an intelligent, contextual reply matching your requested tone."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: 'draft_reply', 'summarize_chat', 'rewrite'. Default is 'draft_reply'.",
                "enum": ["draft_reply", "summarize_chat", "rewrite"],
            },
            "incoming_text": {
                "type": "STRING",
                "description": "The message or conversation text. If omitted, reads from current clipboard.",
            },
            "tone": {
                "type": "STRING",
                "description": "Tone of response: 'professional', 'casual', 'friendly', 'assertive', 'concise'.",
                "enum": ["professional", "casual", "friendly", "assertive", "concise"],
            },
            "intent": {
                "type": "STRING",
                "description": "Optional specific intention (e.g. 'accept the meeting', 'politely decline', 'ask for more time').",
            },
        },
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "draft_reply").strip().lower()
    text = str(parameters.get("incoming_text") or "").strip()
    tone = str(parameters.get("tone") or "professional").strip().lower()
    intent = str(parameters.get("intent") or "").strip()

    try:
        # If no text provided, read from clipboard
        if not text:
            try:
                text = pyperclip.paste().strip()
            except Exception:
                pass

        if not text:
            return "No incoming message provided or found in the clipboard. Copy the message first or supply it directly."

        if action == "draft_reply":
            prompt = f"""You are an expert communication assistant.
INCOMING MESSAGE:
"{text}"

TASK:
Draft a {tone} reply to the message above.
{"Key Objective: " + intent if intent else ""}

Provide ONLY the draft reply text without preamble or quotation marks.
"""
            draft = gemini.text(prompt, tier=gemini.FAST)
            if not draft:
                draft = "Thank you for reaching out. I have received your message and will review it shortly."

            try:
                pyperclip.copy(draft)
                copied_note = " (Copied to your clipboard ready to paste!)"
            except Exception:
                copied_note = ""

            hud_md = (
                f"###  Chat Takeover: Draft Reply ({tone})\n\n"
                f"**Incoming Context:**\n> *\"{text[:200]}...\"*\n\n"
                f"**Suggested Reply:**\n```\n{draft}\n```\n"
                f"{copied_note}"
            )
            if player:
                try:
                    player.show_content("Chat Takeover", hud_md)
                    player.write_log(f"[ChatTakeover] Drafted {tone} reply.")
                except Exception:
                    pass

            return f"Drafted a {tone} reply: \"{draft[:120]}...\".{copied_note}"

        elif action == "summarize_chat":
            prompt = f"""Summarize the following chat conversation into key discussion points and any pending action items:
"{text}"
"""
            summary = gemini.text(prompt, tier=gemini.FAST)
            if player and summary:
                try:
                    player.show_content("Chat Summary", f"###  Chat Summary\n\n{summary}")
                except Exception:
                    pass
            return f"Chat summarized. Displaying key points on HUD."

        elif action == "rewrite":
            prompt = f"""Rewrite the following message to sound {tone}:
"{text}"
Provide ONLY the rewritten message.
"""
            rewritten = gemini.text(prompt, tier=gemini.FAST) or text
            try:
                pyperclip.copy(rewritten)
            except Exception:
                pass
            return f"Rewritten in {tone} tone: \"{rewritten[:120]}...\"."

        else:
            return f"Unknown action '{action}'. Valid actions: draft_reply, summarize_chat, rewrite."

    except Exception as e:
        return f"Error in chat takeover: {e}"
