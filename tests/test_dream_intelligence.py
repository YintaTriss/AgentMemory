"""
2026-07-15 方向 5 + 6: 梦境调度智能 + 梦境产物可追溯

测试覆盖:
- DreamPhaseSelector 各种信号下的决策
- DreamProvenanceTracker 记录 / 查询 / 追溯
- MemoryManager.auto_dream / explain_artifact / record_dream_provenance 集成
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agent_memory.dream_phase_selector import (  # noqa: E402
    DreamPhaseSelector,
    DreamPhaseDecision,
)
from agent_memory.dream_provenance import (  # noqa: E402
    DreamProvenance,
    DreamProvenanceTracker,
)


# ========== 方向 5: DreamPhaseSelector ==========

def _fake_store(mem_count=100, tag_count=20, last_rem_iso=None, tension=0.0):
    """构造 SQLiteStore mock"""
    store = MagicMock()
    store.list_memories = MagicMock(return_value=[{"id": f"m{i}"} for i in range(mem_count)])
    store.list_tags = MagicMock(return_value=[{"id": f"t{i}"} for i in range(tag_count)])
    store.kv_get = MagicMock(side_effect=lambda k: last_rem_iso if "rem" in k else str(tension))
    return store


def test_phase_selector_force_light():
    selector = DreamPhaseSelector(store=None)
    d = selector.select(force="light")
    assert d.phase == "light"
    assert d.reason == "forced by caller"
    assert d.priority == 0


def test_phase_selector_force_rem():
    selector = DreamPhaseSelector(store=None)
    d = selector.select(force="rem")
    assert d.phase == "rem"


def test_phase_selector_first_run_chooses_rem():
    """首次执行应选 REM(建立跨簇虫洞)"""
    store = _fake_store(mem_count=10, tag_count=5, last_rem_iso=None)
    selector = DreamPhaseSelector(store=store)
    d = selector.select()
    assert d.phase == "rem"
    assert "从未执行过" in d.reason or "REM" in d.reason
    assert d.priority == 1


def test_phase_selector_rem_due():
    """超过 rem_days_interval 天没跑 REM → 选 rem"""
    old_rem = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    store = _fake_store(mem_count=10, tag_count=5, last_rem_iso=old_rem)
    selector = DreamPhaseSelector(store=store, rem_days_interval=7)
    d = selector.select()
    assert d.phase == "rem"


def test_phase_selector_high_tension_chooses_deep():
    """涌现张力高 → deep"""
    store = _fake_store(mem_count=100, tag_count=20, last_rem_iso=datetime.now(timezone.utc).isoformat(), tension=0.9)
    selector = DreamPhaseSelector(store=store, high_tension_threshold=0.7)
    d = selector.select()
    assert d.phase == "deep"
    assert "张力" in d.reason


def test_phase_selector_high_tag_density_chooses_deep():
    """标签密度高 → deep"""
    store = _fake_store(mem_count=10, tag_count=10, last_rem_iso=datetime.now(timezone.utc).isoformat())
    # density = 10/10 = 1.0
    selector = DreamPhaseSelector(store=store, deep_tag_density=0.5)
    d = selector.select()
    assert d.phase == "deep"


def test_phase_selector_too_many_memories_chooses_light():
    """记忆过多 → light 清理"""
    store = _fake_store(mem_count=600, tag_count=50, last_rem_iso=datetime.now(timezone.utc).isoformat())
    selector = DreamPhaseSelector(store=store, light_memory_threshold=500)
    d = selector.select()
    assert d.phase == "light"


def test_phase_selector_healthy_system_skips():
    """健康系统 → skip"""
    store = _fake_store(
        mem_count=100, tag_count=20,
        last_rem_iso=datetime.now(timezone.utc).isoformat(),
        tension=0.1,
    )
    # density = 20/100 = 0.2 (低于 0.5 阈值)
    selector = DreamPhaseSelector(store=store)
    d = selector.select()
    assert d.phase == "skip"
    assert "无需梦境" in d.reason


def test_phase_selector_priority_rem_over_deep():
    """rem 比 deep 优先"""
    old_rem = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    store = _fake_store(
        mem_count=1000, tag_count=500,
        last_rem_iso=old_rem, tension=0.9,
    )
    selector = DreamPhaseSelector(store=store)
    d = selector.select()
    assert d.phase == "rem"  # rem 优先


def test_phase_selector_no_store_returns_signals_with_warning():
    """无 store 也能决策(回退)"""
    selector = DreamPhaseSelector(store=None)
    d = selector.select()
    # 无 store,信号全空,默认 skip
    assert d.phase == "skip"
    assert d.signals.get("_warning") == "no store, returning defaults"


def test_phase_selector_explain_output():
    selector = DreamPhaseSelector(store=None)
    d = selector.select(force="deep")
    text = selector.explain(d)
    assert "梦境阶段决策: deep" in text
    assert "理由:" in text
    assert "信号:" in text


# ========== 方向 6: DreamProvenanceTracker ==========

def test_provenance_record_basic():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "prov.jsonl")
        tracker = DreamProvenanceTracker(storage_path=path)
        prov = tracker.record(
            artifact_id="em_001",
            artifact_type="emergent_node",
            phase="rem",
            inputs=["01ABC", "01DEF"],
            method="spike_routing",
            confidence=0.85,
            explanation="测试涌现",
        )
        assert prov.artifact_id == "em_001"
        assert prov.confidence == 0.85
        assert tracker.count() == 1


def test_provenance_record_emergent_convenience():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "prov.jsonl")
        tracker = DreamProvenanceTracker(storage_path=path)
        prov = tracker.record_emergent(
            node_id="em_002",
            phase="deep",
            seed_memory_ids=["m1", "m2", "m3"],
            hops=2,
            confidence=0.7,
        )
        assert prov.method == "spike_routing"
        assert prov.parameters["hops"] == 2
        assert "3 个种子记忆" in prov.explanation


def test_provenance_record_association():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "prov.jsonl")
        tracker = DreamProvenanceTracker(storage_path=path)
        prov = tracker.record_association(
            assoc_id="as_001",
            phase="rem",
            tag_a=5,
            tag_b=12,
            strength=0.6,
        )
        assert prov.artifact_type == "association"
        assert "5 ↔ 12" in prov.explanation


def test_provenance_record_implicit_tag():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "prov.jsonl")
        tracker = DreamProvenanceTracker(storage_path=path)
        prov = tracker.record_implicit_tag(
            tag_id="it_001",
            phase="deep",
            source_memory_ids=["m1", "m2"],
            name="隐性主题",
        )
        assert prov.artifact_type == "implicit_tag"
        assert prov.parameters["name"] == "隐性主题"


def test_provenance_persistence():
    """记录后重新加载应能读到"""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "prov.jsonl")
        t1 = DreamProvenanceTracker(storage_path=path)
        t1.record("a1", "emergent_node", "rem", inputs=["x"])
        t1.record("a2", "association", "deep")

        # 重新加载
        t2 = DreamProvenanceTracker(storage_path=path)
        assert t2.count() == 2
        a1 = t2.get("a1")
        assert a1 is not None
        assert a1.artifact_type == "emergent_node"


def test_provenance_explain_includes_inputs():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "prov.jsonl")
        tracker = DreamProvenanceTracker(storage_path=path)
        tracker.record(
            artifact_id="em_x",
            artifact_type="emergent_node",
            phase="rem",
            inputs=["01A", "01B", "01C"],
            method="spike_routing",
            confidence=0.9,
            explanation="测试",
        )
        text = tracker.explain("em_x")
        assert "em_x" in text
        assert "emergent_node" in text
        assert "spike_routing" in text
        assert "01A" in text
        assert "置信度" in text


def test_provenance_explain_truncates_long_inputs():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "prov.jsonl")
        tracker = DreamProvenanceTracker(storage_path=path)
        tracker.record(
            artifact_id="em_long",
            artifact_type="emergent_node",
            phase="rem",
            inputs=[f"m{i}" for i in range(20)],
            method="graph",
        )
        text = tracker.explain("em_long")
        assert "(+15 more)" in text  # 5 显示 + 15 more


def test_provenance_explain_not_found():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "prov.jsonl")
        tracker = DreamProvenanceTracker(storage_path=path)
        text = tracker.explain("nonexistent")
        assert "未找到" in text


def test_provenance_trace_chain_returns_sorted_by_time():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "prov.jsonl")
        tracker = DreamProvenanceTracker(storage_path=path)
        # 根
        tracker.record("root", "narrative", "deep")
        # 中间
        tracker.record("mid", "emergent_node", "deep", parent_artifacts=["root"])
        # 当前
        tracker.record(
            "current", "association", "rem",
            parent_artifacts=["mid"],
        )

        chain = tracker.trace_chain("current")
        ids = [c.artifact_id for c in chain]
        assert ids.index("root") < ids.index("mid") < ids.index("current")


def test_provenance_trace_chain_avoids_cycles():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "prov.jsonl")
        tracker = DreamProvenanceTracker(storage_path=path)
        # 故意构造环
        tracker.record("a", "x", "deep", parent_artifacts=["b"])
        tracker.record("b", "x", "deep", parent_artifacts=["a"])

        chain = tracker.trace_chain("a")
        ids = [c.artifact_id for c in chain]
        assert len(ids) == 2  # 不应无限循环


def test_provenance_list_by_type():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "prov.jsonl")
        tracker = DreamProvenanceTracker(storage_path=path)
        tracker.record("e1", "emergent_node", "rem")
        tracker.record("e2", "emergent_node", "deep")
        tracker.record("a1", "association", "rem")

        nodes = tracker.list_by_type("emergent_node")
        assert len(nodes) == 2
        assocs = tracker.list_by_type("association")
        assert len(assocs) == 1


# ========== MemoryManager 集成 ==========

def test_memory_manager_record_dream_provenance():
    from agent_memory import MemoryManager

    with tempfile.TemporaryDirectory() as tmp:
        mm = MemoryManager.__new__(MemoryManager)
        mm._store_path = os.path.join(tmp, "test.db")

        result = mm.record_dream_provenance(
            artifact_id="em_test",
            artifact_type="emergent_node",
            phase="rem",
            inputs=["01A", "01B"],
            method="spike_routing",
            confidence=0.88,
            explanation="集成测试",
        )
        assert result["artifact_id"] == "em_test"
        assert result["confidence"] == 0.88

        # explain 能查到
        explanation = mm.explain_artifact("em_test")
        assert "em_test" in explanation
        assert "spike_routing" in explanation


def test_memory_manager_trace_artifact_chain():
    from agent_memory import MemoryManager

    with tempfile.TemporaryDirectory() as tmp:
        mm = MemoryManager.__new__(MemoryManager)
        mm._store_path = os.path.join(tmp, "test.db")

        mm.record_dream_provenance(
            artifact_id="root",
            artifact_type="narrative",
            phase="deep",
        )
        mm.record_dream_provenance(
            artifact_id="mid",
            artifact_type="emergent_node",
            phase="deep",
            parent_artifacts=["root"],
        )
        mm.record_dream_provenance(
            artifact_id="leaf",
            artifact_type="association",
            phase="rem",
            parent_artifacts=["mid"],
        )

        chain = mm.trace_artifact_chain("leaf")
        ids = [p["artifact_id"] for p in chain]
        assert ids == ["root", "mid", "leaf"]


def test_memory_manager_auto_dream_skip_when_healthy():
    """健康系统 auto_dream 返回 skip"""
    from agent_memory import MemoryManager

    with tempfile.TemporaryDirectory() as tmp:
        mm = MemoryManager.__new__(MemoryManager)
        mm._store_path = os.path.join(tmp, "test.db")

        # mock SQLiteStore
        with patch("agent_memory.sqlite_store.SQLiteStore") as MockStore:
            mock_store = MagicMock()
            mock_store.list_memories = MagicMock(return_value=[{"id": f"m{i}"} for i in range(10)])
            mock_store.list_tags = MagicMock(return_value=[])  # 0 tags → density 0
            mock_store.kv_get = MagicMock(return_value=datetime.now(timezone.utc).isoformat())
            MockStore.return_value = mock_store

            out = mm.auto_dream(force="skip")  # 强制 skip
            assert out["decision"].phase == "skip"
            assert "无需梦境" in out["decision"].reason


def test_memory_manager_auto_dream_with_force_runs_engine():
    """force=light 应触发 DreamEngine"""
    from agent_memory import MemoryManager

    with tempfile.TemporaryDirectory() as tmp:
        mm = MemoryManager.__new__(MemoryManager)
        mm._store_path = os.path.join(tmp, "test.db")

        with patch("agent_memory.sqlite_store.SQLiteStore") as MockStore:
            mock_store = MagicMock()
            mock_store.list_memories = MagicMock(return_value=[{"id": f"m{i}"} for i in range(10)])
            mock_store.list_tags = MagicMock(return_value=[])
            mock_store.kv_get = MagicMock(return_value=None)
            MockStore.return_value = mock_store

            # mock DreamEngine 避免真实执行
            with patch.object(MemoryManager, "_get_dream_engine") as mock_get_engine:
                mock_engine = MagicMock()
                mock_engine.dream_cycle = MagicMock(return_value={"phase": "light", "artifacts": []})
                mock_get_engine.return_value = mock_engine

                out = mm.auto_dream(force="light")
                assert out["decision"].phase == "light"
                mock_engine.dream_cycle.assert_called_once()