<p align="center">
  <a href="README_EN.md">English</a> |
  <a href="README.md">简体中文</a> |
  <a href="README_ZHT.md">繁體中文</a> |
  <a href="README_JA.md">日本語</a> |
  <a href="README_KO.md">한국어</a> |
  <a href="README_FR.md">Français</a>
</p>

# AgentMemory v0.3

> **双轨 + 图书馆记忆系统** — 为 AI Agent 打造的持久化、可迁移、热插拔的记忆基础设施

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)

---

## 设计哲学：记忆如图书馆

> **书籍本身不变，但目录系统让查找变得精确。**

传统记忆系统的核心矛盾：**语义搜索（模糊匹配）与精确分类（按领域筛选）只能二选一**。

AgentMemory 的答案：**双轨并存，永不取舍。**

同一份记忆同时存在于两条轨道：

```
同一份记忆：
├─ 图书馆分类轨（.md 本体 + .meta.json 元数据）→ 精确查找，管理边界
└─ Embedding 向量轨（.vec.json）→ 语义搜索，模糊匹配
```

**颗粒度保证**：最少 3 层分类（馆分类 / 书架分类 / 书分类），确保每一份记忆都能被精确归类，最大层数不设限，按需延伸。

---

## 架构总览

```
┌──────────────────────────────────────────────────────────────┐
│                     宿主应用 (Agent / CLI / Web API)        │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│  MemoryManager（统一异步 API）                                │
│  add() / get() / delete() / search() / list() / compress() │
└────────────────────────────┬─────────────────────────────────┘
                             │
          ┌──────────────────┴──────────────────┐
          ▼                                      ▼
┌─────────────────────┐              ┌─────────────────────────┐
│   L4FilesStore      │              │   L3LanceDBStore        │
│   （文件持久化）      │              │   （向量语义搜索）        │
│                     │              │                         │
│  memory/<id>.md     │◄──── sync ──►│  LanceDB Table         │
│  memory/<id>.meta   │              │  (语义相似度检索)        │
│  memory/<id>.vec.json              │                         │
└─────────────────────┘              └─────────────────────────┘
          │                                      │
          ▼ (读取时)                              │
┌─────────────────────┐              ┌─────────────────────────┐
│   L1LCMCompressor   │              │   BM25 混合检索          │
│   （上下文压缩）      │              │   (纯 Python, 零依赖)    │
│                     │              │                         │
│  实体提取 → 摘要     │              │  k1=1.2, b=0.75         │
│  → AI Context 注入   │              │  α=0.7 (向量/BM25)       │
└─────────────────────┘              └─────────────────────────┘
```

### 三层职责

| 层级 | 组件 | 职责 |
|------|------|------|
| **L4** | `L4FilesStore` | `.md` 内容 + `.meta.json` 元数据 + `.vec.json` 向量，文件系统持久化 |
| **L3** | `L3LanceDBStore` | LanceDB 向量搜索（不可用时自动降级为纯 JSON + numpy），支持 BM25 混合检索 |
| **L1** | `L1LCMCompressor` | 记忆压缩为摘要 + 实体列表，注入 AI prompt 时使用，支持 query 相关性增强 |
| **L3** | `SyncManager` | L4 ↔ L3 双轨同步，自动同步关键词检测，portalocker 文件锁 |
| **L3** | `LibraryClassifier` | 5 大顶层类自动分类，关键词归一化评分，缓存分词 |
| **L3** | `IntegrityVerifier` | HMAC-SHA256 文件完整性签名，防篡改 |

### 双轨检索

| 轨道 | 方法 | 适用场景 |
|------|------|---------|
| **轨道一** | 图书馆分类（category_path / tags） | 精确查找、按领域筛选 |
| **轨道二** | Embedding 向量（语义相似度） | 模糊搜索、语义关联 |

### 图书馆分类规范

最少 3 层（馆分类 / 书架分类 / 书分类，确保颗粒度），最大不设限，动态层数：

```
项目/石榴籽/语料/NLLB训练                 ✅ 最少 3 层
项目/石榴籽/语料/NLLB训练/2026-06           ✅ 可继续延伸（不设上限）
学习/AI/Transformer                        ✅ 3 层
AI/Agent/记忆系统/VCP                      ✅ 4 层
```

---

## 核心组件

