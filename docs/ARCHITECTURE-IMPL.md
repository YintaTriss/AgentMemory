# AgentMemory v0.3 Architecture Implementation

> Integration of ARCHITECTURE-v0.3 design with actual implementation

## Overview

This document maps the v0.3 architecture design to the actual code implementation.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    AgentMemory v0.3                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐                                            │
│  │   L4 Files  │  ← File System Layer                      │
│  │  (持久化层)   │     .md + .vec.json + .meta.json         │
│  └──────┬──────┘                                            │
│         │  auto-sync                                         │
│         ↓                                                   │
│  ┌─────────────┐                                            │
│  │   L3 LanceDB │  ← Vector Store Layer                    │
│  │  (向量检索)  │     Semantic Search                       │
│  └──────┬──────┘                                            │
│         │                                                   │
│         ↓                                                   │
│  ┌─────────────┐                                            │
│  │   L1 LCM    │  ← Compression Layer                      │
│  │  (上下文压缩) │     AI Context Output                    │
│  └─────────────┘                                            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Dual-Track Design

### Track 1: Library Classification

| Aspect | Implementation |
|--------|---------------|
| Category | Hierarchical path (max 4 levels) |
| Format | `project/shiliuzi/training` |
| Storage | `meta.json["category"]` |
| Retrieval | Exact match by path prefix |

### Track 2: Embedding Vector

| Aspect | Implementation |
|--------|---------------|
| Vector | Hash-based (default) |
| Format | `vec.json["vector"]` |
| Storage | L3 vector store |
| Retrieval | Semantic similarity |

## Layer Details

### L4: File System Layer

**File**: `src/agent_memory/l4_files.py`

**Classes**:
- `MemoryMeta` - Metadata dataclass
- `MemoryVec` - Vector dataclass  
- `L4FilesStore` - File operations

**Operations**:
```python
# Save 3-file group
l4.save(memory_id, content, meta, vec)

# Load
memory = l4.load(memory_id)

# List
ids = l4.list()

# Delete
l4.delete(memory_id)

# Stats
stats = l4.get_stats()

# Categories
cats = l4.get_categories()
```

### L3: Vector Store Layer

**File**: `src/agent_memory/l3_lancedb.py`

**Classes**:
- `SimpleVectorStore` - JSON fallback
- `L3LanceDBStore` - LanceDB wrapper

**Operations**:
```python
# Upsert vector
l3.upsert(memory_id, content, vector)

# Search
results = l3.search(query, top_k)

# Delete
l3.delete(memory_id)

# Stats
stats = l3.get_stats()
```

### L1: LCM Compressor

**File**: `src/agent_memory/l1_lcm.py`

**Classes**:
- `L1LCMCompressor` - Context compression
- `FactType` - Fact type constants

**Operations**:
```python
# Compress memories
context = l1.compress(memories, query)

# Extract facts
facts = l1.extract_facts(content)
```

## Main Interface

**File**: `src/agent_memory/memory_manager.py`

**Class**: `MemoryManager`

Unified API combining all layers:

```python
mm = MemoryManager(
    memory_dir="memory",   # L4 path
    data_dir="data",      # L3 path
    embedder="hash"       # Embedder type
)

# All operations
mm.add(...)      # → L4 + L3
mm.search(...)  # → L3 → L4
mm.list_all()   # → L4
mm.delete(...)   # → L4 + L3
```

## CLI Interface

**File**: `src/agent_memory/cli.py`

```bash
python -m agent_memory.cli add "content"
python -m agent_memory.cli search "query"
python -m agent_memory.cli list
python -m agent_memory.cli show <id>
python -m agent_memory.cli delete <id>
python -m agent_memory.cli category
python -m agent_memory.cli stats
```

## Data Flow

### Add Memory

```
User Input
    ↓
MemoryManager.add()
    ↓
┌────────────────────────────────────────┐
│  1. Generate ID (SHA256 hash)          │
│  2. Create MemoryMeta                  │
│  3. Create MemoryVec (embedding)       │
│  4. L4.save() → .md, .vec.json, .meta │
│  5. L3.upsert() → Vector store        │
└────────────────────────────────────────┘
    ↓
Return memory_id
```

### Search Memory

```
Query Input
    ↓
MemoryManager.search()
    ↓
┌────────────────────────────────────────┐
│  1. L3.search() → Vector similarity   │
│  2. Filter by category (optional)       │
│  3. L4.load() → Enrich with metadata   │
└────────────────────────────────────────┘
    ↓
Return results
```

### Delete Memory

```
Memory ID Input
    ↓
MemoryManager.delete()
    ↓
┌────────────────────────────────────────┐
│  1. L4.delete() → Remove 3 files      │
│  2. L3.delete() → Remove from vector   │
└────────────────────────────────────────┘
    ↓
Return success
```

## Storage Format

### File Structure

```
memory/
├── abc123.../
│   ├── abc123.md          # Content (plain text)
│   ├── abc123.vec.json    # Vector data
│   └── abc123.meta.json   # Metadata
├── def456.../
│   └── ...
```

### JSON Schemas

#### meta.json

```json
{
  "id": "abc123def4567890",
  "created_at": "2026-06-07T00:00:00",
  "updated_at": "2026-06-07T00:00:00",
  "category": "project/shiliuzi/training",
  "tags": ["nllb", "success"],
  "source": "manual",
  "importance": 0.8
}
```

#### vec.json

```json
{
  "id": "abc123def4567890",
  "vector": [0.1, -0.2, 0.5, ...],
  "embedder": "hash",
  "dims": 1536
}
```

## Configuration

**File**: `src/agent_memory/config.py`

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_MEMORY_DIR` | `memory` | L4 storage path |
| `AGENT_MEMORY_DATA_DIR` | `data` | L3 storage path |
| `DASHSCOPE_API_KEY` | - | DashScope API |
| `OPENAI_API_KEY` | - | OpenAI API |
| `LOCAL_EMBED_MODEL_PATH` | `bge-large-zh` | Local model path |

### Embedder Types

| Type | Description |
|------|-------------|
| `hash` | Hash-based (default, no API) |
| `openai` | OpenAI embeddings |
| `dashscope` | DashScope text2vec |
| `local` | Local bge-large-zh |

## Testing

**File**: `verify_v03.py`

End-to-end verification script testing all acceptance criteria.

```bash
python verify_v03.py
```

Generates `VERIFICATION_REPORT.md`.

## Architecture Decisions

### Decision 1: Remove L2 Graph-DB

**Reason**: Over-engineering for current use cases

**Impact**: 
- Simplified from 4-layer to 3-layer
- Reduced complexity
- Faster implementation

### Decision 2: 3-File Group Storage

**Reason**: Clear separation of concerns

**Impact**:
- `.md` - Human readable
- `.vec.json` - Machine readable
- `.meta.json` - Structured metadata

### Decision 3: Auto-Sync L4→L3

**Reason**: Simplicity

**Impact**:
- No manual sync needed
- Always consistent
- Single source of truth

### Decision 4: Zero-Dependency Default

**Reason**: Accessibility

**Impact**:
- Works without API keys
- Hash-based embedder
- JSON fallback storage

---

*Architecture implemented: 2026-06-07*
*Based on: ARCHITECTURE-v0.3.md by 楚灵*
