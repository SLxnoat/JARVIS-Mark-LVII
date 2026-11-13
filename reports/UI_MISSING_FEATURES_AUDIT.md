# JARVIS Mark-LVII: UI Missing Features & Ergonomic Gap Audit

**Date:** November 13, 2026  
**Auditor:** Antigravity Autonomous Systems Architect  
**Scope:** `gui/` package (`window.py`, `hud.py`, `tactical_radar.py`, `synaptic_board.py`, `mission_capsules.py`, `command_spotlight.py`, `radial_wheel.py`)  
**Design Reference:** Iron Man Mk LVII AR Vibe UI & Ergonomics Spec

---

## Executive Summary

The JARVIS Mark-LVII GUI has achieved an impressive cybernetic aesthetic featuring a 3D parallax head tracking avatar, animated ambient lighting, collapsible drawers, and modal overlays.

However, a strict gap audit comparing the user interface against the AR UI Implementation Checklist and real-world multi-modal operation reveals **6 notable missing features or incomplete integrations**.

---

## 1. UI Feature Gap Matrix

| # | Feature Area | Severity | Current Status | What's Missing / Incomplete |
|---|---|---|---|---|
| **UI-GAP-01** | **Direct Spotlight Tool Dispatch** | **High** | Partial Stub | Selecting a plugin in Universal Command Spotlight (`Ctrl+K`) only writes a log entry; it does not actually prompt the parameters or trigger execution. |
| **UI-GAP-02** | **Radial Wheel Direct Tool Execution** | **Medium** | Partial (Text only) | Selecting "Terminal", "Browser", or "Settings" nodes on the radial pie menu prints static text instead of launching the dedicated views. |
| **UI-GAP-03** | **Interactive AR Browser Surface** | **High** | Headless / Image Only | `inbuilt_hud_browser` projects screenshots via `show_image()`, but lacks a dedicated on-canvas interactive projection viewport with URL bar, click coordinates, and scroll navigation controls. |
| **UI-GAP-04** | **Sub-HUD Panel Tab / Switcher Bar** | **Medium** | Splitter Auto-Reveal | Sub-HUD panels (Content, Quiz, Radar, Synaptic Board, Mission Control) share a single vertical splitter. Switching between them requires manual shortcuts or voice commands; there is no persistent mini tab/dock bar. |
| **UI-GAP-05** | **Audio Input/Output Live Level Meter** | **Low** | State Dot Only | While `CognitiveTelemetry` visualizes arcs and wave ripples, the HUD lacks a dedicated dB VU meter showing real-time microphone gain and speaker output levels. |
| **UI-GAP-06** | **Active Plugin Quick-Toggle Status Pills** | **Low** | Buried in Setup Drawer | 73 plugins are active, but there are no quick status indicators on the HUD or drawer to see which background sentinels are currently running vs. idle. |

---

## 2. Deep Dive Analysis into Top Missing Features

### UI-GAP-01: Command Spotlight Direct Execution
- **Current Behavior**:
  ```python
  elif cmd_id.startswith("plugin_"):
      plugin_name = cmd_id[len("plugin_"):]
      self._log.append_log(f"SYS: Invoked plugin {plugin_name}")
  ```
- **The Missing Piece**: It logs that the plugin was selected, but does not prefill the input row (`self._input.setText(f"Run {plugin_name}...")`), open `plugin_describe`, or dispatch to the running session.
- **Recommended Fix**: Auto-populate the command input bar with the plugin trigger syntax and set focus so the user can immediately hit Enter.

### UI-GAP-02: Radial Wheel Node Action Wiring
- **Current Behavior**:
  ```python
  elif node_id == "browser":
      self._show_content("Web Browser", "Browser interface ready. Open links or invoke web search.")
  elif node_id == "terminal":
      self._show_content("Autonomous Dev Sandbox", "Dev agent & sandbox ready for instruction.")
  ```
- **The Missing Piece**: Selecting "browser" should either bring up the `inbuilt_hud_browser` prompt or activate web research; selecting "terminal" should open the dev agent coding panel.

### UI-GAP-03: Floating AR Browser Viewport
- **Current Behavior**: Browser screenshots are projected into the central avatar slot as a static 2D image via `player.show_image()`.
- **The Missing Piece**: A dedicated holographic browser overlay pane (`gui/browser_viewport.py`) that features:
  - Cyan neon framing with URL header and SSL badge.
  - Interactive click coordinates feedback.
  - Mini navigation controls (Back, Forward, Refresh, Close).

### UI-GAP-04: Sub-HUD Dock / Tab Bar
- **Current Behavior**: The center column displays `self._center_split` containing 6 stacked widgets (`_content_panel`, `_quiz_panel`, `_radar_panel`, `_synaptic_panel`, `_mission_panel`). When one opens, it hides the others, but there are no visual tabs to switch back.
- **The Missing Piece**: A cybernetic breadcrumb/tab bar beneath the avatar (e.g. `[ CONTENT | RADAR | SYNAPSE | MISSIONS | QUIZ ]`) allowing one-click switching between active operational boards.

---

## 3. Recommended Implementation Plan

1. **Phase A (Immediate - High Impact)**:
   - Wire Command Spotlight plugin selections to auto-populate the command prompt line.
   - Wire Radial Wheel nodes ("browser", "terminal") to trigger actual plugin runs or agent interfaces.
2. **Phase B (Ergonomics)**:
   - Add a sleek mini navigation tab bar on top of the sub-HUD panels for switching between Content, Tactical Radar, Synaptic Board, and Mission Control.
