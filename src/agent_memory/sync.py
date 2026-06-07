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
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        self.auto_sync_keywords = [
            "记住", "决定", "重要", "完成", "项目", "计划",
        ]
    
    def sync_one(self, memory_id: str) -> bool:
        try:
            mem = self.l4.load(memory_id)
            if not mem:
                print(f"[Sync] Memory {memory_id} not found in L4")
                return False
            
            content = mem.get("content", "")
            meta = mem.get("meta")
            
            if not content:
                print(f"[Sync] Memory {memory_id} has no content")
                return False
            
            vector = self.embedder.embed(content)
            
            # Handle meta as dict (from l4.load() returns dict with 'meta' key)
            if meta is None:
                meta = {}
            source = meta.get("source", "manual") if isinstance(meta, dict) else getattr(meta, "source", "manual")
            tags = meta.get("tags", []) if isinstance(meta, dict) else getattr(meta, "tags", [])
            importance = meta.get("importance", 0.5) if isinstance(meta, dict) else getattr(meta, "importance", 0.5)
            category_path = meta.get("category_path", "general") if isinstance(meta, dict) else getattr(meta, "category_path", getattr(meta, "category", "general"))
            created_at = meta.get("created_at", "") if isinstance(meta, dict) else getattr(meta, "created_at", "")
            
            if not created_at:
                created_at = datetime.now().isoformat()

            # P0-2: 注入检测，写入 L3 meta 前调用
            flagged, trust_score, matched_patterns = check_injection(content)

            metadata = {
                "source": source,
                "tags": tags,
                "flagged": flagged,
                "trust_score": trust_score,
                "flagged_patterns": matched_patterns,
            }
            
            self.l3.upsert(
                id=memory_id, content=content, vector=vector,
                metadata=metadata, importance=importance,
                category_path=category_path, created_at=created_at,
            )
            
            self._write_vec_json(memory_id, vector)
            return True
            
        except Exception as e:
            print(f"[Sync] Error syncing {memory_id}: {e}")
            return False
    
    def sync_all(self) -> Dict[str, int]:
        memory_ids = self.l4.list()
        results = {"synced": 0, "failed": 0}
        for mid in memory_ids:
            if self.sync_one(mid):
                results["synced"] += 1
            else:
                results["failed"] += 1
        return results
    
    def sync_by_category(self, category_path: str) -> int:
        memory_ids = self.l4.list()
        synced = 0
        for mid in memory_ids:
            mem = self.l4.load(mid)
            if mem:
                meta = mem.get("meta")
                if meta:
                    # Check both dict and object access
                    if isinstance(meta, dict):
                        cat = meta.get("category_path", "")
                    else:
                        cat = getattr(meta, "category_path", getattr(meta, "category", ""))
                    if cat == category_path:
                        if self.sync_one(mid):
                            synced += 1
        return synced
    
    def auto_sync_check(self, memory_id: str) -> bool:
        try:
            mem = self.l4.load(memory_id)
            if not mem:
                return False
            content = mem.get("content", "")
            if not content:
                return False
            trigger_patterns = [
                "记住", "决定", "重要", "完成", "项目", "进展",
            ]
            for pattern in trigger_patterns:
                if pattern in content:
                    return True
            return False
        except Exception as e:
            print(f"[Sync] Auto-sync check error for {memory_id}: {e}")
            return False
    
    def delete_from_l3(self, memory_id: str) -> bool:
        try:
            self.l3.delete(memory_id)
            vec_path = self.memory_dir / f"{memory_id}.vec.json"
            if vec_path.exists():
                vec_path.unlink()
            return True
        except Exception as e:
            print(f"[Sync] Error deleting {memory_id} from L3: {e}")
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
