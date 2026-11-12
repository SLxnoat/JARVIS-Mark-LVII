"""
plugins/task_planner.py - JARVIS Autonomous Goal Planner & Dynamic Multi-Tool Combiner.

Iron Man / JARVIS style autonomous cognitive meta-agent:
- Tool-agnostic architecture: Introspects live Action & Plugin registries at runtime.
- Dynamically plans, decomposes, and combines any available tools to achieve user goals.
- ReAct / Plan-and-Solve adaptive cognitive loop via core.gemini.
- Context pipelining: Passes observations and output data from step N to step N+1.
- Anti-recursion protection, step execution ceilings, and confirmation interlocks.
- Renders rich tactical mission briefs on the HUD via player.show_content().
- Live step-by-step progress logging via player.write_log().

Adheres strictly to AGENTS.md:
- No Qt widgets instantiated on worker threads.
- Thread-safe HUD feedback via player.show_content(), player.write_log(), and player.request_say().
- Background thread execution for non-blocking speech turn returns.
- Never raises exceptions, returns concise spoken feedback.
- Handles player=None gracefully for headless test suites and phone dashboard.
"""
from __future__ import annotations

import json
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core import gemini

PLUGIN = {
    "name": "task_planner",
    "description": (
        "JARVIS Autonomous Goal Planner & Multi-Tool Combiner: Formulates and executes an autonomous, "
        "multi-step plan to achieve complex goals by dynamically selecting, chaining, and combining "
        "any available system tools. Use when a user request requires multiple steps, diagnosis, "
        "cross-tool investigation, or compound workflows."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "goal": {
                "type": "STRING",
                "description": "The high-level objective to accomplish (e.g. 'Investigate web server failure and check network health').",
            },
            "context_hints": {
                "type": "STRING",
                "description": "Optional background hints or operator preferences (e.g. 'focus on port 8000', 'log findings to daily note').",
            },
            "max_steps": {
                "type": "INTEGER",
                "description": "Maximum tool execution steps allowed (default 5, maximum 8).",
            },
            "sync": {
                "type": "BOOLEAN",
                "description": "Set true for synchronous execution (primarily for testing); false/omitted runs in background thread.",
            },
        },
        "required": ["goal"],
    },
}

_MAX_STEPS_HARD_LIMIT = 8
_DEFAULT_MAX_STEPS = 5


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _get_tool_catalog(player=None) -> List[Dict[str, Any]]:
    """
    Introspect the live tool catalog dynamically.
    Prefers player.tool_catalog() if attached, otherwise falls back to
    discovering actions and plugins directly from disk.
    """
    catalog = []
    if player is not None and callable(getattr(player, "tool_catalog", None)):
        try:
            catalog = list(player.tool_catalog())
        except Exception:
            catalog = []

    if not catalog:
        try:
            from core.action_loader import discover_actions
            from core.plugin_loader import discover_plugins

            base_dir = _get_base_dir()
            act_reg = discover_actions(base_dir / "actions", logger=lambda _: None)
            plug_reg = discover_plugins(
                base_dir / "plugins",
                core_tool_names=act_reg.names(),
                logger=lambda _: None,
            )
            catalog = (
                act_reg.get_tool_declarations()
                + plug_reg.get_tool_declarations()
            )
        except Exception:
            catalog = []

    # Anti-recursion: Exclude task_planner from its own tool catalog
    return [t for t in catalog if t.get("name") != "task_planner"]


def _format_tool_catalog(tools: List[Dict[str, Any]]) -> str:
    """Format tools into a compact, token-efficient representation for the reasoning model."""
    lines = []
    for t in tools:
        name = t.get("name", "")
        if not name:
            continue
        desc = (t.get("brief") or t.get("description") or "").strip()
        first_line = desc.split("\n")[0][:120].strip()
        params = t.get("parameters", {}).get("properties", {})
        reqs = set(t.get("parameters", {}).get("required", []))

        param_signatures = []
        for p_name, p_schema in params.items():
            p_type = p_schema.get("type", "ANY")
            req_marker = "*" if p_name in reqs else ""
            param_signatures.append(f"{p_name}{req_marker}: {p_type}")

        sig = f"{name}({', '.join(param_signatures)})"
        lines.append(f"- `{sig}`: {first_line}")
    return "\n".join(lines)


