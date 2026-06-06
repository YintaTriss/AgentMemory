"""
Embedder Module - 向量嵌入抽象与实现

提供：
- Embedder 抽象基类
- HashEmbedder: 零依赖确定性哈希嵌入（默认）
- DashScopeEmbedder: 阿里云百炼 API 嵌入
- get_embedder() 工厂函数
"""

from __future__ import annotations

import hashlib
import json
import os
from abc import ABC, abstractmethod
from typing import Optional

import numpy as np


# ============================================================================
# Abstract Base Class
# ============================================================================


class Embedder(ABC):
    """向量嵌入抽象基类"""

    @property
    @abstractmethod
    def dim(self) -> int:
        """返回向量维度"""
        pass

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """
        单文本嵌入

        Args:
            text: 输入文本

        Returns:
            归一化后的向量列表
        """
        pass

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        批量文本嵌入

        Args:
            texts: 输入文本列表

        Returns:
            归一化后的向量列表
        """
        pass


# ============================================================================
# HashEmbedder - 零依赖确定性哈希嵌入
# ============================================================================


class HashEmbedder(Embedder):
    """
    基于哈希的确定性嵌入器

    特点：
    - 零外部依赖（只用 hashlib + numpy）
    - 确定性：相同文本 → 相同向量
    - 速度 < 50ms/文本（1000字符内）

    算法：
    1. 字符 n-gram (2-4 gram) 特征提取
    2. 词袋 (Word Bag) 哈希
    3. L2 归一化到 [-1, 1]
    """

    def __init__(self, dim: int = 384):
        """
        初始化 HashEmbedder

        Args:
            dim: 向量维度，默认 384
        """
        self._dim = dim
        self._ngram_ranges = [(2, 4)]  # 字符 n-gram 范围

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, text: str) -> list[float]:
        """单文本嵌入"""
        vector = self._hash_to_vector(text)
        # L2 归一化
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        # 缩放到 [-1, 1]
        vector = vector * 0.5  # hash 分布已经是 [-1, 1]
        return vector.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量嵌入"""
        return [self.embed(t) for t in texts]

    def _hash_to_vector(self, text: str) -> np.ndarray:
        """将文本哈希为固定维度向量"""
        vector = np.zeros(self._dim, dtype=np.float32)

        # 1. 字符 n-gram 哈希
        for n in range(2, 5):  # 2, 3, 4-gram
            for i in range(len(text) - n + 1):
                ngram = text[i:i + n]
                hash_val = self._stable_hash(ngram)
                idx = hash_val % self._dim
                # 用 sign 产生 ±1
                sign = 1 if (hash_val // self._dim) % 2 == 0 else -1
                vector[idx] += sign * 0.1

        # 2. 词袋哈希
        words = text.split()
        for word in words:
            if len(word) < 2:
                continue
            hash_val = self._stable_hash(word)
            idx = hash_val % self._dim
            sign = 1 if (hash_val // self._dim) % 2 == 0 else -1
            vector[idx] += sign * 0.15

        # 3. 整体文本哈希（粗粒度）
        text_hash = self._stable_hash(text)
        for i in range(min(32, self._dim)):
            idx = (text_hash + i * 7919) % self._dim  # 质数步长
            sign = 1 if i % 2 == 0 else -1
            vector[idx] += sign * 0.05

        return vector

    def _stable_hash(self, text: str) -> int:
        """稳定的哈希函数，跨 Python 版本一致"""
        # 使用 SHA256 取前 8 字节，转为整数
        h = hashlib.sha256(text.encode("utf-8")).digest()
        return int.from_bytes(h[:8], byteorder="big", signed=False)


# ============================================================================
# DashScopeEmbedder - 阿里云百炼 API 嵌入
# ============================================================================


class DashScopeEmbedder(Embedder):
    """
    阿里云百炼 API 嵌入器

    使用 httpx 异步调用 dashscope API
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "text-embedding-v3",
        dim: int = 1024,
        base_url: str = "https://dashscope.aliyuncs.com/api/v1",
    ):
        """
        初始化 DashScopeEmbedder

        Args:
            api_key: 百炼 API key，若为 None 则从环境变量 DASHSCOPE_API_KEY 读取
            model: 嵌入模型，默认 text-embedding-v3
            dim: 向量维度，默认 1024
            base_url: API 基础 URL
        """
        self._api_key = api_key or os.environ.get("DASHSCOPE_API_KEY", "")
        self._model = model
        self._dim = dim
        self._base_url = base_url.rstrip("/")
        self._client = None

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def api_key(self) -> str:
        return self._api_key

    async def _get_client(self):
        """获取或创建 httpx 异步客户端"""
        if self._client is None:
            try:
                import httpx
                self._client = httpx.AsyncClient(
                    timeout=httpx.Timeout(60.0),
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                )
            except ImportError:
                raise ImportError("httpx is required for DashScopeEmbedder. Install with: pip install httpx")
        return self._client

    async def close(self) -> None:
        """关闭 HTTP 客户端"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def embed(self, text: str) -> list[float]:
        """单文本嵌入"""
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量文本嵌入"""
        if not texts:
            return []

        client = await self._get_client()

        payload = {
            "model": self._model,
            "input": {"texts": texts},
        }

        response = await client.post(
            f"{self._base_url}/embeddings",
            json=payload,
        )

        if response.status_code != 200:
            raise RuntimeError(f"DashScope API error: {response.status_code} - {response.text}")

        data = response.json()
        embeddings = data.get("data", [])

        # 按输入顺序返回
        result = [None] * len(texts)
        for item in embeddings:
            idx = item.get("index", 0)
            embedding = item.get("embedding", [])
            result[idx] = embedding

        # 填充 None 为零向量（理论上不应发生）
        for i in range(len(result)):
            if result[i] is None:
                result[i] = [0.0] * self._dim

        return result

    def embed_sync(self, text: str) -> list[float]:
        """同步单文本嵌入（兼容非异步场景）"""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            # 在已有事件循环中用线程池执行
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self.embed(text))
                return future.result()
        except RuntimeError:
            # 没有运行中的事件循环
            return asyncio.run(self.embed(text))


# ============================================================================
# Factory Function
# ============================================================================


def get_embedder() -> Embedder:
    """
    工厂函数：根据环境变量自动选择嵌入器

    优先级：
    1. DASHSCOPE_API_KEY 存在 → DashScopeEmbedder
    2. 否则 → HashEmbedder
    """
    api_key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if api_key:
        return DashScopeEmbedder(api_key=api_key)
    return HashEmbedder(dim=384)


# ============================================================================
# 测试入口
# ============================================================================

if __name__ == "__main__":
    # 测试 HashEmbedder
    print("=== HashEmbedder Test ===")
    hasher = HashEmbedder(dim=384)
    v1 = hasher.embed("用户参加石榴籽省赛")
    v2 = hasher.embed("用户参加石榴籽省赛")
    v3 = hasher.embed("今天学习NLLB训练")
    print(f"向量维度: {hasher.dim}")
    print(f"相同文本向量相等: {v1 == v2}"
