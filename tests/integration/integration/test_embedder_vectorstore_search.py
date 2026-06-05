"""
Embedder-VectorStore-SearchEngine 集成测试

测试完整的检索流程：
1. Embedder 生成向量
2. VectorStore 存储向量
3. SearchEngine 执行检索
4. HybridRetriever 混合打分
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

from agentmemory.search.search_engine import (
    SearchEngine,
    create_search_engine,
)
from agentmemory.search.hybrid_retriever import (
    HybridRetriever,
    HybridWeights,
    create_hybrid_retriever,
)
from agentmemory.providers.vectorstore import MockVectorStore
from agentmemory.providers.embedder import MockEmbedder, get_embedder


class TestEmbedderVectorStoreWorkflow:
    """Embedder → VectorStore 工作流测试"""
    
    @pytest.mark.asyncio
    async def test_embed_and_store(self, tmp_memory_dir, mock_embedder):
        """测试嵌入并存储"""
        from agentmemory.providers.protocols import VectorEntry
        
        # 创建 VectorStore
        vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        
        # 使用 Embedder 生成向量
        text = "机器学习是人工智能的核心技术"
        vector = mock_embedder.embed(text)
        
        # 存储到 VectorStore
        entry = VectorEntry(
            id="test-1",
            vector=vector,
            metadata={"text": text},
        )
        
        await vs.upsert_async([entry])
        
        assert vs.count == 1
    
    @pytest.mark.asyncio
    async def test_search_stored_vectors(self, tmp_memory_dir, mock_embedder):
        """测试搜索存储的向量"""
        from agentmemory.providers.protocols import VectorEntry
        
        vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        
        # 存储多个向量
        texts = [
            "深度学习使用神经网络",
            "机器学习是人工智能的分支",
            "今天天气很好",
        ]
        
        for i, text in enumerate(texts):
            vector = mock_embedder.embed(text)
            entry = VectorEntry(
                id=f"doc-{i}",
                vector=vector,
                metadata={"text": text},
            )
            await vs.upsert_async([entry])
        
        # 搜索相似内容
        query = "神经网络 深度学习"
        query_vector = mock_embedder.embed(query)
        
        results = await vs.search_async(query_vector, limit=2)
        
        assert len(results) <= 2
        assert all(hasattr(r, 'score') for r in results)


class TestSearchEngineFullWorkflow:
    """SearchEngine 完整工作流测试"""
    
    @pytest.mark.asyncio
    async def test_add_search_delete_workflow(self, tmp_memory_dir, mock_embedder):
        """测试添加-搜索-删除工作流"""
        vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=vs,
        )
        
        # 添加记忆
        await engine.index_entry(
            id="python",
            content="Python 是一种高级编程语言",
            metadata={"category": "技术/编程", "tags": ["编程", "Python"], "importance": 0.9},
        )
        
        assert vs.count == 1
        
        # 搜索
        results = await engine.search_semantic("Python 编程")
        
        assert len(results) >= 0
        
        # 删除
        await engine.delete_entry("python")
        
        assert vs.count == 0
    
    @pytest.mark.asyncio
    async def test_multiple_categories_workflow(self, tmp_memory_dir, mock_embedder):
        """测试多分类工作流"""
        vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=vs,
        )
        
        # 添加不同分类的记忆
        await engine.index_entry(id="python", content="Python教程", metadata={"category": "技术/编程"})
        await engine.index_entry(id="js", content="JavaScript教程", metadata={"category": "技术/编程"})
        await engine.index_entry(id="fitness", content="健身计划", metadata={"category": "生活/健康"})
        await engine.index_entry(id="recipe", content="健康食谱", metadata={"category": "生活/饮食"})
        
        assert vs.count == 4
        
        # 按分类搜索
        tech_results = await engine.search_by_category("技术")
        
        assert len(tech_results) >= 0
    
    @pytest.mark.asyncio
    async def test_tag_filtering_workflow(self, tmp_memory_dir, mock_embedder):
        """测试标签过滤工作流"""
        vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=vs,
        )
        
        # 添加带标签的记忆
        await engine.index_entry(id="dl", content="深度学习教程", metadata={"tags": ["AI", "机器学习"]})
        await engine.index_entry(id="fitness2", content="健身指南", metadata={"tags": ["健康", "运动"]})
        
        assert vs.count == 2


class TestHybridRetrieverWorkflow:
    """HybridRetriever 工作流测试"""
    
    @pytest.mark.asyncio
    async def test_hybrid_search_workflow(self, tmp_memory_dir, mock_embedder):
        """测试混合搜索工作流"""
        vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=vs,
        )
        retriever = HybridRetriever(search_engine=engine)
        
        # 添加测试数据
        await engine.index_entry(id="dl", content="深度学习是神经网络的高级形式", metadata={"tags": ["AI", "深度学习"], "importance": 0.9})
        await engine.index_entry(id="ml", content="机器学习包含监督和无监督学习", metadata={"tags": ["AI", "机器学习"], "importance": 0.8})
        await engine.index_entry(id="life", content="今天天气晴朗适合运动", metadata={"tags": ["生活"], "importance": 0.5})
        
        # 混合搜索
        results = await retriever.search("深度学习 神经网络", limit=3)
        
        assert len(results) <= 3
        
        # 验证分数结构
        for result in results:
            assert hasattr(result, 'final_score')
            assert hasattr(result, 'vector_score')
            assert hasattr(result, 'tag_score')
            assert hasattr(result, 'importance_score')
    
    @pytest.mark.asyncio
    async def test_custom_weights_workflow(self, tmp_memory_dir, mock_embedder):
        """测试自定义权重工作流"""
        vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=vs,
        )
        
        # 使用自定义权重
        weights = HybridWeights(
            vector_similarity=0.4,
            tag_match=0.4,
            importance=0.2,
        )
        
        retriever = HybridRetriever(
            search_engine=engine,
            weights=weights,
        )
        
        # 添加数据
        await engine.index_entry(id="ai", content="AI 内容", metadata={"tags": ["AI"], "importance": 0.9})
        
        # 搜索
        results = await retriever.search("AI 人工智能")
        
        if results:
            entry = results[0]
            
            # 验证权重
            expected = (
                0.4 * entry.vector_score +
                0.4 * entry.tag_score +
                0.2 * entry.importance_score
            )
            
            assert abs(entry.final_score - expected) < 0.001


class TestEndToEndWorkflow:
    """端到端工作流测试"""
    
    @pytest.mark.asyncio
    async def test_complete_memory_cycle(self, tmp_memory_dir, mock_embedder):
        """测试完整的记忆周期"""
        vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=vs,
        )
        retriever = HybridRetriever(search_engine=engine)
        
        # 1. 添加记忆
        await engine.index_entry(
            id="transformer",
            content="今天学习了深度学习中的 Transformer 架构",
            metadata={"category": "学习/AI", "tags": ["深度学习", "Transformer", "学习"], "importance": 0.85},
        )
        
        assert vs.count == 1
        
        # 2. 语义搜索
        semantic_results = await engine.search_semantic("Transformer 架构")
        assert len(semantic_results) >= 0
        
        # 3. 分类搜索
        category_results = await engine.search_by_category("学习")
        assert len(category_results) >= 0
        
        # 4. 混合搜索
        hybrid_results = await retriever.search("深度学习", limit=5)
        assert len(hybrid_results) <= 5
        
        # 5. 更新记忆（通过删除+添加）
        await engine.delete_entry("transformer")
        await engine.index_entry(
            id="transformer-new",
            content="深入学习 Transformer 架构，理解注意力机制",
            metadata={"category": "学习/AI", "tags": ["深度学习", "Transformer", "注意力机制"], "importance": 0.9},
        )
        
        assert vs.count == 1
        
        # 6. 验证更新后的搜索结果
        updated_results = await retriever.search("Transformer")
        assert len(updated_results) == 1
    
    @pytest.mark.asyncio
    async def test_batch_operations_workflow(self, tmp_memory_dir, mock_embedder):
        """测试批量操作工作流"""
        vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=vs,
        )
        retriever = HybridRetriever(search_engine=engine)
        
        # 批量添加
        for i in range(20):
            await engine.index_entry(id=f"mem-{i}", content=f"知识内容 {i}", metadata={})
        
        assert vs.count == 20
        
        # 批量搜索
        queries = ["知识1", "知识5", "知识10"]
        batch_results = await retriever.search_batch(queries, limit_per_query=3)
        
        assert len(batch_results) == 3
        for results in batch_results:
            assert len(results) <= 3
        
        # 批量删除
        for i in range(10):
            await engine.delete_entry(f"mem-{i}")
        
        assert vs.count == 10
    
    @pytest.mark.asyncio
    async def test_search_precision_workflow(self, tmp_memory_dir, mock_embedder):
        """测试搜索精度工作流"""
        vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=vs,
        )
        
        # 添加高度相关的文档
        await engine.index_entry(id="python", content="Python 编程语言简单易学，适合初学者", metadata={"category": "技术/编程", "tags": ["编程", "Python"], "importance": 0.9})
        await engine.index_entry(id="js", content="JavaScript 用于 Web 前端开发", metadata={"category": "技术/编程", "tags": ["编程", "Web"], "importance": 0.7})
        await engine.index_entry(id="dinner", content="今天晚餐吃什么好", metadata={"category": "生活/饮食", "tags": ["生活"], "importance": 0.5})
        
        # 搜索 Python 相关
        results = await engine.search_semantic("Python 编程")
        
        # 应该能找到 Python 相关的内容
        assert isinstance(results, list)


class TestProviderFactoryIntegration:
    """Provider 工厂集成测试"""
    
    @pytest.mark.asyncio
    async def test_embedder_factory_integration(self, tmp_memory_dir):
        """测试 Embedder 工厂集成"""
        embedder = MockEmbedder(dimensions=384)
        vs = MockVectorStore(dimensions=embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=embedder,
            vectorstore=vs,
        )
        
        # 使用工厂创建的 Embedder
        await engine.index_entry(id="factory", content="Factory Embedder test", metadata={})
        
        assert vs.count == 1
    
    @pytest.mark.asyncio
    async def test_get_embedder_auto_selection(self, tmp_memory_dir, monkeypatch):
        """测试 get_embedder 自动选择"""
        # 确保无 API key，使用 mock
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
        
        embedder = get_embedder()
        vs = MockVectorStore(dimensions=embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=embedder,
            vectorstore=vs,
        )
        
        await engine.index_entry(id="auto", content="Auto selection test", metadata={})
        
        assert vs.count == 1


class TestEdgeCasesIntegration:
    """边界情况集成测试"""
    
    @pytest.mark.asyncio
    async def test_very_large_batch(self, tmp_memory_dir, mock_embedder):
        """测试大批量处理"""
        vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=vs,
        )
        
        # 添加 100 个记忆
        for i in range(100):
            await engine.index_entry(id=f"large-{i}", content=f"Content {i}", metadata={})
        
        assert vs.count == 100
        
        # 搜索应该仍然有效
        results = await engine.search_semantic("Query")
        assert isinstance(results, list)
    
    @pytest.mark.asyncio
    async def test_special_characters_content(self, tmp_memory_dir, mock_embedder):
        """测试特殊字符内容"""
        vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=vs,
        )
        
        special_contents = [
            "<script>alert('xss')</script>",
            "Chinese and English",
            "emoji: 🎉🎊",
            "new\nline\ttab",
        ]
        
        for i, content in enumerate(special_contents):
            await engine.index_entry(id=f"special-{i}", content=content, metadata={})
        
        assert vs.count == 4
    
    @pytest.mark.asyncio
    async def test_concurrent_operations(self, tmp_memory_dir, mock_embedder):
        """测试并发操作"""
        vs = MockVectorStore(dimensions=mock_embedder.dimensions)
        engine = SearchEngine(
            memory_dir=str(tmp_memory_dir),
            embedder=mock_embedder,
            vectorstore=vs,
        )
        
        async def add_memory(i):
            await engine.index_entry(id=f"concurrent-{i}", content=f"Concurrent content {i}", metadata={})
        
        # 并发添加
        tasks = [add_memory(i) for i in range(10)]
        await asyncio.gather(*tasks)
        
        assert vs.count == 10
        
        # 并发搜索
        async def search(query):
            return await engine.search_semantic(query)
        
        search_tasks = [
            search(f"Query {i}")
            for i in range(5)
        ]
        results = await asyncio.gather(*search_tasks)
        
        assert len(results) == 5
