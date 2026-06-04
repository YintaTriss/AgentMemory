"""
L3_vector_store.py 单元测试
"""

import pytest
import json
import os
import sys
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../..", "src"))

from L3_vector_store import VectorStore, HybridRetriever


class TestBM25:
    """BM25 相关测试"""
    
    def test_bm25_init(self, temp_dir):
        """测试 BM25 初始化"""
        from L3_vector_store import BM25Index
        
        index = BM25Index()
        assert index.k1 == 1.5
        assert index.b == 0.75
    
    def test_bm25_tokenize(self, temp_dir):
        """测试分词"""
        from L3_vector_store import BM25Index
        
        index = BM25Index()
        tokens = index.tokenize("这是一个测试句子")
        
        assert isinstance(tokens, list)
        assert len(tokens) > 0
    
    def test_bm25_index_documents(self, temp_dir):
        """测试文档索引"""
        from L3_vector_store import BM25Index
        
        index = BM25Index()
        
        docs = [
            "用户喜欢简洁的回复",
            "用户偏好长篇详细解释",
            "简洁和详细各有优势"
        ]
        
        for doc in docs:
            index.add_document(doc)
        
        assert index.doc_count == 3
    
    def test_bm25_search(self, temp_dir):
        """测试 BM25 搜索"""
        from L3_vector_store import BM25Index
        
        index = BM25Index()
        
        docs = [
            "用户喜欢简洁的回复",
            "用户偏好长篇详细解释",
            "简洁和详细各有优势"
        ]
        
        for doc in docs:
            index.add_document(doc)
        
        results = index.search("用户 简洁")
        
        assert len(results) > 0
        assert results[0]["doc_index"] in [0, 2]  # 包含"用户"或"简洁"的文档


class TestVectorMath:
    """向量数学测试"""
    
    def test_cosine_similarity(self):
        """测试余弦相似度"""
        from L3_vector_store import cosine_similarity
        
        # 相同向量
        v1 = [1.0, 0.0, 0.0]
        v2 = [1.0, 0.0, 0.0]
        assert abs(cosine_similarity(v1, v2) - 1.0) < 0.0001
        
        # 正交向量
        v3 = [0.0, 1.0, 0.0]
        assert abs(cosine_similarity(v1, v3)) < 0.0001
        
        # 相反向量
        v4 = [-1.0, 0.0, 0.0]
        assert abs(cosine_similarity(v1, v4) - (-1.0)) < 0.0001
    
    def test_vector_normalize(self):
        """测试向量归一化"""
        from L3_vector_store import normalize_vector
        
        v = [3.0, 4.0, 0.0]
        normalized = normalize_vector(v)
        
        # 计算模长
        magnitude = math.sqrt(sum(x**2 for x in normalized))
        assert abs(magnitude - 1.0) < 0.0001
    
    def test_batch_dot_product(self):
        """测试批量点积"""
        from L3_vector_store import batch_dot_product
        
        query = [1.0, 2.0, 3.0]
        vectors = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0]
        ]
        
        results = batch_dot_product(query, vectors)
        
        assert len(results) == 3
        assert results[0] == 1.0
        assert results[1] == 2.0
        assert results[2] == 3.0


