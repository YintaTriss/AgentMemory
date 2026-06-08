"""
AgentMemory v2.0.2 - Memory Manager (Unified API)

Main entry point for the memory system.
Provides unified async API for all memory operations.

Team Collaboration:
- namespace: 隔离的命名空间，每个 agent/团队独立存储
- TeamMemoryManager: 多 agent 团队共享记忆管理
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from .l4_files import L4FilesStore, MemoryMeta, MemoryVec
from .bm25 import BM25Indexer
from .l1_lcm import L1LCMCompressor
from .sync import SyncManager
from .library import LibraryClassifier
from .embedder import Embedder, get_embedder
from .observability import metrics


class MemoryManager:
    """Unified Memory Manager with async API.

    Args:
        namespace: 命名空间 ID，用于多 agent 隔离存储。
                   设置后，base_dir → base_dir/{namespace}/，db_path → db_path/{namespace}/
        base_dir: L4 file storage directory.
        db_path: L3 vector store directory.
                  For Qdrant:  "data/qdrant" (default)
        embedder: Embedder instance for vectorization.
                  Defaults to the same embedder as L3 Qdrant store.
        l3_backend: Which L3 vector store to use. Always "qdrant".
    """

    def __init__(self, base_dir: str = "memory", db_path: str = "data/qdrant",
                 embedder: Optional[Embedder] = None,
                 l3_backend: str = "qdrant",
                 namespace: Optional[str] = None):
        # Namespace isolation: append namespace to paths
        if namespace:
            ns_sanitized = namespace.replace("../", "").replace("..", "").strip("/")
            base_dir = str(Path(base_dir) / ns_sanitized)
            db_path = str(Path(db_path) / ns_sanitized)
        
        self.namespace = namespace
        self.base_dir = base_dir
        self.db_path = db_path
        self.l3_backend = l3_backend
        self.l4 = L4FilesStore(base_dir)

        # L3 store: always Qdrant Edge
        from .l3_qdrant import L3QdrantStore
        self.l3 = L3QdrantStore(db_path=db_path)

        self.l1 = L1LCMCompressor()
        self.sync = SyncManager(self.l4, self.l3, embedder, memory_dir=base_dir)
        self.classifier = LibraryClassifier()
        # Use the same embedder as L3 Qdrant store (FastEmbed with correct dimensions)
        # This ensures query vectors match stored vectors (e.g. 512-dim for bge-small-zh-v1.5)
        self.embedder = embedder or self.l3._embedder or get_embedder()
        self._stats_cache = None
        self._stats_timestamp = None

    async def add(self, content: str, importance: float = 0.5,
                  category_path: Optional[str] = None, tags: Optional[List[str]] = None,
                  source: str = "manual") -> str:
        import time
        t0 = time.perf_counter()

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
        await self.sync.sync_one(memory_id)

        self._invalidate_cache()
        metrics.inc_add()
        metrics.record_add_latency(time.perf_counter() - t0)
        return memory_id

    async def search(self, query: str, limit: int = 5,
                    category_path: Optional[str] = None) -> List[Dict[str, Any]]:
        import time
        t0 = time.perf_counter()
        mode = "vector"

        # Handle async embedder (DashScopeEmbedder)
        import asyncio
        if asyncio.iscoroutinefunction(self.embedder.embed):
            query_vector = await self.embedder.embed(query)
        else:
            query_vector = self.embedder.embed(query)

        filter_expr = None
        if category_path:
            # Escape single quotes to prevent injection
            safe_cat = category_path.replace("'", "''")
            filter_expr = f"category_path = '{safe_cat}'"

        results = self.l3.search(query_vector, top_k=limit, filter_expr=filter_expr)

        # L3 vector search failed — detect by zero scores and apply BM25 rerank
        needs_bm25 = (
            len(results) > 0
            and all(r.get("score", None) is None or r.get("score", 0) == 0 for r in results)
        )
        if needs_bm25:
            mode = "bm25"
            metrics.inc_bm25_fallback()
            results = self._bm25_rerank(query, results, top_k=limit)

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
                metrics.record_search_score(r.get("score", 0))

        metrics.inc_search(mode)
        metrics.record_search_latency(time.perf_counter() - t0, mode)
        return enriched

    async def list(self, category_path: Optional[str] = None,
                   limit: int = 20) -> List[Dict[str, Any]]:
        all_ids = self.l4.list()
        mem_map = {}
        for memory_id in all_ids[:limit]:
            mem = await self.l4.load_existing(memory_id)
            if mem:
                mem_map[memory_id] = mem

        if category_path:
            # Prefix match so '测试' matches '测试/石榴籽', '测试/其他' etc.
            filtered_ids = [
                mid for mid, mem in mem_map.items()
                if mem.get("meta", {}).get("category_path", "").startswith(category_path)
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
        l3_ok = self.sync.delete_from_l3(memory_id)
        # L4 delete is the source of truth; L3 failure is non-critical
        # (L3 vector becomes orphaned but cannot be retrieved since L4 content is gone)
        if deleted:
            self._invalidate_cache()
            metrics.inc_delete()
        return deleted

    async def compress_for_context(self, memory_ids: List[str],
                                       query: str = "") -> str:
        """
        L1 context compression for AI prompt injection.

        Args:
            memory_ids: List of memory IDs to compress.
            query: Optional query string. Memories matching the query
                   receive relevance score boost in importance tier sorting.
        """
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

        # Detect actual embedder in use: check if FastEmbed was actually loaded
        # _embedder is None when FastEmbed import failed or not installed
        if self.l3_backend == "qdrant":
            actual_embedder = getattr(self.l3, '_embedder', None)
            if actual_embedder is not None:
                # FastEmbed was loaded and is in use
                embedder_name = f"fastembed-{getattr(self.l3, 'embedder_model', 'unknown')}"
                dims = getattr(self.l3, '_vector_dim', None) or getattr(self.l3, 'DEFAULT_DIM', 384)
            else:
                # FastEmbed not loaded — using HashEmbedder fallback
                embedder_name = "hash-v1 (fallback)"
                dims = self.embedder.dim
        else:
            embedder_name = "hash-v1"
            dims = self.embedder.dim

        stats = {
            "total_memories": l4_stats["memory_count"],
            "l3_memories": l3_count,
            "storage_bytes": l4_stats["total_size_bytes"],
            "embedder": embedder_name,
            "embedding_dims": dims,
            "categories": self.l4.get_categories(),
            "l3_backend": self.l3_backend,
        }
        self._stats_cache = stats
        self._stats_timestamp = datetime.now()
        return stats

    def _generate_id(self, content: str) -> str:
        import time, secrets
        return f"mem_{int(time.time()*1000):013x}_{secrets.token_hex(4)}"

    def _invalidate_cache(self) -> None:
        self._stats_cache = None
        self._stats_timestamp = None

    def _bm25_rerank(self, query: str, records: List[Dict[str, Any]],
                     top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Pure-Python BM25 re-ranking when vector search returns zero scores.
        """
        if not records:
            return []
        texts = [r.get("content", "") or "" for r in records]
        indexer = BM25Indexer(k1=1.2, b=0.75)
        indexer.index(texts)
        bm25_results = indexer.search(query, top_k=top_k)
        results = []
        for bm in bm25_results:
            rec = records[bm["doc_index"]]
            results.append({
                "id": rec.get("id", ""),
                "content": rec.get("content", ""),
                "score": bm["bm25_score"],
                "bm25_score": bm["bm25_score"],
                "importance": rec.get("importance", 0.5),
                "category_path": rec.get("category_path", ""),
                "created_at": rec.get("created_at", ""),
            })
        return results

    async def sync_all_memories(self) -> Dict[str, int]:
        return await self.sync.sync_all()


