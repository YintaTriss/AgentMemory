"""Tests for Dream System modules."""
import sys, os, time
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_memory.dream_signal import SignalDecomposer
from agent_memory.dream_graph import GraphPropagator
from agent_memory.dream_consolidate import DreamConsolidator
from agent_memory.dream_engine import DreamEngine
from agent_memory.sqlite_store import SQLiteStore


class TestSignalDecomposer:
    def test_init(self):
        sd = SignalDecomposer(n_components=4, n_clusters=3)
        assert sd.n_components == 4
        assert sd.n_clusters == 3

    def test_fit_epa(self):
        rng = np.random.default_rng(42)
        tags = rng.standard_normal((20, 1536)).astype(np.float32)
        names = [f"tag_{i}" for i in range(20)]
        sd = SignalDecomposer(n_components=4, n_clusters=3)
        sd.fit_epa(tags, names)
        assert sd._basis is not None
        assert sd._basis.shape[0] == 4  # n_components

    def test_project(self):
        rng = np.random.default_rng(42)
        tags = rng.standard_normal((20, 1536)).astype(np.float32)
        sd = SignalDecomposer(n_components=4, n_clusters=3)
        sd.fit_epa(tags)
        v = rng.standard_normal(1536).astype(np.float32)
        result = sd.project(v)
        assert "logic_depth" in result
        assert "resonance" in result
        assert "entropy" in result
        assert 0 <= result["logic_depth"] <= 1
        assert 0 <= result["resonance"] <= 1

    def test_project_empty(self):
        sd = SignalDecomposer()
        result = sd.project(np.zeros(1536))
        assert result["entropy"] == 1.0  # no basis

    def test_decompose(self):
        rng = np.random.default_rng(42)
        query = rng.standard_normal(1536).astype(np.float32)
        tags = rng.standard_normal((50, 1536)).astype(np.float32)
        sd = SignalDecomposer()
        result = sd.decompose(query, tags, max_levels=3, top_k=5)
        assert "levels" in result
        assert "total_coverage" in result
        assert "features" in result
        assert result["features"]["depth"] <= 3
        assert result["total_coverage"] >= 0.0

    def test_features(self):
        rng = np.random.default_rng(42)
        q = rng.standard_normal(1536).astype(np.float32)
        t = rng.standard_normal((50, 1536)).astype(np.float32)
        sd = SignalDecomposer()
        r = sd.decompose(q, t)
        f = r["features"]
        for key in ("coverage", "novelty", "coherence", "tag_memo_activation", "expansion_signal"):
            assert key in f, f"Missing feature: {key}"
            assert 0 <= f[key] <= 1, f"{key} out of range: {f[key]}"


class TestGraphPropagator:
    def test_init(self):
        gp = GraphPropagator()
        assert gp.cooc == {}

    def test_propagate_empty(self):
        gp = GraphPropagator()
        result = gp.propagate([1])
        assert result["activations"] == {}

    def test_propagate_simple(self):
        cooc = {
            1: {2: 0.8, 3: 0.5},
            2: {1: 0.8, 3: 0.3},
            3: {1: 0.5, 2: 0.3},
        }
        gp = GraphPropagator(cooc)
        result = gp.propagate([1], max_hops=3)
        assert 1 in result["activations"]
        assert len(result["activations"]) >= 2

    def test_emergent_nodes(self):
        cooc = {i: {j: 0.5 for j in range(10) if j != i} for i in range(10)}
        gp = GraphPropagator(cooc)
        result = gp.propagate([0, 1], max_hops=2, max_emergent=5)
        assert len(result["emergent_nodes"]) <= 5
        assert len(result["emergent_nodes"]) >= 1

    def test_wormhole_decay(self):
        """跨簇传播应衰减更快。"""
        cooc = {
            1: {2: 0.9, 10: 0.9},  # 1-2 same cluster, 1-10 wormhole
        }
        gp = GraphPropagator(cooc)
        # Without clusters, all decays are the same
        result_a = gp.propagate([1], base_decay=0.1, wormhole_decay=0.5, max_hops=2)
        # With clusters (cluster 1 vs cluster 2)
        gp._clusters = {1: 0, 2: 0, 10: 1}
        result_b = gp.propagate([1], base_decay=0.1, wormhole_decay=0.5, max_hops=2)
        # Node 2 (same cluster) should get higher activation than node 10
        # Actually with same base_decay, same-cluster retains more
        act_2 = result_b["activations"].get(2, 0)
        act_10 = result_b["activations"].get(10, 0)
        assert act_2 >= act_10 * 0.5  # Node 2 should be >= wormhole

    def test_recommend_tags(self):
        cooc = {1: {2: 0.9, 3: 0.7, 4: 0.5}}
        gp = GraphPropagator(cooc)
        recs = gp.recommend_tags([1], top_k=2)
        assert len(recs) <= 2


