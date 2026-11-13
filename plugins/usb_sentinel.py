"""
plugins/usb_sentinel.py - Physical USB Port Sentry & BadUSB Defense Sentinel.

Iron Man / JARVIS style perimeter defense:
- Real-time enumeration of connected physical USB bus endpoints.
- Identifies USB device classes (HID, Storage, Hub, Communications, Vendor-Specific).
- BadUSB / Rubber Ducky defense: Flags unknown HID devices claiming to be keyboards.
- Audits vendor IDs, product strings, and bus topologies.
- Renders a tactical physical port map on the HUD via player.show_content().

Adheres strictly to AGENTS.md:
- No Qt widgets on worker threads.
- Thread-safe HUD feedback via player.show_content() and player.write_log().
- Safe non-blocking execution on background daemon thread.
- Never raises exceptions, returns concise spoken feedback.
- Handles player=None gracefully.
"""
from __future__ import annotations

import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

PLUGIN = {
    "name": "usb_sentinel",
    "description": (
        "JARVIS USB Sentry: Audits physical USB ports, classifies connected peripherals, "
        "and detects BadUSB / Rubber Ducky spoofing attacks (e.g. storage dongles or microcontrollers "
        "impersonating keyboards). Renders a physical port matrix on the HUD."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "Action to perform: 'audit_devices' (list all physical USB devices), "
                    "'badusb_check' (scan for suspicious HID keyboards / injectors), "
                    "or 'full_scan' (complete USB security audit). Default 'full_scan'."
                ),
                "enum": ["audit_devices", "badusb_check", "full_scan"],
            },
        },
        "required": ["action"],
    },
}

_KNOWN_CLASSES = {
    "01": "Audio",
    "02": "Communications / Modem",
    "03": "HID (Human Interface Device)",
    "05": "Physical Interface",
    "06": "Still Imaging",
    "07": "Printer",
    "08": "Mass Storage (Flash / HDD)",
    "09": "USB Hub",
    "0a": "CDC-Data",
    "0b": "Smart Card",
    "0d": "Content Security",
    "0e": "Video / Webcam",
    "e0": "Wireless Controller (Bluetooth/WiFi)",
    "ef": "Miscellaneous / Composite",
    "ff": "Vendor Specific",
}


def _scan_usb_sysfs() -> List[Dict[str, Any]]:
    devices = []
    usb_base = Path("/sys/bus/usb/devices")
    if not usb_base.exists():
        return devices

    for dev_path in sorted(usb_base.glob("*")):
        # Only inspect top-level devices (skip interface endpoints like 1-1:1.0)
        if ":" in dev_path.name:
            continue

        try:
            id_vendor_f = dev_path / "idVendor"
            id_product_f = dev_path / "idProduct"
            if not id_vendor_f.exists() or not id_product_f.exists():
                continue

            vid = id_vendor_f.read_text().strip()
            pid = id_product_f.read_text().strip()
            bus_num = (dev_path / "busnum").read_text().strip() if (dev_path / "busnum").exists() else "1"
            dev_num = (dev_path / "devnum").read_text().strip() if (dev_path / "devnum").exists() else "1"
            product = (dev_path / "product").read_text().strip() if (dev_path / "product").exists() else "Unknown Device"
            manufacturer = (dev_path / "manufacturer").read_text().strip() if (dev_path / "manufacturer").exists() else "Generic"
            speed = (dev_path / "speed").read_text().strip() if (dev_path / "speed").exists() else "480"

            # Check interfaces to discover device classes
            if_classes = []
            is_keyboard = False
            for if_dir in dev_path.glob("*-*:*"):
                b_class_f = if_dir / "bInterfaceClass"
                b_proto_f = if_dir / "bInterfaceProtocol"
                if b_class_f.exists():
                    cls_code = b_class_f.read_text().strip().lower()
                    if_classes.append(cls_code)
                    # Protocol 1 in HID class = Keyboard
                    if cls_code == "03" and b_proto_f.exists() and b_proto_f.read_text().strip() == "01":
                        is_keyboard = True

            class_names = [_KNOWN_CLASSES.get(c, f"Class 0x{c}") for c in set(if_classes)]

            # Rubber Ducky / BadUSB heuristic check:
            # - Device identifies as a keyboard, but product name suggests microcontroller, flash storage, or generic Raspberry Pi / Arduino
            # - Or composite device pairing mass storage + keyboard
            is_suspicious = False
            flag_reason = ""
            name_lower = f"{product} {manufacturer}".lower()

            if is_keyboard:
                suspicious_keywords = ["teensy", "digispark", "rubber ducky", "pico", "arduino", "atmega", "ch340", "ftdi", "badusb", "malduino"]
                for kw in suspicious_keywords:
                    if kw in name_lower:
                        is_suspicious = True
                        flag_reason = f"Microcontroller signature '{kw}' detected on HID keyboard device."
                        break
                if "08" in if_classes and "03" in if_classes:
                    is_suspicious = True
                    flag_reason = "Composite Mass Storage + HID Keyboard detected (Potential Ducky payload)."

            devices.append({
                "bus": bus_num,
                "dev": dev_num,
                "vid": vid,
                "pid": pid,
                "product": product,
                "manufacturer": manufacturer,
                "speed": f"{speed} Mbps",
                "classes": class_names or ["Standard Device"],
                "is_keyboard": is_keyboard,
                "is_suspicious": is_suspicious,
                "flag_reason": flag_reason,
            })
        except Exception:
            continue

    return devices


