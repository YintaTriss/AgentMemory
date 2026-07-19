"""
Dream Provenance — 2026-07-15 方向 6

梦境产物可追溯:每个涌现节点 / 关联 / 隐式 tag 都能回答"为什么出现"。

这是 Mem0/Zep/Letta 完全没做的能力 — 它们的"自动聚合"是黑盒,
我们这里把每个梦境产物的**因果链**完整记录下来。

核心:
1. DreamProvenance — 单个梦境产物的因果链
2. DreamProvenanceTracker — 全局追踪器
3. explain(artifact_id) — 人类可读的因果解释
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any


@dataclass
class DreamProvenance:
    """单个梦境产物的因果链

    字段:
      - artifact_id: 产物 ID (涌现节点 / 关联 / 隐式 tag)
      - artifact_type: "emergent_node" | "association" | "implicit_tag" | "narrative"
      - phase: 产生它的梦境阶段 (light/deep/rem)
      - created_at: ISO 时间
      - inputs: 输入记忆 ID 列表
      - method: 产生方法 ("spike_routing" | "graph_propagation" | "signal_decomposition" 等)
      - parameters: 方法参数
      - confidence: 置信度 (0.0 - 1.0)
      - parent_artifacts: 上游产物 ID (梦境之间的级联)
      - explanation: 人类可读解释
    """
    artifact_id: str
    artifact_type: str
    phase: str
    created_at: str
    inputs: List[str] = field(default_factory=list)
    method: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    parent_artifacts: List[str] = field(default_factory=list)
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DreamProvenance":
        # 兼容旧数据缺字段
        return cls(
            artifact_id=d.get("artifact_id", ""),
            artifact_type=d.get("artifact_type", ""),
            phase=d.get("phase", ""),
            created_at=d.get("created_at", ""),
            inputs=d.get("inputs", []),
            method=d.get("method", ""),
            parameters=d.get("parameters", {}),
            confidence=d.get("confidence", 1.0),
            parent_artifacts=d.get("parent_artifacts", []),
            explanation=d.get("explanation", ""),
        )


class DreamProvenanceTracker:
    """梦境产物追踪器

    用法:
        tracker = DreamProvenanceTracker(storage_path="data/dream_provenance.jsonl")
        tracker.record_emergent(node_id, phase, inputs, method, ...)
        explanation = tracker.explain(node_id)
    """

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path) if storage_path else None
        self._cache: Dict[str, DreamProvenance] = {}
        self._loaded = False

    def _ensure_loaded(self):
        if self._loaded:
            return
        self._loaded = True
        if not self.storage_path or not self.storage_path.exists():
            return
        try:
            with self.storage_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                        prov = DreamProvenance.from_dict(d)
                        self._cache[prov.artifact_id] = prov
                    except Exception:
                        continue
        except Exception:
            pass

    def record(
        self,
        artifact_id: str,
        artifact_type: str,
        phase: str,
        inputs: Optional[List[str]] = None,
        method: str = "",
        parameters: Optional[Dict[str, Any]] = None,
        confidence: float = 1.0,
        parent_artifacts: Optional[List[str]] = None,
        explanation: str = "",
    ) -> DreamProvenance:
        """记录一个梦境产物的因果信息"""
        self._ensure_loaded()
        prov = DreamProvenance(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            phase=phase,
            created_at=datetime.now(timezone.utc).isoformat(),
            inputs=inputs or [],
            method=method,
            parameters=parameters or {},
            confidence=confidence,
            parent_artifacts=parent_artifacts or [],
            explanation=explanation,
        )
        self._cache[artifact_id] = prov
        self._persist(prov)
        return prov

    # ---------- 便捷包装 ----------

    def record_emergent(
        self,
        node_id: str,
        phase: str,
        seed_memory_ids: List[str],
        method: str = "spike_routing",
        hops: int = 0,
        confidence: float = 1.0,
        explanation: str = "",
    ) -> DreamProvenance:
        return self.record(
            artifact_id=node_id,
            artifact_type="emergent_node",
            phase=phase,
            inputs=seed_memory_ids,
            method=method,
            parameters={"hops": hops},
            confidence=confidence,
            explanation=explanation or f"通过 {method} 跨 {hops} 跳从 {len(seed_memory_ids)} 个种子记忆涌现",
        )

    def record_association(
        self,
        assoc_id: str,
        phase: str,
        tag_a: str,
        tag_b: str,
        strength: float,
        method: str = "graph_propagation",
        explanation: str = "",
    ) -> DreamProvenance:
        return self.record(
            artifact_id=assoc_id,
            artifact_type="association",
            phase=phase,
            inputs=[str(tag_a), str(tag_b)],
            method=method,
            parameters={"tag_a": tag_a, "tag_b": tag_b, "strength": strength},
            confidence=min(1.0, strength),
            explanation=explanation or f"{tag_a} ↔ {tag_b} 强度 {strength:.2f}",
        )

    def record_implicit_tag(
        self,
        tag_id: str,
        phase: str,
        source_memory_ids: List[str],
        name: str,
        confidence: float = 1.0,
        method: str = "residual_signal",
        explanation: str = "",
    ) -> DreamProvenance:
        return self.record(
            artifact_id=tag_id,
            artifact_type="implicit_tag",
            phase=phase,
            inputs=source_memory_ids,
            method=method,
            parameters={"name": name},
            confidence=confidence,
            explanation=explanation or f"从 {len(source_memory_ids)} 条记忆的残差信号生成标签 '{name}'",
        )

    # ---------- 查询 ----------

    def get(self, artifact_id: str) -> Optional[DreamProvenance]:
        self._ensure_loaded()
        return self._cache.get(artifact_id)

    def explain(self, artifact_id: str) -> str:
        """人类可读的因果解释"""
        prov = self.get(artifact_id)
        if not prov:
            return f"未找到梦境产物 {artifact_id}"

        lines = [
            f"## 梦境产物: {prov.artifact_id}",
            f"- 类型: {prov.artifact_type}",
            f"- 阶段: {prov.phase}",
            f"- 创建时间: {prov.created_at}",
            f"- 置信度: {prov.confidence:.2f}",
            f"- 方法: {prov.method}",
        ]
        if prov.parameters:
            params_str = ", ".join(f"{k}={v}" for k, v in prov.parameters.items())
            lines.append(f"- 参数: {params_str}")
        if prov.inputs:
            lines.append(f"- 输入 ({len(prov.inputs)}):")
            for inp in prov.inputs[:5]:
                lines.append(f"  - {inp}")
            if len(prov.inputs) > 5:
                lines.append(f"  - ... (+{len(prov.inputs) - 5} more)")
        if prov.parent_artifacts:
            lines.append(f"- 上游产物: {', '.join(prov.parent_artifacts)}")
        if prov.explanation:
            lines.append(f"\n解释: {prov.explanation}")
        return "\n".join(lines)

    def trace_chain(self, artifact_id: str) -> List[DreamProvenance]:
        """递归追溯上游产物链(返回因果链,从根到当前)"""
        self._ensure_loaded()
        chain: List[DreamProvenance] = []
        visited = set()
        stack = [artifact_id]
        while stack:
            aid = stack.pop()
            if aid in visited:
                continue
            visited.add(aid)
            prov = self._cache.get(aid)
            if not prov:
                continue
            chain.append(prov)
            stack.extend(prov.parent_artifacts)
        # 按创建时间排序(根在前)
        chain.sort(key=lambda p: p.created_at)
        return chain

    # ---------- 持久化 ----------

    def _persist(self, prov: DreamProvenance) -> None:
        if not self.storage_path:
            return
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with self.storage_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(prov.to_dict(), ensure_ascii=False) + "\n")
        except Exception:
            pass  # 持久化失败不应阻塞梦境

    def count(self) -> int:
        self._ensure_loaded()
        return len(self._cache)

    def list_by_type(self, artifact_type: str) -> List[DreamProvenance]:
        self._ensure_loaded()
        return [p for p in self._cache.values() if p.artifact_type == artifact_type]