# AgentMemory 架构文档 v0.3.4

> **版本：** v0.3.4（实现版）
> **日期：** 2026-06-08
> **状态：** 与实现同步
> **架构师：** 楚灵 ⚔️

---

## 一、项目概述

| 项目 | 说明 |
|------|------|
| **项目名** | AgentMemory |
| **目标** | 为 AI Agent 提供持久化记忆存储，支持多 Agent 共享、热插拔、零外部依赖 |
| **定位** | 通用记忆基础设施，可复用于各类 AI Agent 项目 |
| **GitHub** | https://github.com/YintaTriss/AgentMemory |
| **当前状态** | L3 向量搜索 + L4 文件双轨，BM25 关键词兜底，Web API 就绪 |

---

## 二、核心架构：双轨 + 图书馆 + BM25兜底

### 设计哲学

> **记忆如图书馆。书籍本身不会变，但目录系统让查找变得精确。**

```
同一份记忆：
├─ L4 文件轨（.md 本体 + meta.json 元数据）→ 精确查找，人类可读
├─ L3 向量轨（Qdrant Edge）→ 语义搜索
└─ BM25 关键词索引→ 语义失败时的兜底检索
```

### 层级分类规范

最多 4 层，示例：
```
石榴籽/技术/NLLB/训练进度
AI/Agent/记忆系统/VCP
```

---

## 三、存储层级（ L1/L3/L4 三层）

| 层级 | 组件 | 说明 |
|------|------|------|
| **L1** | `L1LCMCompressor` | 上下文压缩，FactType 实体提取，AI 上下文精简 |
| **L3** | `L3QdrantStore` | Qdrant Edge 向量搜索（默认，嵌入式 Rust） |
| **L3** | `BM25Indexer` | **Pure Python BM25**，零额外依赖，关键词兜底 |
| **L4** | `L4FilesStore` | md + meta.json + vec.json 文件存储 |

### L3 向量后端选择

```
create_memory_manager()  # 默认：Qdrant Edge + BM25 兜底
```

### 检索流程

```
search(query)
  └→ L3 向量搜索（Qdrant COSINE）
       ├→ scores > 0 → 返回向量相似度结果
       └→ scores 全为 0 → BM25 关键词重排序 → 返回关键词结果
```

**BM25 兜底逻辑**（`manager.py` `_bm25_rerank`）：
- 当所有向量搜索 score = 0 时触发
- Pure Python BM25Indexer（零额外依赖）
- 同时支持 CLI `--mode bm25` / `--mode hybrid` 显式调用

---

## 四、Embedding 模型

### 当前实际使用

| Embedder | 维度 | 说明 |
|----------|------|------|
| **FastEmbed** `BAAI/bge-small-zh-v1.5` | 512 | Qdrant 向量存储（默认中文模型） |
| **HashEmbedder** | 384 | 零依赖纯 Hash 嵌入（CLI 在无 API key 时降级使用，但不用于主存储） |

### 依赖状态

```bash
# 推荐：安装 FastEmbed 以启用语义向量搜索
pip install agentmemory[qdrant]  # 包含 fastembed

# 零依赖模式：使用 HashEmbedder + BM25 关键词搜索
pip install agentmemory          # 无额外依赖，仅 BM25 兜底
```

### ⚠️ 已知问题：维度不一致

**问题描述：** `HashEmbedder` 产生 384 维向量，`FastEmbed` 产生 768 维向量（`bge-base-en-v1.5`）。如果混用两种 Embedder 会导致 Qdrant collection 维度不匹配。

**当前行为：**
- 安装 `fastembed` → 使用 `BAAI/bge-base-en-v1.5`（768维）→ 向量搜索正常
- 未安装 `fastembed` → 回退到 `HashEmbedder`（384维）→ **Qdrant 存入零向量** → 搜索完全依赖 BM25

**实际使用模型：** `BAAI/bge-small-zh-v1.5`（512维），专为中文语义搜索优化。
**HashEmbedder**（384维）仅在 CLI 无 API key 且 L3 Qdrant 不可用时作为兜底。

---

## 五、关键设计决策

| 决策 | 说明 | 原因 |
|------|------|------|
| Qdrant Edge primary | 默认 L3 后端 | 嵌入式 Rust 向量库，高性能语义搜索 |
| BM25 fallback | 当向量搜索**全部**score=0时触发 | Pure Python，零额外依赖，可靠的关键词检索 |
| FastAPI Web 服务 | `src/agent_memory/web.py` | HTTP API 支持，可独立部署 |
| CLI 三模式搜索 | `--mode vector\|bm25\|hybrid` | 向量 / 关键词 / 纯 BM25 三种检索方式 |
| Hybrid 混合搜索 | CLI `--mode hybrid` | 向量 + BM25 分数归一化后相加（normalized_vec + normalized_bm25） |

