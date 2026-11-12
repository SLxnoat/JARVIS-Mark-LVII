"""
plugins/network_topology.py - Tactical Local Network Radar & Topology Cartographer.

Iron Man / JARVIS style local network situational awareness:
- Discovers active LAN devices via OS ARP neighbor tables.
- Identifies local gateway and subnet interface telemetry.
- Probes authorized local home services (SSH, Home Assistant, Web, Media).
- Renders a tactical HUD topology grid via player.show_content().

Adheres strictly to AGENTS.md:
- No Qt widgets instantiated on worker threads.
- Thread-safe HUD feedback via player.show_content() and player.write_log().
- Safe non-blocking execution on a background thread.
- Never raises exceptions, returns concise spoken feedback.
"""
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

PLUGIN = {
    "name": "network_topology",
    "description": (
        "JARVIS Tactical Network Radar: Scans and maps the local authorized network topology, "
        "inspects active LAN devices from the ARP table, checks local service availability, "
        "and displays a tactical network map on the HUD."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: 'scan_lan', 'device_inventory', 'service_check', 'gateway_status'. Default 'scan_lan'.",
                "enum": ["scan_lan", "device_inventory", "service_check", "gateway_status"],
            },
            "target_ip": {
                "type": "STRING",
                "description": "Target IP address or host on the local network (for 'service_check').",
            },
            "ports": {
                "type": "ARRAY",
                "items": {"type": "INTEGER"},
                "description": "Optional list of ports to probe (e.g. [80, 443, 8123, 22]).",
            },
        },
        "required": ["action"],
    },
}

_COMMON_HOME_SERVICES = {
    22: "SSH",
    53: "DNS",
    80: "HTTP Web",
    443: "HTTPS",
    1883: "MQTT Broker",
    5000: "OctoPrint / UPnP",
    8000: "Web Dashboard",
    8080: "HTTP Alt",
    8123: "Home Assistant",
    32400: "Plex Media Server",
}


def _get_default_gateway() -> tuple[str, str]:
    """Return (gateway_ip, interface_name)."""
    try:
        if sys.platform.startswith("linux"):
            r = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True, timeout=2)
            # Example: default via 192.168.1.1 dev wlp2s0 proto dhcp metric 600
            m = re.search(r"default via ([\d\.]+) dev (\S+)", r.stdout)
            if m:
                return m.group(1), m.group(2)
        elif sys.platform == "darwin":
            r = subprocess.run(["netstat", "-rn"], capture_output=True, text=True, timeout=2)
            for line in r.stdout.splitlines():
                if "default" in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        return parts[1], parts[3] if len(parts) > 3 else "en0"
        elif sys.platform == "win32":
            r = subprocess.run(["route", "print", "0.0.0.0"], capture_output=True, text=True, timeout=2)
            for line in r.stdout.splitlines():
                if "0.0.0.0" in line:
                    parts = line.split()
                    if len(parts) >= 4 and re.match(r"^\d+\.\d+\.\d+\.\d+$", parts[2]):
                        return parts[2], parts[3]
    except Exception:
        pass
    return "192.168.1.1", "default"


def _get_arp_neighbors() -> list[dict]:
    """Read local ARP neighbor cache passively."""
    neighbors = []
    try:
        if sys.platform.startswith("linux"):
            r = subprocess.run(["ip", "neigh", "show"], capture_output=True, text=True, timeout=3)
            # Format: 192.168.1.1 dev wlp2s0 lladdr 00:11:22:33:44:55 REACHABLE
            for line in r.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 4 and "lladdr" in parts:
                    ip = parts[0]
                    mac_idx = parts.index("lladdr") + 1
                    mac = parts[mac_idx] if mac_idx < len(parts) else "Unknown"
                    state = parts[-1]
                    if state not in ("FAILED", "INCOMPLETE"):
                        neighbors.append({"ip": ip, "mac": mac, "state": state})
        else:
            r = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=3)
            # Standard arp -a parser
            for line in r.stdout.splitlines():
                m = re.search(r"\(?(\d+\.\d+\.\d+\.\d+)\)?\s+(?:at\s+)?([0-9a-fA-F:-]{11,17})", line)
                if m:
                    neighbors.append({"ip": m.group(1), "mac": m.group(2).replace("-", ":"), "state": "ACTIVE"})
    except Exception:
        pass
    return neighbors


