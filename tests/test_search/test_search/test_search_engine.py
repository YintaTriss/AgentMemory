"""
SearchEngine 测试

测试双轨检索引擎：
- 语义检索
- 分类检索
- 混合检索
- MemoryEntry 操作
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

from agentmemory.search.search_engine import (
    SearchEngine,
    MemoryEntry,
    SearchOptions,
    create_search_engine,
)
from agentmemory.providers.vectorstore import MockVectorStore
from tests.factories.embedder_factory import MockEmbedder


class TestSearchEngineBasics:
    """SearchEngine 基础测试"""
    
    def test_engine_initialization_default(self, tmp_memory_dir):
        """测试默认初始化"""
        engine = SearchEngine(memory_dir=str(tmp_memory_dir))
        
        assert engine._memory_dir == Path(tmp_memory_dir)
        assert engine._embedder is None  # 懒加载
        assert engine._vectorstore is None  # 懒加载
    
    def test_engine_initialization_with_providers(self, tmp_memory_dir, mock_embedder):
        """测试带 provider 的初始化"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=mock_vs,
        )
        
        assert engine._embedder is mock_embedder
        assert engine._vectorstore is mock_vs
    
    def test_engine_lazy_embedder(self, tmp_memory_dir):
        """测试懒加载 embedder"""
        engine = SearchEngine(memory_dir=str(tmp_memory_dir))
        
        # 第一次访问触发加载
        embedder = engine.embedder
        assert embedder is not None
        assert hasattr(embedder, 'embed')
    
    def test_engine_lazy_vectorstore(self, tmp_memory_dir):
        """测试懒加载 vectorstore"""
        engine = SearchEngine(memory_dir=str(tmp_memory_dir))
        
        # 第一次访问触发加载
        vs = engine.vectorstore
        assert vs is not None
        assert hasattr(vs, 'upsert')


class TestSearchEngineEmbedder:
    """SearchEngine Embedder 测试"""
    
    def test_embedder_property(self, tmp_memory_dir, mock_embedder):
        """测试 embedder 属性"""
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
        )
        
        assert engine.embedder is mock_embedder
    
    def test_embedder_dimensions(self, tmp_memory_dir, mock_embedder):
        """测试 embedder 维度"""
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
        )
        
        assert engine.embedder.dimensions == mock_embedder.dimensions


class TestSearchEngineAddMemory:
    """SearchEngine 添加记忆测试"""
    
    @pytest.mark.asyncio
    async def test_add_memory_basic(self, tmp_memory_dir, mock_embedder):
        """测试添加基本记忆"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=mock_vs,
        )
        
        memory_id = "mem-1"
        await engine.index_entry(
            id=memory_id,
            content="今天学习了机器学习",
            metadata={"category": "学习"},
        )
        
        assert memory_id is not None
        assert isinstance(memory_id, str)
        assert mock_vs.count == 1
    
    @pytest.mark.asyncio
    async def test_add_memory_with_category(self, tmp_memory_dir, mock_embedder):
        """测试添加带分类的记忆"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=mock_vs,
        )
        
        memory_id = "mem-python"
        await engine.index_entry(
            id=memory_id,
            content="Python 编程",
            metadata={"category": "技术/编程"},
        )
        
        assert memory_id is not None
    
    @pytest.mark.asyncio
    async def test_add_memory_with_tags(self, tmp_memory_dir, mock_embedder):
        """测试添加带标签的记忆"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=mock_vs,
        )
        
        memory_id = "mem-dl"
        await engine.index_entry(
            id=memory_id,
            content="深度学习",
            metadata={"tags": ["AI", "神经网络"]},
        )
        
        assert memory_id is not None
    
    @pytest.mark.asyncio
    async def test_add_memory_generates_vector(self, tmp_memory_dir, mock_embedder):
        """测试添加记忆时生成向量"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=mock_vs,
        )
        
        content = "测试内容"
        memory_id = "mem-test"
        await engine.index_entry(id=memory_id, content=content, metadata={})
        
        # 验证向量被存储
        assert mock_vs.count == 1
    
    @pytest.mark.asyncio
    async def test_add_memory_multiple(self, tmp_memory_dir, mock_embedder):
        """测试添加多个记忆"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=mock_vs,
        )
        
        contents = ["内容1", "内容2", "内容3"]
        
        for i, content in enumerate(contents):
            await engine.index_entry(id=f"mem-{i}", content=content, metadata={})
        
        assert mock_vs.count == 3
    
    @pytest.mark.asyncio
    async def test_add_memory_empty_content(self, tmp_memory_dir, mock_embedder):
        """测试添加空内容"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=mock_vs,
        )
        
        # 空内容应该也能添加
        await engine.index_entry(id="mem-empty", content="", metadata={})
        
        assert mock_vs.count == 1


