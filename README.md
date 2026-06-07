<p align="center">
  <a href="README.md">English</a> |
  <a href="README_CN.md">简体中文</a>
</p>

# AgentMemory v0.3

> **Dual-Track + Library Memory System** — Persistent, portable, hot-swappable memory infrastructure for AI Agents

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)

---

## Design Philosophy: Memory as a Library

> **The book itself never changes, but the catalog system makes finding precise.**

Traditional memory systems face a core contradiction: **semantic search (fuzzy matching) and exact classification (domain filtering) — you can only pick one**.

AgentMemory's answer: **Both tracks coexist. Never compromise.**

The same memory exists in two tracks simultaneously:

```
Same memory:
├─ Library Classification Track (.md content + .meta.json metadata) → exact lookup, management boundaries
└─ Embedding Vector Track (.vec.json) → semantic search, fuzzy matching
```

**Granularity guarantee**: minimum 3-layer classification (library / shelf / book), ensuring every memory can be precisely categorized. Maximum depth is unlimited — extend as needed.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                     Host App (Agent / CLI / Web API)        │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│  MemoryManager (Unified Async API)                           │
│  add() / get() / delete() / search() / list() / compress() │
└────────────────────────────┬─────────────────────────────────┘
                             │
          ┌──────────────────┴──────────────────┐
          ▼                                      ▼
┌─────────────────────┐              ┌─────────────────────────┐
│   L4FilesStore      │              │   L3LanceDBStore        │
│   (File Persistence)│              │   (Vector Search)       │
│                     │              │                         │
│  memory/<id>.md     │◄──── sync ──►│  LanceDB Table         │
│  memory/<id>.meta   │              │  (Semantic Similarity)  │
│  memory/<id>.vec.json              │                         │
└─────────────────────┘              └─────────────────────────┘
          │                                      │
          ▼ (on read)                            │
┌─────────────────────┐              ┌─────────────────────────┐
│   L1LCMCompressor   │              │   BM25 Hybrid Search    │
│   (Context Compress)│              │   (Pure Python, Zero Deps) │
│                     │              │                         │
│  Entity → Summary   │              │  k1=1.2, b=0.75         │
│  → AI Context       │              │  α=0.7 (vector/BM25)    │
└─────────────────────┘              └─────────────────────────┘
```

### Three-Layer Responsibilities

| Layer | Component | Responsibility |
|-------|-----------|----------------|
| **L4** | `L4FilesStore` | `.md` content + `.meta.json` metadata + `.vec.json` vectors, filesystem persistence |
| **L3** | `L3LanceDBStore` | LanceDB vector search (auto-fallback to pure JSON + numpy when unavailable), BM25 hybrid search |
| **L1** | `L1LCMCompressor` | Memory compression to summary + entity list, used when injecting AI prompts, query-relevance enhancement |
| **L3** | `SyncManager` | L4 ↔ L3 dual-track sync, auto-sync keyword detection, portalocker file locking |
| **L3** | `LibraryClassifier` | 5 top-level categories auto-classification, normalized keyword scoring, cached tokenization |
| **L3** | `IntegrityVerifier` | HMAC-SHA256 file integrity signing, tamper detection |

### Dual-Track Retrieval

| Track | Method | Best For |
|-------|--------|----------|
| **Track 1** | Library Classification (category_path / tags) | Exact lookup, domain filtering |
| **Track 2** | Embedding Vectors (semantic similarity) | Fuzzy search, semantic associations |

### Library Classification Rules

Minimum 3 layers (library / shelf / book — ensuring granularity), maximum unlimited, dynamic depth:

```
Project/Shiliuzi/Corpus/NLLB-Training                 ✅ Minimum 3 layers
Project/Shiliuzi/Corpus/NLLB-Training/2026-06           ✅ Can extend indefinitely (no upper limit)
Learning/AI/Transformer                                ✅ 3 layers
AI/Agent/Memory-System/VCP                      ✅ 4 layers
```

---

## Core Components

| Component | File | Description |
|-----------|------|-------------|
| `MemoryManager` | `manager.py` | Unified async API: add/get/delete/search/list/compress |
| `L4FilesStore` | `l4_files.py` | md + meta.json + vec.json triple-file storage, portalocker file locking |
| `L3LanceDBStore` | `l3_lancedb.py` | LanceDB vector search + JSON Fallback + BM25 hybrid search |
| `L1LCMCompressor` | `l1_lcm.py` | Context compression, FactType entity extraction, query-relevance enhancement |
| `SyncManager` | `sync.py` | L4 ↔ L3 dual-track sync, auto_sync keyword detection |
| `LibraryClassifier` | `library.py` | 5-category keyword classification, hierarchical path validation, cached tokenization |
| `Embedder` | `embedder.py` | HashEmbedder (zero-dep) / OpenAI-Compatible API embedder |
| `IntegrityVerifier` | `integrity.py` | HMAC-SHA256 signature verification |

---

## Data Structure

Each memory = 3 files in the same directory:

```
memory/
├── abc123.md           # Human-readable content
├── abc123.meta.json   # Metadata
└── abc123.vec.json    # Vector data (one per memory, co-located with .md)
```

### meta.json Format

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

## Implementation Details: Elegant Little Tricks

### Atomic Writes: tempfile + os.replace (Windows-Compatible)

L4 file writes use a two-step atomic operation:

```python
# 1. Write to temp file
tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tmp", dir=base_dir)
tmp.write(content); tmp.close()
# 2. os.replace atomic replace (guaranteed atomic on Windows too)
os.replace(tmp.name, target_path)
```

`os.rename` can't work cross-drive on Windows. `os.replace` can. This is a blind spot for many cross-platform Python projects.

### portalocker: Cross-Platform File Locking

```python
with _portalocker_lock(lock_path):
    # Write operations auto-lock
    ...
