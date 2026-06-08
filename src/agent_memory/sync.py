"""
AgentMemory v0.3 - Sync Manager
Synchronizes memories between L4 and L3.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from .embedder import Embedder, get_embedder
from .utils.injection import check_injection


class SyncManager:
    """Sync Manager for L4 <-> L3 synchronization."""
    
    def __init__(self, l4_store, l3_store, embedder: Optional[Embedder] = None,
                 memory_dir: str = "memory"):
        self.l4 = l4_store
        self.l3 = l3_store
        self.embedder = embedder or get_embedder()
        # P1-1 fix: use embed_sync for DashScopeEmbedder (async embed),
        # fall back to regular embed for HashEmbedder (sync)
        if hasattr(self.embedder, 'embed_sync'):
            self._embed_fn = self.embedder.embed_sync
        else:
            self._embed_fn = self.embedder.embed
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # Architecture spec §6.1: 6 trigger categories with Chinese + English keywords.
        # Match is case-insensitive substring on lowercased content.
        self.auto_sync_keywords = [
            # 决策
            "决定", "决策", "确定", "敲定",
            # 完成
            "完成", "结束", "done", "finished", "搞定",
            # 重要
            "重要", "关键", "critical", "important", "要紧",
            # 记住
            "记住", "记下", "备忘", "remember", "memo",
            # 项目
            "项目", "project", "里程碑", "milestone", "sprint",
            # 进展
            "进展", "进度", "progress", "更新", "update", "迭代",
        ]
    
    async def sync_one(self, memory_id: str) -> bool:
        # P0-1 fix: l4.load_existing() returns dict with 'content' and 'meta',
        # NOT l4.load() which returns Optional[str]
        try:
            mem = await self.l4.load_existing(memory_id)
            if not mem:
                return False

            content = mem.get("content", "")
            meta = mem.get("meta", {})

            if not content:
                return False

            # P1-1 fix: use _embed_fn which handles sync/async embedder correctly
            vector = self._embed_fn(content)

            # meta is already a dict from load_existing (P0-1 fix)
            source = meta.get("source", "manual")
            tags = meta.get("tags", [])
            importance = meta.get("importance", 0.5)
            category_path = meta.get("category_path", "general")
            created_at = meta.get("created_at", "")

            if not created_at:
                created_at = datetime.now().isoformat()

            # P0-2: 注入检测，写入 L3 meta 前调用
            flagged, trust_score, matched_patterns = check_injection(content)

            # P0-5 fix: enforce minimum trust threshold — reject if trust_score < 0.2
            if trust_score < 0.2:
                return False
            elif flagged:
                pass  # Flagged memories are logged by caller

            metadata = {
                "source": source,
                "tags": tags,
                "flagged": flagged,
                "trust_score": trust_score,
                "flagged_patterns": matched_patterns,
            }

            # P1-9/P1-10 fix: check upsert return value before writing vec.json.
            # upsert() now returns bool (l3_lancedb.py P1-10 fix).
            ok = self.l3.upsert(
                id=memory_id, content=content, vector=vector,
                metadata=metadata, importance=importance,
                category_path=category_path, created_at=created_at,
            )
            if ok:
                self._write_vec_json(memory_id, vector)
                return True
            else:
                return False

        except Exception as e:
            return False
    
    async def sync_all(self) -> Dict[str, int]:
        # P0-2 fix: sync_one is now async
        memory_ids = self.l4.list()
        results = {"synced": 0, "failed": 0}
        for mid in memory_ids:
            if await self.sync_one(mid):
                results["synced"] += 1
            else:
                results["failed"] += 1
        return results
    
    async def sync_by_category(self, category_path: str) -> int:
        # P0-1 fix: use load_existing instead of load (which returns str not dict)
        memory_ids = self.l4.list()
        synced = 0
        for mid in memory_ids:
            mem = await self.l4.load_existing(mid)
            if mem:
                meta = mem.get("meta", {})
                cat = meta.get("category_path", "")
                if cat == category_path:
                    if await self.sync_one(mid):
                        synced += 1
        return synced
    
    async def auto_sync_check(self, memory_id: str) -> bool:
        # P0-1 fix: use load_existing instead of load (which returns str not dict)
        try:
            mem = await self.l4.load_existing(memory_id)
            if not mem:
                return False
            content = mem.get("content", "")
            if not content:
                return False
            # Architecture spec §6.1: substring match, case-insensitive
            content_lower = content.lower()
            for pattern in self.auto_sync_keywords:
                if pattern in content_lower:
                    return True
            return False
        except Exception as e:
            return False
    
    def delete_from_l3(self, memory_id: str) -> bool:
        """
        Delete memory from L3 and clean up its vec.json file.

        P0-6 fix: propagate actual l3.delete() return value instead of
        always returning True. Also delete vec_path FIRST to ensure cleanup
        even if l3.delete() fails.
        """
        try:
            vec_path = self.memory_dir / f"{memory_id}.vec.json"
            # Delete vec.json first (before l3.delete which might fail)
            if vec_path.exists():
                vec_path.unlink()
            # P0-6: capture and propagate actual return value
            result = self.l3.delete(memory_id)
            return result
        except Exception as e:
            return False
    
    def _write_vec_json(self, memory_id: str, vector: List[float]) -> None:
        vec_path = self.memory_dir / f"{memory_id}.vec.json"
        vec_data = {
            "id": memory_id, "dim": len(vector), "vector": vector,
            "model": "hash-v1", "created_at": datetime.now().isoformat(),
        }
        with open(vec_path, "w", encoding="utf-8") as f:
            json.dump(vec_data, f, ensure_ascii=False, indent=2)
    
    def _read_vec_json(self, memory_id: str) -> Optional[Dict[str, Any]]:
        vec_path = self.memory_dir / f"{memory_id}.vec.json"
        if not vec_path.exists():
            return None
        with open(vec_path, "r", encoding="utf-8") as f:
            return json.load(f)
