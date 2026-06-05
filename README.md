# AgentMemory v2.0

> 交响乐技能家族成员 | 双轨检索 + 图书馆分类 | 多 Agent 共享 | Provider 自适应

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)

AgentMemory 是一个面向 AI Agent 的持久化记忆系统，基于 **双轨检索 + 图书馆分类** 架构，为 LLM 应用提供长期记忆能力。

---

## 核心设计

### 双轨检索

AgentMemory 用两条互补的轨道组织记忆：

```
同一本书（一条记忆）：
├─ 分类/标题/作者（图书馆分类轨）→ 精确查找，权限边界
└─ 全文被索引（Embedding 向量轨）→ 语义搜索，模糊匹配
```

**两条轨道互补，不是替代。** Embedding 负责"找到相关内容"，分类负责"精确锁定 + 人类可理解"。

### 核心模块

| 模块 | 职责 |
|------|------|
| `DataLake` | `.md` 文件 = 记忆本身，删文件 = 删记忆 |
| `Library` | 分类白名单 + 4 层深度校验 |
| `TagIndex` | 标签倒排索引（JSON） |
| `EmbeddingStateMachine` | pending→generating→completed 状态机 + 重试 |
| `TieredLog` | 热层 7 天 + 冷层 gzip 归档 |
| `SearchEngine` | 双轨融合（向量 + 分类 + Tag RRF 融合） |
| `DecayEngine` | 遗忘引擎（基于访问/重要性/时效三因子） |
| `Providers` | LLM / Embedder / VectorStore 三层抽象 |

---

## 安装

```bash
pip install git+https://github.com/YintaTriss/AgentMemory.git
```

### 前置依赖

```bash
# 向量模型（可选，默认用确定性 hash 向量）
pip install usearch

# Web 面板（可选）
pip install flask flask-cors

# API 服务（可选）
pip install fastapi uvicorn sse-starlette
```

---

## 快速开始

```python
from agentmemory import MemoryHermes

mh = MemoryHermes()

# 存储记忆
memory_id = await mh.store(
    content="石榴籽项目省赛答辩在 2026-06-15",
    category=["A.项目", "石榴籽", "语料"],
    importance=0.8,
    tags=["省赛", "PPT"]
)

# 查询记忆（双轨融合）
results = await mh.query("省赛是什么时候")
for r in results:
    print(f"[{r.score:.2f}] {r.content[:60]}...")

# 分类列举
ids = await mh.list(category=["A.项目", "石榴籽"])

# 主动遗忘
await mh.forget(memory_id)
```

---

## 配置

AgentMemory 默认使用百炼（Bailian）API，通过环境变量配置：

```bash
# 必需
export BAILIAN_API_KEY="your-api-key"

# 可选（默认使用百炼）
export OPENAI_API_KEY="your-openai-key"

# 可选 Embedder
export DASHSCOPE_API_KEY="your-dashscope-key"
```

配置文件 `agentmemory.yaml`（可选）：

```yaml
version: "2.0.0"
data_root: "./memory_library"

providers:
  llm:
    type: "bailian"
    model: "qwen3.6-plus"
  embedder:
    type: "dashscope"
    model: "text-embedding-v3"
    dimensions: 1024
  vector_store:
    type: "usearch"  # usearch | mock
    path: "./memory_library/.vectors"

decay:
  enabled: true
  forget_threshold: 0.2
  archive_threshold: 0.5
  half_life_days: 30
```

---

## 架构总览

```
┌─────────────────────────────────────────────┐
│              用户层 / Agent 层              │
│   ClaudeCode · OpenClaw · LangChain · CLI   │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│           MemoryHermes（统一入口）           │
│   store / query / list / forget / prefetch  │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│              核心引擎层（11 模块）            │
│                                             │
│  DataLake  Library  TagIndex  TieredLog    │
│  SearchEngine  HybridRetriever  DecayEngine│
│  EmbeddingStateMachine  Providers          │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│            Providers 抽象层                  │
│  LLM · Embedder · VectorStore（可插拔）     │
└─────────────────────────────────────────────┘
```

---

## Provider 系统

AgentMemory 内置多个 Provider，支持切换：

### Embedder

| Provider | 说明 |
|----------|------|
| `mock` | 确定性 hash 向量，零依赖，测试用 |
| `openai` | OpenAI Embedding API |
| `minimax` | Minimax Embedding API |
| `dashscope` | 阿里百炼 / 通义 Embedding API |

### LLM

| Provider | 说明 |
|----------|------|
| `bailian` | 阿里百炼（默认）|
| `openai` | OpenAI ChatGPT |
| `minimax` | Minimax |
| `mock` | 确定性 Mock，测试用 |

### VectorStore

| Provider | 说明 |
|----------|------|
| `usearch` | USearch 高性能向量索引（默认）|
| `mock` | 内存向量，测试用 |

---

## 写入不阻塞

`store()` 是非阻塞的：

```
调用 store() → 立即写入 .md 文件 → 入队 embedding → 返回 mem_id（<50ms）
                                            ↓
                                    后台 worker 生成向量
                                            ↓
                                    完成 → 向量可搜
```

Embedding 状态可见：`query()` 返回的 `SearchResult` 包含 `embedding_state`。

---

## 多 Agent 共享

