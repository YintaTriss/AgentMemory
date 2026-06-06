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
        
        # Sync to L3 (this also writes vec.json)
        self.sync.sync_one(memory_id)
        
        self._invalidate_cache()
        return memory_id
    
    async def search(self, query: str, limit: int = 5,
                    category_path: Optional[str] = None) -> List[Dict[str, Any]]:
        query_vector = self.embedder.embed(query)
        filter_expr = None
        if category_path:
            # LanceDB filter expression for exact match
            filter_expr = f"category_path = '{category_path}'"
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
        memory_ids = self.l4.list()
        memories = []
        for memory_id in memory_ids[:limit]:
            mem = await self.l4.load_existing(memory_id)
            if mem:
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
        if category_path:
            memories = [x for x in memories if x.get("category") == category_path]
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
    
    async def compress_for_context(self, memory_ids: List[str]) -> str:
        return self.l1.compress(memory_ids, self.l4, self.l3)
    
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
        import hashlib
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _invalidate_cache(self) -> None:
        self._stats_cache = None
        self._stats_timestamp = None
    
    def sync_all_memories(self) -> Dict[str, int]:
        return self.sync.sync_all()


def create_memory_manager(base_dir: str = "memory",
                          db_path: str = "data/lancedb") -> MemoryManager:
    return MemoryManager(base_dir=base_dir, db_path=db_path)
