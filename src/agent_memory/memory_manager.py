"""
AgentMemory v0.3 - Memory Manager

Main entry point for the memory system.
Provides unified API for all memory operations.
"""

import uuid
import hashlib
from datetime import datetime
from typing import List, Optional, Dict, Any

from .config import Config, get_config
from .l4_files import L4FilesStore, MemoryMeta, MemoryVec
from .l3_lancedb import L3LanceDBStore
from .l1_lcm import L1LCMCompressor


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
    """
    
    def __init__(self, memory_dir: str = "memory", data_dir: str = "data", embedder: str = "hash"):
        self.config = get_config(memory_dir=memory_dir, embedder=embedder)
        self.l4 = L4FilesStore(memory_dir)
        self.l3 = L3LanceDBStore(data_dir + "/lancedb", embedder=embedder)
        self.l1 = L1LCMCompressor()
        self._auto_sync_enabled = True
    
    def add(self, content: str, category: str = "general", tags: List[str] = None,
            importance: float = 0.5, source: str = "manual") -> str:
        memory_id = self._generate_id(content)
        now = datetime.now().isoformat()
        
        meta = MemoryMeta(
            id=memory_id, created_at=now, updated_at=now,
            category=category, tags=tags or [], source=source, importance=importance,
        )
        
        vec = MemoryVec(
            id=memory_id, vector=self._compute_vector(content),
            embedder=self.config.embedder, dims=self.config.embedding_dims,
        )
        
        self.l4.save(memory_id, content, meta, vec)
        self.l3.upsert(memory_id, content, vec.vector)
        
        return memory_id
    
    def search(self, query: str, top_k: int = 5, category: str = None) -> List[Dict[str, Any]]:
        results = self.l3.search(query, top_k)
        
        if category:
            filtered = []
            for r in results:
                mem = self.l4.load(r["id"])
                if mem and mem["meta"].category.startswith(category):
                    filtered.append(r)
            results = filtered
        
        enriched = []
        for r in results:
            mem = self.l4.load(r["id"])
            if mem:
                enriched.append({
                    "id": r["id"], "content": mem["content"],
                    "score": r.get("score", 0), "category": mem["meta"].category,
                    "tags": mem["meta"].tags, "importance": mem["meta"].importance,
                    "created_at": mem["meta"].created_at,
                })
        return enriched
    
    def list_all(self) -> List[Dict[str, Any]]:
        memory_ids = self.l4.list()
        memories = []
        for memory_id in memory_ids:
            mem = self.l4.load(memory_id)
            if mem:
                memories.append({
                    "id": memory_id, "content": mem["content"],
                    "category": mem["meta"].category, "tags": mem["meta"].tags,
                    "importance": mem["meta"].importance, "created_at": mem["meta"].created_at,
                })
        return memories
    
    def get(self, memory_id: str) -> Optional[Dict[str, Any]]:
        mem = self.l4.load(memory_id)
        if not mem:
            return None
        return {
            "id": memory_id, "content": mem["content"],
            "category": mem["meta"].category, "tags": mem["meta"].tags,
            "importance": mem["meta"].importance, "created_at": mem["meta"].created_at,
            "updated_at": mem["meta"].updated_at,
        }
    
    def delete(self, memory_id: str) -> bool:
        deleted_l4 = self.l4.delete(memory_id)
        self.l3.delete(memory_id)
        return deleted_l4
    
    def get_categories(self) -> List[str]:
        return self.l4.get_categories()
    
    def stats(self) -> Dict[str, Any]:
        l4_stats = self.l4.get_stats()
        l3_stats = self.l3.get_stats()
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
        return content_hash[:16]
    
    def _compute_vector(self, content: str) -> List[float]:
        content_hash = hashlib.sha256(content.encode()).digest()
        vector = []
        for i in range(min(self.config.embedding_dims, len(content_hash) * 8)):
            byte_idx = i // 8
            bit_idx = i % 8
            if byte_idx < len(content_hash):
                vector.append((content_hash[byte_idx] >> bit_idx) & 1)
            else:
                vector.append(0)
        return [v * 2 - 1 for v in vector]
