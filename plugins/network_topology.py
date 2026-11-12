"""
plugins/network_topology.py - Tactical Local Network Radar & Topology Cartographer.

Iron Man / JARVIS style local network situational awareness:
- Actively sweeps the local /24 subnet (ping + ARP) to discover live hosts.
- Identifies local gateway and subnet interface telemetry.
- Resolves MAC vendor (OUI) for discovered devices.
- Probes authorized local home services (SSH, Home Assistant, Web, Media).
- Grabs service banners on open ports for version/identification.
- Inspects TLS certificates on HTTPS endpoints (expiry, issuer, weak protocol).
- Flags legacy/insecure protocol exposure (plaintext Telnet/FTP, expired certs).
- Renders a tactical HUD topology grid via player.show_content().

Scope & safety notes (read before editing):
- Every action here is READ-ONLY reconnaissance against the operator's OWN LAN:
  ICMP/TCP reachability checks, ARP cache reads, and banner grabs that just
  read what a service sends unprompted on connect. Nothing here authenticates,
  exploits, brute-forces, injects, or sends traffic designed to disrupt a
  service. Keep it that way — this plugin runs with real network access on a
  real machine, so "sandbox"/"simulator" framing doesn't change what the code
  does the moment it's invoked.
- Do not add: credential/brute-force logic, exploit payloads/CVE auto-exploitation,
  packet crafting/spoofing, deauth or ARP-poisoning, traffic interception, or
  anything targeting hosts outside the local subnet. If you want offensive
  security practice, point that effort at an isolated lab (HTB/TryHackMe/a local
  Metasploitable VM), not this plugin.

Adheres strictly to AGENTS.md:
- No Qt widgets instantiated on worker threads.
- Thread-safe HUD feedback via player.show_content() and player.write_log().
- Safe non-blocking execution on a background thread.
- Never raises exceptions, returns concise spoken feedback.
"""
import concurrent.futures
import re
import socket
import ssl
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

PLUGIN = {
    "name": "network_topology",
    "description": (
        "JARVIS Tactical Network Radar: Actively sweeps and maps the local authorized "
        "network topology, identifies device vendors, inspects active LAN devices, "
        "grabs service banners, checks TLS certificate health, flags legacy/insecure "
        "protocol exposure, and displays a tactical network map on the HUD."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "Action: 'scan_lan', 'device_inventory', 'service_check', "
                    "'gateway_status', 'subnet_sweep', 'exposure_audit'. Default 'scan_lan'."
                ),
                "enum": [
                    "scan_lan",
                    "device_inventory",
                    "service_check",
                    "gateway_status",
                    "subnet_sweep",
                    "exposure_audit",
                ],
            },
            "target_ip": {
                "type": "STRING",
                "description": "Target IP address or host on the local network (for 'service_check' / 'exposure_audit').",
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
    21: "FTP",
    22: "SSH",
    23: "Telnet",
    53: "DNS",
    80: "HTTP Web",
    443: "HTTPS",
    445: "SMB",
    1883: "MQTT Broker",
    5000: "OctoPrint / UPnP",
    8000: "Web Dashboard",
    8080: "HTTP Alt",
    8123: "Home Assistant",
    32400: "Plex Media Server",
}

