"""
HybridRetriever 测试

测试混合检索器：
- 混合权重计算
- Tag 匹配打分
- 重要性打分
- 多信号融合
"""

import os
import sys
import asyncio
from pathlib import Path

import pytest

# 添加 agentmemory 路径
AGENTMEMORY_SRC = Path(__file__).parent.parent.parent / "agentmemory"
if str(AGENTMEMORY_SRC) not in sys.path:
    sys.path.insert(0, str(AGENTMEMORY_SRC))

from agentmemory.search.hybrid_retriever import (
    HybridRetriever,
    HybridWeights,
    HybridSearchOptions,
    ScoredEntry,
    create_hybrid_retriever,
)
from agentmemory.search.search_engine import (
    SearchEngine,
    MemoryEntry,
)
from agentmemory.providers.vectorstore import MockVectorStore
from tests.factories.embedder_factory import MockEmbedder


class TestHybridWeights:
    """混合权重测试"""
    
    def test_weights_default(self):
        """测试默认权重"""
        weights = HybridWeights()
        
        assert weights.vector_similarity == 0.6
        assert weights.tag_match == 0.3
        assert weights.importance == 0.1
    
    def test_weights_custom(self):
        """测试自定义权重"""
        weights = HybridWeights(
            vector_similarity=0.5,
            tag_match=0.4,
            importance=0.1,
        )
        
        assert weights.vector_similarity == 0.5
        assert weights.tag_match == 0.4
        assert weights.importance == 0.1
    
    def test_weights_normalization(self):
        """测试权重归一化"""
        weights = HybridWeights(
            vector_similarity=0.6,
            tag_match=0.3,
            importance=0.1,
        )
        
        # 权重和应该为 1
        total = weights.vector_similarity + weights.tag_match + weights.importance
        assert abs(total - 1.0) < 0.001
    
    def test_weights_imbalanced_sum(self):
        """测试非 1 和的归一化"""
        weights = HybridWeights(
            vector_similarity=1.0,
            tag_match=1.0,
            importance=1.0,
        )
        
        # 应该自动归一化
        total = weights.vector_similarity + weights.tag_match + weights.importance
        assert abs(total - 1.0) < 0.001


class TestHybridSearchOptions:
    """混合搜索选项测试"""
    
    def test_options_default(self):
        """测试默认选项"""
        options = HybridSearchOptions()
        
        assert options.limit == 10
        assert options.threshold == 0.0
        assert options.weights is None
        assert options.tag_match_boost == 1.0
        assert options.importance_boost == 1.0
    
    def test_options_with_weights(self):
        """测试带权重的选项"""
        weights = HybridWeights(
            vector_similarity=0.7,
            tag_match=0.2,
            importance=0.1,
        )
        
        options = HybridSearchOptions(
            weights=weights,
            limit=5,
        )
        
        assert options.weights == weights
        assert options.limit == 5


