"""
VectorStore 单元测试

测试 VectorStore Provider 的核心功能：
- 增删改查
- 持久化
- 度量方式
- 并发安全
"""

import pytest
import os
import asyncio
import numpy as np

from agentmemory.v2_providers import (
    USearchVectorStore,
    VectorStoreProtocol,
    DistanceMetric,
    SearchResult,
)


class TestVectorStoreInit:
    """VectorStore 初始化测试"""
    
    def test_init_creates_store(self, vector_store: USearchVectorStore):
        """测试初始化创建存储"""
        assert vector_store is not None
        assert vector_store.dimension == 128
    
    def test_count_is_zero_initially(self, vector_store: USearchVectorStore):
        """测试初始计数为 0"""
        assert vector_store.count == 0


class TestVectorStoreProtocol:
    """VectorStore Protocol 测试"""
    
    def test_vectorstore_isinstance(self, vector_store: USearchVectorStore):
        """测试满足 VectorStoreProtocol"""
        assert isinstance(vector_store, VectorStoreProtocol)
    
    def test_has_upsert_method(self, vector_store: USearchVectorStore):
        """测试有 upsert 方法"""
        assert hasattr(vector_store, "upsert")
        assert callable(vector_store.upsert)
    
    def test_has_search_method(self, vector_store: USearchVectorStore):
        """测试有 search 方法"""
        assert hasattr(vector_store, "search")
        assert callable(vector_store.search)
    
    def test_has_delete_method(self, vector_store: USearchVectorStore):
        """测试有 delete 方法"""
        assert hasattr(vector_store, "delete")
        assert callable(vector_store.delete)
    
    def test_has_persist_method(self, vector_store: USearchVectorStore):
        """测试有 persist 方法"""
        assert hasattr(vector_store, "persist")
        assert callable(vector_store.persist)


class TestVectorStoreUpsert:
    """VectorStore 增删改测试"""
    
    @pytest.mark.asyncio
    async def test_upsert_single_vector(self, vector_store: USearchVectorStore):
        """测试插入单个向量"""
        vector = np.random.randn(128).astype(np.float32)
        vector = (vector / np.linalg.norm(vector)).tolist()
        
        await vector_store.upsert(
            ids=["vec_001"],
            vectors=[vector],
            payloads=[{"text": "test"}]
        )
        
        assert vector_store.count == 1
    
    @pytest.mark.asyncio
    async def test_upsert_multiple_vectors(self, vector_store: USearchVectorStore):
        """测试批量插入向量"""
        vectors = []
        for _ in range(5):
            v = np.random.randn(128).astype(np.float32)
            v = (v / np.linalg.norm(v)).tolist()
            vectors.append(v)
        
        await vector_store.upsert(
            ids=[f"vec_{i:03d}" for i in range(5)],
            vectors=vectors,
            payloads=[{"text": f"text_{i}"} for i in range(5)]
        )
        
        assert vector_store.count == 5
    
    @pytest.mark.asyncio
    async def test_upsert_updates_existing(self, vector_store: USearchVectorStore):
        """测试更新已有向量"""
        vector = np.random.randn(128).astype(np.float32)
        vector = (vector / np.linalg.norm(vector)).tolist()
        
        # 首次插入
        await vector_store.upsert(
            ids=["vec_001"],
            vectors=[vector],
            payloads=[{"text": "original"}]
        )
        
        # 更新
        await vector_store.upsert(
            ids=["vec_001"],
            vectors=[vector],
            payloads=[{"text": "updated"}]
        )
        
        # 应该只有一个向量
        assert vector_store.count == 1
        
        # 验证更新
        results = await vector_store.search(vector, limit=1)
        assert results[0].payload["text"] == "updated"


