"""
plugins/audio_spectrum_analyzer.py - Acoustic Sensor & Ambient Audio Spectrum Radar.

Iron Man / JARVIS style environmental acoustics:
- Samples the workstation microphone to compute instant 20 Hz - 20 kHz FFT spectrum.
- Calculates ambient room noise floor (dB SPL estimate) to determine acoustic quietness.
- Detects dominant harmonic frequencies (e.g. 50/60 Hz mains hum, fan coil whine).
- Renders an ASCII audio spectrum waterfall graph on the HUD via player.show_content().

Adheres strictly to AGENTS.md:
- No Qt widgets on worker threads.
- Thread-safe HUD feedback via player.show_content() and player.write_log().
- Safe non-blocking execution via background daemon thread.
- Never raises exceptions, returns concise spoken feedback.
- Handles player=None gracefully.
"""
from __future__ import annotations

import math
import sys
import threading
import time
from typing import Any, Dict, List, Tuple

import numpy as np

PLUGIN = {
    "name": "audio_spectrum_analyzer",
    "description": (
        "JARVIS Acoustic Sensor: Analyzes ambient room noise, computes FFT frequency "
        "distribution (20 Hz - 20 kHz), measures background noise floor (dB SPL), and detects "
        "fan hum, acoustic resonance, or coil whine. Displays an acoustic spectrum on the HUD."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "Action to perform: 'sample_spectrum' (FFT frequency graph), 'noise_floor' "
                    "(ambient dB level check), 'frequency_peaks' (detect dominant frequencies), "
                    "or 'full_analysis' (complete acoustic audit). Default 'full_analysis'."
                ),
                "enum": ["sample_spectrum", "noise_floor", "frequency_peaks", "full_analysis"],
            },
            "duration_seconds": {
                "type": "NUMBER",
                "description": "Duration to sample ambient audio in seconds (default 1.0, max 3.0).",
            },
        },
        "required": [],
    },
}

_SAMPLE_RATE = 16000


def _record_audio_slice(duration_sec: float) -> np.ndarray | None:
    """Record a lightweight PCM slice via sounddevice or return None if mic unavailable."""
    try:
        import sounddevice as sd
        frames = int(duration_sec * _SAMPLE_RATE)
        # Record 1 channel int16
        recording = sd.rec(frames, samplerate=_SAMPLE_RATE, channels=1, dtype="float32", blocking=True)
        return recording.flatten()
    except Exception:
        return None


def _compute_acoustic_metrics(samples: np.ndarray) -> Dict[str, Any]:
    # RMS loudness
    rms = float(np.sqrt(np.mean(samples ** 2))) if len(samples) > 0 else 0.0
    # Estimate dBFS (dB relative to full scale)
    dbfs = 20 * math.log10(rms) if rms > 1e-6 else -96.0

    # FFT analysis
    n = len(samples)
    fft_vals = np.abs(np.fft.rfft(samples * np.hanning(n)))
    freqs = np.fft.rfftfreq(n, 1.0 / _SAMPLE_RATE)

    # Find dominant peaks above noise
    peak_indices = np.argsort(fft_vals)[-5:][::-1]
    peaks = []
    for idx in peak_indices:
        f = freqs[idx]
        mag = fft_vals[idx]
        if f > 20 and mag > 0.1:  # Filter out sub-audible drift
            peaks.append((round(float(f), 1), round(float(mag), 2)))

    # Compute 8-band octave spectrum for HUD display:
    # Sub-Bass (20-60Hz), Bass (60-250Hz), Low-Mid (250-500Hz), Mid (500-2kHz),
    # High-Mid (2k-4kHz), Presence (4k-6kHz), Brilliance (6k-8kHz), Treble (8k-16kHz)
    bands = [
        ("20-60Hz", 20, 60),
        ("60-250Hz", 60, 250),
        ("250-500Hz", 250, 500),
        ("500-2kHz", 500, 2000),
        ("2k-4kHz", 2000, 4000),
        ("4k-6kHz", 4000, 6000),
        ("6k-8kHz", 6000, 8000),
        ("8k-16kHz", 8000, 16000),
    ]

    band_energies = []
    for label, low, high in bands:
        mask = (freqs >= low) & (freqs < high)
        energy = float(np.mean(fft_vals[mask])) if np.any(mask) else 0.0
        band_energies.append((label, energy))

    return {
        "rms": round(rms, 4),
        "dbfs": round(dbfs, 1),
        "peaks": peaks[:3],
        "bands": band_energies,
    }


