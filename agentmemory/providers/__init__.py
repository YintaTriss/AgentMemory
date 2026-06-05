"""
AgentMemory v2.0 - Provider 抽象层

提供 LLM、Embedder、VectorStore 的 Protocol 接口定义，
支持环境变量自动检测 Provider 类型，支持 Mock 兜底。
"""

from .protocols import (
    BaseEmbedderProvider,
    BaseLLMProvider,
    BaseVectorStoreProvider,
    EmbedderConfig,
    LLMConfig,
    VectorStoreConfig,
    SearchResult,
    VectorEntry,
    DistanceMetric,
    LLMResponse,
)
from .embedder import (
    MockEmbedder,
    OpenAIEmbedder,
    MinimaxEmbedder,
    BailianEmbedder,
    get_embedder,
)
from .llm import (
    BailianProvider,
    MinimaxProvider,
    OpenAICompatProvider,
    MockLLMProvider,
    get_llm_provider,
)
from .vectorstore import (
    USearchVectorStore,
    MockVectorStore,
    get_vectorstore,
)
from .registry import (
    ProviderRegistry,
    get_registry,
    register_provider,
)

__all__ = [
    # Protocols
    "BaseEmbedderProvider",
    "BaseLLMProvider",
    "BaseVectorStoreProvider",
    "EmbedderConfig",
    "LLMConfig",
    "VectorStoreConfig",
    "SearchResult",
    "VectorEntry",
    "DistanceMetric",
    "LLMResponse",
    # Embedder
    "MockEmbedder",
    "OpenAIEmbedder",
    "MinimaxEmbedder",
    "BailianEmbedder",
    "get_embedder",
    # LLM
    "BailianProvider",
    "MinimaxProvider",
    "OpenAICompatProvider",
    "MockLLMProvider",
    "get_llm_provider",
    # VectorStore
    "USearchVectorStore",
    "MockVectorStore",
    "get_vectorstore",
    # Registry
    "ProviderRegistry",
    "get_registry",
    "register_provider",
]

__version__ = "2.0.0"