class TestVectorStore:
    """VectorStore 向量存储测试"""
    
    def test_vector_store_init(self, temp_dir):
        """测试向量存储初始化"""
        store_path = os.path.join(temp_dir, "vector_store.json")
        store = VectorStore(
            path=store_path,
            dimensions=128
        )
        
        assert store.dimensions == 128
        assert store.size() == 0
    
    def test_add_vector(self, temp_dir):
        """测试添加向量"""
        store_path = os.path.join(temp_dir, "vector_store.json")
        store = VectorStore(path=store_path, dimensions=128)
        
        vector_id = store.add_vector(
            content="测试内容",
            embedding=[0.1] * 128,
            metadata={"source": "test"}
        )
        
        assert vector_id is not None
        assert store.size() == 1
    
    def test_add_multiple_vectors(self, temp_dir):
        """测试添加多个向量"""
        store_path = os.path.join(temp_dir, "vector_store.json")
        store = VectorStore(path=store_path, dimensions=128)
        
        for i in range(10):
            embedding = [float(i / 10)] * 128
            store.add_vector(
                content=f"内容 {i}",
                embedding=embedding,
                metadata={"index": i}
            )
        
        assert store.size() == 10
    
    def test_search_similar(self, temp_dir):
        """测试相似向量搜索"""
        store_path = os.path.join(temp_dir, "vector_store.json")
        store = VectorStore(path=store_path, dimensions=128)
        
        # 添加相似和不相似的向量
        store.add_vector(
            content="机器学习是人工智能的子领域",
            embedding=[0.1] * 128,
            metadata={"category": "AI"}
        )
        
        store.add_vector(
            content="今天天气真好",
            embedding=[0.9] * 128,
            metadata={"category": "weather"}
        )
        
        # 搜索与 AI 相关的内容
        results = store.search_similar(
            query_vector=[0.1] * 128,
            top_k=1
        )
        
        assert len(results) >= 1
        assert "机器学习" in results[0]["content"]
    
    def test_delete_vector(self, temp_dir):
        """测试删除向量"""
        store_path = os.path.join(temp_dir, "vector_store.json")
        store = VectorStore(path=store_path, dimensions=128)
        
        vector_id = store.add_vector(
            content="待删除内容",
            embedding=[0.5] * 128
        )
        
        assert store.size() == 1
        
        store.delete_vector(vector_id)
        
        assert store.size() == 0
    
    def test_get_vector_by_id(self, temp_dir):
        """测试按 ID 获取向量"""
        store_path = os.path.join(temp_dir, "vector_store.json")
        store = VectorStore(path=store_path, dimensions=128)
        
        original_content = "测试内容"
        vector_id = store.add_vector(
            content=original_content,
            embedding=[0.1] * 128
        )
        
        retrieved = store.get_vector_by_id(vector_id)
        
        assert retrieved is not None
        assert retrieved["content"] == original_content
    
    def test_update_vector(self, temp_dir):
        """测试更新向量"""
        store_path = os.path.join(temp_dir, "vector_store.json")
        store = VectorStore(path=store_path, dimensions=128)
        
        vector_id = store.add_vector(
            content="原始内容",
            embedding=[0.1] * 128
        )
        
        new_embedding = [0.2] * 128
        store.update_vector(vector_id, embedding=new_embedding, content="更新后内容")
        
        retrieved = store.get_vector_by_id(vector_id)
        assert retrieved["content"] == "更新后内容"
    
    def test_save_and_load(self, temp_dir):
        """测试保存和加载"""
        store_path = os.path.join(temp_dir, "persist_vector.json")
        
        # 创建并保存
        store1 = VectorStore(path=store_path, dimensions=128)
        store1.add_vector(content="持久化测试", embedding=[0.5] * 128)
        
        # 重新加载
        store2 = VectorStore(path=store_path, dimensions=128)
        
        assert store2.size() == 1
        retrieved = store2.get_vector_by_id(store2.list_vectors()[0]["id"])
        assert retrieved["content"] == "持久化测试"


class TestHybridRetriever:
    """HybridRetriever 混合检索器测试"""
    
    def test_hybrid_retriever_init(self, temp_dir):
        """测试混合检索器初始化"""
        from L3_vector_store import HybridRetriever
        
        store_path = os.path.join(temp_dir, "hybrid_store.json")
        retriever = HybridRetriever(
            vector_store_path=store_path,
            dimensions=128,
            vector_weight=0.6,
            bm25_weight=0.3,
            importance_weight=0.1
        )
        
        assert retriever.vector_weight == 0.6
        assert retriever.bm25_weight == 0.3
        assert retriever.importance_weight == 0.1
    
    def test_hybrid_search(self, temp_dir):
        """测试混合搜索"""
        from L3_vector_store import HybridRetriever
        
        store_path = os.path.join(temp_dir, "hybrid_search.json")
        retriever = HybridRetriever(
            vector_store_path=store_path,
            dimensions=128
        )
        
        # 添加文档
        retriever.add_document(
            content="人工智能和机器学习",
            embedding=[0.2] * 128,
            importance=0.9
        )
        
        retriever.add_document(
            content="天气晴朗适合出游",
            embedding=[0.8] * 128,
            importance=0.3
        )
        
        # 混合搜索
        results = retriever.search(
            query="AI 机器学习",
            query_vector=[0.2] * 128,
            top_k=2
        )
        
        assert len(results) >= 1
        # AI/机器学习相关内容应该排在前面
        assert "人工智能" in results[0]["content"]
    
    def test_bm25_only_search(self, temp_dir):
        """测试纯 BM25 搜索"""
        from L3_vector_store import HybridRetriever
        
        store_path = os.path.join(temp_dir, "bm25_only.json")
        retriever = HybridRetriever(
            vector_store_path=store_path,
            dimensions=128
        )
        
        retriever.add_document(content="精确关键词匹配测试", embedding=[0.5] * 128)
        retriever.add_document(content="不相关的文档内容", embedding=[0.5] * 128)
        
        results = retriever.search_bm25("精确关键词", top_k=1)
        
        assert len(results) >= 1
        assert "精确关键词" in results[0]["content"]
    
    def test_vector_only_search(self, temp_dir):
        """测试纯向量搜索"""
        from L3_vector_store import HybridRetriever
        
        store_path = os.path.join(temp_dir, "vector_only.json")
        retriever = HybridRetriever(
            vector_store_path=store_path,
            dimensions=128
        )
        
        # 添加语义相似但词汇不同的文档
        retriever.add_document(
            content="人工智能技术",
            embedding=[0.1] * 128
        )
        
        retriever.add_document(
            content="机器学习应用",
            embedding=[0.12] * 128  # 语义相似
        )
        
        results = retriever.search_vector(
            query_vector=[0.1] * 128,
            top_k=1
        )
        
        assert len(results) >= 1
    
    def test_rerank_results(self, temp_dir):
        """测试结果重排序"""
        from L3_vector_store import HybridRetriever
        
        store_path = os.path.join(temp_dir, "rerank.json")
        retriever = HybridRetriever(
            vector_store_path=store_path,
            dimensions=128
        )
        
        results = [
            {"id": "1", "content": "内容A", "score": 0.8, "vector_score": 0.9, "bm25_score": 0.7},
            {"id": "2", "content": "内容B", "score": 0.9, "vector_score": 0.8, "bm25_score": 0.9},
        ]
        
        reranked = retriever.rerank(results, query="测试")
        
        assert len(reranked) == 2


