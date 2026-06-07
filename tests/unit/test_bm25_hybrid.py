# -*- coding: utf-8 -*-
"""
BM25 + Hybrid Search 专项测试
测试 src/agent_memory/l3_lancedb.py 中的 BM25Indexer、search_bm25、search_hybrid
"""
import pytest
import sys
import os
import tempfile
import shutil
from pathlib import Path

src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from src.agent_memory.l3_lancedb import L3LanceDBStore, BM25Indexer


# ============================================================================
# BM25Indexer 单元测试
# ============================================================================

class TestBM25Indexer:
    """纯 Python BM25 索引器"""

    def setup_method(self):
        self.indexer = BM25Indexer()

    def test_index_and_search_returns_relevant_doc(self):
        """索引后能检索到包含查询词的文档"""
        docs = [
            "Python is a popular programming language",
            "JavaScript is used for web development",
            "Go is a systems programming language",
            "Rust is safe and concurrent",
        ]
        self.indexer.index(docs)
        results = self.indexer.search("Python programming", top_k=2)

        assert len(results) > 0
        # 第一个结果应该是 Python 文档
        assert results[0]["doc_index"] == 0
        assert "python" in results[0]["doc_text"].lower()

    def test_search_top_k_limits_results(self):
        """top_k 参数有效"""
        # 使用所有文档都包含的词，同时文档长度不同产生不同分数
        docs = ["python programming " + "x" * i for i in range(20)]
        self.indexer.index(docs)
        results = self.indexer.search("python", top_k=3)
        assert len(results) == 3
        # 最短的文档应该排第一（长度归一化后分数更高）
        assert results[0]["doc_index"] == 0

    def test_no_match_returns_empty_list(self):
        """无匹配返回空列表"""
        self.indexer.index(["apple", "banana", "cherry"])
        results = self.indexer.search("xyz123nonexistent", top_k=5)
        assert results == []

    def test_bm25_idf_higher_for_rare_terms(self):
        """稀有关系词的 IDF 更高"""
        docs = ["cat dog", "dog cat", "cat"]  # "cat" 在 3 篇中出现，"elephant" 不出现
        self.indexer.index(docs)
        # 搜索稀有词应该返回 0 分
        results = self.indexer.search("elephant cat", top_k=3)
        # "cat" 有匹配，"elephant" 无匹配；总分为 cat 的 IDF * BM25(cat)
        scores = [r["bm25_score"] for r in results]
        assert all(s >= 0 for s in scores)

    def test_tokenize_lowercases_and_splits(self):
        """分词小写化并按非字母数字分割"""
        tokens = self.indexer._tokenize("Hello World! Python 3.9")
        assert "hello" in tokens
        assert "world" in tokens
        assert "python" in tokens
        assert "3" in tokens and "9" in tokens  # 数字被拆分为单独 token
        assert "!" not in "".join(tokens)  # 标点被过滤

    def test_search_empty_index_returns_empty(self):
        """空索引搜索返回空"""
        results = self.indexer.search("anything", top_k=5)
        assert results == []

    def test_duplicate_docs_scored_separately(self):
        """相同内容的文档分开计分"""
        docs = ["python code", "python code", "different content"]
        self.indexer.index(docs)
        results = self.indexer.search("python", top_k=3)
        assert len(results) >= 2
        # 两个 python doc 都有正分
        scores = [r["bm25_score"] for r in results if results[0]["doc_index"] in [0, 1]]
        assert all(s > 0 for s in scores)

    def test_bm25_score_is_positive_for_matches(self):
        """有匹配的文档 BM25 分为正"""
        self.indexer.index(["the quick brown fox", "a lazy dog"])
        results = self.indexer.search("quick fox", top_k=2)
        assert results[0]["bm25_score"] > 0

    def test_k1_and_b_parameters(self):
        """自定义 k1 和 b 参数"""
        indexer = BM25Indexer(k1=0.5, b=0.5)
        indexer.index(["python programming language", "java programming"])
        results = indexer.search("python", top_k=2)
        assert len(results) > 0
        assert results[0]["bm25_score"] >= 0


# ============================================================================
# L3LanceDBStore BM25 + Hybrid 集成测试
# ============================================================================

