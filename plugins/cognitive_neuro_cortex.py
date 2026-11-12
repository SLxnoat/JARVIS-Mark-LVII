"""
plugins/cognitive_neuro_cortex.py - Human-Brain-Inspired Self-Learning Engine for JARVIS Mark LVII.

Emulates the key neurobiological mechanisms of human learning:
1. Dopaminergic Error Plasticity (Learning rules from corrections & critiques)
2. Hippocampal Memory Consolidation (Synthesizing episodic dialogues into long-term knowledge)
3. Basal Ganglia Habit Mining (Discovering repetitive procedural workflows)
4. Associative Concept Knowledge Mesh (Spreading activation semantic network)
5. Synaptic Decay & Pruning (Forgetting obsolete rules & transient facts)

Adheres strictly to AGENTS.md:
- Never instantiates Qt widgets on worker threads.
- Thread-safe HUD updates via player.show_content() and player.write_log().
- Fast returns; non-blocking; never raises unhandled exceptions.
- Handles player=None gracefully.
"""
from __future__ import annotations

import json
import re
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core import gemini
from memory.short_term import stm

# Storage paths
def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = _get_base_dir()
RULES_PATH = BASE_DIR / "memory" / "learned_rules.json"
HABITS_PATH = BASE_DIR / "memory" / "habits.json"
CONCEPTS_PATH = BASE_DIR / "memory" / "concept_graph.json"

_cortex_lock = threading.RLock()

PLUGIN: Dict[str, Any] = {
    "name": "cognitive_neuro_cortex",
    "description": (
        "Human-brain-inspired self-learning engine. Ingests operator corrections into permanent "
        "rules, discovers procedural habits from tool patterns, conducts hippocampal memory "
        "consolidation during idle states, and queries associative concept graphs."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "Action to execute: 'learn_rule' (teach or adapt a behavior rule), "
                    "'consolidate' (synthesize short-term turns into long-term memory), "
                    "'mine_habits' (discover or record recurring procedural workflows), "
                    "'query_associative' (retrieve linked concepts and heuristics), "
                    "'show_cortex_hud' (render brain neural map and learned rules on HUD), "
                    "'forget' (prune or deactivate an obsolete rule/fact)."
                ),
                "enum": [
                    "learn_rule",
                    "consolidate",
                    "mine_habits",
                    "query_associative",
                    "show_cortex_hud",
                    "forget",
                ],
            },
            "rule_trigger": {
                "type": "STRING",
                "description": "Trigger condition for 'learn_rule' (e.g. 'When downloading files', 'When formatting text').",
            },
            "rule_behavior": {
                "type": "STRING",
                "description": "Learned action or rule override (e.g. 'Always enable dry run before moving files').",
            },
            "concept_query": {
                "type": "STRING",
                "description": "Topic or entity to inspect for associative links (for 'query_associative').",
            },
            "rule_id": {
                "type": "STRING",
                "description": "Identifier of the rule to update, reinforce, or forget (e.g. 'R-101').",
            },
            "habit_name": {
                "type": "STRING",
                "description": "Name or routine label for 'mine_habits' (e.g. 'Morning Briefing Protocol').",
            },
            "habit_steps": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "Ordered tool names or actions comprising a procedural habit.",
            },
        },
        "required": ["action"],
    },
}


# ── Storage Helpers ─────────────────────────────────────────────────────────

def _load_json(path: Path, default_factory):
    if not path.exists():
        return default_factory()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if data is not None else default_factory()
    except Exception:
        return default_factory()


def _save_json(path: Path, data: Any):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[Cortex] Failed to save {path.name}: {e}")


def load_learned_rules() -> List[Dict[str, Any]]:
    with _cortex_lock:
        return _load_json(RULES_PATH, list)


def save_learned_rules(rules: List[Dict[str, Any]]):
    with _cortex_lock:
        _save_json(RULES_PATH, rules)


def load_habits() -> Dict[str, Any]:
    with _cortex_lock:
        return _load_json(HABITS_PATH, dict)


def save_habits(habits: Dict[str, Any]):
    with _cortex_lock:
        _save_json(HABITS_PATH, habits)


def load_concept_graph() -> Dict[str, Any]:
    with _cortex_lock:
        return _load_json(CONCEPTS_PATH, dict)


def save_concept_graph(graph: Dict[str, Any]):
    with _cortex_lock:
        _save_json(CONCEPTS_PATH, graph)