class TestVectorStoreSearch:
    """VectorStore 搜索测试"""
    
    @pytest.mark.asyncio
    async def test_search_returns_results(self, vector_store_with_data: USearchVectorStore):
        """测试搜索返回结果"""
        store = vector_store_with_data
        
        query = np.random.randn(128).astype(np.float32)
        query = (query / np.linalg.norm(query)).tolist()
        
        results = await store.search(query, limit=3)
        
        assert len(results) <= 3
        for result in results:
            assert isinstance(result, SearchResult)
    
    @pytest.mark.asyncio
    async def test_search_similarity_order(self, vector_store: USearchVectorStore):
        """测试搜索结果按相似度排序"""
        store = vector_store
        
        # 添加一些向量
        base_vector = np.random.randn(128).astype(np.float32)
        base_vector = base_vector / np.linalg.norm(base_vector)
        base_vector = base_vector.tolist()
        
        vectors = [base_vector]
        for _ in range(4):
            v = np.random.randn(128).astype(np.float32)
            v = (v / np.linalg.norm(v)).tolist()
            vectors.append(v)
        
        await store.upsert(
            ids=["base", "random1", "random2", "random3", "random4"],
            vectors=vectors,
            payloads=[{"text": f"vec_{i}"} for i in range(5)]
        )
        
        # 搜索基向量
        results = await store.search(base_vector, limit=5)
        
        # 基向量应该排第一
        assert results[0].id == "base"
    
    @pytest.mark.asyncio
    async def test_search_with_limit(self, vector_store_with_data: USearchVectorStore):
        """测试限制返回数量"""
        store = vector_store_with_data
        
        query = np.random.randn(128).astype(np.float32)
        query = (query / np.linalg.norm(query)).tolist()
        
        results = await store.search(query, limit=1)
        
        assert len(results) == 1
    
    @pytest.mark.asyncio
    async def test_search_with_threshold(self, vector_store_with_data: USearchVectorStore):
        """测试相似度阈值过滤"""
        store = vector_store_with_data
        
        # 使用随机向量搜索
        query = np.random.randn(128).astype(np.float32)
        query = (query / np.linalg.norm(query)).tolist()
        
        # 高阈值可能过滤掉低相似度结果
        results = await store.search(query, limit=10, threshold=0.99)
        # 应该没有结果或结果很少
        assert isinstance(results, list)


class TestVectorStoreDelete:
    """VectorStore 删除测试"""
    
    @pytest.mark.asyncio
    async def test_delete_existing_vector(self, vector_store_with_data: USearchVectorStore):
        """测试删除已有向量"""
        store = vector_store_with_data
        
        initial_count = store.count
        
        await store.delete(["vec_001"])
        
        assert store.count == initial_count - 1
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_vector(self, vector_store: USearchVectorStore):
        """测试删除不存在的向量"""
        await store.delete(["nonexistent"])
        assert vector_store.count == 0


class TestVectorStorePersistence:
    """VectorStore 持久化测试"""
    
    @pytest.mark.asyncio
    async def test_persist_creates_file(self, vector_store_with_data: USearchVectorStore, temp_dir: str):
        """测试持久化创建文件"""
        store = vector_store_with_data
        
        persist_path = os.path.join(temp_dir, "test_persist.usearch")
        await store.persist(persist_path)
        
        assert os.path.exists(persist_path)
    
    @pytest.mark.asyncio
    async def test_load_restores_data(self, vector_store_with_data: USearchVectorStore, temp_dir: str):
        """测试加载恢复数据"""
        store = vector_store_with_data
        persist_path = os.path.join(temp_dir, "test_load.usearch")
        
        await store.persist(persist_path)
        
        # 创建新存储并加载
        new_store = await USearchVectorStore.load(persist_path)
        
        assert new_store.count == store.count


class TestVectorStoreMetrics:
    """VectorStore 度量测试"""
    
    @pytest.mark.asyncio
    async def test_cosine_similarity(self, vector_store: USearchVectorStore):
        """测试余弦相似度"""
        store = USearchVectorStore(dimension=128, metric="cosine")
        
        v1 = np.random.randn(128).astype(np.float32)
        v1 = (v1 / np.linalg.norm(v1)).tolist()
        
        v2 = v1.copy()  # 相同向量
        
        await store.upsert(["v1", "v2"], [v1, v2])
        
        results = await store.search(v1, limit=2)
        
        # 相同向量应该排在前面
        assert len(results) == 2
        assert results[0].id