| 组件 | 文件 | 说明 |
|------|------|------|
| `MemoryManager` | `manager.py` | 统一异步 API，add/get/delete/search/list/compress |
| `L4FilesStore` | `l4_files.py` | md + meta.json + vec.json 三文件存储，portalocker 文件锁 |
| `L3LanceDBStore` | `l3_lancedb.py` | LanceDB 向量搜索 + JSON Fallback + BM25 混合检索 |
| `L1LCMCompressor` | `l1_lcm.py` | 上下文压缩，FactType 实体提取，query 相关性增强 |
| `SyncManager` | `sync.py` | L4 ↔ L3 双轨同步，auto_sync 关键词检测 |
| `LibraryClassifier` | `library.py` | 5 大类关键词分类，层级路径验证，缓存分词 |
| `Embedder` | `embedder.py` | HashEmbedder（零依赖）/ DashScopeEmbedder（OpenAI-Compatible API）|
| `IntegrityVerifier` | `integrity.py` | HMAC-SHA256 签名验证 |

---

## 数据结构

每条记忆 = 同目录下的 3 个文件：

```
memory/
├── abc123.md           # 人类可读内容
├── abc123.meta.json   # 元数据
└── abc123.vec.json    # 向量数据（每个记忆一个，随 .md 同目录）
```

### meta.json 格式

```json
{
  "id": "abc123...",
  "created_at": "2026-06-07T00:00:00",
  "updated_at": "2026-06-07T00:00:00",
  "category_path": "Project/Shiliuzi/Training",
  "tags": ["nllb", "success"],
  "source": "manual",
  "importance": 0.8,
  "trust_score": 1.0,
  "flagged": false,
  "signed_at": 1759804800.123
}
```

---

## 实现细节：那些让代码更优雅的小巧思

### 原子写入：tempfile + os.replace（Windows 兼容）

L4 文件写入使用两步原子操作：

```python
# 1. 写入临时文件
tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tmp", dir=base_dir)
tmp.write(content); tmp.close()
# 2. os.replace 原子替换（Windows 也保证原子性）
os.replace(tmp.name, target_path)
```

os.rename 在 Windows 上不能跨驱动器工作，os.replace 则可以。这是很多跨平台 Python 项目的盲区。

### portalocker：跨平台文件锁

```python
with _portalocker_lock(lock_path):
    # 写操作自动加锁
    ...
```

`portalocker` 优先，Windows 用 msvcrt，Unix 用 fcntl 回退。读操作用共享锁，写操作用独占锁。`contextmanager` 模式确保锁一定释放，即使异常也不漏。

### `_embed_fn` 模式：sync/async 统一接口

DashScopeEmbedder 的 `embed()` 是 `async def`，HashEmbedder 是 `def`，调用方用统一接口：

```python
# SyncManager.__init__ 中：
if hasattr(embedder, 'embed_sync'):
    self._embed_fn = embedder.embed_sync
else:
    self._embed_fn = embedder.embed
```

运行时检测，不需要类型判断。Embedder 基类提供 `embed_sync` 属性，async 实现包装为子线程运行。

### 缓存分词（LibraryClassifier）

关键词匹配时每次都重新分词是浪费。`_tokenize()` 用 `@functools.lru_cache(maxsize=512)` 缓存：

```python
@functools.lru_cache(maxsize=512)
def _tokenize(self, text: str) -> tuple[str, ...]:
    ...
    return tuple(tokens)  # tuple 可哈希，才能做 lru_cache 的 key
```

返回 `tuple` 而非 `list`，因为 tuple 可哈希、适合做缓存 key。

### 评分归一化：sqrt(keyword_count) 防止大类欺负小类

分类词典中"项目"有 20+ 个关键词，"偏好"只有 8 个。直接累加会导致大类永远胜出。

```python
scores[category] = cat_raw / (len(keywords) ** 0.5)  # 开方归一化
```

用 `sqrt` 而非直接除以 `len(keywords)`：大列表有帮助，但不能主导结果。

### Unicode 规范化 + 双轨检测（injection.py）

检测混淆攻击需要两步：

```python
texts_to_check = [text, _normalize_text(text)]  # 原始文本 + 规范化文本
```

规范化步骤包括：零宽字符处理、HTML 实体 decode、全角→半角、Unicode 转义序列解码、反斜杠词还原、BIDI 控制符清除。混淆攻击（`rm\u200b-rf`、`rm&#x72;f`）在规范化后无处遁形。

