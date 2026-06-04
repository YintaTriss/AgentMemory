"""
L4_file_persist.py 单元测试
"""

import pytest
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../..", "src"))

from L4_file_persist import FilePersistStore, DailyMemory


class TestDailyMemory:
    """DailyMemory 每日记忆测试"""
    
    def test_daily_memory_init(self, temp_dir):
        """测试每日记忆初始化"""
        memory = DailyMemory(workspace_path=temp_dir)
        
        assert memory is not None
    
    def test_daily_memory_append(self, temp_dir):
        """测试添加记忆条目"""
        memory = DailyMemory(workspace_path=temp_dir)
        
        entry_id = memory.append("测试记忆条目")
        
        assert entry_id is not None
    
    def test_list_entries(self, temp_dir):
        """测试获取记忆条目"""
        memory = DailyMemory(workspace_path=temp_dir)
        
        memory.append("内容1")
        memory.append("内容2")
        memory.append("内容3")
        
        entries = memory.list_entries()
        
        assert len(entries) >= 3
    
    def test_search_entries(self, temp_dir):
        """测试搜索记忆条目"""
        memory = DailyMemory(workspace_path=temp_dir)
        
        memory.append("用户喜欢简洁回复")
        memory.append("用户偏好详细解释")
        memory.append("天气很好")
        
        results = memory.search("用户")
        
        assert len(results) >= 2


class TestFilePersistStore:
    """FilePersistStore 文件持久化存储测试"""
    
    def test_store_init(self, temp_dir):
        """测试存储初始化"""
        store = FilePersistStore(workspace_path=temp_dir)
        
        assert store is not None
    
    def test_store_fact(self, temp_dir):
        """测试存储事实"""
        store = FilePersistStore(workspace_path=temp_dir)
        
        fact_id = store.store_fact(
            content="测试事实",
            metadata={"type": "test", "importance": 0.8}
        )
        
        assert fact_id is not None
    
    def test_get_stats(self, temp_dir):
        """测试获取统计信息"""
        store = FilePersistStore(workspace_path=temp_dir)
        
        store.store_fact("事实1", {})
        store.store_fact("事实2", {})
        
        stats = store.get_stats()
        
        assert stats is not None
        assert isinstance(stats, dict)


class TestFilePersistStoreEdgeCases:
    """FilePersistStore 边界情况测试"""
    
    def test_empty_store(self, temp_dir):
        """测试空存储"""
        store = FilePersistStore(workspace_path=temp_dir)
        
        entries = store.get_all_facts()
        
        assert entries == []
    
    def test_unicode_content(self, temp_dir):
        """测试 Unicode 内容"""
        store = FilePersistStore(workspace_path=temp_dir)
        
        # 测试存储 Unicode 内容不崩溃
        store.store_fact("中文内容", {"lang": "zh"})
        store.store_fact("日本語", {"lang": "ja"})
        store.store_fact("한국어", {"lang": "ko"})
        store.store_fact("Emoji😀🎉", {"lang": "emoji"})
        
        # 验证存储成功（不抛出异常即可）
        stats = store.get_stats()
        assert stats is not None
