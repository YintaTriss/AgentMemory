"""
AgentMemory v0.3 - Memory Manager (Fire-and-Forget)

Main entry point for the memory system.
Provides unified API for all memory operations with fire-and-forget writes.
"""

import uuid
import hashlib
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import List, Optional, Dict, Any

from .config import Config, get_config
from .l4_files import L4FilesStore, MemoryMeta, MemoryVec
from .l3_lancedb import L3LanceDBStore
from .l1_lcm import L1LCMCompressor

# Fire-and-forget thread pool
_executor: Optional[ThreadPoolExecutor] = None

def _get_executor() -> ThreadPoolExecutor:
    """Get or create the global thread pool executor."""
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="memory_write_")
    return _executor


class MemoryManager:
    """
    AgentMemory v0.3 - Main Memory Manager
    
    Unified API for:
    - L4 File System (persistent storage)
    - L3 Vector Store (semantic search)
    - L1 LCM Compressor (context summarization)
    
    Design: Dual-track + Library
    - Track 1: Library Classification (exact retrieval)
    - Track 2: Embedding Vector (semantic search)
    
    Features:
    - Fire-and-forget writes (non-blocking add)
    - Automatic sync to L3
    """
    
    def __init__(self, memory_dir: str = "memory", data_dir: str = "data", embedder: str = "hash"):
        self.config = get_config(memory_dir=memory_dir, embedder=embedder)
        self.memory_dir = memory_dir
        self.data_dir = data_dir
        self.l4 = L4FilesStore(memory_dir)
        self.l3 = L3LanceDBStore(data_dir + "/lancedb", embedder=embedder)
        self.l1 = L1LCMCompressor()
        self._auto_sync_enabled = True
    
    def add(self, content: str, category: str = "general", tags: List[str] = None,
            importance: float = 0.5, source: str = "manual", 
            fire_and_forget: bool = True) -> str:
        """
        Add memory (non-blocking with fire-and-forget).
        
        Args:
            content: Memory content
            category: Category path
            tags: Tags list
            importance: Importance score (0-1)
            source: Source identifier
            fire_and_forget: If True, return immediately after queuing the write
        
        Returns:
            Memory ID (generated immediately, actual write happens in background)
        """
        memory_id = self._generate_id(content)
        now = datetime.now().isoformat()
        
        meta = MemoryMeta(
            id=memory_id, 
            created_at=now, 
            updated_at=now,
            category_path=category, 
            tags=tags or [], 
            source=source, 
            importance=importance,
        )
        
        vec = MemoryVec(
            id=memory_id, 
            vector=self._compute_vector(content),
            embedder=self.config.embedder, 
            dims=self.config.embedding_dims,
        )
        
        if fire_and_forget:
            # Fire-and-forget: submit to thread pool and return immediately
            executor = _get_executor()
            executor.submit(self._add_sync, memory_id, content, meta, vec)
            return memory_id
        else:
            # Blocking write
            return self._add_sync(memory_id, content, meta, vec)
    
    def _add_sync(self, memory_id: str, content: str, meta: MemoryMeta, vec: MemoryVec) -> str:
        """
        Synchronous add implementation (called in thread pool for fire-and-forget).
        """
        try:
            # Write to L4
            self.l4.save(memory_id, content, meta, vec)
            
            # Sync to L3
            if self._auto_sync_enabled:
                try:
                    self.l3.upsert(memory_id, content, vec.vector)
                except Exception as e:
                    # L3 sync failure is non-fatal
                    pass
        except Exception as e:
            # Log error but don't raise (fire-and-forget)
            pass
        
        return memory_id
    
    def search(self, query: str, top_k: int = 5, category: str = None) -> List[Dict[str, Any]]:
        results = self.l3.search(query, top_k)
        
        if category:
            filtered = []
            for r in results:
                mem = self.l4.load(r["id"])
                if mem and mem.get("meta") and mem["meta"].category_path.startswith(category):
                    filtered.append(r)
            results = filtered
        
        enriched = []
        for r in results:
            mem = self.l4.load(r["id"])
            if mem:
                enriched.append({
                    "id": r["id"], 
                    "content": mem["content"],
                    "score": r.get("score", 0), 
                    "category": mem.get("meta", {}).category_path if mem.get("meta") else "general",
                    "tags": mem.get("meta", {}).tags if mem.get("meta") else [],
                    "importance": mem.get("meta", {}).importance if mem.get("meta") else 0.5,
                    "created_at": mem.get("meta", {}).created_at if mem.get("meta") else "",
                })
        return enriched
    
    def list_all(self) -> List[Dict[str, Any]]:
        memory_ids = self.l4.list()
        memories = []
        for memory_id in memory_ids:
            mem = self.l4.load(memory_id)
            if mem:
                memories.append({
                    "id": memory_id, 
                    "content": mem["content"],
                    "category": mem.get("meta", {}).category_path if mem.get("meta") else "general", 
                    "tags": mem.get("meta", {}).tags if mem.get("meta") else [],
                    "importance": mem.get("meta", {}).importance if mem.get("meta") else 0.5, 
                    "created_at": mem.get("meta", {}).created_at if mem.get("meta") else "",
                })
        return memories
    
    def get(self, memory_id: str) -> Optional[Dict[str, Any]]:
        mem = self.l4.load(memory_id)
        if not mem:
            return None
        return {
            "id": memory_id, 
            "content": mem["content"],
            "category": mem.get("meta", {}).category_path if mem.get("meta") else "general", 
            "tags": mem.get("meta", {}).tags if mem.get("meta") else [],
            "importance": mem.get("meta", {}).importance if mem.get("meta") else 0.5, 
            "created_at": mem.get("meta", {}).created_at if mem.get("meta") else "",
            "updated_at": mem.get("meta", {}).updated_at if mem.get("meta") else "",
        }
    
    def delete(self, memory_id: str) -> bool:
        deleted_l4 = self.l4.delete(memory_id)
        try:
            self.l3.delete(memory_id)
        except Exception:
            pass
        return deleted_l4
    
    def get_categories(self) -> List[str]:
        return self.l4.get_categories()
    
    def stats(self) -> Dict[str, Any]:
        l4_stats = self.l4.get_stats()
        try:
            l3_stats = self.l3.get_stats()
        except Exception:
            l3_stats = {"vector_count": 0}
        return {
            "total_memories": l4_stats["memory_count"],
            "layers": {"L4_Files": l4_stats, "L3_Vector": l3_stats},
            "embedder": self.config.embedder,
        }
    
    def compress_context(self, query: str = "", top_k: int = 10) -> str:
        memories = self.search(query, top_k)
        return self.l1.compress(memories, query)
    
    def _generate_id(self, content: str) -> str:
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        return f"mem_{content_hash[:8]}"
    
    def _compute_vector(self, content: str) -> List[float]:
        content_hash = hashlib.sha256(content.encode()).digest()
        vector = []
        for i in range(min(self.config.embedding_dims, len(content_hash) * 8)):
            byte_idx = i // 8
            bit_idx = i % 8
            if byte_idx < len(content_hash):
                vector.append((content_hash[byte_idx
