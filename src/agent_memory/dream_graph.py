"""
dream_graph.py — 梦境 Phase 2: 图传播 (Spike Routing)

对标 VCP TagMemoEngine.js 源码 (V7) 的 Spike Propagation：
- 动量衰减脉冲传播 (TTL 每跳 -1，虫洞豁免)
- 虫洞判定：张力 = coocWeight * residualNovelty > TENSION_THRESHOLD
- 涌现节点发现
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple


class GraphPropagator:
    """梦境图传播器 — Spike Routing 在共现图上扩散激活。"""

    def __init__(self, cooccurrence: Optional[Dict[int, Dict[int, float]]] = None):
        self.cooc = cooccurrence or {}
        self._residuals: Dict[int, float] = {}  # tag_id → 残差新颖度 (0~1)

    def load_from_store(self, store, namespace: str = "default"):
        """从 SQLiteStore 加载共现图 + 残差新颖度。"""
        conn = store._get_conn()
        cur = conn.execute("""
            SELECT t1.id, t2.id, tc.weight
            FROM tag_cooccurrence tc
            JOIN tags t1 ON tc.tag1_id = t1.id AND t1.namespace = ?
            JOIN tags t2 ON tc.tag2_id = t2.id AND t2.namespace = ?
        """, (namespace, namespace))

        cooc: Dict[int, Dict[int, float]] = defaultdict(dict)
        for t1_id, t2_id, weight in cur.fetchall():
            norm = min(1.0, weight / 10.0)
            cooc[t1_id][t2_id] = norm
            cooc[t2_id][t1_id] = norm
        self.cooc = dict(cooc)

        # 加载残差新颖度（若无数据，默认 0.5）
        try:
            cur2 = conn.execute("SELECT tag_id, residual_energy FROM tag_intrinsic_residuals")
            for row in cur2.fetchall():
                self._residuals[row[0]] = min(1.0, float(row[1]))
        except Exception:
            self._residuals = {}

    def propagate(self, seed_nodes: List[int],
                  base_momentum: float = 2.0,
                  base_decay: float = 0.25,
                  wormhole_decay: float = 0.7,
                  firing_threshold: float = 0.05,
                  max_hops: int = 10,
                  max_emergent: int = 50,
                  tension_threshold: float = 1.0,
                  max_neighbors: int = 20) -> Dict:
        """
        Spike Routing (对标 VCP TagMemoEngine.js 源码 V7)。

        核心机制：
        - 每跳 momentum -1，归零则停止传播（除非是虫洞）
        - 虫洞 = 张力 > threshold = coocWeight * 目标节点残差新颖度
        - 虫洞豁免动量消耗（零动量成本）
        - 到达同一节点的脉冲能量叠加

        Args:
            seed_nodes: 起始标签 ID 列表（带初始能量）
            base_momentum: 初始动量 (TTL)
            base_decay: 常规边衰减
            wormhole_decay: 虫洞边衰减（VCP 0.7）
            firing_threshold: 激发能量阈值
            max_hops: 最大跳数
            max_emergent: 最多涌现节点数
            tension_threshold: 虫洞判定张力阈值
            max_neighbors: 每个节点最多扇出邻居数
        """
        if not self.cooc:
            return {"activations": {}, "emergent_nodes": [], "propagation_tree": []}

        accumulated: Dict[int, float] = {}
        # { node_id: { energy, momentum } }
        active: Dict[int, Tuple[float, float]] = {
            n: (1.0, base_momentum) for n in seed_nodes
        }
        propagation_tree: List[Dict] = []

        for hop in range(max_hops + 1):
            next_active: Dict[int, Tuple[float, float]] = {}
            propagated = False

            for node_id, (energy, momentum) in active.items():
                if energy < firing_threshold or momentum < 0:
                    continue

                synapses = self.cooc.get(node_id, {})
                sorted_syn = sorted(synapses.items(), key=lambda x: x[1], reverse=True)
                sorted_syn = sorted_syn[:max_neighbors]

                for neighbor_id, cooc_weight in sorted_syn:
                    # 张力：coocWeight * 目标节点残差新颖度
                    neighbor_novelty = self._residuals.get(neighbor_id, 0.5)
                    tension = cooc_weight * neighbor_novelty

                    # 虫洞判定：张力 > threshold
                    is_wormhole = tension >= tension_threshold

                    # VCP 源码:
                    # decayFactor = isWormhole ? WORMHOLE_DECAY : BASE_DECAY
                    # momentumCost = isWormhole ? 0 : 1.0
                    decay_factor = wormhole_decay if is_wormhole else base_decay
                    momentum_cost = 0.0 if is_wormhole else 1.0

                    # injectedCurrent = spike.energy * coocWeight * decayFactor
                    injected = energy * cooc_weight * decay_factor
                    if injected < 0.01:
                        continue

                    next_momentum = momentum - momentum_cost
                    if next_momentum < 0 and not is_wormhole:
                        continue

                    # 能量叠加（同节点合并）
                    existing = next_active.get(neighbor_id)
                    if existing:
                        old_e, old_m = existing
                        next_active[neighbor_id] = (
                            old_e + injected,
                            max(old_m, next_momentum),  # 保留最优动量
                        )
                    else:
                        next_active[neighbor_id] = (injected, next_momentum)

                    propagation_tree.append({
                        "from": node_id,
                        "to": neighbor_id,
                        "hop": hop,
                        "injected_energy": round(injected, 4),
                        "wormhole": is_wormhole,
                        "tension": round(tension, 3),
                        "momentum_remaining": next_momentum,
                    })

                    if injected > 0.01:
                        propagated = True

            # 累加本轮激活到全局
            for nid, (e, _) in next_active.items():
                accumulated[nid] = accumulated.get(nid, 0.0) + e

            if not propagated:
                break
            active = next_active

        # 涌现节点
        seed_set = set(seed_nodes)
        emergent = sorted(
            [n for n in accumulated if n not in seed_set],
            key=lambda n: accumulated[n],
            reverse=True,
        )[:max_emergent]

        return {
            "activations": dict(accumulated),
            "emergent_nodes": emergent,
            "propagation_tree": propagation_tree,
        }

    def recommend_tags(self, seed_tags: List[int], top_k: int = 5) -> List[Dict]:
        result = self.propagate(seed_tags, max_hops=3)
        emergent = result["emergent_nodes"]
        activations = result["activations"]
        emergent.sort(key=lambda n: activations.get(n, 0), reverse=True)
        return [
            {"tag_id": n, "activation": activations.get(n, 0)}
            for n in emergent[:top_k]
        ]
