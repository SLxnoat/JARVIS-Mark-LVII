---
name: operator-flowstate-wellness
description: "Manage Pomodoro focus, hydration, nutrition, and notes."
version: 1.0.0
author: JARVIS Mark-LVII Engineering Core
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [focus, pomodoro, flowstate, hydration, nutrition, obsidian, wellness]
    category: personal
    related_skills: [autonomous-learning]
prerequisites:
  plugins: [pomodoro, focus_flowstate_guardian, water_reminder, calorie_counter, obsidian_vault]
---

# Operator Flow-State & Physical Wellness Protocols

End-to-end operational procedure for protecting cognitive focus, scheduling Pomodoro intervals, tracking physical hydration and nutrition, and recording insights into Obsidian.

## When to Use

- Operator asks: *"Start a 25-minute focus session"*, *"Log my water intake"*, *"Count calories for this meal"*, *"Take a note in Obsidian"*, *"Block distractions"*.
- During high-intensity programming sprints to prevent cognitive burnout.
- When capturing spontaneous architectural thoughts without interrupting work.

## The Iron Law

```
NEVER INTERRUPT ACTIVE FLOW-STATE FOR NON-CRITICAL NOTIFICATIONS
```

When flow-state mode is engaged, suppress all low-priority alerts, background reminders, and non-urgent chatter.

## Step-by-Step Execution Procedure

### 1. Engage Cognitive Flow-State Guardian
Shield the workspace from cognitive fragmentation by silencing non-essential notifications and closing distraction tabs:

```python
# Engage focus shields for 45 minutes
focus_flowstate_guardian(action="engage", duration_minutes=45)

# Start synchronized Pomodoro timer
pomodoro(action="start", duration_minutes=45)
```

### 2. Hydration & Physical Maintenance Tracking
Log water intake to maintain peak mental acuity throughout the work cycle:

```python
# Log a glass of water (250 ml)
water_reminder(action="log", amount_ml=250)

# Check daily hydration progress
water_reminder(action="status")
```

### 3. Nutrition & Meal Macro Analysis
Track energy intake by estimating calories and macronutrients:

```python
# Estimate calories from meal description
calorie_counter(
    description="Grilled salmon with brown rice and steamed broccoli",
    meal_type="lunch"
)
```

### 4. Spontaneous Note Ingestion (Obsidian Vault)
Capture architectural insights, ideas, or meeting takeaways directly into the operator's personal knowledge base:

```python
# Append note to daily or project log
obsidian_vault(
    action="append",
    title="Engineering Log",
    content="Decided to adopt Anthropic progressive disclosure for all JARVIS skills."
)

# Search existing knowledge
obsidian_vault(action="search", query="systematic debugging")
```

## Presentation & HUD Feedback

- **Spoken response**: Subtle, respectful confirmation (e.g. *"Focus shields engaged for 45 minutes. Distractions suppressed, sir."*).
- **HUD telemetry**: Display timer countdown and daily hydration gauge using `player.show_content("Focus & Wellness", markdown)`.
- **Activity log**: Post event via `player.write_log("[Focus] Pomodoro active: 45m.")`.

## Pitfalls & Anti-Patterns

1. **Do not nag**: If the operator is in a deep coding flow, do not pop loud audio alarms for routine hydration; use a subtle visual indicator on the HUD.
2. **Respect user privacy**: Nutritional notes and personal logs must remain local to the user's filesystem (`memory/` and Obsidian vault).
