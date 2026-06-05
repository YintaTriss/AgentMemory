"""
Embedder Protocol 单元测试

测试 Embedder Provider 的 Protocol 实现：
- Protocol 满足性检查
- MockEmbedder 确定性
- 向量生成正确性
"""

import pytest
import numpy as np
from typing import Protocol, runtime_checkable

from agentmemory.v2_providers import (
    MockEmbedder,
    EmbedderProtocol,
)


class TestEmbedderProtocol:
    """Embedder Protocol 测试"""
    
    def test_mock_embedder_isinstance(self, mock_embedder: MockEmbedder):
        """测试 MockEmbedder 满足 EmbedderProtocol"""
        assert isinstance(mock_embedder, EmbedderProtocol)
    
    def test_embedder_has_embed_method(self, mock_embedder: MockEmbedder):
        """测试 Embedder 有 embed 方法"""
        assert hasattr(mock_embedder, "embed")
        assert callable(mock_embedder.embed)
    
    def test_embedder_has_embed_single_method(self, mock_embedder: MockEmbedder):
        """测试 Embedder 有 embed_single 方法"""
        assert hasattr(mock_embedder, "embed_single")
        assert callable(mock_embedder.embed_single)
    
    def test_embedder_has_dimension_property(self, mock_embedder: MockEmbedder):
        """测试 Embedder 有 dimension 属性"""
        assert hasattr(mock_embedder, "dimension")
        assert isinstance(mock_embedder.dimension, int)
    
    def test_embedder_has_aclose_method(self, mock_embedder: MockEmbedder):
        """测试 Embedder 有 aclose 方法"""
        assert hasattr(mock_embedder, "aclose")
        assert callable(mock_embedder.aclose)


class TestMockEmbedderDeterministic:
    """MockEmbedder 确定性测试"""
    
    def test_same_text_same_vector(self, mock_embedder: MockEmbedder):
        """测试相同文本产生相同向量"""
        text = "test text for determinism"
        
        vector1 = asyncio.run(mock_embedder.embed_single(text))
        vector2 = asyncio.run(mock_embedder.embed_single(text))
        
        np.testing.assert_array_almost_equal(vector1, vector2)
    
    def test_different_text_different_vector(self, mock_embedder: MockEmbedder):
        """测试不同文本产生不同向量"""
        text1 = "first text"
        text2 = "second text"
        
        vector1 = asyncio.run(mock_embedder.embed_single(text1))
        vector2 = asyncio.run(mock_embedder.embed_single(text2))
        
        # 向量应该不完全相等
        assert not np.allclose(vector1, vector2)
    
    def test_batch_consistency(self, mock_embedder: MockEmbedder):
        """测试批量处理一致性"""
        texts = ["text1", "text2", "text3"]
        
        # 单个调用
        vectors_single = []
        for text in texts:
            vectors_single.append(asyncio.run(mock_embedder.embed_single(text)))
        
        # 批量调用
        vectors_batch = asyncio.run(mock_embedder.embed(texts))
        
        # 结果应该一致
        for v_single, v_batch in zip(vectors_single, vectors_batch):
            np.testing.assert_array_almost_equal(v_single, v_batch)


class TestMockEmbedderVector:
    """MockEmbedder 向量测试"""
    
    @pytest.mark.asyncio
    async def test_embed_returns_list(self, mock_embedder: MockEmbedder):
        """测试 embed 返回列表"""
        texts = ["hello", "world"]
        result = await mock_embedder.embed(texts)
        
        assert isinstance(result, list)
        assert len(result) == 2
    
    @pytest.mark.asyncio
    async def test_embed_single_returns_vector(self, mock_embedder: MockEmbedder):
        """测试 embed_single 返回向量"""
        text = "test"
        result = await mock_embedder.embed_single(text)
        
        assert isinstance(result, list)
        assert len(result) == mock_embedder.dimension
    
    @pytest.mark.asyncio
    async def test_vector_normalized(self, mock_embedder: MockEmbedder):
        """测试向量已归一化"""
        text = "normalize test"
        vector = await mock_embedder.embed_single(text)
        
        norm = float(np.linalg.norm(vector))
        assert abs(norm - 1.0) < 1e-6
    
    @pytest.mark.asyncio
    async def test_vector_values_in_range(self, mock_embedder: MockEmbedder):
        """测试向量值在 [-1, 1] 范围内"""
        text = "range test"
        vector = await mock_embedder.embed_single(text)
        
        for val in vector:
            assert -1.0 <= val <= 1.0
    
    @pytest.mark.asyncio
    async def test_empty_texts(self, mock_embedder: MockEmbedder):
        """测试空文本列表"""
        result = await mock_embedder.embed([])
        assert result == []


class TestMockEmbedderContextManager:
    """MockEmbedder 上下文管理器测试"""
    
    @pytest.mark.asyncio
    async def test_context_manager(self, mock_embedder: MockEmbedder):
        """测试上下文管理器"""
        async with mock_embedder:
            vector = await mock_embedder.embed_single("test")
        
        assert isinstance(vector, list)
    
    @pytest.mark.asyncio
    async def test_context_manager_closes(self, mock_embedder: MockEmbedder):
        """测试上下文管理器正确关闭"""
        async with mock_embedder:
            pass
        
        # aclose 应该被调用，不抛出异常
        await mock_embedder.aclose()


class TestMockEmbedderDifferentDimensions:
    """不同维度测试"""
    
    @pytest.mark.asyncio
    async def test_128_dimensions(self):
        """测试 128 维"""
        embedder = MockEmbedder(dimensions=128)
        vector = await embedder.embed_single("test")
        assert len(vector) == 128
    
    @pytest.mark.asyncio
    async def test_512_dimensions(self):
        """测试 512 维"""
        embedder = MockEmbedder(dimensions=512)
        vector = await embedder.embed_single("test")
        assert len(vector) == 512
    
    @pytest.mark.asyncio
    async def test_1024_dimensions(self):
        """测试 1024 维"""
        embedder = MockEmbedder(dimensions=1024)
        vector = await embedder.embed_single("test")
        assert len(vector) == 1024