class TestHybridRetrieverBasics:
    """HybridRetriever 基础测试"""
    
    def test_retriever_initialization(self, tmp_memory_dir, mock_embedder):
        """测试初始化"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=mock_vs,
        )
        
        retriever = HybridRetriever(search_engine=engine)
        
        assert retriever._search_engine is engine
        assert retriever._weights is not None
    
    def test_retriever_with_custom_weights(self, tmp_memory_dir, mock_embedder):
        """测试带自定义权重的初始化"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=mock_vs,
        )
        
        weights = HybridWeights(
            vector_similarity=0.8,
            tag_match=0.1,
            importance=0.1,
        )
        
        retriever = HybridRetriever(
            search_engine=engine,
            weights=weights,
        )
        
        assert retriever.weights == weights
    
    def test_retriever_default_limit(self, tmp_memory_dir, mock_embedder):
        """测试默认限制"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=mock_vs,
        )
        
        retriever = HybridRetriever(
            search_engine=engine,
            default_limit=20,
        )
        
        assert retriever._default_limit == 20


class TestHybridRetrieverWeightsProperty:
    """HybridRetriever 权重属性测试"""
    
    def test_weights_getter(self, tmp_memory_dir, mock_embedder):
        """测试权重获取"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(memory_dir=str(tmp_memory_dir), embedder=mock_embedder, vectorstore=mock_vs)
        
        weights = HybridWeights()
        retriever = HybridRetriever(search_engine=engine, weights=weights)
        
        assert retriever.weights is weights
    
    def test_weights_setter(self, tmp_memory_dir, mock_embedder):
        """测试权重设置"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(memory_dir=str(tmp_memory_dir), embedder=mock_embedder, vectorstore=mock_vs)
        
        retriever = HybridRetriever(search_engine=engine)
        
        new_weights = HybridWeights(
            vector_similarity=0.9,
            tag_match=0.05,
            importance=0.05,
        )
        
        retriever.weights = new_weights
        
        assert retriever.weights is new_weights


class TestHybridRetrieverTagScoring:
    """Tag 打分测试"""
    
    def test_calculate_tag_score_full_match(self, tmp_memory_dir, mock_embedder):
        """完全匹配得满分"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(memory_dir=str(tmp_memory_dir), embedder=mock_embedder, vectorstore=mock_vs)
        
        retriever = HybridRetriever(search_engine=engine)
        
        entry = MemoryEntry(
            id="test",
            content="测试",
            metadata={"tags": ["AI", "ML"]},
        )
        
        score = retriever._calculate_tag_score(entry, query_tags=["AI", "ML"])
        
        assert score > 0
    
    def test_calculate_tag_score_partial_match(self, tmp_memory_dir, mock_embedder):
        """部分匹配得分"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(memory_dir=str(tmp_memory_dir), embedder=mock_embedder, vectorstore=mock_vs)
        
        retriever = HybridRetriever(search_engine=engine)
        
        entry = MemoryEntry(
            id="test",
            content="测试",
            metadata={"tags": ["AI"]},
        )
        
        score = retriever._calculate_tag_score(entry, query_tags=["AI", "ML"])
        
        assert 0 < score < 1
    
    def test_calculate_tag_score_no_match(self, tmp_memory_dir, mock_embedder):
        """无匹配得 0 分"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(memory_dir=str(tmp_memory_dir), embedder=mock_embedder, vectorstore=mock_vs)
        
        retriever = HybridRetriever(search_engine=engine)
        
        entry = MemoryEntry(
            id="test",
            content="测试",
            metadata={"tags": ["其他"]},
        )
        
        score = retriever._calculate_tag_score(entry, query_tags=["AI", "ML"])
        
        assert score == 0
    
    def test_calculate_tag_score_no_query_tags(self, tmp_memory_dir, mock_embedder):
        """无查询标签得满分"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(memory_dir=str(tmp_memory_dir), embedder=mock_embedder, vectorstore=mock_vs)
        
        retriever = HybridRetriever(search_engine=engine)
        
        entry = MemoryEntry(
            id="test",
            content="测试",
            metadata={"tags": ["AI"]},
        )
        
        score = retriever._calculate_tag_score(entry, query_tags=None)
        
        assert score == 1.0
    
    def test_calculate_tag_score_empty_entry_tags(self, tmp_memory_dir, mock_embedder):
        """条目无标签得 0 分"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(memory_dir=str(tmp_memory_dir), embedder=mock_embedder, vectorstore=mock_vs)
        
        retriever = HybridRetriever(search_engine=engine)
        
        entry = MemoryEntry(
            id="test",
            content="测试",
            metadata={},
        )
        
        score = retriever._calculate_tag_score(entry, query_tags=["AI"])
        
        assert score == 0


class TestHybridRetrieverImportanceScoring:
    """重要性打分测试"""
    
    def test_calculate_importance_score(self, tmp_memory_dir, mock_embedder):
        """重要性分数"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(memory_dir=str(tmp_memory_dir), embedder=mock_embedder, vectorstore=mock_vs)
        
        retriever = HybridRetriever(search_engine=engine)
        
        entry = MemoryEntry(
            id="test",
            content="测试",
            metadata={"importance": 0.8},
        )
        
        score = retriever._calculate_importance_score(entry)
        
        assert score == 0.8
    
    def test_calculate_importance_score_out_of_range(self, tmp_memory_dir, mock_embedder):
        """超出范围的重要性"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(memory_dir=str(tmp_memory_dir), embedder=mock_embedder, vectorstore=mock_vs)
        
        retriever = HybridRetriever(search_engine=engine)
        
        entry = MemoryEntry(
            id="test",
            content="测试",
            metadata={"importance": 1.5},
        )
        
        score = retriever._calculate_importance_score(entry)
        
        assert score == 1.0  # 应该被限制在 1.0
    
    def test_calculate_importance_score_default(self, tmp_memory_dir, mock_embedder):
        """默认重要性"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(memory_dir=str(tmp_memory_dir), embedder=mock_embedder, vectorstore=mock_vs)
        
        retriever = HybridRetriever(search_engine=engine)
        
        entry = MemoryEntry(
            id="test",
            content="测试",
            metadata={},
        )
        
        score = retriever._calculate_importance_score(entry)
        
        assert score == 0.5  # 默认值


class TestHybridRetrieverStats:
    """统计信息测试"""
    
    def test_get_stats(self, tmp_memory_dir, mock_embedder):
        """获取统计信息"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=mock_vs,
        )
        
        retriever = HybridRetriever(search_engine=engine)
        
        stats = retriever.get_stats()
        
        assert isinstance(stats, dict)
        assert 'weights' in stats
        assert 'search_engine' in stats


class TestCreateHybridRetriever:
    """create_hybrid_retriever 工厂函数测试"""
    
    def test_create_retriever_default(self, tmp_memory_dir):
        """测试默认创建"""
        retriever = create_hybrid_retriever(memory_dir=str(tmp_memory_dir))
        
        assert retriever is not None
        assert isinstance(retriever, HybridRetriever)
    
    def test_create_retriever_custom(self, tmp_memory_dir, mock_embedder):
        """测试自定义创建"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=mock_vs,
        )
        
        weights = HybridWeights(
            vector_similarity=0.9,
            tag_match=0.05,
            importance=0.05,
        )
        
        retriever = create_hybrid_retriever(
            memory_dir=str(tmp_memory_dir),
            weights=weights,
            default_limit=15,
        )
        
        assert retriever.weights == weights
        assert retriever._default_limit == 15
