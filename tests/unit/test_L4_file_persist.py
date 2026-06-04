"""
L4_file_persist.py 单元测试
"""

import pytest
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../..", "src"))

from L4_file_persist import FilePersistStore, DailyMemory, SessionSummary


class TestDailyMemory:
    """DailyMemory 每日记忆测试"""
    
    def test_daily_memory_init(self, temp_dir):
        """测试每日记忆初始化"""
        from L4_file_persist import DailyMemory
        
        date_str = datetime.now().strftime("%Y-%m-%d")
        memory_path = os.path.join(temp_dir, "daily")
        
        memory = DailyMemory(base_path=memory_path, date=date_str)
        
        assert memory.date == date_str
        assert memory.base_path == memory_path
    
    def test_add_entry(self, temp_dir):
        """测试添加记忆条目"""
        from L4_file_persist import DailyMemory
        
        date_str = datetime.now().strftime("%Y-%m-%d")
        memory = DailyMemory(base_path=temp_dir, date=date_str)
        
        entry_id = memory.add_entry(
            content="测试记忆条目",
            metadata={"type": "fact"}
        )
        
        assert entry_id is not None
        assert memory.get_entry_count() == 1
    
    def test_get_entries(self, temp_dir):
        """测试获取记忆条目"""
        from L4_file_persist import DailyMemory
        
        date_str = datetime.now().strftime("%Y-%m-%d")
        memory = DailyMemory(base_path=temp_dir, date=date_str)
        
        memory.add_entry("内容1", {"index": 1})
        memory.add_entry("内容2", {"index": 2})
        memory.add_entry("内容3", {"index": 3})
        
        entries = memory.get_entries()
        
        assert len(entries) == 3
    
    def test_search_entries(self, temp_dir):
        """测试搜索记忆条目"""
        from L4_file_persist import DailyMemory
        
        date_str = datetime.now().strftime("%Y-%m-%d")
        memory = DailyMemory(base_path=temp_dir, date=date_str)
        
        memory.add_entry("用户喜欢简洁回复", {"category": "preference"})
        memory.add_entry("用户偏好详细解释", {"category": "preference"})
        memory.add_entry("天气很好", {"category": "weather"})
        
        results = memory.search("用户")
        
        assert len(results) == 2
    
    def test_delete_entry(self, temp_dir):
        """测试删除记忆条目"""
        from L4_file_persist import DailyMemory
        
        date_str = datetime.now().strftime("%Y-%m-%d")
        memory = DailyMemory(base_path=temp_dir, date=date_str)
        
        entry_id = memory.add_entry("待删除内容", {})
        
        assert memory.get_entry_count() == 1
        
        memory.delete_entry(entry_id)
        
        assert memory.get_entry_count() == 0
    
    def test_update_entry(self, temp_dir):
        """测试更新记忆条目"""
        from L4_file_persist import DailyMemory
        
        date_str = datetime.now().strftime("%Y-%m-%d")
        memory = DailyMemory(base_path=temp_dir, date=date_str)
        
        entry_id = memory.add_entry("原始内容", {"version": 1})
        
        memory.update_entry(entry_id, content="更新后内容", metadata={"version": 2})
        
        entries = memory.get_entries()
        entry = next((e for e in entries if e["id"] == entry_id), None)
        
        assert entry is not None
        assert entry["content"] == "更新后内容"
        assert entry["metadata"]["version"] == 2


