# AgentMemory v2.0 API 契约

> **作者**：架构师（architect）
> **任务 ID**：`44b99bdb-4f36-401c-99fb-34d20af8d4d9`
> **版本**：v2.0.0
> **日期**：2026-06-05
> **配套**：`v2-architecture.md` / `providers-contract.md`

---

## 0. 阅读路径

| 角色 | 推荐阅读 |
|------|---------|
| backend | §1 / §2 / §3 / §4 / §5 |
| frontend | §3（HTTP/REST）|
| qa | §4（错误码 → HTTP 状态码）+ §5（兼容性）|
| 适配器作者 | §1（Python API）+ §6（适配器约定） |

---

## 1. Python API（MemoryHermes 公开方法）

### 1.1 总览

| 方法 | 同步/异步 | P99 预算 | 用途 |
|------|----------|---------|------|
| `__init__` | 同步 | < 1s | 初始化所有子系统 |
| `store` | 异步 | < 50ms（同步部分）| 写入（不阻塞 embedding）|
| `query` | 异步 | < 200ms | 双轨融合检索 |
| `list` | 异步 | < 100ms | 列出记忆 ID |
| `read` | 异步 | < 30ms | 读单条 |
| `forget` | 异步 | < 100ms | 主动遗忘 |
| `prefetch` | 异步 | < 150ms | 语义预取 |
| `stats` | 同步 | < 50ms | 统计信息 |
| `sync_turn` | 异步 | < 500ms | 对话轮次同步 |
| `on_session_end` | 异步 | < 500ms | 会话结束写摘要 |
| `run_decay_check` | 异步 | < 30s | 遗忘检查 |
| `close` | 异步 | < 2s | flush + 关闭 |

### 1.2 详细签名

```python
from typing import Literal
from datetime import datetime
from pathlib import Path
from agentmemory.config import Config
from agentmemory.models import MemoryEntry, SearchResult

class MemoryHermes:
    def __init__(
        self,
        config: Config | None = None,
        config_path: str | Path | None = None,
        agent_id: str | None = None,
    ) -> None:
        """初始化 MemoryHermes

        Args:
            config: 显式 Config（优先级最高）
            config_path: YAML 路径
            agent_id: 当前 Agent ID（默认读 AGENTMEMORY_AGENT_ID，否则 "default_agent"）

        Raises:
            ConfigError: 配置文件不存在或解析失败
        """
        ...

    async def store(
        self,
        content: str,
        category: list[str] | None = None,
        metadata: dict | None = None,
        importance: float = 0.5,
        tags: list[str] | None = None,
        wait_embedding: bool = False,
    ) -> str:
        """存储一条记忆

        Args:
            content: 1-100,000 字符
            category: e.g. ["A.项目", "石榴籽", "语料"]；None 时 LLM 推荐
            metadata: 自由元数据
            importance: 0.0-1.0
            tags: 最多 50 个
            wait_embedding: True 阻塞等 embedding（仅调试）

        Returns:
            mem_id: ULID 字符串

        Raises:
            CategoryNotInWhitelistError (E004.1) — 分类不在白名单
            CategoryDepthExceededError (E004.2) — 深度 > 4
            CategoryPathInvalidError (E004.3) — 路径格式错
            ProviderAPIKeyMissingError (E002.1) — LLM 推荐时
            FileIOError (E003.1) / DiskFullError (E003.3)

        Example:
            >>> await mh.store("优优说石榴籽省赛结果要等几天",
            ...     category=["A.项目", "石榴籽"], importance=0.8,
            ...     tags=["省赛"])
        """
        ...

    async def query(
        self,
        query: str,
        limit: int = 10,
        category: list[str] | None = None,
        tags: list[str] | None = None,
        mode: Literal["hybrid", "vector", "category", "tag"] = "hybrid",
        min_score: float = 0.0,
    ) -> list[SearchResult]:
        """双轨融合检索

        Args:
            query: 查询字符串
            limit: 1-100
            category: 分类过滤
            tags: 标签过滤
            mode: hybrid(双轨) | vector | category | tag
            min_score: 0.0-1.0 最低分

        Returns:
            list[SearchResult]，按 score 降序

        Raises:
            ProviderAPIKeyMissingError / ProviderTimeoutError
        """
        ...

    async def list(
        self, category: list[str] | None = None,
        since: datetime | None = None, until: datetime | None = None,
        limit: int = 100, offset: int = 0,
    ) -> list[str]: ...   # 列出符合的 mem_id（不加载内容）

    async def read(self, mem_id: str) -> MemoryEntry:
        """读单条；Raises: MemoryNotFoundError (E005.1) / JSONCorruptedError (E003.2)"""
        ...

    async def forget(self, mem_id: str) -> None:
        """主动遗忘（幂等；重复抛 NotFoundError）
        Side Effects: 删 .md/.meta.json/.vec.json / 更新 tag_index / append TieredLog
        """
        ...

    async def prefetch(self, query: str, limit: int = 5) -> list[SearchResult]:
        """语义预取（仅向量轨，不融合 BM25）"""
        ...

    def stats(self) -> dict:
        """同步统计（5s 缓存）
        Returns: {total_memories, by_category, embedding_state, provider, tiered_log, disk_usage_bytes, agent_id}
        """
        ...

    async def sync_turn(
        self, user_msg: str, assistant_msg: str, category: list[str] | None = None,
    ) -> str | None:
        """对话轮次同步：LLM 判定是否值得记；Returns: mem_id 或 None"""
        ...

    async def on_session_end(self, summary: str) -> str:
        """会话结束：写 session_summary 记忆（tag=["session_summary"]）"""
        ...

    async def run_decay_check(self) -> dict:
        """手动触发遗忘检查
        Returns: {scanned, forgotten, archived, kept, duration_ms, permanent_failures}
        """
        ...

    async def close(self) -> None:
        """关闭（flush worker + 关闭文件句柄）"""
        ...
```

