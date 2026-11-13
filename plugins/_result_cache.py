"""
Lightweight TTL result cache for JARVIS plugins.

Usage:
    from plugins._result_cache import cached_tool_call

    @cached_tool_call(ttl_seconds=60)
    def my_expensive_fetch(args):
        ...
"""
from __future__ import annotations

import functools
import hashlib
import json
import threading
import time
from typing import Any, Callable, Optional

_CACHE: dict[str, tuple[float, Any]] = {}
_LOCK = threading.Lock()

def _make_key(prefix: str, params: Any) -> str:
    try:
        raw = json.dumps(params, sort_keys=True, default=str)
    except Exception:
        raw = str(params)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"

def get_cached(key: str, ttl_seconds: float) -> Optional[Any]:
    now = time.monotonic()
    with _LOCK:
        if key in _CACHE:
            timestamp, val = _CACHE[key]
            if now - timestamp < ttl_seconds:
                return val
            del _CACHE[key]
    return None

def set_cached(key: str, val: Any) -> None:
    now = time.monotonic()
    with _LOCK:
        # Cap cache size at 128 entries
        if len(_CACHE) > 128:
            oldest_key = min(_CACHE.keys(), key=lambda k: _CACHE[k][0])
            _CACHE.pop(oldest_key, None)
        _CACHE[key] = (now, val)

def cached_tool_call(ttl_seconds: float = 60.0):
    def decorator(fn: Callable):
        @functools.wraps(fn)
        def wrapper(parameters: dict, *args, **kwargs):
            key = _make_key(fn.__name__, parameters)
            cached = get_cached(key, ttl_seconds)
            if cached is not None:
                return cached
            res = fn(parameters, *args, **kwargs)
            if res and not (isinstance(res, str) and (res.startswith("Sir,") or "failed" in res.lower())):
                set_cached(key, res)
            return res
        return wrapper
    return decorator