# Compact, commonly-seen OUI (first 3 MAC octets) -> vendor map. Not exhaustive;
# unresolved prefixes just report "Unknown Vendor" rather than failing.
_OUI_VENDORS = {
    "B827EB": "Raspberry Pi Foundation",
    "DCA632": "Raspberry Pi Foundation",
    "E45F01": "Raspberry Pi Foundation",
    "D83ADD": "Google / Nest",
    "F4F5D8": "Google",
    "001A11": "Google",
    "3C5AB4": "Google",
    "B4F1DA": "Amazon",
    "FC65DE": "Amazon",
    "68371D": "Amazon",
    "A4D18C": "Amazon (Echo/Ring)",
    "000D93": "Apple",
    "F0DBF8": "Apple",
    "A4B197": "Apple",
    "3C0754": "Apple",
    "DCA904": "Apple",
    "B8E856": "Apple",
    "001D4F": "Apple",
    "F40F24": "Apple",
    "ACBC32": "Apple",
    "001B63": "Apple",
    "CC50E3": "Apple",
    "001CB3": "Apple",
    "0024D7": "Intel",
    "3CF862": "Intel",
    "A434D9": "Intel",
    "001E65": "Samsung",
    "5C0A5B": "Samsung",
    "D0176A": "Samsung",
    "F8042E": "Samsung",
    "38AA3C": "Hewlett Packard",
    "3C4A92": "Hewlett Packard",
    "001E0B": "Hewlett Packard",
    "001F29": "TP-Link",
    "6CB0CE": "TP-Link",
    "F4EC38": "TP-Link",
    "B0487A": "TP-Link",
    "0022B0": "D-Link",
    "001195": "D-Link",
    "D8EB97": "Ubiquiti",
    "245A4C": "Ubiquiti",
    "FCECDA": "Ubiquiti",
    "9C8ECD": "Netgear",
    "A42B8C": "Netgear",
    "204E71": "Netgear",
    "00224D": "ASUSTek",
    "AC220B": "ASUSTek",
    "F832E4": "ASUSTek",
    "6C4008": "Xiaomi",
    "286DCD": "Xiaomi",
    "F0B429": "Xiaomi",
    "34CE00": "Espressif (ESP8266/32 IoT)",
    "A020A6": "Espressif (ESP8266/32 IoT)",
    "CC50E3": "Espressif (ESP8266/32 IoT)",
    "483FDA": "Sonos",
    "000E58": "Sonos",
}


def _normalize_mac_prefix(mac: str) -> str:
    cleaned = re.sub(r"[^0-9A-Fa-f]", "", mac or "")
    return cleaned[:6].upper()


def _lookup_vendor(mac: str) -> str:
    prefix = _normalize_mac_prefix(mac)
    return _OUI_VENDORS.get(prefix, "Unknown Vendor")


def _get_default_gateway() -> tuple[str, str]:
    """Return (gateway_ip, interface_name)."""
    try:
        if sys.platform.startswith("linux"):
            r = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True, timeout=2)
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


def _get_local_ip() -> str:
    """Best-effort local IP of the primary outbound interface."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(1)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def _get_arp_neighbors() -> list[dict]:
    """Read local ARP neighbor cache passively."""
    neighbors = []
    try:
        if sys.platform.startswith("linux"):
            r = subprocess.run(["ip", "neigh", "show"], capture_output=True, text=True, timeout=3)
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
            for line in r.stdout.splitlines():
                m = re.search(r"\(?(\d+\.\d+\.\d+\.\d+)\)?\s+(?:at\s+)?([0-9a-fA-F:-]{11,17})", line)
                if m:
                    neighbors.append({"ip": m.group(1), "mac": m.group(2).replace("-", ":"), "state": "ACTIVE"})
    except Exception:
        pass
    return neighbors


def _ping_once(ip: str) -> bool:
    """Single lightweight ping to coax the OS into populating its ARP cache."""
    try:
        if sys.platform == "win32":
            cmd = ["ping", "-n", "1", "-w", "300", ip]
        else:
            cmd = ["ping", "-c", "1", "-W", "1", ip]
        r = subprocess.run(cmd, capture_output=True, timeout=2)
        return r.returncode == 0
    except Exception:
        return False


def _subnet_sweep(local_ip: str, max_workers: int = 48) -> list[dict]:
    """
    Active discovery across the local /24: ping-sweeps every host address so the
    OS ARP cache gets populated, then reads that cache back. Read-only reachability
    probing of the operator's own subnet only — no packet crafting, no spoofing.
    """
    try:
        octets = local_ip.split(".")
        if len(octets) != 4:
            return _get_arp_neighbors()
        base = ".".join(octets[:3])
        targets = [f"{base}.{i}" for i in range(1, 255)]

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            list(pool.map(_ping_once, targets))

        time.sleep(0.3)  # let ARP cache settle
        return _get_arp_neighbors()
    except Exception:
        return _get_arp_neighbors()


def _probe_ports(host: str, ports_to_check: list[int]) -> list[tuple[int, str]]:
    open_ports = []
    for port in ports_to_check:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.3)
                res = s.connect_ex((host, port))
                if res == 0:
                    svc_name = _COMMON_HOME_SERVICES.get(port, f"Port {port}")
                    open_ports.append((port, svc_name))
        except Exception:
            continue
    return open_ports


def _grab_banner(host: str, port: int) -> str:
    """
    Read whatever a service volunteers on connect, or issue a minimal protocol-
    standard probe (HTTP HEAD) and read the response header. Does not authenticate
    or send any payload beyond a bare, unauthenticated request line.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.8)
            s.connect((host, port))
            if port in (80, 8080, 8000, 8123, 5000):
                s.sendall(b"HEAD / HTTP/1.0\r\nHost: %s\r\n\r\n" % host.encode())
            data = s.recv(256)
            text = data.decode(errors="replace").strip().splitlines()
            return text[0] if text else ""
    except Exception:
        return ""