### 1.3 异步/同步策略

| 类别 | 方法 |
|------|------|
| 同步 | `__init__` / `stats`（其他所有走 IO/LLM 均为异步）|
| 异步 | store / query / list / read / forget / prefetch / sync_turn / on_session_end / run_decay_check / close |

### 1.4 上下文管理器

```python
async with MemoryHermes() as mh:    # 自动 close()
    await mh.store("...")
```

---

## 2. 数据契约

### 2.1 MemoryEntry（Pydantic v2）

```python
class MemoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str                                   # ULID (26 chars)
    content: str                              # 1-100,000 chars
    category: list[str]                       # 1-4 层
    tags: list[str] = []
    metadata: dict = {}
    importance: float                         # 0.0-1.0
    embedding_state: Literal["pending", "generating", "completed", "failed", "permanent_failure"]
    created_at: datetime
    updated_at: datetime
    last_access_at: datetime | None = None
    access_count: int = 0
    schema_version: Literal[2] = 2


class SearchResult(BaseModel):
    mem_id: str
    content: str
    snippet: str                              # 200 字摘要
    score: float
    rank_vec: int | None
    rank_bm25: int | None
    category: list[str]
    tags: list[str]
    metadata: dict = {}
    embedding_state: Literal["pending", "generating", "completed", "failed", "permanent_failure"]


class ErrorResponse(BaseModel):
    error: str                                # 异常类名
    code: str                                 # E000 ~ E007.x
    message: str
    context: dict = {}
    traceback: str | None = None              # 仅 debug
```

---

## 3. HTTP REST API

### 3.1 基础信息

| 项 | 值 |
|----|---|
| Base URL | `http://localhost:8765` |
| 路径前缀 | `/v2/` |
| 默认端口 | 8765 |
| Content-Type | `application/json` |
| 时间格式 | ISO 8601 with `Z` (UTC) |
| 限流 | 100 req/s per IP |
| 鉴权 | `Authorization: Bearer <token>`（可选，AGENTMEMORY_API_AUTH=1 开启）|

### 3.2 端点清单

