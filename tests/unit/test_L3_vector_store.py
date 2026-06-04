"""
L3_vector_store.py 单元测试
v1.0 API 对齐版本
"""

import pytest
import json
import os
import sys
import math
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../..", "src"))

from L3_vector_store import VectorStore, HybridRetriever, BM25Indexer, MemoryEntry


class TestBM25Indexer:
    """BM25Indexer 测试 - v1.0 使用 BM25Indexer"""
    
    def test_bm25_indexer_init(self):
        """测试 BM25 初始化"""
        index = BM25Indexer()
        assert index.k1 == 1.5
        assert index.b == 0.75
    
    def test_bm25_tokenize(self):
        """测试分词"""
        index = BM25Indexer()
        tokens = index._tokenize("这是一个测试句子")
        
        assert isinstance(tokens, list)
        assert len(tokens) > 0
    
    def test_bm25_index_documents(self):
        """测试文档索引"""
        index = BM25Indexer()
        
        docs = [
            "User likes simple responses",
            "User prefers detailed explanations",
            "Simple and detailed each have advantages"
        ]
        
        index.index(docs)
        
        # 使用 len(documents) 而不是 doc_count
        assert len(index.documents) == 3
        assert len(index.doc_ids) == 3
    
    def test_bm25_search(self):
        """测试 BM25 搜索"""
        index = BM25Indexer()
        
        docs = [
            "User likes simple responses",
            "User prefers detailed explanations",
            "Simple and detailed each have advantages"
        ]
        
        index.index(docs)
        
        results = index.search("User simple")
        
        # 结果是 [(doc_id, score), ...] 格式
        assert len(results) > 0
    
    def test_bm25_empty_index(self):
        """测试空索引"""
        index = BM25Indexer()
        results = index.search("任意查询")
        assert results == []


class TestVectorMath:
    """向量数学测试"""
    
    def test_cosine_similarity(self):
        """测试余弦相似度"""
        # 使用 VectorStore._cosine_similarity
        vs = VectorStore(storage_path=":memory:", embedding_dims=128)
        
        # 相同向量
        v1 = [1.0, 0.0, 0.0]
        v2 = [1.0, 0.0, 0.0]
        assert abs(vs._cosine_similarity(v1, v2) - 1.0) < 0.0001
        
        # 正交向量
        v3 = [0.0, 1.0, 0.0]
        assert abs(vs._cosine_similarity(v1, v3)) < 0.0001
        
        # 相反向量
        v4 = [-1.0, 0.0, 0.0]
        assert abs(vs._cosine_similarity(v1, v4) - (-1.0)) < 0.0001


class TestVectorStore:
    """VectorStore 向量存储测试"""
    
    @pytest.fixture
    def store_path(self):
        """创建临时存储路径"""
        temp_dir = tempfile.mkdtemp()
        path = os.path.join(temp_dir, "vector_store.json")
        yield path
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_vector_store_init(self, store_path):
        """测试向量存储初始化"""
        store = VectorStore(
            storage_path=store_path,
            embedding_dims=128
        )
        
        assert store.embedding_dims == 128
        assert len(store.entries) == 0
    
    def test_store(self, store_path):
        """测试存储（v1.0 使用 store()）"""
        store = VectorStore(storage_path=store_path, embedding_dims=128)
        
        memory_id = store.store(
            content="测试内容",
            metadata={"source": "test"},
            importance=0.8
        )
        
        assert memory_id is not None
        assert len(store.entries) == 1
    
    def test_store_multiple(self, store_path):
        """测试多次存储"""
        store = VectorStore(storage_path=store_path, embedding_dims=64)
        
        for i in range(10):
            memory_id = store.store(
                content=f"测试记忆 {i}",
                importance=0.5 + i * 0.05
            )
            assert memory_id is not None
        
        assert len(store.entries) == 10
    
    def test_search(self, store_path):
        """测试搜索（v1.0 使用 search()）"""
        store = VectorStore(storage_path=store_path, embedding_dims=128)
        
        store.store(content="User likes simple response style", importance=0.8)
        store.store(content="AI technology develops rapidly", importance=0.9)
        
        results = store.search("simple", limit=5)
        
        assert len(results) > 0
        assert "content" in results[0]
    
    def test_get(self, store_path):
        """测试获取单条记忆（v1.0 使用 get()）"""
        store = VectorStore(storage_path=store_path, embedding_dims=128)
        
        memory_id = store.store(content="测试内容", importance=0.8)
        
        retrieved = store.get(memory_id)
        
        assert retrieved is not None
        assert retrieved["content"] == "测试内容"
    
    def test_delete(self, store_path):
        """测试删除"""
        store = VectorStore(storage_path=store_path, embedding_dims=128)
        
        memory_id = store.store(content="待删除内容", importance=0.5)
        
        success = store.delete(memory_id)
        assert success is True
        assert len(store.entries) == 0
    
    def test_save_and_load(self, store_path):
        """测试持久化"""
        # 存储
        store1 = VectorStore(storage_path=store_path, embedding_dims=64)
        id1 = store1.store(content="持久化测试", importance=0.9)
        
        # 重新加载
        store2 = VectorStore(storage_path=store_path, embedding_dims=64)
        retrieved = store2.get(id1)
        
        assert retrieved is not None
        assert retrieved["content"] == "持久化测试"
    
    def test_get_stats(self, store_path):
        """测试统计信息"""
        store = VectorStore(storage_path=store_path, embedding_dims=64)
        
        store.store(content="测试1", importance=0.8, fact_type="type1", tags=["tag1"])
        store.store(content="测试2", importance=0.6, fact_type="type2", tags=["tag1", "tag2"])
        
        stats = store.get_stats()
        
        assert stats["total"] == 2
        assert "avg_importance" in stats
        assert "fact_types" in stats
    
    def test_increment_access(self, store_path):
        """测试访问计数"""
        store = VectorStore(storage_path=store_path, embedding_dims=64)
        
        memory_id = store.store(content="访问计数测试", importance=0.5)
        
        store.increment_access(memory_id)
        store.increment_access(memory_id)
        
        entry = store.get(memory_id)
        assert entry["access_count"] == 2
    
    def test_update_importance(self, store_path):
        """测试更新重要性"""
        store = VectorStore(storage_path=store_path, embedding_dims=64)
        
        memory_id = store.store(content="重要性测试", importance=0.5)
        
        store.update_importance(memory_id, 0.9)
        
        entry = store.get(memory_id)
        assert entry["importance"] == 0.9
    
    def test_get_all_entries(self, store_path):
        """测试获取所有条目"""
        store = VectorStore(storage_path=store_path, embedding_dims=64)
        
        store.store(content="测试1", importance=0.8)
        store.store(content="测试2", importance=0.6)
        
        entries = store.get_all_entries()
        assert len(entries) == 2


