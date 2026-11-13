# JARVIS Mark-LVII: Autonomous Learning, Memory & Execution Architecture

This document defines the architectural specification and operational guide for JARVIS's self-learning cognition, multi-tiered memory systems, and deterministic execution pipeline.

---

## 1. System Architecture

```
                    ┌─────────────────────────┐
                    │  Operator Instructions  │
                    │   & Environmental Cues  │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ 1. INGESTION & LEARNING │
                    │ • Error Plasticity      │
                    │ • Feedback Mining       │
                    │ • Observation / OCR     │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ 2. MULTI-TIER MEMORY    │
                    │ • Short-Term (STM)      │
                    │ • Core Prompt (LTM)     │
                    │ • Deep Vector/Semantic  │
                    │ • Neuro-Cortex Rules    │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ 3. PIPELINE EXECUTION   │
                    │ • Pre-check & Iron Law  │
                    │ • Progressive Discovery │
                    │ • Tool Chaining         │
                    │ • Thread-Safe HUD (Qt)  │
                    └─────────────────────────┘
```

---

## 2. Ingestion & Self-Learning System

JARVIS does not rely on static prompting; it adapts autonomously through three sensory and learning vectors:

### A. Dopaminergic Error Plasticity (`plugins/cognitive_neuro_cortex.py`)
- Emulates biological learning from negative and positive reinforcement.
- When an operator issues a correction (e.g. *"Don't use sudo for this"*, *"Format code with 4 spaces"*), the system extracts:
  - **`trigger`**: The context condition.
  - **`action`**: The preferred behavior.
- Ingested via:
  ```python
  cognitive_neuro_cortex.run({
      "action": "learn_rule",
      "rule_trigger": "When packaging release builds",
      "rule_action": "Always execute test suite first"
  })
  ```
- Persisted in: `memory/learned_rules.json`.

### B. Hippocampal Memory Consolidation
- Idle background cycles synthesize episodic short-term dialogues into compact, semantic facts.
- Strips conversational boilerplate and extracts core preferences, project milestones, and entity states.

### C. Basal Ganglia Procedural Habit Mining
- Identifies repeated sequences of tool usage (e.g., `git status` -> `git diff` -> `git commit`).
- Compiles recurrent chains into fast-path automated execution macros in `memory/habits.json`.

---

## 3. The 4-Tier Memory Hierarchy

| Tier | Module | Storage Medium | Characteristics | Usage |
|---|---|---|---|---|
| **Tier 1: Short-Term Memory (STM)** | `memory/short_term.py` | RAM / Thread-safe data structure | `< 0.01 ms` latency, rolling 50-turn window, entity TTLs | Active ongoing dialogue and scratchpad context. |
| **Tier 2: Prompt Core LTM** | `memory/memory_manager.py` | `memory/long_term.json` | Instant (injected on connect), hard capped at 900 chars | Highest priority operator preferences, identity, key relationships. |
| **Tier 3: Extended Semantic Memory** | `memory/memory_manager.py` & Vector Store | `memory/long_term.json` & `memory/chroma/` | Disk/Vector retrieval, 200,000+ char capacity | Full project histories, reference docs, retrieved via `recall_memory(query)`. |
| **Tier 4: Dynamic Concept Graph** | `plugins/cognitive_neuro_cortex.py` | `memory/concept_graph.json` | Semantic network graph | Associative relationships and connected domain concepts. |

---

## 4. Deterministic Execution Engine

The execution subsystem converts goals into verified outcomes without hallucination or UI lockups.

### A. The Iron Law of Pre-Execution
1. **Never guess**: When dealing with uncertain APIs or schemas, query `list_plugins` or `plugin_describe`.
2. **Standard Playbooks**: For complex workflows, invoke `skill_loader(action="read", skill_name="...")` to load structured instructions (e.g. `systematic-debugging`, `test-driven-development`).
3. **Root Cause First**: Never attempt code fixes without completing Phase 1 of root-cause investigation.

### B. Tool Chaining & Context Forwarding (`plugins/tool_chain.py`)
- Executes multi-stage pipelines where step outputs cascade as inputs to subsequent tools:
  ```python
  tool_chain.run({
      "goal": "Audit and secure network ports",
      "steps": [
          {"tool": "wifi_radar", "params": {"action": "scan"}},
          {"tool": "firewall_warden", "params": {"action": "status"}}
      ]
  })
  ```

### C. Thread-Safe Presentation Protocol (`AGENTS.md`)
- Tools run on background worker threads and **must never touch Qt widgets directly**.
- All telemetry and visuals route via `player`:
  - Telemetry: `player.write_log("message")`
  - Visual Reports: `player.show_content(title, markdown)`
  - Decision Quizzes: `player.show_quiz(topic, questions)`
  - Code/SDLC Reviews: `player.show_review(title, summary, findings)`

---

## 5. Quick Verification & Maintenance Commands

```bash
# Verify active skill inventory
.venv/bin/python -c "import plugins.skill_loader as sl; print(sl.run({'action': 'list'}))"

# Inspect current learned rules
cat memory/learned_rules.json

# Check core prompt memory budget
.venv/bin/python -c "import memory.memory_manager as mm; print(mm.format_memory_for_prompt()[:300])"

# Run memory and tool verification tests
.venv/bin/python -m unittest tests/test_advanced_tools.py -v
```
