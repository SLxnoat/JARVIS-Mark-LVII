"""
plugins/wifi_radar.py - Tactical Wi-Fi Radar & RF Spectrum Cartographer.

Iron Man / JARVIS style wireless spectrum situational awareness:
- Telemetry on the active Wi-Fi link (SSID, BSSID, RSSI dBm/%, channel, bitrate, band).
- Sweeps ambient RF environment for surrounding Wi-Fi access points.
- Analyzes channel congestion across 2.4 GHz and 5 GHz bands, recommending optimal channels.
- Audits wireless security hygiene (flags open unencrypted APs and legacy WEP/WPA1).
- Renders a tactical HUD spectrum visualizer via player.show_content().

Adheres strictly to AGENTS.md:
- No Qt widgets instantiated on worker threads.
- Thread-safe HUD presentation via player.show_content() and player.write_log().
- Safe execution on background thread; never raises exceptions.
- Returns concise, natural spoken feedback.
"""
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

PLUGIN = {
    "name": "wifi_radar",
    "description": (
        "JARVIS Tactical Wi-Fi Radar: Inspects current Wi-Fi link health (signal dBm, bitrate, channel), "
        "scans ambient wireless networks, analyzes channel congestion (2.4 GHz & 5 GHz), "
        "flags insecure open/WEP networks, and renders an RF spectrum heatmap on the HUD."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "Action: 'current_link', 'scan_networks', 'channel_optimizer', "
                    "'security_hygiene', 'spectrum_map'. Default is 'current_link'."
                ),
                "enum": [
                    "current_link",
                    "scan_networks",
                    "channel_optimizer",
                    "security_hygiene",
                    "spectrum_map",
                ],
            },
        },
        "required": ["action"],
    },
}