| Method | Path | Python |
|--------|------|--------|
| POST | `/v2/memories` | `mh.store()` |
| GET | `/v2/memories/search` | `mh.query()` |
| GET | `/v2/memories` | `mh.list()` |
| GET | `/v2/memories/{id}` | `mh.read()` |
| DELETE | `/v2/memories/{id}` | `mh.forget()` |
| POST | `/v2/memories/prefetch` | `mh.prefetch()` |
| GET | `/v2/stats` | `mh.stats()` |
| POST | `/v2/sync-turn` | `mh.sync_turn()` |
| POST | `/v2/session-end` | `mh.on_session_end()` |
| POST | `/v2/decay/run` | `mh.run_decay_check()` |
| GET | `/v2/embedding-state/{id}` | `esm.get_state()` |
| GET | `/v2/library/tree` | `library.export_tree()` |
| POST | `/v2/library/subcategory` | `library.add_subcategory()` |
| GET | `/v2/log/tail` | `tiered_log.read_tail()` |
| GET | `/v2/health` | — |
| GET | `/v2/version` | `__version__` |

### 3.3 关键端点契约

#### POST /v2/memories

```http
POST /v2/memories
Content-Type: application/json
Authorization: Bearer <token>

{
  "content": "优优说石榴籽省赛结果要等几天",
  "category": ["A.项目", "石榴籽", "语料"],
  "metadata": {"source": "conversation", "speaker": "优优"},
  "importance": 0.8,
  "tags": ["省赛"],
  "wait_embedding": false
}
```
→ **200**: `{"mem_id": "01HXYZ...", "embedding_state": "pending", "estimated_embedding_seconds": 10}`
→ **400**: `CategoryNotInWhitelistError` (E004.1) / `CategoryDepthExceededError` (E004.2)
→ **500**: `StorageError` (E003.x) / **503**: `LockTimeoutError` (E006.1)

#### GET /v2/memories/search

```http
GET /v2/memories/search?q=石榴籽&limit=10&category=A.项目,石榴籽&tags=省赛,PPT&mode=hybrid
```
→ **200**:
```json
{
  "results": [
    {
      "mem_id": "01HXYZ...",
      "content": "省赛PPT要改第三页配色",
      "snippet": "省赛PPT要改第三页配色，主色调用 #FF6B35...",
      "score": 0.92,
      "rank_vec": 1,
      "rank_bm25": 2,
      "category": ["A.项目", "石榴籽", "PPT"],
      "tags": ["省赛", "PPT"],
      "metadata": {"source": "conversation"},
      "embedding_state": "completed"
    }
  ],
  "total": 1,
  "duration_ms": 87
}
```

#### GET /v2/memories/{id}

→ **200**: 完整 `MemoryEntry` / **404**: `MemoryNotFoundError` (E005.1)

#### DELETE /v2/memories/{id}

→ **204**: No Content / **404** / **503**

#### GET /v2/stats

→ **200**:
```json
{
  "total_memories": 1234,
  "by_category": {"A.项目": 567, "B.个人": 234, "C.知识": 433},
  "embedding_state": {"pending": 5, "generating": 2, "completed": 1220, "failed": 0, "permanent_failure": 7},
  "provider": {"llm": "bailian", "embedder": "bailian", "vector_store": "json"},
  "tiered_log": {"heat_files": 5, "archive_files": 30, "total_entries": 4567},
  "disk_usage_bytes": 12345678,
  "agent_id": "agent_a"
}
```

#### POST /v2/sync-turn

```http
POST /v2/sync-turn
{"user_msg": "...", "assistant_msg": "...", "category": ["A.项目"]}
```
→ **200**: `{"stored": true, "mem_id": "..."}` or `{"stored": false, "reason": "..."}`

#### POST /v2/decay/run

→ **200**: `{"scanned": 1234, "forgotten": 12, "archived": 89, "kept": 1133, "duration_ms": 1234.5, "permanent_failures": 7}`

#### GET /v2/library/tree

→ **200**: 嵌套 JSON，每节点含 `description` / `count` / `children`

#### GET /v2/log/tail?n=50

→ **200**: `{"entries": [{ts, level, event, mem_id, agent_id, payload}, ...]}`

