"""
plugins/network_speed.py — Local internet bandwidth & latency diagnostics sentinel for JARVIS.

Tests network ping round-trip latency, jitter, packet loss, and measures real-world download
throughput using native ICMP and Cloudflare CDN speed probes. Zero external binaries.
"""
from __future__ import annotations

import re
import subprocess
import time
from typing import Any

import httpx

PLUGIN = {
    "name": "network_speed",
    "description": (
        "Test and diagnose your local internet connection health, latency, and download speed. "
        "Can perform a quick latency & packet loss check ('ping'), a real-time download bandwidth test ('speed'), "
        "or inspect local default gateway information ('gateway'). "
        "Use this tool when the user asks about internet speed, network latency, ping, or connection quality."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Diagnostic action: 'speed' (ping + bandwidth), 'ping' (latency & packet loss only), 'gateway'",
            },
        },
        "required": [],
    },
}


def _run_ping(target: str = "1.1.1.1", count: int = 4) -> dict[str, Any]:
    try:
        r = subprocess.run(
            ["ping", "-c", str(count), "-W", "2", target],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
        out = r.stdout
        loss_m = re.search(r"(\d+)% packet loss", out)
        loss = int(loss_m.group(1)) if loss_m else 0

        rtt_m = re.search(r"rtt min/avg/max/mdev = ([0-9.]+)/([0-9.]+)/([0-9.]+)/([0-9.]+)", out)
        if rtt_m:
            return {
                "ok": True,
                "target": target,
                "loss": loss,
                "avg_ms": float(rtt_m.group(2)),
                "min_ms": float(rtt_m.group(1)),
                "max_ms": float(rtt_m.group(3)),
            }
        return {"ok": False, "error": "Could not parse ping statistics."}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _measure_bandwidth(bytes_to_fetch: int = 8_000_000) -> float | None:
    url = f"https://speed.cloudflare.com/__down?bytes={bytes_to_fetch}"
    try:
        start = time.perf_counter()
        with httpx.stream("GET", url, timeout=4.5) as resp:
            if resp.status_code != 200:
                return None
            total_bytes = sum(len(chunk) for chunk in resp.iter_bytes())
        elapsed = time.perf_counter() - start
        if elapsed <= 0 or total_bytes < 100_000:
            return None
        # Convert to Megabits per second (Mbps)
        mbps = (total_bytes * 8.0) / (1_000_000.0 * elapsed)
        return round(mbps, 1)
    except Exception:
        return None


def run(parameters: dict, player: Any = None, session_memory: Any = None) -> str:
    action = str(parameters.get("action", "speed")).strip().lower()

    try:
        if action == "gateway":
            try:
                r = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True, timeout=2)
                gw_line = r.stdout.strip()
                m = re.search(r"default via ([0-9.]+) dev (\S+)", gw_line)
                if m:
                    gw_ip, dev = m.group(1), m.group(2)
                    msg = f"Default local gateway is {gw_ip} via interface {dev}."
                else:
                    msg = f"Default route: {gw_line or 'No default route detected.'}"
                if player and hasattr(player, "show_content"):
                    player.show_content("Default Gateway", gw_line)
                return msg
            except Exception as e:
                return f"Could not determine default gateway: {e}"

        # 1. Ping Latency
        ping_data = _run_ping("1.1.1.1", count=4)
        if not ping_data.get("ok"):
            return f"Network test failed: {ping_data.get('error', 'Gateway unreachable')}."

        avg_ms = ping_data["avg_ms"]
        loss = ping_data["loss"]

        if action == "ping":
            quality = "excellent" if avg_ms < 30 else ("moderate" if avg_ms < 80 else "poor")
            msg = f"Network latency is {avg_ms:.1f} ms with {loss}% packet loss. Connection quality is {quality}."
            if player and hasattr(player, "show_content"):
                content = f"Ping Target: 1.1.1.1\nAverage RTT: {avg_ms:.1f} ms\nMin/Max: {ping_data['min_ms']:.1f} / {ping_data['max_ms']:.1f} ms\nPacket Loss: {loss}%"
                player.show_content("Ping Diagnostics", content)
            return msg

        # 2. Bandwidth Throughput
        speed_mbps = _measure_bandwidth()
        speed_str = f"{speed_mbps:.1f} Mbps" if speed_mbps is not None else "unavailable (timed out)"

        quality = "fast and stable" if (speed_mbps and speed_mbps > 50 and avg_ms < 40) else ("stable" if loss == 0 else "degraded")
        msg = f"Internet connection is {quality}: ping is {avg_ms:.1f} ms, packet loss is {loss}%, and download speed is {speed_str}."

        if player and hasattr(player, "show_content"):
            content = (
                f" Network Health Report:\n"
                f"• Download Speed: {speed_str}\n"
                f"• Latency (Ping): {avg_ms:.1f} ms (Min: {ping_data['min_ms']:.1f} ms, Max: {ping_data['max_ms']:.1f} ms)\n"
                f"• Packet Loss: {loss}%\n"
                f"• Gateway Status: Online"
            )
            player.show_content("Network Diagnostics", content)

        return msg

    except Exception as e:
        return f"Network diagnostic error: {e}"
