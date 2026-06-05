"""
AgentMemory v2.0 - Workers 模块

后台任务处理：
- EmbeddingWorker: 向量化任务处理器
"""

from .embedding_worker import (
    EmbeddingWorker,
    EmbeddingStatus,
    EmbeddingTask,
    EmbeddingState,
    create_worker,
)

__all__ = [
    "EmbeddingWorker",
    "EmbeddingStatus",
    "EmbeddingTask",
    "EmbeddingState",
    "create_worker",
]
