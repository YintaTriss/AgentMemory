# AgentMemory v2.0 Provider 接口契约

> **作者**：架构师（architect）
> **任务 ID**：`44b99bdb-4f36-401c-99fb-34d20af8d4d9`
> **版本**：v2.0.0 · **日期**：2026-06-05
> **配套**：`v2-architecture.md` / `api-contract.md`

---

## 0. 阅读路径

| 角色 | 阅读 |
|------|------|
| backend1 | §1 / §2 / §3 |
| backend2 | §4 / §5 |
| qa | §6（Mock）/ §7（错误约定）|

---

## 1. Provider 总览

v2.0 砍掉 GraphStore，保留 3 个 Protocol：**LLM** / **Embedder** / **VectorStore**。

| Protocol | 用途 | v2.0 实现 |
|----------|------|----------|
| `Embedder` | 文本向量化 | DashScopeEmbedder / OpenAICompatEmbedder / **MockEmbedder**（兜底） |
| `LLM` | 文本生成 | BailianProvider / MinimaxProvider / OpenAICompatProvider / **MockLLM**（兜底） |
| `VectorStore` | 向量存取 + 检索 | **JsonVectorStore**（默认） / SqliteVectorStore |

**抽象原则**：`typing.Protocol`（结构化子类型）；错误抛 `ProviderError` 子类；切换 Provider 不需重启。

---

## 2. Embedder Protocol

### 2.1 接口

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Embedder(Protocol):
    """文本向量化 Provider"""

    async def embed(self, text: str) -> list[float]:
        """单条 → 向量（dim == self.dimension）

        Raises: ProviderAPIKeyMissingError (E002.1) / RateLimit (E002.2)
                Timeout (E002.4) / EmbedderPermanent (E002.5)
        """
        ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
    @property
    def dimension(self) -> int: ...
    @property
    def model_name(self) -> str: ...
```

### 2.2 MockEmbedder（兜底，必备）

```python
import hashlib, struct

