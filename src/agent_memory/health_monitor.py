"""
health_monitor.py — 记忆健康度监控（对标 OpenClaw 的 health_score / recovery）

- health_score: 0~1, 基于标签使用率 / 共现密度 / 最近写入时间
- recovery: 当 score < threshold 时自动触发补救
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class HealthMonitor:
    """记忆健康度监控。"""

    def __init__(self, sqlite_store=None, namespace: str = "default"):
        self.store = sqlite_store
        self.namespace = namespace
        self.trigger_below = 0.35

    def compute_health(self) -> Dict[str, Any]:
        """计算记忆健康度（0~1）。"""
        if not self.store:
            return {"health": 0.5, "error": "no store"}

        stats = self.store.stats(self.namespace)
        mem_count = stats.get("memories", 0)
        tag_count = stats.get("tags", 0)
        cooc_count = stats.get("cooccurrences", 0)

        if mem_count == 0:
            return {"health": 0.0, "reason": "empty", "stats": stats}

        # 标签覆盖率
        tag_density = min(1.0, tag_count / max(mem_count, 1))

        # 共现图密度
        if tag_count > 1:
            possible_edges = tag_count * (tag_count - 1) / 2
            graph_density = min(1.0, cooc_count / max(possible_edges, 1))
        else:
            graph_density = 0.0

        # 最近写入活动
        conn = self.store._get_conn()
        cur = conn.execute(
            "SELECT created_at FROM memories WHERE namespace=? ORDER BY created_at DESC LIMIT 1",
            (self.namespace,),
        )
        row = cur.fetchone()
        recency = 0.5
        if row and row[0]:
            try:
                last_write = datetime.fromisoformat(row[0])
                days_since = (datetime.now(timezone.utc) - last_write).total_seconds() / 86400
                recency = max(0, min(1, 1 - days_since / 30))
            except (ValueError, TypeError):
                pass

        # 综合评分
        health = (tag_density * 0.3 + graph_density * 0.3 + recency * 0.4)

        return {
            "health": round(min(1.0, health), 3),
            "tag_density": round(tag_density, 3),
            "graph_density": round(graph_density, 3),
            "recency": round(recency, 3),
            "memories": mem_count,
            "tags": tag_count,
            "cooccurrences": cooc_count,
        }

    def needs_recovery(self) -> bool:
        """检测是否需要恢复。"""
        info = self.compute_health()
        return info.get("health", 1.0) < self.trigger_below

    def recover(self, dry_run: bool = False) -> Dict:
        """自动恢复：回填标签 / 重建共现 / 写入健康报告。"""
        if not self.store:
            return {"error": "no store"}

        info = self.compute_health()
        actions = []

        # 1. 如果共现图稀疏，重建
        if info.get("graph_density", 1) < 0.05:
            if not dry_run:
                self.store.rebuild_cooccurrence()
            actions.append("rebuild_cooccurrence")

        # 2. 写入健康报告
        if not dry_run:
            from datetime import datetime, timezone
            self.store.kv_set(f"health_report_{datetime.now(timezone.utc).isoformat()}", info)

        return {
            "health": info,
            "actions": actions,
            "dry_run": dry_run,
        }
