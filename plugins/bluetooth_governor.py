"""
plugins/bluetooth_governor.py — Linux Bluetooth device & battery manager for JARVIS.

Inspects paired devices, checks wireless peripheral battery percentages, and connects/disconnects
Bluetooth headsets and accessories using native BlueZ bluetoothctl. Zero external dependencies.
"""
from __future__ import annotations

import re
import subprocess
from typing import Any

PLUGIN = {
    "name": "bluetooth_governor",
    "description": (
        "Inspect and manage Bluetooth devices, wireless headphones, and peripherals on Linux. "
        "Can list paired devices ('list'), query battery percentages ('battery'), "
        "connect to a device ('connect'), disconnect ('disconnect'), or check adapter state ('status'). "
        "Use this tool when the user asks about Bluetooth devices, headphone battery, or connecting audio gear."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: 'list', 'battery', 'connect', 'disconnect', 'status', 'power_on', 'power_off'",
            },
            "device": {
                "type": "STRING",
                "description": "Device name or keyword to connect/inspect (e.g. 'headphones', 'speaker', 'mouse', or MAC address)",
            },
        },
        "required": ["action"],
    },
}


def _run_bt(cmd: list[str], timeout: int = 5) -> tuple[int, str]:
    try:
        r = subprocess.run(
            ["bluetoothctl"] + cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return r.returncode, (r.stdout or r.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return -1, "Bluetoothctl timed out."
    except Exception as e:
        return -1, str(e)


def _get_paired_devices() -> list[dict[str, str]]:
    code, out = _run_bt(["devices"])
    devices = []
    if code != 0 or not out:
        return devices

    for line in out.splitlines():
        # Format: Device <MAC> <Name>
        m = re.match(r"^Device\s+([0-9A-Fa-f:]{17})\s+(.*)$", line.strip())
        if m:
            devices.append({"mac": m.group(1).upper(), "name": m.group(2).strip() or "Unnamed Device"})
    return devices


def _get_device_info(mac: str) -> dict[str, str]:
    code, out = _run_bt(["info", mac])
    info: dict[str, str] = {}
    if code != 0 or not out:
        return info

    for line in out.splitlines():
        if ":" in line:
            k, _, v = line.strip().partition(":")
            info[k.strip().lower()] = v.strip()
    return info


def run(parameters: dict, player: Any = None, session_memory: Any = None) -> str:
    action = str(parameters.get("action", "list")).strip().lower()
    target_dev = str(parameters.get("device", "")).strip().lower()

    try:
        if action in ("status", "adapter"):
            code, out = _run_bt(["show"])
            powered = "Powered: yes" in out
            name_m = re.search(r"Name:\s+(.*)", out)
            adapter_name = name_m.group(1).strip() if name_m else "Bluetooth Adapter"
            state = "powered on and ready" if powered else "powered off"
            msg = f"The {adapter_name} is currently {state}."
            if player and hasattr(player, "show_content"):
                player.show_content("Bluetooth Adapter", out)
            return msg

        elif action in ("power_on", "on"):
            _run_bt(["power", "on"])
            return "Bluetooth adapter has been powered on, Sir."

        elif action in ("power_off", "off"):
            _run_bt(["power", "off"])
            return "Bluetooth adapter has been powered off."

        paired = _get_paired_devices()
        if not paired:
            return "No paired Bluetooth devices were found on this system, Sir."

        # Find target device if provided
        matched_dev = None
        if target_dev:
            for d in paired:
                if target_dev in d["name"].lower() or target_dev in d["mac"].lower():
                    matched_dev = d
                    break

        if action == "connect":
            if not matched_dev:
                return f"Could not find a paired device matching '{target_dev}'. Available devices: {', '.join(d['name'] for d in paired)}."
            code, out = _run_bt(["connect", matched_dev["mac"]], timeout=8)
            if "Successful" in out or "Connection successful" in out:
                msg = f"Successfully connected to {matched_dev['name']}."
            else:
                msg = f"Attempted to connect to {matched_dev['name']}. Status: {out[:90]}"
            if player and hasattr(player, "write_log"):
                player.write_log(f"[Bluetooth]: Connect {matched_dev['name']} -> {out[:60]}")
            return msg

        elif action == "disconnect":
            if not matched_dev:
                return f"Could not find a device matching '{target_dev}' to disconnect."
            code, out = _run_bt(["disconnect", matched_dev["mac"]], timeout=6)
            return f"Disconnected from {matched_dev['name']}."

        elif action in ("battery", "batteries"):
            connected_batteries = []
            for d in paired:
                info = _get_device_info(d["mac"])
                connected = info.get("connected", "").lower() == "yes"
                bat = info.get("battery percentage")
                if connected:
                    pct = f"{bat}%" if bat else "unknown percentage"
                    connected_batteries.append(f"{d['name']} ({pct})")

            if connected_batteries:
                msg = f"Active Bluetooth device batteries: {', '.join(connected_batteries)}."
            else:
                msg = "No connected Bluetooth devices with reporting batteries were found."

            if player and hasattr(player, "show_content"):
                player.show_content("Bluetooth Batteries", "\n".join(f" {b}" for b in connected_batteries) if connected_batteries else "No active device batteries detected.")
            return msg

        else:  # Default: 'list'
            dev_rows = []
            connected_names = []
            for d in paired:
                info = _get_device_info(d["mac"])
                connected = info.get("connected", "").lower() == "yes"
                bat = info.get("battery percentage")
                bat_str = f"[ {bat}%]" if bat else ""
                status_str = " Connected" if connected else " Disconnected"
                dev_rows.append(f"{status_str} — {d['name']} ({d['mac']}){bat_str}")
                if connected:
                    connected_names.append(d["name"])

            if connected_names:
                msg = f"Found {len(paired)} paired devices. Currently connected: {', '.join(connected_names)}."
            else:
                msg = f"Found {len(paired)} paired devices, none are currently connected."

            if player and hasattr(player, "show_content"):
                player.show_content("Paired Bluetooth Devices", "\n".join(dev_rows))
            return msg

    except Exception as e:
        return f"Could not manage Bluetooth: {e}"
