"""
plugins/network_topology.py - Tactical Local Network Radar & Topology Cartographer.

Iron Man / JARVIS style local network situational awareness:
- Actively sweeps the local /24 subnet (ping + ARP + TCP handshake probe) to discover live hosts.
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
from pathlib import Path

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

# Compact, normalized 6-hex-digit OUI -> vendor map.
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


def _get_local_ip(gw_ip: str = "192.168.1.1") -> str:
    """Best-effort local IP of the primary outbound interface."""
    for target in [(gw_ip, 80), ("8.8.8.8", 80), ("1.1.1.1", 80)]:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(0.5)
                s.connect(target)
                ip = s.getsockname()[0]
                if ip and not ip.startswith("127."):
                    return ip
        except Exception:
            continue
    try:
        h_ip = socket.gethostbyname(socket.gethostname())
        if h_ip and not h_ip.startswith("127."):
            return h_ip
    except Exception:
        pass
    return "127.0.0.1"


def _get_arp_neighbors() -> list[dict]:
    """Read local ARP neighbor cache passively across Linux procfs, ip neigh, and arp."""
    neighbors = []
    seen_ips = set()

    # 1. Linux /proc/net/arp (instantaneous, zero subprocess)
    if Path("/proc/net/arp").is_file():
        try:
            with open("/proc/net/arp", "r", encoding="utf-8") as f:
                lines = f.readlines()[1:]
            for line in lines:
                parts = line.split()
                if len(parts) >= 4:
                    ip, hw_flags, mac = parts[0], parts[2], parts[3]
                    if hw_flags != "0x0" and mac != "00:00:00:00:00:00" and ip not in seen_ips:
                        neighbors.append({"ip": ip, "mac": mac, "state": "REACHABLE"})
                        seen_ips.add(ip)
        except Exception:
            pass

    # 2. Linux ip neigh
    if sys.platform.startswith("linux"):
        try:
            r = subprocess.run(["ip", "neigh", "show"], capture_output=True, text=True, timeout=2)
            for line in r.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 4 and "lladdr" in parts:
                    ip = parts[0]
                    mac_idx = parts.index("lladdr") + 1
                    mac = parts[mac_idx] if mac_idx < len(parts) else "Unknown"
                    state = parts[-1]
                    if state not in ("FAILED", "INCOMPLETE") and mac != "00:00:00:00:00:00" and ip not in seen_ips:
                        neighbors.append({"ip": ip, "mac": mac, "state": state})
                        seen_ips.add(ip)
        except Exception:
            pass

    # 3. Windows/macOS arp -a
    if not neighbors:
        try:
            r = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=2)
            for line in r.stdout.splitlines():
                m = re.search(r"\(?(\d+\.\d+\.\d+\.\d+)\)?\s+(?:at\s+)?([0-9a-fA-F:-]{11,17})", line)
                if m:
                    ip, mac = m.group(1), m.group(2).replace("-", ":")
                    if mac.lower() not in ("ff:ff:ff:ff:ff:ff", "00:00:00:00:00:00") and ip not in seen_ips:
                        neighbors.append({"ip": ip, "mac": mac, "state": "ACTIVE"})
                        seen_ips.add(ip)
        except Exception:
            pass

    return neighbors


def _probe_host_presence(ip: str) -> bool:
    """Send a lightweight ICMP ping and TCP handshake attempt to register ARP in the kernel."""
    # 1. ICMP ping
    try:
        cmd = ["ping", "-n", "1", "-w", "250", ip] if sys.platform == "win32" else ["ping", "-c", "1", "-W", "1", ip]
        r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1.5)
        if r.returncode == 0:
            return True
    except Exception:
        pass
    # 2. Fast TCP touch (coaxes ARP resolution even when ICMP is firewalled)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            s.connect_ex((ip, 80))
    except Exception:
        pass
    return False


def _subnet_sweep(local_ip: str, gw_ip: str, max_workers: int = 48) -> list[dict]:
    """Active discovery across local /24 subnet."""
    try:
        ip_for_sweep = local_ip if not local_ip.startswith("127.") else gw_ip
        octets = ip_for_sweep.split(".")
        if len(octets) != 4:
            return _get_arp_neighbors()
        base = ".".join(octets[:3])
        targets = [f"{base}.{i}" for i in range(1, 255)]

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            list(pool.map(_probe_host_presence, targets))

        time.sleep(0.3)  # Let ARP cache settle
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
    """Read whatever a service volunteers on connect, extracting server/version headers."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.8)
            s.connect((host, port))
            if port in (80, 8080, 8000, 8123, 5000):
                s.sendall(f"HEAD / HTTP/1.0\r\nHost: {host}\r\nUser-Agent: JARVIS-Radar\r\n\r\n".encode())
            data = s.recv(512)
            if not data:
                return ""
            raw_text = data.decode(errors="replace").strip()
            # If HTTP, check for Server: header
            if port in (80, 8080, 8000, 8123, 5000) or raw_text.startswith("HTTP/"):
                for line in raw_text.splitlines():
                    if line.lower().startswith("server:"):
                        return line.split(":", 1)[1].strip()
            # Otherwise return first meaningful line
            lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
            return lines[0][:80] if lines else ""
    except Exception:
        return ""


