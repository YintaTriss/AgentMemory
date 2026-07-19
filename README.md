# AgentMemory — 四层闭环记忆系统 + 梦境子系统

> 版本: v2.1.0 (2026-07-15 代码审计 + FactExtractor 默认集成 + 梦境子系统)
> 基于 VCP 记忆系统架构 + 自创梦境子系统(对标 VCP TagMemo v3.7 源码级)
> License: MIT | Author: 楚零

## 架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AgentMemory v2.1.0                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                  搜索管道 (实时)                                              │
│  Fuzzy → BM25 → Vector → Reranker → 加权融合                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                  梦境子系统 (后台)                                            │
│  Light(6h) → Deep(3am) → REM(周日) → LLM叙事                                │
│  信号分解 → 图传播 → 产物生成 → 记忆固化                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                  存储层                                                       │
│  L4: 纯文件 (.md + .meta.json + .vec.json)                                  │
│  L3: Qdrant Edge 向量库                                                    │
│  SQLite WAL: 标签/共现/元数据/KV                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                  外部集成 (LangChain / LlamaIndex / OpenAI Agents / Claude)   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 模块一览

| 模块 | 文件 | 功能 |
|------|------|------|
| **核心** | `manager.py` | `MemoryManager` / `TeamMemoryManager` 统一 API |
| | `l1_lcm.py` | L1 LCM 压缩器 (默认挂载 FactExtractor,2026-07-15+) |
| | `fact_extractor.py` | LLM 驱动的事实提取(双模式:LLM + 规则) |
| **搜索** | `search_pipeline.py` | Fuzzy → BM25 → Vector → Reranker 四层融合 |
| | `fuzzy_search.py` | 错别字容错搜索 (rapidfuzz) |
| | `bm25.py` | 关键词检索 (jieba 中文分词) |
| | `reranker.py` | 语义重排 |
| **梦境** | `dream_engine.py` | 梦境总控编排 (Phase 1-4) |
| | `dream_signal.py` | EPA 投影 + 残差金字塔分解 |
| | `dream_graph.py` | Spike Routing 图传播 + 涌现节点 |
| | `dream_consolidate.py` | 产物生成 + 记忆固化 |
| | `dream_narrative.py` | 梦境叙事 (LLM) |
| **存储** | `sqlite_store.py` | 标签/共现/元数据 WAL |
| | `l3_qdrant.py` | 向量检索引擎 |
| | `l4_files.py` | 文件级存储 |
| **工具** | `config_watcher.py` | 热加载配置 |
| | `watcher.py` | 文件监听 |
| | `write_queue.py` | 三级优先级写入队列 |
| | `compactor.py` | 记忆老化压缩 |
| | `agent_tool.py` | Agent 可调用的记忆接口 |
| | `health_monitor.py` | 健康监控 |

## 快速开始

### 安装

```bash
pip install agentmemory
```

### CLI

```bash
agentmemory add "内容"              # 添加记忆
agentmemory search "查询"            # 搜索记忆
agentmemory list                    # 列出记忆
agentmemory show <id>               # 查看单条记忆
agentmemory delete <id>             # 删除记忆
agentmemory stats                   # 统计信息
agentmemory doctor                  # 环境诊断(依赖/路径/环境变量)
agentmemory dream [--dry-run]       # 执行梦境循环
agentmemory bg                      # 启动后台记忆捕获器
agentmemory serve                   # 启动 Web API 服务器
```

### Python API

```python
import asyncio
from agent_memory import MemoryManager, FactExtractor

async def main():
    # 构造 MemoryManager (默认挂载 FactExtractor)
    mm = MemoryManager(namespace="my-app")

    # 写入记忆
    mid = await mm.add(
        "我决定改用 NewAPI 聚合 MiniMax + DeepSeek",
        importance=0.9,
        tags=["decision", "infra"],
        category="project",
    )

    # 搜索
    results = await mm.search("你选了什么模型?", limit=5)

    # 上下文压缩 (同步路径)
    ctx = await mm.compress_for_context([mid], query="模型")

    # 上下文压缩 + LLM 事实抽取 (异步增强路径,2026-07-15+)
    ctx_enhanced = await mm.compress_with_facts([mid], query="模型")

asyncio.run(main())
```

## 梦境子系统

