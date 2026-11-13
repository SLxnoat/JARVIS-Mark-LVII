"""
plugins/weather_astronomy_briefing.py - Live Hourly Weather, Rain Radar & Astronomical Forecast.

Provides real-time meteorological forecasts, hourly precipitation probability (rain radar),
UV index, wind speeds, and astronomical solar/lunar data using the 100% free Open-Meteo API.
Displays a high-density hourly forecast card on the HUD without opening external browser windows.

Adheres strictly to AGENTS.md:
- Never instantiates Qt widgets on worker threads.
- Thread-safe HUD updates via player.show_content() and player.write_log().
- Fast returns; non-blocking; never raises unhandled exceptions.
- Handles player=None gracefully.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx

PLUGIN: Dict[str, Any] = {
    "name": "weather_astronomy_briefing",
    "description": (
        "Provides real-time meteorological forecasts, hourly precipitation probability (rain radar), "
        "UV index, wind speeds, and astronomical solar schedule using the 100% free Open-Meteo API. "
        "Displays a rich hourly forecast card on the HUD without opening browser windows."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "city": {
                "type": "STRING",
                "description": "City name to look up (e.g. 'London', 'Colombo', 'Tokyo', 'San Francisco'). Defaults to 'London' if unspecified.",
            },
            "hourly": {
                "type": "BOOLEAN",
                "description": "Whether to include next 12-hour rain probability and temperature breakdown (default true).",
            },
            "astronomy": {
                "type": "BOOLEAN",
                "description": "Whether to include sunrise, sunset, and daylight details (default true).",
            },
        },
    },
}

WMO_CODES: Dict[int, Tuple[str, str]] = {
    0: ("Clear sky", ""),
    1: ("Mainly clear", "️"),
    2: ("Partly cloudy", ""),
    3: ("Overcast", ""),
    45: ("Foggy", "️"),
    48: ("Depositing rime fog", "️"),
    51: ("Light drizzle", "️"),
    53: ("Moderate drizzle", "️"),
    55: ("Dense drizzle", "️"),
    61: ("Slight rain", "️"),
    63: ("Moderate rain", "️"),
    65: ("Heavy rain", "️"),
    71: ("Slight snow fall", "️"),
    73: ("Moderate snow fall", "️"),
    75: ("Heavy snow fall", "❄️"),
    80: ("Slight rain showers", "️"),
    81: ("Moderate rain showers", "️"),
    82: ("Violent rain showers", ""),
    95: ("Thunderstorm", ""),
    96: ("Thunderstorm with slight hail", ""),
    99: ("Thunderstorm with heavy hail", ""),
}


def _interpret_wmo(code: int) -> Tuple[str, str]:
    return WMO_CODES.get(code, ("Variable conditions", "️"))


def _make_bar(pct: int, length: int = 10) -> str:
    filled = max(0, min(length, round((pct / 100.0) * length)))
    return "█" * filled + "░" * (length - filled)


def _geocode_city(city_name: str) -> Optional[Tuple[str, float, float, str]]:
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={city_name}&count=1"
    try:
        resp = httpx.get(url, timeout=4.0)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results")
            if results and len(results) > 0:
                first = results[0]
                name = first.get("name", city_name)
                lat = float(first["latitude"])
                lon = float(first["longitude"])
                country = first.get("country", "")
                return name, lat, lon, country
    except Exception:
        pass
    return None


def run(parameters: dict | None = None, player=None, session_memory=None) -> str:
    try:
        params = parameters or {}
        city_input = params.get("city", "London").strip()
        include_hourly = params.get("hourly", True)
        include_astronomy = params.get("astronomy", True)

        geo = _geocode_city(city_input)
        if not geo:
            # Fallback coordinates for common cities if offline or geocode fails
            fallback_coords = {
                "london": ("London", 51.5085, -0.1257, "United Kingdom"),
                "tokyo": ("Tokyo", 35.6895, 139.6917, "Japan"),
                "colombo": ("Colombo", 6.9271, 79.8612, "Sri Lanka"),
                "new york": ("New York", 40.7128, -74.0060, "United States"),
            }
            geo = fallback_coords.get(city_input.lower())

        if not geo:
            # If completely unreachable and unknown city
            err = f"Sir, I could not resolve coordinates for '{city_input}'. Please check connection or city name."
            if player:
                player.write_log(f"Weather: Failed to geocode {city_input}")
            return err

        city_name, lat, lon, country = geo

        forecast_url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m"
            f"&hourly=temperature_2m,precipitation_probability,weather_code"
            f"&daily=sunrise,sunset,uv_index_max&timezone=auto"
        )

        try:
            resp = httpx.get(forecast_url, timeout=5.0)
            if resp.status_code != 200:
                return f"Sir, Open-Meteo weather service responded with HTTP status {resp.status_code}."
            data = resp.json()
        except Exception as e:
            msg = f"Sir, meteorological service is temporarily offline or unreachable: {e}"
            if player:
                player.write_log(f"Weather: Network error ({e})")
            return msg

        curr = data.get("current", {})
        temp = curr.get("temperature_2m", 0.0)
        app_temp = curr.get("apparent_temperature", temp)
        humidity = curr.get("relative_humidity_2m", 0)
        wind = curr.get("wind_speed_10m", 0.0)
        wmo_code = curr.get("weather_code", 0)
        desc, emoji = _interpret_wmo(wmo_code)

        daily = data.get("daily", {})
        uv_max = (daily.get("uv_index_max") or [0.0])[0]
        sunrises = daily.get("sunrise") or [""]
        sunsets = daily.get("sunset") or [""]
        sunrise_time = sunrises[0].split("T")[-1] if sunrises and "T" in sunrises[0] else "06:00"
        sunset_time = sunsets[0].split("T")[-1] if sunsets and "T" in sunsets[0] else "18:00"

        # Hourly rain radar & forecast table
        hourly = data.get("hourly", {})
        hourly_times = hourly.get("time", [])
        hourly_temps = hourly.get("temperature_2m", [])
        hourly_pops = hourly.get("precipitation_probability", [])
        hourly_codes = hourly.get("weather_code", [])

        hourly_rows: List[str] = []
        max_pop = 0
        max_pop_hour = ""

        # Take next 12 hours from current hour
        current_iso_hour = curr.get("time", "")[:13]
        start_idx = 0
        for i, t_str in enumerate(hourly_times):
            if t_str.startswith(current_iso_hour):
                start_idx = i
                break

        for i in range(start_idx, min(start_idx + 12, len(hourly_times))):
            t_label = hourly_times[i].split("T")[-1]
            t_temp = hourly_temps[i] if i < len(hourly_temps) else temp
            pop = hourly_pops[i] if i < len(hourly_pops) else 0
            code = hourly_codes[i] if i < len(hourly_codes) else 0
            c_desc, c_emoji = _interpret_wmo(code)

            if pop > max_pop:
                max_pop = pop
                max_pop_hour = t_label

            bar = _make_bar(pop)
            hourly_rows.append(f"| `{t_label}` | {c_emoji} {t_temp:.1f}°C | `{bar}` **{pop}%** | {c_desc} |")

        # Spoken briefing construction
        location_label = f"{city_name}, {country}" if country else city_name
        spoken = (
            f"Current conditions for {location_label}: {temp:.1f}° Celsius, {desc.lower()}, "
            f"feeling like {app_temp:.1f}° with wind at {wind:.0f} kilometers per hour."
        )
        if max_pop > 25:
            spoken += f" Rain probability peaks at {max_pop}% around {max_pop_hour}, sir."
        else:
            spoken += " Low chance of rain expected today, sir."

        # Markdown HUD Card
        md = (
            f"## {emoji} Weather & Atmospheric Briefing: `{location_label}`\n\n"
            f"> **Conditions:** `{desc}` &nbsp;|&nbsp; **Temp:** `{temp:.1f}°C` (Feels like `{app_temp:.1f}°C`) &nbsp;|&nbsp; **Wind:** `{wind:.1f} km/h`\n\n"
            f"### ️ Current Atmospheric Telemetry\n\n"
            f"| Metric | Measurement | Rating / Range |\n"
            f"|:---|:---|:---|\n"
            f"| **Ambient Temperature** | `{temp:.1f} °C` | Real-time sensor readout |\n"
            f"| **Apparent Temperature** | `{app_temp:.1f} °C` | Wind-chill & heat index factor |\n"
            f"| **Relative Humidity** | `{humidity}%` | Ambient moisture level |\n"
            f"| **Wind Velocity** | `{wind:.1f} km/h` | Surface 10m anemometer |\n"
            f"| **Max UV Index** | `{uv_max:.1f}` | {'Low' if uv_max < 3 else ('Moderate' if uv_max < 6 else 'Very High')} |\n\n"
        )

        if include_astronomy:
            md += (
                f"###  Solar & Daylight Schedule\n\n"
                f"- **Sunrise:** `{sunrise_time}`\n"
                f"- **Sunset:** `{sunset_time}`\n"
                f"- **Coordinates:** `{lat:.4f}°N, {lon:.4f}°E`\n\n"
            )

        if include_hourly and hourly_rows:
            md += (
                f"### ️ Next 12-Hour Rain Radar & Temperature Curve\n\n"
                f"| Time | Temp | Precipitation Probability | Sky Condition |\n"
                f"|:---|:---|:---|:---|\n"
                + "\n".join(hourly_rows)
                + "\n\n"
            )

        md += f"---\n*Source: Open-Meteo Public Meteorological Model • Lat {lat:.2f}, Lon {lon:.2f}*"

        if player:
            player.show_content(f"Weather: {city_name}", md)
            player.write_log(f"Weather: {city_name} is {temp:.1f}°C, {desc} (Rain max {max_pop}%)")

        return spoken

    except Exception as e:
        err = f"Weather briefing error: {e}"
        if player:
            player.write_log(err)
        return f"Sir, I was unable to retrieve the weather and astronomy briefing: {e}"