class TestSessionSummary:
    """SessionSummary 会话总结测试"""
    
    def test_session_summary_init(self, temp_dir):
        """测试会话总结初始化"""
        from L4_file_persist import SessionSummary
        
        summary = SessionSummary(
            session_id="session_001",
            base_path=temp_dir
        )
        
        assert summary.session_id == "session_001"
        assert summary.base_path == temp_dir
    
    def test_add_turn(self, temp_dir):
        """测试添加对话轮次"""
        from L4_file_persist import SessionSummary
        
        summary = SessionSummary(session_id="session_001", base_path=temp_dir)
        
        summary.add_turn(
            user_message="你好",
            assistant_message="你好！有什么可以帮你的吗？"
        )
        
        summary.add_turn(
            user_message="今天天气怎么样？",
            assistant_message="今天天气晴朗，适合外出。"
        )
        
        assert summary.get_turn_count() == 2
    
    def test_add_fact(self, temp_dir):
        """测试添加事实"""
        from L4_file_persist import SessionSummary
        
        summary = SessionSummary(session_id="session_001", base_path=temp_dir)
        
        summary.add_fact("用户询问天气", {"type": "question"})
        summary.add_fact("助手回答天气晴朗", {"type": "answer"})
        
        facts = summary.get_facts()
        
        assert len(facts) == 2
    
    def test_generate_summary(self, temp_dir):
        """测试生成总结"""
        from L4_file_persist import SessionSummary
        
        summary = SessionSummary(session_id="session_001", base_path=temp_dir)
        
        summary.add_turn("问题1", "回答1")
        summary.add_turn("问题2", "回答2")
        summary.add_fact("关键事实1", {})
        summary.add_fact("关键事实2", {})
        
        generated = summary.generate_summary()
        
        assert generated is not None
        assert len(generated) > 0
    
    def test_save_and_load(self, temp_dir):
        """测试保存和加载"""
        from L4_file_persist import SessionSummary
        
        summary1 = SessionSummary(session_id="session_load", base_path=temp_dir)
        summary1.add_turn("测试对话", "测试回复")
        summary1.save()
        
        summary2 = SessionSummary(session_id="session_load", base_path=temp_dir)
        summary2.load()
        
        assert summary2.get_turn_count() == 1


