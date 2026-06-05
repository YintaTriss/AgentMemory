"""
AgentMemory v2.0 - Provider 单元测试

测试 Provider 抽象层：
- MockEmbedder
- MockLLMProvider  
- MockVectorStore
- Provider 自动检测
"""

import sys
import os
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

import pytest

# Add source path
sys.path.insert(0, "C:/Users/31683/AppData/Local/Programs/SpectrAI/2026.6.5.13.09")

from agentmemory.providers.protocols import (
    VectorEntry,
    SearchResult,
    LLMResponse,
)
from agentmemory.providers.embedder import (
    MockEmbedder,
    _hash_to_vector,
    get_embedder,
)
from agentmemory.providers.llm import (
    MockLLMProvider,
    get_llm_provider,
    LLMResponse,
)
from agentmemory.providers.vectorstore import (
    MockVectorStore,
    get_vectorstore,
)
from agentmemory.providers.registry import ProviderRegistry, get_registry


class TestMockEmbedder:
    """MockEmbedder 测试"""
    
    def test_deterministic_hash(self):
        """测试 hash 的确定性"""
        text = "Hello, World!"
        dims = 384
        
        vec1 = _hash_to_vector(text, dims)
        vec2 = _hash_to_vector(text, dims)
        
        assert vec1 == vec2
        assert len(vec1) == dims
    
    def test_different_texts(self):
        """测试不同文本产生不同向量"""
        text1 = "Hello"
        text2 = "World"
        dims = 384
        
        vec1 = _hash_to_vector(text1, dims)
        vec2 = _hash_to_vector(text2, dims)
        
        # 不同文本大概率产生不同向量
        assert vec1 != vec2
    
    def test_embedder_basic(self):
        """测试 MockEmbedder 基本功能"""
        embedder = MockEmbedder(dimensions=256)
        
        vector = embedder.embed("test text")
        
        assert len(vector) == 256
        # 验证是单位向量
        import math
        magnitude = math.sqrt(sum(v * v for v in vector))
        assert abs(magnitude - 1.0) < 0.001
    
    def test_embedder_empty_text(self):
        """测试空文本"""
        embedder = MockEmbedder()
        
        vector = embedder.embed("")
        
        assert len(vector) == 384
        assert all(v == 0.0 for v in vector)
    
    def test_embed_batch(self):
        """测试批量嵌入"""
        embedder = MockEmbedder(dimensions=128)
        
        texts = ["hello", "world", "test"]
        vectors = embedder.embed_batch(texts)
        
        assert len(vectors) == 3
        for vec in vectors:
            assert len(vec) == 128
    
    @pytest.mark.asyncio
    async def test_embed_async(self):
        """测试异步嵌入"""
        embedder = MockEmbedder()
        
        vector = await embedder.embed_async("async test")
        
        assert len(vector) == 384


class TestMockLLMProvider:
    """MockLLM Provider 测试"""
    
    def test_chat_sync(self):
        """测试同步聊天"""
        provider = MockLLMProvider()
        
        messages = [{"role": "user", "content": "Hello"}]
        response = provider.chat(messages)
        
        assert isinstance(response, LLMResponse)
        assert "Hello" in response.content
    
    @pytest.mark.asyncio
    async def test_chat_async(self):
        """测试异步聊天"""
        provider = MockLLMProvider(
            response_template="Response to: {query}"
        )
        
        messages = [{"role": "user", "content": "What is AI?"}]
        response = await provider.chat_async(messages)
        
        assert isinstance(response, LLMResponse)
        assert "What is AI?" in response.content
    
    @pytest.mark.asyncio
    async def test_stream(self):
        """测试流式输出"""
        provider = MockLLMProvider(
            response_template="Streaming response"
        )
        
        chunks = []
        async for chunk in provider.stream_complete("test"):
            chunks.append(chunk)
        
        full_response = "".join(chunks)
        assert "Streaming response" in full_response


class TestMockVectorStore:
    """MockVectorStore 测试"""
    
    def test_upsert_and_search(self):
        """测试写入和搜索"""
        store = MockVectorStore(dimensions=128)
        
        entries = [
            VectorEntry(
                id="1",
                vector=[0.1] * 128,
                metadata={"content": "test 1", "tags": ["a"]},
            ),
            VectorEntry(
                id="2",
                vector=[0.2] * 128,
                metadata={"content": "test 2", "tags": ["b"]},
            ),
        ]
        
        store.upsert(entries)
        assert store.count == 2
        
        # 搜索
        results = store.search([0.1] * 128, limit=2)
        
        assert len(results) == 2
        assert results[0].id == "1"  # 最相似的
    
    @pytest.mark.asyncio
    async def test_async_operations(self):
        """测试异步操作"""
        store = MockVectorStore(dimensions=64)
        
        entry = VectorEntry(
            id="async-1",
            vector=[0.5] * 64,
            metadata={"content": "async test"},
        )
        
        await store.upsert_async([entry])
        assert store.count == 1
        
        results = await store.search_async([0.5] * 64, limit=1)
        
        assert len(results) == 1
        assert results[0].id == "async-1"
    
    def test_delete(self):
        """测试删除"""
        store = MockVectorStore(dimensions=32)
        
        entry = VectorEntry(id="to-delete", vector=[0.1] * 32)
        store.upsert([entry])
        
        assert store.count == 1
        
        store.delete(["to-delete"])
        
        assert store.count == 0


