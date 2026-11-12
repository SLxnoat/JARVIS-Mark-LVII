"""
plugins/smart_unit_converter.py - Technical Data Rates, Storage & Unit Engine.

Provides instant voice-driven conversions for technical, networking, storage, scientific,
and engineering quantities, including download time estimation and binary vs decimal compute storage.

Adheres strictly to AGENTS.md:
- Never instantiates Qt widgets on worker threads.
- Thread-safe HUD updates via player.show_content() and player.write_log().
- Fast returns; non-blocking; never raises unhandled exceptions.
- Handles player=None gracefully.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

PLUGIN: Dict[str, Any] = {
    "name": "smart_unit_converter",
    "description": (
        "High-precision technical, networking, and scientific unit conversion engine. "
        "Converts digital data transfer rates (Mbps to GB/h), binary vs decimal storage (TiB to TB / GiB), "
        "download/transfer duration estimates, temperature, pressure, energy, and speed."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "value": {
                "type": "NUMBER",
                "description": "Numerical magnitude to convert (e.g. 500, 2.5).",
            },
            "from_unit": {
                "type": "STRING",
                "description": "Source unit (e.g. 'Mbps', 'Gbps', 'TiB', 'TB', 'GB/h', 'celsius', 'psi', 'km/h').",
            },
            "to_unit": {
                "type": "STRING",
                "description": "Destination unit (e.g. 'GB/h', 'MB/s', 'GiB', 'TB', 'fahrenheit', 'bar', 'mph').",
            },
            "calculation_type": {
                "type": "STRING",
                "description": "Type of calculation: 'convert' (standard conversion) or 'download_time' (file transfer estimate).",
                "enum": ["convert", "download_time"],
            },
            "file_size_gb": {
                "type": "NUMBER",
                "description": "For 'download_time' calculation: File size in Gigabytes (e.g. 75).",
            },
            "speed_mbps": {
                "type": "NUMBER",
                "description": "For 'download_time' calculation: Network bandwidth in Megabits per second (e.g. 100).",
            },
        },
    },
}

# Base units definition:
# Storage base: Bytes (B)
STORAGE_UNITS: Dict[str, float] = {
    "b": 1.0,
    "byte": 1.0,
    "bytes": 1.0,
    "kb": 1e3,
    "mb": 1e6,
    "gb": 1e9,
    "tb": 1e12,
    "pb": 1e15,
    "kib": 1024.0,
    "mib": 1024.0 ** 2,
    "gib": 1024.0 ** 3,
    "tib": 1024.0 ** 4,
    "pib": 1024.0 ** 5,
}

# Data transfer rates base: bits per second (bps)
DATA_RATE_UNITS: Dict[str, float] = {
    "bps": 1.0,
    "kbps": 1e3,
    "mbps": 1e6,
    "gbps": 1e9,
    "tbps": 1e12,
    "b/s": 8.0,
    "kb/s": 8.0 * 1e3,
    "mb/s": 8.0 * 1e6,
    "gb/s": 8.0 * 1e9,
    "gb/h": (8.0 * 1e9) / 3600.0,
    "gb/hr": (8.0 * 1e9) / 3600.0,
    "tb/day": (8.0 * 1e12) / 86400.0,
    "kib/s": 8.0 * 1024.0,
    "mib/s": 8.0 * (1024.0 ** 2),
    "gib/s": 8.0 * (1024.0 ** 3),
}

# Pressure base: Pascal (Pa)
PRESSURE_UNITS: Dict[str, float] = {
    "pa": 1.0,
    "kpa": 1e3,
    "mpa": 1e6,
    "bar": 1e5,
    "mbar": 1e2,
    "psi": 6894.757,
    "atm": 101325.0,
    "torr": 133.322,
    "mmhg": 133.322,
}

# Speed base: meters per second (m/s)
SPEED_UNITS: Dict[str, float] = {
    "m/s": 1.0,
    "mps": 1.0,
    "km/h": 1.0 / 3.6,
    "kmh": 1.0 / 3.6,
    "kph": 1.0 / 3.6,
    "mph": 0.44704,
    "knots": 0.514444,
    "knot": 0.514444,
    "fps": 0.3048,
}

# Energy base: Joules (J)
ENERGY_UNITS: Dict[str, float] = {
    "j": 1.0,
    "joule": 1.0,
    "joules": 1.0,
    "kj": 1e3,
    "wh": 3600.0,
    "kwh": 3.6e6,
    "mwh": 3.6e9,
    "cal": 4.184,
    "kcal": 4184.0,
    "btu": 1055.06,
}


def _convert_temperature(val: float, from_u: str, to_u: str) -> float:
    # Convert from source to Kelvin
    if from_u in ("c", "celsius"):
        k = val + 273.15
    elif from_u in ("f", "fahrenheit"):
        k = (val - 32.0) * (5.0 / 9.0) + 273.15
    elif from_u in ("k", "kelvin"):
        k = val
    else:
        raise ValueError(f"Unknown temperature unit: {from_u}")

    # Convert Kelvin to destination
    if to_u in ("c", "celsius"):
        return k - 273.15
    elif to_u in ("f", "fahrenheit"):
        return (k - 273.15) * (9.0 / 5.0) + 32.0
    elif to_u in ("k", "kelvin"):
        return k
    raise ValueError(f"Unknown temperature unit: {to_u}")


def _format_time(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    mins, secs = divmod(int(seconds), 60)
    hours, mins = divmod(mins, 60)
    days, hours = divmod(hours, 24)
    parts = []
    if days > 0:
        parts.append(f"{days} day{'s' if days > 1 else ''}")
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
    if mins > 0:
        parts.append(f"{mins} minute{'s' if mins > 1 else ''}")
    if secs > 0 or not parts:
        parts.append(f"{secs} second{'s' if secs > 1 else ''}")
    return ", ".join(parts)


def run(parameters: dict | None = None, player=None, session_memory=None) -> str:
    try:
        params = parameters or {}
        calc_type = params.get("calculation_type", "convert")

        # 1. Download Time Calculation
        if calc_type == "download_time" or "file_size_gb" in params or "speed_mbps" in params:
            size_gb = float(params.get("file_size_gb", 10.0))
            speed_mbps = float(params.get("speed_mbps", 100.0))

            if speed_mbps <= 0:
                return "Network speed must be greater than zero, sir."

            # size in bits: size_gb * 1e9 bytes * 8 bits
            total_bits = size_gb * 1e9 * 8.0
            bits_per_sec = speed_mbps * 1e6
            duration_sec = total_bits / bits_per_sec
            time_str = _format_time(duration_sec)

            rate_mb_s = speed_mbps / 8.0

            md = (
                f"## ⏱️ Download Time Estimation\n\n"
                f"- **Payload Size:** `{size_gb:.2f} GB` ({size_gb * 1000:.0f} MB)\n"
                f"- **Bandwidth Speed:** `{speed_mbps:.1f} Mbps` (~`{rate_mb_s:.2f} MB/s` throughput)\n"
                f"- **Estimated Transfer Duration:** **`{time_str}`**\n\n"
                f"| Overhead Estimate | Duration |\n"
                f"|:---|:---|\n"
                f"| Ideal (100% throughput) | `{time_str}` |\n"
                f"| Realistic (85% TCP efficiency) | `{_format_time(duration_sec / 0.85)}` |\n"
                f"| Congested (60% throughput) | `{_format_time(duration_sec / 0.60)}` |\n"
            )
            if player:
                player.show_content("Download Time Calculator", md)
                player.write_log(f"Converter: {size_gb}GB at {speed_mbps}Mbps is {time_str}")

            return f"Downloading a {size_gb:.0f} Gigabyte file at {speed_mbps:.0f} Megabits per second will take approximately {time_str}, sir."

        # 2. General Unit Conversion
        val = float(params.get("value", 1.0))
        from_u = str(params.get("from_unit", "")).strip().lower()
        to_u = str(params.get("to_unit", "")).strip().lower()

        if not from_u or not to_u:
            return "Please provide both source and destination units for conversion, sir."

        result_val: float
        domain_name = ""

        # Temperature
        if from_u in ("c", "celsius", "f", "fahrenheit", "k", "kelvin"):
            result_val = _convert_temperature(val, from_u, to_u)
            domain_name = "Thermal Temperature"

        # Data Transfer Rates
        elif from_u in DATA_RATE_UNITS and to_u in DATA_RATE_UNITS:
            base_bps = val * DATA_RATE_UNITS[from_u]
            result_val = base_bps / DATA_RATE_UNITS[to_u]
            domain_name = "Data Transfer Bandwidth"

        # Digital Storage
        elif from_u in STORAGE_UNITS and to_u in STORAGE_UNITS:
            base_bytes = val * STORAGE_UNITS[from_u]
            result_val = base_bytes / STORAGE_UNITS[to_u]
            domain_name = "Digital Compute Storage"

        # Pressure
        elif from_u in PRESSURE_UNITS and to_u in PRESSURE_UNITS:
            base_pa = val * PRESSURE_UNITS[from_u]
            result_val = base_pa / PRESSURE_UNITS[to_u]
            domain_name = "Mechanical Pressure"

        # Speed
        elif from_u in SPEED_UNITS and to_u in SPEED_UNITS:
            base_mps = val * SPEED_UNITS[from_u]
            result_val = base_mps / SPEED_UNITS[to_u]
            domain_name = "Velocity & Speed"

        # Energy
        elif from_u in ENERGY_UNITS and to_u in ENERGY_UNITS:
            base_j = val * ENERGY_UNITS[from_u]
            result_val = base_j / ENERGY_UNITS[to_u]
            domain_name = "Energy & Work"

        else:
            return f"Sir, I do not have a compatible conversion path between '{from_u}' and '{to_u}'."

        # Format number nicely
        if abs(result_val) >= 1000 or (abs(result_val) < 0.01 and result_val != 0):
            res_str = f"{result_val:,.4g}"
        else:
            res_str = f"{result_val:,.2f}"

        spoken = f"{val:g} {from_u.upper()} is equal to {res_str} {to_u.upper()}, sir."

        md = (
            f"## 📐 Scientific & Technical Conversion: {domain_name}\n\n"
            f"> **Input:** `{val:g} {from_u.upper()}` &nbsp; ➡️ &nbsp; **Output:** **`{res_str} {to_u.upper()}`**\n\n"
            f"| Parameter | Value |\n"
            f"|:---|:---|\n"
            f"| **Measurement Domain** | {domain_name} |\n"
            f"| **Source Magnitude** | `{val:g}` `{from_u}` |\n"
            f"| **Target Magnitude** | **`{res_str}`** `{to_u}` |\n"
        )

        # Highlight binary compute storage difference if applicable
        if from_u in ("tb", "tib") or to_u in ("tb", "tib"):
            md += (
                f"\n> 💡 **Storage Insight:** Decimal Terabytes (`1 TB = 10^12 bytes`) are commonly used by drive makers, "
                f"while Operating Systems report binary Tebibytes (`1 TiB = 2^40 bytes = 1.0995 TB`).\n"
            )

        if player:
            player.show_content("Unit Conversion", md)
            player.write_log(f"Converter: {val} {from_u} -> {res_str} {to_u}")

        return spoken

    except Exception as e:
        err = f"Converter error: {e}"
        if player:
            player.write_log(err)
        return f"Sir, an error occurred during unit conversion: {e}"
