"""
VectorStore Provider 测试

测试 VectorStore Provider 实现：
- MockVectorStore
- USearchVectorStore (fallback to MockVectorStore)
- CRUD 操作
- 持久化
"""

import os
import sys
import asyncio
import json
from pathlib import Path

import pytest

# 添加 agentmemory 路径
AGENTMEMORY_SRC = Path(__file__).parent.parent.parent / "agentmemory"
if str(AGENTMEMORY_SRC) not in sys.path:
    sys.path.insert(0, str(AGENTMEMORY_SRC))

from agentmemory.providers.vectorstore import (
    MockVectorStore,
    get_vectorstore,
)
from agentmemory.providers.protocols import (
    VectorEntry,
    SearchResult,
    DistanceMetric,
)


class TestMockVectorStoreBasics:
    """MockVectorStore 基础测试"""
    
    def test_vectorstore_initialization_default(self, tmp_vectorstore_path):
        """测试默认初始化"""
        store = MockVectorStore()
        
        assert store.dimensions == 384
        assert store.count == 0
    
    def test_vectorstore_initialization_custom(self, tmp_vectorstore_path):
        """测试自定义初始化"""
        store = MockVectorStore(
            path=str(tmp_vectorstore_path),
            dimensions=768,
        )
        
        assert store.dimensions == 768
        assert store.count == 0
    
    def test_vectorstore_properties(self, tmp_vectorstore_path):
        """测试属性"""
        store = MockVectorStore(path=str(tmp_vectorstore_path))
        
        assert hasattr(store, 'dimensions')
        assert hasattr(store, 'count')
        assert hasattr(store, 'path')


class TestMockVectorStoreCRUD:
    """MockVectorStore CRUD 测试"""
    
    @pytest.mark.asyncio
    async def test_upsert_single_entry(self, tmp_vectorstore_path, mock_embedder):
        """插入单个条目"""
        store = MockVectorStore(
            path=str(tmp_vectorstore_path),
            dimensions=mock_embedder.dimensions,
        )
        
        entry = VectorEntry(
            id="test-1",
            vector=mock_embedder.embed("测试文本"),
            metadata={"content": "测试内容"},
        )
        
        await store.upsert_async([entry])
        
        assert store.count == 1
    
    @pytest.mark.asyncio
    async def test_upsert_multiple_entries(self, tmp_vectorstore_path, mock_embedder):
        """插入多个条目"""
        store = MockVectorStore(
            path=str(tmp_vectorstore_path),
            dimensions=mock_embedder.dimensions,
        )
        
        entries = []
        for i in range(5):
            entry = VectorEntry(
                id=f"test-{i}",
                vector=mock_embedder.embed(f"文本 {i}"),
                metadata={"index": i},
            )
            entries.append(entry)
        
        await store.upsert_async(entries)
        
        assert store.count == 5
    
    @pytest.mark.asyncio
    async def test_upsert_update_existing(self, tmp_vectorstore_path, mock_embedder):
        """更新已存在的条目"""
        store = MockVectorStore(
            path=str(tmp_vectorstore_path),
            dimensions=mock_embedder.dimensions,
        )
        
        entry1 = VectorEntry(
            id="test-1",
            vector=mock_embedder.embed("原始文本"),
            metadata={"version": 1},
        )
        
        await store.upsert_async([entry1])
        assert store.count == 1
        
        entry2 = VectorEntry(
            id="test-1",
            vector=mock_embedder.embed("更新文本"),
            metadata={"version": 2},
        )
        
        await store.upsert_async([entry2])
        assert store.count == 1  # 数量不变
    
    @pytest.mark.asyncio
    async def test_upsert_empty_list(self, tmp_vectorstore_path):
        """插入空列表"""
        store = MockVectorStore(path=str(tmp_vectorstore_path))
        
        await store.upsert_async([])
        
        assert store.count == 0
    
    @pytest.mark.asyncio
    async def test_delete_single_entry(self, tmp_vectorstore_path, mock_embedder):
        """删除单个条目"""
        store = MockVectorStore(
            path=str(tmp_vectorstore_path),
            dimensions=mock_embedder.dimensions,
        )
        
        entry = VectorEntry(
            id="test-1",
            vector=mock_embedder.embed("测试文本"),
        )
        
        await store.upsert_async([entry])
        assert store.count == 1
        
        await store.delete_async(["test-1"])
        assert store.count == 0
    
    @pytest.mark.asyncio
    async def test_delete_multiple_entries(self, tmp_vectorstore_path, mock_embedder):
        """删除多个条目"""
        store = MockVectorStore(
            path=str(tmp_vectorstore_path),
            dimensions=mock_embedder.dimensions,
        )
        
        for i in range(5):
            entry = VectorEntry(
                id=f"test-{i}",
                vector=mock_embedder.embed(f"文本 {i}"),
            )
            await store.upsert_async([entry])
        
        assert store.count == 5
        
        await store.delete_async(["test-0", "test-2", "test-4"])
        assert store.count == 2
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, tmp_vectorstore_path, mock_embedder):
        """删除不存在的条目"""
        store = MockVectorStore(
            path=str(tmp_vectorstore_path),
            dimensions=mock_embedder.dimensions,
        )
        
        # 不应该抛出异常
        await store.delete_async(["nonexistent"])
        
        assert store.count == 0