### BM25 参数可配置

BM25 的 `k1`（词频饱和）和 `b`（文档长度归一化）可按场景调整：

```python
# k1=1.2, b=0.75 是 Lucene 默认值
l3_store.search_bm25(query, top_k=5, k1=1.2, b=0.75)
```

### 混合搜索 α 加权可调

向量相似度和 BM25 的混合权重 α 默认 0.7（向量 70%，BM25 30%）：

```python
alpha = 0.7
final_score = alpha * vec_score + (1 - alpha) * bm25_score
```

### 5 分钟 stats 缓存

`MemoryManager.stats()` 有本地缓存，避免每次都读文件系统：

```python
age = (datetime.now() - self._stats_timestamp).total_seconds()
if age < 300:  # 5 分钟内直接返回缓存
    return self._stats_cache
```

### `access_count` 持久化（不是内存变量）

很多记忆系统把访问计数放内存，重启就丢。AgentMemory 把 `access_count` 写回 `.meta.json`，每次 `load_existing()` 自动 +1 并持久化。

### query 参数增强 L1 压缩的相关性排序

`compress_for_context(memory_ids, query="...")` 支持 query 参数，同 query 关键词重合的记忆在同重要性层级中排到前面：

```python
def _relevance_score(mem):
    if not query_toks: return 0
    return sum(1 for tok in query_toks if tok in mem.get("content","").lower())
```

---

## 安全防护（P0 级）

| 防护项 | 实现位置 | 说明 |
|--------|----------|------|
| **注入检测** | `utils/injection.py` | Unicode 规范化 + 双轨检测（原始/规范化双重匹配），50+ 攻击模式，含 JNDI/SSTI/Shellshock/Prompt Injection |
| **trust_score** | `sync.py` | < 0.2 拒绝写入 L3，≤ 0.35 标记 flagged 并警告 |
| **HMAC 验证** | `integrity.py` | HMAC-SHA256 签名，写入 `.meta.json` 的 `signed_at` 字段 |
| **API Key 校验** | `embedder.py` | `DashScopeEmbedder.__init__` 立即校验，缺失抛 RuntimeError |
| **LanceDB 注入防护** | `web.py` / `cli.py` | category_path 中单引号转义为 `''`（SQL 标准转义）|
| **原子写入** | `l4_files.py` | tempfile + os.replace，进程崩溃也不留脏文件 |
| **文件锁** | `l4_files.py` | portalocker 独占锁，写操作互斥 |

---

## 并发安全

写入安全由 `portalocker` 保证，Windows 回退到 `msvcrt`，Unix 回退到 `fcntl`：

```python
# L4FilesStore 写操作：自动加独占锁
with _portalocker_lock(lock_path):
    ...

# 读操作：自动加共享锁
with _file_lock(lock_path, exclusive=False):
    ...
```

---

## 安装

```bash
cd AgentMemory
pip install -e .
```

### 依赖项

**运行时依赖（仅有 3 个，无需其他服务）：**

```
httpx>=0.25.0    # DashScope API 异步调用
aiofiles>=23.0.0 # 异步文件 IO
pydantic>=2.5    # 数据验证（运行时必需）
```

**可选依赖：**

```bash
pip install agentmemory[web]     # Web API 支持（fastapi + uvicorn）
pip install agentmemory[lancedb] # LanceDB 向量数据库（高性能场景）
pip install agentmemory[dev]     # 开发依赖（pytest 等）
```

> LanceDB 不可用时（未安装），系统自动降级为纯 JSON + numpy 实现，零额外依赖即可运行。

### Embedder 选择

```python
from agent_memory import MemoryManager, get_embedder

# 默认（auto 模式）：无 API Key → HashEmbedder（零依赖，离线可用）
#                    有 EMBEDDING_API_KEY → OpenAI-Compatible 嵌入（任意兼容 provider）
mm = MemoryManager()

# 显式指定（无 API Key 时立即抛 RuntimeError，不静默降级）
mm = MemoryManager(embedder=get_embedder(backend="openai-compat"))

# 等价于默认 auto 模式
mm = MemoryManager(embedder=get_embedder())
```

> **模型不绑定**：内部使用 OpenAI-Compatible API 格式，自动识别任意支持 `/v1/embeddings` 接口的 provider（DashScope / Minimax / OpenAI / 本地 Embedding Server 等）。

