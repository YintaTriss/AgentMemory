# AgentMemory v2.0.1

> 通用、便携、可插拔的 Agent 长期记忆插件
> 一句话：让任何 Agent 框架在 **5 分钟内**接上一套工业级长期记忆

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)

AgentMemory 是一个面向 AI Agent 的持久化记忆系统，基于 **双轨检索 + 图书馆分类** 架构，为 LLM 应用提供工业级长期记忆能力。

---

## 特性（5 维度）

| 维度 | 说明 |
|------|------|
| 易用 | `pip install` + `from agentmemory import MemoryHermes` |
| 可移植 | 纯 Python 3.10+，仅 2 个核心依赖 |
| 强大 | 4 层闭环记忆 + 混合检索 + 半衰期遗忘引擎 |
| 易修改 | Provider 完全抽象（LLM/Embedder/VectorStore） |
| 适配 | 5 个 Agent 框架支持 |

---

## 与 v1.0 对比

| 指标 | v1.0 | v2.0 |
|------|------|------|
| 接口对齐 | 37% | 100% |
| 测试通过 | 68 failed / 38 passed | 100% (目标) |
| API 路由 | 空壳 | 完整 RESTful |
| 多 Agent | 无 | 支持 |
| 遗忘引擎 | 线性加权 | 几何乘积 |

---

## 快速开始

### 安装

```bash
pip install agentmemory
```

### 1 行代码接入

```python
from agentmemory import MemoryHermes

mh = MemoryHermes()
memory_id = await mh.store("用户喜欢蓝色", metadata={"user": "alice"})
results = await mh.query("用户喜欢什么颜色")
print(results)
```

### 配置

```python
from agentmemory import MemoryConfig, get_memory_config

config = MemoryConfig()
# 自定义配置
config.version = "2.0.0"
config.decay.half_life_days = 30.0
config.decay.forget_threshold = 0.2
```

### 多 Agent 共享记忆

```python
from agentmemory import MultiAgentLock, SharedLog, AgentRegistry

# 多 Agent 共享锁
lock = MultiAgentLock(memory_id="task_123")
async with lock:
    log = SharedLog(agent_id="agent_alice")
    await log.append({"action": "store", "content": "..."})
    registry = AgentRegistry()
    await registry.register("agent_alice")
```

### REST API 服务

```python
from agentmemory.api.v2 import create_app
import uvicorn

app = create_app()
uvicorn.run(app, host="0.0.0.0", port=8000)
```

### API 路由

| Method | 路由 | 说明 |
|--------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/v2/memories` | 列出记忆 |
| POST | `/v2/memories` | 创建记忆 |
| GET | `/v2/memories/{id}` | 获取单条 |
| PUT | `/v2/memories/{id}` | 更新 |
| DELETE | `/v2/memories/{id}` | 删除 |
| GET | `/v2/memories/search?q=xxx` | 搜索 |
| GET | `/v2/stats` | 统计 |

---

## 架构概览

```
输入 → L1 压缩 → L2 图谱 → L3 向量 → L4 文件
                         ↓
                      检索 ← 混合搜索（向量 + BM25 + 重要性）
                         ↓
                      遗忘引擎（半衰期衰减）
