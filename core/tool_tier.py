"""
core/tool_tier.py — JARVIS Dynamic Tool Tiering (Hermes Core/Edge Pattern)
===========================================================================
Reduces Gemini context window token pressure by splitting the 73+ plugin
tool declarations into two tiers:

  CORE (<=15)  — High-frequency, low-token tools always present in every turn.
  EDGE (rest)  — Domain-specific tools injected on-demand via ``list_plugins``.

The 15-slot Core budget is defined by the CORE_TOOLS set below.  Any plugin
whose PLUGIN dict includes ``"tier": "core"`` is promoted automatically.
Everything else stays in the edge pool and can be discovered via
``list_plugins(category=...)`` progressive disclosure.

Usage in main.py / LiveConnectConfig
-------------------------------------
    from core.tool_tier import split_declarations, budget_declarations

    all_decls  = loader.get_tool_declarations()
    core_decls = budget_declarations(all_decls)      # <= 15 entries for every turn
    edge_decls = split_declarations(all_decls)[1]    # available for on-demand load

The ``budget_declarations`` helper is what main.py / providers/schema.py
should pass to Gemini instead of the full list when ``TOOL_TIER_ENABLED``
is True (default).  Setting the env-var ``JARVIS_TOOL_TIER=0`` disables
tiering for debugging.
"""
from __future__ import annotations

import os
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

#: Hard set of plugin names that always occupy a Core slot regardless of
#: usage frequency.  Kept to exactly 15 entries so the declaration budget
#: is predictable.  Reorder to reprioritise.
CORE_TOOLS: List[str] = [
    "list_plugins",          # progressive discovery gateway — must always be Core
    "plugin_describe",       # companion to list_plugins
    "tool_chain",            # multi-step planning
    "web_search",            # most common user intent
    "file_controller",       # file read/write
    "code_helper",           # coding assistance
    "computer_control",      # mouse / keyboard automation
    "send_message",          # notifications
    "reminder",              # scheduling
    "task_planner",          # autonomous task engine
    "skill_loader",          # progressive skill disclosure
    "cognitive_neuro_cortex",# memory & learning
    "screen_processor",      # screenshot / vision
    "dev_agent",             # agentic coding
    "desktop",               # desktop operations
]

#: Maximum number of Core declarations injected per turn.
CORE_BUDGET: int = 15

#: Set to False (or env JARVIS_TOOL_TIER=0) to disable tiering for debugging.
TIER_ENABLED: bool = os.environ.get("JARVIS_TOOL_TIER", "1") not in ("0", "false", "False")


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def split_declarations(
    all_decls: List[dict],
) -> Tuple[List[dict], List[dict]]:
    """
    Partition *all_decls* into (core_list, edge_list).

    Priority order for Core slot:
      1. Explicitly ``"tier": "core"`` in the declaration.
      2. Name appears in CORE_TOOLS list (in order).
      3. First-come remainder fills up to CORE_BUDGET if slots remain.
    """
    if not TIER_ENABLED:
        return all_decls, []

    core: List[dict] = []
    edge: List[dict] = []
    core_names_seen: set = set()

    # Pass 1: declarations self-labelled as core
    for decl in all_decls:
        if decl.get("tier") == "core" and decl["name"] not in core_names_seen:
            if len(core) < CORE_BUDGET:
                core.append(decl)
                core_names_seen.add(decl["name"])

    # Pass 2: CORE_TOOLS list order
    name_to_decl = {d["name"]: d for d in all_decls}
    for name in CORE_TOOLS:
        if name not in core_names_seen and name in name_to_decl:
            if len(core) < CORE_BUDGET:
                core.append(name_to_decl[name])
                core_names_seen.add(name)

    # Pass 3: remaining go to edge
    for decl in all_decls:
        if decl["name"] not in core_names_seen:
            edge.append(decl)

    return core, edge


def budget_declarations(all_decls: List[dict]) -> List[dict]:
    """Return the declarations that should be sent to Gemini on every turn."""
    core, _edge = split_declarations(all_decls)
    return core


def edge_declarations(all_decls: List[dict]) -> List[dict]:
    """Return the edge pool that is available for on-demand injection."""
    _core, edge = split_declarations(all_decls)
    return edge


def tier_summary(all_decls: List[dict]) -> str:
    """Human-readable summary for debugging / log output."""
    core, edge = split_declarations(all_decls)
    lines = [
        f"Tool Tiering Summary  (TIER_ENABLED={TIER_ENABLED})",
        f"  Core ({len(core)}/{CORE_BUDGET}): {', '.join(d['name'] for d in core)}",
        f"  Edge ({len(edge)}): {', '.join(d['name'] for d in edge[:10])}"
        + (" ..." if len(edge) > 10 else ""),
    ]
    return "\n".join(lines)