def _tls_cert_info(host: str, port: int = 443) -> dict:
    """Fetch and summarize the TLS certificate presented on an HTTPS-style port."""
    info = {"ok": False}
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((host, port), timeout=1.5) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert(binary_form=False) or {}
                proto = ssock.version()
                not_after = cert.get("notAfter")
                expiry = None
                expired = None
                if not_after:
                    try:
                        expiry_dt = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
                        expiry = expiry_dt.strftime("%Y-%m-%d")
                        expired = expiry_dt < datetime.now(timezone.utc)
                    except Exception:
                        pass
                issuer = dict(x[0] for x in cert.get("issuer", [])) if cert.get("issuer") else {}
                info.update({
                    "ok": True,
                    "protocol": proto,
                    "expiry": expiry,
                    "expired": expired,
                    "issuer": issuer.get("organizationName") or issuer.get("commonName") or "Unknown",
                    "weak_protocol": proto in ("TLSv1", "TLSv1.1", "SSLv3"),
                })
    except Exception:
        pass
    return info


def _exposure_flags(host: str, open_svcs: list[tuple[int, str]]) -> list[str]:
    """
    Heuristic, non-exploitative exposure flags: legacy plaintext protocols and
    TLS/cert hygiene issues on the operator's own device. No CVE database lookup
    (would require an external feed) and no automated exploitation.
    """
    flags = []
    port_map = dict(open_svcs)

    if 23 in port_map:
        flags.append("🔴 Telnet (23) open — unencrypted remote admin protocol, consider disabling")
    if 21 in port_map:
        banner = _grab_banner(host, 21)
        flags.append(f"🟠 FTP (21) open — unencrypted file transfer{f' [{banner}]' if banner else ''}")
    if 445 in port_map:
        flags.append("🟠 SMB (445) exposed to LAN — confirm this host should be reachable")
    if 80 in port_map and 443 not in port_map:
        flags.append("🟡 HTTP (80) open with no HTTPS (443) counterpart — unencrypted web admin UI")
    if 443 in port_map:
        tls = _tls_cert_info(host, 443)
        if tls.get("ok"):
            if tls.get("expired"):
                flags.append(f"🔴 TLS certificate EXPIRED on {tls.get('expiry')}")
            if tls.get("weak_protocol"):
                flags.append(f"🔴 Weak TLS protocol negotiated: {tls.get('protocol')}")
            if not tls.get("expired") and not tls.get("weak_protocol"):
                flags.append(f"🟢 TLS OK — {tls.get('protocol')}, issuer: {tls.get('issuer')}, expires {tls.get('expiry')}")
    if not flags:
        flags.append("🟢 No legacy/plaintext exposure detected on probed ports")
    return flags


def _resolve_hostname(ip: str) -> str:
    try:
        host, _, _ = socket.gethostbyaddr(ip)
        return host
    except Exception:
        return "Unknown Node"


