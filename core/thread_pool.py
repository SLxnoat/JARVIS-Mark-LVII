"""
core/thread_pool.py — JARVIS Centralized Worker Thread Registry
================================================================
Implements the Hermes cooperative-cancellation pattern for all background
plugin daemon threads.  Plugins call ``managed_thread(...)`` instead of
constructing a bare ``threading.Thread`` so that:

  * Every active worker is tracked in a global registry.
  * A ``threading.Event`` cancel token is handed to the worker so it can
    exit cleanly when interrupted.
  * ``cancel_all()`` and ``cancel_by_tag()`` let the assistant interrupt
    any in-flight task on voice interruption or session reset.
  * The registry is self-cleaning: finished threads are pruned on each new
    registration so the dict never grows unbounded.

Usage in a plugin
-----------------
    from core.thread_pool import managed_thread

    def run(parameters: dict, player=None, session_memory=None) -> str:
        def _worker(cancel: threading.Event):
            for chunk in heavy_generator():
                if cancel.is_set():
                    return          # cooperative exit
                process(chunk)

        managed_thread(_worker, tag="audio_spectrum_analyzer", player=player)
        return "Analysis started, Sir."

The cancel token is ALWAYS the first positional argument of the target.
"""
from __future__ import annotations

import threading
from typing import Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
_lock: threading.Lock = threading.Lock()
_registry: Dict[int, Tuple[threading.Thread, threading.Event, str]] = {}
# {thread.ident -> (thread, cancel_event, tag)}


def _prune() -> None:
    """Remove finished threads from the registry (called under _lock)."""
    dead = [tid for tid, (t, _e, _tag) in _registry.items() if not t.is_alive()]
    for tid in dead:
        del _registry[tid]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def managed_thread(
    target: Callable[[threading.Event], None],
    *,
    tag: str = "worker",
    player=None,
    args: tuple = (),
    kwargs: Optional[dict] = None,
) -> threading.Thread:
    """
    Spawn a managed background thread and register it.

    Parameters
    ----------
    target:
        Callable whose **first** positional argument is a ``threading.Event``
        cancel token.  When the event is set the worker should return promptly.
    tag:
        Human-readable label (plugin name) used for ``cancel_by_tag``.
    player:
        JarvisUI player instance for logging (may be None in tests).
    args:
        Additional positional arguments forwarded to *target* after the cancel
        token.
    kwargs:
        Additional keyword arguments forwarded to *target*.
    """
    cancel = threading.Event()

    def _wrapper():
        try:
            target(cancel, *args, **(kwargs or {}))
        except Exception as exc:
            if player is not None:
                try:
                    player.write_log(f"Worker [{tag}] error: {exc}")
                except Exception:
                    pass
        finally:
            with _lock:
                if threading.current_thread().ident in _registry:
                    del _registry[threading.current_thread().ident]

    t = threading.Thread(target=_wrapper, daemon=True, name=f"jarvis-{tag}")
    with _lock:
        _prune()
        t.start()
        _registry[t.ident] = (t, cancel, tag)
    return t


def cancel_all() -> int:
    """Signal every registered worker to stop.  Returns the count cancelled."""
    with _lock:
        _prune()
        count = 0
        for _tid, (t, cancel, _tag) in _registry.items():
            if t.is_alive():
                cancel.set()
                count += 1
    return count


def cancel_by_tag(tag: str) -> int:
    """Signal all workers whose tag matches *tag*.  Returns count cancelled."""
    with _lock:
        _prune()
        count = 0
        for _tid, (t, cancel, t_tag) in _registry.items():
            if t_tag == tag and t.is_alive():
                cancel.set()
                count += 1
    return count


def active_workers() -> List[dict]:
    """Return a snapshot of currently running workers for the status pills UI."""
    with _lock:
        _prune()
        return [
            {"tag": tag, "alive": t.is_alive(), "ident": tid}
            for tid, (t, _cancel, tag) in _registry.items()
            if t.is_alive()
        ]


def active_tags() -> List[str]:
    """Return a deduplicated list of currently active worker tags."""
    workers = active_workers()
    seen: List[str] = []
    for w in workers:
        if w["tag"] not in seen:
            seen.append(w["tag"])
    return seen
