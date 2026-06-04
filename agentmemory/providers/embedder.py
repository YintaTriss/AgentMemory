"""
Embedder Provider 抽象层 v1
支持 DashScope / Mock 多 provider 可切换
"""

import os
import hashlib
import httpx
from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class BaseEmbedderProvider(Protocol):
    """Embedder Provider 协议"""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """将文本列表转为向量列表"""
        ...

    async def embed_single(self, text: str) -> list[float]:
        """将单个文本转为向量"""
        ...

    async def aclose(self) -> None:
        """关闭 provider，释放资源"""
        ...


class DashScopeEmbedder:
    """
    阿里云 DashScope Embedder Provider
    使用 DashScope text-embedding API
    """

    DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    DEFAULT_MODEL = "text-embedding-v3"
    DEFAULT_DIMENSIONS = 1024

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        dimensions: int = DEFAULT_DIMENSIONS,
        **kwargs,
    ):
        self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("BAILIAN_API_KEY", "")
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.model = model or self.DEFAULT_MODEL
        self.dimensions = dimensions
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
        return self._client

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """
        批量获取文本的 embedding 向量
        
        Args:
            texts: 文本列表
        
        Returns:
            向量列表 list[list[float]]
        """
        if not texts:
            return []

        client = self._get_client()

        payload = {
            "model": self.model,
            "input": {"texts": texts},
            "parameters": {"encoding_format": "float"},
        }

        response = await client.post(
            f"{self.base_url}/services/embeddings/text-embedding/embedding",
            json=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        data = response.json()

        outputs = data["output"]["embeddings"]
        vectors = [item["embedding"] for item in outputs]

        return vectors

    async def embed_single(self, text: str) -> list[float]:
        """获取单个文本的 embedding"""
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


class MockEmbedder:
    """
    Mock Embedder Provider
    无 API key 时使用，基于 hash 的确定性向量生成
    保证相同文本产生相同向量，用于测试/离线环境
    """

    DEFAULT_DIMENSIONS = 1024

    def __init__(
        self,
        dimensions: int = DEFAULT_DIMENSIONS,
        seed: int = 42,
        **kwargs,
    ):
        self.dimensions = dimensions
        self.seed = seed
        self._cache: dict[str, list[float]] = {}

    def _hash_to_vector(self, text: str) -> list[float]:
        """将文本 hash 为确定性向量"""
        import struct

        # 主 hash (32 bytes)
        h = hashlib.sha256(f"{self.seed}:{text}".encode()).digest()
        # 辅助 hash (16 bytes)
        h2 = hashlib.md5(f"{self.seed}:{text}".encode()).digest()
        
        # 生成多个 float 值
        values = []
        for i in range(self.dimensions):
            # 从多个 hash 中提取数据
            # 使用 SHA256 的不同位置
            idx1 = (i * 4) % len(h)
            val1 = struct.unpack(">I", h[idx1:idx1+4])[0]
            
            # 使用 MD5 的不同位置
            idx2 = (i * 4) % len(h2)
            val2 = struct.unpack(">I", h2[idx2:idx2+4])[0]
            
            # 使用额外 SHA256 轮次
            h3 = hashlib.sha256(f"{self.seed}:{text}:{i}".encode()).digest()
            val3 = struct.unpack(">I", h3[0:4])[0]
            
            # 合并多个 hash
            combined = ((val1 ^ val2 ^ val3) % (2**32)) / (2**32)
            values.append(combined)
        
        # L2 归一化
        norm = sum(v**2 for v in values) ** 0.5
        if norm > 0:
            values = [v / norm for v in values]
        
        return values

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """批量获取文本的 embedding 向量"""
        vectors = []
        for text in texts:
            if text not in self._cache:
                self._cache[text] = self._hash_to_vector(text)
            vectors.append(self._cache[text])
        return vectors

    async def embed_single(self, text: str) -> list[float]:
        """获取单个文本的 embedding"""
        vectors = await self.embed([text])
        return vectors[0]

    async def aclose(self) -> None:
        """Mock 无需关闭"""
        pass

    async def __aenter__(self) -> "MockEmbedder":
        return self

    async def __aexit__(self, *args) -> None:
        await self.aclose()


# Provider 映射表
_EMBEDDER_PROVIDER_MAP = {
    "dashscope": DashScopeEmbedder,
    "dashscope/": DashScopeEmbedder,
    "text-embedding": DashScopeEmbedder,
    "mock": MockEmbedder,
    "hash": MockEmbedder,
}


def get_embedder(
    model: str = None,
    api_key: str = None,
    **kwargs,
) -> BaseEmbedderProvider:
    """
    工厂函数：根据配置返回对应 Embedder provider
    
    Args:
        model: 模型 ID（如 "text-embedding-v3" 或 "dashscope"）
              若为 None，根据环境变量自动检测
        api_key: API Key，若为 None 从环境变量读取
        **kwargs: 传递给 provider 的额外参数
    
    Returns:
        BaseEmbedderProvider 实例
        - 有 DASHSCOPE_API_KEY / BAILIAN_API_KEY → DashScopeEmbedder
        - 无 API key → MockEmbedder
    
    Examples:
        >>> embedder = get_embedder("text-embedding-v3")
        >>> embedder = get_embedder()  # 自动检测
    """
    # 检查是否有 DashScope API key
    dashscope_key = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("BAILIAN_API_KEY")
    
    if api_key:
        pass  # 显式传入 key，使用对应 provider
    elif dashscope_key:
        # 有 DashScope key，使用 DashScopeEmbedder
        return DashScopeEmbedder(
            api_key=dashscope_key,
            model=model,
            **kwargs,
        )
    else:
        # 无 API key，自动回退到 MockEmbedder
        return MockEmbedder(**kwargs)
    
    # 根据 model 前缀匹配
    if model:
        for prefix, cls in _EMBEDDER_PROVIDER_MAP.items():
            if model.startswith(prefix):
                return cls(model=model, api_key=api_key or dashscope_key, **kwargs)
    
    # 默认使用 DashScopeEmbedder
    return DashScopeEmbedder(
        api_key=api_key or dashscope_key,
        model=model,
        **kwargs,
    )
