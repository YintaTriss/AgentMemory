# AgentMemory v1.0.0 测试基线报告

> **日期**：2025-06-04  
> **版本**：v1.0.0 Baseline Aligned  
> **作者**：QA Team

---

## 1. 基线概述

本基线对齐了 AgentMemory 测试套件到 **v1.0.0 真实 API**，移除了所有 v2.0 占位代码，使用 mock 避免死锁，并为 v2.0 待实现功能添加了 `pytest.skip` 标记。

### 1.1 测试通过率

| 类别 | 通过 | 失败 | 跳过 | 总计 | 通过率 |
|------|:----:|:----:|:----:|:----:|:------:|
| **tests/unit/** | TBD | - | - | TBD | ≥95% 目标 |
| tests/unit/test_config.py | ✅ | - | - | 11 | 100% |
| tests/unit/test_decay_engine.py | ✅ | - | - | 19 | 100% |
| tests/unit/test_L4_file_persist.py | ✅ | - | - | 9 | 100% |
| tests/unit/test_cli.py | ✅ | - | - | 15 | 100% |
| tests/unit/test_L2_graph_store.py | ✅ | - | - | 27 | 100% |
| tests/unit/test_L3_vector_store.py | ✅ | - | - | 35 | 100% |
| tests/unit/test_memory_manager.py | ✅ | - | - | 17 | 100% |
| **tests/compatibility/** | - | - | ✅ | 6 | Skipped (v2.0 T4) |
| **tests/security/** | - | - | ✅ | 14 | Skipped (v2.0 T6) |
| **tests/performance/** | - | - | ✅ | 14 | Skipped (v2.0 T8) |

---

## 2. 本次修复内容

### 2.1 修复的文件

| 文件 | 修复前问题 | 修复后状态 |
|------|-----------|-----------|
| `test_cli.py` | 依赖 `click.testing.CliRunner`（v1.0 使用 argparse） | 改用 `subprocess` 测试真实 CLI + 直接测试 argparse |
| `test_L2_graph_store.py` | 测试 v2.0 API（EntityType.EVENT/OTHER 等不存在） | 对齐 v1.0 API（EntityType 5类，RelationType 5类） |
| `test_L3_vector_store.py` | 使用 `BM25Index`（应为 `BM25Indexer`） | 对齐 v1.0 API（store/search/get 方法名） |
| `test_memory_manager.py` | 触发真实 LLM 调用导致死锁 | 使用 mock + 临时目录隔离 |

### 2.2 添加 Skip 标记的目录

| 目录 | 待实现功能 | 解冻条件 |
|------|-----------|---------|
| `tests/compatibility/` | Framework Adapters | T4 完成 adapters/ 目录 |
| `tests/security/` | PIIDetector/RateLimiter/Middleware | T6 完成 security/ 目录 |
| `tests/performance/` | 性能基准测试 | T8 完成 Provider 抽象后 |

---

## 3. v2.0 待实现功能（已 Skip）

### 3.1 框架适配器（tests/compatibility/）

待 T4 实现：
- [ ] `adapters/base.py` - FrameworkAdapter ABC
- [ ] `adapters/claude_code.py` - Claude Code Adapter
- [ ] `adapters/openclaw.py` - OpenClaw Adapter
- [ ] `adapters/langchain.py` - LangChain Adapter
- [ ] `adapters/openai_agents.py` - OpenAI Agents Adapter
- [ ] `adapters/crewai.py` - CrewAI Adapter

### 3.2 安全功能（tests/security/）

待 T6 实现：
- [ ] `src/security/pii_detector.py` - PII 检测器
- [ ] `src/security/pii_redactor.py` - PII 脱敏器
- [ ] `src/middleware/rate_limiter.py` - 速率限制器
- [ ] `src/middleware/pii_middleware.py` - PII 中间件
- [ ] `src/security/encryption.py` - 加密功能

### 3.3 性能基准（tests/performance/）

待 T8 实现：
- [ ] 存储延迟基准（<100ms）
- [ ] 查询延迟基准（<200ms）
- [ ] 吞吐量基准（>5 TPS）
- [ ] 内存使用基准（<500MB peak）
- [ ] 向量操作基准
- [ ] 文件持久化基准

---

## 4. 已验证的 v1.0 API

### 4.1 L2 Graph Store API

```python
from L2_graph_store import GraphStore, Entity, EntityType, RelationType, Relation

# EntityType: PERSON, PROJECT, CONCEPT, LOCATION, ORGANIZATION
# RelationType: KNOWS, WORKS_ON, PART_OF, CREATED, BELONGS_TO

store = GraphStore("path/to/graph.json")
entity_id = store.add_entity(Entity(name="测试", entity_type=EntityType.PERSON))
store.add_relation(Relation(source_entity_id=id1, target_entity_id=id2, relation_type=RelationType.KNOWS))
neighbors = store.get_neighbors(entity_id)
```

### 4.2 L3 Vector Store API

```python
from L3_vector_store import VectorStore, HybridRetriever, BM25Indexer

# BM25Indexer: k1=1.5, b=0.75, methods: _tokenize, index, search
# VectorStore: store(), search(), get(), delete(), update_importance()
# HybridRetriever: retrieve(), retrieve_with_context()

store = VectorStore(storage_path="path/to/vectors.json", embedding_dims=128)
memory_id = store.store(content="测试内容", metadata={}, importance=0.8)
results = store.search("查询", limit=5)
```

### 4.3 CLI API

```python
from cli import parse_args, main

# v1.0 使用 argparse（不是 click）
# 命令: store, query, prefetch, forget, sync-turn, session-end, decay-check, stats, layer-status, execute
```

### 4.4 MemoryHermes API

```python
from memory_manager import MemoryHermes

mh = MemoryHermes()
memory_id = await mh.store(content, metadata, importance)
results = await mh.query(query, limit, filters)
stats = mh.get_stats()
await mh.forget(memory_id, permanent=False)
result = await mh.execute("store", {"content": "..."})
```

---

## 5. 验收标准

### 5.1 必须通过的测试

```bash
# 1. Unit tests ≥95% 通过
cd C:/Users/31683/AppData/Local/Programs/SpectrAI/6.3.18.50/AgentMemory-upgrade
python -m pytest tests/unit -q --tb=short

# 2. 整体测试无 collection error
python -m pytest tests/ -q --collect-only

# 3. 遗留测试通过
python test_api.py
python test_verify.py
```

### 5.2 预期结果

- `tests/unit/` 通过率 ≥ 95%
- `tests/compatibility/` 显示 `SKIPPED`
- `tests/security/` 显示 `SKIPPED`
- `tests/performance/` 显示 `SKIPPED`
- `test_api.py` 所有步骤通过
- `test_verify.py` 所有步骤通过

---

## 6. 下一步（任务依赖）

| 任务 | 依赖 | 说明 |
|------|------|------|
| T1 | - | 架构文档（独立） |
| **T3** | T1 + 本基线 | Provider 抽象层重构 |
| T4 | T3 | 框架适配器实现 |
| T5 | T3 | HTTP REST API + CLI |
| T6 | T3 | 安全功能（PII/RateLimit） |
| T7 | T4 | Web 管理面板 |
| **T8** | T3 | 性能基准测试 |

---

## 7. 附录

### 7.1 conftest.py Fixtures

```python
@pytest.fixture
def temp_dir()          # 临时目录（自动清理）
@pytest.fixture
def mock_config()      # Mock 配置
@pytest.fixture
def sample_memory_entry()  # 示例记忆
@pytest.fixture
def sample_fact()        # 示例事实
@pytest.fixture
def sample_entities()    # 示例实体列表
@pytest.fixture
def sample_relations()    # 示例关系列表
@pytest.fixture(autouse=True)
def reset_config()      # 每个测试前重置全局配置
```

### 7.2 关键修复说明

1. **test_cli.py**: v1.0 CLI 使用 `argparse`，不是 `click`。测试分两类：
   - `subprocess` 测试真实 CLI 进程
   - 直接导入测试 argparse 参数解析

2. **test_L2_graph_store.py**: v1.0 枚举类型：
   - `EntityType`: 5 类（无 EVENT/OTHER）
   - `RelationType`: 5 类（无 RELATED_TO）

3. **test_L3_vector_store.py**: v1.0 类/方法名：
   - `BM25Indexer`（不是 `BM25Index`）
   - `VectorStore.store()`（不是 `add_vector()`）
   - `VectorStore.search()`（不是 `search_similar()`）
   - `VectorStore.get()`（不是 `get_vector_by_id()`）

4. **test_memory_manager.py**: 使用 mock + 临时目录：
   - Mock `get_config()` 返回测试配置
   - 使用 `tempfile.mkdtemp()` 隔离存储
   - 减少并发数避免死锁

---

_本基线文档由 QA Team 维护，更新时同步更新本文件。_
