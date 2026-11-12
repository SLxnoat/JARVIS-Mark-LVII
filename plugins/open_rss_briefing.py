"""
plugins/open_rss_briefing.py — Free, open-source RSS/Atom tech & developer news aggregator for JARVIS.

Pulls headline intelligence from Hacker News, ArXiv AI, Linux Foundation, and tech feeds
without requiring any API keys, credentials, or paid subscriptions.
"""
from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from typing import Any

import httpx

FEEDS = {
    "tech": "https://news.ycombinator.com/rss",
    "ai": "https://rss.arxiv.org/rss/cs.AI",
    "linux": "https://www.kernel.org/feeds/kdist.xml",
    "security": "https://feeds.feedburner.com/TheHackersNews",
}

PLUGIN = {
    "name": "open_rss_briefing",
    "description": (
        "Fetch and summarize the latest tech, AI, security, or Linux developer news from free, open RSS feeds. "
        "Can fetch Hacker News ('tech'), ArXiv AI research ('ai'), or cybersecurity ('security'). "
        "Use this tool when the user asks for tech headlines, developer news, or what is trending on Hacker News."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "category": {
                "type": "STRING",
                "description": "Category to fetch: 'tech' (Hacker News), 'ai' (ArXiv papers), 'security', 'linux'",
            },
            "limit": {
                "type": "INTEGER",
                "description": "Number of stories to return (default 3, max 6)",
            },
        },
        "required": [],
    },
}


def _strip_tags(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", text or "")
    return " ".join(html.unescape(cleaned).split()).strip()


def run(parameters: dict, player: Any = None, session_memory: Any = None) -> str:
    raw_cat = str(parameters.get("category") or parameters.get("topic") or parameters.get("feed") or parameters.get("action") or "tech").strip().lower()
    if "ai" in raw_cat or "arxiv" in raw_cat:
        cat = "ai"
    elif "sec" in raw_cat or "hack" in raw_cat:
        cat = "security"
    elif "linux" in raw_cat or "kernel" in raw_cat:
        cat = "linux"
    else:
        cat = "tech"
    limit = min(6, max(1, int(parameters.get("limit", 3))))
    url = FEEDS.get(cat, FEEDS["tech"])

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) JARVIS-OpenRSS/1.0",
        "Accept": "application/rss+xml, application/xml, text/xml",
    }

    try:
        resp = httpx.get(url, headers=headers, timeout=6.0, follow_redirects=True)
        if resp.status_code != 200:
            return f"Could not reach the {cat} news feed (HTTP {resp.status_code})."

        root = ET.fromstring(resp.text)
        stories = []

        # Parse standard RSS 2.0 (<channel><item>)
        items = root.findall(".//item")
        if not items:
            # Try Atom 1.0 (<feed><entry>)
            items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

        for item in items[:limit]:
            title_node = item.find("title")
            if title_node is None:
                title_node = item.find("{http://www.w3.org/2005/Atom}title")
            title = _strip_tags(title_node.text) if title_node is not None and title_node.text else "Untitled"

            desc_node = item.find("description")
            if desc_node is None:
                desc_node = item.find("{http://www.w3.org/2005/Atom}summary")
            desc = _strip_tags(desc_node.text)[:160] if desc_node is not None and desc_node.text else ""

            link_node = item.find("link")
            if link_node is None:
                link_node = item.find("{http://www.w3.org/2005/Atom}link")
            link = link_node.text if link_node is not None and link_node.text else (link_node.get("href") if link_node is not None else "")

            stories.append({"title": title, "desc": desc, "link": link})

        if not stories:
            return f"No headlines found in the {cat} RSS feed, Sir."

        # Spoken summary
        top_titles = [s["title"] for s in stories[:3]]
        speech = f"Top {cat.title()} stories: 1. {top_titles[0]}. 2. {top_titles[1]}." if len(top_titles) >= 2 else f"Top story: {top_titles[0]}."

        if player and hasattr(player, "show_content"):
            content_lines = []
            for i, s in enumerate(stories, 1):
                content_lines.append(f"**{i}. {s['title']}**")
                if s["desc"]:
                    content_lines.append(f"   _{s['desc']}_")
                if s["link"]:
                    content_lines.append(f"   [Read Source]({s['link']})\n")
            player.show_content(f"📰 {cat.title()} News Digest", "\n".join(content_lines))

        return speech

    except Exception as e:
        return f"Unable to fetch RSS briefing: {e}"