class TestMockVectorStoreSearch:
    """MockVectorStore 搜索测试"""
    
    @pytest.mark.asyncio
    async def test_search_basic(self, tmp_vectorstore_path, mock_embedder):
        """基础搜索"""
        store = MockVectorStore(
            path=str(tmp_vectorstore_path),
            dimensions=mock_embedder.dimensions,
        )
        
        # 插入测试数据
        for i, text in enumerate(["苹果", "香蕉", "电脑", "手机", "汽车"]):
            entry = VectorEntry(
                id=f"item-{i}",
                vector=mock_embedder.embed(text),
                metadata={"text": text},
            )
            await store.upsert_async([entry])
        
        # 搜索
        query = mock_embedder.embed("水果")
        results = await store.search_async(query, limit=3)
        
        assert len(results) <= 3
        for result in results:
            assert hasattr(result, 'id')
            assert hasattr(result, 'score')
    
    @pytest.mark.asyncio
    async def test_search_with_limit(self, tmp_vectorstore_path, mock_embedder):
        """限制结果数量"""
        store = MockVectorStore(
            path=str(tmp_vectorstore_path),
            dimensions=mock_embedder.dimensions,
        )
        
        for i in range(10):
            entry = VectorEntry(
                id=f"item-{i}",
                vector=mock_embedder.embed(f"文本 {i}"),
            )
            await store.upsert_async([entry])
        
        query = mock_embedder.embed("查询")
        results = await store.search_async(query, limit=5)
        
        assert len(results) <= 5
    
    @pytest.mark.asyncio
    async def test_search_with_threshold(self, tmp_vectorstore_path, mock_embedder):
        """带阈值的搜索"""
        store = MockVectorStore(
            path=str(tmp_vectorstore_path),
            dimensions=mock_embedder.dimensions,
        )
        
        # 插入相似度明显不同的数据
        entry1 = VectorEntry(
            id="similar",
            vector=mock_embedder.embed("机器学习是人工智能的一个分支"),
        )
        entry2 = VectorEntry(
            id="different",
            vector=mock_embedder.embed("今天天气很好"),
        )
        
        await store.upsert_async([entry1, entry2])
        
        query = mock_embedder.embed("深度学习神经网络")
        results = await store.search_async(query, threshold=0.1)
        
        # 所有结果都应满足阈值
        for result in results:
            assert result.score >= 0.1
    
    @pytest.mark.asyncio
    async def test_search_empty_index(self, tmp_vectorstore_path, mock_embedder):
        """空索引搜索"""
        store = MockVectorStore(
            path=str(tmp_vectorstore_path),
            dimensions=mock_embedder.dimensions,
        )
        
        query = mock_embedder.embed("查询")
        results = await store.search_async(query)
        
        assert results == []
    
    @pytest.mark.asyncio
    async def test_search_results_ordered(self, tmp_vectorstore_path, mock_embedder):
        """结果按分数排序"""
        store = MockVectorStore(
            path=str(tmp_vectorstore_path),
            dimensions=mock_embedder.dimensions,
        )
        
        for i in range(5):
            entry = VectorEntry(
                id=f"item-{i}",
                vector=mock_embedder.embed(f"文本 {i}"),
            )
            await store.upsert_async([entry])
        
        query = mock_embedder.embed("查询")
        results = await store.search_async(query, limit=5)
        
        # 分数应该递减
        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score


class TestMockVectorStoreMetadata:
    """MockVectorStore 元数据测试"""
    
    @pytest.mark.asyncio
    async def test_search_with_metadata_filter(self, tmp_vectorstore_path, mock_embedder):
        """带元数据过滤的搜索"""
        store = MockVectorStore(
            path=str(tmp_vectorstore_path),
            dimensions=mock_embedder.dimensions,
        )
        
        entries = [
            VectorEntry(
                id="item-1",
                vector=mock_embedder.embed("苹果"),
                metadata={"category": "水果", "color": "red"},
            ),
            VectorEntry(
                id="item-2",
                vector=mock_embedder.embed("香蕉"),
                metadata={"category": "水果", "color": "yellow"},
            ),
            VectorEntry(
                id="item-3",
                vector=mock_embedder.embed("汽车"),
                metadata={"category": "交通工具", "color": "blue"},
            ),
        ]
        
        await store.upsert_async(entries)
        
        query = mock_embedder.embed("查询")
        results = await store.search_async(
            query,
            filter_metadata={"category": "水果"},
        )
        
        # 结果应该只包含水果类别
        for result in results:
            assert result.metadata.get("category") == "水果"