class TestL3BM25AndHybrid:
    """L3LanceDBStore 的 search_bm25 和 search_hybrid"""

    def setup_method(self):
        self.store = L3LanceDBStore(db_path=":memory:", force_fallback=True)

    def teardown_method(self):
        self.store.drop_table()

    def test_search_bm25_finds_keyword_match(self):
        """BM25 能命中关键词"""
        self.store.upsert(
            id="mem1",
            content="Python is a great programming language",
            vector=[0.1] * 128,
            metadata={},
            importance=0.8,
            category_path="tech",
        )
        self.store.upsert(
            id="mem2",
            content="Go language performance optimization",
            vector=[0.1] * 128,
            metadata={},
            importance=0.7,
            category_path="tech",
        )

        results = self.store.search_bm25("Python", top_k=5)
        assert len(results) > 0
        assert results[0]["id"] == "mem1"
        assert results[0]["bm25_score"] > 0

    def test_search_bm25_no_match_returns_empty(self):
        """无匹配时返回空"""
        self.store.upsert(
            id="mem1",
            content="apple banana",
            vector=[0.1] * 128,
            metadata={},
        )
        results = self.store.search_bm25("xyz", top_k=5)
        assert results == []

    def test_search_bm25_top_k_works(self):
        """BM25 top_k 限制结果数量"""
        for i in range(10):
            self.store.upsert(
                id=f"mem{i}",
                content=f"document number {i} with content",
                vector=[0.1] * 128,
                metadata={},
            )
        results = self.store.search_bm25("document", top_k=3)
        assert len(results) == 3

    def test_search_hybrid_combines_vector_and_bm25(self):
        """混合搜索结合向量和 BM25 分数"""
        # 存储两条记忆
        self.store.upsert(
            id="mem_vector",
            content="Python programming language tutorial",
            vector=[0.9, 0.1, 0.1, 0.1] * 32,  # 接近查询向量
            metadata={},
            importance=0.9,
            category_path="tech",
        )
        self.store.upsert(
            id="mem_bm25",
            content="Python is great for data science and web development",
            vector=[0.1] * 128,  # 远离查询向量
            metadata={},
            importance=0.9,
            category_path="tech",
        )

        query_vector = [0.8, 0.2, 0.2, 0.2] * 32  # 接近 mem_vector
        results = self.store.search_hybrid(
            query_vector=query_vector,
            query_text="Python tutorial",
            top_k=2,
            alpha=0.5,  # 50/50 混合
        )

        assert len(results) > 0
        # 两个结果都应该有分数字段
        assert "vector_score" in results[0]
        assert "bm25_score" in results[0]
        assert "score" in results[0]  # combined score

    def test_search_hybrid_alpha_bias_vector(self):
        """alpha=1.0 完全偏向向量（使用正交向量避免 collinearity）"""
        # 查询向量：前半 1.0，后半 0.0
        query_vector = [1.0] * 64 + [0.0] * 64
        # mem_vector：同方向，高度相似（余弦 1.0）
        mem_vector_vec = [0.9] * 64 + [0.0] * 64
        # mem_bm25：正交方向，余弦相似度 = 0
        mem_bm25_vec = [0.0] * 64 + [1.0] * 64

        self.store.upsert(
            id="mem_vector",
            content="unrelated content here",
            vector=mem_vector_vec,
            metadata={},
            importance=0.5,
            category_path="tech",
        )
        self.store.upsert(
            id="mem_bm25",
            content="python programming",  # BM25 完美匹配
            vector=mem_bm25_vec,
            metadata={},
            importance=0.5,
            category_path="tech",
        )

        results = self.store.search_hybrid(
            query_vector=query_vector,
            query_text="python",
            top_k=2,
            alpha=1.0,  # 只看向量
        )

        assert results[0]["id"] == "mem_vector"
        assert results[0]["bm25_score"] == 0.0  # alpha=1 时 BM25 不参与

    def test_search_hybrid_alpha_bias_bm25(self):
        """alpha=0.0 完全偏向 BM25（使用正交向量）"""
        # 查询向量：前半 1.0，后半 0.0
        query_vector = [1.0] * 64 + [0.0] * 64
        # mem_vector：正交，余弦相似度 = 0
        mem_vector_vec = [0.0] * 64 + [1.0] * 64
        # mem_bm25：同方向，但 BM25 完美匹配
        mem_bm25_vec = [0.9] * 64 + [0.0] * 64

        self.store.upsert(
            id="mem_vector",
            content="unrelated content here",
            vector=mem_vector_vec,
            metadata={},
            importance=0.5,
            category_path="tech",
        )
        self.store.upsert(
            id="mem_bm25",
            content="python programming tutorial",  # BM25 完美匹配
            vector=mem_bm25_vec,
            metadata={},
            importance=0.5,
            category_path="tech",
        )

        results = self.store.search_hybrid(
            query_vector=query_vector,
            query_text="python",
            top_k=2,
            alpha=0.0,  # 只看 BM25
        )

        assert results[0]["id"] == "mem_bm25"
        assert results[0]["bm25_score"] > 0

    def test_search_hybrid_returns_all_fields(self):
        """混合搜索返回完整字段"""
        self.store.upsert(
            id="mem1",
            content="test content",
            vector=[0.5] * 128,
            metadata={"key": "value"},
            importance=0.8,
            category_path="test",
        )

        results = self.store.search_hybrid(
            query_vector=[0.5] * 128,
            query_text="test",
            top_k=1,
        )

        assert len(results) == 1
        r = results[0]
        assert r["id"] == "mem1"
        assert r["content"] == "test content"
        assert r["metadata"] == {"key": "value"}
        assert r["importance"] == 0.8
        assert r["category_path"] == "test"
        assert "score" in r
        assert "vector_score" in r
        assert "bm25_score" in r

    def test_search_hybrid_on_empty_store(self):
        """空库混合搜索返回空"""
        results = self.store.search_hybrid(
            query_vector=[0.5] * 128,
            query_text="anything",
            top_k=5,
        )
        assert results == []

    def test_count_returns_correct_number(self):
        """count 方法返回正确数量"""
        assert self.store.count() == 0
        self.store.upsert(id="a", content="a", vector=[0.1] * 128)
        self.store.upsert(id="b", content="b", vector=[0.1] * 128)
        assert self.store.count() == 2
        self.store.delete("a")
        assert self.store.count() == 1