def _dispatch_tool(
    name: str,
    parameters: Dict[str, Any],
    player=None,
    session_memory=None,
) -> str:
    """Dispatch a selected tool safely using player.run_tool or direct fallback."""
    if name == "task_planner":
        return "Error: Anti-recursion lock engaged — task_planner cannot invoke itself."

    if player is not None and callable(getattr(player, "run_tool", None)):
        try:
            res = player.run_tool(name, parameters)
            return str(res) if res is not None else "Done."
        except Exception as e:
            return f"Error executing tool '{name}': {e}"

    # Standalone / fallback direct dispatch
    try:
        from core.action_loader import discover_actions
        from core.plugin_loader import discover_plugins

        base_dir = _get_base_dir()
        act_reg = discover_actions(base_dir / "actions", logger=lambda _: None)
        if act_reg.has(name):
            res = act_reg.run(
                name,
                parameters,
                {"player": player, "session_memory": session_memory},
            )
            return str(res) if res is not None else "Done."

        plug_reg = discover_plugins(
            base_dir / "plugins",
            core_tool_names=act_reg.names(),
            logger=lambda _: None,
        )
        if plug_reg.has(name):
            res = plug_reg.run(
                name,
                parameters,
                player=player,
                session_memory=session_memory,
            )
            return str(res) if res is not None else "Done."

    except Exception as e:
        return f"Tool dispatch error for '{name}': {e}"

    return f"Tool '{name}' is not recognized in the available system catalog."


def _format_history_scratchpad(history: List[Dict[str, Any]]) -> str:
    if not history:
        return "None. No steps executed yet."

    entries = []
    for h in history:
        step_num = h.get("step", 1)
        tool = h.get("tool", "")
        params = json.dumps(h.get("parameters", {}), ensure_ascii=False)
        thought = h.get("thought", "")
        result = str(h.get("result", ""))
        # Truncate overly verbose tool results in scratchpad
        if len(result) > 600:
            result = result[:600] + "... [truncated]"
        entries.append(
            f"Step {step_num}:\n"
            f"  Tool: {tool}\n"
            f"  Parameters: {params}\n"
            f"  Reasoning: {thought}\n"
            f"  Observation: {result}"
        )
    return "\n\n".join(entries)


def _render_hud_briefing(
    goal: str,
    history: List[Dict[str, Any]],
    summary: str,
    elapsed: float,
    status: str = "COMPLETED 🟢",
) -> str:
    lines = [
        "### 🎯 AUTONOMOUS MISSION SUMMARY (JARVIS MARK-LVII)\n",
        f"**Target Objective:** `{goal}`",
        f"**Status:** {status}",
        f"**Execution Time:** `{elapsed:.2f}s` | **Steps Taken:** `{len(history)}`\n",
    ]

    if history:
        chain = " ➔ ".join(f"`{h.get('tool', 'step')}`" for h in history)
        lines.append(f"**Execution Pipeline:** {chain}\n")
        lines.append("#### 📋 Step Breakdown")
        for h in history:
            s_num = h.get("step", 1)
            s_tool = h.get("tool", "unknown")
            s_params = json.dumps(h.get("parameters", {}), ensure_ascii=False)
            s_thought = h.get("thought", "")
            s_res = str(h.get("result", "")).strip()
            if len(s_res) > 240:
                s_res = s_res[:240] + "..."
            lines.append(
                f"{s_num}. **`{s_tool}`** `{s_params}`\n"
                f"   - *Intent:* {s_thought or 'Direct step execution'}\n"
                f"   - *Observation:* `{s_res}`\n"
            )

    lines.append("#### 🔍 Tactical Intelligence & Findings")
    lines.append(summary.strip())
    lines.append(f"\n*Autonomous mission completed at {time.strftime('%H:%M:%S')}.*")
    return "\n".join(lines)