def create_memory_manager(base_dir: str = "memory",
                          db_path: str = "data/qdrant",
                          l3_backend: str = "qdrant",
                          namespace: Optional[str] = None) -> MemoryManager:
    """Create a MemoryManager instance.

    Args:
        base_dir: L4 file storage directory.
        db_path: L3 vector store directory.
        l3_backend: Always "qdrant" (Qdrant Edge embedded, default).
        namespace: 命名空间，用于多 agent 隔离存储。
    """
    return MemoryManager(base_dir=base_dir, db_path=db_path, l3_backend=l3_backend, namespace=namespace)


class TeamMemoryManager:
    """
    团队协作记忆管理器。
    
    支持多 agent 共享同一个团队的记忆，同时保持各自独立的空间。
    
    存储结构:
        memory/
            {team}/              ← 团队共享记忆
                _shared/         ← 团队成员共享的记忆
                {agent1}/        ← agent1 私有记忆
                {agent2}/        ← agent2 私有记忆
            data/
                qdrant/
                    {team}/
                        _shared/
                        {agent1}/
                        {agent2}/

    Args:
        team: 团队 ID
        base_dir: 根存储目录
        db_path: 向量库根目录
        embedder: Embedder 实例
    """

    def __init__(self, team: str,
                 base_dir: str = "memory",
                 db_path: str = "data/qdrant",
                 embedder: Optional[Embedder] = None):
        self.team = team
        self.base_dir = base_dir
        self.db_path = db_path
        self._embedder = embedder
        
        # Shared memory manager for the team
        self.shared = MemoryManager(
            base_dir=str(Path(base_dir) / team / "_shared"),
            db_path=str(Path(db_path) / team / "_shared"),
            embedder=embedder,
            namespace=None,
        )
        # Track registered agents
        self._agents: Dict[str, MemoryManager] = {}

    def register_agent(self, agent_id: str) -> MemoryManager:
        """
        注册一个 agent，获得其私有的记忆空间。
        
        Args:
            agent_id: Agent 唯一标识
        Returns:
            该 agent 的 MemoryManager 实例
        """
        if agent_id not in self._agents:
            self._agents[agent_id] = MemoryManager(
                base_dir=str(Path(self.base_dir) / self.team / agent_id),
                db_path=str(Path(self.db_path) / self.team / agent_id),
                embedder=self._embedder,
                namespace=None,
            )
        return self._agents[agent_id]

    def get_agent(self, agent_id: str) -> Optional[MemoryManager]:
        """获取已注册的 agent MemoryManager，未注册返回 None"""
        return self._agents.get(agent_id)

    def list_agents(self) -> List[str]:
        """列出所有已注册的 agent ID"""
        return list(self._agents.keys())

    async def share_to_team(self, agent_id: str, memory_id: str) -> bool:
        """
        将某 agent 的记忆共享到团队空间。
        
        Args:
            agent_id: 来源 agent
            memory_id: 要共享的记忆 ID
        Returns:
            是否共享成功
        """
        agent_mem = self._agents.get(agent_id)
        if not agent_mem:
            return False
        mem = await agent_mem.get(memory_id)
        if not mem:
            return False
        # Write to team shared space
        shared_id = await self.shared.add(
            content=mem["content"],
            importance=mem.get("importance", 0.5),
            category_path=f"team:{self.team}/shared",
            tags=["shared", f"from:{agent_id}"],
            source=f"agent:{agent_id}",
        )
        return True

    async def get_shared(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取团队共享的所有记忆"""
        return await self.shared.list(limit=limit)

    async def stats_all(self) -> Dict[str, Any]:
        """获取团队所有 agent 的统计"""
        stats = {
            "team": self.team,
            "shared": await self.shared.stats(),
            "agents": {},
        }
        for agent_id, mgr in self._agents.items():
            stats["agents"][agent_id] = await mgr.stats()
        return stats


def create_team_memory_manager(team: str,
                               base_dir: str = "memory",
                               db_path: str = "data/qdrant",
                               embedder: Optional[Embedder] = None) -> TeamMemoryManager:
    """Create a TeamMemoryManager instance.

    Args:
        team: 团队 ID
        base_dir: 根存储目录
        db_path: 向量库根目录
        embedder: Embedder 实例
    """
    return TeamMemoryManager(team=team, base_dir=base_dir, db_path=db_path, embedder=embedder)
