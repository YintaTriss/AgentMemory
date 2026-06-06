"""
端到端流程测试
测试完整用户流程
"""
import pytest
import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.agent_memory.l4_files import L4FilesStore, generate_mem_id
from src.agent_memory.library import LibraryClassifier


@pytest.fixture
def mock_embedder():
    """Mock embedder for testing"""
    class MockEmbedder:
        def __init__(self):
            self.dims = 128
        
        def embed(self, text):
            # 返回固定的简单向量
            return [0.1] * self.dims
        
        async def aembed(self, text):
            return self.embed(text)
    
    return MockEmbedder()


class TestEndToEndFlow:
    """端到端流程测试"""

    @pytest.mark.asyncio
    async def test_complete_user_flow(self, tmp_memory_dir, mock_embedder):
        """完整用户流程测试"""
        # 初始化存储
        l4_store = L4FilesStore(str(tmp_memory_dir))
        classifier = LibraryClassifier()
        
        # Step 1: Add 3 条记忆
        contents = ["Python 编程很有趣", "JavaScript 用于前端开发", "Go 语言性能很好"]
        
        for content in contents:
            memory_id = generate_mem_id()
            category = classifier.classify(content)
            await l4_store.save_async(memory_id, content, {
                "importance": 0.8,
                "category_path": category
            })
        
        # Step 2: List 查看
        all_ids = l4_store.list_all()
        assert len(all_ids) >= 3, "应该有至少3条记忆"
        
        # Step 3: Load 查看内容
        for memory_id in all_ids[:3]:
            content = await l4_store.load_async(memory_id)
            assert content is not None
            assert len(content) > 0
        
        # Step 4: Delete 1次
        if all_ids:
            delete_id = all_ids[0]
            await l4_store.delete_async(delete_id)
        
        # Step 5: 验证剩余
        remaining = l4_store.list_all()
        assert len(remaining) >= 2, "应该剩余至少2条记忆"

    @pytest.mark.asyncio
    async def test_two_file_group_generation(self, tmp_memory_dir):
        """2 文件组（.md / .meta.json）全部生成"""
        l4_store = L4FilesStore(str(tmp_memory_dir))
        
        # 存储一条记忆
        memory_id = generate_mem_id()
        content = "测试内容"
        await l4_store.save_async(memory_id, content, {"importance": 0.8})
        
        # 验证文件
        md_file = Path(tmp_memory_dir) / f"{memory_id}.md"
        meta_file = Path(tmp_memory_dir) / f"{memory_id}.meta.json"
        
        assert md_file.exists(), ".md 文件应该存在"
        assert meta_file.exists(), ".meta.json 文件应该存在"
        
        # 验证内容
        assert md_file.read_text(encoding="utf-8") == content
        
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        assert meta["id"] == memory_id

    @pytest.mark.asyncio
    async def test_cross_category_flow(self, tmp_memory_dir):
        """跨分类的流程"""
        l4_store = L4FilesStore(str(tmp_memory_dir))
        
        # 存储不同分类的记忆
        categories_contents = [
            ("技术/Python", "Python 是一种高级语言"),
            ("技术/JavaScript", "JavaScript 用于前端"),
            ("项目/石榴籽", "石榴籽是比赛项目"),
            ("生活/日常", "今天天气很好"),
        ]
        
        for category, content in categories_contents:
            memory_id = generate_mem_id()
            await l4_store.save_async(memory_id, content, {
                "importance": 0.8,
                "category_path": category
            })
        
        # 获取所有分类
        all_categories = l4_store.get_categories()
        
        assert "技术/Python" in all_categories or "技术" in str(all_categories)

    @pytest.mark.asyncio
    async def test_bulk_operations(self, tmp_memory_dir):
        """批量操作"""
        l4_store = L4FilesStore(str(tmp_memory_dir))
        
        # 批量存储
        batch_size = 10
        ids = []
        for i in range(batch_size):
            memory_id = generate_mem_id()
            await l4_store.save_async(
                memory_id, 
                f"批量记忆{i}", 
                {"importance": 0.5 + i * 0.05}
            )
            ids.append(memory_id)
        
        # 验证数量
        all_ids = l4_store.list_all()
        assert len(all_ids) >= batch_size

    @pytest.mark.asyncio
    async def test_metadata_integrity(self, tmp_memory_dir):
        """元数据完整性"""
        store = L4FilesStore(str(tmp_memory_dir))
        
        memory_id = generate_mem_id()
        metadata = {
            "importance": 0.9,
            "tags": ["重要", "测试"],
            "category_path": "决策/技术选型"
        }
        
        await store.save_async(memory_id, "测试记忆", metadata)
        
        # 验证元数据
        meta = await store.get_meta_async(memory_id)
        
        assert meta["importance"] == 0.9
        assert meta["tags"] == ["重要", "测试"]
        assert meta["category_path"] == "决策/技术选型"
        assert "created_at" in meta
        assert "updated_at" in meta

    @pytest.mark.asyncio
    async def test_unicode_content_persistence(self, tmp_memory_dir):
        """Unicode 内容持久化"""
        l4_store = L4FilesStore(str(tmp_memory_dir))
        
        # 存储特殊字符内容
        special_content = "特殊字符测试: 中文字符 🎉 Emoji"
        
        memory_id = generate_mem_id()
        await l4_store.save_async(memory_id, special_content, {"importance": 0.8})
        
        # 验证读取
        loaded = await l4_store.load_async(memory_id)
        assert loaded == special_content

    @pytest.mark.asyncio
    async def test_update_flow(self, tmp_memory_dir):
        """更新流程"""
        l4_store = L4FilesStore(str(tmp_memory_dir))
        
        memory_id = generate_mem_id()
        await l4_store.save_async(memory_id, "原始内容", {"importance": 0.5})
        
        # 更新元数据
        await l4_store.update_meta_async(memory_id, {
            "importance": 0.9,
            "tags": ["更新过"]
        })
        
        # 验证更新
        meta = await l4_store.get_meta_async(memory_id)
        assert meta["importance"] == 0.9
        assert meta["tags"] == ["更新过"]
        
        # 内容保持不变
        content = await l4_store.load_async(memory_id)
        assert content == "原始内容"