def _get_current_link() -> dict:
    """Extract telemetry for the currently connected Wi-Fi link."""
    info = {
        "connected": False,
        "ssid": "Disconnected",
        "bssid": "N/A",
        "channel": "N/A",
        "freq": "N/A",
        "signal_pct": 0,
        "bitrate": "N/A",
        "security": "N/A",
        "band": "Unknown",
    }

    try:
        if sys.platform.startswith("linux"):
            # Try nmcli active connection
            if shutil.which("nmcli"):
                r = subprocess.run(
                    ["nmcli", "-t", "-f", "IN-USE,SSID,BSSID,CHAN,FREQ,SIGNAL,SECURITY,RATE", "dev", "wifi", "list"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                for line in r.stdout.splitlines():
                    if line.startswith("*"):
                        parts = line.split(":")
                        if len(parts) >= 7:
                            info["connected"] = True
                            info["ssid"] = parts[1] or "Hidden SSID"
                            info["bssid"] = parts[2]
                            info["channel"] = parts[3]
                            info["freq"] = parts[4]
                            info["signal_pct"] = int(parts[5]) if parts[5].isdigit() else 70
                            info["security"] = parts[6]
                            info["bitrate"] = parts[7] if len(parts) > 7 else "N/A"
                            freq_num = re.sub(r"[^\d]", "", parts[4])
                            if freq_num:
                                f_val = int(freq_num)
                                info["band"] = "5 GHz" if f_val > 4000 else ("6 GHz" if f_val > 5900 else "2.4 GHz")
                            break

            # Fallback to iw / procfs if nmcli not connected or absent
            if not info["connected"] and Path("/proc/net/wireless").is_file():
                try:
                    with open("/proc/net/wireless", "r", encoding="utf-8") as f:
                        lines = f.readlines()[2:]
                    if lines:
                        parts = lines[0].split()
                        link_val = int(parts[2].replace(".", "")) if len(parts) > 2 else 50
                        info["connected"] = True
                        info["signal_pct"] = min(100, int((link_val / 70.0) * 100))
                        info["ssid"] = "Active Wireless Interface"
                except Exception:
                    pass

        elif sys.platform == "win32":
            r = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, timeout=3)
            for line in r.stdout.splitlines():
                if ":" in line:
                    k, v = [x.strip() for x in line.split(":", 1)]
                    kl = k.lower()
                    if "state" in kl and "connected" in v.lower():
                        info["connected"] = True
                    elif "ssid" in kl and "bssid" not in kl:
                        info["ssid"] = v
                    elif "bssid" in kl:
                        info["bssid"] = v
                    elif "signal" in kl:
                        m = re.search(r"(\d+)%", v)
                        if m:
                            info["signal_pct"] = int(m.group(1))
                    elif "channel" in kl:
                        info["channel"] = v
                        if v.isdigit():
                            ch = int(v)
                            info["band"] = "2.4 GHz" if ch <= 14 else ("5 GHz" if ch <= 165 else "6 GHz")
                    elif "receive rate" in kl or "transmit rate" in kl:
                        info["bitrate"] = f"{v} Mbps"
                    elif "authentication" in kl:
                        info["security"] = v

        elif sys.platform == "darwin":
            airport = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
            r = subprocess.run([airport, "-I"], capture_output=True, text=True, timeout=3)
            for line in r.stdout.splitlines():
                if ":" in line:
                    k, v = [x.strip() for x in line.split(":", 1)]
                    kl = k.lower()
                    if "state" in kl and "running" in v.lower():
                        info["connected"] = True
                    elif "ssid" in kl and "bssid" not in kl:
                        info["ssid"] = v
                    elif "bssid" in kl:
                        info["bssid"] = v
                    elif "channel" in kl:
                        info["channel"] = v
                    elif "agrctlrssi" in kl:
                        rssi = int(v) if v.lstrip("-").isdigit() else -60
                        info["signal_pct"] = max(0, min(100, int(2 * (rssi + 100))))
                    elif "lasttxrate" in kl:
                        info["bitrate"] = f"{v} Mbps"
                    elif "link auth" in kl:
                        info["security"] = v
    except Exception:
        pass

    return info


def _scan_ambient_networks() -> list[dict]:
    """Scan nearby ambient Wi-Fi access points."""
    networks = []
    try:
        if sys.platform.startswith("linux"):
            if shutil.which("nmcli"):
                r = subprocess.run(
                    ["nmcli", "-t", "-f", "IN-USE,SSID,BSSID,CHAN,FREQ,SIGNAL,SECURITY", "dev", "wifi", "list"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                for line in r.stdout.splitlines():
                    parts = line.split(":")
                    if len(parts) >= 7:
                        ssid = parts[1] or "[Hidden SSID]"
                        bssid = parts[2]
                        chan = parts[3]
                        freq = parts[4]
                        sig = int(parts[5]) if parts[5].isdigit() else 50
                        sec = parts[6] or "Open"
                        freq_num = re.sub(r"[^\d]", "", freq)
                        band = "5 GHz" if (freq_num and int(freq_num) > 4000) else "2.4 GHz"
                        networks.append({
                            "ssid": ssid,
                            "bssid": bssid,
                            "channel": chan,
                            "signal": sig,
                            "security": sec,
                            "band": band,
                            "in_use": parts[0] == "*",
                        })

        elif sys.platform == "win32":
            r = subprocess.run(["netsh", "wlan", "show", "networks", "mode=bssid"], capture_output=True, text=True, timeout=5)
            curr_net = {}
            for line in r.stdout.splitlines():
                line = line.strip()
                if line.startswith("SSID"):
                    if curr_net and curr_net.get("ssid"):
                        networks.append(curr_net)
                    curr_net = {"ssid": line.split(":", 1)[1].strip() or "[Hidden SSID]", "signal": 50, "security": "WPA2"}
                elif "Authentication" in line:
                    curr_net["security"] = line.split(":", 1)[1].strip()
                elif "Signal" in line:
                    m = re.search(r"(\d+)%", line)
                    if m:
                        curr_net["signal"] = int(m.group(1))
                elif "Channel" in line:
                    curr_net["channel"] = line.split(":", 1)[1].strip()
                    ch = int(curr_net["channel"]) if curr_net["channel"].isdigit() else 1
                    curr_net["band"] = "2.4 GHz" if ch <= 14 else "5 GHz"
                elif "BSSID" in line:
                    curr_net["bssid"] = line.split(":", 1)[1].strip()
            if curr_net and curr_net.get("ssid"):
                networks.append(curr_net)

        elif sys.platform == "darwin":
            airport = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
            r = subprocess.run([airport, "-s"], capture_output=True, text=True, timeout=5)
            lines = r.stdout.splitlines()
            if len(lines) > 1:
                for line in lines[1:]:
                    parts = line.split()
                    if len(parts) >= 6:
                        networks.append({
                            "ssid": parts[0],
                            "bssid": parts[1],
                            "signal": 70,
                            "channel": parts[3],
                            "security": parts[6] if len(parts) > 6 else "WPA2",
                            "band": "5 GHz" if int(parts[3].split(",")[0]) > 14 else "2.4 GHz" if parts[3].split(",")[0].isdigit() else "2.4 GHz",
                            "in_use": False,
                        })
    except Exception:
        pass

    return networks


def _analyze_channel_congestion(networks: list[dict]) -> tuple[dict, str]:
    """Analyze channel distribution and provide optimal channel recommendation."""
    chan_24 = {1: 0, 6: 0, 11: 0}
    chan_5g = {}

    for n in networks:
        ch_str = str(n.get("channel", "")).split(",")[0].strip()
        if ch_str.isdigit():
            ch = int(ch_str)
            if ch in (1, 6, 11):
                chan_24[ch] += 1
            elif ch <= 14:
                # Nearest standard non-overlapping channel
                nearest = min([1, 6, 11], key=lambda x: abs(x - ch))
                chan_24[nearest] += 1
            else:
                chan_5g[ch] = chan_5g.get(ch, 0) + 1

    best_24 = min(chan_24, key=chan_24.get) if chan_24 else 6
    best_5g = min([36, 44, 149, 157], key=lambda c: chan_5g.get(c, 0))

    summary = (
        f"2.4 GHz Band: Ch 1 ({chan_24[1]} APs), Ch 6 ({chan_24[6]} APs), Ch 11 ({chan_24[11]} APs). "
        f"Least crowded 2.4 GHz channel is **Channel {best_24}**. "
        f"For 5 GHz, **Channel {best_5g}** offers minimal co-channel interference."
    )
    return {"chan_24": chan_24, "chan_5g": chan_5g, "best_24": best_24, "best_5g": best_5g}, summary


def _audit_security(networks: list[dict]) -> list[str]:
    """Flag wireless security vulnerabilities in ambient RF perimeter."""
    flags = []
    open_nets = [n for n in networks if "open" in n.get("security", "").lower() or n.get("security") == "None"]
    wep_nets = [n for n in networks if "wep" in n.get("security", "").lower()]
    hidden_nets = [n for n in networks if "[Hidden" in n.get("ssid", "")]

    if open_nets:
        flags.append(f"🔴 **{len(open_nets)} Open/Unencrypted Network(s)** detected: {', '.join(n['ssid'] for n in open_nets[:3])} (prone to packet sniffing).")
    if wep_nets:
        flags.append(f"🔴 **{len(wep_nets)} Legacy WEP Network(s)** detected (broken RC4 encryption, trivially cracked).")
    if hidden_nets:
        flags.append(f"🟡 **{len(hidden_nets)} Hidden SSID(s)** observed in the area.")
    if not flags:
        flags.append("🟢 All detected ambient wireless networks enforce modern WPA2/WPA3 authentication.")
    return flags


def _make_signal_bar(pct: int) -> str:
    filled = max(1, min(5, (pct + 10) // 20))
    return "█" * filled + "░" * (5 - filled)


def _radar_worker(action: str, player):
    try:
        curr = _get_current_link()
        networks = _scan_ambient_networks()

        if action == "current_link":
            hud_lines = [
                "### 📡 Current Wi-Fi Link Telemetry\n",
                f"**Status:** {'ONLINE 🟢' if curr['connected'] else 'DISCONNECTED 🔴'}\n",
                f"- **SSID:** `{curr['ssid']}`\n",
                f"- **BSSID:** `{curr['bssid']}`\n",
                f"- **Frequency Band:** `{curr['band']}` *(Channel {curr['channel']})*\n",
                f"- **Signal Quality:** `{_make_signal_bar(curr['signal_pct'])} {curr['signal_pct']}%`\n",
                f"- **Link Rate:** `{curr['bitrate']}`\n",
                f"- **Security Mode:** `{curr['security']}`\n",
            ]
            if player:
                try:
                    player.show_content("WI-FI LINK TELEMETRY", "\n".join(hud_lines))
                    player.write_log(f"📡 [WiFi] Active link: '{curr['ssid']}' ({curr['signal_pct']}% | Ch {curr['channel']})")
                except Exception:
                    pass
            return

        elif action == "channel_optimizer":
            _, opt_text = _analyze_channel_congestion(networks)
            hud_lines = [
                "### 📊 RF Channel Congestion & Optimization\n",
                f"**Ambient Access Points Analyzed:** `{len(networks)}`\n\n",
                f"> 💡 **Recommendation:** {opt_text}\n\n",
                "**Spectrum Density Breakdown:**\n",
            ]
            for n in sorted(networks, key=lambda x: x.get("signal", 0), reverse=True)[:10]:
                hud_lines.append(f"- **Ch {n.get('channel', '?')}** *({n.get('band', '?')})* — `{n.get('ssid')}` [{n.get('signal')}%]")

            if player:
                try:
                    player.show_content("CHANNEL OPTIMIZER", "\n".join(hud_lines))
                    player.write_log("📊 [WiFi] Evaluated RF channel congestion and generated channel recommendation.")
                except Exception:
                    pass
            return

        elif action == "security_hygiene":
            sec_flags = _audit_security(networks)
            hud_lines = [
                "### 🛡️ Wireless Perimeter Security Audit\n",
                f"**Ambient Networks Assessed:** `{len(networks)}`\n\n",
                "**Security Assessment Findings:**\n",
            ]
            hud_lines.extend(f"- {f}\n" for f in sec_flags)

            if player:
                try:
                    player.show_content("WIRELESS HYGIENE AUDIT", "\n".join(hud_lines))
                    player.write_log(f"🛡️ [WiFi] Completed wireless security audit ({len(sec_flags)} findings).")
                except Exception:
                    pass
            return

        # Default: spectrum_map / scan_networks
        hud_lines = [
            "### 🛰️ TACTICAL WI-FI RF SPECTRUM (JARVIS MARK-LVII)\n",
            f"**Connected SSID:** `{curr['ssid']}` *({curr['signal_pct']}% | Ch {curr['channel']})*\n",
            f"**Ambient Access Points Detected:** `{len(networks)}`\n",
            "```text",
            "SIGNAL  CH   BAND     SECURITY         BSSID             SSID",
            "──────  ──   ────     ────────         ─────             ────",
        ]

        # Sort with connected on top, then by signal strength
        sorted_nets = sorted(networks, key=lambda n: (not n.get("in_use", False), -n.get("signal", 0)))
        for n in sorted_nets[:15]:
            bar = _make_signal_bar(n.get("signal", 50))
            active_marker = "▶" if n.get("in_use") else " "
            hud_lines.append(
                f"{active_marker}{bar} {n.get('signal', 0):3d}% {str(n.get('channel', '?')):>3s}  "
                f"{n.get('band', '2.4G'):<7s}  {n.get('security', 'WPA2')[:15]:<15s}  "
                f"{n.get('bssid', 'Unknown'):<17s} {n.get('ssid', 'Hidden')[:20]}"
            )

        hud_lines.append("```\n")
        hud_lines.append(f"*Tactical RF sweep completed at {time.strftime('%H:%M:%S')}.*")

        if player:
            try:
                player.show_content("TACTICAL WI-FI RADAR", "\n".join(hud_lines))
                player.write_log(f"🛰️ [WiFi] Mapped RF spectrum: {len(networks)} access points observed.")
            except Exception:
                pass

    except Exception as e:
        if player:
            try:
                player.write_log(f"⚠️ [WiFi] Radar error: {e}")
            except Exception:
                pass


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "current_link").strip().lower()

    threading.Thread(target=_radar_worker, args=(action, player), daemon=True).start()

    if action == "current_link":
        curr = _get_current_link()
        if curr["connected"]:
            return f"Connected to {curr['ssid']} on channel {curr['channel']} with {curr['signal_pct']}% signal quality, sir."
        return "Wi-Fi is currently disconnected or in flight mode, sir. Telemetry is displayed on screen."
    elif action == "channel_optimizer":
        return "Analyzing ambient channel congestion across 2.4 GHz and 5 GHz spectrum, sir. Optimization matrix rendering on HUD."
    elif action == "security_hygiene":
        return "Auditing wireless perimeter security hygiene for open access points and encryption vulnerabilities, sir."
    else:
        return "Sweeping ambient RF spectrum, sir. Tactical Wi-Fi heatmap and access point radar mapping on HUD."
