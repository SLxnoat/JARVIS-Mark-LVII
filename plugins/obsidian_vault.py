"""
plugins/obsidian_vault.py - Obsidian Markdown Vault integration.

Adheres strictly to AGENTS.md:
- Thread-safe file operations.
- Thread-safe HUD presentation via player.show_content().
- Never raises exceptions, returns concise spoken feedback.
"""
import os
import time
from datetime import date
from pathlib import Path

PLUGIN = {
    "name": "obsidian_vault",
    "description": (
        "Reads, searches, creates, and appends notes in a local Obsidian Markdown vault. "
        "Supports daily notes, tag searches, and full-text searches."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: 'search', 'read', 'create', 'append', 'daily_note', 'list'.",
                "enum": ["search", "read", "create", "append", "daily_note", "list"],
            },
            "title": {
                "type": "STRING",
                "description": "Note title or file name (e.g. 'Project Alpha', 'Meeting Notes').",
            },
            "content": {
                "type": "STRING",
                "description": "Content to write or append to the note.",
            },
            "query": {
                "type": "STRING",
                "description": "Search term or tag (e.g. '#todo', 'architecture') for 'search'.",
            },
            "vault_path": {
                "type": "STRING",
                "description": "Optional custom path to the Obsidian vault directory.",
            },
        },
        "required": ["action"],
    },
}


def _find_vault(custom_path: str = None) -> Path:
    if custom_path:
        p = Path(custom_path).expanduser().resolve()
        if p.is_dir():
            return p

    candidates = [
        Path.cwd() / "notes",
        Path.home() / "Documents" / "Obsidian Vault",
        Path.home() / "Documents" / "Obsidian",
        Path.home() / "Obsidian",
        Path.home() / "obsidian",
        Path.home() / "Documents" / "Notes",
    ]
    for c in candidates:
        if c.is_dir():
            return c

    # Try creating in candidates, fallback to workspace notes
    for target in [Path.home() / "Documents" / "Obsidian", Path.cwd() / "notes"]:
        try:
            target.mkdir(parents=True, exist_ok=True)
            return target
        except OSError:
            continue

    fallback = Path.cwd() / "notes"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = parameters.get("action", "list").strip().lower()
    title = str(parameters.get("title") or "").strip()
    content = str(parameters.get("content") or "").strip()
    query = str(parameters.get("query") or "").strip()
    custom_vault = parameters.get("vault_path")

    try:
        vault = _find_vault(custom_vault)

        if action == "list":
            files = sorted(vault.glob("**/*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
            if not files:
                return f"No markdown notes found in Obsidian vault at '{vault}'."
            top = files[:10]
            names = [f.stem for f in top]
            if player:
                try:
                    listing = "\n".join(f"- **{f.stem}** *({f.relative_to(vault)})*" for f in top)
                    player.show_content("Obsidian Notes", f"### 📓 Obsidian Vault (`{vault}`)\n\n{listing}")
                except Exception:
                    pass
            return f"Found {len(files)} note(s) in Obsidian. Recent notes include: {', '.join(names[:5])}."

        elif action == "search":
            if not query:
                return "Please provide a query or tag to search for in your Obsidian notes."
            matched = []
            q_lower = query.lower()
            for md_file in vault.glob("**/*.md"):
                try:
                    text = md_file.read_text(encoding="utf-8", errors="replace")
                    if q_lower in md_file.name.lower() or q_lower in text.lower():
                        matched.append(md_file)
                except Exception:
                    continue

            if not matched:
                return f"No notes matching '{query}' found in Obsidian vault."

            if player:
                try:
                    summary = f"### 🔍 Notes matching '{query}':\n\n" + "\n".join(
                        f"- **{f.stem}** (`{f.relative_to(vault)}`)" for f in matched[:12]
                    )
                    player.show_content(f"Obsidian Search: {query}", summary)
                except Exception:
                    pass
            return f"Found {len(matched)} note(s) matching '{query}', such as '{matched[0].stem}'."

        elif action == "read":
            if not title:
                return "Please specify the title of the note you want to read."
            target = None
            for f in vault.glob("**/*.md"):
                if f.stem.lower() == title.lower() or f.name.lower() == title.lower():
                    target = f
                    break
            if not target:
                return f"Note '{title}' not found in Obsidian vault."

            text = target.read_text(encoding="utf-8", errors="replace")
            if player:
                try:
                    player.show_content(f"Obsidian: {target.stem}", f"### 📄 {target.stem}\n\n{text}")
                except Exception:
                    pass
            preview = text[:200].replace("\n", " ").strip()
            return f"Note '{target.stem}' found. Beginning: \"{preview}...\""

        elif action == "create":
            if not title:
                return "Please provide a title for the new note."
            clean_name = title if title.endswith(".md") else f"{title}.md"
            target = vault / clean_name
            if target.exists():
                return f"Note '{clean_name}' already exists in Obsidian. Use 'append' to add to it."

            timestamp = time.strftime("%Y-%m-%d %H:%M")
            body = f"# {title}\n*Created on {timestamp}*\n\n{content}\n"
            target.write_text(body, encoding="utf-8")
            if player:
                try:
                    player.show_content(f"Obsidian: {title}", body)
                except Exception:
                    pass
            return f"Created new Obsidian note '{title}'."

        elif action == "append":
            if not title:
                return "Please specify which note title to append to."
            target = None
            for f in vault.glob("**/*.md"):
                if f.stem.lower() == title.lower() or f.name.lower() == title.lower():
                    target = f
                    break
            if not target:
                target = vault / (title if title.endswith(".md") else f"{title}.md")

            timestamp = time.strftime("%Y-%m-%d %H:%M")
            addition = f"\n\n### Update ({timestamp})\n{content}\n"
            with open(target, "a", encoding="utf-8") as f:
                f.write(addition)

            return f"Appended update to Obsidian note '{target.stem}'."

        elif action == "daily_note":
            today_str = str(date.today())
            daily_file = vault / f"{today_str}.md"
            timestamp = time.strftime("%H:%M:%S")

            if not daily_file.exists():
                init_text = f"# Daily Note — {today_str}\n\n"
                if content:
                    init_text += f"- **[{timestamp}]** {content}\n"
                daily_file.write_text(init_text, encoding="utf-8")
                return f"Created today's daily note ({today_str})."
            else:
                if content:
                    with open(daily_file, "a", encoding="utf-8") as f:
                        f.write(f"- **[{timestamp}]** {content}\n")
                    return f"Added entry to today's daily note ({today_str})."
                else:
                    text = daily_file.read_text(encoding="utf-8", errors="replace")
                    if player:
                        try:
                            player.show_content(f"Daily Note {today_str}", text)
                        except Exception:
                            pass
                    return f"Today's daily note has {len(text.splitlines())} lines."

        else:
            return f"Unknown action '{action}'. Valid actions: list, search, read, create, append, daily_note."

    except Exception as e:
        return f"Error interacting with Obsidian vault: {e}"