class TestVectorStoreEdgeCases:
    """VectorStore 边界情况测试"""
    
    def test_empty_store_search(self, temp_dir):
        """测试空存储搜索"""
        store_path = os.path.join(temp_dir, "empty_store.json")
        store = VectorStore(path=store_path, dimensions=128)
        
        results = store.search_similar(query_vector=[0.5] * 128, top_k=5)
        assert len(results) == 0
    
    def test_dimension_mismatch(self, temp_dir):
        """测试维度不匹配"""
        store_path = os.path.join(temp_dir, "dim_mismatch.json")
        store = VectorStore(path=store_path, dimensions=128)
        
        # 错误维度
        with pytest.raises((ValueError, AssertionError)):
            store.add_vector(content="错误维度", embedding=[0.1] * 64)  # 应该是 128
    
    def test_zero_vector(self, temp_dir):
        """测试零向量"""
        store_path = os.path.join(temp_dir, "zero_vector.json")
        store = VectorStore(path=store_path, dimensions=128)
        
        vector_id = store.add_vector(content="零向量", embedding=[0.0] * 128)
        assert vector_id is not None
        
        # 零向量与自身的相似度应该是 1
        results = store.search_similar(query_vector=[0.0] * 128, top_k=1)
        assert len(results) >= 1
    
    def test_large_dataset(self, temp_dir):
        """测试大数据集"""
        store_path = os.path.join(temp_dir, "large_dataset.json")
        store = VectorStore(path=store_path, dimensions=64)
        
        # 添加 1000 个向量
        for i in range(1000):
            embedding = [float(i % 10) / 10] * 64
            store.add_vector(content=f"内容 {i}", embedding=embedding)
        
        assert store.size() == 1000
        
        # 搜索应该仍然有效
        results = store.search_similar(query_vector=[0.5] * 64, top_k=10)
        assert len(results) == 10
    
    def test_special_characters_content(self, temp_dir):
        """测试特殊字符内容"""
        store_path = os.path.join(temp_dir, "special_chars.json")
        store = VectorStore(path=store_path, dimensions=32)
        
        special_content = "测试<>\"'&符号和emoji😀🎉以及中文"
        vector_id = store.add_vector(
            content=special_content,
            embedding=[0.5] * 32
        )
        
        retrieved = store.get_vector_by_id(vector_id)
        assert retrieved["content"] == special_content
    
    def test_unicode_in_content(self, temp_dir):
        """测试 Unicode 内容"""
        store_path = os.path.join(temp_dir, "unicode.json")
        store = VectorStore(path=store_path, dimensions=32)
        
        store.add_vector(content="中文内容测试", embedding=[0.5] * 32)
        store.add_vector(content="日本語テスト", embedding=[0.5] * 32)
        store.add_vector(content="한국어 테스트", embedding=[0.5] * 32)
        
        assert store.size() == 3