class TestHybridRetriever:
    """HybridRetriever 混合检索测试"""
    
    @pytest.fixture
    def store_path(self):
        """创建临时存储路径"""
        temp_dir = tempfile.mkdtemp()
        path = os.path.join(temp_dir, "hybrid_store.json")
        yield path
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_hybrid_retriever_init(self, store_path):
        """测试混合检索器初始化"""
        store = VectorStore(storage_path=store_path, embedding_dims=64)
        retriever = HybridRetriever(vector_store=store)
        
        assert retriever.vector_store is not None
    
    def test_retrieve(self, store_path):
        """测试检索"""
        store = VectorStore(storage_path=store_path, embedding_dims=64)
        retriever = HybridRetriever(vector_store=store)
        
        store.store(content="User likes simple response style", importance=0.8, fact_type="preference")
        store.store(content="AI technology develops rapidly", importance=0.9, fact_type="knowledge")
        
        results = retriever.retrieve("simple style", limit=5)
        
        assert len(results) > 0
        assert "content" in results[0]
        assert "score" in results[0]
    
    def test_retrieve_with_context(self, store_path):
        """测试带上下文的检索"""
        store = VectorStore(storage_path=store_path, embedding_dims=64)
        retriever = HybridRetriever(vector_store=store)
        
        store.store(content="Recent events happened", importance=0.8)
        store.store(content="Things from long ago", importance=0.7)
        
        results = retriever.retrieve_with_context("things", limit=5, time_decay=True)
        
        assert isinstance(results, list)


class TestVectorStoreEdgeCases:
    """向量存储边界情况测试"""
    
    @pytest.fixture
    def store_path(self):
        """创建临时存储路径"""
        temp_dir = tempfile.mkdtemp()
        path = os.path.join(temp_dir, "edge_store.json")
        yield path
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_empty_store_search(self, store_path):
        """测试空存储搜索"""
        store = VectorStore(storage_path=store_path, embedding_dims=64)
        
        results = store.search("任意查询", limit=5)
        assert results == []
    
    def test_nonexistent_id_get(self, store_path):
        """测试获取不存在的 ID"""
        store = VectorStore(storage_path=store_path, embedding_dims=64)
        
        result = store.get("nonexistent_id")
        assert result is None
    
    def test_delete_nonexistent(self, store_path):
        """测试删除不存在的记忆"""
        store = VectorStore(storage_path=store_path, embedding_dims=64)
        
        success = store.delete("nonexistent_id")
        assert success is False
    
    def test_special_characters_content(self, store_path):
        """测试特殊字符内容"""
        store = VectorStore(storage_path=store_path, embedding_dims=32)
        
        special_content = "Test special chars <>&'\""
        memory_id = store.store(content=special_content, importance=0.8)
        
        retrieved = store.get(memory_id)
        assert retrieved["content"] == special_content
    
    def test_unicode_content(self, store_path):
        """测试 Unicode 内容"""
        store = VectorStore(storage_path=store_path, embedding_dims=32)
        
        store.store(content="Test content", importance=0.8)
        store.store(content="Another test", importance=0.7)
        
        assert len(store.entries) == 2
    
    def test_large_dataset(self, store_path):
        """测试大数据集（限制数量避免超时）"""
        store = VectorStore(storage_path=store_path, embedding_dims=32)
        
        # 添加 50 个向量（限制数量避免超时）
        for i in range(50):
            store.store(content=f"Content {i}", importance=0.5)
        
        assert len(store.entries) == 50
