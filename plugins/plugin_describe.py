"""
JARVIS Plugin: plugin_describe
Inspects and displays the complete schema, description, and parameter specification of any plugin.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

PLUGIN = {
    "name": "plugin_describe",
    "description": (
        "Returns the full name, description, and parameter schema of any named JARVIS plugin. "
        "Use this before calling a plugin whose parameters you are unsure of."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "name": {
                "type": "STRING",
                "description": "The exact identifier name of the plugin to inspect (e.g. 'docker_sentinel')",
            },
        },
        "required": ["name"],
    },
    "tier": "core",
    "brief": "Returns full schema of a named plugin.",
}

def run(parameters: dict, player=None, session_memory=None) -> str:
    target_name = str(parameters.get("name", "")).strip().lower()
    if not target_name:
        return "Sir, please specify which plugin you want to inspect."

    plugins_dir = Path(__file__).parent
    found_meta = None
    target_file = None

    for path in sorted(plugins_dir.glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"_desc_{path.stem}", path)
            if not spec or not spec.loader:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            meta = getattr(mod, "PLUGIN", None)
            if isinstance(meta, dict) and meta.get("name") == target_name:
                found_meta = meta
                target_file = path.name
                break
        except Exception:
            continue

    if not found_meta:
        return f"Sir, I could not find a plugin named '{target_name}'."

    try:
        desc = found_meta.get("description", "No description provided.")
        params = found_meta.get("parameters", {})
        props = params.get("properties", {})
        required = params.get("required", [])

        hud_lines = [
            f"PLUGIN: {found_meta.get('name')}",
            f"SOURCE: plugins/{target_file}",
            f"TIER:   {found_meta.get('tier', 'standard')}",
            "-" * 60,
            "DESCRIPTION:",
            desc,
            "-" * 60,
            f"PARAMETERS ({len(props)} defined, {len(required)} required):",
        ]

        if not props:
            hud_lines.append("  (No parameters required)")
        else:
            for p_name, p_info in props.items():
                p_type = p_info.get("type", "ANY")
                req_str = "[REQUIRED]" if p_name in required else "[OPTIONAL]"
                p_desc = p_info.get("description", "")
                hud_lines.append(f"  • {p_name} ({p_type}) {req_str}: {p_desc}")

        full_detail = "\n".join(hud_lines)

        if player:
            try:
                player.show_content(f"Schema: {target_name}", full_detail)
                player.write_log(f"JARVIS: Inspected schema for '{target_name}'")
            except Exception:
                pass

        return f"Sir, I have displayed the schema for {target_name} on your screen."
    except Exception as e:
        return f"Sir, error reading plugin schema: {e}"