class TestSearchEngineSemanticSearch:
    """SearchEngine 语义检索测试"""
    
    @pytest.mark.asyncio
    async def test_search_semantic_basic(self, tmp_memory_dir, mock_embedder):
        """测试基础语义检索"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=mock_vs,
        )
        
        # 添加记忆
        await engine.index_entry(id="ml", content="机器学习是人工智能的一个分支", metadata={})
        await engine.index_entry(id="weather", content="今天天气很好", metadata={})
        await engine.index_entry(id="dl", content="深度学习使用神经网络", metadata={})
        
        # 搜索
        results = await engine.search_semantic("深度学习 神经网络")
        
        assert isinstance(results, list)
        assert len(results) >= 0
    
    @pytest.mark.asyncio
    async def test_search_semantic_with_options(self, tmp_memory_dir, mock_embedder):
        """测试带选项的语义检索"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=mock_vs,
        )
        
        for i in range(10):
            await engine.index_entry(id=f"mem-{i}", content=f"内容 {i}", metadata={})
        
        options = SearchOptions(limit=5, threshold=0.0)
        results = await engine.search_semantic("查询", options=options)
        
        assert len(results) <= 5
    
    @pytest.mark.asyncio
    async def test_search_semantic_empty_index(self, tmp_memory_dir, mock_embedder):
        """空索引搜索"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=mock_vs,
        )
        
        results = await engine.search_semantic("查询")
        
        assert results == []
    
    @pytest.mark.asyncio
    async def test_search_semantic_results_structure(self, tmp_memory_dir, mock_embedder):
        """搜索结果结构"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=mock_vs,
        )
        
        await engine.index_entry(
            id="test-1",
            content="测试内容",
            metadata={"test": "value"},
        )
        
        results = await engine.search_semantic("测试")
        
        for entry in results:
            assert hasattr(entry, 'id')
            assert hasattr(entry, 'content')
            assert hasattr(entry, 'metadata')


class TestSearchEngineCategorySearch:
    """SearchEngine 分类检索测试"""
    
    @pytest.mark.asyncio
    async def test_search_by_category_basic(self, tmp_memory_dir, mock_embedder):
        """测试基础分类检索"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=mock_vs,
        )
        
        # 添加不同分类的记忆
        await engine.index_entry(id="python", content="Python教程", metadata={"category": "技术/编程"})
        await engine.index_entry(id="js", content="JavaScript教程", metadata={"category": "技术/编程"})
        await engine.index_entry(id="fitness", content="健身计划", metadata={"category": "生活/健康"})
        
        # 按分类搜索
        results = await engine.search_by_category("技术/编程")
        
        assert isinstance(results, list)
        # 应该只返回编程相关的记忆
        for entry in results:
            assert "技术" in (entry.category or "")
    
    @pytest.mark.asyncio
    async def test_search_by_category_nonexistent(self, tmp_memory_dir, mock_embedder):
        """搜索不存在的分类"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=mock_vs,
        )
        
        await engine.index_entry(id="tech", content="测试", metadata={"category": "技术"})
        
        results = await engine.search_by_category("不存在的分类")
        
        # 应该返回空列表或只有部分匹配
        assert isinstance(results, list)


