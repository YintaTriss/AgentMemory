"""
v2_providers - AgentMemory v2.0 Provider 抽象层

提供独立的 Embedder、LLM、VectorStore Provider 实现。
所有 Provider 通过 Protocol 协议隔离，不直接互相依赖。
"""

from .protocols import (
    EmbedderProtocol,
    LLMProtocol,
    VectorStoreProtocol,
    DistanceMetric,
    SearchResult,
    VectorStoreStats,
    LLMResponse,
    EmbedderResult,
)
from .registry import (
    get_embedder,
    get_llm,
    get_vectorstore,
    list_available_providers,
)
from .embedder_provider import (
    MockEmbedder,
    OpenAIEmbedder,
    DashScopeEmbedder,
    MiniMaxEmbedder,
)
from .llm_provider import (
    MockLLM,
    OpenAILLM,
    BailianLLM,
    MiniMaxLLM,
)
from .vectorstore_provider import USearchVectorStore

__all__ = [
    # Protocols
    "EmbedderProtocol",
    "LLMProtocol",
    "VectorStoreProtocol",
    "DistanceMetric",
    "SearchResult",
    "VectorStoreStats",
    "LLMResponse",
    "EmbedderResult",
    # Registry
    "get_embedder",
    "get_llm",
    "get_vectorstore",
    "list_available_providers",
    # Embedders
    "MockEmbedder",
    "OpenAIEmbedder", 
    "DashScopeEmbedder",
    "MiniMaxEmbedder",
    # LLMs
    "MockLLM",
    "OpenAILLM",
    "BailianLLM",
    "MiniMaxLLM",
    # VectorStores
    "USearchVectorStore",
]
