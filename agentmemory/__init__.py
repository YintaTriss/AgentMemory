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
from .data.datalake import DataLake
from .data.library import Library
from .data.tag_index import TagIndex
from .data.embedding_state import EmbeddingStateMachine, EmbeddingState
from .data.tiered_log import TieredLog

# Search
from .search.search_engine import SearchEngine

# Decay
from .decay_engine import DecayEngine

# Providers
try:
    from .providers.llm import get_llm_provider
except ImportError:
    get_llm_provider = None

try:
    from .providers.embedder import get_embedder
except ImportError:
    get_embedder = None

try:
    from .providers.vectorstore import get_vectorstore
except ImportError:
    get_vectorstore = None

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
    "Library",
    "TagIndex",
    "EmbeddingStateMachine",
    "EmbeddingState",
    "TieredLog",
    # Search
    "SearchEngine",
    # Decay
    "DecayEngine",
    # Providers
    "get_llm_provider",
    "get_embedder",
    "get_vectorstore",
]
