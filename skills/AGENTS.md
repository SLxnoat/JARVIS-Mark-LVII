# skills/ — Skill Execution & Authoring Instructions for JARVIS

This instruction manual governs how JARVIS autonomously **discovers, learns, memorizes, and executes** specialized skills and knowledge playbooks, adhering to the Anthropic (`anthropics/skills`) and Hermes Agent standards.

---

## 1. Skill Discovery & Invocation Lifecycle

When resolving user instructions or complex tasks, follow the 3-step progressive execution lifecycle:

### Step 1: Scan Frontmatter (Lightweight Index)
Never load full markdown manuals into active working context blindly.
- Check available skills:
  ```python
  skill_loader(action="list")
  ```
- Look up target skills by category (`[DESKTOP]`, `[SOFTWARE-DEVELOPMENT]`, `[LEARNING-AND-MEMORY]`, `[RESEARCH]`, `[DEVOPS]`, `[WEB]`).

### Step 2: Load Procedure on Demand
When a task matches a skill's scope (e.g. debugging a failure, refactoring, running desktop actions, ingesting user rules):
- Read the full procedure playbook:
  ```python
  skill_loader(action="read", skill_name="<name>")
  ```
- Absorb the **Iron Law**, **Prerequisites**, and **Step-by-step Procedures**.

### Step 3: Execute with Verified Telemetry
- Execute the actions using JARVIS tools (`tool_chain`, `actions/*`, `plugins/*`).
- Post progress directly to the HUD via thread-safe proxies (`player.write_log`, `player.show_content`).
- Never violate the skill's explicit constraints.

---

## 2. Ingestion & Learning Protocols (Handling User Inputs & Feedback)

Whenever the user provides corrections, new facts, or workflow rules:

### A. Learning Rules (Dopaminergic Error Plasticity)
When the user corrects a mistake or sets an operational preference:
1. **Never argue or apologize.**
2. Ingest the rule immediately via:
   ```python
   cognitive_neuro_cortex(
       action="learn_rule",
       rule_trigger="When <context/condition>",
       rule_action="Always <required behavior>"
   )
   ```
3. The rule is committed to `memory/learned_rules.json` and governs all future actions.

### B. Ingesting Semantic Facts & Entities
When the user mentions projects, personal details, or preferences:
- Call `save_memory(category="projects"|"preferences"|"identity", key="<key>", value="<value>")`.
- Persists to `memory/long_term.json`.

---

## 3. Memory Retrieval & Context Budget Rules

Knowledge is partitioned into 4 distinct layers:

1. **Short-Term Memory (STM - `memory/short_term.py`)**:
   - Active dialogue turns and rolling entity state (<0.01 ms latency).
2. **Core Prompt Memory (`memory/long_term.json`)**:
   - Capped at **900 characters** in the base prompt. Contains only highest-priority operator identity and top rules.
3. **Deep Extended Memory (`chroma/` & disk)**:
   - For historical queries or large reference data, fetch on demand:
     ```python
     recall_memory(query="<search terms>")
     ```
4. **Associative Concept Graph (`memory/concept_graph.json`)**:
   - Connected entity mesh queried via `cognitive_neuro_cortex(action="query_concept", concept="...")`.

---

## 4. Execution Discipline & Standards

### A. The Iron Law of Debugging
```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```
- If a bug occurs, load `systematic-debugging`.
- Complete **Phase 1: Root Cause Investigation** before attempting any code change.
- Never make blind guesses or patch symptoms.

### B. Test-Driven Development (TDD)
```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```
- For new features or non-trivial fixes, load `test-driven-development`.
- Follow strict **RED -> GREEN -> REFACTOR**.

### C. Background-First Desktop Automation
- When driving the user's desktop, consult `computer-use`.
- Favor background interaction (`screen_agent`, direct command tools) over stealing mouse/keyboard focus.

### D. Thread Safety & Presentation (Qt Boundary)
- **NEVER create or touch Qt widgets directly on worker threads.**
- All UI feedback must pass through thread-safe `player` methods:
  - `player.write_log(text)`
  - `player.show_content(title, text)`
  - `player.show_quiz(topic, questions)`
  - `player.show_review(title, summary, findings)`

---

## 5. Authoring New Skills for JARVIS

When creating a new skill under `skills/<category>/<skill-name>/SKILL.md`:

1. **Frontmatter Specification**:
   ```yaml
   ---
   name: <skill-name>
   description: "<One sentence <= 60 chars ending with a period.>"
   version: 1.0.0
   author: <Author Name>, JARVIS Core
   license: MIT
   platforms: [linux, macos, windows]
   metadata:
     hermes:
       tags: [tag1, tag2]
       category: <category-name>
       related_skills: [other-skill]
   ---
   ```
2. **Description Rule**: Exactly one sentence, maximum 60 characters, ending with a period.
3. **Required Section Layout**:
   - `# <Skill Name>`
   - `## Overview`
   - `## The Iron Law / Core Principle`
   - `## When to Use`
   - `## Step-by-Step Procedure`
   - `## Pitfalls & Anti-Patterns`
   - `## Verification & Next Steps`
4. **Helper Scripts**: Place complex parsers or scripts inside `skills/<category>/<skill-name>/scripts/` instead of asking the model to write inline scripts repeatedly.
