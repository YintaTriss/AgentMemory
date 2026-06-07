# AgentMemory v0.3

> **双轨 + 图书馆记忆系统** — 为 AI Agent 打造的持久化、可迁移、热插拔的记忆基础设施

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![Core Dependencies](https://img.shields.io/badge/Core%20Deps-8-green.svg)](#dependencies)

---

## 核心特性

| 特性 | 说明 |
|------|------|
| **双轨检索** | Embedding 向量（语义）+ 图书馆分类（精确），同时生效，永不取舍 |
| **3 组件架构** | L4 文件持久化 · L3 向量语义搜索 · L1 上下文压缩

> ⚠️ L4/L3/L1 是组件编号而非层级顺序。L2 在 v0.3 中被移除（原 Graph-DB 过度设计）。 |
| **零依赖运行** | 默认 HashEmbedder，无需任何 API Key 或外部服务 |
| **热插拔** | 整个记忆库是文件夹，复制即迁移 |
| **并发安全** | `portalocker` + `msvcrt/fcntl`，Windows / Unix 均支持文件锁 |
| **安全防护** | P0 注入检测 + Unicode 规范化 + trust_score 阈值 + HMAC 完整性验证 |
| **多框架适配** | openclaw / Claude Code / CrewAI / LangChain / OpenAI Agents |

---

## 设计哲学：记忆如图书馆

> **书籍本身不变，但目录系统让查找变得精确。**

同一份记忆同时存在于两条轨道，永远双轨并存：

```
同一份记忆：
├─ 图书馆分类轨（.md 本体 + meta.json 元数据）→ 精确查找，管理边界
└─ Embedding 向量轨（vec.json）→ 语义搜索，模糊匹配
```

---

## 架构总览

```
┌──────────────────────────────────────────────────────────────┐
│                     宿主应用 (Agent / CLI)                   │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│  MemoryManager（统一异步 API）                                │
│  ├─ add() / get() / delete() / search() / list()          │
│  └─ compress_for_context() → L1 压缩注入 prompt              │
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
          │
          ▼ (读取时)
┌─────────────────────┐
│   L1LCMCompressor   │
│   （上下文压缩）      │
│                     │
│  实体提取 → 摘要     │
│  → AI Context 注入   │
└─────────────────────┘
```

### 三层职责

| 层级 | 组件 | 职责 |
|------|------|------|
| **L4** | `L4FilesStore` | `.md` 内容 + `.meta.json` 元数据 + `.vec.json` 向量，文件系统持久化 |
| **L3** | `L3LanceDBStore` | LanceDB 向量语义搜索，支持按 category_path / tags 过滤 |
| **L1** | `L1LCMCompressor` | 记忆压缩为摘要 + 实体列表，注入 AI prompt 时使用 |

### 双轨检索

| 轨道 | 方法 | 适用场景 |
|------|------|---------|
| **轨道一** | 图书馆分类（category_path / tags） | 精确查找、按领域筛选 |
| **轨道二** | Embedding 向量（语义相似度） | 模糊搜索、语义关联 |

### 图书馆分类规范

最多 4 层，用 `/` 分隔：

```
Project/Shiliuzi/Corpus/NLLB-Training
Project/Shiliuzi/Competition/Provincial
AI/LLM/GPT/微调
AI/Agent/记忆系统/VCP
```

---

## 核心组件

| 组件 | 文件 | 说明 |
|------|------|------|
| `MemoryManager` | `manager.py` | 统一异步 API，add/get/delete/search/list/compress |
| `L4FilesStore` | `l4_files.py` | md + meta.json + vec.json 三文件存储 |
| `L3LanceDBStore` | `l3_lancedb.py` | LanceDB 向量语义搜索 |
| `L1LCMCompressor` | `l1_lcm.py` | 上下文压缩，FactType 实体提取 |
| `SyncManager` | `sync.py` | L4 ↔ L3 双轨同步 |
| `LibraryClassifier` | `library.py` | 4 层分类自动推断 |
| `Embedder` | `embedder.py` | HashEmbedder（零依赖）/ DashScopeEmbedder / 本地模型 |
| `IntegrityVerifier` | `integrity.py` | HMAC 签名验证 |

---

## 数据结构

每条记忆 = 同目录下的 3 个文件：

```
memory/
├── abc123.md           # 人类可读内容
├── abc123.meta.json    # 元数据
└── abc123.vec.json    # 向量数据
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
  "flagged": false
}
```

---

## 并发控制

写入安全由 `portalocker`（跨平台文件锁）保证，Windows 回退到 `msvcrt`，Unix 回退到 `fcntl`：

```python
# L4FilesStore 底层：写操作自动加锁
portalocker.FileLock(f"{memory_id}.lock", timeout=5)
# 读操作：共享锁（Unix fcntl.LOCK_SH / Windows msvcrt.LK_RLCK）
# 写操作：独占锁（Unix fcntl.LOCK_EX / Windows msvcrt.LK_LOCK）
```

---

## 安全防护（P0 级）

| 防护项 | 说明 |
|--------|------|
| **注入检测** | `injection.py`：Unicode 规范化、角色扮演指令检测、越狱模式识别 |
| **trust_score** | 同步前计算，< 0.2 拒绝写入 L3，≥ 0.2 且 flagged 时警告 |
| **HMAC 验证** | `IntegrityVerifier`：记忆完整性签名，防篡改 |

---

## 适配器生态

| 适配器 | 文件 | 框架 |
|--------|------|------|
| OpenClaw | `adapters/openclaw.py` | OpenClaw Agent |
| Claude Code | `adapters/claude_code.py` | Anthropic Claude Code |
| CrewAI | `adapters/crewai.py` | CrewAI Agents |
| LangChain | `adapters/langchain.py` | LangChain |
| OpenAI Agents | `adapters/openai_agents.py` | OpenAI Agents SDK |

---

## 安装

```bash
cd AgentMemory
pip install -e .
```

### 依赖项

**核心依赖（8 个）：**

```
httpx, aiofiles, portalocker,
pydantic, aiofiles.os, json, pathlib, datetime
```

**可选依赖：**

| 包 | 功能 | 默认 |
|----|------|------|
| `lancedb` | 向量数据库 | 纯 JSON 回退 |
| `dashscope` | DashScope Embedding API | HashEmbedder 零依赖 |
| `bge-large-zh` | 本地 Embedding 模型 | HashEmbedder 零依赖 |

### Embedder 选择

```python
from agent_memory import MemoryManager

# 默认：HashEmbedder（零依赖，无需 API Key）
mm = MemoryManager()

# OpenAI Embedding
mm = MemoryManager(embedder="openai")

# DashScope（阿里）
mm = MemoryManager(embedder="dashscope")

# 本地模型（bge-large-zh）
mm = MemoryManager(embedder="local")
```

### 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `AGENT_MEMORY_DIR` | `memory` | 记忆存储目录 |
| `AGENT_MEMORY_DATA_DIR` | `data` | 向量数据目录 |
| `DASHSCOPE_API_KEY` | - | DashScope API（可选） |
| `OPENAI_API_KEY` | - | OpenAI API（可选） |

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

    # 语义搜索
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
    compressed = await mm.compress_for_context([mem_id])
    print(compressed)

    # 删除
    await mm.delete(mem_id)

asyncio.run(main())
```

### CLI

```bash
# 添加记忆
python -m agent_memory.cli add "测试记忆" --category "test" --tags "demo"

# 语义搜索
python -m agent_memory.cli search "测试"

# 列出所有
python -m agent_memory.cli list

# 查看单条
python -m agent_memory.cli show <memory_id>

# 按分类列出
python -m agent_memory.cli list --category "Project/Shiliuzi"

# 统计
python -m agent_memory.cli stats

# 同步 L4 → L3
python -m agent_memory.cli sync

# 删除
python -m agent_memory.cli delete <memory_id>
```

### MemoryManager API

| 方法 | 返回 | 说明 |
|------|------|------|
| `add(content, category_path, tags, importance)` | `str` (memory_id) | 添加记忆，L4 + L3 双轨写入 |
| `get(memory_id)` | `dict \| None` | 按 ID 获取 |
| `delete(memory_id)` | `bool` | 删除，L4 + L3 同时清除 |
| `search(query, limit, category_path)` | `list[dict]` | 向量语义搜索 |
| `list(category_path)` | `list[dict]` | 按分类列出 |
| `compress_for_context(memory_ids)` | `str` | L1 压缩，生成 AI 可用摘要 |
| `stats()` | `dict` | 统计：总数、分类、标签分布 |

---

## 与其他系统对比

| 系统 | 数据形态 | 索引方式 | 多 Agent | NAS 支持 | 零依赖 |
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
| 去掉相变机制 | 文件 + 向量永远是双轨 | VCP 验证：不需要相变 |
| 并发写入控制 | portalocker 文件锁 | 多 Agent 并发写入场景 |
| 记忆关联 | AI 自动推断 + 用户手动 | 平衡自动化和精确性 |
| Embedder 默认 Hash | 零外部依赖 | 君子生非异也 |

---

## 许可证

MIT License — 可自由使用、修改和分发。

---

_AgentMemory — 记忆如图书馆，双轨并存，永不取舍。_