class TestFilePersistStore:
    """FilePersistStore 文件持久化存储测试"""
    
    def test_store_init(self, temp_dir):
        """测试存储初始化"""
        from L4_file_persist import FilePersistStore
        
        store = FilePersistStore(base_path=temp_dir)
        
        assert store.base_path == temp_dir
        assert os.path.exists(store.memory_dir)
    
    def test_store_fact(self, temp_dir):
        """测试存储事实"""
        from L4_file_persist import FilePersistStore
        
        store = FilePersistStore(base_path=temp_dir)
        
        fact_id = store.store_fact(
            content="测试事实",
            metadata={"type": "test", "importance": 0.8}
        )
        
        assert fact_id is not None
        assert "fact_" in fact_id
    
    def test_get_facts(self, temp_dir):
        """测试获取事实列表"""
        from L4_file_persist import FilePersistStore
        
        store = FilePersistStore(base_path=temp_dir)
        
        store.store_fact("事实1", {"index": 1})
        store.store_fact("事实2", {"index": 2})
        
        facts = store.get_facts()
        
        assert len(facts) >= 2
    
    def test_search_facts(self, temp_dir):
        """测试搜索事实"""
        from L4_file_persist import FilePersistStore
        
        store = FilePersistStore(base_path=temp_dir)
        
        store.store_fact("用户喜欢简洁回复", {"category": "preference"})
        store.store_fact("用户偏好长篇解释", {"category": "preference"})
        store.store_fact("今天天气好", {"category": "weather"})
        
        results = store.search_facts("用户")
        
        assert len(results) == 2
    
    def test_append_diary(self, temp_dir):
        """测试追加日记"""
        from L4_file_persist import FilePersistStore
        
        store = FilePersistStore(base_path=temp_dir)
        
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        store.append_diary(date_str, "日记内容1")
        store.append_diary(date_str, "日记内容2")
        
        # 读取日记
        diary_path = os.path.join(store.memory_dir, f"{date_str}.md")
        assert os.path.exists(diary_path)
        
        with open(diary_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert "日记内容1" in content
            assert "日记内容2" in content
    
    def test_get_diary(self, temp_dir):
        """测试获取日记"""
        from L4_file_persist import FilePersistStore
        
        store = FilePersistStore(base_path=temp_dir)
        
        date_str = datetime.now().strftime("%Y-%m-%d")
        store.append_diary(date_str, "测试日记内容")
        
        diary = store.get_diary(date_str)
        
        assert diary is not None
        assert "测试日记内容" in diary
    
    def test_get_daily_memory(self, temp_dir):
        """测试获取每日记忆对象"""
        from L4_file_persist import FilePersistStore
        
        store = FilePersistStore(base_path=temp_dir)
        
        daily = store.get_daily_memory()
        
        assert daily is not None
        assert isinstance(daily, type(store.daily_memory))
    
    def test_archive_session(self, temp_dir):
        """测试归档会话"""
        from L4_file_persist import FilePersistStore
        
        store = FilePersistStore(base_path=temp_dir)
        
        session_data = {
            "session_id": "test_session",
            "turns": [
                {"user": "问题", "assistant": "回答"}
            ],
            "facts": ["事实1", "事实2"],
            "summary": "会话总结"
        }
        
        archive_path = store.archive_session(session_data)
        
        assert archive_path is not None
        assert os.path.exists(archive_path)
    
    def test_get_archived_sessions(self, temp_dir):
        """测试获取归档会话列表"""
        from L4_file_persist import FilePersistStore
        
        store = FilePersistStore(base_path=temp_dir)
        
        # 归档多个会话
        for i in range(3):
            store.archive_session({
                "session_id": f"session_{i}",
                "summary": f"总结{i}"
            })
        
        sessions = store.get_archived_sessions()
        
        assert len(sessions) >= 3
    
    def test_backup_and_restore(self, temp_dir):
        """测试备份和恢复"""
        from L4_file_persist import FilePersistStore
        
        store = FilePersistStore(base_path=temp_dir)
        
        # 添加数据
        store.store_fact("备份测试事实", {"type": "backup"})
        
        # 创建备份
        backup_path = os.path.join(temp_dir, "backup")
        store.backup(backup_path)
        
        assert os.path.exists(backup_path)
        
        # 添加新数据
        store.store_fact("新数据", {})
        
        # 恢复备份
        store.restore(backup_path)
        
        facts = store.search_facts("备份测试")
        assert len(facts) >= 1


class TestFilePersistStoreEdgeCases:
    """FilePersistStore 边界情况测试"""
    
    def test_empty_store(self, temp_dir):
        """测试空存储"""
        from L4_file_persist import FilePersistStore
        
        store = FilePersistStore(base_path=temp_dir)
        
        assert store.get_facts() == []
        assert store.get_diary("2099-12-31") is None
    
    def test_special_characters_in_content(self, temp_dir):
        """测试内容中的特殊字符"""
        from L4_file_persist import FilePersistStore
        
        store = FilePersistStore(base_path=temp_dir)
        
        special_content = "测试<>\"'&符号\n换行和\t制表符"
        
        store.store_fact(special_content, {})
        
        facts = store.get_facts()
        assert any(f["content"] == special_content for f in facts)
    
    def test_unicode_content(self, temp_dir):
        """测试 Unicode 内容"""
        from L4_file_persist import FilePersistStore
        
        store = FilePersistStore(base_path=temp_dir)
        
        store.store_fact("中文内容", {"lang": "zh"})
        store.store_fact("日本語", {"lang": "ja"})
        store.store_fact("한국어", {"lang": "ko"})
        store.store_fact("Emoji😀🎉", {"lang": "emoji"})
        
        facts = store.get_facts()
        assert len(facts) == 4
    
    def test_large_content(self, temp_dir):
        """测试大内容"""
        from L4_file_persist import FilePersistStore
        
        store = FilePersistStore(base_path=temp_dir)
        
        large_content = "x" * 100000  # 100KB
        
        store.store_fact(large_content, {})
        
        facts = store.get_facts()
        assert any(f["content"] == large_content for f in facts)
    
    def test_metadata_types(self, temp_dir):
        """测试不同类型的元数据"""
        from L4_file_persist import FilePersistStore
        
        store = FilePersistStore(base_path=temp_dir)
        
        complex_metadata = {
            "string": "value",
            "number": 42,
            "float": 3.14,
            "boolean": True,
            "list": [1, 2, 3],
            "nested": {"a": 1, "b": 2}
        }
        
        store.store_fact("测试元数据", complex_metadata)
        
        facts = store.get_facts()
        fact = facts[-1]
        
        assert fact["metadata"]["string"] == "value"
        assert fact["metadata"]["number"] == 42
        assert fact["metadata"]["nested"]["a"] == 1
    
    def test_concurrent_writes(self, temp_dir):
        """测试并发写入"""
        from L4_file_persist import FilePersistStore
        
        store = FilePersistStore(base_path=temp_dir)
        
        # 模拟多次快速写入
        for i in range(100):
            store.store_fact(f"并发写入 {i}", {"index": i})
        
        facts = store.get_facts()
        assert len(facts) >= 100
    
    def test_date_formats(self, temp_dir):
        """测试不同日期格式"""
        from L4_file_persist import FilePersistStore
        
        store = FilePersistStore(base_path=temp_dir)
        
        dates = [
            "2026-01-01",
            "2026-12-31",
            datetime.now().strftime("%Y-%m-%d")
        ]
        
        for date_str in dates:
            store.append_diary(date_str, f"日记 {date_str}")
            assert store.get_diary(date_str) is not None
