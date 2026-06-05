"""
Embedder Factory - Embedder 对象工厂

用于创建测试中使用的 Embedder 对象。
"""

import asyncio
import hashlib
from typing import Optional
from unittest.mock import AsyncMock, Mock

from agentmemory.providers.protocols import BaseEmbedderProvider


class EmbedderFactory:
    """
    Embedder 工厂类
    
    提供便捷的方法来创建测试用的 Embedder 对象。
    """
    
    @staticmethod
    def create_hash_vector(text: str, dimensions: int = 384) -> list[float]:
        """
        创建确定性 hash 向量
        
        Args:
            text: 输入文本
            dimensions: 向量维度
            
        Returns:
            归一化的向量
        """
        hash_bytes = hashlib.sha256(text.encode("utf-8")).digest()
        vector = []
        for i in range(dimensions):
            byte_idx = (i * 2) % len(hash_bytes)
            high_byte = hash_bytes[byte_idx]
            low_byte = hash_bytes[(byte_idx + 1) % len(hash_bytes)]
            value = ((high_byte << 8) | low_byte) / 65535.0
            vector.append(value)
        
        # L2 归一化
        magnitude = sum(v * v for v in vector) ** 0.5
        if magnitude > 0:
            vector = [v / magnitude for v in vector]
        
        return vector
    
    @staticmethod
    def create_random_vector(dimensions: int = 384, seed: Optional[int] = None) -> list[float]:
        """
        创建随机向量
        
        Args:
            dimensions: 向量维度
            seed: 随机种子（用于可重现性）
            
        Returns:
            归一化的随机向量
        """
        import random
        
        if seed is not None:
            random.seed(seed)
        
        vector = [random.random() for _ in range(dimensions)]
        
        # L2 归一化
        magnitude = sum(v * v for v in vector) ** 0.5
        if magnitude > 0:
            vector = [v / magnitude for v in vector]
        
        return vector
    
    @staticmethod
    def create_similar_vector(
        base_vector: list[float],
        noise_scale: float = 0.1,
        seed: Optional[int] = None,
    ) -> list[float]:
        """
        创建与基准向量相似的带噪声向量
        
        Args:
            base_vector: 基准向量
            noise_scale: 噪声强度
            seed: 随机种子
            
        Returns:
            相似向量
        """
        import random
        import math
        
        if seed is not None:
            random.seed(seed)
        
        vector = []
        for v in base_vector:
            noise = random.uniform(-noise_scale, noise_scale)
            new_v = v + noise
            vector.append(new_v)
        
        # L2 归一化
        magnitude = math.sqrt(sum(x * x for x in vector))
        if magnitude > 0:
            vector = [v / magnitude for v in vector]
        
        return vector
    
    @staticmethod
    def create_orthogonal_vector(base_vector: list[float]) -> list[float]:
        """
        创建与基准向量正交的向量
        
        Args:
            base_vector: 基准向量
            
        Returns:
            正交向量
        """
        import random
        import math
        
        dimensions = len(base_vector)
        
        # 随机方向
        vector = [random.random() - 0.5 for _ in range(dimensions)]
        
        # Gram-Schmidt 正交化
        dot_product = sum(b * v for b, v in zip(base_vector, vector))
        vector = [v - dot_product * b for b, v in zip(base_vector, vector)]
        
        # L2 归一化
        magnitude = math.sqrt(sum(x * x for x in vector))
        if magnitude > 0:
            vector = [v / magnitude for v in vector]
        
        return vector
    
    @classmethod
    def create_mock_embedder(
        cls,
        dimensions: int = 384,
        model: str = "mock-embedder-v1",
    ) -> "MockEmbedder":
        """
        创建 MockEmbedder
        
        Args:
            dimensions: 向量维度
            model: 模型名称
            
        Returns:
            MockEmbedder 实例
        """
        return MockEmbedder(dimensions=dimensions, model=model)
    
    @classmethod
    def create_async_mock(cls) -> AsyncMock:
        """
        创建异步 Mock Embedder
        
        Returns:
            AsyncMock 对象
        """
        mock = AsyncMock()
        mock.embed = AsyncMock()
        mock.embed_batch = AsyncMock()
        mock.embed_async = AsyncMock()
        mock.embed_batch_async = AsyncMock()
        return mock


class MockEmbedder:
    """
    Mock Embedder 实现
    
    用于测试的确定性 Embedder。
    """
    
    def __init__(self, dimensions: int = 384, model: str = "mock-embedder-v1"):
        self._dimensions = dimensions
        self._model = model
    
    @property
    def dimensions(self) -> int:
        return self._dimensions
    
    @property
    def model(self) -> str:
        return self._model
    
    def embed(self, text: str) -> list[float]:
        """单文本嵌入"""
        return EmbedderFactory.create_hash_vector(text, self._dimensions)
    
    async def embed_async(self, text: str) -> list[float]:
        """异步单文本嵌入"""
        await asyncio.sleep(0)
        return self.embed(text)
    
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量文本嵌入"""
        if not texts:
            return []
        return [self.embed(text) for text in texts]
    
    async def embed_batch_async(self, texts: list[str]) -> list[list[float]]:
        """异步批量文本嵌入"""
        await asyncio.sleep(0)
        return self.embed_batch(texts)
