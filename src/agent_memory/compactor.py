"""
MemoryCompactor — 记忆压缩/老化。
- 标记低重要性记忆
- 删除过期（importance < threshold 且 age > max_age_days）
- 支持 dry_run
"""
from __future__ import annotations
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class MemoryCompactor:
    def __init__(
        self,
        importance_threshold: float = 0.2,
        max_age_days: int = 90,
        max_memories: int = 10000,
    ):
        self.importance_threshold = importance_threshold
        self.max_age_days = max_age_days
        self.max_memories = max_memories

    def score_for_removal(self, memory: Dict[str, Any]) -> Tuple[float, str]:
        """返回移除分数（越高越该删）+ 原因。"""
        import hashlib
        content = memory.get("content", "") or ""
        meta = memory.get("meta", {}) or {}
        importance = float(meta.get("importance", 0.5))
        age_days = 0
        created = meta.get("created_at", None)
        if created:
            try:
                created_ts = datetime.fromisoformat(created).timestamp()
                age_days = (time.time() - created_ts) / 86400
            except (ValueError, TypeError):
                pass

        reasons = []
        score = 0.0

        if importance < self.importance_threshold:
            score += 2.0
            reasons.append(f"low_importance({importance:.2f})")

        if age_days > self.max_age_days:
            score += 3.0
            reasons.append(f"expired({age_days:.0f}d)")

        if len(content) < 10:
            score += 1.0
            reasons.append("too_short")

        # 短内容权重加成
        if score > 0:
            return score, ",".join(reasons)
        return 0.0, ""

    def compact(
        self, memories: List[Dict[str, Any]], dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        执行压缩：标记 + 可选删除。

        Args:
            memories: 记忆列表
            dry_run: 仅模拟（统计已删而不真的删）

        Returns:
            {"removed": N, "kept": M, "details": [...]}
        """
        details = []
        kept = []
        removed = []

        for mem in memories:
            score, reason = self.score_for_removal(mem)
            if score > 0:
                details.append({
                    "id": mem.get("id", ""),
                    "content_preview": (mem.get("content", "") or "")[:60],
                    "score": score,
                    "reason": reason,
                })
                if not dry_run:
                    removed.append(mem)
            else:
                kept.append(mem)

        # 如果内存总数超过 max_memories，删最旧的
        if not dry_run and len(kept) > self.max_memories:
            # 按 created_at 排序
            kept.sort(key=lambda m: m.get("meta", {}).get("created_at", "") or "")
            excess = len(kept) - self.max_memories
            for m in kept[:excess]:
                removed.append(m)
                details.append({
                    "id": m.get("id", ""),
                    "content_preview": (m.get("content", "") or "")[:60],
                    "score": 0.0,
                    "reason": "max_memories_exceeded",
                })
            kept = kept[excess:]

        return {
            "removed": len(details),
            "kept": len(kept),
            "dry_run": dry_run,
            "details": details,
        }
