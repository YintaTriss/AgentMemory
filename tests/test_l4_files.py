"""
L4 文件层单元测试
测试 FilePersistStore
"""
import json
import pytest
from pathlib import Path
from datetime import datetime

from src.L4_file_persist import FilePersistStore, FactEntry, DiaryEntry


class TestFilePersistStore:
    """FilePersistStore 单元测试"""

    def test_store_fact_creates_files(self, tmp_memory_dir):
        """store_fact 后文件生成"""
        store = FilePersistStore(str(tmp_memory_dir))
        
        result = store.store_fact(
            content="测试记忆条目",
            metadata={"category": "test", "importance": 0.9}
        )
        
        assert result is True, "store_fact 应该返回 True"
        
        # 验证文件生成 - 检查 get_all_facts
        facts = store.get_all_facts()
        assert len(facts) > 0, "应该至少有一条记忆"

    def test_get_all_facts_returns_all(self, tmp_memory_dir):
        """get_all_facts 返回所有事实"""
        store = FilePersistStore(str(tmp_memory_dir))
        
        store.store_fact("记忆1", {"importance": 0.5})
        store.store_fact("记忆2", {"importance": 0.6})
        store.store_fact("记忆3", {"importance": 0.7})
        
        facts = store.get_all_facts()
        
        assert len(facts) >= 3, "应该返回至少3条记忆"

    def test_store_fact_with_metadata(self, tmp_memory_dir):
        """存储带元数据的事实"""
        store = FilePersistStore(str(tmp_memory_dir))
        
        metadata = {
            "importance": 0.8,
            "tags": ["tag1", "tag2"],
            "fact_type": "preference"
        }
        result = store.store_fact("测试内容", metadata)
        
        assert result is True
        
        facts = store.get_all_facts()
        assert any(f.get("fact_type") == "preference" or 
                   f.get("metadata", {}).get("fact_type") == "preference" 
                   for f in facts)

    def test_store_fact_with_unicode(self, tmp_memory_dir):
        """存储包含 Unicode 的内容"""
        store = FilePersistStore(str(tmp_memory_dir))
        
        result = store.store_fact(
            content="中文测试内容 🎉 Emoji 测试",
            metadata={"importance": 0.9}
        )
        
        assert result is True
        
        facts = store.get_all_facts()
        assert any("中文" in str(f.get("content", "")) for f in facts)

    def test_get_recent_returns_n_days(self, tmp_memory_dir):
        """获取最近 N 天日记"""
        store = FilePersistStore(str(tmp_memory_dir))
        
        store.store_fact("今天的记录", {"importance": 0.5})
        
        recent = store.get_recent(3)
        
        assert isinstance(recent, list)

    def test_export_json_format(self, tmp_memory_dir):
        """导出为 JSON 格式"""
        store = FilePersistStore(str(tmp_memory_dir))
        
        store.store_fact("测试导出", {"importance": 0.8})
        
        exported = store.export("json")
        
        assert exported is not None
        assert isinstance(exported, str)


class TestDiaryEntry:
    """DiaryEntry 数据类测试"""

    def test_diary_entry_to_markdown(self):
        """DiaryEntry 转换为 Markdown"""
        entry = DiaryEntry(
            time="10:30",
            category="test",
            content="测试日记条目"
        )
        
        md = entry.to_markdown()
        
        assert "10:30" in md
        assert "test" in md
        assert "测试日记条目" in md

    def test_diary_entry_to_dict(self):
        """DiaryEntry 转换为字典"""
        entry = DiaryEntry(
            time="10:30",
            category="test",
            content="测试条目",
            importance=0.8
        )
        
        d = entry.to_dict()
        
        assert d["time"] == "10:30"
        assert d["category"] == "test"
        assert d["importance"] == 0.8


class TestFactEntry:
    """FactEntry 数据类测试"""

    def test_fact_entry_to_dict(self):
        """FactEntry 转换为字典"""
        entry = FactEntry(
            fact="测试事实",
            category="test",
            importance=0.8,
            tags=["tag1", "tag2"]
        )
        
        d = entry.to_dict()
        
        assert d["fact"] == "测试事实"
        assert d["category"] == "test"
        assert d["importance"] == 0.8
        assert d["tags"] == ["tag1", "tag2"]

    def test_fact_entry_default_values(self):
        """FactEntry 默认值"""
        entry = FactEntry(fact="测试", category="general", importance=0.5)
        
        assert entry.created_at is not None
        assert entry.tags == []