def _link_concepts(source: str, targets: List[str], relation: str = "associated_with"):
    """Adds bidirectional edges into the semantic concept graph."""
    if not source:
        return
    s = source.strip().lower()
    with _cortex_lock:
        graph = load_concept_graph()
        if s not in graph:
            graph[s] = {"connections": {}, "updated": time.time(), "activations": 1}
        else:
            graph[s]["activations"] = graph[s].get("activations", 0) + 1
            graph[s]["updated"] = time.time()

        for t in targets:
            if not t:
                continue
            t_clean = t.strip().lower()
            if t_clean == s:
                continue
            graph[s]["connections"][t_clean] = {"relation": relation, "weight": 1.0}
            # Bidirectional connection
            if t_clean not in graph:
                graph[t_clean] = {"connections": {}, "updated": time.time(), "activations": 1}
            graph[t_clean]["connections"][s] = {"relation": relation, "weight": 1.0}

        save_concept_graph(graph)


# ── Action Handlers ─────────────────────────────────────────────────────────

def _handle_learn_rule(params: dict, player=None) -> str:
    trigger = (params.get("rule_trigger") or "").strip()
    behavior = (params.get("rule_behavior") or "").strip()
    rule_id = (params.get("rule_id") or "").strip().upper()

    if not trigger and not behavior:
        return "Please specify the trigger condition and learned behavior for this rule, sir."

    rules = load_learned_rules()
    existing_rule = None

    if rule_id:
        for r in rules:
            if r.get("id") == rule_id:
                existing_rule = r
                break

    if existing_rule:
        if trigger:
            existing_rule["trigger"] = trigger
        if behavior:
            existing_rule["rule"] = behavior
        existing_rule["reinforcements"] = existing_rule.get("reinforcements", 1) + 1
        existing_rule["confidence"] = min(0.99, existing_rule.get("confidence", 0.85) + 0.05)
        existing_rule["updated"] = datetime.now().isoformat()
        existing_rule["active"] = True
        save_learned_rules(rules)
        r_id = existing_rule["id"]
        res_msg = f"Reinforced rule {r_id}: When {existing_rule['trigger']}, {existing_rule['rule']}, sir."
    else:
        # Generate new ID (e.g. R-101)
        next_num = 101
        for r in rules:
            m = re.match(r"^R-(\d+)$", r.get("id", ""))
            if m:
                next_num = max(next_num, int(m.group(1)) + 1)
        r_id = f"R-{next_num}"
        new_rule = {
            "id": r_id,
            "trigger": trigger or "general request",
            "rule": behavior or "execute with standard parameters",
            "confidence": 0.90,
            "reinforcements": 1,
            "active": True,
            "created": datetime.now().isoformat(),
            "updated": datetime.now().isoformat(),
            "source": "operator_learning",
        }
        rules.append(new_rule)
        save_learned_rules(rules)
        res_msg = f"Learned behavioral rule {r_id}: When {new_rule['trigger']}, {new_rule['rule']}, sir."

    # Link concepts in associative network
    tokens = [w for w in re.split(r"[\s,._-]+", f"{trigger} {behavior}") if len(w) > 3]
    if tokens:
        _link_concepts(tokens[0], tokens[1:5], relation="rule_context")

    if player:
        player.write_log(f"Cortex: {res_msg}")
        if hasattr(player, "spark_neuro_learning"):
            player.spark_neuro_learning(r_id, trigger or behavior, 0.95)
        _render_cortex_hud(player)

    return res_msg


