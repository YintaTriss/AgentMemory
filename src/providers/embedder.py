"""
Embedder Provider 抽象层 v2
支持 DashScope / MiniMax / Local (OpenAI 兼容) / Mock 多 provider
LocalEmbedder 升级：多模型路由 + fallback + chunking + 并发 + 429 重试
"""

import os
import hashlib
import json
import time
import asyncio
import re
import math
from typing import List, Optional, Protocol, runtime_checkable

import httpx

try:
    from .base import Provider  # type: ignore
except ImportError:
    pass


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


# ---- 工具函数 ----

def _resolve_base_url(default: str, env_var: str, key: str, *, general_env: Optional[str] = None) -> str:
    """解析 base_url，优先级：general_env > env_var > default.

    Args:
        default: 内置默认 URL。
        env_var: 专用环境变量名（如 EMBEDDING_API_URL / BAILIAN_BASE_URL）。
        key: provider key（仅用于诊断）。
        general_env: 通用网关环境变量名（如 LLM_BASE_URL），默认 None 表示不读。
            注意：embedder 默认不读 LLM_BASE_URL——避免 LLM 网关地址误覆盖 embedding 服务地址。
    """
    if general_env:
        general = os.environ.get(general_env, "").strip()
        if general:
            return general.rstrip("/")
    specific = os.environ.get(env_var, "").strip()
    if specific:
        return specific.rstrip("/")
    return default


# ---- 文本分块 ----

# text2vec-base-chinese 上限 512 token
DEFAULT_MAX_TOKENS = 480  # 留 6% 余量给特殊 token
CHARS_PER_TOKEN_ZH = 1.5  # 中文大概 1.5 字符/token（粗估）

# 中英文句子边界
_SENT_SPLIT_PATTERN = re.compile(r"(?<=[。！？!?\.])")  # 在句末标点后切


def estimate_tokens(text: str) -> int:
    """粗估 token 数。中文按 1.5 字符/token，英文按 0.5 字符/token。"""
    if not text:
        return 0
    n_cjk = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    n_other = len(text) - n_cjk
    return int(n_cjk / CHARS_PER_TOKEN_ZH + n_other * 0.5)