---

## 六、核心模块

| 文件 | 类/函数 | 说明 |
|------|---------|------|
| `manager.py` | `MemoryManager` | 统一异步 API，BM25 兜底逻辑 |
| `l3_qdrant.py` | `L3QdrantStore` | Qdrant Edge L3 向量存储 |
| `bm25.py` | `BM25Indexer` | Pure Python BM25 关键词索引（零依赖） |
| `l4_files.py` | `L4FilesStore` | md + meta.json + vec.json 文件存储 |
| `library.py` | `LibraryClassifier` | 4 层分类自动推断 |
| `embedder.py` | `Embedder`, `HashEmbedder`, `DashScopeEmbedder` | Embedder 抽象 + 零依赖 Hash 实现 |
| `l1_lcm.py` | `L1LCMCompressor` | 上下文压缩，FactType 实体提取 |
| `sync.py` | `SyncManager` | L4 ↔ L3 双轨同步 |
| `web.py` | FastAPI app | HTTP API 服务 |
| `cli.py` | CLI | 命令行工具，支持 vector/bm25/hybrid 搜索 |
| `integrity.py` | `IntegrityVerifier` | HMAC 签名验证 |

---

## 七、Web 服务（FastAPI）

启动方式：
```bash
cd AgentMemory
python -m src.agent_memory.web
# 默认：http://localhost:8080
```

主要端点：
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/stats` | 记忆统计 |
| POST | `/search` | 搜索（?q=&top_k=&mode=） |
| POST | `/add` | 添加记忆 |
| GET | `/list` | 列出记忆（?category=&limit=） |
| GET | `/get/{id}` | 获取单条记忆 |
| DELETE | `/delete/{id}` | 删除记忆 |

---

## 八、参考系统对比（更新）

| 系统 | 数据形态 | 索引方式 | 多 Agent | NAS 支持 | 零依赖 | BM25 |
|------|---------|---------|---------|---------|-------|------|
| Hermes | 文件 | 无向量 | 共享工作空间 | 原生 | ✅ | ❌ |
| VCP | 文件 + 向量双轨 | Tag + 向量 | 共用文件夹 | SQLite 单文件 | ✅ | ❌ |
| Mem0 | 向量 + 图关系 | 向量 + 关系图 | 多租户 | 需数据库 | ❌ | ❌ |
| **AgentMemory** | md + Qdrant + BM25 | 双轨 + BM25兜底 | 共用文件夹 | 原生 | ✅ | ✅ |

---

## 九、依赖项

| 依赖 | 用途 | 性质 |
|------|------|------|
| Python | 运行时 | 必需 |
| `qdrant-client` | Qdrant Edge 客户端 | L3 向量库（推荐） |
| `fastembed` | 语义向量生成 | **可选**，安装后启用向量搜索 |
| `portalocker` | 文件锁并发控制 | Windows 并发必需 |
| `fastapi`, `uvicorn` | Web 服务 | 可选，Web 服务必需 |
| **BM25Indexer** | 关键词检索 | **内置**，Pure Python，零依赖 |

**零依赖安装：**
```bash
pip install agentmemory
# 仅需 Python，无需安装任何向量库或模型
# 搜索方式：HashEmbedder（384维）+ BM25 关键词兜底
```

---

## 十、.gitignore 说明

以下为运行时生成文件，**不应提交**：
```
memory/.lock_*           # 文件锁
data/qdrant/             # Qdrant 向量数据库文件
data/lancedb/            # LanceDB 数据目录（已删除，不再使用）
```

---

## 十一、已知实现细节（与早期文档的差异）

以下为已废弃/更改的设计，对应旧版文档：

| 旧版描述 | 当前实际 | 说明日期 |
|---------|---------|---------|
| `bge-base-en-v1.5` (768维) | `BAAI/bge-small-zh-v1.5` (512维) | 2026-06-08 |
| `bge-large-zh` (1024维) | 未使用 | 2026-06-08 |
| l3_lancedb.py | 已删除 | 2026-06-07 |
| BM25 触发条件 "scores ≈ 0" | scores **全为 0** | 2026-06-08 |

---

_最后更新：2026-06-08 v0.3.4_
_架构师：楚灵 ⚔️_
