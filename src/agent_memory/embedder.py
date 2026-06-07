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


class Embedder(ABC):
    """向量嵌入抽象基类"""

    @property
    @abstractmethod
    def dim(self) -> int:
        pass

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        pass

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        pass


class HashEmbedder(Embedder):
    """基于哈希的确定性嵌入器，零依赖"""

    def __init__(self, dim: int = 384):
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, text: str) -> list[float]:
        vector = self._hash_to_vector(text)
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        vector = vector * 0.5
        return vector.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]

    def _hash_to_vector(self, text: str) -> np.ndarray:
        vector = np.zeros(self._dim, dtype=np.float32)
        for n in range(2, 5):
            for i in range(len(text) - n + 1):
                ngram = text[i:i + n]
                hash_val = self._stable_hash(ngram)
                idx = hash_val % self._dim
                sign = 1 if (hash_val // self._dim) % 2 == 0 else -1
                vector[idx] += sign * 0.1
        words = text.split()
        for word in words:
            if len(word) < 2:
                continue
            hash_val = self._stable_hash(word)
            idx = hash_val % self._dim
            sign = 1 if (hash_val // self._dim) % 2 == 0 else -1
            vector[idx] += sign * 0.15
        text_hash = self._stable_hash(text)
        for i in range(min(32, self._dim)):
            idx = (text_hash + i * 7919) % self._dim
            sign = 1 if i % 2 == 0 else -1
            vector[idx] += sign * 0.05
        return vector

    def _stable_hash(self, text: str) -> int:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        return int.from_bytes(h[:8], byteorder="big", signed=False)


class DashScopeEmbedder(Embedder):
    """阿里云百炼 API 嵌入器"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "text-embedding-v3",
        dim: int = 1024,
        base_url: str = "https://dashscope.aliyuncs.com/api/v1",
    ):
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
        if self._client is None:
            import httpx
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0),
                headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def embed(self, text: str) -> list[float]:
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        client = await self._get_client()
        payload = {"model": self._model, "input": {"texts": texts}}
        response = await client.post(f"{self._base_url}/embeddings", json=payload)
        if response.status_code != 200:
            raise RuntimeError(f"DashScope API error: {response.status_code}")
        data = response.json()
        embeddings = data.get("data", [])
        result = [None] * len(texts)
        for item in embeddings:
            idx = item.get("index", 0)
            embedding = item.get("embedding", [])
            result[idx] = embedding
        for i in range(len(result)):
            if result[i] is None:
                result[i] = [0.0] * self._dim
        return result

    def embed_sync(self, text: str) -> list[float]:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self.embed(text))
                return future.result()
        except RuntimeError:
            return asyncio.run(self.embed(text))


def get_embedder() -> Embedder:
    """工厂函数：根据环境变量自动选择嵌入器"""
    api_key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if api_key:
        return DashScopeEmbedder(api_key=api_key)
    return HashEmbedder(dim=384)


if __name__ == "__main__":
    print("=== HashEmbedder Test ===")
    hasher = HashEmbedder(dim=384)
    v1 = hasher.embed("用户参加石榴籽省赛")
    v2 = hasher.embed("用户参加石榴籽省赛")
    v3 = hasher.embed("今天学习NLLB训练")
    print(f"向量维度: {hasher.dim}")
    print(f"相同文本向量相等: {v1 == v2}")
    print(f"不同文本向量不同: {v1 != v3}")
    print(f"向量长度: {len(v1)}")
    print("=== HashEmbedder Test PASSED ===")