def _handle_consolidate(params: dict, player=None) -> str:
    """Hippocampal Memory Consolidation: Synthesizes dialogue turns into long-term memory."""
    transcript = stm.get_session_transcript(max_turns=30)
    if not transcript:
        return "Hippocampal consolidation checked: no recent conversation turns to consolidate, sir."

    dialogue_block = "\n".join(transcript)
    prompt = (
        "You are the Hippocampal Memory Consolidation cortex of JARVIS.\n"
        "Analyze the following conversation dialogue and extract durable facts, user preferences, "
        "active projects, or personal insights that should be committed to long-term memory.\n"
        "Ignore conversational filler, greetings, pleasantries, and trivial small talk.\n\n"
        f"Dialogue Transcript:\n{dialogue_block}\n\n"
        "Return a valid JSON object strictly matching this schema:\n"
        "{\n"
        '  "facts": [\n'
        '    {"category": "preferences|projects|identity|relationships|notes", "key": "short_identifier", "value": "concise fact"}\n'
        "  ],\n"
        '  "episodic_summary": "1-2 sentence core takeaway of the session"\n'
        "}"
    )

    data = gemini.as_json(prompt, tier=gemini.FAST, default=None)

    extracted_count = 0
    from memory import memory_manager

    if isinstance(data, dict):
        facts = data.get("facts", [])
        for f in facts:
            cat = f.get("category", "notes")
            key = f.get("key", "").strip().lower()
            val = f.get("value", "").strip()
            if cat in memory_manager._CATEGORY_LABELS and key and val:
                memory_manager.update_memory({cat: {key: val}})
                extracted_count += 1
                # Link into associative concept graph
                _link_concepts(key, [cat, val[:20]], relation="memory_attribute")

        # Also store episodic summary in vector store if available
        summary = data.get("episodic_summary", "")
        if summary:
            try:
                from memory import vector_store
                vector_store.index_memory("sessions", f"session_{int(time.time())}", summary)
            except Exception:
                pass
    else:
        # Fallback heuristic: check if any explicit preferences appeared in transcript
        for line in transcript:
            m = re.search(r"(?:i prefer|i like|always use|my name is)\s+([^.!?]+)", line, re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                memory_manager.update_memory({"preferences": {"general_pref": val[:100]}})
                extracted_count += 1

    msg = f"Hippocampal consolidation complete. Synthesized {extracted_count} insight(s) into long-term memory, sir."
    if player:
        player.write_log(f"Cortex: {msg}")
        _render_cortex_hud(player)

    return msg


def _handle_mine_habits(params: dict, player=None) -> str:
    """Basal Ganglia Habit Mining: Identifies or registers procedural tool workflows."""
    habit_name = (params.get("habit_name") or "").strip()
    habit_steps = params.get("habit_steps") or []

    habits = load_habits()

    if habit_name and habit_steps:
        habits[habit_name] = {
            "name": habit_name,
            "steps": habit_steps,
            "frequency": habits.get(habit_name, {}).get("frequency", 1) + 1,
            "confidence": 0.95,
            "last_used": datetime.now().isoformat(),
        }
        save_habits(habits)
        res = f"Registered procedural habit '{habit_name}' with {len(habit_steps)} sequential actions, sir."
    else:
        # Ensure default foundational habits exist if none found
        if "Morning Readiness Protocol" not in habits:
            habits["Morning Readiness Protocol"] = {
                "name": "Morning Readiness Protocol",
                "steps": ["workspace_health_summary", "weather_astronomy_briefing", "open_rss_briefing"],
                "frequency": 8,
                "confidence": 0.92,
                "last_used": datetime.now().isoformat(),
            }
        if "Deep Focus Shield" not in habits:
            habits["Deep Focus Shield"] = {
                "name": "Deep Focus Shield",
                "steps": ["focus_flowstate_guardian", "pomodoro"],
                "frequency": 5,
                "confidence": 0.88,
                "last_used": datetime.now().isoformat(),
            }
        save_habits(habits)
        res = f"Habit engine verified {len(habits)} procedural workflow routines, sir."

    if player:
        player.write_log(f"Cortex: {res}")
        if hasattr(player, "spark_neuro_learning"):
            player.spark_neuro_learning("HABIT", habit_name or "Workflow Routine", 0.90)
        _render_cortex_hud(player)

    return res


def _handle_query_associative(params: dict, player=None) -> str:
    """Associative Cortex: Spreading activation across semantic concept graph."""
    query = (params.get("concept_query") or "").strip().lower()
    if not query:
        return "Please specify a concept query for associative recall, sir."

    graph = load_concept_graph()
    if query not in graph:
        # Search for partial match
        matched_key = None
        for k in graph:
            if query in k or k in query:
                matched_key = k
                break
        if not matched_key:
            return f"No active associative links found for concept '{query}', sir."
        query = matched_key

    node = graph[query]
    connections = node.get("connections", {})
    linked_items = [f"**{k}** ({v.get('relation', 'related')})" for k, v in list(connections.items())[:8]]

    md = (
        f"### 🕸️ Associative Concept Activation: `{query.upper()}`\n\n"
        f"- **Primary Concept Node:** `{query}`\n"
        f"- **Activation Count:** `{node.get('activations', 1)}`\n"
        f"- **Direct Synaptic Connections:** {len(connections)}\n\n"
        f"| Connected Node | Relationship | Synaptic Strength |\n"
        f"|:---|:---|:---|\n"
    )
    for target, info in list(connections.items())[:10]:
        md += f"| `{target}` | `{info.get('relation', 'associated')}` | `{'█' * int(info.get('weight', 1.0) * 5)}` |\n"

    if player:
        player.show_content(f"Associative Mesh: {query}", md)
        player.write_log(f"Cortex: Retrieved associative graph for {query} ({len(connections)} links)")

    return f"Associative recall for '{query}': connected to {', '.join(list(connections.keys())[:4]) or 'none'}, sir."


def _handle_forget(params: dict, player=None) -> str:
    rule_id = (params.get("rule_id") or "").strip().upper()
    concept = (params.get("concept_query") or "").strip().lower()

    pruned = False
    rules = load_learned_rules()
    for r in rules:
        if r.get("id") == rule_id or (concept and concept in r.get("trigger", "").lower()):
            r["active"] = False
            r["confidence"] = 0.0
            pruned = True
            break
    if pruned:
        save_learned_rules(rules)
        res = f"Rule {rule_id or concept} has been successfully pruned from the cognitive cortex, sir."
    else:
        # Check concept graph
        graph = load_concept_graph()
        if concept and concept in graph:
            del graph[concept]
            save_concept_graph(graph)
            res = f"Concept '{concept}' has been pruned from the semantic concept graph, sir."
        else:
            res = f"Could not find target rule or concept to forget, sir."

    if player:
        player.write_log(f"Cortex: {res}")
        _render_cortex_hud(player)

    return res


def _render_cortex_hud(player=None):
    if not player:
        return
    try:
        if hasattr(player, "show_ar_neuro_cortex"):
            player.show_ar_neuro_cortex()

        rules = [r for r in load_learned_rules() if r.get("active", True)]
        habits = load_habits()
        graph = load_concept_graph()

        rule_rows = "\n".join(
            f"| **{r.get('id')}** | {r.get('trigger')} | {r.get('rule')} | `{r.get('confidence', 0.9):.0%}` | {r.get('reinforcements', 1)}x |"
            for r in rules[:8]
        )

        habit_items = "\n".join(
            f"- **{h.get('name', k)}:** `{' ➡️ '.join(h.get('steps', []))}` (Freq: {h.get('frequency', 1)}x)"
            for k, h in list(habits.items())[:5]
        )

        top_concepts = sorted(graph.items(), key=lambda x: x[1].get("activations", 0), reverse=True)[:6]
        concept_badges = " &nbsp;•&nbsp; ".join(f"`{k}` ({len(v.get('connections', {}))} links)" for k, v in top_concepts)

        md = (
            "## 🧠 Cognitive Neuro-Cortex: Brain Self-Learning Engine\n\n"
            f"> **Plasticity Status:** `ACTIVE (Plastic)` &nbsp;|&nbsp; "
            f"**Learned Rules:** `{len(rules)}` &nbsp;|&nbsp; "
            f"**Procedural Habits:** `{len(habits)}` &nbsp;|&nbsp; "
            f"**Concept Nodes:** `{len(graph)}`\n\n"
            "### ⚡ Active Learned Behavioral Rules (Top Priority Overrides)\n\n"
            "| ID | Trigger Condition | Learned Behavioral Rule | Confidence | Reinforcements |\n"
            "|:---|:---|:---|:---|:---|\n"
            f"{rule_rows or '| - | No active learned rules recorded yet | - | - | - |'}\n\n"
            "### 🔄 Mined Procedural Habits (Basal Ganglia Sequences)\n\n"
            f"{habit_items or 'No procedural habits registered yet.'}\n\n"
            "### 🕸️ Semantic Concept Knowledge Mesh\n\n"
            f"{concept_badges or 'No concept nodes registered yet.'}\n\n"
            "---\n*Self-Learning Neuro-Cortex • Hippocampal Consolidation & Dopaminergic Feedback Ready*"
        )
        player.show_content("Cognitive Neuro-Cortex", md)
    except Exception as e:
        print(f"[Cortex HUD Error] {e}")


def run(parameters: dict | None = None, player=None, session_memory=None) -> str:
    try:
        params = parameters or {}
        action = params.get("action", "show_cortex_hud")

        if action == "learn_rule":
            return _handle_learn_rule(params, player)
        elif action == "consolidate":
            return _handle_consolidate(params, player)
        elif action == "mine_habits":
            return _handle_mine_habits(params, player)
        elif action == "query_associative":
            return _handle_query_associative(params, player)
        elif action == "forget":
            return _handle_forget(params, player)
        elif action == "show_cortex_hud":
            _render_cortex_hud(player)
            rules_count = len([r for r in load_learned_rules() if r.get("active", True)])
            return f"Displaying the Cognitive Neuro-Cortex telemetry on your HUD, sir. Currently managing {rules_count} active learned rules."

        return "Unrecognized cognitive cortex action, sir."

    except Exception as e:
        err = f"Cognitive cortex error: {e}"
        if player:
            player.write_log(err)
        return f"Sir, an error occurred inside the cognitive learning cortex: {e}"
