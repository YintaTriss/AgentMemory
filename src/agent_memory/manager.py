"""
AgentMemory v0.3 - Memory Manager (Unified API)

Main entry point for the memory system.
Provides unified async API for all memory operations.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from .l4_files import L4FilesStore, MemoryMeta, MemoryVec
from .l3_lancedb import L3LanceDBStore
from .l1_lcm import L1LCMCompressor
from .sync import SyncManager
from .library import LibraryClassifier
from .embedder import Embedder, get_embedder


class MemoryManager:
    """Unified Memory Manager with async API."""
    
    def __init__(self, base_dir: str = "memory", db_path: str = "data/lancedb",
                 embedder: Optional[Embedder] = None):
        self.base_dir = base_dir
        self.db_path = db_path
        self.l4 = L4FilesStore(base_dir)
        self.l3 = L3LanceDBStore(db_path)
        self.l1 = L1LCMCompressor()
        self.sync = SyncManager(self.l4, self.l3, embedder, memory_dir=base_dir)
        self.classifier = LibraryClassifier()
        self.embedder = embedder or get_embedder()
        self._stats_cache = None
        self._stats_timestamp = None
    
    async def add(self, content: str, importance: float = 0.5,
                  category_path: Optional[str] = None, tags: Optional[List[str]] = None,
                  source: str = "manual") -> str:
        if category_path is None:
            category_path = self.classifier.classify(content)
        memory_id = self._generate_id(content)
        now = datetime.now().isoformat()
        
        # Create metadata as dict (L4FilesStore expects dict)
        meta_dict = {
            "id": memory_id,
            "created_at": now,
            "updated_at": now,
            "category_path": category_path,
            "tags": tags or [],
            "source": source,
            "importance": importance,
        }
        
        # Save to L4 (async)
        await self.l4.save(memory_id, content, meta_dict)
        
        # Sync to L3 (this also writes vec.json) — P0-2: must await since sync_one is now async
        await self.sync.sync_one(memory_id)
        
        self._invalidate_cache()
        return memory_id
    
    async def search(self, query: str, limit: int = 5,
                    category_path: Optional[str] = None) -> List[Dict[str, Any]]:
        # P2 latent fix: handle async embedder (DashScopeEmbedder). In practice
        # manager always gets HashEmbedder, but be safe.
        import asyncio
        if asyncio.iscoroutinefunction(self.embedder.embed):
            query_vector = await self.embedder.embed(query)
        else:
            query_vector = self.embedder.embed(query)
        filter_expr = None
        if category_path:
            # Escape single quotes to prevent LanceDB injection
            safe_cat = category_path.replace("'", "''")
            filter_expr = f"category_path = '{safe_cat}'"
        results = self.l3.search(query_vector, top_k=limit, filter_expr=filter_expr)
        enriched = []
        for r in results:
            memory_id = r.get("id", "")
            mem = await self.l4.load_existing(memory_id)
            if mem:
                meta = mem.get("meta", {})
                enriched.append({
                    "id": memory_id, 
                    "content": mem.get("content", ""),
                    "score": r.get("score", 0),
                    "category": meta.get("category_path", ""),
                    "tags": meta.get("tags", []),
                    "importance": meta.get("importance", r.get("importance", 0.5)),
                    "created_at": meta.get("created_at", r.get("created_at", "")),
                    "metadata": r.get("metadata", {}),
                })
        return enriched
    
    async def list(self, category_path: Optional[str] = None,
                   limit: int = 20) -> List[Dict[str, Any]]:
        # P2-4 fix (manager.py): load each memory once instead of twice.
        # Previous pattern: load all → filter in Python (N times for N items).
        # New pattern: load all in one pass, then filter.
        all_ids = self.l4.list()
        mem_map = {}
        for memory_id in all_ids[:limit]:
            mem = await self.l4.load_existing(memory_id)
            if mem:
                mem_map[memory_id] = mem

        if category_path:
            filtered_ids = [
                mid for mid, mem in mem_map.items()
                if mem.get("meta", {}).get("category_path") == category_path
            ]
        else:
            filtered_ids = list(mem_map.keys())

        memories = []
        for memory_id in filtered_ids:
            mem = mem_map[memory_id]
            meta = mem.get("meta", {})
            memories.append({
                "id": memory_id,
                "content": mem.get("content", ""),
                "category": meta.get("category_path", ""),
                "tags": meta.get("tags", []),
                "importance": meta.get("importance", 0.5),
                "created_at": meta.get("created_at", ""),
                "source": meta.get("source", ""),
            })
        return memories
    
    async def get(self, memory_id: str) -> Optional[Dict[str, Any]]:
        mem = await self.l4.load_existing(memory_id)
        if not mem:
            return None
        meta = mem.get("meta", {})
        return {
            "id": memory_id, 
            "content": mem.get("content", ""),
            "category": meta.get("category_path", ""),
            "tags": meta.get("tags", []),
            "importance": meta.get("importance", 0.5),
            "created_at": meta.get("created_at", ""),
            "updated_at": meta.get("updated_at", ""),
            "source": meta.get("source", ""),
        }
    
    async def delete(self, memory_id: str) -> bool:
        deleted = await self.l4.delete(memory_id)
        self.sync.delete_from_l3(memory_id)
        if deleted:
            self._invalidate_cache()
        return deleted
    
    async def compress_for_context(self, memory_ids: List[str],
                                       query: str = "") -> str:
        """
        Sugg-5 fix: expose query parameter so callers can use query-focused compression.

        Args:
            memory_ids: List of memory IDs to compress.
            query: Optional query string. Memories matching the query
                   receive relevance score boost in importance tier sorting.
        """
        # P0-3 fix: L1LCMCompressor.compress() expects List[Dict] with 'content'/'meta' keys,
        # not List[str] memory IDs.
        memories = []
        for mid in memory_ids:
            mem = await self.l4.load_existing(mid)
            if mem:
                memories.append(mem)
        return self.l1.compress(memories, query=query)
    
    async def stats(self) -> Dict[str, Any]:
        if self._stats_cache and self._stats_timestamp:
            age = (datetime.now() - self._stats_timestamp).total_seconds()
            if age < 300:
                return self._stats_cache
        l4_stats = self.l4.get_stats()
        l3_count = self.l3.count()
        stats = {
            "total_memories": l4_stats["memory_count"],
            "l3_memories": l3_count,
            "storage_bytes": l4_stats["total_size_bytes"],
            "embedder": "hash-v1",
            "embedding_dims": self.embedder.dim,
            "categories": self.l4.get_categories(),
        }
        self._stats_cache = stats
        self._stats_timestamp = datetime.now()
        return stats
    
    def _generate_id(self, content: str) -> str:
        # P0-3 fix: use timestamp+random so same content gets unique IDs
        import time, secrets
        return f"mem_{int(time.time()*1000):013x}_{secrets.token_hex(4)}"
    
    def _invalidate_cache(self) -> None:
        self._stats_cache = None
        self._stats_timestamp = None
    
    async def sync_all_memories(self) -> Dict[str, int]:
        # P0-2 fix: sync_all is now async
        return await self.sync.sync_all()


def create_memory_manager(base_dir: str = "memory",
                          db_path: str = "data/lancedb") -> MemoryManager:
    return MemoryManager(base_dir=base_dir, db_path=db_path)
