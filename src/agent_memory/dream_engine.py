"""
dream_engine.py — 梦境系统总控（三阶段版）

OpenClaw 风格三阶段调度：
- Light (每6h):  快速 Tag 扫描 + 轻量去重，更新标签使用计数
- Deep (每天3am): 完整的信号分解 + 残差金字塔
- REM (每周日):   全图传播 + Spike Routing + 跨簇虫洞路由

每个阶段调用 Phase 1~4：
Phase 1: 信号分解
Phase 2: 图传播
Phase 3: 梦境产物生成
Phase 4: 记忆固化
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .dream_signal import SignalDecomposer
from .dream_graph import GraphPropagator
from .dream_consolidate import DreamConsolidator
from .dream_narrative import DreamNarrativeGenerator
from .health_monitor import HealthMonitor


class DreamEngine:
    """梦境引擎 — 三阶段记忆处理。"""

    def __init__(self, sqlite_store=None, embedder=None, namespace: str = "default"):
        self.store = sqlite_store
        self.embedder = embedder
        self.namespace = namespace
        self.signal = SignalDecomposer()
        self.graph = GraphPropagator()
        self.consolidator = DreamConsolidator(sqlite_store, embedder)
        self.narrator = DreamNarrativeGenerator(sqlite_store)
        self.health = HealthMonitor(sqlite_store, namespace)

    def dream_cycle(self, phase: str = "deep", dry_run: bool = False,
                    candidate_names: Optional[List[str]] = None) -> Dict:
        """
        执行梦境循环（三阶段调度）。

        Args:
            phase: "light" | "deep" | "rem"
            dry_run: 仅模拟
            candidate_names: 隐式标签候选名称

        Returns:
            包含所有阶段结果的报告
        """
        t_start = time.perf_counter()
        report = {"phase": phase, "phases": {}, "artifacts": [], "timing_ms": {}}

        if not self.store:
            return {"error": "SQLiteStore not configured"}

        # 检查是否已在该阶段当前周期执行过
        phase_key = f"dream_last_run_{phase}"
        last_run = self.store.kv_get(phase_key)
        if last_run and not dry_run:
            report["skipped_reason"] = f"Already ran {phase} at {last_run}"

        # 加载数据
        t0 = time.perf_counter()
        memories = self.store.list_memories(namespace=self.namespace, limit=5000)
        tags_data = self._load_tags()
        report["data"] = {"memories": len(memories), "tags": len(tags_data)}
        report["timing_ms"]["load"] = (time.perf_counter() - t0) * 1000

        # 按阶段执行
        if phase == "light":
            artifacts = self._run_light_phase(memories, tags_data, report)
        elif phase == "deep":
            artifacts = self._run_deep_phase(memories, tags_data, candidate_names or [], report)
        elif phase == "rem":
            artifacts = self._run_rem_phase(memories, tags_data, candidate_names or [], report)
        else:
            return {"error": f"Unknown phase: {phase}"}

        report["artifacts"] = artifacts
        report["total_ms"] = (time.perf_counter() - t_start) * 1000

        # 固化
        t0 = time.perf_counter()
        cons = self.consolidator.consolidate(artifacts, dry_run=dry_run)
        report["phases"]["consolidation"] = cons
        report["timing_ms"]["consolidate"] = (time.perf_counter() - t0) * 1000

        # 叙事生成
        t0 = time.perf_counter()
        narrative = self.narrator.generate(phase, report)
        if narrative:
            report["narrative"] = narrative
            if not dry_run and self.store:
                # 以高置信度写入记忆
                art = self.narrator.format_as_memory(narrative, phase)
                self.consolidator.consolidate([art], dry_run=False)
        report["timing_ms"]["narrative"] = (time.perf_counter() - t0) * 1000

        # 健康监控
        t0 = time.perf_counter()
        health_info = self.health.compute_health()
        report["health"] = health_info
        if health_info.get("health", 1.0) < self.health.trigger_below and not dry_run:
            recovery = self.health.recover(dry_run=False)
            report["recovery"] = recovery
            report["timing_ms"]["recovery"] = (time.perf_counter() - t0) * 1000

        # 记录运行时间
        if not dry_run and self.store:
            self.store.kv_set(phase_key, datetime.now(timezone.utc).isoformat())

        return report

    # ========== Light Phase ==========

    def _run_light_phase(self, memories, tags_data, report) -> List[Dict]:
        """Light：快速 Tag 扫描 + 轻量关联。"""
        t0 = time.perf_counter()
        artifacts = []

        if not tags_data:
            return artifacts

        # 提取高频标签的共现关联
        self.graph.load_from_store(self.store, self.namespace)
        if self.graph.cooc:
            # 取前 10 个标签做种子
            sorted_tags = sorted(tags_data, key=lambda t: t.get("id", 0))
            seed_ids = [t["id"] for t in sorted_tags[:10] if "id" in t]
            if seed_ids:
                spike = self.graph.propagate(seed_ids, max_hops=2, firing_threshold=0.1)
                tag_id_to_name = {t["id"]: t["name"] for t in tags_data if "id" in t}
                for nid in spike.get("emergent_nodes", [])[:5]:
                    name = tag_id_to_name.get(nid, f"tag_{nid}")
                    act = spike["activations"].get(nid, 0)
                    if act > 0.1:
                        artifacts.append({
                            "id": f"light_{nid}",
                            "content": f"## Light Dream Association\nTag: {name}\nActivation: {act:.2f}\nTag: 轻梦境, {name}\n",
                            "tags": ["轻梦境", name],
                            "confidence": min(0.6, act),
                            "importance": act * 0.3,
                            "category": "light_dream",
                            "meta": {"activation": act},
                        })

        report["phases"]["light"] = {
            "status": "completed",
            "artifacts": len(artifacts),
        }
        report["timing_ms"]["phase"] = (time.perf_counter() - t0) * 1000
        return artifacts

    # ========== Deep Phase (原完整 cycle) ==========

    def _run_deep_phase(self, memories, tags_data, candidate_names, report):
        t0 = time.perf_counter()
        phase1 = self._phase1_signal_decomposition(memories, tags_data)
        report["phases"]["signal_decomposition"] = phase1
        report["timing_ms"]["phase1"] = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        phase2 = self._phase2_graph_propagation(tags_data)
        report["phases"]["graph_propagation"] = phase2
        report["timing_ms"]["phase2"] = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        phase3 = self._phase3_artifact_generation(phase1, phase2, tags_data, candidate_names)
        report["phases"]["artifact_generation"] = phase3
        report["timing_ms"]["phase3"] = (time.perf_counter() - t0) * 1000

        return phase3.get("artifacts", [])

    # ========== REM Phase ==========

    def _run_rem_phase(self, memories, tags_data, candidate_names, report):
        """REM：全图传播 + 跨簇虫洞路由。"""
        t0 = time.perf_counter()
        artifacts = []

        # 加载完整共现图
        self.graph.load_from_store(self.store, self.namespace)
        if not self.graph.cooc:
            return artifacts

        # 全标签注入作为种子
        all_ids = [t["id"] for t in tags_data if "id" in t]
        if len(all_ids) < 3:
            return artifacts

        # Spike Routing 全图传播（更多跳数、更低阈值）
        spike = self.graph.propagate(
            all_ids[:min(20, len(all_ids))],
            max_hops=5,
            firing_threshold=0.03,
            max_emergent=100,
        )

        tag_id_to_name = {t["id"]: t["name"] for t in tags_data if "id" in t}
        discovered = set()
        for nid in spike.get("emergent_nodes", []):
            name = tag_id_to_name.get(nid)
            if not name or name in discovered:
                continue
            discovered.add(name)
            act = spike["activations"].get(nid, 0)
            if act > 0.05:
                artifacts.append({
                    "id": f"rem_{hashlib.md5(name.encode()).hexdigest()[:8]}",
                    "content": f"## REM Dream Pattern\nTag: {name}\nActivation: {act:.3f}\nTag: rem梦境, {name}\n",
                    "tags": ["rem梦境", name],
                    "confidence": min(0.8, act),
                    "importance": min(0.6, act * 0.5),
                    "category": "rem_dream",
                    "meta": {"activation": act, "phase": "rem"},
                })

        # 虫洞路由统计
        wormholes = [p for p in spike.get("propagation_tree", []) if p.get("wormhole")]
        report["phases"]["rem"] = {
            "status": "completed",
            "emergent_tags": len(artifacts),
            "wormhole_count": len(wormholes),
            "total_activated": len(spike["activations"]),
        }
        report["timing_ms"]["phase"] = (time.perf_counter() - t0) * 1000
        return artifacts

    # ========== 以下为原来的私有方法，保持不变 ==========

    def _load_tags(self) -> List[Dict]:
        if not self.store:
            return []
        conn = self.store._get_conn()
        cur = conn.execute(
            "SELECT id, name, vector FROM tags WHERE namespace=? ORDER BY usage_count DESC",
            (self.namespace,),
        )
        return [{"id": row["id"], "name": row["name"], "vector_raw": row["vector"]} for row in cur.fetchall()]

    def _tags_to_vectors(self, tags: List[Dict]) -> Optional[np.ndarray]:
        vectors = []
        for t in tags:
            raw = t.get("vector_raw")
            if raw and len(raw) > 0:
                try:
                    vec = np.frombuffer(raw, dtype=np.float32)
                    if len(vec) == 1536:
                        vectors.append(vec)
                        t["vector"] = vec
                except Exception:
                    pass
        return np.array(vectors) if vectors else None

    def _phase1_signal_decomposition(self, memories, tags_data):
        if not memories or not tags_data:
            return {"status": "skipped", "reason": "no data"}
        import numpy as np
        content_vecs = self._memories_to_vectors(memories)
        tag_vecs = self._tags_to_vectors(tags_data)
        if content_vecs is None or tag_vecs is None:
            return {"status": "skipped", "reason": "no vectors"}
        tag_names = [t.get("name", "") for t in tags_data]
        self.signal.fit_epa(tag_vecs, tag_names)
        n_batches = min(5, len(content_vecs))
        batch_size = max(1, len(content_vecs) // n_batches)
        decompositions = []
        for b in range(n_batches):
            start, end = b * batch_size, min((b + 1) * batch_size, len(content_vecs))
            batch_vecs = content_vecs[start:end]
            if len(batch_vecs) == 0:
                continue
            qv = batch_vecs.mean(axis=0)
            qv /= np.linalg.norm(qv) + 1e-8
            epa = self.signal.project(qv)
            pyr = self.signal.decompose(qv, tag_vecs)
            decompositions.append({"batch": b, "epa": epa, "pyramid": {"total_coverage": pyr["total_coverage"], "features": pyr["features"]}})
        avg_cov = float(np.mean([d["pyramid"]["total_coverage"] for d in decompositions]))
        avg_nov = float(np.mean([d["pyramid"]["features"]["novelty"] for d in decompositions]))
        avg_ld = float(np.mean([d["epa"]["logic_depth"] for d in decompositions]))
        avg_res = float(np.mean([d["epa"]["resonance"] for d in decompositions]))
        return {"status": "completed", "batches": n_batches, "decompositions": decompositions,
                "aggregate": {"avg_coverage": avg_cov, "avg_novelty": avg_nov, "avg_logic_depth": avg_ld, "avg_resonance": avg_res}}

    def _phase2_graph_propagation(self, tags_data):
        if not self.store or not tags_data:
            return {"status": "skipped", "reason": "no data"}
        self.graph.load_from_store(self.store, self.namespace)
        if not self.graph.cooc:
            return {"status": "skipped", "reason": "no co-occurrence graph"}
        sorted_tags = sorted(tags_data, key=lambda t: t.get("id", 0))
        seed_ids = [t["id"] for t in sorted_tags[:5] if "id" in t]
        if not seed_ids:
            return {"status": "skipped", "reason": "no seed nodes"}
        spike = self.graph.propagate(seed_ids)
        tag_id_to_name = {t["id"]: t["name"] for t in tags_data if "id" in t}
        emergent_names = [{"name": tag_id_to_name.get(nid, f"tag_{nid}"), "activation": spike["activations"].get(nid, 0)} for nid in spike["emergent_nodes"]]
        return {"status": "completed", "emergent_tags": emergent_names, "seed_ids": seed_ids, "total_activated": len(spike["activations"])}

    def _phase3_artifact_generation(self, phase1, phase2, tags_data, candidate_names):
        artifacts = []
        if phase1.get("status") == "completed":
            for dec in phase1.get("decompositions", []):
                implicit = self.consolidator.generate_implicit_tags(dec["pyramid"], tags_data, candidate_names)
                for tag in implicit:
                    if tag["confidence"] > 0.3:
                        artifacts.append({
                            "id": f"implicit_{hashlib.md5(tag['name'].encode()).hexdigest()[:8]}",
                            "type": "implicit_tag",
                            "content": f"## Deep Dream Concept\nConcept: {tag['name']}\nConfidence: {tag['confidence']:.2f}\nTag: 梦境概念, {tag['name']}\n",
                            "tags": ["梦境概念", tag["name"]],
                            "confidence": tag["confidence"], "importance": tag["confidence"] * 0.8,
                            "category": "dream_concept", "meta": {"novelty": tag.get("novelty", 0)},
                        })
        if phase2.get("status") == "completed":
            for e in phase2.get("emergent_tags", [])[:10]:
                if e["activation"] > 0.1:
                    artifacts.append({
                        "id": f"emergent_{hashlib.md5(e['name'].encode()).hexdigest()[:8]}",
                        "type": "emergent_association",
                        "content": f"## Deep Dream Association\nTag: {e['name']}\nActivation: {e['activation']:.3f}\nTag: 梦境关联, {e['name']}\n",
                        "tags": ["梦境关联", e["name"]],
                        "confidence": min(0.8, e["activation"]), "importance": min(0.5, e["activation"] * 0.5),
                        "category": "dream_association", "meta": {"activation": e["activation"]},
                    })
        return {"artifacts": artifacts}

    def _memories_to_vectors(self, memories):
        if not memories:
            return None
        if self.embedder:
            try:
                texts = [m.get("content", "") for m in memories]
                vectors = self.embedder.embed_batch(texts)
                if vectors and len(vectors) > 0:
                    return np.array(vectors, dtype=np.float32)
            except Exception:
                pass
        vecs = []
        conn = self.store._get_conn()
        for m in memories:
            cur = conn.execute("SELECT vector FROM memories WHERE id=?", (m["id"],))
            row = cur.fetchone()
            if row and row["vector"] and len(row["vector"]) > 0:
                try:
                    vecs.append(np.frombuffer(row["vector"], dtype=np.float32))
                except Exception:
                    pass
        return np.array(vecs) if vecs else None