```bash
# 单次梦境 (模拟)
agentmemory dream --dry-run

# 完整梦境循环 (写入)
agentmemory dream --namespace default

# 梦境输出为 JSON
agentmemory dream --dry-run --json
```

### 梦境阶段

| 阶段 | 模块 | 算法 |
|------|------|------|
| 1. 信号分解 | `dream_signal.py` | K-Means + 加权 SVD → EPA 投影 |
| | | Gram-Schmidt → 残差金字塔 |
| 2. 图传播 | `dream_graph.py` | Spike Routing 动量衰减 |
| | | 虫洞跨簇路由 (coocWeight × residualNovelty) |
| 3. 产物生成 | `dream_consolidate.py` | 隐式标签生成 |
| | | 关联记忆创生 |
| 4. 固化 | `dream_consolidate.py` | 三级置信度处理 (写入/暂存/丢弃) |

## 配置

`rag_params.json` — 搜索权重 / Tag 增强 / 时间衰减 / 去重阈值,热加载生效。

```json
{
  "search": {
    "fuzzy_weight": 0.2,
    "bm25_weight": 0.3,
    "vector_weight": 0.4,
    "rerank_weight": 0.1
  },
  "tag_boost": 1.5,
  "time_decay": 0.95,
  "dedup_threshold": 0.92
}
```

## 测试

```bash
# 单元测试 (CI 路径,无需真实服务)
pytest tests/ -q --ignore=tests/integration
# 542 passed, 72 skipped (2026-07-15)

# 完整测试 (含真实服务集成)
pytest tests/ -q
# 542 passed, 72 skipped (包含 4 个 integration 真实服务测试)
```

## 对标 VCP

| VCP 特性 | AgentMemory | 状态 |
|----------|-------------|------|
| Fuse.js 模糊搜索 | `fuzzy_search.py` | ✅ |
| BM25 关键词 | `bm25.py` (jieba) | ✅ |
| Reranker 重排 | `reranker.py` | ✅ |
| chokidar 文件监听 | `watcher.py` | ✅ |
| chokidar 热加载 | `config_watcher.py` | ✅ |
| SQLite WAL | `sqlite_store.py` | ✅ |
| Tag 系统 + 共现矩阵 | `sqlite_store.py` | ✅ |
| 文件索引管道 | `watcher.py` + `sync.py` | ✅ |
| EPA 投影 (K-Means + SVD) | `dream_signal.py` | ✅ |
| 残差金字塔 (Gram-Schmidt) | `dream_signal.py` | ✅ |
| Spike Routing (图传播) | `dream_graph.py` | ✅ |
| 记忆固化 | `dream_consolidate.py` | ✅ |
| FactExtractor (LLM 事实抽取) | `fact_extractor.py` | ✅ |
| Rust VexusIndex 引擎 | Python + numpy | ⚠️ 慢但够用 |
| Geodesic Rerank | — | ❌ 已知差距 (不抄) |
| ResultDeduplicator (SVD 去重) | — | ❌ 已知差距 (不抄) |
| ContextFoldingV2 (实时去重) | — | ❌ 已知差距 (不抄) |

### 为什么这 3 个不抄?

| VCP 特性 | 我们的理由 |
|----------|------------|
| GeodesicRerank | 依赖 Rust VexusIndex 距离场,梦境场景几何意义不同 |
| ResultDeduplicator | SVD 去重用于搜索结果,梦境产物已过量置信度过滤 |
| ContextFoldingV2 | 实时搜索去重,不适用于梦境后台 |

详见 `CHANGELOG-2026-07-15.md` 的"自主判断"章节。

## 抽象目标

**成为市面上 AI 界顶尖记忆系统**。对标:Mem0 / Zep / Letta / LangChain / VCP。

- 鼓励抄袭好用的特性
- 主人授权:文件/配置/env/token 都能改
- 测试基线(2026-07-15 起):**542 passed / 72 skipped / 175 warnings in ~130s**

## 升级方向 (Roadmap)

详见 `CHANGELOG-2026-07-15.md` 的"未做项" + 后续市场对比分析。

## 引用

如使用本项目,请引用:

```bibtex
@software{agentmemory_2026,
  title = {AgentMemory: A Four-Layer Closed-Loop Memory System with Dreaming Subsystem},
  author = {Chu Ling},
  year = {2026},
  url = {https://github.com/YintaTriss/AgentMemory}
}
```

---

_编制: 楚零 | 最后更新 2026-07-15_