"""
AgentMemory v2.0 - 顶尖记忆系统
融合 Hermes + Mem0 优点，四层闭环记忆架构（v2.0 架构重写）

导出所有公开类，符合 §5 接口契约。
"""

__version__ = "2.0.0"

from .memory_manager import MemoryHermes
from .config import MemoryConfig, get_memory_config
from .multi_agent import MultiAgentLock, SharedLog
from .models import MemoryEntry, Memory

# Data layer
from .data.datalake import DataLake, MemoryMeta
from .data.library import Library
from .data.tag_index import TagIndex
from .data.embedding_state import EmbeddingStateMachine, EmbeddingState
from .data.tiered_log import TieredLog

# Search
from .search.search_engine import SearchEngine

# Decay
from .decay_engine import DecayEngine

# CLI & Web
from . import cli
from . import web

# Providers
try:
    from .providers.llm import get_llm_provider
except ImportError:
    get_llm_provider = None

try:
    from .providers.embedder import get_embedder, MockEmbedder
except ImportError:
    get_embedder = None
    MockEmbedder = None

try:
    from .providers.vectorstore import get_vectorstore, MockVectorStore
except ImportError:
    get_vectorstore = None
    MockVectorStore = None

try:
    from .workers import create_worker, EmbeddingWorker, EmbeddingStatus
except ImportError:
    create_worker = None
    EmbeddingWorker = None
    EmbeddingStatus = None

__all__ = [
    # Core
    "MemoryHermes",
    "MemoryConfig",
    "get_memory_config",
    # MultiAgent
    "MultiAgentLock",
    "SharedLog",
    # Models
    "MemoryEntry",
    "Memory",
    # Data layer
    "DataLake",
    "MemoryMeta",
    "Library",
    "TagIndex",
    "EmbeddingStateMachine",
    "EmbeddingState",
    "TieredLog",
    # Search
    "SearchEngine",
    # Decay
    "DecayEngine",
    # CLI & Web
    "cli",
    "web",
    # Providers
    "get_llm_provider",
    "get_embedder",
    "get_vectorstore",
    "MockEmbedder",
    "MockVectorStore",
    # Workers
    "create_worker",
    "EmbeddingWorker",
    "EmbeddingStatus",
]
