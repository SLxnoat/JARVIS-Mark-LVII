---
name: smart-workspace-orchestration
description: "Organize desktop, automate scenes, and plan multi-step tasks."
version: 1.0.0
author: JARVIS Mark-LVII Engineering Core
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [automation, desktop, scenes, task-planner, workspace, cleaning]
    category: automation
    related_skills: [computer-use]
prerequisites:
  plugins: [smart_desktop_cleaner, smart_home_scene_automator, task_planner, tool_chain]
---

# Smart Workspace Orchestration & Environment Automation

End-to-end operational procedure for tidying cluttered desktop directories, executing smart home environmental scenes, and formulating autonomous multi-step goal execution plans.

## When to Use

- Operator asks: *"Clean my downloads folder"*, *"Organize desktop"*, *"Engage focus scene"*, *"Plan this task"*.
- At the start or end of long development sessions to restore desktop order.
- To orchestrate complex ambient states (lighting, audio, display modes) across connected devices.

## The Iron Law

```
DRY-RUN FIRST BEFORE MOVING OR CATEGORIZING FILES
```

Never execute mass file organization operations without running a dry-run preview first to avoid displacing critical active project files.

## Step-by-Step Execution Procedure

### 1. Smart Desktop & Downloads Organization
Intelligently categorize cluttered folders (e.g. `~/Downloads`, `~/Desktop`) into structured directories (`Documents`, `Images`, `Archives`, `Installers`, `Media`):

```python
# Step 1: Preview file moves safely with dry_run
smart_desktop_cleaner(target_dir="~/Downloads", action="scan", dry_run=True)

# Step 2: Execute organization only after operator confirms or when explicitly requested
smart_desktop_cleaner(target_dir="~/Downloads", action="clean", dry_run=False)
```

### 2. Ambient Environment & Scene Automation
Engage pre-configured multi-device scenes (Iron Man style protocols) across smart home peripherals:

```python
# Engage focus/hacking environment
smart_home_scene_automator(protocol="focus")

# Engage relaxation or evening protocol
smart_home_scene_automator(protocol="evening")
```

Protocols adjust ambient lighting color temperatures, mute distracting notifications, and set HUD themes.

### 3. Autonomous Task Formulation & Tool Combiner
When the operator specifies a high-level goal requiring 3+ distinct tools:

```python
# Formulate autonomous execution plan
task_planner(
    goal="Clean ~/Downloads, verify Docker health, and audit workstation security",
    sync=True
)
```

The planner uses Gemini to decompose the objective into executable tool steps and executes them sequentially.

### 4. Direct Pipeline Execution
Alternatively, construct a verified `tool_chain` directly:

```python
tool_chain(
    goal="End of day workspace shutdown",
    steps=[
        {"tool": "smart_desktop_cleaner", "params": {"action": "clean", "dry_run": False}},
        {"tool": "docker_sentinel", "params": {"action": "status"}},
        {"tool": "smart_home_scene_automator", "params": {"protocol": "evening"}}
    ]
)
```

## Presentation & HUD Feedback

- **Spoken response**: Concise voice confirmation (e.g. *"Downloads sorted into 5 categories, 24 files organized, sir."*).
- **HUD telemetry**: Display the before/after organization manifest via `player.show_content("Workspace Cleaner", markdown)`.
- **Activity log**: Post summary via `player.write_log("[Cleaner] Organized 24 files in ~/Downloads.")`.

## Pitfalls & Anti-Patterns

1. **Never touch git repositories or dotfiles**: `.git`, `.venv`, `.env`, and config files must never be moved or archived.
2. **Handle name collisions defensively**: If a file with the target name already exists, append a timestamp rather than overwriting.