def _execute_planner_loop(
    goal: str,
    context_hints: str,
    max_steps: int,
    player=None,
    session_memory=None,
) -> tuple[str, str]:
    """
    Main cognitive reasoning and execution loop.
    Returns (spoken_response, full_summary_markdown).
    """
    t_start = time.monotonic()
    catalog = _get_tool_catalog(player)
    if not catalog:
        fail_msg = "I could not retrieve the system tool catalog, sir. No tools are currently available for planning."
        return fail_msg, fail_msg

    formatted_catalog = _format_tool_catalog(catalog)
    history: List[Dict[str, Any]] = []
    consecutive_repeat_count = 0
    last_action_sig = ""

    if player:
        try:
            player.write_log(f"🎯 [Planner] Initialized autonomous mission for: '{goal[:60]}'")
        except Exception:
            pass

    for step_idx in range(1, max_steps + 1):
        scratchpad = _format_history_scratchpad(history)

        prompt = (
            "You are JARVIS's Autonomous Mission Planner & Dynamic Tool Combiner.\n"
            f"Current Goal: {goal}\n"
            f"{f'Operator Context/Hints: {context_hints}' if context_hints else ''}\n\n"
            f"Available System Tools:\n"
            f"{formatted_catalog}\n\n"
            f"Execution Scratchpad (Steps Completed So Far):\n"
            f"{scratchpad}\n\n"
            "INSTRUCTIONS:\n"
            "1. Analyze what information has been gathered and what remains to achieve the operator's goal.\n"
            "2. If the goal is satisfied OR no further tool can help, set done=true, provide a comprehensive markdown summary of all findings, and a crisp 1-2 sentence spoken response.\n"
            "3. If an additional step is required, set done=false, explain your thought, select an available tool from the list above, and provide exact JSON parameters.\n"
            "4. NEVER invent tools outside the available system catalog.\n"
            "5. Respond STRICTLY with a single JSON object matching this schema:\n"
            "{\n"
            '  "done": false,\n'
            '  "thought": "Reasoning for choosing this tool next",\n'
            '  "tool": "exact_tool_name",\n'
            '  "parameters": {"param_key": "param_value"}\n'
            "}\n"
            "OR when finished:\n"
            "{\n"
            '  "done": true,\n'
            '  "thought": "Summary of goal fulfillment",\n'
            '  "summary": "Detailed markdown synthesis of results and conclusions",\n'
            '  "spoken_response": "Crisp 1-2 sentence spoken summary for voice HUD"\n'
            "}"
        )

        decision = gemini.as_json(prompt, tier=gemini.SMART, default=None)
        if not isinstance(decision, dict):
            # Fallback attempt if parsing had an issue
            raw_text = gemini.text(prompt, tier=gemini.SMART, default="")
            parsed = gemini.parse_json(raw_text, default=None)
            decision = parsed if isinstance(parsed, dict) else None

        if not decision:
            # Model unavailable or failure to produce plan
            if history:
                break
            fallback_spoken = "I encountered an issue generating the tactical plan for that objective, sir."
            return fallback_spoken, fallback_spoken

        if decision.get("done") is True:
            summary = decision.get("summary") or "Objective fulfilled successfully."
            spoken = decision.get("spoken_response") or "Autonomous mission completed as requested, sir."
            elapsed = time.monotonic() - t_start
            hud_card = _render_hud_briefing(goal, history, summary, elapsed, status="COMPLETED 🟢")
            return spoken, hud_card

        tool_name = str(decision.get("tool") or "").strip()
        params = decision.get("parameters") or {}
        thought = str(decision.get("thought") or "").strip()

        if not tool_name:
            break

        # Stagnation / infinite loop detection
        curr_sig = f"{tool_name}:{json.dumps(params, sort_keys=True)}"
        if curr_sig == last_action_sig:
            consecutive_repeat_count += 1
            if consecutive_repeat_count >= 2:
                if player:
                    try:
                        player.write_log(f"⚠️ [Planner] Detected repeated tool invocation '{tool_name}'. Breaking loop.")
                    except Exception:
                        pass
                break
        else:
            consecutive_repeat_count = 0
            last_action_sig = curr_sig

        if player:
            try:
                player.write_log(f"🎯 [Planner] Step {step_idx}/{max_steps}: {tool_name} ➔ Executing...")
            except Exception:
                pass

        # Execute selected tool
        t_step_start = time.monotonic()
        tool_output = _dispatch_tool(tool_name, params, player=player, session_memory=session_memory)
        t_step_dur = time.monotonic() - t_step_start

        if player:
            try:
                player.write_log(f"🎯 [Planner] Step {step_idx}/{max_steps}: {tool_name} ➔ Completed ({t_step_dur:.2f}s)")
            except Exception:
                pass

        history.append({
            "step": step_idx,
            "tool": tool_name,
            "parameters": params,
            "thought": thought,
            "result": tool_output,
        })

    # If reached here, either max_steps reached or broken early -> Synthesize final findings
    elapsed = time.monotonic() - t_start
    scratchpad = _format_history_scratchpad(history)

    synth_prompt = (
        "You are JARVIS's Mission Debriefer.\n"
        f"Target Goal: {goal}\n"
        f"Execution History:\n{scratchpad}\n\n"
        "Synthesize all observations into:\n"
        "1. A comprehensive markdown findings summary.\n"
        "2. A crisp, natural 1-2 sentence spoken debrief for the user.\n"
        "Return STRICTLY JSON: {\"summary\": \"...\", \"spoken_response\": \"...\"}"
    )

    synth = gemini.as_json(synth_prompt, tier=gemini.SMART, default=None)
    if isinstance(synth, dict) and synth.get("summary"):
        summary = synth.get("summary")
        spoken = synth.get("spoken_response") or f"Mission completed in {len(history)} steps, sir. Findings are on your HUD."
    else:
        summary = f"Completed {len(history)} autonomous steps toward objective: {goal}.\n\n" + "\n".join(
            f"- **{h['tool']}**: {str(h['result'])[:160]}" for h in history
        )
        spoken = f"I've completed the autonomous investigation across {len(history)} tools, sir. Summary is displayed on your HUD."

    status = "COMPLETED 🟢" if len(history) > 0 else "HALTED ⚠️"
    hud_card = _render_hud_briefing(goal, history, summary, elapsed, status=status)
    return spoken, hud_card


