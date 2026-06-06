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
L4 Files (File System) → L3 LanceDB (Vector) → L1 LCM (Compression)
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
