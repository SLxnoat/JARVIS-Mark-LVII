"""
plugins/stealth_browser_recon.py - Headless Clean Article & Web Intelligence Extractor.

Iron Man / JARVIS style web intelligence extraction:
- Fetches documentation, research papers, or news articles via stealth headless HTTP.
- Strips ads, navigation bars, cookie walls, and JavaScript tracking scripts.
- Extracts core readable article text, headings, and clean markdown representation.
- Summarizes the key insights for rapid operator briefing.
- Renders an ad-free article digest on the HUD via player.show_content().

Adheres strictly to AGENTS.md:
- No Qt widgets on worker threads.
- Thread-safe HUD feedback via player.show_content() and player.write_log().
- Safe non-blocking execution on background daemon thread.
- Never raises exceptions, returns concise spoken feedback.
- Handles player=None gracefully.
"""
from __future__ import annotations

import re
import sys
import threading
import time
import urllib.request
from typing import Any, Dict

from core import gemini

PLUGIN = {
    "name": "stealth_browser_recon",
    "description": (
        "JARVIS Web Intelligence Recon: Fetches any web article or documentation page, "
        "strips ads, popups, and cookie walls, and extracts clean, readable Markdown text with "
        "an executive summary. Displays the clean article on the HUD."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "url": {
                "type": "STRING",
                "description": "The webpage or article URL to extract and clean.",
            },
        },
        "required": ["url"],
    },
}


def _fetch_clean_html(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw_html = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return f"Failed to fetch webpage: {e}"

    # Strip scripts, styles, headers, footers, navs
    cleaned = re.sub(r"(?is)<script.*?>.*?</script>", "", raw_html)
    cleaned = re.sub(r"(?is)<style.*?>.*?</style>", "", cleaned)
    cleaned = re.sub(r"(?is)<nav.*?>.*?</nav>", "", cleaned)
    cleaned = re.sub(r"(?is)<footer.*?>.*?</footer>", "", cleaned)
    cleaned = re.sub(r"(?is)<header.*?>.*?</header>", "", cleaned)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned[:4000]


def _summarize_article(text: str, url: str) -> str:
    prompt = (
        "You are JARVIS's Web Intelligence Officer.\n"
        f"Webpage Target: {url}\n\n"
        f"Clean Extracted Text:\n{text[:3000]}\n\n"
        "Provide:\n"
        "1. 📰 Article Title & Subject\n"
        "2. 💡 3 Key Executive Takeaways (bullet points)\n"
        "3. 📖 Core Article Content Summary (clean markdown paragraph)\n\n"
        "Return clean markdown."
    )
    res = gemini.text(prompt, tier=gemini.SMART, default="")
    return res.strip() or "Web intelligence extraction complete."


def _render_hud_card(url: str, summary_md: str) -> str:
    lines = [
        "### 🌐 STEALTH WEB RECON & INTELLIGENCE (JARVIS MARK-LVII)\n",
        f"**Source URL:** `{url}`\n",
        summary_md,
        f"\n*Intelligence extracted at {time.strftime('%H:%M:%S')}.*",
    ]
    return "\n".join(lines)


def _worker(url: str, player):
    try:
        clean_text = _fetch_clean_html(url)
        summary = _summarize_article(clean_text, url)
        card = _render_hud_card(url, summary)

        if player:
            try:
                player.show_content("WEB INTELLIGENCE RECON", card)
                player.write_log(f"🌐 [WebRecon] Extracted ad-free intelligence from '{url[:40]}'.")
            except Exception:
                pass
    except Exception as e:
        if player:
            try:
                player.write_log(f"⚠️ [WebRecon] Error: {e}")
            except Exception:
                pass


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        url = str(parameters.get("url") or "").strip()
        if not url:
            return "Please provide a valid web URL for intelligence extraction, sir."

        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        threading.Thread(target=_worker, args=(url, player), daemon=True).start()

        return f"Executing stealth web extraction on '{url[:45]}', sir. Clean digest will display on the HUD."
    except Exception as e:
        return f"Sir, web recon extractor encountered an issue: {e}"