def _radar_worker(action: str, target_ip: str | None, custom_ports: list[int] | None, player):
    try:
        gw_ip, iface = _get_default_gateway()
        local_ip = _get_local_ip()

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
                    banner = _grab_banner(host, port)
                    tag = f" — `{banner}`" if banner else ""
                    hud_lines.append(f"- 🟢 **Port {port}** — `{name}`{tag}")
            else:
                hud_lines.append("> ℹ️ No standard services open on probed ports.")

            if player:
                try:
                    player.show_content("SERVICE VERIFICATION", "\n".join(hud_lines))
                    player.write_log(f"🛡️ [Radar] Service check on {host}: {len(open_svcs)} open ports.")
                except Exception:
                    pass
            return

        if action == "exposure_audit":
            host = target_ip or gw_ip
            ports = custom_ports or list(_COMMON_HOME_SERVICES.keys())
            open_svcs = _probe_ports(host, ports)
            flags = _exposure_flags(host, open_svcs)

            hud_lines = [
                f"### 🔎 Exposure Audit: `{host}`\n",
                f"**Open Ports:** `{len(open_svcs)}` | **Probed:** `{len(ports)}`\n",
                "**Findings:**",
            ]
            hud_lines.extend(f"- {f}" for f in flags)

            if player:
                try:
                    player.show_content("EXPOSURE AUDIT", "\n".join(hud_lines))
                    player.write_log(f"🔎 [Radar] Exposure audit on {host}: {len(flags)} findings.")
                except Exception:
                    pass
            return

        # scan_lan / device_inventory / gateway_status / subnet_sweep all converge
        # on a full topology map; subnet_sweep does the active ping sweep first.
        if action == "subnet_sweep":
            neighbors = _subnet_sweep(local_ip)
        else:
            neighbors = _get_arp_neighbors()

        if not any(n["ip"] == gw_ip for n in neighbors):
            neighbors.insert(0, {"ip": gw_ip, "mac": "Gateway", "state": "REACHABLE"})

        nodes_info = []
        for n in neighbors[:20]:
            ip = n["ip"]
            hname = _resolve_hostname(ip)
            active_ports = _probe_ports(ip, [22, 80, 443, 8000, 8123])
            vendor = _lookup_vendor(n.get("mac", ""))
            nodes_info.append({
                "ip": ip,
                "mac": n.get("mac", "Unknown"),
                "vendor": vendor,
                "hostname": hname,
                "services": active_ports,
                "is_gateway": (ip == gw_ip),
            })

        hud_lines = [
            "### 🛰️ TACTICAL NETWORK RADAR (JARVIS MARK-LVII)\n",
            f"**Primary Gateway:** `{gw_ip}` *({iface})* — [ONLINE 🟢]\n",
            f"**This Host:** `{local_ip}`\n",
            f"**Discovered Active Nodes:** `{len(nodes_info)}`\n",
            "```text",
            f"[ROUTER / GATEWAY: {gw_ip}]",
        ]

        for idx, node in enumerate(nodes_info):
            prefix = "└── " if idx == len(nodes_info) - 1 else "├── "
            label = " (DEFAULT GATEWAY)" if node["is_gateway"] else ""
            hname = f" [{node['hostname']}]" if node["hostname"] != "Unknown Node" else ""
            vendor_tag = f" <{node['vendor']}>" if node["vendor"] != "Unknown Vendor" else ""
            svcs = f" :: {', '.join(s[1] for s in node['services'])}" if node["services"] else ""
            hud_lines.append(f"{prefix}🟢 {node['ip']:15s} ({node['mac']}){vendor_tag}{label}{hname}{svcs}")

        hud_lines.append("```\n")
        mode_tag = "active subnet sweep" if action == "subnet_sweep" else "passive ARP cache"
        hud_lines.append(f"*Radar scan ({mode_tag}) completed at {time.strftime('%H:%M:%S')}.*")

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
    elif action == "exposure_audit":
        host = target_ip or gw_ip
        return f"Running an exposure audit on {host} — checking for legacy protocols and certificate issues, sir."
    elif action == "gateway_status":
        return f"Checking gateway perimeter at {gw_ip} via interface {iface}."
    elif action == "subnet_sweep":
        return f"Running an active subnet sweep off interface {iface}, sir. This takes a few seconds longer than a passive scan."
    else:
        return f"Scanning perimeter network topology, sir. Mapping active nodes and gateway {gw_ip} on the HUD radar."
