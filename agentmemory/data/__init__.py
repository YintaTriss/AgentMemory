"""
v2.0 Data Layer - 数据层模块

包含 5 个核心模块：
- DataLake: 数据湖，文件存储基础
- Library: 图书馆分类管理
- TagIndex: Tag 倒排索引
- EmbeddingStateMachine: Embedding 状态机
- TieredLog: 分层日志

Author: backend engineer
Version: v2.0
"""

from .datalake import (
    DataLake,
    DataLakeError,
    PathSecurityError,
    MemoryNotFoundError,
    AtomicWriteError,
    MemoryFile,
    MemoryContent,
    MemoryVector,
    MemoryMeta,
)

from .library import (
    Library,
    LibraryError,
    CategoryNotFoundError,
    CategoryDepthExceededError,
    CategoryNotInWhitelistError,
    CategoryAlreadyExistsError,
    CategoryNode,
    CategoryInfo,
)

from .tag_index import (
    TagIndex,
    TagIndexError,
    TagEntry,
    TagStats,
)

from .embedding_state import (
    EmbeddingStateMachine,
    EmbeddingState,
    EmbeddingStateError,
    InvalidStateTransitionError,
    EmbeddingStateEntry,
)

from .tiered_log import (
    TieredLog,
    TieredLogError,
    LogLevel,
    LogEntry,
    Manifest,
)

__all__ = [
    # DataLake
    "DataLake",
    "DataLakeError",
    "PathSecurityError",
    "MemoryNotFoundError",
    "AtomicWriteError",
    "MemoryFile",
    "MemoryContent",
    "MemoryVector",
    "MemoryMeta",
    # Library
    "Library",
    "LibraryError",
    "CategoryNotFoundError",
    "CategoryDepthExceededError",
    "CategoryNotInWhitelistError",
    "CategoryAlreadyExistsError",
    "CategoryNode",
    "CategoryInfo",
    # TagIndex
    "TagIndex",
    "TagIndexError",
    "TagEntry",
    "TagStats",
    # EmbeddingStateMachine
    "EmbeddingStateMachine",
    "EmbeddingState",
    "EmbeddingStateError",
    "InvalidStateTransitionError",
    "EmbeddingStateEntry",
    # TieredLog
    "TieredLog",
    "TieredLogError",
    "LogLevel",
    "LogEntry",
    "Manifest",
]