```

`portalocker` preferred, with Windows `msvcrt` and Unix `fcntl` fallbacks. Reads use shared locks; writes use exclusive locks. The `contextmanager` pattern guarantees lock release even on exceptions.

### `_embed_fn` Pattern: Unified Sync/Async Interface

DashScopeEmbedder's `embed()` is `async def`; HashEmbedder's is `def`. Callers use a unified interface:

```python
# In SyncManager.__init__:
if hasattr(embedder, 'embed_sync'):
    self._embed_fn = embedder.embed_sync
else:
    self._embed_fn = embedder.embed
```

Runtime detection — no type checking needed. The Embedder base class provides the `embed_sync` property; async implementations wrap in a worker thread.

### Cached Tokenization (LibraryClassifier)

Re-tokenizing on every keyword match is wasteful. `_tokenize()` uses `@functools.lru_cache(maxsize=512)`:

```python
@functools.lru_cache(maxsize=512)
def _tokenize(self, text: str) -> tuple[str, ...]:
    ...
    return tuple(tokens)  # tuple is hashable, suitable as lru_cache key
```

Returns `tuple` not `list` — tuple is hashable and cacheable.

### Score Normalization: sqrt(keyword_count) Prevents Large Categories Bullying Small Ones

The "Project" category has 20+ keywords; "Preferences" has only 8. Raw summation would let the large category always win:

```python
scores[category] = cat_raw / (len(keywords) ** 0.5)  # sqrt normalization
```

Using `sqrt` instead of dividing by `len(keywords)` directly: large lists help, but don't dominate.

### Unicode Normalization + Dual-Track Detection (injection.py)

Detecting obfuscation attacks requires two steps:

```python
texts_to_check = [text, _normalize_text(text)]  # Original + normalized
```

Normalization steps include: zero-width character handling, HTML entity decoding, fullwidth→halfwidth conversion, Unicode escape sequence decoding, backslash word还原, BIDI control char removal. Obfuscation attacks (`rm\u200b-rf`, `rm&#x72;f`) are exposed after normalization.

### Configurable BM25 Parameters

BM25's `k1` (term frequency saturation) and `b` (document length normalization) are tunable:

```python
# k1=1.2, b=0.75 are Lucene defaults
l3_store.search_bm25(query, top_k=5, k1=1.2, b=0.75)
```

### Adjustable Hybrid Search α Weighting

Vector similarity and BM25 hybrid weighting: α defaults to 0.7 (70% vector, 30% BM25):

```python
alpha = 0.7
final_score = alpha * vec_score + (1 - alpha) * bm25_score
```

### 5-Minute Stats Cache

`MemoryManager.stats()` has a local cache to avoid reading the filesystem every call:

```python
age = (datetime.now() - self._stats_timestamp).total_seconds()
if age < 300:  # Within 5 min, return cached
    return self._stats_cache
```

### `access_count` Persistence (Not an In-Memory Variable)