#### 其余端点（简短约定）

| 端点 | 行为 |
|------|------|
| GET `/v2/health` | `{"status": "ok", "uptime_s": 1234}` |
| GET `/v2/version` | `{"version": "2.0.0", "providers": {...}}` |
| GET `/v2/embedding-state/{id}` | `{mem_id, state, retry_count, last_error}` |
| POST `/v2/library/subcategory` | body: `{parent: [...], name, description}` → CategoryNode |
| POST `/v2/session-end` | body: `{summary}` → `{mem_id}` |

### 3.4 HTTP 状态码映射

| 错误类别 | HTTP | CLI exit |
|---------|------|---------|
| OK | 200/201/204 | 0 |
| ValidationError | 400 | 5 |
| NotFoundError | 404 | 7 |
| RateLimitError | 429 | 4 |
| ConfigError / StorageError / ProviderError | 500 | 2/3 |
| LockTimeoutError | 503 | 6 |

---

## 4. 错误码完整映射

| 异常类 | 错误码 | HTTP | CLI | 客户端处理 |
|--------|------|------|-----|----------|
| `ConfigError` | E001 | 500 | 2 | 检查配置 |
| `ConfigFileNotFoundError` | E001.1 | 500 | 2 | 已加载默认 |
| `ConfigFieldMissingError` | E001.2 | 500 | 2 | 提示必填 |
| `ConfigTypeMismatchError` | E001.3 | 500 | 2 | 提示类型 |
| `ProviderError` | E002 | 500 | 3 | 报告 Provider |
| `ProviderAPIKeyMissingError` | E002.1 | 500 | 3 | 提示设 `*_API_KEY` |
| `ProviderRateLimitError` | E002.2 | 429 | 4 | 退避 60s |
| `ProviderNetworkError` | E002.3 | 500 | 3 | 重试 3 次 |
| `ProviderTimeoutError` | E002.4 | 500 | 3 | 增大 timeout |
| `EmbedderPermanentError` | E002.5 | 500 | 3 | → permanent_failure |
| `StorageError` | E003 | 500 | 2 | 报告存储 |
| `FileIOError` | E003.1 | 500 | 2 | 检查权限 |
| `JSONCorruptedError` | E003.2 | 500 | 2 | 启动时隔离 |
| `DiskFullError` | E003.3 | 500 | 2 | 清理 |
| `PathNotAllowedError` | E003.4 | 403 | 6 | 检查 data_root |
| `ValidationError` | E004 | 400 | 5 | 报告参数 |
| `CategoryNotInWhitelistError` ⭐ | E004.1 | 400 | 5 | 询问扩白名单 |
| `CategoryDepthExceededError` ⭐ | E004.2 | 400 | 5 | 提示 ≤ 4 层 |
| `CategoryPathInvalidError` ⭐ | E004.3 | 400 | 5 | 路径格式 |
| `SchemaVersionMismatchError` | E004.4 | 400 | 5 | 跑 migrate |
| `ULIDFormatError` | E004.5 | 400 | 5 | ID 格式 |
| `NotFoundError` | E005 | 404 | 7 | 资源不存在 |
| `MemoryNotFoundError` | E005.1 | 404 | 7 | 记忆不存在 |
| `CategoryNotFoundError` | E005.2 | 404 | 7 | 分类不存在 |
| `TagNotFoundError` | E005.3 | 404 | 7 | 标签不存在 |
| `PermissionError` | E006 | 403 | 6 | 权限不足 |
| `LockTimeoutError` ⭐ | E006.1 | 503 | 6 | 重试 3 次（0.1s 指数退避）|
| `AccessDeniedError` | E006.2 | 403 | 6 | 检查 agent_role |
| `RoleMismatchError` | E006.3 | 403 | 6 | 角色不匹配 |
| `RateLimitError` | E007 | 429 | 4 | 退避 |
| `EmbeddingQueueFullError` | E007.1 | 429 | 4 | 增大 queue_max_size |
| `LocalQueueBackpressureError` | E007.2 | 429 | 4 | 减少并发 store |

