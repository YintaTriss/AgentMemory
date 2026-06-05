## AgentMemory v2.0.0

> 架构接口完全对齐 · 62/62 契约通过 · API v2 完整实现

### 核心升级

| 模块 | 状态 | 说明 |
|------|------|------|
| §5.1 DataLake | ✅ | `write/read/delete/list_memories/hydrate/exists/move` |
| §5.2 Library | ✅ | `validate/suggest/add_subcategory/get_descendants/save/load` |
| §5.3 EmbeddingStateMachine | ✅ | `enqueue/worker_loop/list_by_state/stats` |
| §5.4 TagIndex | ✅ | `add/remove/query/save/load` |
| §5.5 TieredLog | ✅ | `append/read_range/read_tail/rotate/get_manifest` |
| §5.7 SearchEngine | ✅ | `search/prefetch` 统一入口 |
| §5.9 DecayEngine | ✅ | 几何乘积公式修正 |
| §5.10 MemoryConfig | ✅ | v2.0.0 schema |
| §5.11 MemoryHermes | ✅ | 全 9 方法实现 |
| §7.2 MemoryEntry | ✅ | 12 字段 schema_version=2 |

**总计：62/62 接口全部通过**

### API v2 路由（完整 RESTful）

```
GET  /health                  健康检查
GET  /v2/memories            列出记忆
POST /v2/memories            创建记忆
GET  /v2/memories/{id}      获取单条
PUT  /v2/memories/{id}       更新
DELETE /v2/memories/{id}     删除
GET  /v2/memories/search     搜索
GET  /v2/stats               统计
POST /v2/decay/run           触发衰减
```

### 关键修复

- **DecayEngine 公式**：线性加权 → 几何乘积 `log(1+access)^0.3 × importance^0.4 × recency^0.3`
- **DecayEngine 修复**：`access_factor` 不再错误 cap 在 1.0
- **Config v2**：`half_life_days` 30.0，`forget_threshold` 0.2，`archive_threshold` 0.5
- **.gitignore**：修复 `data/` 误忽略 `agentmemory/data/`
- **DataLake.list**：修复方法名冲突（`list` → `list_memories`）

### 新增模块

| 模块 | 路径 |
|------|------|
| DataLake | `agentmemory/data/datalake.py` |
| Library | `agentmemory/data/library.py` |
| TagIndex | `agentmemory/data/tag_index.py` |
| EmbeddingStateMachine | `agentmemory/data/embedding_state.py` |
| TieredLog | `agentmemory/data/tiered_log.py` |
| API v2 | `agentmemory/api/v2/app.py` |

### 架构文档

- 顶层设计：[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)（800+ 行）
- 技术实现：[docs/v2-architecture.md](docs/v2-architecture.md)（1500+ 行）
- API 契约：[docs/api-contract.md](docs/api-contract.md)
- Provider 协议：[docs/providers-contract.md](docs/providers-contract.md)

### 与 v1.0 对比

| 指标 | v1.0 | v2.0 |
|------|------|------|
| 接口对齐 | 37% | **100%** |
| 测试通过 | 68 failed / 38 passed | **62/62 通过** |
| API 路由 | 空壳 | 完整 RESTful |
| 多 Agent | 无 | MultiAgentLock + SharedLog |
| 遗忘引擎 | 线性加权 | 几何乘积 |

---
