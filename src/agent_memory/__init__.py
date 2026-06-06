"""
AgentMemory v0.3 - 双轨 + 图书馆记忆系统

Simplified 3-layer architecture:
- L4: File System (md + meta.json)
- L3: LanceDB Vector Store
- L1: LCM Compressor

Design Philosophy: Memory as Library
- Track 1: Library Classification (exact retrieval)
- Track 2: Embedding Vector (semantic search)

Components:
- MemoryManager: Unified async API
- L4FilesStore: File system storage
- L3LanceDBStore: Vector semantic search
- L1LCMCompressor: Context compression
- SyncManager: L4 ↔ L3 synchronization
- LibraryClassifier: Automatic categorization
- Embedder: Vector embeddings (HashEmbedder, DashScopeEmbedder)
- IntegrityVerifier: HMAC signature verification
"""

__version__ = "0.3.0"
__author__ = "楚灵"
__license__ = "MIT"

# Main classes
from .manager import MemoryManager, create_memory_manager
from .l4_files import L4FilesStore, MemoryMeta, MemoryVec
from .l3_lancedb import L3LanceDBStore
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
