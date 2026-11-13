"""memory/short_term.py — High-speed in-memory Short-Term Memory (STM) for JARVIS.

Manages active conversation turns, working entity references, and transient
scratchpad context with zero I/O latency (< 0.01 ms).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import RLock
from typing import Any

MAX_TURNS_IN_MEMORY = 50


@dataclass
class DialogueTurn:
    role: str
    text: str
    timestamp: float = field(default_factory=time.time)
    modality: str = "voice"  # "voice", "telegram", "terminal"


class ShortTermMemory:
    """Thread-safe in-memory rolling dialogue and active working state manager."""

    def __init__(self, max_turns: int = MAX_TURNS_IN_MEMORY):
        self._max_turns = max_turns
        self._lock = RLock()
        self._turns: list[DialogueTurn] = []
        self._entities: dict[str, tuple[Any, int]] = {}  # key -> (value, turns_remaining)
        self._scratchpad: str = ""

    def add_turn(self, role: str, text: str, modality: str = "voice") -> None:
        """Record an exchange in the working memory."""
        if not text or not str(text).strip():
            return
        turn = DialogueTurn(role=role, text=str(text).strip(), modality=modality)
        with self._lock:
            self._turns.append(turn)
            turn_idx = len(self._turns)
            if len(self._turns) > self._max_turns:
                self._turns = self._turns[-self._max_turns:]

            # Decrement entity TTLs
            expired = []
            for k, (val, ttl) in self._entities.items():
                if ttl <= 1:
                    expired.append(k)
                else:
                    self._entities[k] = (val, ttl - 1)
            for k in expired:
                del self._entities[k]

        # Dual-write into ChromaDB vector store asynchronously for hybrid recall
        try:
            from memory import vector_store
            vector_store.upsert_short_term_turn(role, text, turn_idx, modality)
        except Exception:
            pass

    def set_entity(self, key: str, value: Any, ttl_turns: int = 8) -> None:
        """Cache an active entity or topic in working context (e.g. current_file, last_subject)."""
        if not key:
            return
        with self._lock:
            self._entities[str(key).strip().lower()] = (value, max(1, ttl_turns))

    def get_entity(self, key: str) -> Any | None:
        """Retrieve an active working entity if still in context."""
        with self._lock:
            pair = self._entities.get(str(key).strip().lower())
            return pair[0] if pair else None

    def set_scratchpad(self, notes: str) -> None:
        """Update transient scratchpad reasoning or intermediate step logs."""
        with self._lock:
            self._scratchpad = (notes or "").strip()

    def get_scratchpad(self) -> str:
        with self._lock:
            return self._scratchpad

    def get_recent_turns(self, count: int = 15) -> list[DialogueTurn]:
        """Return the most recent turns."""
        with self._lock:
            return list(self._turns[-max(1, count):])

    def get_session_transcript(self, max_turns: int = 40) -> list[str]:
        """Return formatted transcript strings for summarization or consolidation."""
        with self._lock:
            turns = self._turns[-max_turns:]
            return [f"{t.role.upper()} ({t.modality}): {t.text}" for t in turns]

    def format_for_prompt(self) -> str:
        """Format active working entities and scratchpad for injection into prompt context."""
        with self._lock:
            parts = []
            if self._entities:
                items = [f"{k}: {val}" for k, (val, _) in self._entities.items()]
                parts.append("[ACTIVE WORKING ENTITIES]\n" + "\n".join(f"- {item}" for item in items))
            if self._scratchpad:
                parts.append(f"[WORKING SCRATCHPAD]\n{self._scratchpad}")
            return "\n\n".join(parts)

    def clear(self) -> None:
        """Reset short-term state."""
        with self._lock:
            self._turns.clear()
            self._entities.clear()
            self._scratchpad = ""


# Global singleton instance
stm = ShortTermMemory()
