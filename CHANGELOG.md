# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-06-07

### Major Changes

#### Architecture Simplification

**BREAKING: Removed Layer 2 (Graph-DB)**

After review, the L2 Graph-DB layer was deemed over-engineering and removed. The v0.3 architecture is now:

```
L4 Files (File System) → L3 Qdrant Edge (Vector) → L1 LCM (Compression)
```

Previous v0.1/v0.2 architecture had 4 layers:
```
L1 LCM → L2 Graph-DB → L3 Vector → L4 Files
```

### Features

- **3-File Group Storage**: Each memory now stored as:
  - `<id>.md` - Raw content
  - `<id>.vec.json` - Vector data
  - `<id>.meta.json` - Metadata

- **Dual-Track Retrieval**:
  - Track 1: Library Classification (category/tags)
  - Track 2: Embedding Vector (semantic search)

- **Library Classification**:
  - Hierarchical categories (max 4 levels)
  - Examples: `Project/Shiliuzi/Corpus/NLLB-Training`

- **Zero Dependency Mode**:
  - Hash-based embedder (no API key needed)
  - JSON-based vector store fallback

- **Optional Real Embedding**:
  - OpenAI embeddings
  - DashScope text2vec
  - Local bge-large-zh model

### CLI Commands

```bash
add          Add new memory
search       Search memories
list         List all memories
show         Show specific memory
delete       Delete memory
category     List categories
stats        Show statistics
```

## Migration from v0.2 → v0.3

### Removed APIs
- `L2_graph_store.GraphStore` → removed (use `L1LCMCompressor.extract_facts` instead)
- `DecayEngine` → removed (use L4 metadata `importance` field for prioritization)
- v0.2 config sections `l2` and `decay` → no longer needed, delete from config

### Config Migration
```python
# v0.2 config (REMOVE these sections in v0.3)
config = {
    "l2": {"enabled": True},
    "decay": {"policy": "LRU"},
    # keep everything else
}
# v0.3: delete "l2" and "decay" keys, rest is unchanged
```

### Import Migration
```python
# v0.2
from agent_memory import MemoryManager  # same in v0.3
from agent_memory.graph_store import GraphStore  # REMOVED
from agent_memory.decay import DecayEngine  # REMOVED

# v0.3
from agent_memory import MemoryManager
# L2 functionality replaced by L1LCMCompressor
```

---

### Security

> 详细说明见 `docs/SECURITY.md` 与 `docs/ARCHITECTURE-IMPL.md` 第 17 章。

| P0 编号 | 原风险编号 | 问题 | 修复 | 状态 |
|---------|-----------|------|------|------|
| P0-1 | H-05 | 无 API Key 时隐式降级为假随机向量，用户以为向量可用 | `get_embedder("dashscope")` 缺 Key 立即抛 `RuntimeError`；`get_embedder("auto")` 显式声明降级并打 WARN | 已实现 |
| P0-2 | H-04 | 对话原文 → 持久事实 → 后续 prompt 的存储型 Prompt Injection | `sync.sync_one()` 写入 L3 前调 `check_injection()`；命中后 `trust_score <= 0.3` + `meta.flagged_patterns` | 已实现 |
| P0-3 | H-01 / H-02 | 写入无文件锁 + 无原子性；并发写损坏数据 | `L4FilesStore.save/delete` 加 `portalocker.FileLock`；`tempfile + os.replace + fsync` 三步原子写；统一在 `MemoryManager.add()` 改为 fire-and-forget `ThreadPoolExecutor` (4 workers) | 已实现 |
| P0-4 | H-03 | 热插拔文件夹无签名/校验/Schema | `utils/integrity.py::sign_file / verify_folder` HMAC-SHA256 签名 `.meta.json`；CLI `agent-memory sign / verify` | 已实现 |

**新增模块**：

- `src/agent_memory/utils/injection.py` — `check_injection(text) -> (flagged, score, matched)`
- `src/agent_memory/utils/integrity.py` — `sign_file(path)` / `verify_folder(root) -> (ok, bad)`
- `src/agent_memory/l4_files.py` — 文件锁 + 原子写
- `src/agent_memory/embedder.py` — `get_embedder()` 工厂函数

**v0.4 P1 待办**：M-01 base_url 校验 / M-02 config 白名单 / M-03 pydantic schema / M-06 .trash 30 天宽限（详见 `docs/SECURITY.md` §四）。

### Performance

| Operation | Time (ms) |
|-----------|-----------|
| add | ~2 |
| search | ~0.3 |
| list | ~0.5 |

## [0.2.0] - 2026-05-29

### Architecture

- VCP 3-phase architecture (相变)
- Layered storage with phase transitions

### Status

Superseded by v0.3.

## [0.1.0] - 2026-05-15

### Initial Design

- 4-layer architecture: L1 LCM / L2 Graph / L3 Vector / L4 Files
- Hermes + Mem0 hybrid approach
- MemoryHermes main class

### Status

Superseded by v0.3.
