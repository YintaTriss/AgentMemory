"""Tests for new VCP-aligned modules — fixed."""
import pytest
import os
import tempfile
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_memory.fuzzy_search import fuzzy_search, prefix_search, similarity
from agent_memory.reranker import rerank, tokenize_simple
from agent_memory.watcher import MemoryWatcher


class TestFuzzySearch:
    def test_basic_fuzzy(self):
        candidates = ["记忆系统架构", "嵌入模型测试", "VCP配置笔记"]
        result = fuzzy_search("记忆系统", candidates, limit=5, score_cutoff=20)
        assert len(result) >= 1
        texts = [r[0] for r in result]
        assert "记忆系统架构" in texts

    def test_fuzzy_with_ids(self):
        from agent_memory.fuzzy_search import fuzzy_search_with_ids
        items = [("记忆系统", "id1"), ("嵌入模型", "id2"), ("VCP配置", "id3")]
        result = fuzzy_search_with_ids("嵌入", items, limit=3)
        assert len(result) >= 1
        assert result[0][2] == "id2"

    def test_prefix_search(self):
        candidates = ["记忆系统", "记录用户偏好", "测试", "项目计划"]
        result = prefix_search("记", candidates, limit=5)
        assert len(result) >= 2
        assert result[0][0] == "记忆系统"
        assert result[1][0] == "记录用户偏好"

    def test_empty_inputs(self):
        assert fuzzy_search("", ["a", "b"]) == []
        assert fuzzy_search("test", []) == []
        assert prefix_search("", ["a"]) == []

    def test_similarity(self):
        s = similarity("VCP配置", "VCP配置指南")
        assert s > 50.0
        s2 = similarity("记忆系统", "今天天气")
        assert s2 < s


class TestReranker:
    def test_basic_rerank(self):
        docs = [
            {"content": "记忆系统支持向量搜索", "id": "a"},
            {"content": "嵌入模型加载失败时的降级策略", "id": "b"},
            {"content": "今天天气不错", "id": "c"},
        ]
        ranked = rerank("嵌入模型降级", docs, text_field="content")
        assert len(ranked) == 3
        # 最相关的应该在前面
        assert ranked[0]["id"] in ("a", "b")

    def test_rerank_empty(self):
        assert rerank("test", []) == []
        assert rerank("", [{"content": "a"}]) != []

    def test_rerank_scores_in_01_range(self):
        """分数应在 0-1 之间"""
        docs = [
            {"content": "嵌入模型降级策略文档"},
            {"content": "今天天气"},
            {"content": "AAA"},
        ]
        ranked = rerank("嵌入模型", docs)
        scores = [d["_rerank_score"] for d in ranked]
        assert all(0 <= s <= 1 for s in scores), f"Should be 0-1: {scores}"

    def test_rerank_relevance_over_irrelevance(self):
        """相关内容得分应低于不相关内容"""
        docs = [
            {"content": "今天天气不错，明天会更好", "id": "irrelevant"},
            {"content": "嵌入模型加载失败的降级策略文档", "id": "relevant"},
            {"content": "嵌入", "id": "partial"},
        ]
        ranked = rerank("嵌入模型", docs)
        ids = [d["id"] for d in ranked]
        # "relevant" 应该排在 "irrelevant" 前面
        assert ids.index("relevant") < ids.index("irrelevant")

    def test_tokenize_simple(self):
        """jieba 分词测试"""
        tokens = tokenize_simple("嵌入模型故障")
        assert "嵌入" in tokens
        assert "模型" in tokens
        assert "故障" in tokens
        tokens2 = tokenize_simple("load failed")
        assert "load" in tokens2
        assert "failed" in tokens2


class TestFileWatcher:
    def test_watcher_detects_file_creation(self):
        tmp = tempfile.mkdtemp()
        captured = []
        watcher = MemoryWatcher(tmp, callback=lambda paths: captured.extend(paths), debounce_ms=300)
        watcher.start()
        time.sleep(0.5)
        with open(os.path.join(tmp, "test_watcher.md"), "w") as f:
            f.write("watcher test content")
        time.sleep(1.5)
        watcher.stop()
        assert any("test_watcher" in p for p in captured)

    def test_watcher_detects_file_modification(self):
        tmp = tempfile.mkdtemp()
        captured = []
        f_path = os.path.join(tmp, "test_mod.md")
        with open(f_path, "w") as f:
            f.write("original")
        watcher = MemoryWatcher(tmp, callback=lambda paths: captured.extend(paths), debounce_ms=300)
        watcher.start()
        time.sleep(1.0)
        with open(f_path, "w") as f:
            f.write("modified")
        time.sleep(1.5)
        watcher.stop()
        assert any("test_mod" in p for p in captured)

    def test_watcher_ignores_non_memory_files(self):
        tmp = tempfile.mkdtemp()
        captured = []
        watcher = MemoryWatcher(tmp, callback=lambda paths: captured.extend(paths), debounce_ms=300)
        watcher.start()
        time.sleep(0.5)
        with open(os.path.join(tmp, "test.py"), "w") as f:
            f.write("code")
        with open(os.path.join(tmp, "test.md"), "w") as f:
            f.write("memory")
        time.sleep(1.5)
        watcher.stop()
        assert not any("test.py" in p for p in captured)
        assert any("test.md" in p for p in captured)

    def test_watcher_is_alive_state(self):
        tmp = tempfile.mkdtemp()
        watcher = MemoryWatcher(tmp, callback=lambda p: None, debounce_ms=1000)
        assert not watcher.is_alive
        watcher.start()
        time.sleep(0.5)
        assert watcher.is_alive
        watcher.stop()
        assert not watcher.is_alive
