"""
AgentMemory v0.3 - 双轨 + 图书馆记忆系统

Simplified 3-layer architecture:
- L4: File System (md + meta.json)
- L3: Vector Store (LanceDB or Qdrant Edge)
- L1: LCM Compressor

Design Philosophy: Memory as Library
- Track 1: Library Classification (exact retrieval)
- Track 2: Embedding Vector (semantic search)

Components:
- MemoryManager: Unified async API
- L4FilesStore: File system storage
- L3LanceDBStore: LanceDB vector search (default)
- L3QdrantStore: Qdrant Edge vector search (Rust内核，高性能)
- L1LCMCompressor: Context compression
- SyncManager: L4 ↔ L3 synchronization
- LibraryClassifier: Automatic categorization
- Embedder: Vector embeddings (HashEmbedder, DashScopeEmbedder)
- IntegrityVerifier: HMAC signature verification

L3 Backend Selection:
- LanceDB (default): pip install agentmemory[lancedb]
- Qdrant Edge: pip install agentmemory[qdrant]
"""

__version__ = "0.3.4"
__author__ = "楚灵"
__license__ = "MIT"

# Main classes
from .manager import MemoryManager, create_memory_manager
from .l4_files import L4FilesStore, MemoryMeta, MemoryVec
from .l3_lancedb import L3LanceDBStore
try:
    from .l3_qdrant import L3QdrantStore
    _QDRANT_AVAILABLE = True
except ImportError:
    L3QdrantStore = None
    _QDRANT_AVAILABLE = False
from .l1_lcm import L1LCMCompressor, FactType
from .sync import SyncManager
from .library import LibraryClassifier
from .embedder import Embedder, HashEmbedder, DashScopeEmbedder, get_embedder
from . import integrity

__all__ = [
    # Version
    "__version__",
    # Main API
    "MemoryManager",
    "create_memory_manager",
    # Storage layers
    "L4FilesStore",
    "L3LanceDBStore",
    "L3QdrantStore",
    "_QDRANT_AVAILABLE",
    # Compression
    "L1LCMCompressor",
    "FactType",
    # Sync
    "SyncManager",
    # Classification
    "LibraryClassifier",
    # Embedding
    "Embedder",
    "HashEmbedder",
    "DashScopeEmbedder",
    "get_embedder",
    # Data classes
    "MemoryMeta",
    "MemoryVec",
    # Integrity
    "integrity",
]
