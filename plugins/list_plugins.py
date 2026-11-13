"""
JARVIS Plugin: list_plugins
Lists all currently active or available plugins, optionally filtered by category.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

PLUGIN = {
    "name": "list_plugins",
    "description": (
        "Lists all currently available JARVIS plugins, optionally filtered by category keyword "
        "(e.g. 'security', 'web', 'code', 'system', 'media', 'data'). Call this when unsure "
        "which plugin handles a user request — never guess a plugin name. Returns the live set."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "category": {
                "type": "STRING",
                "description": "Optional keyword to filter plugins by name or functionality",
            },
        },
        "required": [],
    },
    "tier": "core",
    "brief": "Lists available plugins, optionally filtered by category.",
}

def _scan_plugins() -> list[dict]:
    plugins_dir = Path(__file__).parent
    results = []
    for path in sorted(plugins_dir.glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"_probe_{path.stem}", path)
            if not spec or not spec.loader:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            meta = getattr(mod, "PLUGIN", None)
            if isinstance(meta, dict) and meta.get("name"):
                desc = str(meta.get("description", "")).strip().split(". ")[0]
                if desc and not desc.endswith("."):
                    desc += "."
                results.append({
                    "name": meta["name"],
                    "description": desc,
                    "full_desc": str(meta.get("description", "")).strip(),
                    "file": path.name,
                })
        except Exception:
            continue
    return results

def run(parameters: dict, player=None, session_memory=None) -> str:
    category = str(parameters.get("category", "")).strip().lower()
    try:
        all_plugins = _scan_plugins()
        if category:
            matched = [
                p for p in all_plugins
                if category in p["name"].lower() or category in p["full_desc"].lower()
            ]
        else:
            matched = all_plugins

        count = len(matched)
        if not matched:
            msg = f"No plugins found matching category '{category}'. Total installed: {len(all_plugins)}."
            if player:
                try:
                    player.write_log(f"JARVIS: {msg}")
                except Exception:
                    pass
            return f"Sir, I found no plugins matching '{category}'."

        # Format visual HUD display
        lines = [f"{'PLUGIN':<28} | DESCRIPTION", "-" * 70]
        for p in matched:
            lines.append(f"{p['name']:<28} | {p['description']}")
        content_table = "\n".join(lines)

        title = f"Plugins ({category})" if category else f"Available Plugins ({count})"
        if player:
            try:
                player.show_content(title, content_table)
                player.write_log(f"JARVIS: Displayed {count} plugins for '{category or 'all'}'")
            except Exception:
                pass

        if category:
            return f"Found {count} plugins for {category}. I have displayed them on your screen, Sir."
        return f"Sir, there are {count} plugins active. The full directory is on your display."
    except Exception as e:
        return f"Sir, failed to list plugins: {e}"