def _tls_cert_info(host: str, port: int = 443) -> dict:
    """Fetch and parse TLS certificate, extracting expiry and issuer via DER decoding."""
    info = {"ok": False}
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((host, port), timeout=1.5) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                proto = ssock.version()
                der_cert = ssock.getpeercert(binary_form=True)
                expiry = None
                expired = None
                issuer_str = "Unknown"

                if der_cert:
                    try:
                        from cryptography import x509
                        cert = x509.load_der_x509_certificate(der_cert)
                        expiry_dt = (
                            cert.not_valid_after_utc
                            if hasattr(cert, "not_valid_after_utc")
                            else cert.not_valid_after.replace(tzinfo=timezone.utc)
                        )
                        expiry = expiry_dt.strftime("%Y-%m-%d")
                        expired = expiry_dt < datetime.now(timezone.utc)
                        for attr in cert.issuer:
                            oid_name = attr.oid._name if hasattr(attr.oid, "_name") else ""
                            if oid_name in ("organizationName", "commonName"):
                                issuer_str = attr.value
                                break
                    except Exception:
                        pass

                info.update({
                    "ok": True,
                    "protocol": proto,
                    "expiry": expiry,
                    "expired": expired,
                    "issuer": issuer_str,
                    "weak_protocol": proto in ("TLSv1", "TLSv1.1", "SSLv3"),
                })
    except Exception:
        pass
    return info


