"""
TagIndex 单元测试

测试 TagIndex 模块的核心功能：
- Tag CRUD
- 倒排索引正确性
- 并发安全
- 前缀搜索
"""

import pytest
import json
from pathlib import Path

from agentmemory.data import TagIndex


class TestTagIndexInit:
    """TagIndex 初始化测试"""
    
    def test_init_creates_index_file(self, tag_index: TagIndex):
        """测试初始化创建索引文件"""
        assert tag_index.index_file.exists()
    
    def test_init_loads_existing_index(self, tag_index_with_tags: TagIndex):
        """测试初始化加载已有索引"""
        index = tag_index_with_tags
        assert index.index_file.exists()


class TestTagIndexCRUD:
    """TagIndex CRUD 测试"""
    
    @pytest.mark.asyncio
    async def test_add_tag(self, tag_index: TagIndex):
        """测试添加 tag"""
        await tag_index.add_tag("test", "mem_001", "A.项目/测试")
        
        result = await tag_index.get_by_tag("test")
        assert ("mem_001", "A.项目/测试") in result
    
    @pytest.mark.asyncio
    async def test_add_duplicate_tag(self, tag_index: TagIndex):
        """测试添加重复 tag"""
        await tag_index.add_tag("test", "mem_001", "A.项目")
        await tag_index.add_tag("test", "mem_001", "A.项目")  # 重复添加
        
        result = await tag_index.get_by_tag("test")
        # 不应该有重复
        count = sum(1 for entry in result if entry[0] == "mem_001")
        assert count == 1
    
    @pytest.mark.asyncio
    async def test_remove_tag(self, tag_index_with_tags: TagIndex):
        """测试移除 tag"""
        index = tag_index_with_tags
        
        await index.remove_tag("重要", "mem_002")
        
        result = await index.get_by_tag("重要")
        assert ("mem_002", "A.项目/石榴籽") not in result
    
    @pytest.mark.asyncio
    async def test_remove_nonexistent_tag(self, tag_index: TagIndex):
        """测试移除不存在的 tag"""
        # 不应该抛出异常
        await tag_index.remove_tag("nonexistent", "mem_001")
    
    @pytest.mark.asyncio
    async def test_update_tags(self, tag_index: TagIndex):
        """测试更新记忆的 tags"""
        await tag_index.add_tag("old_tag", "mem_001", "A.项目")
        
        await tag_index.update_tags(
            memory_id="mem_001",
            category_path="A.项目",
            old_tags=["old_tag"],
            new_tags=["new_tag"]
        )
        
        # 旧 tag 应该不存在
        old_result = await tag_index.get_by_tag("old_tag")
        assert ("mem_001", "A.项目") not in old_result
        
        # 新 tag 应该存在
        new_result = await tag_index.get_by_tag("new_tag")
        assert ("mem_001", "A.项目") in new_result
    
    @pytest.mark.asyncio
    async def test_remove_memory(self, tag_index_with_tags: TagIndex):
        """测试移除记忆的所有 tags"""
        index = tag_index_with_tags
        
        await index.remove_memory("mem_001")
        
        # mem_001 的所有 tags 都应该被移除
        assert await index.get_by_tag("重要") == [("mem_002", "A.项目/石榴籽")]
        assert await index.get_by_tag("AI") == []
        assert await index.get_by_tag("测试") == []


class TestTagIndexQuery:
    """TagIndex 查询测试"""
    
    @pytest.mark.asyncio
    async def test_get_by_tag(self, tag_index_with_tags: TagIndex):
        """测试根据 tag 获取记忆"""
        index = tag_index_with_tags
        
        result = await index.get_by_tag("重要")
        assert len(result) == 2
        assert ("mem_001", "A.项目/石榴籽") in result
        assert ("mem_002", "A.项目/石榴籽") in result
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_tag(self, tag_index: TagIndex):
        """测试获取不存在的 tag"""
        result = await tag_index.get_by_tag("nonexistent")
        assert result == []
    
    @pytest.mark.asyncio
    async def test_search_tags_prefix(self, tag_index_with_tags: TagIndex):
        """测试前缀搜索 tags"""
        index = tag_index_with_tags
        
        # 添加更多 tags 用于搜索测试
        await index.add_tag("重要", "mem_003", "B.个人")
        await index.add_tag("重要任务", "mem_004", "A.项目")
        await index.add_tag("重试", "mem_005", "C.临时")
        
        result = await index.search_tags("重要")
        assert "重要" in result
        assert "重要任务" in result
        # "重试" 不应该匹配 "重要" 前缀
        assert "重试" not in result
    
    @pytest.mark.asyncio
    async def test_search_tags_case_insensitive(self, tag_index_with_tags: TagIndex):
        """测试 tag 搜索大小写不敏感"""
        index = tag_index_with_tags
        
        result_lower = await index.search_tags("ai")
        result_upper = await index.search_tags("AI")
        
        assert len(result_lower) > 0
        assert "AI" in result_lower
        assert result_lower == result_upper


class TestTagIndexPersistence:
    """TagIndex 持久化测试"""
    
    @pytest.mark.asyncio
    async def test_index_persistence(self, tag_index_with_tags: TagIndex):
        """测试索引持久化"""
        index = tag_index_with_tags
        
        # 读取索引文件
        with open(index.index_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        assert isinstance(data, dict)
        assert "重要" in data


class TestTagIndexConcurrency:
    """TagIndex 并发测试"""
    
    @pytest.mark.asyncio
    async def test_concurrent_add_tags(self, tag_index: TagIndex):
        """测试并发添加 tags"""
        import asyncio
        
        async def add_tag_task(tag: str, memory_id: str):
            await tag_index.add_tag(tag, memory_id, "A.项目")
        
        tasks = [
            add_tag_task("tag1", "mem_001"),
            add_tag_task("tag1", "mem_002"),
            add_tag_task("tag1", "mem_003"),
        ]
        await asyncio.gather(*tasks)
        
        result = await tag_index.get_by_tag("tag1")
        assert len(result) == 3
    
    @pytest.mark.asyncio
    async def test_concurrent_updates(self, tag_index: TagIndex):
        """测试并发更新"""
        import asyncio
        
        # 先添加一些 tags
        await tag_index.add_tag("shared", "mem_001", "A.项目")
        await tag_index.add_tag("shared", "mem_002", "A.项目")
        
        # 并发更新
        async def update_task(mem_id: str):
            await tag_index.update_tags(
                memory_id=mem_id,
                category_path="A.项目",
                old_tags=["shared"],
                new_tags=["updated"]
            )
        
        await asyncio.gather(
            update_task("mem_001"),
            update_task("mem_002")
        )
        
        # 验证更新成功
        old_result = await tag_index.get_by_tag("shared")
        assert len(old_result) == 0
        
        new_result = await tag_index.get_by_tag("updated")
        assert len(new_result) == 2
