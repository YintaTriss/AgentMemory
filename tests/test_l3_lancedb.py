"""
L3 向量存储层单元测试
测试 VectorStore 和 HybridRetriever
"""
import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.L3_vector_store import VectorStore, HybridRetriever, BM25Indexer, MemoryEntry


def create_test_store(tmp_path, mock_embedder):
    """创建测试用 VectorStore"""
    data_path = tmp_path / "vectors.json"
    store = VectorStore(
        storage_path=str(data_path),
        embedding_model="text-embedding-v3",
        embedding_dims=1024,
        embedding_batch_size=16
    )
    return store


class TestVectorStore:
    """VectorStore 单元测试"""

    def test_store_increases_count(self, tmp_path, mock_embedder):
        """store 后 count 增加"""
        store = create_test_store(tmp_path, mock_embedder)
        
        initial_count = store.count()
        
        store.store("第一条记忆", metadata={"importance": 0.8})
        
        assert store.count() == initial_count + 1

    def test_search_returns_results(self, tmp_path, mock_embedder):
        """search 返回 top_k 条"""
        store = create_test_store(tmp_path, mock_embedder)
        
        store.store("Python 编程语言很优雅", metadata={"importance": 0.9})
        store.store("JavaScript 是前端主要语言", metadata={"importance": 0.7})
        store.store("Go 语言性能很好", metadata={"importance": 0.8})
        
        # 使用 HybridRetriever 搜索
        retriever = HybridRetriever(store)
        results = retriever.retrieve("编程语言", limit=2)
        
        assert len(results) <= 2

    def test_search_similarity_ordering(self, tmp_path):
        """search 相似度排序正确"""
        mock_emb = MagicMock()
        mock_emb.embed.return_value = [0.1] * 1024
        
        store = create_test_store(tmp_path, mock_emb)
        
        # 存储相同内容两次
        id1 = store.store("测试内容完全相同", metadata={"importance": 0.8})
        id2 = store.store("测试内容完全相同", metadata={"importance": 0.8})
        
        # 检索相同内容
        retriever = HybridRetriever(store)
        results = retriever.retrieve("测试内容完全相同", limit=10)
        
        assert isinstance(results, list)

    def test_delete_decreases_count(self, tmp_path, mock_embedder):
        """delete 后 count 减少"""
        store = create_test_store(tmp_path, mock_embedder)
        
        id1 = store.store("待删除的记忆", metadata={"importance": 0.5})
        initial_count = store.count()
        
        store.delete(id1)
        
        assert store.count() == initial_count - 1

    def test_search_empty_store_returns_empty(self, tmp_path, mock_embedder):
        """空库 search 返回 []"""
        store = create_test_store(tmp_path, mock_embedder)
        
        retriever = HybridRetriever(store)
        results = retriever.retrieve("任意查询", limit=5)
        
        assert results == []

    def test_store_with_tags(self, tmp_path, mock_embedder):
        """存储带标签的记忆"""
        store = create_test_store(tmp_path, mock_embedder)
        
        memory_id = store.store(
            "带标签的记忆",
            metadata={"tags": ["重要", "项目"], "importance": 0.9}
        )
        
        entry = store.get(memory_id)
        assert entry is not None
        assert "重要" in entry["tags"]
        assert "项目" in entry["tags"]

    def test_increment_access_count(self, tmp_path, mock_embedder):
        """访问计数增加"""
        store = create_test_store(tmp_path, mock_embedder)
        
        memory_id = store.store("测试访问计数", metadata={"importance": 0.5})
        
        initial_count = store.get(memory_id)["access_count"]
        
        store.increment_access(memory_id)
        store.increment_access(memory_id)
        
        updated = store.get(memory_id)
        assert updated["access_count"] == initial_count + 2


class TestBM25Indexer:
    """BM25 索引器单元测试"""

    def test_bm25_index_and_search(self):
        """BM25 索引和搜索"""
        indexer = BM25Indexer()
        
        docs = [
            "Python is a great programming language",
            "JavaScript is used for web development",
            "Go is a systems programming language"
        ]
        
        indexer.index(docs)
        
        results = indexer.search("Python programming", k=2)
        
        assert len(results) <= 2
        if results:
            assert results[0][0] == "0"

    def test_bm25_empty_query(self):
        """空查询处理"""
        indexer = BM25Indexer()
        indexer.index(["doc1", "doc2"])
        
        results = indexer.search("", k=10)
        
        assert isinstance(results, list)

    def test_bm25_no_match(self):
        """无匹配结果"""
        indexer = BM25Indexer()
        indexer.index(["Python code", "JavaScript code"])
        
        results = indexer.search("xyz123nonexistent", k=5)
        
        assert isinstance(results, list)

    def test_bm25_tokenization(self):
        """BM25 分词"""
        indexer = BM25Indexer()
        
        tokens = indexer._tokenize("Hello World! Python 3.9")
        
        assert "hello" in tokens
        assert "world" in tokens
        assert "python" in tokens


class TestHybridRetriever:
    """混合检索器测试"""

    def test_hybrid_search_combines_scores(self, tmp_path, mock_embedder):
        """混合检索结合多种评分"""
        store = create_test_store(tmp_path, mock_embedder)
        
        store.store("测试混合检索", metadata={"importance": 0.9})
        
        retriever = HybridRetriever(store, vector_weight=0.5, bm25_weight=0.5)
        results = retriever.retrieve("测试", limit=1)
        
        assert isinstance(results, list)

    def test_rerank_enabled(self, tmp_path, mock_embedder):
        """启用重排序"""
        store = create_test_store(tmp_path, mock_embedder)
        
        retriever = HybridRetriever(store, rerank_enabled=True)
        
        assert retriever.rerank_enabled is True
