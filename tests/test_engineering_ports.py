"""Tests for VCP engineering ports: SQLiteStore, ConfigWatcher"""
import sys, os, json, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_memory.sqlite_store import SQLiteStore
from agent_memory.config_watcher import ConfigWatcher


class TestSQLiteStore:
    def test_init(self):
        tmp = tempfile.mktemp(suffix=".db")
        s = SQLiteStore(tmp)
        assert os.path.exists(tmp)

    def test_tag_extraction(self):
        s = SQLiteStore(":memory:")
        content = "这是记忆内容\nTag: 机器学习, 深度学习\nTag: NLP\n"
        tags = s.extract_tags_from_content(content)
        assert "机器学习" in tags
        assert "深度学习" in tags
        assert "NLP" in tags

    def test_tag_extraction_chinese_label(self):
        s = SQLiteStore(":memory:")
        content = "内容\n标签：记忆系统, RAG\n"
        tags = s.extract_tags_from_content(content)
        assert "记忆系统" in tags
        assert "RAG" in tags

    def test_add_and_get_tags(self):
        s = SQLiteStore(":memory:")
        s.upsert_memory("mem1", "内容\nTag: AI, ML", namespace="test")
        s.add_tags_to_memory("mem1", ["AI", "ML"], namespace="test")
        tags = s.get_memory_tags("mem1")
        assert "AI" in tags
        assert "ML" in tags

    def test_cooccurrence(self):
        s = SQLiteStore(":memory:")
        s.upsert_memory("m1", "内容", namespace="test")
        s.upsert_memory("m2", "内容", namespace="test")
        s.add_tags_to_memory("m1", ["AI", "ML", "NLP"], namespace="test")
        s.add_tags_to_memory("m2", ["AI", "ML", "Python"], namespace="test")
        # AI 应该与 ML 高度共现
        cooc = s.get_cooccurrence("AI", namespace="test")
        names = [c[0] for c in cooc]
        assert "ML" in names
        assert names[0] == "ML"  # 最高权重

    def test_rebuild_cooccurrence(self):
        s = SQLiteStore(":memory:")
        s.upsert_memory("m1", "内容", namespace="test")
        s.add_tags_to_memory("m1", ["A", "B"], namespace="test")
        s.rebuild_cooccurrence()
        cooc = s.get_cooccurrence("A", namespace="test")
        assert len(cooc) >= 1

    def test_upsert_and_get_memory(self):
        s = SQLiteStore(":memory:")
        s.upsert_memory("mem1", "测试内容", namespace="ns1", category="test", importance=0.8)
        m = s.get_memory("mem1")
        assert m is not None
        assert m["content"] == "测试内容"
        assert m["importance"] == 0.8

    def test_list_memories_by_importance(self):
        s = SQLiteStore(":memory:")
        s.upsert_memory("m1", "低重要", namespace="ns", importance=0.1)
        s.upsert_memory("m2", "高重要", namespace="ns", importance=0.9)
        high = s.list_memories(namespace="ns", min_importance=0.5)
        assert len(high) == 1
        assert high[0]["id"] == "m2"

    def test_kv_store(self):
        s = SQLiteStore(":memory:")
        s.kv_set("test_key", {"nested": True, "value": 42})
        val = s.kv_get("test_key")
        assert val == {"nested": True, "value": 42}
        assert s.kv_get("nonexistent", "fallback") == "fallback"

    def test_stats(self):
        s = SQLiteStore(":memory:")
        s.upsert_memory("m1", "内容", namespace="ns")
        s.add_tags_to_memory("m1", ["A", "B"], namespace="ns")
        stats = s.stats("ns")
        assert stats["memories"] >= 1
        assert stats["tags"] >= 2


class TestConfigWatcher:
    def test_load_empty(self):
        cw = ConfigWatcher("/nonexistent/path/rag_params.json")
        assert cw.load() == {}

    def test_load_valid(self):
        tmp = tempfile.mktemp(suffix=".json")
        with open(tmp, "w") as f:
            json.dump({"key": "value"}, f)
        cw = ConfigWatcher(tmp)
        data = cw.load()
        assert data == {"key": "value"}

    def test_callback_on_change(self):
        tmp = tempfile.mktemp(suffix=".json")
        with open(tmp, "w") as f:
            json.dump({"v": 1}, f)
        results = []

        def cb(data):
            results.append(data)

        cw = ConfigWatcher(tmp, callback=cb)
        cw.start()
        time.sleep(0.5)

        # Change file
        with open(tmp, "w") as f:
            json.dump({"v": 2}, f)
        time.sleep(3)  # Wait for poll
        cw.stop()

        assert len(results) >= 1
        assert results[-1].get("v") == 2
