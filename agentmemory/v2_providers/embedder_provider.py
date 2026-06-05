"""
Embedder Provider 实现

提供多种 Embedder 实现：
- MockEmbedder: 确定性 hash 向量，用于无 API Key 场景
- OpenAIEmbedder: OpenAI text-embedding-3 API
- DashScopeEmbedder: 阿里云 DashScope text-embedding-v3 API
- MiniMaxEmbedder: MiniMax Embedding API
"""

import os
import struct
import hashlib
import httpx
from typing import Optional

from .protocols import EmbedderProtocol, EmbedderResult


class MockEmbedder:
    """
    Mock Embedder Provider
    
    无 API Key 时使用，基于 hash 的确定性向量生成。
    保证相同文本产生相同向量，用于测试/离线环境。
    """
    
    DEFAULT_DIMENSIONS = 1024
    
    def __init__(self, dimensions: int = DEFAULT_DIMENSIONS, seed: int = 42, **kwargs):
        self.dimensions = dimensions
        self.seed = seed
        self._cache: dict[str, list[float]] = {}
        self._model = "mock/hash"
    
    @property
    def dimension(self) -> int:
        return self.dimensions
    
    def _hash_to_vector(self, text: str) -> list[float]:
        h = hashlib.sha256(f"{self.seed}:{text}".encode()).digest()
        h2 = hashlib.md5(f"{self.seed}:{text}".encode()).digest()
        values = []
        for i in range(self.dimensions):
            idx1 = (i * 4) % len(h)
            val1 = struct.unpack(">I", h[idx1:idx1+4])[0]
            idx2 = (i * 4) % len(h2)
            val2 = struct.unpack(">I", h2[idx2:idx2+4])[0]
            h3 = hashlib.sha256(f"{self.seed}:{text}:{i}".encode()).digest()
            val3 = struct.unpack(">I", h3[0:4])[0]
            combined = ((val1 ^ val2 ^ val3) % (2**32)) / (2**32)
            values.append(combined)
        norm = sum(v**2 for v in values) ** 0.5
        if norm > 0:
            values = [v / norm for v in values]
        return values
    
    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            if text not in self._cache:
                self._cache[text] = self._hash_to_vector(text)
            vectors.append(self._cache[text])
        return vectors
    
    async def embed_single(self, text: str) -> list[float]:
        vectors = await self.embed([text])
        return vectors[0]
    
    async def aclose(self) -> None:
        pass
    
    async def __aenter__(self) -> "MockEmbedder":
        return self
    
    async def __aexit__(self, *args) -> None:
        await self.aclose()


class OpenAIEmbedder:
    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    DEFAULT_MODEL = "text-embedding-3-large"
    DEFAULT_DIMENSIONS = 3072
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None,
                 model: Optional[str] = None, dimensions: int = DEFAULT_DIMENSIONS, **kwargs):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.model = model or self.DEFAULT_MODEL
        self.dimensions = dimensions
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def dimension(self) -> int:
        return self.dimensions
    
    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
        return self._client
    
    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        client = self._get_client()
        payload = {"model": self.model, "input": texts, "dimensions": self.dimensions}
        response = await client.post(
            f"{self.base_url}/embeddings", json=payload,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        )
        response.raise_for_status()
        data = response.json()
        return [item["embedding"] for item in data["data"]]
    
    async def embed_single(self, text: str) -> list[float]:
        vectors = await self.embed([text])
        return vectors[0]
    
    async def aclose(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def __aenter__(self) -> "OpenAIEmbedder":
        return self
    
    async def __aexit__(self, *args) -> None:
        await self.aclose()


class DashScopeEmbedder:
    DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    DEFAULT_MODEL = "text-embedding-v3"
    DEFAULT_DIMENSIONS = 1024
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None,
                 model: Optional[str] = None, dimensions: int = DEFAULT_DIMENSIONS, **kwargs):
        self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("BAILIAN_API_KEY", "")
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.model = model or self.DEFAULT_MODEL
        self.dimensions = dimensions
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def dimension(self) -> int:
        return self.dimensions
    
    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
        return self._client
    
    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        client = self._get_client()
        payload = {
            "model": self.model,
            "input": {"texts": texts},
            "parameters": {"encoding_format": "float", "dimensions": self.dimensions}
        }
        response = await client.post(
            f"{self.base_url}/services/embeddings/text-embedding/embedding",
            json=payload,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        )
        response.raise_for_status()
        data = response.json()
        outputs = data["output"]["embeddings"]
        return [item["embedding"] for item in outputs]
    
    async def embed_single(self, text: str) -> list[float]:
        vectors = await self.embed([text])
        return vectors[0]
    
    async def aclose(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def __aenter__(self) -> "DashScopeEmbedder":
        return self
    
    async def __aexit__(self, *args) -> None:
        await self.aclose()


class MiniMaxEmbedder:
    DEFAULT_BASE_URL = "https://api.minimaxi.chat/v1"
    DEFAULT_MODEL = "embo-01"
    DEFAULT_DIMENSIONS = 1024
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None,
                 model: Optional[str] = None, dimensions: int = DEFAULT_DIMENSIONS, **kwargs):
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.model = model or self.DEFAULT_MODEL
        self.dimensions = dimensions
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def dimension(self) -> int:
        return self.dimensions
    
    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
        return self._client
    
    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        client = self._get_client()
        payload = {"model": self.model, "texts": texts, "dimensions": self.dimensions}
        response = await client.post(
            f"{self.base_url}/text/embeddings", json=payload,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        )
        response.raise_for_status()
        data = response.json()
        return [item["embedding"] for item in data["data"]]
    
    async def embed_single(self, text: str) -> list[float]:
        vectors = await self.embed([text])
        return vectors[0]
    
    async def aclose(self) -> None:
        if self._client:
            await self._client.aclose()
            self._