### 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `AGENT_MEMORY_DIR` | `memory` | 记忆存储目录 |
| `AGENT_MEMORY_DATA_DIR` | `data` | 向量数据目录（LanceDB 表 / JSON Fallback） |
| `EMBEDDING_API_KEY` | - | OpenAI-Compatible API（推荐，支持任意兼容 provider） |
| `DASHSCOPE_API_KEY` | - | 向后兼容，与 `EMBEDDING_API_KEY` 二选一 |
| `OPENAI_API_KEY` | - | 向后兼容 |

---

## 快速开始

### Python API

```python
import asyncio
from agent_memory import MemoryManager

async def main():
    mm = MemoryManager()

    # 添加记忆
    mem_id = await mm.add(
        content="NLLB 训练成功完成，词汇准确率达到 85%",
        category_path="Project/Shiliuzi/Training",
        tags=["nllb", "success", "training"],
        importance=0.9
    )
    print(f"Added: {mem_id}")

    # 语义搜索（默认 vector 模式）
    results = await mm.search("NLLB 模型训练")
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:60]}")

    # 按分类列出
    all_memories = await mm.list(category_path="Project/Shiliuzi")
    print(f"Found {len(all_memories)} memories")

    # 统计
    stats = await mm.stats()
    print(f"Total: {stats['total_memories']}, Categories: {stats['categories']}")

    # L1 压缩（注入 AI Context）
    # query 参数：与 query 相关性高的记忆优先展示
    compressed = await mm.compress_for_context([mem_id], query="NLLB训练")
    print(compressed)

    # 删除
    await mm.delete(mem_id)

asyncio.run(main())
```

### CLI

```bash
# 添加记忆（自动分类）
python -m agent_memory.cli add "测试记忆"

# 指定分类和标签
python -m agent_memory.cli add "NLLB训练完成" --category "Project/Shiliuzi/Training" --tags "nllb,done"

# 语义搜索（默认）
python -m agent_memory.cli search "NLLB 模型训练"

# 关键词搜索（BM25，无需向量模型）
python -m agent_memory.cli search "NLLB" --mode bm25

# 混合搜索（向量 + BM25 加权）
python -m agent_memory.cli search "NLLB" --mode hybrid

# 列出所有
python -m agent_memory.cli list

# 按分类列出
python -m agent_memory.cli list --category "Project/Shiliuzi"

# 查看单条
python -m agent_memory.cli show <memory_id>

# 统计
python -m agent_memory.cli stats

# 删除
python -m agent_memory.cli delete <memory_id>

# 显示所有顶层分类
python -m agent_memory.cli category --show-all

# 显示已使用的所有分类路径
python -m agent_memory.cli category --list

# HMAC 签名（新加入的文件夹需要签名）
python -m agent_memory.cli sign memory/ --key "your-secret-key-here"

# HMAC 校验（验证文件夹完整性）
python -m agent_memory.cli verify memory/ --key "your-secret-key-here"

# 重新向量化（更换 embedder 时使用）
python -m agent_memory.cli --json reembed --embedder hash

# 启动 Web API 服务器
python -m agent_memory.cli serve --port 8765
```

### MemoryManager API

| 方法 | 返回 | 说明 |
|------|------|------|
| `add(content, category_path, tags, importance)` | `str` (memory_id) | 添加记忆，L4 + L3 双轨写入 |
| `get(memory_id)` | `dict \| None` | 按 ID 获取 |
| `delete(memory_id)` | `bool` | 删除，L4 + L3 + vec.json 同时清除 |
| `search(query, limit, category_path, mode)` | `list[dict]` | 向量/BM25/混合搜索，支持 mode=vector/bm25/hybrid |
| `list(category_path, limit)` | `list[dict]` | 按分类列出 |
| `compress_for_context(memory_ids, query)` | `str` | L1 压缩，query 参数增强同 query 相关记忆的优先级 |
| `stats()` | `dict` | 统计（5 分钟缓存），总数/分类/存储大小/L3 覆盖率 |

---

## 透明后台（自动记忆捕获）

无需关键词触发，TransparentBackground 自动：

- **心跳捕获**：每 N 分钟自动存储对话片段
- **周期摘要**：每 20 轮自动生成会话摘要（存入"会话/定期摘要"）
- **上下文预取**：回复前自动注入相关记忆到 AI Context

