"""
plugins/skill_loader.py - Progressive disclosure skill manager for JARVIS.

Follows Anthropic & Hermes Agent standards (anthropics/skills):
- Progressive disclosure: list short metadata (~30 tokens) on demand
- Full instruction body is only loaded when an action requires specialized procedures
- Thread-safe HUD feedback via player
- Never raises exceptions
"""
import os
import re
from pathlib import Path

PLUGIN = {
    "name": "skill_loader",
    "description": (
        "Progressive skill manager. Lists available skills or loads specialized, "
        "step-by-step instructions for debugging, TDD, codebase inspection, computer use, etc."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action to perform: 'list' (index of all skills) or 'read' (fetch full skill procedure).",
                "enum": ["list", "read"],
            },
            "skill_name": {
                "type": "STRING",
                "description": "The exact name of the skill to read (e.g., 'systematic-debugging', 'test-driven-development'). Required if action is 'read'.",
            },
        },
        "required": ["action"],
    },
}

_BASE_DIR = Path(__file__).resolve().parent.parent
_SKILLS_DIR = _BASE_DIR / "skills"


def _parse_frontmatter(content: str) -> dict:
    meta = {}
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1]
            for line in fm_text.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and not k.startswith("#"):
                        meta[k] = v
    return meta


def _list_skills() -> str:
    if not _SKILLS_DIR.exists():
        return "No skills directory found."

    skills = []
    for skill_file in sorted(_SKILLS_DIR.rglob("SKILL.md")):
        try:
            rel_path = skill_file.relative_to(_SKILLS_DIR)
            category = rel_path.parts[0] if len(rel_path.parts) > 1 else "general"
            text = skill_file.read_text(encoding="utf-8", errors="replace")
            meta = _parse_frontmatter(text)
            name = meta.get("name", skill_file.parent.name)
            desc = meta.get("description", "No description provided.")
            skills.append((category, name, desc))
        except Exception:
            continue

    if not skills:
        return "No skills found in repository."

    lines = ["Available JARVIS Skills (Anthropic / Hermes Standard):"]
    current_cat = None
    for cat, name, desc in skills:
        if cat != current_cat:
            lines.append(f"\n[{cat.upper()}]")
            current_cat = cat
        lines.append(f"  • {name}: {desc}")

    lines.append("\nUse skill_loader(action='read', skill_name='<name>') to load full procedure instructions.")
    return "\n".join(lines)


def _read_skill(skill_name: str) -> str:
    target = skill_name.strip().lower()
    if not _SKILLS_DIR.exists():
        return f"Error: Skills directory not found."

    for skill_file in _SKILLS_DIR.rglob("SKILL.md"):
        try:
            text = skill_file.read_text(encoding="utf-8", errors="replace")
            meta = _parse_frontmatter(text)
            name = meta.get("name", skill_file.parent.name).lower()
            if name == target or skill_file.parent.name.lower() == target:
                # Strip frontmatter for direct instruction reading
                if text.startswith("---"):
                    parts = text.split("---", 2)
                    if len(parts) >= 3:
                        text = parts[2].strip()
                return text
        except Exception as e:
            return f"Error reading skill {skill_name}: {e}"

    return f"Skill '{skill_name}' not found. Call skill_loader(action='list') to view available skills."


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "list").strip().lower()
    skill_name = str(parameters.get("skill_name") or "").strip()

    if action == "read":
        if not skill_name:
            return "Please specify the skill_name to read."
        content = _read_skill(skill_name)
        if player:
            try:
                player.write_log(f"🧠 [SkillLoader] Loaded skill: {skill_name}")
                summary = content[:300].replace("\n", " ") + "..."
                player.show_content(f"Skill: {skill_name}", content[:4000])
            except Exception:
                pass
        return content
    else:
        index_text = _list_skills()
        if player:
            try:
                player.write_log("📚 [SkillLoader] Indexed repository skills.")
                player.show_content("JARVIS Skills Index", index_text)
            except Exception:
                pass
        return index_text