class TestMockVectorStoreSync:
    """MockVectorStore 同步方法测试"""
    
    def test_upsert_sync(self, tmp_vectorstore_path, mock_embedder):
        """同步 upsert"""
        # 在新的事件循环中运行
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            store = MockVectorStore(
                path=str(tmp_vectorstore_path),
                dimensions=mock_embedder.dimensions,
            )
            
            entry = VectorEntry(
                id="test-1",
                vector=mock_embedder.embed("测试"),
            )
            
            # 同步调用
            store.upsert([entry])
            
            assert store.count == 1
        finally:
            loop.close()
    
    def test_delete_sync(self, tmp_vectorstore_path, mock_embedder):
        """同步 delete"""
        # 在新的事件循环中运行
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            store = MockVectorStore(
                path=str(tmp_vectorstore_path),
                dimensions=mock_embedder.dimensions,
            )
            
            entry = VectorEntry(
                id="test-1",
                vector=mock_embedder.embed("测试"),
            )
            
            loop.run_until_complete(store.upsert_async([entry]))
            store.delete(["test-1"])
            
            assert store.count == 0
        finally:
            loop.close()


class TestMockVectorStorePersistence:
    """MockVectorStore 持久化测试"""
    
    @pytest.mark.asyncio
    async def test_persist_no_error(self, tmp_vectorstore_path, mock_embedder):
        """持久化不报错（Mock 版本无实际操作）"""
        store = MockVectorStore(
            path=str(tmp_vectorstore_path),
            dimensions=mock_embedder.dimensions,
        )
        
        entry = VectorEntry(
            id="test-1",
            vector=mock_embedder.embed("测试"),
        )
        
        await store.upsert_async([entry])
        await store.persist_async()
        
        # Mock 版本应该通过
        assert True
    
    @pytest.mark.asyncio
    async def test_load_no_error(self, tmp_vectorstore_path):
        """加载不报错（Mock 版本无实际操作）"""
        store = MockVectorStore(path=str(tmp_vectorstore_path))
        
        await store.load_async()
        
        # Mock 版本应该通过
        assert True


class TestGetVectorStoreFactory:
    """get_vectorstore 工厂函数测试"""
    
    def test_get_mock_vectorstore(self):
        """获取 MockVectorStore"""
        store = get_vectorstore(provider="mock")
        
        assert isinstance(store, MockVectorStore)
    
    def test_get_vectorstore_fallback_to_mock(self):
        """usearch 不可用时回退到 mock"""
        # 强制使用 mock provider
        store = get_vectorstore(provider="usearch")
        
        # 应该是 MockVectorStore（因为 usearch 可能不可用）
        assert isinstance(store, MockVectorStore)
    
    def test_get_vectorstore_custom_dimensions(self):
        """自定义维度"""
        store = get_vectorstore(provider="mock", dimensions=512)
        
        assert store.dimensions == 512


class TestVectorStoreEdgeCases:
    """VectorStore 边界情况测试"""
    
    @pytest.mark.asyncio
    async def test_upsert_after_delete(self, tmp_vectorstore_path, mock_embedder):
        """删除后重新插入"""
        store = MockVectorStore(
            path=str(tmp_vectorstore_path),
            dimensions=mock_embedder.dimensions,
        )
        
        entry = VectorEntry(
            id="test-1",
            vector=mock_embedder.embed("测试"),
        )
        
        await store.upsert_async([entry])
        await store.delete_async(["test-1"])
        await store.upsert_async([entry])
        
        assert store.count == 1
    
    @pytest.mark.asyncio
    async def test_duplicate_ids_in_batch(self, tmp_vectorstore_path, mock_embedder):
        """批量插入中包含重复 ID"""
        store = MockVectorStore(
            path=str(tmp_vectorstore_path),
            dimensions=mock_embedder.dimensions,
        )
        
        entries = [
            VectorEntry(
                id="same-id",
                vector=mock_embedder.embed("文本1"),
            ),
            VectorEntry(
                id="same-id",
                vector=mock_embedder.embed("文本2"),
            ),
        ]
        
        await store.upsert_async(entries)
        
        # 应该只保留最后一个
        assert store.count == 1
    
    @pytest.mark.asyncio
    async def test_large_batch_upsert(self, tmp_vectorstore_path, mock_embedder):
        """大批量插入"""
        store = MockVectorStore(
            path=str(tmp_vectorstore_path),
            dimensions=mock_embedder.dimensions,
        )
        
        entries = [
            VectorEntry(
                id=f"item-{i}",
                vector=mock_embedder.embed(f"文本 {i}"),
            )
            for i in range(100)
        ]
        
        await store.upsert_async(entries)
        
        assert store.count == 100
    
    @pytest.mark.asyncio
    async def test_search_large_index(self, tmp_vectorstore_path, mock_embedder):
        """大索引搜索"""
        store = MockVectorStore(
            path=str(tmp_vectorstore_path),
            dimensions=mock_embedder.dimensions,
        )
        
        # 插入 100 个条目
        entries = [
            VectorEntry(
                id=f"item-{i}",
                vector=mock_embedder.embed(f"文本 {i}"),
            )
            for i in range(100)
        ]
        await store.upsert_async(entries)
        
        # 搜索
        query = mock_embedder.embed("查询")
        results = await store.search_async(query, limit=10)
        
        assert len(results) <= 10
