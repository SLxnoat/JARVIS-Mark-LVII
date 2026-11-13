# JARVIS Mark-LVII: Comprehensive Architecture, Safety & Feature Gap Audit

**Date:** November 13, 2026  
**Auditor:** Antigravity Autonomous Systems Architect  
**Scope:** Architecture (`core/`, `actions/`, `plugins/`, `gui/`, `memory/`, `skills/`, `tests/`)  
**Compliance Standard:** Hermes Agent & Anthropic Standards (`AGENTS.md`)

---

## Executive Summary

JARVIS Mark-LVII has reached an advanced stage of maturity, boasting 73 active plugins, 23 built-in actions, an AR point-cloud HUD with head parallax tracking, a 4-tier memory hierarchy, and Anthropic/Hermes progressive disclosure skills.

However, a strict gap audit against production standards reveals **7 critical gaps** spanning test regression drift, background thread lifecycle leaks, external API polling collisions, and context window optimizations.

---

## 1. Audit Matrix & Gap Severity Assessment

| # | Gap Area | Severity | Impact | Status |
|---|---|---|---|---|
| **GAP-01** | Unit Test Assertion Drift (Outdated Asserts on Inlined Tools) | **Medium** | Breaks automated regression test suites (`test_20_cool_plugins`, `test_new_high_tech_plugins`). | Actionable Fix Available |
| **GAP-02** | Telegram Bridge Polling Collision (HTTP 409 Conflict) | **Medium** | Log pollution & dropped inbound messages when multiple instances or test suites run. | Actionable Fix Available |
| **GAP-03** | Display Server Headless Execution Crash (GLib/GIO xsettings) | **High (CI)** | Headless CI/test runs abort when Qt initializes without `QT_QPA_PLATFORM=offscreen`. | Actionable Fix Available |
| **GAP-04** | Deprecated Dependency Warning (`pynvml` vs `nvidia-ml-py`) | **Low** | Console warning on startup; potential breaking deprecation in future Python/driver releases. | Actionable Fix Available |
| **GAP-05** | Lack of Background Worker Thread Cancellation in Plugins | **Medium** | Async plugins that spawn daemon threads lack explicit timeout/cooperative cancellation tokens. | Structural Optimization |
| **GAP-06** | Extended Context Window Budgeting in Prompt Ingestion | **Low** | `memory/memory_manager.py` respects 900 chars, but raw plugin parameter descriptions lack compaction. | Structural Optimization |
| **GAP-07** | Automated Skill Usage Telemetry (`.usage.json`) | **Low** | Skills are loaded on demand, but invocation counters/recency tracking (Hermes Curator pattern) are pending. | Enhancement Opportunity |

---

## 2. Detailed Gap Analysis & Technical Root Causes

### GAP-01: Unit Test Assertion Drift
- **Root Cause**: During Phase 2, `pci_hardware_radar.py` and `multilingual_live_translator.py` were optimized to return real factual data directly to Gemini Live instead of static stub phrases (*"Translating in the background..."*).
- **The Gap**: Older test files (`test_new_high_tech_plugins.py` and `test_20_cool_plugins.py`) still assert on obsolete stub words (`"radar"`, `"translating"`).
- **Fix**: Update the 2 assertions to match the calibrated factual returns.

### GAP-02: Telegram Bridge Polling Collision (HTTP 409)
- **Root Cause**: `plugins/telegram_bridge.py` polls `getUpdates` with the bot token. If tests or another daemon instance run concurrently, Telegram rejects with `409 Conflict: terminated by other getUpdates request`.
- **The Gap**: No singleton lock or `skip_polling_if_testing` flag in `telegram_bridge.py`.
- **Fix**: Detect test environments (`sys.argv` or `PYTEST_CURRENT_TEST`) and suppress live polling during test execution.

### GAP-03: Headless Test Display Crash (GLib-GIO xsettings)
- **Root Cause**: On Linux workstations running GNOME/Wayland/X11, running `python -m unittest` without an active virtual frame causes `GLib-GIO-ERROR: Settings schema '...xsettings' does not contain a key named 'antialiasing'` when PyQt6 loads fonts.
- **The Gap**: Tests inheriting from `unittest.TestCase` that touch UI modules do not automatically set `os.environ["QT_QPA_PLATFORM"] = "offscreen"`.
- **Fix**: Enforce `QT_QPA_PLATFORM=offscreen` in test setup fixtures.

### GAP-04: Deprecated NVML Package
- **Root Cause**: `gui/metrics.py` imports `pynvml` for GPU telemetry.
- **The Gap**: NVIDIA has deprecated `pynvml` in favor of `nvidia-ml-py`.
- **Fix**: Replace `pynvml` import with fallback to `nvidia-ml-py`.

### GAP-05: Unbounded Thread Spawning in Audio/Sensor Plugins
- **Root Cause**: Plugins like `audio_spectrum_analyzer.py` and `air_quality_sentinel.py` spawn bare `threading.Thread(daemon=True)`.
- **The Gap**: While compliant with `AGENTS.md` (non-blocking), they do not track thread handles or allow cooperative cancellation when the user interrupts or speaks.
- **Fix**: Introduce a centralized `_ThreadExecutorPool` in `core/` to register and cancel active worker tasks.

### GAP-06: Tool Description Token Footprint
- **Root Cause**: With 73 plugins, injecting all tool JSON schemas into Gemini on every turn consumes substantial tokens.
- **The Gap**: While `list_plugins` provides progressive discovery, all 73 are currently registered into the function declarations list.
- **Fix**: Implement selective tool tiering (Hermes Core vs. Edge Tools) where only top 15 core tools load initially, and edge tools are loaded dynamically via `list_plugins`.

### GAP-07: Skill Curator & Telemetry Tracking
- **Root Cause**: The new `skills/` architecture provides progressive disclosure via `skill_loader`, but does not yet record usage frequency in `memory/skills_usage.json`.
- **The Gap**: Without usage telemetry, stale or rarely used skills cannot be prioritized or archived automatically.
- **Fix**: Add a simple usage counter increment to `plugins/skill_loader.py` on every `action="read"`.

---

## 3. Recommended Remediation Roadmap

1. **Immediate (P0 - Code Health)**:
   - Synchronize test assertions in `test_new_high_tech_plugins.py` and `test_20_cool_plugins.py`.
   - Add `QT_QPA_PLATFORM=offscreen` fallback in test harnesses.
   - Suppress Telegram long-polling during automated test runs.
2. **Short-Term (P1 - Stability)**:
   - Migrate `gui/metrics.py` to `nvidia-ml-py`.
   - Add usage telemetry logging to `plugins/skill_loader.py`.
3. **Long-Term (P2 - Scalability)**:
   - Implement dynamic tool set swapping (Core 15 + Edge on-demand) to reduce system prompt token consumption.
