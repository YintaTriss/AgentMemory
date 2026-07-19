"""
Observations Generator — 方向 3 (2026-07-15)

从一组 memory fact 提取模式 / 观察 / 洞察,作为给 LLM 的 context 第三层。

设计哲学:
- 精简版,不上 LLM 总结 — 100% 用现有 meta 数据
- 给已经在 dream_graph.py 里的 Spike Routing "涌现节点" 能力起个名 + 暴露
- 让 compress_for_context / compress_with_facts 的输出更聪明

输出:
- 字符串列表,每条都是一句自然语言 observation
- 按重要性排序,最多 5 条

实现层次:
1. 高频 tag 聚类 (出现 ≥ 3 次)
2. 高重要度事实统计 (≥ 0.8)
3. 时间窗口密度 (同一日期 ≥ 2 条 = "高频")
4. 类别分布 (top-3 category)
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import List, Dict, Any


class ObservationsGenerator:
    """从 facts 中产生简洁 pattern observations(不上 LLM)"""

    def __init__(
        self,
        min_tag_freq: int = 3,
        high_importance_threshold: float = 0.8,
        same_day_density: int = 2,
        max_observations: int = 5,
    ):
        self.min_tag_freq = min_tag_freq
        self.high_importance_threshold = high_importance_threshold
        self.same_day_density = same_day_density
        self.max_observations = max_observations

    def generate(self, memories: List[Dict[str, Any]]) -> List[str]:
        """从 memories 中产生 observations"""
        observations: List[str] = []

        if not memories:
            return observations

        # 1. 高频 tag
        tag_counter = self._top_tags(memories)
        if tag_counter:
            top_tags = [tag for tag, count in tag_counter.items() if count >= self.min_tag_freq]
            if top_tags:
                observations.append(
                    f"高频标签:{', '.join(top_tags[:5])}"
                    f"({', '.join(f'{t}({c}次)' for t, c in tag_counter.most_common(3))})"
                )

        # 2. 高重要度事实统计
        high_count = sum(
            1 for m in memories
            if m.get("meta", {}).get("importance", 0.5) >= self.high_importance_threshold
        )
        if high_count > 0:
            observations.append(
                f"高重要度(≥{self.high_importance_threshold})事实:{high_count} 条,可能与近期关键决策相关"
            )

        # 3. 时间窗口密度 — 同一日期 ≥ 2 条
        date_groups = self._group_by_date(memories)
        dense_dates = [
            (date, len(items)) for date, items in date_groups.items()
            if len(items) >= self.same_day_density
        ]
        if dense_dates:
            dense_dates.sort(key=lambda x: -x[1])
            top = dense_dates[:3]
            observations.append(
                "高频日期:"
                + ", ".join(f"{date}({n}条)" for date, n in top)
            )

        # 4. 类别分布 top-3
        cat_counter = self._top_categories(memories)
        if cat_counter:
            top_cats = cat_counter.most_common(3)
            observations.append(
                "类别分布:"
                + ", ".join(f"{cat}({c}条)" for cat, c in top_cats)
            )

        # 5. 来源分布
        source_counter = self._top_sources(memories)
        if len(source_counter) > 1:
            top_src = source_counter.most_common(3)
            observations.append(
                "来源分布:"
                + ", ".join(f"{src}({c}条)" for src, c in top_src)
            )

        return observations[: self.max_observations]

    @staticmethod
    def _top_tags(memories: List[Dict[str, Any]]) -> Counter:
        counter: Counter = Counter()
        for m in memories:
            for tag in m.get("meta", {}).get("tags", []) or []:
                counter[tag] += 1
        return counter

    @staticmethod
    def _top_categories(memories: List[Dict[str, Any]]) -> Counter:
        counter: Counter = Counter()
        for m in memories:
            cat = m.get("meta", {}).get("category", "general") or "general"
            counter[cat] += 1
        return counter

    @staticmethod
    def _top_sources(memories: List[Dict[str, Any]]) -> Counter:
        counter: Counter = Counter()
        for m in memories:
            src = m.get("meta", {}).get("source", "") or "unknown"
            counter[src] += 1
        return counter

    @staticmethod
    def _group_by_date(memories: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for m in memories:
            ts = m.get("meta", {}).get("created_at", "")
            date_str = ts[:10] if ts else "unknown"
            groups.setdefault(date_str, []).append(m)
        return groups