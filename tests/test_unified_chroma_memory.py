"""
Tests for unified ChromaDB vector memory integrating long-term facts and short-term dialogue.
"""
import os
import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestUnifiedChromaMemory(unittest.TestCase):
    """Verifies seamless dual-memory convergence: Long-term JSON + ChromaDB Vector + STM."""

    def test_short_term_auto_vector_indexing(self):
        from memory.short_term import stm
        from memory.vector_store import semantic_search

        test_secret = "Unified Quantum Resonance 9912"
        stm.add_turn("user", f"My experimental architecture is called {test_secret}.")

        # Check semantic search retrieves from ChromaDB short_term_dialogue
        results = semantic_search(test_secret, n_results=5)
        self.assertTrue(len(results) > 0)
        found = any(test_secret in r.get("value", "") for r in results)
        self.assertTrue(found, f"Expected {test_secret} in vector store search results")

    def test_hybrid_search_unifies_stm_and_ltm(self):
        from memory.short_term import stm
        from memory.memory_manager import search_memory, update_memory

        # 1. Active working entity in STM
        stm.set_entity("active_framework", "FastAPI-Asyncio-Core")

        # 2. Long term fact
        update_memory({"projects": {"quantum_proj": "Hyperloop sub-system automation"}})

        # 3. Hybrid search resolves active working entity with top priority
        entity_out = search_memory("active_framework")
        self.assertIn("FastAPI-Asyncio-Core", entity_out)
        self.assertIn("active_context", entity_out)

        # 4. Hybrid search resolves long-term fact
        ltm_out = search_memory("Hyperloop")
        self.assertIn("Hyperloop", ltm_out)

    def test_vector_store_compatibility_aliases(self):
        from memory import vector_store

        # Verify index_memory alias
        ok = vector_store.index_memory("notes", "compat_test", "Testing compatibility alias")
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