def _background_worker(
    goal: str,
    context_hints: str,
    max_steps: int,
    player=None,
    session_memory=None,
):
    """Background execution runner conforming to AGENTS.md."""
    try:
        spoken, hud_card = _execute_planner_loop(
            goal=goal,
            context_hints=context_hints,
            max_steps=max_steps,
            player=player,
            session_memory=session_memory,
        )

        if player:
            try:
                player.show_content("AUTONOMOUS TASK PLANNER", hud_card)
                player.write_log(f"🎯 [Planner] Mission finished. Spoken: \"{spoken}\"")
                # Voice HUD mid-task speech channel if supported
                if callable(getattr(player, "request_say", None)):
                    player.request_say(spoken)
            except Exception:
                pass

    except Exception as e:
        if player:
            try:
                player.write_log(f"⚠️ [Planner] Background worker encountered error: {e}")
            except Exception:
                pass


def run(parameters: dict, player=None, session_memory=None) -> str:
    """
    Plugin entrypoint complying strictly with AGENTS.md:
    - Never raises exceptions.
    - Handles player=None gracefully.
    - Returns within a few seconds, delegating heavy planning and tool execution to a background thread.
    - Supports synchronous execution when explicitly requested (sync=True).
    """
    try:
        goal = str(parameters.get("goal") or "").strip()
        if not goal:
            return "Please provide a specific goal or objective for me to plan and execute, sir."

        context_hints = str(parameters.get("context_hints") or "").strip()
        raw_max = parameters.get("max_steps")
        try:
            max_steps = min(_MAX_STEPS_HARD_LIMIT, max(1, int(raw_max))) if raw_max is not None else _DEFAULT_MAX_STEPS
        except Exception:
            max_steps = _DEFAULT_MAX_STEPS

        is_sync = bool(parameters.get("sync", False))

        if is_sync:
            spoken, hud_card = _execute_planner_loop(
                goal=goal,
                context_hints=context_hints,
                max_steps=max_steps,
                player=player,
                session_memory=session_memory,
            )
            if player:
                try:
                    player.show_content("AUTONOMOUS TASK PLANNER", hud_card)
                except Exception:
                    pass
            return spoken

        # Background thread execution (default for live voice HUD session)
        t = threading.Thread(
            target=_background_worker,
            args=(goal, context_hints, max_steps, player, session_memory),
            daemon=True,
            name=f"task-planner-{int(time.time())}",
        )
        t.start()

        return (
            f"Understood, sir. Formulating an autonomous plan for '{goal[:50]}' "
            "and coordinating available tools now. I will display the intelligence on your HUD."
        )

    except Exception as e:
        return f"Sir, the task planner encountered an error: {e}"