```

AgentMemory 用**双轨检索**组织记忆：

```
同一本书（一条记忆）：
├─ 分类/标题/作者（图书馆分类轨）→ 精确查找，权限边界
└─ 全文被索引（Embedding 向量轨）→ 语义搜索，模糊匹配
```

**两条轨道互补，不是替代。** Embedding 负责"找到相关内容"，分类负责"精确锁定 + 人类可理解"。

---

## 核心模块

| 模块 | 文件 | 说明 |
|------|------|------|
| MemoryHermes | memory_manager.py | 主管理器，10 个公开方法 |
| DataLake | data/datalake.py | 文件系统存储 |
| Library | data/library.py | 分类白名单 |
| TagIndex | data/tag_index.py | 标签索引 |
| EmbeddingStateMachine | data/embedding_state.py | 异步向量状态机 |
| TieredLog | data/tiered_log.py | 分层日志 |
| SearchEngine | search/search_engine.py | 混合搜索引擎 |
| DecayEngine | decay_engine.py | 半衰期遗忘引擎 |
| MultiAgent | multi_agent.py | 多 Agent 共享 |

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

## 配置参考

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|------|
| `AGENTMEMORY_STORAGE_PATH` | 存储根目录 | `~/.agentmemory/` |
| `LLM_API_KEY` | LLM API Key | - |
| `EMBEDDER_API_KEY` | Embedder API Key | - |

### Decay 配置

```python
config.decay.half_life_days = 30.0    # 半衰期 30 天
config.decay.forget_threshold = 0.2  # 遗忘阈值
config.decay.archive_threshold = 0.5  # 归档阈值
```

遗忘公式：
```
score = log(1 + access_count)^0.3 × importance^0.4 × recency^0.3
recency = 0.5^(age_days / half_life_days)
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
    type: "usearch"
    path: "./memory_library/.vectors"

decay:
  enabled: true
  forget_threshold: 0.2
  archive_threshold: 0.5
  half_life_days: 30
```

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

## 与业界对比

| | AgentMemory v2.0 | Mem0 | Letta | Zep |
|--|--|--|--|--|
| 依赖数 | 2 | 8+ | 10+ | 5+ |
| 多框架适配 | 5 | 7+ | 4 | 3 |
| 遗忘引擎 | ✅ 半衰期 | ✅ 简单 | ✅ 高级 | ✅ 时序 |
| 类型安全 | Pydantic v2 | Pydantic v2 | 自研 | 自研 |

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
│   │   ├── embedder.py         # Embedder 实现
│   │   ├── llm.py              # LLM 实现
│   │   └── vectorstore.py      # VectorStore 实现
│   ├── search/              # 检索引擎
│   │   ├── search_engine.py    # SearchEngine（双轨融合）
│   │   └── hybrid_retriever.py # HybridRetriever（混合打分）
│   ├── api/
│   │   ├── v2/app.py          # FastAPI v2
│   │   └── app.py             # FastAPI v1
│   ├── web/
│   │   └── app.py             # Flask 管理面板
│   ├── decay_engine.py       # DecayEngine（遗忘引擎）
│   ├── config.py             # 配置管理
│   ├── memory_manager.py     # MemoryHermes 入口
│   ├── multi_agent.py        # 多 Agent 共享
│   └── errors.py             # 错误码体系
├── docs/                    # 架构文档
├── tests/                   # 测试套件
└── README.md
```

---

## 开发

```bash
# 克隆
git clone https://github.com/YintaTriss/AgentMemory.git
cd AgentMemory

# 安装依赖
pip install -e .

# 运行测试
pytest agentmemory/tests/ -v

# 启动 API
python -m agentmemory.api.v2.app

# CLI 存储
agentmemory store "这是一条测试记忆" --category "B.个人" --tags "测试"

# CLI 查询
agentmemory query "测试"

# CLI 列举
agentmemory list --category "B.个人"

# CLI 统计
agentmemory stats

# Web 管理面板
agentmemory web --port 5000
```

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

## 版本历史

| 版本 | 日期 | 变化 |
|------|------|------|
| **v2.0.1** | 2026-06-06 | 🐛 Bug修复：移除递归锁死锁、修复 `total_entries` 计数、修复 `read_range` 时区问题、移除分类深度硬限制（动态深度）<br>⚠️ **重大变更**：彻底抛弃"四层架构"（L1-L4），采用纯双轨检索 + 图书馆分类<br>📋 后续升级：Tag 共现图谱、多 Agent 权限模型 |
| **v2.0.0** | 2026-06-05 | 架构接口完全对齐，62/62 接口通过，API v2 完整实现 |
| **v1.0.0** | 2026-05-20 | 初始版本 |

---

## 许可证

MIT License

---

_AgentMemory v2.0 | 交响乐技能家族 | 2026-06-05_
