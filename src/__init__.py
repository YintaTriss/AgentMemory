"""
AgentMemory v0.3 - 双轨 + 图书馆记忆系统
统一导出接口，代理到 src.agent_memory
"""

__version__ = "0.3.4"

from src.agent_memory import (
    MemoryManager,
    create_memory_manager,
    L4FilesStore,
    L3QdrantStore,
    L1LCMCompressor,
    FactType,
    SyncManager,
    LibraryClassifier,
    Embedder,
    HashEmbedder,
    get_embedder,
    MemoryMeta,
    MemoryVec,
    integrity,
    _QDRANT_AVAILABLE,
)

__all__ = [
    "__version__",
    "MemoryManager",
    "create_memory_manager",
    "L4FilesStore",
    "L3QdrantStore",
    "_QDRANT_AVAILABLE",
    "L1LCMCompressor",
    "FactType",
    "SyncManager",
    "LibraryClassifier",
    "Embedder",
    "HashEmbedder",
    "get_embedder",
    "MemoryMeta",
    "MemoryVec",
    "integrity",
]