⭐ = v2.0 新增（v0.5 三大边界问题对应错误码）

---

## 5. 与 v1.0.0 的兼容性

### 5.1 破坏性变更

| 变更 | v1.0.0 | v2.0 | 迁移 |
|------|--------|------|------|
| `store()` 参数 | `(content, metadata, importance)` | +`category` 必填 | 旧调用必须加 `category` |
| `query()` 返回 | `list[dict]` | `list[SearchResult]` | 改用 `result.mem_id` |
| `MemoryEntry` schema | version=1 | version=2 | 自动迁移 |
| 删除模块 | LCMCompressor / GraphStore | — | 移除引用 |
| 删除类 | `Entity` / `Relation` | — | 重写调用方 |

### 5.2 兼容部分

- **Provider**：`BaseLLMProvider` / `BaseEmbedderProvider` 完全复用
- **YAML 配置**：1.x 自动迁移 2.x（缺失字段填默认）
- **适配器 import**：`from agentmemory.adapters import ClaudeCode` 路径不变
- **CLI 命令**：`store / query / list / forget / stats` 名不变
- **Web 端口**：5000（Flask）/ 8765（FastAPI）不变
- **dict 协议**：`mh.store(**dict)` 向后兼容

### 5.3 迁移工具

```bash
agentmemory migrate-v1-to-v2 --src ./data --dst ./memory_library
# 1. 扫描 ./data/vectors.json + ./memory/MEMORY.md
# 2. 推断分类（文件名 + 前缀） 3. schema_version=1 → 2
# 4. 写入 ./memory_library/       5. 备份 ./data.bak-<date>/
```

**迁移期 dual-read**：`data_root=./data`（v1）只读 + deprecation warning；`data_root=./memory_library`（v2）读写。

---

## 6. 适配器约定

### 6.1 接口

```python
class FrameworkAdapter(Protocol):
    framework_name: str  # "claude_code" | "openclaw" | "langchain" | "openai_agents" | "crewai"

    def __init__(self, mh: MemoryHermes) -> None: ...

    async def on_session_start(self, session_id: str) -> None:
        """会话开始：注入相关记忆到上下文"""
        ...

    async def on_user_turn(self, user_msg: str) -> list[SearchResult]:
        """用户发言：prefetch"""
        ...

    async def on_assistant_turn(self, user_msg: str, assistant_msg: str) -> None:
        """助手回复：sync_turn()"""
        ...

    async def on_session_end(self, summary: str) -> str:
        """会话结束：on_session_end()"""
        ...
```

### 6.2 5 个适配器 + 错误处理规则

| 框架 | 文件 | 通信方式 |
|------|------|---------|
| ClaudeCode | `adapters/claude_code.py` | MCP stdio |
| OpenClaw | `adapters/openclaw.py` | HTTP + skill 协议 |
| LangChain | `adapters/langchain.py` | BaseMemory 接口 |
| OpenAI Agents | `adapters/openai_agents.py` | function tool |
| CrewAI | `adapters/crewai.py` | agent tool |

**错误处理规则**：适配器异常**不得**中断 framework 主循环；应捕获后仅记 TieredLog + 降级返回；不得绕过 `sync_turn` 直接调 `store`（调试除外）。

---

## 7. 版本与文档元信息

| 项 | 值 |
|----|---|
| 公开 API 版本 | `2.0.0` (SemVer) |
| MemoryEntry schema | `version=2`（锁定）|
| HTTP 路径前缀 | `/v2/` |
| 配置 schema | `version: "2.0.0"` |
| Protocol 兼容 | 新增方法允许，删除方法走 v3 |
| 公开方法数 | 12 |
| HTTP 端点数 | 16 |
| 错误码数 | 22（v2.0 新增 5）|
| Pydantic 模型数 | 3 |
| 适配器数 | 5 |

---

_本 API 契约由 architect 在任务 `44b99bdb-4f36-401c-99fb-34d20af8d4d9` 产出 · 2026-06-05_
_所有方法有 Type Hint + 异常 + 性能预算 + 示例；所有错误码有 HTTP/CLI 映射_