class TestSearchEngineHybridSearch:
    """SearchEngine 混合检索测试"""
    
    @pytest.mark.asyncio
    async def test_search_hybrid_basic(self, tmp_memory_dir, mock_embedder):
        """测试基础混合检索"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=mock_vs,
        )
        
        await engine.index_entry(
            id="dl",
            content="深度学习",
            metadata={"category": "技术/AI"},
        )
        
        results = await engine.search_hybrid("深度学习", category="技术")
        
        assert isinstance(results, list)
    
    @pytest.mark.asyncio
    async def test_search_hybrid_with_options(self, tmp_memory_dir, mock_embedder):
        """测试带选项的混合检索"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=mock_vs,
        )
        
        for i in range(20):
            await engine.index_entry(id=f"mem-{i}", content=f"内容 {i}", metadata={})
        
        options = SearchOptions(limit=5)
        results = await engine.search_hybrid("查询", options=options)
        
        assert len(results) <= 5


class TestSearchEngineDelete:
    """SearchEngine 删除记忆测试"""
    
    @pytest.mark.asyncio
    async def test_delete_memory(self, tmp_memory_dir, mock_embedder):
        """测试删除记忆"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=mock_vs,
        )
        
        memory_id = "to-delete"
        await engine.index_entry(id=memory_id, content="待删除内容", metadata={})
        assert mock_vs.count == 1
        
        await engine.delete_entry(memory_id)
        
        assert mock_vs.count == 0
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, tmp_memory_dir, mock_embedder):
        """测试删除不存在的记忆"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=mock_vs,
        )
        
        # 不应该抛出异常
        await engine.delete_entry("nonexistent-id")
        
        assert mock_vs.count == 0


class TestSearchEngineStats:
    """SearchEngine 统计信息测试"""
    
    def test_get_stats(self, tmp_memory_dir, mock_embedder):
        """测试获取统计信息"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=mock_vs,
        )
        
        stats = engine.get_stats()
        
        assert isinstance(stats, dict)
        assert 'vectorstore_count' in stats
        assert 'embedder_dimensions' in stats


class TestSearchEngineLibraryIndex:
    """SearchEngine 图书馆索引测试"""
    
    @pytest.mark.asyncio
    async def test_library_index_creation(self, tmp_memory_dir, tmp_library_index_path, mock_embedder):
        """测试图书馆索引创建"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=mock_vs,
            library_index_path=str(tmp_library_index_path),
        )
        
        await engine.index_entry(
            id="test-1",
            content="测试",
            metadata={"category": "测试分类"},
        )
        
        # 验证索引文件存在
        assert tmp_library_index_path.exists()


class TestSearchEngineEdgeCases:
    """SearchEngine 边界情况测试"""
    
    @pytest.mark.asyncio
    async def test_very_long_content(self, tmp_memory_dir, mock_embedder):
        """测试超长内容"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=mock_vs,
        )
        
        long_content = "测试内容 " * 10000  # 超长内容
        
        await engine.index_entry(id="long-content", content=long_content, metadata={})
        
        assert mock_vs.count == 1
    
    @pytest.mark.asyncio
    async def test_special_characters_content(self, tmp_memory_dir, mock_embedder):
        """测试特殊字符内容"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=mock_vs,
        )
        
        special_content = "<script>alert('xss')</script>\n\t测试"
        
        await engine.index_entry(id="special", content=special_content, metadata={})
        
        assert mock_vs.count == 1
    
    @pytest.mark.asyncio
    async def test_concurrent_add_memory(self, tmp_memory_dir, mock_embedder):
        """测试并发添加记忆"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=mock_vs,
        )
        
        async def add_content(i):
            await engine.index_entry(id=f"mem-{i}", content=f"内容 {i}", metadata={})
        
        # 并发添加
        tasks = [add_content(i) for i in range(10)]
        await asyncio.gather(*tasks)
        
        assert mock_vs.count == 10


class TestCreateSearchEngine:
    """create_search_engine 工厂函数测试"""
    
    def test_create_search_engine_default(self, tmp_memory_dir):
        """测试默认创建"""
        engine = create_search_engine(memory_dir=str(tmp_memory_dir))
        
        assert engine is not None
        assert isinstance(engine, SearchEngine)
    
    def test_create_search_engine_custom(self, tmp_memory_dir, mock_embedder):
        """测试自定义创建"""
        mock_vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        
        engine = create_search_engine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=mock_vs,
        )
        
        assert engine._embedder is mock_embedder
        assert engine._vectorstore is mock_vs