> ⚠️ **v2.0 部分：MultiAgent 模块规划中，完整实现见 Roadmap**

多 Agent 通过共享 NDJSON 日志同步：

```python
# Agent A
await mh.sync_turn(
    user_msg="帮我整理石榴籽语料",
    assistant_msg="好的，已整理 200 条东乡语词汇",
    category=["A.项目", "石榴籽"]
)

# Agent B（另一进程）
events = await shared_log.read_since(offset=12345)
```

---

## API 服务

启动 HTTP API（端口 8765）：

```bash
agentmemory serve --port 8765
```

### 主要端点

| Method | Path | 用途 |
|--------|------|------|
| POST | `/v2/memories` | 存储记忆 |
| GET | `/v2/memories/search` | 查询记忆 |
| GET | `/v2/memories/{id}` | 读取单条 |
| DELETE | `/v2/memories/{id}` | 遗忘记忆 |
| GET | `/v2/memories` | 列举记忆 |
| GET | `/v2/stats` | 统计信息 |
| GET | `/v2/library/tree` | 分类树 |
| GET | `/v2/embedding-state/{id}` | 向量化状态 |

---

## Web 管理面板

```bash
agentmemory web --port 5000
```

访问 `http://localhost:5000` 查看记忆统计和分类树。

---

## CLI

```bash
# 存储
agentmemory store "这是一条测试记忆" --category "B.个人" --tags "测试"

# 查询
agentmemory query "测试"

# 列举
agentmemory list --category "B.个人"

# 统计
agentmemory stats

# 触发遗忘检查
agentmemory decay-check
```

---

## v2.0 迁移说明

v2.0 是破坏性升级，主要变化：

### 已删除
- ❌ `L1_lcm_compressor.py`（LLM 事实压缩）→ 改由 Embedder 直接生成 embed text
- ❌ `L2_graph_store.py`（实体图谱）→ Tag 共现不建图
- ❌ `FactType` / `Entity` / `Relation` 数据类

### 接口变化
- `store()` 增加 `category` 必填参数
- `query()` 返回 `SearchResult` 对象（非 dict）
- `MemoryEntry.schema_version` 升级为 2

### 向后兼容
- 配置文件 YAML 1.x 自动迁移（缺失字段填充默认值）
- 5 个 framework adapter 保留，import 路径不变

---

## Roadmap

### v2.0（当前）
- [x] 核心数据层（DataLake / Library / TagIndex / TieredLog）
- [x] Provider 抽象层（LLM / Embedder / VectorStore）
- [x] 双轨检索（SearchEngine + HybridRetriever）
- [x] Embedding 状态机（5 状态 + 重试）
- [x] DecayEngine 遗忘引擎
- [ ] **MultiAgent（文件锁 + 共享日志）** — ⚠️ 规划中
- [ ] **Config v2.0 schema** — ⚠️ 需升级

### v2.1（下一版）
- [ ] Chroma 向量后端（可选生产级）
- [ ] 实时 WebSocket（embedding 状态推送）
- [ ] 跨主机分布式锁（基于 etcd）
- [ ] 语义重排序（Cross-Encoder）

### v3.0（远期）
- [ ] 多模态记忆（图片、音频）
- [ ] Agent 间记忆共享协议

---

## 文档索引

| 文档 | 内容 |
|------|------|
| `docs/v2-architecture.md` | v2.0 完整架构设计（1500+ 行）|
| `docs/api-contract.md` | Python API + HTTP 端点契约 |
| `docs/providers-contract.md` | Provider 接口协议 |
| `docs/ARCHITECTURE.md` | 补充架构说明 |
| `docs/investigation-report.md` | v1.0 现状调查报告 |

---

## 项目结构

```
AgentMemory/
├── agentmemory/
│   ├── data/               # 核心数据层
│   │   ├── datalake.py         # DataLake（.md 文件存储）
│   │   ├── library.py          # Library（分类白名单）
│   │   ├── tag_index.py        # TagIndex（倒排索引）
│   │   ├── embedding_state.py  # Embedding 状态机
│   │   └── tiered_log.py       # TieredLog（分层日志）
│   ├── providers/           # Provider 抽象层
│   │   ├── protocols.py        # Protocol 接口定义
│   │   ├── registry.py         # Provider 注册表
│   │   ├── embedder.py          # Embedder 实现
│   │   ├── llm.py              # LLM 实现
│   │   └── vectorstore.py       # VectorStore 实现
│   ├── search/              # 检索引擎
│   │   ├── search_engine.py     # SearchEngine（双轨融合）
│   │   └── hybrid_retriever.py # HybridRetriever（混合打分）
│   ├── api/
│   │   ├── v2/app.py          # FastAPI v2（端口 8765）
│   │   └── app.py             # FastAPI v1
│   ├── web/
│   │   └── app.py             # Flask 管理面板（端口 5000）
│   ├── decay_engine.py       # DecayEngine（遗忘引擎）
│   ├── config.py             # 配置管理
│   ├── memory_manager.py     # MemoryHermes 入口
│   └── errors.py             # 错误码体系
├── docs/                    # 架构文档
├── tests/                   # 测试套件
└── README.md
```

---

## License

MIT

---

_AgentMemory v2.0 | 交响乐技能家族 | 2026-06-05_
