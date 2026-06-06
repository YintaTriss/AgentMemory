"""
AgentMemory v0.3 - 双轨 + 图书馆记忆系统

Simplified 3-layer architecture:
- L4: File System (md + vec.json + meta.json)
- L3: LanceDB Vector Store
- L1: LCM Compressor

Design Philosophy: Memory as Library
- Track 1: Library Classification (exact retrieval)
- Track 2: Embedding Vector (semantic search)
"""

__version__ = "0.3.0"
__author__ = "楚灵"
__license__ = "MIT"

from .memory_manager import MemoryManager
from .l4_files import L4FilesStore, MemoryMeta, MemoryVec
from .l1_lcm import L1LCMCompressor, FactType

__all__ = [
    "__version__",
    "MemoryManager",
    "L4FilesStore",
    "MemoryMeta",
    "MemoryVec",
    "L1LCMCompressor",
    "FactType",
]
