---
name: workstation-security-audit
description: "Audit Linux workstation security, containers, and ports."
version: 1.0.0
author: JARVIS Mark-LVII Engineering Core
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [security, firewall, docker, systemd, forensics, audit]
    category: system-ops
    related_skills: [systematic-debugging]
prerequisites:
  plugins: [firewall_warden, docker_sentinel, process_forensics, systemd_sentinel, network_topology]
---

# Workstation Security Audit & Defensive Hardening

End-to-end operational procedure to audit workstation packet filtering, running containers, hidden listening sockets, and high-resource or rogue system processes.

## When to Use

- Operator asks: *"Audit my workstation security"*, *"Check open ports"*, *"Inspect running containers"*.
- After unexpected network latency or unusual system load spikes.
- Routine defensive baseline check before and after major deployments.

## The Iron Law

```
NEVER MODIFY FIREWALL RULES OR KILL SERVICES WITHOUT OPERATOR APPROVAL
```

Discovery, inspection, and telemetry gathering are read-only. Report findings first; confirm before taking destructive mitigation actions.

## Step-by-Step Execution Procedure

### 1. Audit Packet Filtering & Open Ports
Scan active firewall tables (iptables/nftables/ufw) and listening socket bindings:

```python
# Check workstation firewall status
firewall_warden(action="status")

# Inspect local listening sockets and network topology
network_topology(action="scan", target_ip="127.0.0.1")
```

Verify whether ports like `22` (SSH), `2375` (Docker daemon unencrypted), `8080`, or database ports are exposed externally.

### 2. Inspect Container Fleet
Verify container health, running images, open port bindings, and unhealthy restarts:

```python
# Check container status across Docker and Podman
docker_sentinel(action="status")
```

If suspicious containers are discovered, pull detailed telemetry:
```python
docker_sentinel(action="inspect")
```

### 3. Process Tree & Zombie/Rogue Inspection
Run forensic analysis across the active process tree to spot hidden CPU spikes, orphan background processes, or memory leaks:

```python
# Inspect process anomalies, zombies, and high-resource consumers
process_forensics(action="inspect")
```

### 4. Systemd Daemon Health Check
Inspect failed or degraded units in the user and system managers:

```python
# Check failed systemd services
systemd_sentinel(action="failed")
```

### 5. Multi-Tool Pipeline Automation
For a comprehensive single-turn audit, execute the sequential tool pipeline:

```python
tool_chain(
    goal="Comprehensive Workstation Security Audit",
    steps=[
        {"tool": "firewall_warden", "params": {"action": "status"}},
        {"tool": "docker_sentinel", "params": {"action": "status"}},
        {"tool": "process_forensics", "params": {"action": "inspect"}},
        {"tool": "systemd_sentinel", "params": {"action": "failed"}}
    ]
)
```

## Presentation & HUD Feedback

- **Spoken response**: 1-2 concise sentences summarizing the posture (e.g. *"Firewall active, 4 containers healthy, no degraded systemd units detected, sir."*).
- **HUD telemetry**: Route the structured markdown review to the tactical panel via `player.show_review("Security Audit", summary, findings)`.
- **Activity log**: Post status line via `player.write_log("️ [SecurityAudit] Workstation posture nominal.")`.

## Pitfalls & Anti-Patterns

1. **Do not run `kill -9` blindly**: If a rogue process is identified, present the PID and command line to the operator first.
2. **Never expose Docker socket**: Ensure `docker_sentinel` does not report `/var/run/docker.sock` mounted into untrusted containers.
3. **Respect user containers**: Do not restart or stop user containers without explicit instruction.
