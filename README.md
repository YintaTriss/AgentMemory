# AgentMemory v0.3

> Dual-track + Library Memory System for AI Agents

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)

AgentMemory v0.3 is a simplified, zero-dependency memory system for AI agents. It uses a **3-layer architecture** with **dual-track retrieval** and **library-style classification**.

## Core Concepts

### Architecture (3-Layer Simplified)

```
L4 Files (File System)
    └─ .md / .vec.json / .meta.json
           ↓  auto-sync
L3 LanceDB (Vector Store)
    └─  Semantic Search
           ↓
L1 LCM (Context Compression)
    └─  AI Context Output
```

### Dual-Track Retrieval

| Track | Method | Use Case |
|-------|--------|----------|
| Library Classification | Category/Tags | Exact retrieval |
| Embedding Vector | Semantic similarity | Fuzzy search |

### Library Classification

Up to 4 levels deep:
```
Project/Shiliuzi/Corpus/NLLB-Training
Project/Shiliuzi/Competition/Provincial
```

## Installation

```bash
cd AgentMemory
pip install -e .
```

## Quick Start

### Python API

```python
from agent_memory import MemoryManager

# Initialize
mm = MemoryManager()

# Add memory
mem_id = mm.add(
    content="NLLB training succeeded",
    category="Project/Shiliuzi/Training",
    tags=["nllb", "success"],
    importance=0.8
)
print(f"Added: {mem_id}")

# Search
results = mm.search("NLLB training")
for r in results:
    print(f"[{r["score"]:.2f}] {r["content"]}")

# List all
all_memories = mm.list_all()

# Get categories
cats = mm.get_categories()
print(f"Categories: {cats}")

# Stats
stats = mm.stats()
print(f"Total memories: {stats["total_memories"]}")

# Delete
mm.delete(mem_id)
```

### CLI

```bash
# Add memory
python -m agent_memory.cli add "Test memory" --category "test" --tags "demo"

# Search
python -m agent_memory.cli search "test"

# List all
python -m agent_memory.cli list

# Show specific
python -m agent_memory.cli show <memory_id>

# Delete
python -m agent_memory.cli delete <memory_id>

# List categories
python -m agent_memory.cli category

# Stats
python -m agent_memory.cli stats
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_MEMORY_DIR` | `memory` | Memory storage directory |
| `AGENT_MEMORY_DATA_DIR` | `data` | Vector data directory |
| `DASHSCOPE_API_KEY` | - | DashScope API (optional) |
| `OPENAI_API_KEY` | - | OpenAI API (optional) |

### Embedder Selection

```python
# Hash-based (default, no API needed)
mm = MemoryManager(embedder="hash")

# OpenAI
mm = MemoryManager(embedder="openai")

# DashScope
mm = MemoryManager(embedder="dashscope")

# Local model (bge-large-zh)
mm = MemoryManager(embedder="local")
```

## Data Structure

Each memory = 3 files in same directory:

```
memory/
├── <id>.md              # Raw content
├── <id>.vec.json        # Vector data
└── <id>.meta.json       # Metadata
```

### Metadata Format

```json
{
  "id": "abc123...",
  "created_at": "2026-06-07T00:00:00",
  "updated_at": "2026-06-07T00:00:00",
  "category": "Project/Shiliuzi",
  "tags": ["nllb", "success"],
  "source": "manual",
  "importance": 0.8
}
```

## Design Philosophy

> **Memory as Library.** Books don't change, but the catalog makes finding them precise.

### Key Innovations

1. **Dual-track**: File + Vector always coexist
2. **Zero dependency**: Just needs a folder + optional embedding model
3. **Hot-swappable**: Copy folder = migrate entire memory library
4. **Library classification**: Up to 4-level hierarchical tags

## Performance

| Operation | Time (ms) |
|-----------|-----------|
| add | ~2 |
| search | ~0.3 |
| list | ~0.5 |

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

## License

MIT License