```bash
# 持续运行（每 5 分钟心跳）
agentmemory bg --agent-id main

# 单次触发（适合 cron 调用）
agentmemory bg --agent-id main --once
```

**OpenClaw 配置示例**（每 5 分钟自动记忆）：

```json
{
  "name": "memory-heartbeat",
  "sessionTarget": "isolated",
  "schedule": { "kind": "cron", "expr": "*/5 * * * *", "tz": "Asia/Shanghai" },
  "payload": { "kind": "agentTurn", "message": "agentmemory bg --agent-id main --once" }
}
```

Python API：

```python
from src.adapters.transparent_background import TransparentBackground

tb = TransparentBackground(agent_id="main")

# 回复前预取相关记忆注入上下文
context = await tb.inject_context_for_prompt(
    current_message="省赛的进度怎么样了？",
    max_memories=5,
    max_chars=2000
)
# → "\n\n[相关记忆]\n- [石榴籽/项目] 项目截止日期是 2026-06-15...\n[/相关记忆]"
```

---

## MCP Server（跨平台工具调用）

通过 MCP（Model Context Protocol）暴露记忆工具，支持所有主流 AI Coding 工具：

| 客户端 | 协议 | 配置 |
|--------|------|------|
| Claude Code | MCP stdio | `~/.claude/settings.json` |
| Codex | MCP stdio | `~/.config/codex/config.json` |
| Cursor | MCP stdio/HTTP | Settings → MCP |
| Windsurf | MCP stdio/HTTP | Settings → MCP |

### 启动 MCP Server

```bash
# Claude Code / Codex（stdio 模式）
agentmemory mcp

# 其他客户端（HTTP 模式）
agentmemory mcp --http --port 8765
```

### Claude Code 配置

在 `~/.claude/settings.json` 添加：

```json
{
  "mcpServers": {
    "agentmemory": {
      "command": "agentmemory",
      "args": ["mcp"]
    }
  }
}
```

### MCP 工具列表

| 工具名 | 说明 |
|--------|------|
| `memory_add` | 添加记忆 |
| `memory_search` | 语义/关键词/混合搜索 |
| `memory_list` | 按分类列出 |
| `memory_get` | 获取单条记忆 |
| `memory_delete` | 删除记忆 |
| `memory_stats` | 统计信息 |
| `memory_compress` | L1 上下文压缩 |

### 使用示例

```
# 记住重要信息
Remember: memory_add content="石榴籽省赛答辩 2026-06-15" importance=0.9 tags="石榴籽"

# 搜索相关记忆
Search: memory_search query="省赛时间" limit=5 mode="hybrid"
```

---

## 与其他系统对比

| 系统 | 数据形态 | 索引方式 | 多 Agent | NAS 支持 | 无外部服务依赖 |
|------|---------|---------|---------|---------|-------|
| Hermes | 文件 | 无向量 | 共享工作空间 | 原生 | ✅ |
| VCP | 文件 + 向量双轨 | Tag + 向量 | 共用文件夹 | SQLite 单文件 | ✅ |
| Mem0 | 向量 + 图关系 | 向量 + 关系图 | 多租户 | 需数据库 | ❌ |
| Letta | Memory Blocks | 块索引 | Agent 内存 | 需服务 | ❌ |
| **AgentMemory v0.3** | md + vec.json | 双轨检索 | 共用文件夹 | 原生 | ✅ |

---

## 架构决策记录（v0.3）

| 决策 | 说明 | 原因 |
|------|------|------|
| 去掉 L2 Graph-DB | 三层变四层 | Graph-DB 过度设计，实际只用分类路径就够了 |
| 去掉了相变机制 | 文件 + 向量永远是双轨 | VCP 验证：不需要相变 |
| 并发写入控制 | portalocker 文件锁 | 多 Agent 并发写入场景 |
| Embedder 默认 Hash | 零依赖、确定性 | 生非异也，善假于物也 |
| LanceDB 优先 + JSON Fallback | LanceDB 不可用自动降级 | 高性能场景用 LanceDB，零依赖场景用 JSON |
| BM25 混合检索 | 纯 Python 实现，零额外依赖 | 补充纯关键词搜索场景，无需向量模型 |
| min_depth=3 | 馆/架/书三级结构 | 确保记忆颗粒度，避免顶层过于笼统 |

---

## 许可证

MIT License — 可自由使用、修改和分发。

---

_AgentMemory — 记忆如图书馆，双轨并存，永不取舍。_