Many memory systems store access counts in memory — lost on restart. AgentMemory writes `access_count` back to `.meta.json`, incrementing and persisting on every `load_existing()` call.

### Query Parameter Enhances L1 Compression Relevance Ordering

`compress_for_context(memory_ids, query="...")` accepts a query parameter; memories sharing keywords with the query are ranked higher within the same importance tier:

```python
def _relevance_score(mem):
    if not query_toks: return 0
    return sum(1 for tok in query_toks if tok in mem.get("content","").lower())
```

---

## Security (P0 Level)

| Protection | Location | Description |
|------------|----------|-------------|
| **Injection Detection** | `utils/injection.py` | Unicode normalization + dual-track detection (original/normalized both checked), 50+ attack patterns including JNDI/SSTI/Shellshock/Prompt Injection |
| **trust_score** | `sync.py` | < 0.2 rejects L3 write, ≤ 0.35 marks flagged + warns |
| **HMAC Verification** | `integrity.py` | HMAC-SHA256 signing, writes `signed_at` to `.meta.json` |
| **API Key Validation** | `embedder.py` | `DashScopeEmbedder.__init__` validates immediately, throws RuntimeError if missing |
| **LanceDB Injection Protection** | `web.py` / `cli.py` | Single quotes in category_path escaped as `''` (SQL standard) |
| **Atomic Writes** | `l4_files.py` | tempfile + os.replace — no stray files even on crash |
| **File Locking** | `l4_files.py` | portalocker exclusive lock, write operations are mutually exclusive |

---

## Concurrency Safety

Write safety guaranteed by `portalocker`: Windows falls back to `msvcrt`, Unix to `fcntl`:

```python
# L4FilesStore write: auto-exclusive lock
with _portalocker_lock(lock_path):
    ...

# Read: auto-shared lock
with _file_lock(lock_path, exclusive=False):
    ...
```

---

## Installation

```bash
cd AgentMemory
pip install -e .
```

### Dependencies

**Runtime dependencies (only 3, no external services needed):**

```
httpx>=0.25.0    # Async HTTP for API calls
aiofiles>=23.0.0 # Async file I/O
pydantic>=2.5    # Data validation (required at runtime)
```

**Optional dependencies:**

```bash
pip install agentmemory[web]     # Web API support (FastAPI + uvicorn)
pip install agentmemory[lancedb] # LanceDB vector database (high-performance scenarios)
pip install agentmemory[dev]     # Development dependencies (pytest etc.)
```

> When LanceDB is unavailable (not installed), the system auto-falls back to pure JSON + numpy — zero extra dependencies needed to run.

### Embedder Selection

```python
from agent_memory import MemoryManager, get_embedder

# Default (auto mode): no API Key → HashEmbedder (zero-dep, works offline)
#                      has EMBEDDING_API_KEY → OpenAI-Compatible embedding (any compatible provider)
mm = MemoryManager()

# Explicit (throws RuntimeError immediately if no API Key — no silent degradation)
mm = MemoryManager(embedder=get_embedder(backend="openai-compat"))

# Equivalent to default auto mode
mm = MemoryManager(embedder=get_embedder())
```

> **No model lock-in**: Uses OpenAI-Compatible API format internally; auto-detects any provider supporting `/v1/embeddings` (DashScope / Minimax / OpenAI / local Embedding Server, etc.).

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_MEMORY_DIR` | `memory` | Memory storage directory |
| `AGENT_MEMORY_DATA_DIR` | `data` | Vector data directory (LanceDB table / JSON fallback) |
| `EMBEDDING_API_KEY` | - | OpenAI-Compatible API (recommended; any compatible provider works) |
| `DASHSCOPE_API_KEY` | - | Backwards compatible, choose one with `EMBEDDING_API_KEY` |
| `OPENAI_API_KEY` | - | Backwards compatible |

---

## Quick Start

### Python API

```python
import asyncio
from agent_memory import MemoryManager

