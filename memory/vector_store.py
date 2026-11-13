"""memory/vector_store.py — Persistent ChromaDB vector memory for JARVIS Mark-LVII.

Provides local semantic embedding search, automatic collection management,
and vector indexing for user identity, preferences, episodic sessions, and
knowledge notes. Runs 100% locally with zero cloud dependencies.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any

logger = logging.getLogger("JARVIS.VectorStore")

_CHROMA_DIR = Path(__file__).resolve().parent / "chroma"
_lock = RLock()
_client: Any = None
_collections: dict[str, Any] = {}
_initialized = False

# Collections mapping
COLLECTIONS = {
    "user_profile": "User identity, biographical facts, and relationships",
    "knowledge_notes": "Preferences, active projects, technical notes, and goals",
    "episodic_sessions": "Past conversation summaries, dates, and historical context",
    "task_knowledge": "Autonomous research reports, findings, and technical plans",
}

CATEGORY_TO_COLLECTION = {
    "identity": "user_profile",
    "relationships": "user_profile",
    "wishes": "user_profile",
    "preferences": "knowledge_notes",
    "projects": "knowledge_notes",
    "notes": "knowledge_notes",
    "sessions": "episodic_sessions",
    "tasks": "task_knowledge",
    "reports": "task_knowledge",
}


def _get_client():
    global _client, _initialized
    if _client is not None:
        return _client
    with _lock:
        if _client is not None:
            return _client
        try:
            import chromadb
            from chromadb.config import Settings

            _CHROMA_DIR.mkdir(parents=True, exist_ok=True)
            _client = chromadb.PersistentClient(
                path=str(_CHROMA_DIR),
                settings=Settings(anonymized_telemetry=False),
            )
            for cname in COLLECTIONS:
                _collections[cname] = _client.get_or_create_collection(
                    name=cname,
                    metadata={"hnsw:space": "cosine"},
                )
            _initialized = True
            print(f"[VectorStore]  ChromaDB initialized at {_CHROMA_DIR}")
            return _client
        except Exception as e:
            print(f"[VectorStore]  ChromaDB initialization failed: {e}")
            _client = None
            _initialized = False
            return None


def get_collection(name: str):
    _get_client()
    return _collections.get(name)


def _format_document(category: str, key: str, value: str) -> str:
    pretty_key = key.replace("_", " ").strip()
    return f"[{category.title()}] {pretty_key.title()}: {value}"


def upsert_fact(category: str, key: str, value: str, updated: str | None = None) -> bool:
    """Store or update a factual statement in the appropriate vector collection."""
    client = _get_client()
    if not client:
        return False
    if not key or not value:
        return False

    cname = CATEGORY_TO_COLLECTION.get(category, "knowledge_notes")
    coll = _collections.get(cname)
    if not coll:
        return False

    doc_id = f"{category}:{key}"
    doc_text = _format_document(category, key, value)
    timestamp = updated or datetime.now().strftime("%Y-%m-%d")

    metadata = {
        "category": str(category),
        "key": str(key),
        "value": str(value)[:380],
        "updated": timestamp,
    }

    with _lock:
        try:
            coll.upsert(
                ids=[doc_id],
                documents=[doc_text],
                metadatas=[metadata],
            )
            return True
        except Exception as e:
            print(f"[VectorStore]  Upsert error ({doc_id}): {e}")
            return False


def delete_fact(category: str, key: str) -> bool:
    """Remove a fact from its vector collection."""
    client = _get_client()
    if not client:
        return False

    cname = CATEGORY_TO_COLLECTION.get(category, "knowledge_notes")
    coll = _collections.get(cname)
    if not coll:
        return False

    doc_id = f"{category}:{key}"
    with _lock:
        try:
            coll.delete(ids=[doc_id])
            return True
        except Exception as e:
            print(f"[VectorStore]  Delete error ({doc_id}): {e}")
            return False


def semantic_search(query: str, n_results: int = 5, target_category: str | None = None) -> list[dict]:
    """Execute a semantic similarity query across vector collections.

    Returns a list of dicts:
    [{'id': str, 'category': str, 'key': str, 'value': str, 'distance': float, 'doc': str}]
    """
    client = _get_client()
    if not client or not query or not query.strip():
        return []

    target_collections = []
    if target_category and target_category in CATEGORY_TO_COLLECTION:
        cname = CATEGORY_TO_COLLECTION[target_category]
        if cname in _collections:
            target_collections.append(_collections[cname])
    else:
        target_collections = list(_collections.values())

    results: list[dict] = []
    with _lock:
        for coll in target_collections:
            try:
                count = coll.count()
                if count == 0:
                    continue
                k = min(n_results, count)
                res = coll.query(query_texts=[query], n_results=k)
                if not res or not res.get("ids") or not res["ids"][0]:
                    continue

                for i, doc_id in enumerate(res["ids"][0]):
                    meta = res["metadatas"][0][i] if res.get("metadatas") else {}
                    dist = res["distances"][0][i] if res.get("distances") else 1.0
                    doc = res["documents"][0][i] if res.get("documents") else ""

                    results.append({
                        "id": doc_id,
                        "category": meta.get("category", ""),
                        "key": meta.get("key", doc_id),
                        "value": meta.get("value", doc),
                        "distance": float(dist),
                        "document": doc,
                        "updated": meta.get("updated", ""),
                    })
            except Exception as e:
                print(f"[VectorStore]  Query error in {coll.name}: {e}")

    results.sort(key=lambda x: x["distance"])
    return results[:n_results]


def upsert_session(date_str: str, summary: str, language: str = "") -> bool:
    """Store an episodic session summary into the episodic_sessions collection."""
    client = _get_client()
    if not client or not summary:
        return False
    coll = _collections.get("episodic_sessions")
    if not coll:
        return False

    doc_id = f"session:{date_str}_{datetime.now().strftime('%H%M%S')}"
    metadata = {
        "category": "sessions",
        "date": date_str,
        "language": language or "English",
        "value": summary[:380],
    }

    with _lock:
        try:
            coll.upsert(
                ids=[doc_id],
                documents=[f"Session on {date_str} ({language}): {summary}"],
                metadatas=[metadata],
            )
            return True
        except Exception as e:
            print(f"[VectorStore]  Session upsert error: {e}")
            return False


def migrate_from_json(json_path: Path | None = None) -> int:
    """Seed ChromaDB collections from an existing long_term.json store."""
    if json_path is None:
        json_path = Path(__file__).resolve().parent / "long_term.json"
    if not json_path.exists():
        return 0

    client = _get_client()
    if not client:
        return 0

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return 0
    except Exception as e:
        print(f"[VectorStore]  Migration read error: {e}")
        return 0

    migrated = 0
    for cat, items in data.items():
        if cat == "sessions" and isinstance(items, list):
            for s in items:
                if isinstance(s, dict) and s.get("summary"):
                    upsert_session(s.get("date", "unknown"), s["summary"], s.get("language", ""))
                    migrated += 1
            continue

        if not isinstance(items, dict):
            continue

        for key, entry in items.items():
            val = entry.get("value", "") if isinstance(entry, dict) else str(entry)
            upd = entry.get("updated", "") if isinstance(entry, dict) else None
            if val:
                upsert_fact(cat, key, str(val), upd)
                migrated += 1

    if migrated:
        print(f"[VectorStore]  Migrated {migrated} items from {json_path.name} into ChromaDB")
    return migrated


def get_stats() -> dict[str, int]:
    """Return vector counts per collection."""
    _get_client()
    stats = {}
    with _lock:
        for name, coll in _collections.items():
            try:
                stats[name] = coll.count()
            except Exception:
                stats[name] = 0
    return stats
