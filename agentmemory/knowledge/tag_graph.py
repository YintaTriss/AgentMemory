"""
tag_graph.py — Tag 共现图谱
从历史记忆的 Tags 中挖掘共现关系，构建 Tag 共现图谱。
用于：
1. 检索增强（共现Tags关联记忆）
2. 推荐共现Tags（写入时推荐常一起出现的Tags）
3. 社区发现（Tag聚类）
"""

import json
import asyncio
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional
from collections import defaultdict
from itertools import combinations
import aiofiles


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class TagNode:
    """Tag 图谱中的节点"""
    tag: str
    frequency: int = 0  # 出现次数
    cooccurrence_count: int = 0  # 共现次数（边权重之和）
    first_seen: str = ""  # UTC ISO 8601
    last_seen: str = ""  # UTC ISO 8601


@dataclass
class TagEdge:
    """Tag 共现边"""
    tag_a: str
    tag_b: str
    weight: float = 0.0  # 共现次数 / min(freq_a, freq_b)，归一化
    co_count: int = 0  # 原始共现次数
    last_updated: str = ""  # UTC ISO 8601


# =============================================================================
# Tag Cooccurrence Graph
# =============================================================================

class TagCooccurrenceGraph:
    """Tag 共现图谱"""

    SCHEMA_VERSION = 1

    def __init__(self, storage_path: Path):
        self.storage_path = Path(storage_path)
        self.graph_file = self.storage_path / ".tag_graph.json"
        self.nodes: dict[str, TagNode] = {}
        self.edges: dict[tuple[str, str], TagEdge] = {}  # (min, max) -> Edge
        self._lock = asyncio.Lock()

    # --------------------------------------------------------------------------
    # Edge Key Helpers
    # --------------------------------------------------------------------------

    @staticmethod
    def _edge_key(tag_a: str, tag_b: str) -> tuple[str, str]:
        """返回规范化的边键（字典序）"""
        return (min(tag_a, tag_b), max(tag_a, tag_b))

    # --------------------------------------------------------------------------
    # Core Operations
    # --------------------------------------------------------------------------

    async def add_memory_tags(self, memory_id: str, tags: list[str]) -> None:
        """从一条记忆的 Tags 更新图谱

        1. 更新每个 Tag 的 frequency
        2. 对每对 Tag 组合，更新共现边
        3. 归一化边权重
        """
        if not tags:
            return

        async with self._lock:
            now = _utc_now()

            # 1. Update each tag's frequency and timestamps
            for tag in tags:
                if tag not in self.nodes:
                    self.nodes[tag] = TagNode(
                        tag=tag,
                        frequency=0,
                        cooccurrence_count=0,
                        first_seen=now,
                        last_seen=now,
                    )
                self.nodes[tag].frequency += 1
                self.nodes[tag].last_seen = now

            # 2. Update cooccurrence edges for each pair
            for tag_a, tag_b in combinations(sorted(set(tags)), 2):
                key = self._edge_key(tag_a, tag_b)
                if key not in self.edges:
                    self.edges[key] = TagEdge(
                        tag_a=key[0],
                        tag_b=key[1],
                        co_count=0,
                        weight=0.0,
                        last_updated=now,
                    )
                self.edges[key].co_count += 1
                self.edges[key].last_updated = now

            # 3. Normalize edge weights and update node cooccurrence counts
            self._recompute_weights_unlocked()

            await self._save_graph()

    async def remove_memory_tags(self, memory_id: str, tags: list[str]) -> None:
        """删除记忆时，更新图谱（减少计数）"""
        if not tags:
            return

        async with self._lock:
            now = _utc_now()

            # Decrement frequency for each tag
            for tag in tags:
                if tag in self.nodes:
                    self.nodes[tag].frequency -= 1
                    self.nodes[tag].last_seen = now
                    if self.nodes[tag].frequency <= 0:
                        del self.nodes[tag]

            # Decrement cooccurrence edges
            for tag_a, tag_b in combinations(sorted(set(tags)), 2):
                key = self._edge_key(tag_a, tag_b)
                if key in self.edges:
                    self.edges[key].co_count -= 1
                    self.edges[key].last_updated = now
                    if self.edges[key].co_count <= 0:
                        del self.edges[key]

            # Recompute weights
            self._recompute_weights_unlocked()
            await self._save_graph()

    def _recompute_weights_unlocked(self) -> None:
        """重建整个图谱的边权重（必须在持有锁时调用）"""
        for key, edge in list(self.edges.items()):
            tag_a, tag_b = key
            if tag_a not in self.nodes or tag_b not in self.nodes:
                # Clean up orphaned edges
                del self.edges[key]
                continue
            edge.weight = self._normalize_weight(edge)

        # Update node cooccurrence counts (sum of edge weights)
        for node in self.nodes.values():
            node.cooccurrence_count = 0
        for edge in self.edges.values():
            self.nodes[edge.tag_a].cooccurrence_count += int(edge.co_count)
            self.nodes[edge.tag_b].cooccurrence_count += int(edge.co_count)

    def _normalize_weight(self, edge: TagEdge) -> float:
        """归一化权重 = co_count / min(freq_a, freq_b)"""
        node_a = self.nodes.get(edge.tag_a)
        node_b = self.nodes.get(edge.tag_b)
        if not node_a or not node_b:
            return 0.0
        min_freq = min(node_a.frequency, node_b.frequency)
        return edge.co_count / min_freq if min_freq > 0 else 0.0

    # --------------------------------------------------------------------------
    # Query Operations
    # --------------------------------------------------------------------------

    async def get_neighbors(self, tag: str, top_k: int = 5) -> list[tuple[str, float]]:
        """获取与 tag 共现最多的 K 个 Tags，返回 (tag, weight) 列表"""
        async with self._lock:
            neighbors: list[tuple[str, float]] = []
            for key, edge in self.edges.items():
                if edge.tag_a == tag:
                    neighbors.append((edge.tag_b, edge.weight))
                elif edge.tag_b == tag:
                    neighbors.append((edge.tag_a, edge.weight))
            # Sort by weight descending
            neighbors.sort(key=lambda x: x[1], reverse=True)
            return neighbors[:top_k]

    async def get_communities(self, weight_threshold: float = 0.3) -> list[list[str]]:
        """社区发现——找出经常一起出现的 Tag 群组

        简单实现：基于阈值过滤 + 连通分量
        """
        async with self._lock:
            # Build adjacency list
            adj: dict[str, set[str]] = defaultdict(set)
            for edge in self.edges.values():
                if edge.weight >= weight_threshold:
                    adj[edge.tag_a].add(edge.tag_b)
                    adj[edge.tag_b].add(edge.tag_a)

            # Find connected components via BFS
            visited: set[str] = set()
            communities: list[list[str]] = []

            for start_tag in adj:
                if start_tag in visited:
                    continue
                component: list[str] = []
                queue = [start_tag]
                while queue:
                    node = queue.pop(0)
                    if node in visited:
                        continue
                    visited.add(node)
                    component.append(node)
                    for neighbor in adj[node]:
                        if neighbor not in visited:
                            queue.append(neighbor)
                if component:
                    communities.append(sorted(component))

            return communities

    async def suggest_tags(
        self, input_tags: list[str], top_k: int = 3
    ) -> list[tuple[str, float]]:
        """基于已有 Tags 推荐可能一起出现的 Tags"""
        async with self._lock:
            # Aggregate neighbor weights from all input tags
            candidate_weights: dict[str, float] = defaultdict(float)
            for tag in input_tags:
                for neighbor, weight in self._get_neighbors_unlocked(tag):
                    if neighbor not in input_tags:
                        candidate_weights[neighbor] += weight

            # Sort by aggregated weight
            sorted_candidates = sorted(
                candidate_weights.items(), key=lambda x: x[1], reverse=True
            )
            return sorted_candidates[:top_k]

    def _get_neighbors_unlocked(self, tag: str) -> list[tuple[str, float]]:
        """Neighbor lookup (must hold lock)"""
        neighbors: list[tuple[str, float]] = []
        for key, edge in self.edges.items():
            if edge.tag_a == tag:
                neighbors.append((edge.tag_b, edge.weight))
            elif edge.tag_b == tag:
                neighbors.append((edge.tag_a, edge.weight))
        neighbors.sort(key=lambda x: x[1], reverse=True)
        return neighbors

    async def search_by_cooccurrence(
        self, seed_tags: list[str], depth: int = 1
    ) -> list[str]:
        """从种子 Tags 出发，按共现关系扩展搜索"""
        async with self._lock:
            if depth <= 0:
                return list(seed_tags)

            result = set(seed_tags)
            frontier = list(seed_tags)

            for _ in range(depth):
                next_frontier: list[str] = []
                for tag in frontier:
                    for neighbor, weight in self._get_neighbors_unlocked(tag):
                        if neighbor not in result and weight > 0:
                            result.add(neighbor)
                            next_frontier.append(neighbor)
                frontier = next_frontier
                if not frontier:
                    break

            return list(result)

    # --------------------------------------------------------------------------
    # Persistence
    # --------------------------------------------------------------------------

    async def load(self) -> None:
        """从 .tag_graph.json 加载图谱"""
        if not self.graph_file.exists():
            return

        async with self._lock:
            async with aiofiles.open(self.graph_file, "r", encoding="utf-8") as f:
                data = json.loads(await f.read())

            self.nodes.clear()
            self.edges.clear()

            for tag, node_data in data.get("nodes", {}).items():
                self.nodes[tag] = TagNode(**node_data)

            for edge_key, edge_data in data.get("edges", {}).items():
                # Parse "tag_a||tag_b" back to tuple key
                parts = edge_key.split("||")
                if len(parts) == 2:
                    key = (parts[0], parts[1])
                    self.edges[key] = TagEdge(**edge_data)

    async def _save_graph(self) -> None:
        """持久化图谱到 .tag_graph.json"""
        self.storage_path.mkdir(parents=True, exist_ok=True)

        nodes_data = {tag: asdict(node) for tag, node in self.nodes.items()}

        edges_data: dict[str, dict] = {}
        for key, edge in self.edges.items():
            edge_key_str = f"{key[0]}||{key[1]}"
            edges_data[edge_key_str] = asdict(edge)

        data = {
            "schema_version": self.SCHEMA_VERSION,
            "nodes": nodes_data,
            "edges": edges_data,
        }

        tmp = self.graph_file.with_suffix(".tmp")
        async with aiofiles.open(tmp, "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=2))
        tmp.replace(self.graph_file)


# =============================================================================
# Helpers
# =============================================================================

def _utc_now() -> str:
    """返回当前 UTC ISO 8601 时间字符串"""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
