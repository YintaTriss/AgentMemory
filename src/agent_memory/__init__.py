"""
AgentMemory v2.1.0 - 四层闭环记忆系统 + 梦境子系统

架构升级（2026-07-14）：
- L4 文件存储（md + meta.json）
- L3 Qdrant Edge 向量库
- L2 标签系统 + 共现矩阵（SQLite WAL）
- L1 LCM 压缩器

搜索管道（实时）：
  Fuzzy → BM25 → Vector → Reranker → 加权融合

梦境子系统（后台）：
  Light (6h) → Deep (3am) → REM (周日) → LLM 叙事
  信号分解 (EPA + 残差金字塔) → 图传播 (Spike Routing) → 固化

对标 VCP 记忆系统、OpenClaw Dreaming、Hermes Memory 的工程实践。
"""

__version__ = "2.1.0"
__author__ = "楚零"
__license__ = "MIT"

# Main classes
from .manager import MemoryManager, create_memory_manager, TeamMemoryManager, create_team_memory_manager
from .l4_files import L4FilesStore, MemoryMeta, MemoryVec
try:
    from .l3_qdrant import L3QdrantStore
    _QDRANT_AVAILABLE = True
except ImportError:
    L3QdrantStore = None
    _QDRANT_AVAILABLE = False
from .l1_lcm import L1LCMCompressor, FactType
from .fact_extractor import FactExtractor, extract_facts
from .observations import ObservationsGenerator  # 2026-07-15+ 方向 3
from .contradiction import ContradictionDetector  # 2026-07-15+ 方向 1
from .temporal import (  # 2026-07-15+ 方向 2
    TemporalIntentDetector,
    filter_by_time_range,
    filter_only_valid,
)
from .sync import SyncManager
from .watcher import MemoryWatcher
from .fuzzy_search import fuzzy_search, prefix_search, similarity
from .reranker import rerank
from .dream_signal import SignalDecomposer
from .dream_graph import GraphPropagator
from .dream_consolidate import DreamConsolidator
from .dream_engine import DreamEngine
from .dream_narrative import DreamNarrativeGenerator
from .dream_phase_selector import DreamPhaseSelector, DreamPhaseDecision  # 2026-07-15 方向 5
from .dream_provenance import DreamProvenance, DreamProvenanceTracker  # 2026-07-15 方向 6
from .dream_scheduler import DreamScheduler, ScheduleRule, DEFAULT_SCHEDULE  # 2026-07-15 方向 7
from .embedder_registry import (  # 2026-07-15 方向 8
    list_models,
    get_recommended_model,
    get_model_from_env,
    create_embedder,
)
from .health_monitor import HealthMonitor
from .config_watcher import ConfigWatcher
from .agent_tool import AgentMemoryTool
from .compactor import MemoryCompactor
from .write_queue import AsyncWriteQueue, Priority
from .search_pipeline import SearchPipeline
from .library import LibraryClassifier
from .embedder import Embedder, HashEmbedder, get_embedder
from .sqlite_store import SQLiteStore
from .langchain_compat import AgentMemoryForLangChain, LangChainMemory, LlamaIndexMemory
from . import integrity

# AgentTeam integration（可选依赖，运行时检测）
try:
    from .agentteam_integration import (
        AgentTeamMemoryProvider,
        get_memory_provider,
        TeamContext,
        is_agentteam_environment,
    )
    _AGENTTEAM_AVAILABLE = True
except ImportError:
    AgentTeamMemoryProvider = None
    get_memory_provider = None
    TeamContext = None
    is_agentteam_environment = None
    _AGENTTEAM_AVAILABLE = False

__all__ = [
    # Version
    "__version__",
    # Main API
    "MemoryManager",
    "create_memory_manager",
    "TeamMemoryManager",
    "create_team_memory_manager",
    # Storage layers
    "L4FilesStore",
    "L3QdrantStore",
    "_QDRANT_AVAILABLE",
    # Compression
    "L1LCMCompressor",
    "FactType",
    # FactType extraction (v0.3 +)
    "FactExtractor",
    "extract_facts",
    # Observations (2026-07-15+ 方向 3)
    "ObservationsGenerator",
    # Contradiction detection (2026-07-15+ 方向 1)
    "ContradictionDetector",
    # Temporal (2026-07-15+ 方向 2)
    "TemporalIntentDetector",
    "filter_by_time_range",
    "filter_only_valid",
    # Sync
    "SyncManager",
    # Classification
    "LibraryClassifier",
    # Embedding
    "Embedder",
    "HashEmbedder",
    "get_embedder",
    # Data classes
    "MemoryMeta",
    "MemoryVec",
    # Integrity
    "integrity",
    # V2.1 新增：搜索/梦境/监控/工具类
    "MemoryWatcher",
    "fuzzy_search", "prefix_search", "similarity",
    "rerank",
    "SearchPipeline",
    "SignalDecomposer", "GraphPropagator", "DreamConsolidator", "DreamEngine",
    "DreamNarrativeGenerator", "HealthMonitor",
    # 2026-07-15 方向 5 + 6
    "DreamPhaseSelector", "DreamPhaseDecision",
    "DreamProvenance", "DreamProvenanceTracker",
    # 2026-07-15 方向 7
    "DreamScheduler", "ScheduleRule", "DEFAULT_SCHEDULE",
    # 2026-07-15 方向 8: 可插拔本地 embedding 模型
    "list_models", "get_recommended_model", "get_model_from_env", "create_embedder",
    "ConfigWatcher",
    "AgentMemoryTool",
    "MemoryCompactor",
    "AsyncWriteQueue", "Priority",
    "SQLiteStore",
    # LangChain / LlamaIndex 兼容
    "AgentMemoryForLangChain", "LangChainMemory", "LlamaIndexMemory",
    # AgentTeam integration
    "AgentTeamMemoryProvider",
    "get_memory_provider",
    "TeamContext",
    "is_agentteam_environment",
    "_AGENTTEAM_AVAILABLE",
]
