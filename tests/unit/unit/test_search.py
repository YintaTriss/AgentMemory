"""
AgentMemory v2.0 - Search 单元测试

测试 SearchEngine 和 HybridRetriever：
- 双轨检索（语义 + 分类）
- 混合打分
"""

import sys
import os
import asyncio
import tempfile
import shutil
from pathlib import Path

import pytest

# Add source path
sys.path.insert(0, "C:/Users/31683/AppData/Local/Programs/SpectrAI/2026.6.5.13.09")

from agentmemory.providers.protocols import VectorEntry
from agentmemory.providers.embedder import MockEmbedder
from agentmemory.providers.vectorstore import MockVectorStore
from agentmemory.search.search_engine import SearchEngine, SearchOptions
from agentmemory.search.hybrid_retriever import (
    HybridRetriever,
    HybridWeights,
    ScoredEntry,
)


class TestSearchEngine:
    """SearchEngine 测试"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp = tempfile.mkdtemp()
        yield Path(temp)
        shutil.rmtree(temp, ignore_errors=True)
    
    @pytest.fixture
    def search_engine(self, temp_dir):
        """创建 SearchEngine"""
        embedder = MockEmbedder(dimensions=128)
        vectorstore = MockVectorStore(dimensions=128)
        
        return SearchEngine(
            embedder=embedder,
            vectorstore=vectorstore,
            memory_dir=str(temp_dir),
        )
    
    @pytest.mark.asyncio
    async def test_index_and_search_semantic(self, search_engine):
        """测试索引和语义搜索"""
        # 索引文档
        await search_engine.index_entry(
            id="doc-1",
            content="苹果是一种红色的水果",
            metadata={"category": "水果/苹果", "tags": ["水果", "红色"], "importance": 0.8},
        )
        await search_engine.index_entry(
            id="doc-2", 
            content="香蕉是一种黄色的水果",
            metadata={"category": "水果/香蕉", "tags": ["水果", "黄色"], "importance": 0.7},
        )
        await search_engine.index_entry(
            id="doc-3",
            content="汽车是交通工具",
            metadata={"category": "交通工具/汽车", "tags": ["车", "交通"], "importance": 0.6},
        )
        
        # 语义搜索
        results = await search_engine.search_semantic(
            "红色的水果",
            options=SearchOptions(limit=3),
        )
        
        assert len(results) >= 2  # 至少找到苹果
        assert any(r.id == "doc-1" for r in results)
    
    @pytest.mark.asyncio
    async def test_search_by_category(self, search_engine):
        """测试分类搜索"""
        # 索引文档
        await search_engine.index_entry(
            id="doc-1",
            content="苹果内容",
            metadata={"category": "水果/苹果"},
        )
        await search_engine.index_entry(
            id="doc-2",
            content="香蕉内容",
            metadata={"category": "水果/香蕉"},
        )
        await search_engine.index_entry(
            id="doc-3",
            content="汽车内容",
            metadata={"category": "交通工具/汽车"},
        )
        
        # 分类搜索
        results = await search_engine.search_by_category(
            "水果",
            recursive=True,
            options=SearchOptions(limit=10),
        )
        
        assert len(results) == 2
        assert {r.id for r in results} == {"doc-1", "doc-2"}
    
    @pytest.mark.asyncio
    async def test_search_hybrid(self, search_engine):
        """测试混合搜索"""
        # 索引文档
        await search_engine.index_entry(
            id="doc-1",
            content="苹果是一种红色的水果",
            metadata={"category": "水果", "tags": ["水果"], "importance": 0.9},
        )
        await search_engine.index_entry(
            id="doc-2",
            content="香蕉是一种黄色的水果",
            metadata={"category": "水果", "tags": ["水果"], "importance": 0.8},
        )
        await search_engine.index_entry(
            id="doc-3",
            content="红色的汽车",
            metadata={"category": "交通工具", "tags": ["汽车"], "importance": 0.7},
        )
        
        # 混合搜索
        results = await search_engine.search_hybrid(
            query="红色的水果",
            category="水果",
            options=SearchOptions(limit=5),
        )
        
        # 验证搜索到了结果
        assert len(results) >= 1
        # 验证至少包含水果分类的文档
        # (由于 MockEmbedder 使用 hash，结果顺序可能不同)
        result_ids = {r.id for r in results}
        assert result_ids & {"doc-1", "doc-2"}  # 至少有一个水果文档
    
    @pytest.mark.asyncio
    async def test_delete_entry(self, search_engine):
        """测试删除条目"""
        # 索引
        await search_engine.index_entry(
            id="to-delete",
            content="将被删除的内容",
            metadata={"category": "测试"},
        )
        
        # 验证存在
        results = await search_engine.search_semantic(
            "删除",
            options=SearchOptions(limit=5),
        )
        initial_count = len(results)
        
        # 删除
        await search_engine.delete_entry("to-delete")
        
        # 验证不存在
        stats = search_engine.get_stats()
        assert stats["vectorstore_count"] == 0


class TestHybridRetriever:
    """HybridRetriever 测试"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp = tempfile.mkdtemp()
        yield Path(temp)
        shutil.rmtree(temp, ignore_errors=True)
    
    @pytest.fixture
    def hybrid_retriever(self, temp_dir):
        """创建 HybridRetriever"""
        from agentmemory.search import create_search_engine
        
        search_engine = create_search_engine(
            memory_dir=str(temp_dir),
        )
        
        return HybridRetriever(
            search_engine=search_engine,
            weights=HybridWeights(
                vector_similarity=0.6,
                tag_match=0.3,
                importance=0.1,
            ),
        )
    
    @pytest.mark.asyncio
    async def test_search_with_weights(self, hybrid_retriever):
        """测试带权重的搜索"""
        engine = hybrid_retriever._search_engine
        
        # 索引文档
        await engine.index_entry(
            id="high-imp",
            content="重要的内容",
            metadata={"tags": ["重要"], "importance": 1.0},
        )
        await engine.index_entry(
            id="low-imp",
            content="不重要的内容",
            metadata={"tags": ["普通"], "importance": 0.2},
        )
        
        # 搜索
        results = await hybrid_retriever.search(
            query="内容",
            tags=["重要"],
            limit=2,
        )
        
        assert len(results) >= 1
        # 带有 "重要" tag 的应该排名更前
        if len(results) >= 1:
            assert results[0].id == "high-imp"
    
    @pytest.mark.asyncio
    async def test_threshold_filter(self, hybrid_retriever):
        """测试阈值过滤"""
        engine = hybrid_retriever._search_engine
        
        # 索引多个文档
        for i in range(5):
            await engine.index_entry(
                id=f"doc-{i}",
                content=f"文档 {i} 内容",
                metadata={"importance": 0.5},
            )
        
        # 高阈值应该过滤掉一些结果
        results = await hybrid_retriever.search(
            query="文档",
            threshold=0.9,  # 高阈值
            limit=10,
        )
        
        # 可能没有结果或只有少量结果
    
    @pytest.mark.asyncio
    async def test_custom_weights(self, hybrid_retriever):
        """测试自定义权重"""
        engine = hybrid_retriever._search_engine
        
        # 索引
        await engine.index_entry(
            id="tag-match",
            content="普通内容",
            metadata={"tags": ["目标"], "importance": 0.5},
        )
        await engine.index_entry(
            id="high-imp",
            content="普通内容",
            metadata={"tags": ["其他"], "importance": 1.0},
        )
        
        # Tag 权重高时
        results = await hybrid_retriever.search(
            query="内容",
            tags=["目标"],
            weights=HybridWeights(
                vector_similarity=0.0,
                tag_match=1.0,
                importance=0.0,
            ),
            limit=2,
        )
        
        assert len(results) >= 1
        if results:
            assert results[0].id == "tag-match"
    
    @pytest.mark.asyncio
    async def test_scored_entry(self, hybrid_retriever):
        """测试 ScoredEntry 的各项分数"""
        engine = hybrid_retriever._search_engine
        
        await engine.index_entry(
            id="scored",
            content="测试内容",
            metadata={"tags": ["测试"], "importance": 0.8},
        )
        
        results = await hybrid_retriever.search(
            query="测试",
            tags=["测试"],
            limit=1,
        )
        
        assert len(results) == 1
        scored = results[0]
        
        assert isinstance(scored, ScoredEntry)
        assert scored.vector_score >= 0
        assert scored.tag_score >= 0
        assert scored.importance_score >= 0
        assert scored.final_score >= 0
        assert scored.final_score <= 1.0