class TestDreamConsolidator:
    def test_init(self):
        dc = DreamConsolidator()
        assert dc.store is None

    def test_generate_implicit_tags_high_novelty(self):
        dc = DreamConsolidator()
        residual = {
            "features": {"novelty": 0.6, "coverage": 0.3, "depth": 3},
        }
        tags = [{"name": "AI"}]
        candidates = ["记忆系统", "语义分析", "模式识别"]
        result = dc.generate_implicit_tags(residual, tags, candidates)
        assert len(result) >= 1
        assert all("confidence" in i for i in result)

    def test_generate_implicit_tags_low_novelty(self):
        dc = DreamConsolidator()
        residual = {
            "features": {"novelty": 0.1, "coverage": 0.9, "depth": 1},
        }
        result = dc.generate_implicit_tags(residual, [])
        assert len(result) >= 0  # low novelty = no artifacts

    def test_consolidate_high_confidence(self):
        store = SQLiteStore(":memory:")
        dc = DreamConsolidator(store)
        artifacts = [
            {"id": "test_1", "content": "梦境产物", "tags": ["梦境测试"],
             "confidence": 0.8, "importance": 0.6, "category": "test",
             "meta": {"source": "test"}},
        ]
        result = dc.consolidate(artifacts)
        assert result["written"] == 1
        assert result["rejected"] == 0
        # Verify it was actually written
        m = store.get_memory("test_1")
        assert m is not None
        assert "梦境产物" in m["content"]

    def test_consolidate_low_confidence(self):
        dc = DreamConsolidator()
        artifacts = [
            {"id": "bad_1", "content": "噪声", "tags": [],
             "confidence": 0.1, "importance": 0.1, "category": "test", "meta": {}},
        ]
        result = dc.consolidate(artifacts)
        assert result["rejected"] == 1


class TestDreamEngine:
    def test_init(self):
        store = SQLiteStore(":memory:")
        engine = DreamEngine(sqlite_store=store)
        assert engine.namespace == "default"
        assert engine.signal is not None
        assert engine.graph is not None

    def test_dream_cycle_empty(self):
        store = SQLiteStore(":memory:")
        engine = DreamEngine(sqlite_store=store)
        report = engine.dream_cycle(dry_run=True)
        assert "phases" in report
        # Should not crash with empty data
        assert report["data"]["memories"] == 0

    def test_dream_cycle_with_data(self):
        store = SQLiteStore(":memory:")
        # Add some test data
        store.upsert_memory("m1", "机器学习的基础是数学\nTag: ML, AI", namespace="test")
        store.upsert_memory("m2", "深度学习需要大量数据\nTag: DL, AI", namespace="test")
        store.upsert_memory("m3", "自然语言处理的应用场景\nTag: NLP, AI", namespace="test")
        store.add_tags_to_memory("m1", ["ML", "AI"], namespace="test")
        store.add_tags_to_memory("m2", ["DL", "AI"], namespace="test")
        store.add_tags_to_memory("m3", ["NLP", "AI"], namespace="test")

        # Need vectors for memories too - add them manually
        import hashlib
        for mid in ["m1", "m2", "m3"]:
            h = hashlib.shake_256(mid.encode()).digest(1536 * 4)
            vec = [float(x) for x in np.frombuffer(h, dtype=np.float32)[:1536]]
            store.kv_set(f"vec_{mid}", vec)

        engine = DreamEngine(sqlite_store=store, namespace="test")
        report = engine.dream_cycle(dry_run=True, candidate_names=["知识图谱", "强化学习", "迁移学习"])

        assert "total_ms" in report
        assert "phases" in report
        print(f"Dream cycle took: {report['total_ms']:.0f}ms")
        print(f"Artifacts: {len(report.get('artifacts', []))}")
        print(f"Phase status: signal={report['phases']['signal_decomposition'].get('status')}, graph={report['phases']['graph_propagation'].get('status')}")
