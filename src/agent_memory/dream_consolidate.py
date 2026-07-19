"""
dream_consolidate.py — 梦境 Phase 3+4: 梦境产物生成 + 记忆固化

Phase 3: 梦境产物
- 隐式标签生成（来自残差信号的弱概念命名）
- 关联记忆创生（跨 namespace 连接）
- 语义锚点精炼（弱信号增强）

Phase 4: 记忆固化
- 高置信度产物写入 SQLite
- 低置信度写入"梦境草稿区"
- 老化压缩清理
"""
from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import numpy as np


class DreamConsolidator:
    """梦境产物生成器 + 记忆固化器"""

    def __init__(self, sqlite_store=None, embedder=None):
        self.store = sqlite_store
        self.embedder = embedder

    # ========== Phase 3: 梦境产物生成 ==========

    def generate_implicit_tags(self, residual_signal: Dict,
                               existing_tags: List[Dict],
                               candidate_names: Optional[List[str]] = None) -> List[Dict]:
        """
        从残差信号中提取隐式标签。
        
        Args:
            residual_signal: 残差金字塔分析结果中的 features
            existing_tags: 现有标签列表 [{"id": ..., "name": ..., "vector": ...}]
            candidate_names: 候选名称列表（可配领域词典）

        Returns:
            implicit_tags: [{"name": ..., "confidence": ..., "from_residual": bool}, ...]
        """
        features = residual_signal.get("features", {})
        novelty = features.get("novelty", 0.0)
        coverage = features.get("coverage", 0.0)

        implicit_tags = []

        # Novelty > 0.3：残差中有未解释的信号 → 可能的新概念
        if novelty > 0.3:
            # 尝试从候选名称匹配
            if candidate_names and existing_tags:
                import random
                # 找与残差最相关的候选名称
                used_names = {t.get("name", "") for t in existing_tags}
                available = [n for n in candidate_names if n not in used_names]
                if available:
                    name = random.choice(available)
                    confidence = min(0.8, novelty)
                    implicit_tags.append({
                        "name": name,
                        "confidence": confidence,
                        "from_residual": True,
                        "novelty": novelty,
                    })

        # Coverage < 0.5：大量信号未被覆盖 → 模糊概念
        if coverage < 0.5 and coverage > 0.1:
            implicit_tags.append({
                "name": f"uncategorized_signal_{int(novelty * 100)}",
                "confidence": (1.0 - coverage) * 0.3,
                "from_residual": True,
                "novelty": novelty,
            })

        return implicit_tags

    def create_association(self, tag_id_a: int, tag_id_b: int,
                           strength: float, source: str = "dream") -> Optional[str]:
        """
        在两个标签之间创建关联记忆。
        返回关联记忆的 ID，如果已存在则返回 None。
        """
        if not self.store:
            return None

        # 检查是否已有直接关联
        existing = self.store.get_cooccurrence_by_tag_ids(tag_id_a, tag_id_b)
        if existing and existing > 1.0:
            return None

        # 生成关联内容
        tag_name_a = self._get_tag_name(tag_id_a)
        tag_name_b = self._get_tag_name(tag_id_b)
        if not tag_name_a or not tag_name_b:
            return None

        # 草稿内容
        content = f"## Dream Association\n{tag_name_a} ↔ {tag_name_b}\nStrength: {strength:.2f}\nTag: 梦境关联, {tag_name_a}, {tag_name_b}\n"

        mem_id = f"dream_{tag_id_a}_{tag_id_b}"
        self.store.upsert_memory(
            memory_id=mem_id,
            content=content,
            namespace="dream",
            category="association",
            importance=min(1.0, strength * 0.5),
            meta={"source": source, "tag_a": tag_id_a, "tag_b": tag_id_b, "strength": strength},
        )
        self.store.add_tags_to_memory(mem_id, ["梦境关联", tag_name_a, tag_name_b])
        return mem_id

    def refine_anchor(self, tag_id: int, vector: np.ndarray,
                      confidence: float) -> bool:
        """
        精炼语义锚点：将标签向量向梦境分析方向微调。
        confidence < 0.3 时不调整（噪声保护）。
        """
        if confidence < 0.3 or not self.store:
            return False
        # 使用 kv_store 存储精炼向量
        self.store.kv_set(f"refined_vector_{tag_id}", {
            "vector": vector.tolist() if isinstance(vector, np.ndarray) else vector,
            "confidence": confidence,
            "refined_at": datetime.now(timezone.utc).isoformat(),
        })
        return True

    # ========== Phase 4: 记忆固化 ==========

    def consolidate(self, artifacts: List[Dict], dry_run: bool = False) -> Dict:
        """
        固化梦境产物到长程记忆。

        Args:
            artifacts: 梦境产物列表
            dry_run: 仅模拟

        Returns:
            {"written": N, "drafted": M, "rejected": K}
        """
        written = 0
        drafted = 0
        rejected = 0

        for art in artifacts:
            confidence = art.get("confidence", 0.0)

            if confidence >= 0.6:
                # 高置信度 → 直接写入
                if not dry_run:
                    self._write_artifact(art)
                written += 1
            elif confidence >= 0.2:
                # 中等置信度 → 写入梦境草稿区
                if not dry_run and self.store:
                    self.store.kv_set(f"draft_{art.get('id', int(time.time()))}", {
                        "artifact": art,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    })
                drafted += 1
            else:
                # 低置信度 → 丢弃
                rejected += 1

        return {"written": written, "drafted": drafted, "rejected": rejected}

    def _write_artifact(self, art: Dict):
        if not self.store:
            return
        mem_id = art.get("id", f"dream_{int(time.time())}_{hash(str(art)) % 10000}")
        content = art.get("content", str(art))
        tags = art.get("tags", [])
        importance = art.get("importance", 0.3)

        self.store.upsert_memory(
            memory_id=mem_id,
            content=content,
            namespace="dream",
            category=art.get("category", "dream_product"),
            importance=importance,
            meta=art.get("meta", {"source": "dream"}),
        )
        if tags:
            self.store.add_tags_to_memory(mem_id, tags)

    def _get_tag_name(self, tag_id: int) -> Optional[str]:
        if not self.store:
            return None
        conn = self.store._get_conn()
        cur = conn.execute("SELECT name FROM tags WHERE id=?", (tag_id,))
        row = cur.fetchone()
        return row[0] if row else None

    def cleanup_old_drafts(self, max_age_hours: int = 48):
        """清理过期的梦境草稿。"""
        if not self.store:
            return
        # 草稿存储在 kv_store 里，key 前缀为 "draft_"
        # 这里简化处理：读取所有 draft_ 键，检查创建时间
        now = time.time()
        keys = self.store.kv_get("__draft_keys__", [])
        valid = []
        for k in keys:
            draft = self.store.kv_get(k, {})
            created = draft.get("created_at", "")
            try:
                if created:
                    ct = datetime.fromisoformat(created).timestamp()
                    if (now - ct) / 3600 > max_age_hours:
                        self.store.kv_set(k, None)  # delete
                        continue
            except (ValueError, TypeError):
                pass
            valid.append(k)
        self.store.kv_set("__draft_keys__", valid)