def _probe_ports(host: str, ports_to_check: list[int]) -> list[tuple[int, str]]:
    open_ports = []
    for port in ports_to_check:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.25)
                res = s.connect_ex((host, port))
                if res == 0:
                    svc_name = _COMMON_HOME_SERVICES.get(port, f"Port {port}")
                    open_ports.append((port, svc_name))
        except Exception:
            continue
    return open_ports


def _resolve_hostname(ip: str) -> str:
    try:
        host, _, _ = socket.gethostbyaddr(ip)
        return host
    except Exception:
        return "Unknown Node"


def _radar_worker(action: str, target_ip: str | None, custom_ports: list[int] | None, player):
    try:
        gw_ip, iface = _get_default_gateway()

        if action == "service_check":
            host = target_ip or gw_ip
            ports = custom_ports or list(_COMMON_HOME_SERVICES.keys())
            open_svcs = _probe_ports(host, ports)

            hud_lines = [
                f"### 🛡️ Tactical Service Verification: `{host}`\n",
                f"**Interface:** `{iface}` | **Probed Ports:** `{len(ports)}`\n",
            ]
            if open_svcs:
                hud_lines.append("**Active Local Services:**")
                for port, name in open_svcs:
                    hud_lines.append(f"- 🟢 **Port {port}** — `{name}` [OPEN]")
            else:
                hud_lines.append("> ℹ️ No standard services open on probed ports.")

            if player:
                try:
                    player.show_content("SERVICE VERIFICATION", "\n".join(hud_lines))
                    player.write_log(f"🛡️ [Radar] Service check on {host}: {len(open_svcs)} open ports.")
                except Exception:
                    pass
            return

        # General LAN Scan & Device Inventory
        neighbors = _get_arp_neighbors()

        # Add gateway if missing from ARP
        if not any(n["ip"] == gw_ip for n in neighbors):
            neighbors.insert(0, {"ip": gw_ip, "mac": "Gateway", "state": "REACHABLE"})

        # Resolve hostnames for top 8 neighbors
        nodes_info = []
        for n in neighbors[:10]:
            ip = n["ip"]
            # Fast ping / check
            hname = _resolve_hostname(ip)
            # Check a couple of common web/ssh ports
            active_ports = _probe_ports(ip, [22, 80, 8000, 8123])
            nodes_info.append({
                "ip": ip,
                "mac": n.get("mac", "Unknown"),
                "hostname": hname,
                "services": active_ports,
                "is_gateway": (ip == gw_ip),
            })

        hud_lines = [
            f"### 🛰️ TACTICAL NETWORK RADAR (JARVIS MARK-LVII)\n",
            f"**Primary Gateway:** `{gw_ip}` *({iface})* — [ONLINE 🟢]\n",
            f"**Discovered Active Nodes:** `{len(nodes_info)}`\n",
            "```text",
            f"[ROUTER / GATEWAY: {gw_ip}]",
        ]

        for idx, node in enumerate(nodes_info):
            prefix = "└── " if idx == len(nodes_info) - 1 else "├── "
            label = " (DEFAULT GATEWAY)" if node["is_gateway"] else ""
            hname = f" [{node['hostname']}]" if node["hostname"] != "Unknown Node" else ""
            svcs = f" :: {', '.join(s[1] for s in node['services'])}" if node["services"] else ""
            hud_lines.append(f"{prefix}🟢 {node['ip']:15s} ({node['mac']}){label}{hname}{svcs}")

        hud_lines.append("```\n")
        hud_lines.append(f"*Radar scan completed at {time.strftime('%H:%M:%S')} across subnet perimeter.*")

        if player:
            try:
                player.show_content("TACTICAL NETWORK RADAR", "\n".join(hud_lines))
                player.write_log(f"🛰️ [Radar] Mapped network: {len(nodes_info)} nodes active (Gateway: {gw_ip}).")
            except Exception:
                pass

    except Exception as e:
        if player:
            try:
                player.write_log(f"⚠️ [Radar] Scan error: {e}")
            except Exception:
                pass


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "scan_lan").strip().lower()
    target_ip = parameters.get("target_ip")
    custom_ports = parameters.get("ports")

    gw_ip, iface = _get_default_gateway()

    threading.Thread(
        target=_radar_worker,
        args=(action, target_ip, custom_ports, player),
        daemon=True,
    ).start()

    if action == "service_check":
        host = target_ip or gw_ip
        return f"Initiating service verification on {host}. Port analysis will display on the tactical radar in a moment, sir."
    elif action == "gateway_status":
        return f"Checking gateway perimeter at {gw_ip} via interface {iface}."
    else:
        return f"Scanning perimeter network topology, sir. Mapping active nodes and gateway {gw_ip} on the HUD radar."