def _exposure_flags(host: str, open_svcs: list[tuple[int, str]]) -> list[str]:
    """Heuristic, non-exploitative exposure audit flags."""
    flags = []
    port_map = dict(open_svcs)

    if 23 in port_map:
        flags.append(" Telnet (23) open — unencrypted remote admin protocol, consider disabling")
    if 21 in port_map:
        banner = _grab_banner(host, 21)
        flags.append(f" FTP (21) open — unencrypted file transfer{f'[{banner}]' if banner else ''}")
    if 445 in port_map:
        flags.append(" SMB (445) exposed to LAN — confirm this host should be reachable")
    if 80 in port_map and 443 not in port_map:
        flags.append(" HTTP (80) open with no HTTPS (443) counterpart — unencrypted web admin UI")
    if 443 in port_map:
        tls = _tls_cert_info(host, 443)
        if tls.get("ok"):
            if tls.get("expired"):
                flags.append(f" TLS certificate EXPIRED on {tls.get('expiry')}")
            elif tls.get("weak_protocol"):
                flags.append(f" Weak TLS protocol negotiated: {tls.get('protocol')}")
            else:
                expiry_str = f", expires {tls.get('expiry')}" if tls.get("expiry") else ""
                flags.append(f" TLS OK — {tls.get('protocol')}, issuer: {tls.get('issuer')}{expiry_str}")
        else:
            flags.append(" HTTPS (443) open but TLS handshake could not be inspected")
    if not flags:
        flags.append(" No legacy/plaintext exposure detected on probed ports")
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
        local_ip = _get_local_ip(gw_ip)

        if action == "service_check":
            host = target_ip or gw_ip
            ports = custom_ports or list(_COMMON_HOME_SERVICES.keys())
            open_svcs = _probe_ports(host, ports)

            hud_lines = [
                f"### ️ Tactical Service Verification: `{host}`\n",
                f"**Interface:** `{iface}` | **Probed Ports:** `{len(ports)}`\n",
            ]
            if open_svcs:
                hud_lines.append("**Active Local Services:**")
                for port, name in open_svcs:
                    banner = _grab_banner(host, port)
                    tag = f" — `{banner}`" if banner else ""
                    hud_lines.append(f"-  **Port {port}** — `{name}`{tag}")
            else:
                hud_lines.append("> ℹ️ No standard services open on probed ports.")

            if player:
                try:
                    player.show_content("SERVICE VERIFICATION", "\n".join(hud_lines))
                    player.write_log(f"️ [Radar] Service check on {host}: {len(open_svcs)} open ports.")
                except Exception:
                    pass
            return

        if action == "exposure_audit":
            host = target_ip or gw_ip
            ports = custom_ports or list(_COMMON_HOME_SERVICES.keys())
            open_svcs = _probe_ports(host, ports)
            flags = _exposure_flags(host, open_svcs)

            hud_lines = [
                f"###  Exposure Audit: `{host}`\n",
                f"**Open Ports:** `{len(open_svcs)}` | **Probed:** `{len(ports)}`\n",
                "**Findings:**",
            ]
            hud_lines.extend(f"- {f}" for f in flags)

            if player:
                try:
                    player.show_content("EXPOSURE AUDIT", "\n".join(hud_lines))
                    player.write_log(f"[Radar] Exposure audit on {host}: {len(flags)} findings.")
                except Exception:
                    pass
            return

        # scan_lan / device_inventory / gateway_status / subnet_sweep
        if action == "subnet_sweep":
            neighbors = _subnet_sweep(local_ip, gw_ip)
        else:
            neighbors = _get_arp_neighbors()

        # Ensure gateway is present
        if not any(n["ip"] == gw_ip for n in neighbors):
            neighbors.insert(0, {"ip": gw_ip, "mac": "Gateway", "state": "REACHABLE"})

        # Ensure local host is present
        if local_ip != "127.0.0.1" and not any(n["ip"] == local_ip for n in neighbors):
            neighbors.append({"ip": local_ip, "mac": "Host", "state": "REACHABLE"})

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
                "is_host": (ip == local_ip),
            })

        hud_lines = [
            "### ️ TACTICAL NETWORK RADAR (JARVIS MARK-LVII)\n",
            f"**Primary Gateway:** `{gw_ip}` *({iface})* — [ONLINE ]\n",
            f"**JARVIS Host Node:** `{local_ip}`\n",
            f"**Discovered Active Nodes:** `{len(nodes_info)}`\n",
            "```text",
            f"[ROUTER / GATEWAY: {gw_ip}]",
        ]

        for idx, node in enumerate(nodes_info):
            prefix = "└── " if idx == len(nodes_info) - 1 else "├── "
            label = " (DEFAULT GATEWAY)" if node["is_gateway"] else (" (JARVIS HOST)" if node["is_host"] else "")
            hname = f"[{node['hostname']}]" if node["hostname"] != "Unknown Node" else ""
            vendor_tag = f" <{node['vendor']}>" if node["vendor"] != "Unknown Vendor" else ""
            svcs = f" :: {', '.join(s[1] for s in node['services'])}" if node["services"] else ""
            hud_lines.append(f"{prefix} {node['ip']:15s} ({node['mac']}){vendor_tag}{label}{hname}{svcs}")

        hud_lines.append("```\n")
        mode_tag = "active subnet sweep" if action == "subnet_sweep" else "passive ARP cache"
        hud_lines.append(f"*Radar scan ({mode_tag}) completed at {time.strftime('%H:%M:%S')}.*")

        if player:
            try:
                player.show_content("TACTICAL NETWORK RADAR", "\n".join(hud_lines))
                player.write_log(f"️ [Radar] Mapped network: {len(nodes_info)} nodes active (Gateway: {gw_ip}).")
            except Exception:
                pass

    except Exception as e:
        if player:
            try:
                player.write_log(f"[Radar] Scan error: {e}")
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
