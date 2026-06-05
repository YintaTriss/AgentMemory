"""
Embedder Provider 测试

测试所有 Embedder Provider 实现：
- MockEmbedder
- get_embedder 工厂函数
- Protocol 接口满足性
"""

import os
import sys
import asyncio
from pathlib import Path
from typing import Protocol

import pytest

# 添加 agentmemory 路径
AGENTMEMORY_SRC = Path(__file__).parent.parent.parent / "agentmemory"
if str(AGENTMEMORY_SRC) not in sys.path:
    sys.path.insert(0, str(AGENTMEMORY_SRC))

from agentmemory.providers.embedder import (
    MockEmbedder,
    get_embedder,
)
from agentmemory.providers.protocols import BaseEmbedderProvider


class TestMockEmbedderBasics:
    """MockEmbedder 基础测试"""
    
    def test_embedder_initialization_default(self):
        """测试默认初始化"""
        embedder = MockEmbedder()
        
        assert embedder.dimensions == 384
        assert embedder.model == "mock-hash-v1"
    
    def test_embedder_initialization_custom(self):
        """测试自定义初始化"""
        embedder = MockEmbedder(dimensions=768, model="custom-model")
        
        assert embedder.dimensions == 768
        assert embedder.model == "custom-model"
    
    def test_embedder_properties(self):
        """测试属性访问"""
        embedder = MockEmbedder(dimensions=1536)
        
        assert isinstance(embedder.dimensions, int)
        assert isinstance(embedder.model, str)
        assert embedder.dimensions == 1536


class TestMockEmbedderDeterminism:
    """MockEmbedder 确定性测试"""
    
    def test_same_text_same_vector(self, mock_embedder):
        """相同文本产生相同向量"""
        text = "这是一段测试文本"
        
        vec1 = mock_embedder.embed(text)
        vec2 = mock_embedder.embed(text)
        
        assert vec1 == vec2
    
    def test_different_text_different_vector(self, mock_embedder):
        """不同文本产生不同向量"""
        text1 = "第一段文本"
        text2 = "第二段文本"
        
        vec1 = mock_embedder.embed(text1)
        vec2 = mock_embedder.embed(text2)
        
        assert vec1 != vec2
    
    def test_vector_normalized(self, mock_embedder):
        """向量已归一化"""
        import math
        
        text = "测试文本"
        vec = mock_embedder.embed(text)
        
        # 计算 L2 范数
        magnitude = math.sqrt(sum(v * v for v in vec))
        
        # 归一化后范数应该接近 1
        assert abs(magnitude - 1.0) < 1e-6
    
    def test_empty_text_vector(self, mock_embedder):
        """空文本返回零向量"""
        vec = mock_embedder.embed("")
        
        assert len(vec) == mock_embedder.dimensions
        assert all(v == 0.0 for v in vec)
    
    def test_vector_length_matches_dimensions(self, mock_embedder):
        """向量长度等于维度"""
        vec = mock_embedder.embed("测试")
        
        assert len(vec) == mock_embedder.dimensions
    
    def test_unicode_text(self, mock_embedder):
        """Unicode 文本处理"""
        texts = [
            "中文测试",
            "日本語テスト",
            "🎉 emoji 测试",
            "Mixed 中文 and English",
        ]
        
        for text in texts:
            vec = mock_embedder.embed(text)
            assert len(vec) == mock_embedder.dimensions
            # 不同文本应该产生不同的向量
            if text != texts[0]:
                assert mock_embedder.embed(texts[0]) != vec


class TestMockEmbedderBatch:
    """MockEmbedder 批量操作测试"""
    
    def test_embed_batch_empty(self, mock_embedder):
        """批量嵌入空列表"""
        result = mock_embedder.embed_batch([])
        
        assert result == []
    
    def test_embed_batch_single(self, mock_embedder):
        """批量嵌入单个文本"""
        texts = ["单个文本"]
        result = mock_embedder.embed_batch(texts)
        
        assert len(result) == 1
        assert result[0] == mock_embedder.embed(texts[0])
    
    def test_embed_batch_multiple(self, mock_embedder):
        """批量嵌入多个文本"""
        texts = ["文本1", "文本2", "文本3"]
        result = mock_embedder.embed_batch(texts)
        
        assert len(result) == 3
        for i, text in enumerate(texts):
            assert result[i] == mock_embedder.embed(text)
    
    def test_embed_batch_consistency(self, mock_embedder):
        """批量嵌入与单独嵌入一致"""
        texts = ["测试1", "测试2", "测试3"]
        
        batch_result = mock_embedder.embed_batch(texts)
        individual_results = [mock_embedder.embed(t) for t in texts]
        
        assert batch_result == individual_results


class TestMockEmbedderAsync:
    """MockEmbedder 异步操作测试"""
    
    @pytest.mark.asyncio
    async def test_embed_async(self, mock_embedder):
        """异步单文本嵌入"""
        text = "异步测试文本"
        
        result = await mock_embedder.embed_async(text)
        expected = mock_embedder.embed(text)
        
        assert result == expected
    
    @pytest.mark.asyncio
    async def test_embed_batch_async(self, mock_embedder):
        """异步批量嵌入"""
        texts = ["文本1", "文本2", "文本3"]
        
        result = await mock_embedder.embed_batch_async(texts)
        expected = mock_embedder.embed_batch(texts)
        
        assert result == expected
    
    @pytest.mark.asyncio
    async def test_async_empty_batch(self, mock_embedder):
        """异步批量嵌入空列表"""
        result = await mock_embedder.embed_batch_async([])
        
        assert result == []


