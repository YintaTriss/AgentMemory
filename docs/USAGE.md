# AgentMemory v0.3 Usage Guide

## Table of Contents

1. [Quick Start](#quick-start)
2. [Python API](#python-api)
3. [CLI Reference](#cli-reference)
4. [Library Classification](#library-classification)
5. [Embedder Selection](#embedder-selection)
6. [Sync Mechanism](#sync-mechanism)
7. [FAQ](#faq)

---

## Quick Start

### Installation

```bash
cd AgentMemory
pip install -e .
```

### Basic Usage

```python
from agent_memory import MemoryManager

mm = MemoryManager()

# Add a memory
mem_id = mm.add("Remember that NLLB training succeeded", category="project/shiliuzi")

# Search memories
results = mm.search("NLLB")
print(results)

# List all
print(mm.list_all())

# Get stats
print(mm.stats())
```

---

## Python API

### MemoryManager

Main class for memory operations.

```python
from agent_memory import MemoryManager

mm = MemoryManager(
    memory_dir="memory",   # Directory for file storage
    data_dir="data",       # Directory for vector data
    embedder="hash"        # Embedder type
)
```

#### Methods

##### `add(content, category, tags, importance, source)`

Add a new memory.

```python
mem_id = mm.add(
    content="Your memory content here",
    category="project/shiliuzi/training",  # Optional
    tags=["nllb", "success"],               # Optional
    importance=0.8,                         # 0.0-1.0, default 0.5
    source="manual"                         # Optional
)
```

Returns: `str` - Memory ID

##### `search(query, top_k, category)`

Search for relevant memories.

```python
results = mm.search(
    query="NLLB training",
    top_k=5,                                # Max results
    category="project/shiliuzi"             # Optional filter
)

# Results format:
# [
#     {
#         "id": "abc123...",
#         "content": "...",
#         "score": 0.85,
#         "category": "project/shiliuzi",
#         "tags": ["nllb"],
#         "importance": 0.8,
#         "created_at": "2026-06-07T00:00:00"
#     },
#     ...
# ]
```

Returns: `List[Dict]` - Matching memories

##### `list_all()`

List all memories.

```python
memories = mm.list_all()
```

Returns: `List[Dict]` - All memories

##### `get(memory_id)`

Get a specific memory by ID.

```python
memory = mm.get("abc123...")
```

Returns: `Dict` or `None` - Memory data

##### `delete(memory_id)`

Delete a memory.

```python
deleted = mm.delete("abc123...")
```

Returns: `bool` - Success status

##### `get_categories()`

Get all unique categories.

```python
categories = mm.get_categories()
# ["general", "project/shiliuzi", "test"]
```

Returns: `List[str]` - Categories

##### `stats()`

Get system statistics.

```python
stats = mm.stats()
# {
#     "total_memories": 42,
#     "layers": {
#         "L4_Files": {"memory_count": 42, ...},
#         "L3_Vector": {"memory_count": 42, ...}
#     },
#     "embedder": "hash"
# }
```

Returns: `Dict` - Statistics

##### `compress_context(query, top_k)`

Compress relevant memories into AI context.

```python
context = mm.compress_context(
    query="Shiliuzi project",
    top_k=10
)
```

Returns: `str` - Compressed context

---

## CLI Reference

### Installation

After `pip install -e .`, use:

```bash
python -m agent_memory.cli <command> [options]
```

### Commands

#### `add <content>`

Add a new memory.

```bash
python -m agent_memory.cli add "Your memory content"

# With options
python -m agent_memory.cli add "Content" --category "project/test" --tags "tag1,tag2" --importance 0.8
```

#### `search <query>`

Search memories.

```bash
python -m agent_memory.cli search "query text"
python -m agent_memory.cli search "query" --limit 10
```

#### `list`

List all memories.

```bash
python -m agent_memory.cli list
```

#### `show <memory_id>`

Show a specific memory.

```bash
python -m agent_memory.cli show abc123def456
```

#### `delete <memory_id>`

Delete a memory.

```bash
python -m agent_memory.cli delete abc123def456
```

#### `category`

List all categories.

```bash
python -m agent_memory.cli category
```

#### `stats`

Show system statistics.

```bash
python -m agent_memory.cli stats
```

---

## Library Classification

### Concept

Library classification uses hierarchical categories (like a library's catalog system) to organize memories. Max 4 levels deep.

### Examples

```
# Good examples
project/shiliuzi/training
project/shiliuzi/competition/provincial
ai/llm/claude/context-window
personal/learning/python

# Simple
general
work
test
```

### Benefits

1. **Exact retrieval**: Find all memories in a category
2. **Hierarchical organization**: Like a file system
3. **No semantic ambiguity**: Category paths are precise

### Best Practices

- Use lowercase for categories
- Use `/` as level separator
- Keep categories meaningful and consistent
- Max 4 levels deep

---

## Embedder Selection

### Hash (Default)

No API needed, fast but basic matching.

```python
mm = MemoryManager(embedder="hash")
```

### OpenAI

Uses OpenAI's embedding API.

```bash
export OPENAI_API_KEY="sk-..."
```

```python
mm = MemoryManager(embedder="openai")
```

### DashScope

Uses Alibaba's DashScope API.

```bash
export DASHSCOPE_API_KEY="..."
```

```python
mm = MemoryManager(embedder="dashscope")
```

### Local

Uses local embedding model (bge-large-zh).

```bash
export LOCAL_EMBED_MODEL_PATH="/path/to/bge-large-zh"
```

```python
mm = MemoryManager(embedder="local")
```

---

## Sync Mechanism

### Auto-Sync (L4 → L3)

When you add a memory, it automatically syncs to the vector store:

```
mm.add(content)
       ↓
L4 Files (.md, .vec.json, .meta.json)
       ↓ (auto)
L3 Vector Store
```

### Manual Operations

```python
# All operations auto-sync
mm.add("content")      # → L4 + L3
mm.delete("id")         # → L4 + L3
```

### When to Sync

The system auto-syncs on:
- `add()` - New memory
- `delete()` - Remove memory

---

## FAQ

### Q: What's the difference between L4 and L3?

**A**: 
- **L4** = File storage (.md, .vec.json, .meta.json)
- **L3** = Vector index for fast search

Both store the same data, just in different formats.

### Q: Can I use without API keys?

**A**: Yes! Use `embedder="hash"` (default). Works offline.

### Q: How do I migrate data?

**A**: Simply copy the `memory/` folder. It's self-contained.

### Q: What's the storage format?

**A**: Each memory = 3 files:
```
memory/abc123.../
├── abc123.md         # Content
├── abc123.vec.json   # Vector
└── abc123.meta.json  # Metadata
```

### Q: How do I search by category?

**A**:
```python
results = mm.search("query", category="project/shiliuzi")
```

### Q: How do I backup?

**A**: Just backup the `memory/` directory. It's human-readable.

---

## Troubleshooting

### Memory not found

```python
# Check if exists
memories = mm.list_all()
print(memories)

# Get specific
memory = mm.get("your-id")
```

### Empty search results

- Try shorter queries
- Check category filter
- Verify memory was added

### Slow performance

- Use hash embedder (fastest)
- Limit `top_k` in search
- Consider organizing into categories

---

*Last updated: 2026-06-07*