class TestProviderAutoDetection:
    """Provider 自动检测测试"""
    
    def test_embedder_auto_detection_mock(self):
        """测试无 API Key 时使用 Mock"""
        # 确保没有 API Key
        env_to_clear = ["OPENAI_API_KEY", "DASHSCOPE_API_KEY", "MINIMAX_API_KEY"]
        original = {k: os.environ.pop(k, None) for k in env_to_clear}
        
        try:
            embedder = get_embedder()
            assert isinstance(embedder, MockEmbedder)
        finally:
            # 恢复环境变量
            for k, v in original.items():
                if v:
                    os.environ[k] = v
    
    def test_llm_auto_detection_mock(self):
        """测试 LLM 无 API Key 时使用 Mock"""
        env_to_clear = ["OPENAI_API_KEY", "DASHSCOPE_API_KEY", "MINIMAX_API_KEY"]
        original = {k: os.environ.pop(k, None) for k in env_to_clear}
        
        try:
            provider = get_llm_provider()
            assert isinstance(provider, MockLLMProvider)
        finally:
            for k, v in original.items():
                if v:
                    os.environ[k] = v
    
    def test_explicit_provider(self):
        """测试显式指定 Provider"""
        embedder = get_embedder(provider="mock", dimensions=64)
        assert isinstance(embedder, MockEmbedder)
        assert embedder.dimensions == 64
        
        provider = get_llm_provider(provider="mock")
        assert isinstance(provider, MockLLMProvider)


class TestProviderRegistry:
    """ProviderRegistry 测试"""
    
    def test_singleton(self):
        """测试单例模式"""
        registry1 = get_registry()
        registry2 = get_registry()
        
        assert registry1 is registry2
    
    def test_configure(self):
        """测试配置"""
        registry = ProviderRegistry()
        registry.configure(
            embedder={"dimensions": 512},
            llm={"model": "custom-model"},
        )
        
        embedder = registry.get_embedder()
        assert embedder.dimensions == 512
        
        llm = registry.get_llm()
        assert llm.model == "custom-model"
    
    def test_reset(self):
        """测试重置"""
        registry = ProviderRegistry()
        registry.configure(embedder={"dimensions": 128})
        
        registry.reset()  # 应该不抛出异常


class TestIntegration:
    """集成测试"""
    
    def test_embedder_vectorstore_pipeline(self):
        """测试 Embedder → VectorStore 流水线"""
        # 创建 Mock Embedder
        embedder = MockEmbedder(dimensions=128)
        
        # 创建 Mock VectorStore
        vectorstore = MockVectorStore(dimensions=128)
        
        # 文本 → 向量 → 存储
        texts = ["apple fruit", "banana yellow", "carrot orange"]
        
        vectors = embedder.embed_batch(texts)
        entries = [
            VectorEntry(id=f"doc-{i}", vector=vec, metadata={"content": text})
            for i, (text, vec) in enumerate(zip(texts, vectors))
        ]
        
        vectorstore.upsert(entries)
        
        # 查询
        query = "yellow fruit"
        query_vec = embedder.embed(query)
        
        results = vectorstore.search(query_vec, limit=2)
        
        assert len(results) == 2
        # "apple fruit" 和 "banana yellow" 都与 "yellow fruit" 相关
        assert results[0].id in ["doc-0", "doc-1"]
    
    @pytest.mark.asyncio
    async def test_async_pipeline(self):
        """测试异步流水线"""
        embedder = MockEmbedder(dimensions=64)
        vectorstore = MockVectorStore(dimensions=64)
        
        # 异步生成向量
        texts = ["async test 1", "async test 2"]
        vectors = await embedder.embed_batch_async(texts)
        
        # 异步存储
        entries = [
            VectorEntry(id=f"async-{i}", vector=vec)
            for i, vec in enumerate(vectors)
        ]
        await vectorstore.upsert_async(entries)
        
        # 异步搜索
        query_vec = await embedder.embed_async("async")
        results = await vectorstore.search_async(query_vec, limit=5)
        
        assert len(results) == 2