def _scan_usb_lsusb() -> List[Dict[str, Any]]:
    devices = []
    try:
        r = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=3)
        for line in r.stdout.splitlines():
            # Bus 001 Device 002: ID 8087:0024 Intel Corp. ...
            m = re.match(r"Bus\s+(\d+)\s+Device\s+(\d+):\s+ID\s+([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\s+(.*)", line)
            if m:
                devices.append({
                    "bus": m.group(1),
                    "dev": m.group(2),
                    "vid": m.group(3),
                    "pid": m.group(4),
                    "product": m.group(5)[:40],
                    "manufacturer": "Discovered via lsusb",
                    "speed": "USB",
                    "classes": ["Discovered Endpoint"],
                    "is_keyboard": False,
                    "is_suspicious": False,
                    "flag_reason": "",
                })
    except Exception:
        pass
    return devices


def _render_hud_card(action: str, devices: List[Dict[str, Any]]) -> str:
    lines = [
        "### ️ TACTICAL USB SENTRY & PORT SHIELD (JARVIS MARK-LVII)\n",
        f"**Active Physical Ports Monitored:** `{len(devices)}`\n",
    ]

    suspicious = [d for d in devices if d.get("is_suspicious")]
    if suspicious:
        lines.append(f" **SECURITY ALERT: {len(suspicious)} UNVERIFIED/ANOMALOUS USB DEVICE(S) DETECTED!**")
        for s in suspicious:
            lines.append(f"-  **{s['product']}** (VID: `{s['vid']}`, PID: `{s['pid']}`) — `{s['flag_reason']}`")
        lines.append("")
    else:
        lines.append(" **Perimeter Integrity:** `SECURE` — No BadUSB or HID injection devices detected.\n")

    lines.append("####  Connected Physical USB Peripherals")
    lines.append("```text")
    for d in devices:
        cls_str = ", ".join(d["classes"])
        status_tag = "[ALERT ]" if d.get("is_suspicious") else ("[KEYBOARD ⌨️]" if d.get("is_keyboard") else "")
        lines.append(f"Bus {d['bus']} Dev {d['dev']} | {d['vid']}:{d['pid']} | {d['product'][:30]:30s} | {cls_str}{status_tag}")
    lines.append("```\n")

    lines.append(f"*Hardware scan concluded at {time.strftime('%H:%M:%S')}.*")
    return "\n".join(lines)


def _worker(action: str, player):
    try:
        devices = _scan_usb_sysfs()
        if not devices:
            devices = _scan_usb_lsusb()

        card = _render_hud_card(action, devices)
        if player:
            try:
                player.show_content("TACTICAL USB SENTRY", card)
                susp = [d for d in devices if d.get("is_suspicious")]
                if susp:
                    if hasattr(player, "trigger_defense_alert"):
                        player.trigger_defense_alert("ROGUE_USB", f"{len(susp)} suspicious USB device(s) flagged")
                    player.write_log(f"[USBSentry] Alert: {len(susp)} suspicious USB device(s) flagged!")
                else:
                    player.write_log(f"️ [USBSentry] Audited {len(devices)} physical USB devices. Perimeter secure.")
            except Exception:
                pass
    except Exception as e:
        if player:
            try:
                player.write_log(f"[USBSentry] Error: {e}")
            except Exception:
                pass


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        action = str(parameters.get("action") or "full_scan").strip().lower()
        if action not in ("audit_devices", "badusb_check", "full_scan"):
            action = "full_scan"

        threading.Thread(target=_worker, args=(action, player), daemon=True).start()

        if action == "badusb_check":
            return "Scanning physical USB bus for BadUSB microcontrollers and unauthorized HID keyboard injectors, sir."
        elif action == "audit_devices":
            return "Enumerating all connected physical USB devices and interface descriptors, sir."
        else:
            return "Conducting a physical USB perimeter sweep, sir. Port security status will appear on your HUD."
    except Exception as e:
        return f"Sir, USB sentry encountered an issue: {e}"
