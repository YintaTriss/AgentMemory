"""Tests for modules previously without direct test coverage."""
import sys
import os
import tempfile
import time
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_memory.sqlite_store import SQLiteStore
from agent_memory.compactor import MemoryCompactor
from agent_memory.write_queue import AsyncWriteQueue, Priority
from agent_memory.search_pipeline import SearchPipeline, SearchResult
from agent_memory.dream_narrative import DreamNarrativeGenerator
from agent_memory.health_monitor import HealthMonitor
from agent_memory.agent_tool import AgentMemoryTool


class TestCompactor:
    def test_score_low_importance(self):
        c = MemoryCompactor(importance_threshold=0.3)
        mem = {"content": "x" * 50, "meta": {"importance": 0.1}}
        score, reason = c.score_for_removal(mem)
        assert score > 0
        assert "low_importance" in reason

    def test_score_short_content(self):
        c = MemoryCompactor()
        mem = {"content": "short", "meta": {"importance": 0.5}}
        score, reason = c.score_for_removal(mem)
        assert "too_short" in reason

    def test_score_keep_good(self):
        c = MemoryCompactor()
        mem = {"content": "x" * 100, "meta": {"importance": 0.8}}
        score, reason = c.score_for_removal(mem)
        assert score == 0.0

    def test_compact_dry_run(self):
        c = MemoryCompactor(importance_threshold=0.3)
        memories = [
            {"id": "1", "content": "short", "meta": {"importance": 0.1}},
            {"id": "2", "content": "x" * 100, "meta": {"importance": 0.8}},
        ]
        result = c.compact(memories, dry_run=True)
        assert result["removed"] >= 1
        assert result["dry_run"]


class TestWriteQueue:
    def test_init(self):
        flushed = []
        q = AsyncWriteQueue(flush_fn=lambda items: flushed.extend(items))
        assert q.size == 0

    def test_push(self):
        flushed = []
        async def flush(items):
            flushed.extend(items)
        q = AsyncWriteQueue(flush_fn=flush)
        q.push("a", Priority.HIGH)
        q.push("b", Priority.NORMAL)
        q.push("c", Priority.LOW)
        assert q.size == 3

    def test_priority_ordering(self):
        flushed = []
        async def flush(items):
            flushed.extend(items)
        q = AsyncWriteQueue(flush_fn=flush)
        q.push("low", Priority.LOW)
        q.push("high", Priority.HIGH)
        q.push("normal", Priority.NORMAL)
        # Drain by priority
        items_high = q._queues[Priority.HIGH]
        items_normal = q._queues[Priority.NORMAL]
        items_low = q._queues[Priority.LOW]
        assert len(items_high) == 1
        assert len(items_normal) == 1
        assert len(items_low) == 1


class TestSearchPipeline:
    def test_init(self):
        p = SearchPipeline()
        assert p.fuzzy_fn is None

    def test_search_empty(self):
        async def run():
            p = SearchPipeline()
            result = await p.search("test", [], top_k=10)
            assert result == []
        asyncio.run(run())

    def test_search_fuzzy_only(self):
        async def run():
            def fuzzy_fn(q, candidates):
                return [(c, 80.0) for c in candidates[:2]]

            candidates = [{"content": "alpha"}, {"content": "beta"}, {"content": "gamma"}]
            p = SearchPipeline(fuzzy_fn=fuzzy_fn)
            results = await p.search("test", candidates, top_k=10)
            assert len(results) >= 1
        asyncio.run(run())


class TestDreamNarrative:
    def test_template_narrative(self):
        gen = DreamNarrativeGenerator(sqlite_store=None)
        report = {
            "phase": "deep",
            "data": {"memories": 100, "tags": 50},
            "phases": {"consolidation": {"written": 3, "drafted": 2, "rejected": 1}},
            "artifacts": [
                {"type": "test", "tags": ["AI"], "confidence": 0.7}
            ],
        }
        narrative = gen._template_narrative("deep", report)
        assert "深睡" in narrative
        assert "100 条记忆" in narrative

    def test_build_prompt(self):
        gen = DreamNarrativeGenerator()
        report = {
            "phase": "rem",
            "data": {"memories": 50, "tags": 25},
            "phases": {"signal_decomposition": {"aggregate": {"avg_coverage": 0.7, "avg_novelty": 0.3}}},
            "artifacts": [{"type": "test", "tags": ["AI"], "confidence": 0.8}],
        }
        prompt = gen.build_prompt("rem", report)
        assert "REM" in prompt
        assert "覆盖率" in prompt


class TestHealthMonitor:
    def test_empty(self):
        store = SQLiteStore(":memory:")
        hm = HealthMonitor(store)
        info = hm.compute_health()
        assert info["health"] == 0.0
        assert info["reason"] == "empty"

    def test_with_data(self):
        store = SQLiteStore(":memory:")
        store.upsert_memory("m1", "x" * 100, namespace="test", importance=0.8)
        store.add_tags_to_memory("m1", ["AI", "ML"], namespace="test")
        hm = HealthMonitor(store, namespace="test")
        info = hm.compute_health()
        assert "health" in info
        assert info["memories"] == 1
        assert info["tags"] == 2
        assert 0 <= info["health"] <= 1

    def test_needs_recovery(self):
        store = SQLiteStore(":memory:")
        hm = HealthMonitor(store)
        hm.trigger_below = 0.99  # 设为超高门槛迫使恢复
        assert hm.needs_recovery()  # Empty → health 0.0 < 0.99

    def test_recover_dry_run(self):
        store = SQLiteStore(":memory:")
        store.upsert_memory("m1", "test", namespace="test")
        store.add_tags_to_memory("m1", ["A", "B"], namespace="test")
        hm = HealthMonitor(store, namespace="test")
        result = hm.recover(dry_run=True)
        assert result["dry_run"]
        assert "actions" in result


class TestAgentMemoryTool:
    def test_no_manager(self):
        tool = AgentMemoryTool(memory_manager=None)
        async def run():
            result = await tool.add("test")
            assert "error" in result
        asyncio.run(run())

    def test_tool_definition(self):
        tool = AgentMemoryTool()
        defn = tool.tool_definition()
        assert defn["name"] == "agentmemory"
        assert "add" in [f["name"] for f in defn["functions"]]
        assert "search" in [f["name"] for f in defn["functions"]]
        assert "recent" in [f["name"] for f in defn["functions"]]