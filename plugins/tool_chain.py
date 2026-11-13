"""
JARVIS Plugin: tool_chain
Runs a sequence of JARVIS plugins sequentially in a background thread for agentic multi-step workflows.
"""
from __future__ import annotations

import importlib.util
import threading
from pathlib import Path
from typing import Any

PLUGIN = {
    "name": "tool_chain",
    "description": (
        "Runs a sequence of JARVIS plugins in order as an autonomous background pipeline. "
        "Use for multi-step tasks such as research+summarise, audit+report, or scan+clean. "
        "Each step is executed sequentially with progress logged to the HUD."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "goal": {
                "type": "STRING",
                "description": "High-level description of what this pipeline aims to accomplish",
            },
            "steps": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "List of plugin names to execute in exact order (maximum 8 steps)",
            },
        },
        "required": ["goal", "steps"],
    },
    "tier": "core",
    "brief": "Autonomous pipeline executor for sequential multi-tool workflows.",
}

def _resolve_plugin_runner(name: str):
    plugins_dir = Path(__file__).parent
    target_path = plugins_dir / f"{name}.py"
    if not target_path.is_file():
        # Fallback probe
        for path in plugins_dir.glob("*.py"):
            if path.name.startswith("_"):
                continue
            if path.stem == name:
                target_path = path
                break
        else:
            return None
    try:
        spec = importlib.util.spec_from_file_location(f"_chain_{name}", target_path)
        if not spec or not spec.loader:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return getattr(mod, "run", None)
    except Exception:
        return None

def _execute_pipeline(goal: str, step_names: list[str], player):
    results = []
    total = len(step_names)

    if player:
        try:
            player.write_log(f"JARVIS: Starting pipeline '{goal}' ({total} steps)")
        except Exception:
            pass

    for i, step_name in enumerate(step_names, 1):
        clean_name = str(step_name).strip()
        if not clean_name:
            continue

        if player:
            try:
                player.write_log(f"JARVIS: Pipeline [{i}/{total}] → {clean_name}")
            except Exception:
                pass

        runner = _resolve_plugin_runner(clean_name)
        if not runner:
            err = f"Plugin '{clean_name}' could not be resolved."
            results.append(f"Step {i} ({clean_name}): FAILED — {err}")
            if player:
                try:
                    player.write_log(f"JARVIS: ✗ {err}")
                except Exception:
                    pass
            continue

        try:
            res = runner({}, player=player)
            results.append(f"Step {i} ({clean_name}): {res}")
        except Exception as e:
            err = f"Error executing {clean_name}: {e}"
            results.append(f"Step {i} ({clean_name}): FAILED — {err}")
            if player:
                try:
                    player.write_log(f"JARVIS: ✗ {err}")
                except Exception:
                    pass

    summary_text = "\n".join(results)
    if player:
        try:
            player.show_content(f"Pipeline Result: {goal}", summary_text)
            player.write_log(f"JARVIS: Pipeline completed successfully: {goal}")
        except Exception:
            pass

def run(parameters: dict, player=None, session_memory=None) -> str:
    goal = str(parameters.get("goal", "Multi-step task")).strip()
    steps_raw = parameters.get("steps", [])

    if not isinstance(steps_raw, list) or not steps_raw:
        return "Sir, please provide a list of plugin names to execute in the pipeline."

    step_names = [str(s).strip() for s in steps_raw if str(s).strip()][:8]

    if not step_names:
        return "Sir, no valid step names were provided for the pipeline."

    # Launch background thread to prevent blocking Qt and main loop
    thread = threading.Thread(
        target=_execute_pipeline,
        args=(goal, step_names, player),
        daemon=True,
        name=f"ToolChain-{goal[:20]}",
    )
    thread.start()

    return f"Sir, I have initiated the {len(step_names)}-step pipeline for '{goal}'. Progress will be tracked on your HUD."