class TestEmbedderProtocol:
    """Embedder Protocol 接口测试"""
    
    def test_mock_embedder_implements_protocol(self, mock_embedder):
        """MockEmbedder 实现 Protocol"""
        assert isinstance(mock_embedder, BaseEmbedderProvider)
    
    def test_protocol_methods_exist(self, mock_embedder):
        """Protocol 方法存在"""
        assert hasattr(mock_embedder, 'embed')
        assert hasattr(mock_embedder, 'embed_async')
        assert hasattr(mock_embedder, 'embed_batch')
        assert hasattr(mock_embedder, 'embed_batch_async')
    
    def test_protocol_properties_exist(self, mock_embedder):
        """Protocol 属性存在"""
        assert hasattr(mock_embedder, 'dimensions')
        assert hasattr(mock_embedder, 'model')


class TestGetEmbedderFactory:
    """get_embedder 工厂函数测试"""
    
    def test_get_mock_embedder_explicit(self):
        """显式指定 mock provider"""
        embedder = get_embedder(provider="mock")
        
        assert isinstance(embedder, MockEmbedder)
    
    def test_get_hash_embedder(self):
        """获取 hash embedder"""
        embedder = get_embedder(provider="hash")
        
        assert isinstance(embedder, MockEmbedder)
    
    def test_get_fake_embedder(self):
        """获取 fake embedder"""
        embedder = get_embedder(provider="fake")
        
        assert isinstance(embedder, MockEmbedder)
    
    def test_get_embedder_custom_dimensions(self):
        """自定义维度"""
        embedder = get_embedder(provider="mock", dimensions=512)
        
        assert isinstance(embedder, MockEmbedder)
        assert embedder.dimensions == 512
    
    def test_get_embedder_no_env_vars(self, monkeypatch):
        """无环境变量时使用 mock"""
        # 清除可能存在的环境变量
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
        
        embedder = get_embedder()
        
        assert isinstance(embedder, MockEmbedder)
    
    def test_get_embedder_openai_env(self, monkeypatch):
        """OPENAI_API_KEY 环境变量"""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
        
        # 应该返回 OpenAI Embedder (如果有 API key)
        embedder = get_embedder()
        assert isinstance(embedder, BaseEmbedderProvider)
    
    def test_get_embedder_dashscope_env(self, monkeypatch):
        """DASHSCOPE_API_KEY 环境变量"""
        monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
        
        embedder = get_embedder()
        assert isinstance(embedder, BaseEmbedderProvider)
    
    def test_get_embedder_minimax_env(self, monkeypatch):
        """MINIMAX_API_KEY 环境变量"""
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        
        embedder = get_embedder()
        assert isinstance(embedder, BaseEmbedderProvider)


class TestEmbedderEdgeCases:
    """Embedder 边界情况测试"""
    
    def test_very_long_text(self, mock_embedder):
        """超长文本"""
        text = "测试" * 10000  # 很长的文本
        
        vec = mock_embedder.embed(text)
        
        assert len(vec) == mock_embedder.dimensions
    
    def test_special_characters(self, mock_embedder):
        """特殊字符"""
        texts = [
            "<script>alert('xss')</script>",
            "文本 with\nnewline\tand\ttab",
            "emoji: 🎉🎊🎁🎄🎅",
            "math: ∑∏∫∂∇",
        ]
        
        for text in texts:
            vec = mock_embedder.embed(text)
            assert len(vec) == mock_embedder.dimensions
    
    def test_large_batch(self, mock_embedder):
        """大批量处理"""
        texts = [f"文本{i}" for i in range(1000)]
        
        result = mock_embedder.embed_batch(texts)
        
        assert len(result) == 1000
        for vec in result:
            assert len(vec) == mock_embedder.dimensions
    
    def test_batch_with_empty_strings(self, mock_embedder):
        """批量中包含空字符串"""
        texts = ["文本1", "", "文本2"]
        
        result = mock_embedder.embed_batch(texts)
        
        assert len(result) == 3
        assert all(len(v) == mock_embedder.dimensions for v in result)


class TestEmbedderReproducibility:
    """Embedder 可重现性测试"""
    
    def test_multiple_instances_same_result(self):
        """多个实例产生相同结果"""
        text = "可重现性测试"
        
        embedder1 = MockEmbedder(dimensions=384)
        embedder2 = MockEmbedder(dimensions=384)
        
        vec1 = embedder1.embed(text)
        vec2 = embedder2.embed(text)
        
        assert vec1 == vec2
    
    def test_cross_session_reproducibility(self):
        """跨会话可重现"""
        text = "跨会话测试"
        
        # 模拟两次独立的会话
        vec1 = MockEmbedder(384).embed(text)
        vec2 = MockEmbedder(384).embed(text)
        
        assert vec1 == vec2