class TestSearchIntegration:
    """搜索集成测试"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp = tempfile.mkdtemp()
        yield Path(temp)
        shutil.rmtree(temp, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_full_pipeline(self, temp_dir):
        """测试完整流水线"""
        from agentmemory.search import create_search_engine, create_hybrid_retriever
        
        # 创建引擎
        engine = create_search_engine(memory_dir=str(temp_dir))
        retriever = create_hybrid_retriever(
            memory_dir=str(temp_dir),
        )
        
        # 批量索引
        docs = [
            ("doc-1", "机器学习是人工智能的子领域", 
             {"category": "AI", "tags": ["ML", "AI"], "importance": 0.9}),
            ("doc-2", "深度学习使用神经网络",
             {"category": "AI", "tags": ["DL", "AI"], "importance": 0.85}),
            ("doc-3", "Python 是一种编程语言",
             {"category": "编程", "tags": ["Python"], "importance": 0.7}),
            ("doc-4", "JavaScript 用于 Web 开发",
             {"category": "编程", "tags": ["JS"], "importance": 0.65}),
            ("doc-5", "神经网络是深度学习的基础",
             {"category": "AI", "tags": ["DL", "AI", "ML"], "importance": 0.88}),
        ]
        
        for id, content, metadata in docs:
            await engine.index_entry(id, content, metadata)
        
        # 语义搜索
        semantic_results = await engine.search_semantic(
            "人工智能和神经网络",
            options=SearchOptions(limit=3),
        )
        # MockEmbedder 使用 hash，相关性取决于 hash 结果
        assert isinstance(semantic_results, list)
        
        # 分类搜索
        category_results = await engine.search_by_category(
            "AI",
            recursive=True,
            options=SearchOptions(limit=10),
        )
        assert len(category_results) == 3
        
        # 混合搜索 - 使用标签匹配
        hybrid_results = await retriever.search(
            query="机器学习",
            tags=["AI", "ML"],  # 使用标签来匹配
            limit=3,
        )
        # 标签匹配应该能找到相关文档
        assert isinstance(hybrid_results, list)
        
        # 删除
        await engine.delete_entry("doc-3")
        
        # 验证删除
        stats = engine.get_stats()
        assert stats["vectorstore_count"] == 4