def _render_ascii_bars(bands: List[Tuple[str, float]]) -> List[str]:
    lines = []
    max_e = max((e for _, e in bands), default=1.0)
    max_e = max(max_e, 0.01)

    for label, energy in bands:
        ratio = min(1.0, energy / max_e)
        bar_len = int(ratio * 24)
        bar = "█" * bar_len + "░" * (24 - bar_len)
        lines.append(f"{label:10s} [{bar}] {energy:.2f}")
    return lines


def _render_hud_card(action: str, metrics: Dict[str, Any] | None) -> str:
    lines = [
        "### 🎙️ ACOUSTIC SPECTRUM RADAR (JARVIS MARK-LVII)\n",
    ]

    if not metrics:
        lines.append("⚠️ **Microphone Stream Inaccessible:** Audio hardware is currently dedicated to another subsystem or uninitialized.\n")
        lines.append("*Ensure PortAudio / ALSA microphone access is permitted.*")
        return "\n".join(lines)

    db = metrics["dbfs"]
    quietness = "Whisper / Library 🟢" if db < -45 else ("Quiet Room 🟡" if db < -30 else "Moderate / Active Audio 🟠" if db < -15 else "Loud Environment 🔴")

    lines.append(f"**Ambient Noise Floor:** `{db} dBFS` *({quietness})*")
    lines.append(f"**Signal RMS Energy:** `{metrics['rms']}`\n")

    lines.append("#### 📊 Octave Energy Spectrum")
    lines.append("```text")
    lines.extend(_render_ascii_bars(metrics["bands"]))
    lines.append("```\n")

    lines.append("#### 🔍 Dominant Harmonic Peaks")
    if metrics["peaks"]:
        for f, mag in metrics["peaks"]:
            note = ""
            if 48 <= f <= 62:
                note = " (Possible 50/60 Hz AC Mains Hum)"
            elif 800 <= f <= 2500:
                note = " (Human Speech / Vocal Range)"
            elif f >= 3000:
                note = " (High-frequency resonance / Fan / Coil Whine)"
            lines.append(f"- **`{f} Hz`** — Relative Magnitude: `{mag}`{note}")
    else:
        lines.append("- *No prominent harmonic resonant peaks detected; uniform ambient noise.*")

    lines.append(f"\n*Acoustic sample captured at {time.strftime('%H:%M:%S')}.*")
    return "\n".join(lines)


def _worker(action: str, duration: float, player):
    try:
        samples = _record_audio_slice(duration)
        metrics = _compute_acoustic_metrics(samples) if samples is not None else None
        card = _render_hud_card(action, metrics)

        if player:
            try:
                player.show_content("ACOUSTIC SPECTRUM RADAR", card)
                if metrics:
                    player.write_log(f"🎙️ [AcousticRadar] Sampled {duration}s: Noise floor {metrics['dbfs']} dBFS.")
                else:
                    player.write_log("🎙️ [AcousticRadar] Microphone capture yielded no audio stream.")
            except Exception:
                pass
    except Exception as e:
        if player:
            try:
                player.write_log(f"⚠️ [AcousticRadar] Error: {e}")
            except Exception:
                pass


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        action = str(parameters.get("action") or parameters.get("mode") or "full_analysis").strip().lower()
        if action not in ("sample_spectrum", "noise_floor", "frequency_peaks", "full_analysis"):
            action = "full_analysis"

        raw_dur = parameters.get("duration_seconds") or parameters.get("duration_sec") or parameters.get("duration") or 1.0
        dur = float(raw_dur)
        dur = max(0.3, min(3.0, dur))

        threading.Thread(target=_worker, args=(action, dur, player), daemon=True).start()

        if action == "noise_floor":
            return "Measuring ambient room noise floor, sir. Acoustic level telemetry will display shortly."
        elif action == "frequency_peaks":
            return "Sampling room acoustics for dominant resonant frequencies and coil whine, sir."
        else:
            return "Analyzing ambient room acoustics and FFT frequency spectrum, sir. Results are heading to your HUD."
    except Exception as e:
        return f"Sir, acoustic analyzer encountered an issue: {e}"