async def main():
    mm = MemoryManager()

    # Add a memory
    mem_id = await mm.add(
        content="NLLB training completed successfully, vocabulary accuracy reached 85%",
        category_path="Project/Shiliuzi/Training",
        tags=["nllb", "success", "training"],
        importance=0.9
    )
    print(f"Added: {mem_id}")

    # Semantic search (default vector mode)
    results = await mm.search("NLLB model training")
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:60]}")

    # List by category
    all_memories = await mm.list(category_path="Project/Shiliuzi")
    print(f"Found {len(all_memories)} memories")

    # Stats
    stats = await mm.stats()
    print(f"Total: {stats['total_memories']}, Categories: {stats['categories']}")

    # L1 compression (inject into AI Context)
    # query param: memories relevant to query are prioritized
    compressed = await mm.compress_for_context([mem_id], query="NLLB training")
    print(compressed)

    # Delete
    await mm.delete(mem_id)

asyncio.run(main())
```

### CLI

```bash
# Add memory (auto-classified)
python -m agent_memory.cli add "Test memory"

# Specify category and tags
python -m agent_memory.cli add "NLLB training done" --category "Project/Shiliuzi/Training" --tags "nllb,done"

# Semantic search (default)
python -m agent_memory.cli search "NLLB model training"

# Keyword search (BM25, no vector model needed)
python -m agent_memory.cli search "NLLB" --mode bm25

# Hybrid search (vector + BM25 weighted)
python -m agent_memory.cli search "NLLB" --mode hybrid

# List all
python -m agent_memory.cli list

# List by category
python -m agent_memory.cli list --category "Project/Shiliuzi"

# Show single memory
python -m agent_memory.cli show <memory_id>

# Stats
python -m agent_memory.cli stats

# Delete
python -m agent_memory.cli delete <memory_id>

# Show all top-level categories
python -m agent_memory.cli category --show-all

# Show all used category paths
python -m agent_memory.cli category --list

# HMAC sign (needed for newly added folders)
python -m agent_memory.cli sign memory/ --key "your-secret-key-here"

# HMAC verify (verify folder integrity)
python -m agent_memory.cli verify memory/ --key "your-secret-key-here"

# Re-embed (when switching embedder)
python -m agent_memory.cli --json reembed --embedder hash

# Start Web API server
python -m agent_memory.cli serve --port 8765
```

### MemoryManager API

| Method | Returns | Description |
|--------|---------|-------------|
| `add(content, category_path, tags, importance)` | `str` (memory_id) | Add memory, dual-track write to L4 + L3 |
| `get(memory_id)` | `dict \| None` | Get by ID |
| `delete(memory_id)` | `bool` | Delete from L4 + L3 + vec.json simultaneously |
| `search(query, limit, category_path, mode)` | `list[dict]` | Vector/BM25/hybrid search, mode=vector/bm25/hybrid |
| `list(category_path, limit)` | `list[dict]` | List by category |
| `compress_for_context(memory_ids, query)` | `str` | L1 compression; query param prioritizes query-relevant memories |
| `stats()` | `dict` | Stats (5-min cache): total/categories/storage size/L3 coverage |

---

## Comparison with Other Systems

| System | Data Format | Index | Multi-Agent | NAS Support | Zero External Dependencies |
|--------|-------------|-------|-------------|-------------|--------------------------|
| Hermes | Files | No vectors | Shared workspace | Native | ✅ |
| VCP | Files + vectors | Tag + vector | Shared folder | SQLite single file | ✅ |
| Mem0 | Vectors + graph | Vector + relations | Multi-tenant | Requires DB | ❌ |
| Letta | Memory Blocks | Block index | Agent memory | Requires service | ❌ |
| **AgentMemory v0.3** | md + vec.json | Dual-track retrieval | Shared folder | Native | ✅ |

---

## Architecture Decision Records (v0.3)

| Decision | Description | Rationale |
|----------|-------------|-----------|
| Removed L2 Graph-DB | Three → four layers | Graph-DB was over-engineered; classification paths suffice |
| Removed phase-transition mechanism | Files + vectors always dual-track | VCP verification: phase transition unnecessary |
| Concurrent write control | portalocker file locks | Multi-agent concurrent write scenarios |
| HashEmbedder as default | Zero-dependency, deterministic | 生非异也，善假于物也 |
| LanceDB-first + JSON Fallback | Auto-degrade when unavailable | LanceDB for high-performance, JSON for zero-dependency |
| BM25 hybrid search | Pure Python, zero extra deps | Complements pure keyword search without vector model |
| min_depth=3 | Library/shelf/book 3-level structure | Ensures memory granularity; prevents overly broad top-level |

---

## License

MIT License — free to use, modify, and distribute.

---

_AgentMemory — Memory as a Library. Dual tracks coexist. Never compromise._
