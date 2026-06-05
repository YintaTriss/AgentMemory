"""
Embedder Provider 测试

测试所有 Embedder Provider 实现：
- Protocol 满足性
- MockEmbedder 确定性
- 环境变量检测
"""

import pytest
import os
import asyncio
import numpy as np
from unittest.mock import patch, MagicMock

from agentmemory.v2_providers import (
    MockEmbedder,
    OpenAIEmbedder,
    DashScopeEmbedder,
    MiniMaxEmbedder,
    EmbedderProtocol,
)


class TestMockEmbedder:
    """MockEmbedder 完整测试"""
    
    def test_protocol_satisfaction(self):
        """测试满足 EmbedderProtocol"""
        embedder = MockEmbedder()
        assert isinstance(embedder, EmbedderProtocol)
    
    def test_default_dimensions(self):
        """测试默认维度"""
        embedder = MockEmbedder()
        assert embedder.dimension == 1024
    
    def test_custom_dimensions(self):
        """测试自定义维度"""
        embedder = MockEmbedder(dimensions=256)
        assert embedder.dimension == 256
    
    def test_custom_seed(self):
        """测试自定义种子"""
        embedder1 = MockEmbedder(seed=1)
        embedder2 = MockEmbedder(seed=2)
        
        vec1 = asyncio.run(embedder1.embed_single("test"))
        vec2 = asyncio.run(embedder2.embed_single("test"))
        
        # 不同种子产生不同向量
        assert not np.allclose(vec1, vec2)
    
    def test_same_seed_deterministic(self):
        """测试相同种子产生相同向量"""
        embedder1 = MockEmbedder(seed=42)
        embedder2 = MockEmbedder(seed=42)
        
        vec1 = asyncio.run(embedder1.embed_single("test"))
        vec2 = asyncio.run(embedder2.embed_single("test"))
        
        np.testing.assert_array_almost_equal(vec1, vec2)
    
    def test_model_property(self):
        """测试 model 属性"""
        embedder = MockEmbedder()
        assert embedder._model == "mock/hash"
    
    @pytest.mark.asyncio
    async def test_embed_batch(self):
        """测试批量嵌入"""
        embedder = MockEmbedder()
        texts = ["hello", "world", "test"]
        
        vectors = await embedder.embed(texts)
        
        assert len(vectors) == 3
        for vec in vectors:
            assert len(vec) == embedder.dimension
    
    @pytest.mark.asyncio
    async def test_embed_empty_list(self):
        """测试空列表"""
        embedder = MockEmbedder()
        vectors = await embedder.embed([])
        assert vectors == []
    
    @pytest.mark.asyncio
    async def test_cache_works(self):
        """测试缓存生效"""
        embedder = MockEmbedder()
        text = "cached text"
        
        vec1 = await embedder.embed_single(text)
        vec2 = await embedder.embed_single(text)
        
        np.testing.assert_array_almost_equal(vec1, vec2)
    
    @pytest.mark.asyncio
    async def test_aclose(self):
        """测试关闭方法"""
        embedder = MockEmbedder()
        await embedder.aclose()  # 不应该抛出异常


class TestOpenAIEmbedder:
    """OpenAIEmbedder 测试"""
    
    def test_protocol_satisfaction(self):
        """测试满足 EmbedderProtocol"""
        embedder = OpenAIEmbedder(api_key="test-key")
        assert isinstance(embedder, EmbedderProtocol)
    
    def test_default_dimensions(self):
        """测试默认维度"""
        embedder = OpenAIEmbedder()
        assert embedder.dimension == 3072
    
    def test_custom_dimensions(self):
        """测试自定义维度"""
        embedder = OpenAIEmbedder(dimensions=1536)
        assert embedder.dimension == 1536
    
    def test_default_model(self):
        """测试默认模型"""
        embedder = OpenAIEmbedder()
        assert embedder.model == "text-embedding-3-large"
    
    def test_custom_model(self):
        """测试自定义模型"""
        embedder = OpenAIEmbedder(model="text-embedding-3-small")
        assert embedder.model == "text-embedding-3-small"
    
    def test_api_key_from_env(self):
        """测试从环境变量读取 API Key"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-test-key"}):
            embedder = OpenAIEmbedder()
            assert embedder.api_key == "env-test-key"
    
    def test_custom_base_url(self):
        """测试自定义 base URL"""
        embedder = OpenAIEmbedder(base_url="https://custom.api.com/v1")
        assert embedder.base_url == "https://custom.api.com/v1"


class TestDashScopeEmbedder:
    """DashScopeEmbedder 测试"""
    
    def test_protocol_satisfaction(self):
        """测试满足 EmbedderProtocol"""
        embedder = DashScopeEmbedder(api_key="test-key")
        assert isinstance(embedder, EmbedderProtocol)
    
    def test_default_dimensions(self):
        """测试默认维度"""
        embedder = DashScopeEmbedder()
        assert embedder.dimension == 1024
    
    def test_api_key_from_env(self):
        """测试从环境变量读取 API Key"""
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "dashscope-key"}):
            embedder = DashScopeEmbedder()
            assert embedder.api_key == "dashscope-key"
    
    def test_fallback_env_var(self):
        """测试后备环境变量"""
        with patch.dict(os.environ, {"BAILIAN_API_KEY": "bailian-key"}):
            embedder = DashScopeEmbedder()
            assert embedder.api_key == "bailian-key"


class TestMiniMaxEmbedder:
    """MiniMaxEmbedder 测试"""
    
    def test_protocol_satisfaction(self):
        """测试满足 EmbedderProtocol"""
        embedder = MiniMaxEmbedder(api_key="test-key")
        assert isinstance(embedder, EmbedderProtocol)
    
    def test_default_dimensions(self):
        """测试默认维度"""
        embedder = MiniMaxEmbedder()
        assert embedder.dimension == 1024
    
    def test_api_key_from_env(self):
        """测试从环境变量读取 API Key"""
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "minimax-key"}):
            embedder = MiniMaxEmbedder()
            assert embedder.api_key == "minimax-key"


class TestEmbedderFactory:
    """Embedder 工厂测试"""
    
    def test_mock_embedder_instantiation(self):
        """测试创建 MockEmbedder"""
        from agentmemory.v2_providers import get_embedder
        
        with patch.dict(os.environ, {}, clear=True):
            embedder = get_embedder("mock")
            assert isinstance(embedder, MockEmbedder)
    
    def test_list_providers(self):
        """测试列出可用 Provider"""
        from agentmemory.v2_providers import list_available_providers
        
        providers = list_available_providers()
        assert "mock" in providers
        assert "openai" in providers
        assert "dashscope" in providers
        assert "minimax" in providers