def chunk_text(text: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> List[str]:
    """把长文本切成 ≤max_tokens 的块，按句子边界切。

    保留原始分隔符（不 strip，避免丢失格式信息）。
    """
    if not text or not text.strip():
        return []

    if estimate_tokens(text) <= max_tokens:
        return [text]

    sentences = _SENT_SPLIT_PATTERN.split(text)
    sentences = [s for s in sentences if s.strip()]

    chunks = []
    current: List[str] = []
    current_tokens = 0

    for sent in sentences:
        sent_tokens = estimate_tokens(sent)
        # 单句超长 → 硬切
        if sent_tokens > max_tokens:
            if current:
                # 句子自然已含边界标点，直接拼接
                chunks.append("".join(current))
                current = []
                current_tokens = 0
            # 按字符硬切
            max_chars = int(max_tokens * CHARS_PER_TOKEN_ZH)
            for i in range(0, len(sent), max_chars):
                chunks.append(sent[i:i + max_chars])
            continue

        if current_tokens + sent_tokens > max_tokens:
            chunks.append("".join(current))
            current = [sent]
            current_tokens = sent_tokens
        else:
            current.append(sent)
            current_tokens += sent_tokens

    if current:
        chunks.append("".join(current))

    return chunks


# ---- 通用 OpenAI 兼容 Embedder ----

class LocalEmbedder:
    """
    本地 Embedder Provider（v2：多模型路由 + fallback + chunking + 并发）

    支持以下能力：
      - 按 model 名路由到不同 endpoint（本地、NewAPI、其他 OpenAI 兼容）
      - 自动 fallback：主模型失败切 backup
      - 长文本 chunking：超过 max_tokens 自动切句
      - 批量并发：embeds() 内部按 chunk 切分并发请求
      - 429 退避重试
      - 内容 hash 缓存：相同内容不重复 embed

    配置优先级：
      1. 显式 routes 参数
      2. LOCAL_EMBED_ROUTES 环境变量（JSON 数组）
      3. 单模型回退（EMBEDDING_API_URL + model）
    """

    DEFAULT_BASE_URL = "http://localhost:18080"
    DEFAULT_MODEL = "text2vec-base-chinese"
    DEFAULT_DIMENSIONS = 768
    DEFAULT_MAX_TOKENS = 480
    DEFAULT_TIMEOUT = 60.0
    DEFAULT_CONCURRENCY = 5
    DEFAULT_RETRIES = 3

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        dimensions: int = DEFAULT_DIMENSIONS,
        timeout: float = DEFAULT_TIMEOUT,
        routes: Optional[List[dict]] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        concurrency: int = DEFAULT_CONCURRENCY,
        retries: int = DEFAULT_RETRIES,
        chunking_enabled: bool = True,
        cache_size: int = 256,
        **kwargs,
    ):
        # 解析路由
        if routes is None:
            env_routes = os.environ.get("LOCAL_EMBED_ROUTES", "").strip()
            if env_routes:
                try:
                    routes = json.loads(env_routes)
                except json.JSONDecodeError as e:
                    raise ValueError(f"LOCAL_EMBED_ROUTES JSON 解析失败: {e}") from e

        if not routes:
            # 单模型回退（旧 API 兼容）
            legacy_url = base_url or _resolve_base_url(
                self.DEFAULT_BASE_URL, "EMBEDDING_API_URL", "embedding"
            )
            legacy_model = model or os.environ.get("LOCAL_EMBED_MODEL") or self.DEFAULT_MODEL
            legacy_key = api_key or os.environ.get("LOCAL_EMBED_API_KEY", "")
            routes = [{
                "model": legacy_model,
                "base_url": legacy_url,
                "api_key": legacy_key,
                "dimensions": dimensions,
            }]

        # 验证路由
        for i, r in enumerate(routes):
            if "model" not in r or "base_url" not in r:
                raise ValueError(f"routes[{i}] 缺少必需字段 model/base_url: {r}")

        self.routes: List[dict] = routes
        self.default_model = model or self.routes[0]["model"]
        self.dimensions = dimensions
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.concurrency = max(1, concurrency)
        self.retries = max(0, retries)
        self.chunking_enabled = chunking_enabled
        self._cache: OrderedDictFallback = OrderedDictFallback(max_size=cache_size)
        self._client: Optional[httpx.AsyncClient] = None
        self._sem = None  # lazily init

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            # Use a primary key from first route that has api_key
            primary_key = next((r.get("api_key", "") for r in self.routes if r.get("api_key")), "")
            headers = {"Content-Type": "application/json"}
            if primary_key:
                headers["Authorization"] = f"Bearer {primary_key}"
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers=headers,
            )
        return self._client

    def _get_sem(self) -> asyncio.Semaphore:
        if self._sem is None:
            self._sem = asyncio.Semaphore(self.concurrency)
        return self._sem

    async def aclose(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "LocalEmbedder":
        return self

    async def __aexit__(self, *args) -> None:
        await self.aclose()

    # ---- 公开 API ----

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """批量 embed。先查缓存；未命中按 chunk 切分并发请求；同 model fallback。"""
        if not texts:
            return []

        # 1) 检查缓存，未命中部分走网络
        results: List[Optional[list[float]]] = [None] * len(texts)
        missing_idx: List[int] = []
        missing_texts: List[str] = []

        for i, t in enumerate(texts):
            if not t or not t.strip():
                continue
            cached = self._cache.get(t)
            if cached is not None:
                results[i] = cached
            else:
                missing_idx.append(i)
                missing_texts.append(t)

        if not missing_texts:
            return [r if r is not None else [0.0] * self.dimensions for r in results]

        # 2) 切分 chunks
        all_chunks: List[str] = []  # 切分后的所有小块
        text_to_chunks: List[List[int]] = []  # 原始 text -> 对应 chunk 在 all_chunks 里的 index
        for t in missing_texts:
            if self.chunking_enabled:
                pieces = chunk_text(t, self.max_tokens)
            else:
                pieces = [t]
            if not pieces:
                pieces = [t]  # fallback: 即使空也保留
            chunk_ids = []
            for p in pieces:
                # 用 (text_hash, chunk_index) 缓存
                key = self._hash(p)
                if key not in [self._hash(c) for c in all_chunks]:
                    all_chunks.append(p)
                chunk_ids.append(self._hash(p))
            text_to_chunks.append(chunk_ids)

        # 3) 去重：找出需要真去调 API 的 chunk
        unique_chunks: List[str] = []
        seen = set()
        for c in all_chunks:
            h = self._hash(c)
            if h not in seen:
                seen.add(h)
                unique_chunks.append(c)

        # 4) 并发请求
        if unique_chunks:
            chunk_vectors = await self._dispatch_batch(unique_chunks)
            # 缓存
            for c, v in zip(unique_chunks, chunk_vectors):
                self._cache.put(c, v)
        else:
            chunk_vectors = []

        # 5) 重组：原始 text 的所有 chunk 向量平均池化
        for orig_idx, chunk_ids in zip(missing_idx, text_to_chunks):
            vecs = []
            for cid in chunk_ids:
                # 找到对应向量
                for c, v in zip(unique_chunks, chunk_vectors):
                    if self._hash(c) == cid:
                        vecs.append(v)
                        break
            if vecs:
                merged = self._mean_pool(vecs)
                results[orig_idx] = merged

        return [r if r is not None else [0.0] * self.dimensions for r in results]

    async def embed_single(self, text: str) -> list[float]:
        vecs = await self.embed([text])
        return vecs[0] if vecs else [0.0] * self.dimensions

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()

    @staticmethod
    def _mean_pool(vectors: List[List[float]]) -> List[float]:
        if not vectors:
            return [0.0]
        if len(vectors) == 1:
            return vectors[0]
        n = len(vectors[0])
        sums = [0.0] * n
        for v in vectors:
            for i, x in enumerate(v):
                sums[i] += x
        return [x / len(vectors) for x in sums]

    # ---- 内部：分派请求 ----

    async def _dispatch_batch(self, texts: List[str]) -> List[List[float]]:
        """并发调用 embed API，支持模型 fallback 和 429 重试。
        所有 route 全失败时降级为 MockEmbedder 风格 hash 向量（保持系统可用）。
        """
        sem = self._get_sem()
        results: List[Optional[List[float]]] = [None] * len(texts)

        async def call_one(idx: int, text: str):
            errors = []
            for route in self.routes:
                try:
                    vec = await self._call_route_with_retry(route, text, sem)
                    results[idx] = vec
                    return
                except Exception as e:
                    errors.append(f"{route['model']}: {type(e).__name__}: {str(e)[:60]}")
            # 全部 route 失败 → 降级
            if not results[idx]:
                results[idx] = self._mock_vector(text)
            if not getattr(self, '_degraded', False):
                self._degraded = True
                print("WARNING embedding service unreachable")
                for err in errors:
                    print(f"         {err}")
                print("         Degraded to MockEmbedder (deterministic hash vectors). ")
                print("         Start text2vec service or set LOCAL_EMBED_ROUTES to restore.")

        tasks = [call_one(i, t) for i, t in enumerate(texts)]
        await asyncio.gather(*tasks)
        return [r if r is not None else self._mock_vector(t) for r, t in zip(results, texts)]

    @staticmethod
    def _mock_vector(text: str) -> List[float]:
        """生成确定性 mock 向量（降级用，与 MockEmbedder 逻辑一致）。"""
        import hashlib, struct
        h = hashlib.sha256(text.encode()).digest()
        values = []
        dims = 768  # 匹配 text2vec 维度
        for i in range(dims):
            idx = (i * 4) % len(h)
            v = struct.unpack(">I", h[idx:idx+4])[0]
            values.append((v % (2**32)) / (2**32))
        norm = sum(v**2 for v in values) ** 0.5
        if norm > 0:
            values = [v / norm for v in values]
        return values

    async def _call_route_with_retry(
        self, route: dict, text: str, sem: asyncio.Semaphore
    ) -> List[float]:
        """带 429 重试的单一 route 调用。"""
        model = route["model"]
        base_url = route["base_url"].rstrip("/")
        api_key = route.get("api_key", "")
        client = self._get_client()

        last_error = None
        for attempt in range(1, self.retries + 1):
            try:
                async with sem:
                    return await self._embed_one(client, base_url, api_key, model, text)
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 429 and attempt < self.retries:
                    wait = min(2 ** attempt, 10)
                    await asyncio.sleep(wait)
                    continue
                if e.response.status_code in (401, 403):
                    # 认证失败不要重试，直接换下一个 route
                    raise
                if e.response.status_code >= 500 and attempt < self.retries:
                    wait = min(2 ** attempt, 5)
                    await asyncio.sleep(wait)
                    continue
                raise
            except (httpx.ConnectError, httpx.ReadError, httpx.WriteError) as e:
                last_error = e
                if attempt < self.retries:
                    await asyncio.sleep(min(2 ** attempt, 5))
                    continue
                raise
        if last_error:
            raise last_error
        raise RuntimeError("retry loop ended without result")

    async def _embed_one(
        self, client: httpx.AsyncClient, base_url: str, api_key: str, model: str, text: str
    ) -> List[float]:
        """单次 embed 调用。"""
        payload = {"model": model, "input": text}
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        response = await client.post(
            f"{base_url}/v1/embeddings",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()
        if "data" not in data or not data["data"]:
            raise RuntimeError(f"empty data from {base_url}: {data}")
        # 按 index 排序取第一个
        items = sorted(data["data"], key=lambda x: x.get("index", 0))
        return items[0]["embedding"]


# ---- LRU 缓存（移到类内不影响外部 API） ----

class OrderedDictFallback:
    """简单 LRU 缓存"""

    def __init__(self, max_size: int = 256):
        from collections import OrderedDict
        self._data: OrderedDict = OrderedDict()
        self.max_size = max(1, max_size)

    def get(self, key: str):
        if key in self._data:
            self._data.move_to_end(key)
            return self._data[key]
        return None

    def put(self, key: str, value):
        if key in self._data:
            self._data.move_to_end(key)
            self._data[key] = value
        else:
            self._data[key] = value
            if len(self._data) > self.max_size:
                self._data.popitem(last=False)


# ---- 规则 + DashScope + Mock（保持兼容） ----

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


class MockEmbedder:
    """
    Mock Embedder Provider — 零外部依赖，离线测试用
    """

    DEFAULT_DIMENSIONS = 1024

    def __init__(self, dimensions: int = DEFAULT_DIMENSIONS, seed: int = 42, **kwargs):
        self.dimensions = dimensions
        self.seed = seed
        self._cache: dict = {}

    def _hash_to_vector(self, text: str) -> list[float]:
        h = hashlib.sha256(f"{self.seed}:{text}".encode()).digest()
        h2 = hashlib.md5(f"{self.seed}:{text}".encode()).digest()
        values = []
        for i in range(self.dimensions):
            idx1 = (i * 4) % len(h)
            val1 = int.from_bytes(h[idx1:idx1+4], "big")
            idx2 = (i * 4) % len(h2)
            val2 = int.from_bytes(h2[idx2:idx2+4], "big")
            h3 = hashlib.sha256(f"{self.seed}:{text}:{i}".encode()).digest()
            val3 = int.from_bytes(h3[0:4], "big")
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


# ---- Provider 映射 ----

_EMBEDDER_PROVIDER_MAP = {
    "dashscope": DashScopeEmbedder,
    "bailian": DashScopeEmbedder,
    "text-embedding": DashScopeEmbedder,
    "local": LocalEmbedder,
    "text2vec": LocalEmbedder,
    "text2vec-base-chinese": LocalEmbedder,
    "bge": LocalEmbedder,
    "mock": MockEmbedder,
    "hash": MockEmbedder,
}


def get_embedder(
    model: str = None,
    api_key: str = None,
    base_url: Optional[str] = None,
    routes: Optional[List[dict]] = None,
    **kwargs,
) -> BaseEmbedderProvider:
    """
    工厂函数：根据配置返回对应 Embedder provider

    优先级：
      1. 显式 routes 参数（多模型 fallback 链路）
      2. 显式 model 字符串 → 按前缀匹配
      3. LOCAL_EMBED_ROUTES 环境变量
      4. 自动检测环境变量

    Examples:
        >>> e = get_embedder("text2vec-base-chinese")  # 旧 API 兼容
        >>> e = get_embedder(routes=[
        ...     {"model": "text2vec-base-chinese", "base_url": "http://localhost:18080"},
        ...     {"model": "BAAI/bge-large-zh-v1.5", "base_url": "http://localhost:3000",
        ...      "api_key": "sk-cp-…qSes"},
        ... ])
    """
    if routes:
        return LocalEmbedder(routes=routes, **kwargs)

    if model:
        for prefix, cls in _EMBEDDER_PROVIDER_MAP.items():
            if model.startswith(prefix) and cls is not MockEmbedder:
                if cls is LocalEmbedder:
                    return cls(
                        api_key=api_key,
                        base_url=base_url,
                        model=model,
                        **kwargs,
                    )
                return cls(
                    api_key=api_key
                    or os.environ.get("DASHSCOPE_API_KEY")
                    or os.environ.get("BAILIAN_API_KEY"),
                    model=model,
                    **kwargs,
                )

    if os.environ.get("LOCAL_EMBED_BASE_URL") or os.environ.get("LOCAL_EMBED_URL") or os.environ.get("LOCAL_EMBED_ROUTES"):
        return LocalEmbedder(
            api_key=api_key,
            base_url=base_url,
            model=model or os.environ.get("LOCAL_EMBED_MODEL", LocalEmbedder.DEFAULT_MODEL),
            **kwargs,
        )

    dashscope_key = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("BAILIAN_API_KEY")
    if api_key or dashscope_key:
        return DashScopeEmbedder(
            api_key=api_key or dashscope_key,
            model=model,
            **kwargs,
        )

    return MockEmbedder(**kwargs)