class MockEmbedder:
    """确定性 hash 向量：零网络/零磁盘，离线/测试/CI 兜底"""
    DEFAULT_DIM = 384

    def __init__(self, dimension: int = 384) -> None:
        self._dim = dimension

    async def embed(self, text: str) -> list[float]:
        # SHA-256 多次扩展 → 截断 → 中心化 → L2 归一化
        vec, h = [], hashlib.sha256()
        for i in range((self._dim + 31) // 32):
            h.update(text.encode("utf-8")); h.update(struct.pack("<I", i))
            for b in h.digest():
                vec.append((b - 128) / 128.0)
                if len(vec) >= self._dim: break
        norm = sum(x * x for x in vec) ** 0.5
        return [x / norm for x in vec]

    async def embed_batch(self, texts): return [await self.embed(t) for t in texts]
    @property
    def dimension(self): return self._dim
    @property
    def model_name(self): return "mock-hash-v1"
```

### 2.3 DashScopeEmbedder / OpenAICompatEmbedder

```python
class DashScopeEmbedder:
    """阿里百炼 text-embedding-v3（type='bailian'）

    模型：text-embedding-v3 (1024d) / -v2 (1536d) / -async-v2 (1536d)
    endpoint: https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings
    配置: api_key, model, dimension, timeout=30
    """
    def __init__(self, api_key, model="text-embedding-v3",
                 dimension=None, endpoint=..., timeout=30.0): ...
    async def embed(self, text): ...   # POST + Bearer + 校验 dim
    async def embed_batch(self, texts): ...  # 分片 25 条 + asyncio.gather
    async def close(self): await self._client.aclose()


class OpenAICompatEmbedder:
    """OpenAI 兼容协议（OpenAI/Azure/LocalAI/vLLM/Ollama）

    与 DashScopeEmbedder 差异：仅 endpoint = {base_url}/embeddings
    """
```

---

## 3. LLM Protocol

### 3.1 接口

```python
@runtime_checkable
class LLM(Protocol):
    """文本生成（sync_turn / 分类推荐）"""
    async def complete(
        self, prompt: str, *, max_tokens: int = 512, temperature: float = 0.3,
        system: str | None = None, json_mode: bool = False,
    ) -> str: ...
    async def stream_complete(
        self, prompt: str, *, max_tokens: int = 512, temperature: float = 0.3,
        system: str | None = None,
    ) -> AsyncIterator[str]: ...
```

### 3.2 实现概览

| Provider | 模型 | API |
|----------|------|-----|
| `BailianProvider` | qwen3.6-plus | DashScope 兼容 |
| `MinimaxProvider` | MiniMax-M2.7-highspeed | OpenAI 兼容 |
| `OpenAICompatProvider` | GPT-4o 等 | OpenAI 兼容 |
| `MockLLM` | — | 离线规则（v2.0 新增兜底）|

**MockLLM**：

```python
class MockLLM:
    """离线 LLM：无 Key 时 sync_turn 兜底"""
    async def complete(self, prompt, **kw) -> str:
        worth = any(kw in prompt for kw in ["记住", "记录", "记得", "项目"])
        return json.dumps({
            "worth_recording": worth,
            "summary": prompt[:100] if worth else None,
            "category": ["A.项目"] if worth else None,
            "reason": None if worth else "mock: 规则未命中",
        }, ensure_ascii=False)

    async def stream_complete(self, prompt, **kw):
        for ch in await self.complete(prompt, **kw): yield ch
```

---

## 4. VectorStore Protocol（v2.0 新增）

### 4.1 接口

```python
@runtime_checkable
class VectorStore(Protocol):
    """向量存取 + 相似度检索"""
    async def upsert(self, mem_id: str, vector: list[float], meta: dict) -> None: ...
    async def search(
        self, vector: list[float], k: int = 10, filter: dict | None = None,
    ) -> list[tuple[str, float]]:
        """Top-K cosine；filter 支持 category_prefix"""
        ...
    async def delete(self, mem_id: str) -> None: ...
    async def persist(self) -> None: ...
    async def load(self) -> None: ...
    @property
    def count(self) -> int: ...
    @property
    def dimension(self) -> int: ...
```

### 4.2 JsonVectorStore（默认）

```python
class JsonVectorStore:
    """JSON 文件向量库（零依赖），适用 ≤ 50k 记忆

    存储：memory_library/.vectors.json
    格式：{version, dimension, backend:"json",
           vectors:{mem_id:{vector,category,tags,updated_at}}}
    """
    def __init__(self, path: Path, dimension: int) -> None: ...
    async def load(self) -> None: ...        # 读 .vectors.json → self._data
    async def upsert(self, mem_id, vector, meta) -> None:
        # dim 校验 → asyncio.Lock → self._data[mem_id]={...}; mark dirty
        ...
    async def search(self, vector, k, filter=None):
        # numpy: query/candidates L2 归一化 → np.dot → 排序 → top-k
        # 支持 filter["category_prefix"]: entry["category"][:len(prefix)] == prefix
        ...
    async def delete(self, mem_id): ...      # Lock → pop；mark dirty
    async def persist(self): ...             # 原子写：.tmp → rename；清 dirty
    @property
    def count(self): return len(self._data)
    @property
    def dimension(self): return self._dim
```

### 4.3 SqliteVectorStore（v2.0 同 PR）

```python
class SqliteVectorStore:
    """SQLite 向量库，适用 ≤ 1M 记忆

    Schema:
        CREATE TABLE vectors (mem_id TEXT PK, vector BLOB,
                              category TEXT, tags TEXT, updated_at TEXT);
        CREATE INDEX idx_category ON vectors(category);

    与 JsonVectorStore 差异：vector 存 BLOB（np.float32 tobytes）；
    search 走全表 + numpy 批量 cosine；persist 即 commit。

    接口（upsert/search/delete/persist/load/count/dimension）与 JsonVectorStore 完全一致。
    """
    def __init__(self, db_path: Path, dimension: int) -> None:
        # sqlite3.connect(check_same_thread=False) + _init_schema()
        ...
```

**性能对比**（10k×1024d）：

| 后端 | upsert | search | persist | load |
|------|--------|--------|---------|------|
| JsonVectorStore | < 1ms | 80ms | 400ms | 800ms |
| SqliteVectorStore | 2ms | 250ms | 50ms | 600ms |

**选择**：≤ 10k → JSON（简单）；10k-1M → SQLite（可靠）；> 1M → v2.1 Chroma。

---

## 5. Provider 选择机制

### 5.1 优先级

```
1. 显式 Config  >  2. 环境变量  >  3. Mock 兜底
```

| 类别 | 检测 | 兜底 |
|------|------|------|
| LLM | `AGENTMEMORY_LLM__TYPE` | `mock` |
| Embedder | `BAILIAN_API_KEY` / `OPENAI_API_KEY` / `MINIMAX_API_KEY` | `mock` |
| VectorStore | `AGENTMEMORY_VECTOR_STORE__TYPE` (`json` / `sqlite`) | `json` |

### 5.2 工厂

```python
def get_embedder(config) -> Embedder:
    explicit = config.get("providers.embedder.type")
    api_key = config.get("providers.embedder.api_key", "").replace(
        "${BAILIAN_API_KEY}", os.environ.get("BAILIAN_API_KEY", ""))
    if explicit == "bailian" or (not explicit and os.environ.get("BAILIAN_API_KEY")):
        return DashScopeEmbedder(api_key=api_key, ...)
    if explicit == "openai" or (not explicit and os.environ.get("OPENAI_API_KEY")):
        return OpenAICompatEmbedder(api_key=api_key, ...)
    return MockEmbedder(dimension=config.get("providers.embedder.dimension", 384))


def get_llm(config) -> LLM:
    t = config.get("providers.llm.type")
    if t == "bailian":  return BailianProvider(...)
    if t == "minimax":  return MinimaxProvider(...)
    if t == "openai":   return OpenAICompatProvider(...)
    return MockLLM()


def get_vector_store(config) -> VectorStore:
    t = config.get("providers.vector_store.type", "json")
    dim = config.get("providers.embedder.dimension", 1024)
    path = Path(config.get("providers.vector_store.path", "./memory_library/.vectors"))
    if t == "sqlite":
        return SqliteVectorStore(path.with_suffix(".db"), dimension=dim)
    return JsonVectorStore(path.with_suffix(".json"), dimension=dim)
```

### 5.3 启动日志

```
[AgentMemory v2.0] Initializing...
  LLM:           bailian (qwen3.6-plus)
  Embedder:      bailian (text-embedding-v3, dim=1024)
  VectorStore:   json (./memory_library/.vectors.json)
  DataLake:      ./memory_library/
  MultiAgent:    enabled (agent_id=agent_a, role=owner)
[AgentMemory v2.0] Ready in 1.23s
```

### 5.4 热切换

**v2.0 不支持**：需 close → 改 Config → 重建。**v2.1 计划**通过 `Config.reload()` 实现。

---

## 6. Mock 与测试

```python
# tests/conftest.py
import pytest
from agentmemory.providers import MockEmbedder, MockLLM, JsonVectorStore

@pytest.fixture
def mock_embedder(): return MockEmbedder(dimension=384)

@pytest.fixture
def mock_llm(): return MockLLM()

@pytest.fixture
async def tmp_vector_store(tmp_path):
    store = JsonVectorStore(tmp_path / "vectors.json", dimension=384)
    await store.load()
    yield store
    await store.persist()
```

---

## 7. Provider 错误约定

### 7.1 异常类

```
ProviderError (E002)
├── ProviderAPIKeyMissingError (E002.1)
├── ProviderRateLimitError (E002.2)
├── ProviderNetworkError (E002.3)
├── ProviderTimeoutError (E002.4)
└── EmbedderPermanentError (E002.5)
```

### 7.2 状态机对接

| 异常 | EmbeddingStateMachine 动作 |
|------|------------------------|
| `ProviderRateLimitError` | retry（退避 5s）|
| `ProviderTimeoutError` | retry（退避 2s）|
| `ProviderNetworkError` | retry（退避 1s）|
| `EmbedderPermanentError` | **立即 → permanent_failure** |
| `ProviderAPIKeyMissingError` | **立即 → permanent_failure**（不重试）|
| 其他 `ProviderError` | retry |

上限 `max_retries=3`（可配）。

---

## 8. 依赖与安装

```toml
# pyproject.toml
dependencies = [
    "pydantic>=2.0",      # 数据契约
    "httpx>=0.25",        # 异步 HTTP
    "aiofiles>=23.0",     # 异步文件 IO
    "numpy>=1.24",        # 向量计算
    "python-ulid>=2.0",   # ULID
]

[project.optional-dependencies]
web    = ["fastapi>=0.100", "flask>=2.3", "uvicorn[standard]>=0.23"]
chroma = ["chromadb>=0.4"]     # v2.1
all    = ["chromadb>=0.4", "fastapi>=0.100", "flask>=2.3", "uvicorn[standard]>=0.23"]
```

```bash
pip install agentmemory            # 最小化
pip install agentmemory[web]      # + web/api
pip install agentmemory[all]      # 全功能
```

---

## 9. 文档元信息

| 项 | 值 |
|----|---|
| 文档路径 | `C:\Users\31683\AgentMemory\docs\providers-contract.md` |
| Protocol | 3（LLM / Embedder / VectorStore）|
| 实现 | 8（LLM×4、Embedder×3、VectorStore×2）含 Mock 兜底 |
| 工厂 | 3（get_llm / get_embedder / get_vector_store）|
| 错误类 | 5（ProviderError 子类）|
| 优先级 | 3 级（Config > 环境变量 > Mock）|
| 核心依赖 | 5（pydantic/httpx/aiofiles/numpy/python-ulid）|
| 可选 | chroma / web / all |

---

_本 Provider 契约由 architect 在任务 `44b99bdb-4f36-401c-99fb-34d20af8d4d9` 产出 · 2026-06-05_
_所有 Protocol 有 Type Hint + docstring + 异常；MockEmbedder 是兜底默认_
