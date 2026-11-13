---
name: autonomous-learning
description: "Self-learning, memory retention, and execution lifecycle."
version: 1.0.0
author: JARVIS Mark-LVII Engineering Core
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [learning, memory, knowledge-retention, execution, self-improvement]
    category: learning-and-memory
    related_skills: [systematic-debugging, test-driven-development]
---

# Autonomous Learning, Memorization & Execution Lifecycle

Comprehensive operational protocol for JARVIS self-learning, multi-tier knowledge storage, memory synthesis, and high-precision execution.

---

## 1. Architectural Overview: The 3-Tier Cognitive Loop

```
+-----------------------------------------------------------------------------------+
|                              1. INGESTION & LEARNING                              |
|   User Correction / Critique / New Fact / Procedural Habit / Environmental Input  |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                              2. MULTI-TIER MEMORIZATION                           |
|   • Level 1: Working / Short-Term Memory (STM) [<0.01ms rolling cache]             |
|   • Level 2: Core Long-Term Memory (LTM) [~900 chars high-priority prompt budget]  |
|   • Level 3: Extended Semantic Store & Concept Graph [Vector search & JSON mesh]  |
|   • Level 4: Neuro-Cortex Plasticity [Learned behavioral rules & habit mining]    |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                              3. DETERMINISTIC EXECUTION                           |
|   • Iron Law Pre-check: Root cause & verification before action                   |
|   • Tool Chaining & Sequential Telemetry (Structured Pipelines)                   |
|   • Thread-safe HUD feedback (player.show_content, player.write_log)              |
|   • Post-execution outcome evaluation & self-reinforcement                        |
+-----------------------------------------------------------------------------------+
```

---

## 2. Ingestion & Self-Learning (How JARVIS Learns)

### A. Dopaminergic Error Plasticity (Learning from Corrections)
Whenever the user corrects an error, refines a command, or establishes a preference:
1. **Never argue or apologize repeatedly.** Accept the correction immediately.
2. Ingest the correction into permanent behavioral guidelines:
   - Call `cognitive_neuro_cortex(action="learn_rule", rule_trigger="...", rule_action="...")`
   - Example trigger: *"When compiling Rust targets..."* -> action: *"Always use --release mode."*
3. The rule is written to `memory/learned_rules.json` and injected into execution contexts automatically.

### B. Procedural Habit Mining (Basal Ganglia)
When repetitive multi-tool command sequences are executed:
- Frequency and sequence of tools are monitored.
- Patterns exceeding threshold frequency are consolidated into execution macros (`memory/habits.json`).

### C. Fact & Entity Ingestion
- Identity, preferences, project updates, and relationship milestones must be routed to `memory/memory_manager.py`.
- Call: `save_memory(category="preferences" | "projects" | "identity", key="...", value="...")`

---

## 3. Memorization Architecture (Where Knowledge Lives)

| Memory Layer | Storage Location | Latency & Budget | Purpose |
|---|---|---|---|
| **Tier 1: Short-Term Memory (STM)** | `memory/short_term.py` (In-memory) | `< 0.01 ms` / Rolling 50 turns | Active dialogue, entities with turn TTLs, scratchpad. |
| **Tier 2: Prompt Core LTM** | `memory/long_term.json` | Instant (bootstrapped into prompt) / Max 900 chars | Highest priority preferences, names, critical rules. |
| **Tier 3: Extended Deep Memory** | `memory/long_term.json` + `chroma/` | Disk lookup on demand / 200,000+ chars | Searchable archive fetched via `recall_memory(query="...")`. |
| **Tier 4: Learned Rules & Mesh** | `memory/learned_rules.json` & `concept_graph.json` | Structured JSON graph | Neuro-plastic behavioral rules and associative entity concepts. |

---

## 4. Execution Workflow (The Action Phase)

### A. Pre-Execution Validation (The Iron Law)
Before executing mutating actions (file edits, system reboots, external API writes):
1. **Check Learned Rules**: Query active rules for domain-specific constraints.
2. **Context Grounding**: Verify target path, environment variables, and tool parameters via `plugin_describe` or `list_plugins`.
3. **No Guessing**: If uncertainty exists, consult `skill_loader(action="read", skill_name="...")` for the standard procedure.

### B. Sequential Tool Chaining
For complex multi-action tasks:
- Structure tool steps sequentially using `tool_chain`:
  ```json
  tool_chain(goal="Deploy service", steps=[
      {"tool": "docker_sentinel", "params": {"action": "status"}},
      {"tool": "firewall_warden", "params": {"action": "check_port", "port": 8080}}
  ])
  ```
- Output from Step $N$ automatically feeds downstream tools.

### C. Non-Blocking Thread-Safe Presentation
- **Never create or touch PyQt widgets directly** on worker threads (`AGENTS.md`).
- Pass all visual and log updates through the thread-safe `player` proxy:
  - `player.write_log(text)`: Concise telemetry.
  - `player.show_content(title, markdown)`: Deep formatted reports and data.
  - `player.show_quiz(topic, questions)`: Interactive quizzes.
  - `player.show_review(title, summary, findings)`: Structured audits.

---

## 5. Quick Reference & Playbook Commands

| Action | Built-in Plugin / Tool | Example Invocation |
|---|---|---|
| **List Skills** | `skill_loader` | `skill_loader(action="list")` |
| **Read Skill Guide** | `skill_loader` | `skill_loader(action="read", skill_name="systematic-debugging")` |
| **Ingest Rule** | `cognitive_neuro_cortex` | `cognitive_neuro_cortex(action="learn_rule", rule_trigger="...", rule_action="...")` |
| **Consolidate Memory**| `cognitive_neuro_cortex` | `cognitive_neuro_cortex(action="consolidate")` |
| **Save Persistent Fact**| `save_memory` | `save_memory(category="projects", key="name", value="details")` |
| **Recall Deep Memory**| `recall_memory` | `recall_memory(query="deployment architecture")` |
| **Pipeline Execute** | `tool_chain` | `tool_chain(goal="...", steps=[...])` |
