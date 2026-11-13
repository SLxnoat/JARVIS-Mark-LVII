---
name: architectural-refactoring
description: "Map codebase architecture, sandbox test, and manage Git."
version: 1.0.0
author: JARVIS Mark-LVII Engineering Core
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [architecture, refactoring, git, sandbox, testing, development]
    category: development
    related_skills: [test-driven-development, systematic-debugging, codebase-inspection]
prerequisites:
  plugins: [code_architecture_mapper, code_debugger_sandbox, git_workspace, ai_terminal_copilot]
---

# Architectural Refactoring & Code Hygiene

End-to-end engineering procedure for safely restructuring codebase modules, analyzing abstract syntax trees (AST), running candidate changes in an isolated sandbox, and committing clean git histories.

## When to Use

- Operator asks: *"Analyze project architecture"*, *"Refactor this module"*, *"Check git repo status"*, *"Test this snippet safely"*.
- When a god-file exceeds 1,500 lines and needs decomposition into facades and topical siblings.
- Before committing code changes to verify zero regressions.

## The Iron Law

```
NO REFACTORING WITHOUT RUNNING SANDBOXED VERIFICATION FIRST
```

Never rewrite production files in-place without verifying the candidate logic in `code_debugger_sandbox` or running automated unit tests.

## Step-by-Step Execution Procedure

### 1. Map Codebase Structure & Dependencies
Generate an AST-level dependency map of classes, public methods, and circular imports before changing any code:

```python
# Map project architecture and dependencies
code_architecture_mapper(target_dir=".")
```

Identify:
- Core facades vs. helper modules.
- Tight coupling between modules that violate the Single Responsibility Principle.

### 2. Verify Working Tree & Git Hygiene
Before starting changes, verify that the git working tree is clean and on the expected branch:

```python
# Check local Git workspace status
git_workspace(action="status")
```

If uncommitted changes exist, check diffs with `git_workspace(action="diff")` before modifying files.

### 3. Isolated Sandbox Execution
When developing new algorithms or refactoring tricky transformation logic, run candidate snippets in the isolated debugger sandbox:

```python
# Test Python snippet with automatic error repair
code_debugger_sandbox(
    code="""
def refactored_parser(payload):
    import json
    return json.loads(payload)
print(refactored_parser('{"status": "ok"}'))
""",
    max_repair_attempts=2
)
```

### 4. Code Generation & AGENTS.md Compliance Check
When writing new code for JARVIS:
- **No Qt widgets on worker threads**: Ensure all UI calls go through `player` methods.
- **Fast return**: Plugins must return short spoken feedback within 3 seconds.
- **Never raise**: Catch all exceptions and return clean error descriptions.

### 5. Automated Regression Test Execution
Run test suites using terminal execution:

```bash
.venv/bin/python -m unittest tests/test_advanced_tools.py -v
```

### 6. Clean Commit & Handover
Once all tests pass, stage and commit the changes cleanly following the conventional commits standard (`feat:`, `fix:`, `refactor:`, `test:`).

## Presentation & HUD Feedback

- **Spoken response**: Direct summary of architectural changes (e.g. *"Refactoring complete. 3 modules decoupled, all 17 unit tests passing."*).
- **HUD telemetry**: Display the architectural diff or AST tree using `player.show_content("Architecture Map", markdown)`.
- **Activity log**: Post commit hash via `player.write_log("[Refactor] Codebase restructured cleanly.")`.

## Pitfalls & Anti-Patterns

1. **Never commit broken tests**: If a test fails after refactoring, revert to the last working commit immediately.
2. **Avoid gratuitous formatting churn**: Do not reformat entire files unrelated to the refactoring task.
3. **Keep facades backward-compatible**: When moving functions into siblings, re-export public APIs through the facade.
