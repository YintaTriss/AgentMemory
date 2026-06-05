"""
Provider Registry - Provider 工厂和自动检测

根据环境变量自动检测并返回对应的 Provider 实例。
支持 minimax / bailian / openai / mock 四种模式。
"""

import os
from typing import Optional, Type
from dataclasses import dataclass
from enum import Enum

from .protocols import (
    EmbedderProtocol,
    LLMProtocol,
    VectorStoreProtocol,
)


class ProviderType(Enum):
    """Provider 类型枚举"""
    MINIMAX = "minimax"
    BAILIAN = "bailian"
    OPENAI = "openai"
    MOCK = "mock"


@dataclass
class ProviderInfo:
    """Provider 信息"""
    provider_type: ProviderType
    embedder_class: Type[EmbedderProtocol]
    llm_class: Type[LLMProtocol]
    description: str


# =============================================================================
# Provider 注册表
# =============================================================================

_PROVIDER_REGISTRY: dict[ProviderType, ProviderInfo] = {}


def _register_provider(info: ProviderInfo) -> None:
    """注册 Provider 到注册表"""
    _PROVIDER_REGISTRY[info.provider_type] = info


# =============================================================================
# Provider 自动检测
# =============================================================================

def detect_provider_from_env() -> ProviderType:
    """
    根据环境变量自动检测可用 Provider
    
    检测优先级：
    1. MINIMAX_API_KEY → minimax
    2. BAILIAN_API_KEY / DASHSCOPE_API_KEY → bailian
    3. OPENAI_API_KEY → openai
    4. 无 API Key → mock
    
    Returns:
        ProviderType: 检测到的 Provider 类型
    """
    if os.environ.get("MINIMAX_API_KEY"):
        return ProviderType.MINIMAX
    if os.environ.get("BAILIAN_API_KEY") or os.environ.get("DASHSCOPE_API_KEY"):
        return ProviderType.BAILIAN
    if os.environ.get("OPENAI_API_KEY"):
        return ProviderType.OPENAI
    return ProviderType.MOCK


# =============================================================================
# Embedder 工厂函数
# =============================================================================

def get_embedder(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    dimensions: int = 1024,
    **kwargs,
) -> EmbedderProtocol:
    """
    获取 Embedder Provider 实例
    
    Args:
        provider: Provider 名称 (minimax/bailian/openai/mock)，若为 None 则自动检测
        model: 模型名称，若为 None 使用 Provider 默认模型
        dimensions: 向量维度，默认 1024
        **kwargs: 传递给 Provider 的额外参数
    
    Returns:
        EmbedderProtocol 实例
    
    Examples:
        >>> embedder = get_embedder()  # 自动检测
        >>> embedder = get_embedder("mock", dimensions=512)
        >>> embedder = get_embedder("openai", model="text-embedding-3-small")
    """
    # 延迟导入避免循环依赖
    from .embedder_provider import (
        MockEmbedder,
        OpenAIEmbedder,
        DashScopeEmbedder,
        MiniMaxEmbedder,
    )
    
    # 自动检测
    if provider is None:
        detected = detect_provider_from_env()
        provider = detected.value
    
    # 创建对应 Provider
    provider_lower = provider.lower()
    
    if provider_lower in ("minimax", "minimax"):
        return MiniMaxEmbedder(model=model, dimensions=dimensions, **kwargs)
    
    if provider_lower in ("bailian", "dashscope", "qwen"):
        return DashScopeEmbedder(model=model, dimensions=dimensions, **kwargs)
    
    if provider_lower in ("openai",):
        return OpenAIEmbedder(model=model, dimensions=dimensions, **kwargs)
    
    if provider_lower in ("mock", "hash", "local"):
        return MockEmbedder(dimensions=dimensions, **kwargs)
    
    # 默认返回 Mock
    return MockEmbedder(dimensions=dimensions, **kwargs)


# =============================================================================
# LLM 工厂函数
# =============================================================================

def get_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs,
) -> LLMProtocol:
    """
    获取 LLM Provider 实例
    
    Args:
        provider: Provider 名称 (minimax/bailian/openai/mock)，若为 None 则自动检测
        model: 模型名称，若为 None 使用 Provider 默认模型
        **kwargs: 传递给 Provider 的额外参数
    
    Returns:
        LLMProtocol 实例
    
    Examples:
        >>> llm = get_llm()  # 自动检测
        >>> llm = get_llm("openai", model="gpt-4o")
        >>> llm = get_llm("bailian", model="qwen3.6-plus")
    """
    # 延迟导入避免循环依赖
    from .llm_provider import (
        MockLLM,
        OpenAILLM,
        BailianLLM,
        MiniMaxLLM,
    )
    
    # 自动检测
    if provider is None:
        detected = detect_provider_from_env()
        provider = detected.value
    
    # 创建对应 Provider
    provider_lower = provider.lower()
    
    if provider_lower in ("minimax",):
        return MiniMaxLLM(model=model, **kwargs)
    
    if provider_lower in ("bailian", "dashscope", "qwen"):
        return BailianLLM(model=model, **kwargs)
    
    if provider_lower in ("openai",):
        return OpenAILLM(model=model, **kwargs)
    
    if provider_lower in ("mock", "local"):
        return MockLLM(**kwargs)
    
    # 默认返回 Mock
    return MockLLM(**kwargs)


# =============================================================================
# VectorStore 工厂函数
# =============================================================================

def get_vectorstore(
    backend: str = "usearch",
    path: Optional[str] = None,
    dimension: int = 1024,
    metric: str = "cosine",
    **kwargs,
) -> VectorStoreProtocol:
    """
    获取 VectorStore Provider 实例
    
    Args:
        backend: 向量存储后端 (usearch/np)，默认 usearch
        path: 存储路径，默认 .vector_store.usearch
        dimension: 向量维度，默认 1024
        metric: 距离度量 (cosine/l2/ip)，默认 cosine
        **kwargs: 传递给 Provider 的额外参数
    
    Returns:
        VectorStoreProtocol 实例
    
    Examples:
        >>> store = get_vectorstore()
        >>> store = get_vectorstore(path="./data/vectors.usearch", dimension=512)
    """
    # 延迟导入避免循环依赖
    from .vectorstore_provider import USearchVectorStore
    
    backend_lower = backend.lower()
    
    if backend_lower == "usearch":
        return USearchVectorStore(
            path=path,
            dimension=dimension,
            metric=metric,
            **kwargs,
        )
    
    # 默认返回 USearch
    return USearchVectorStore(
        path=path,
        dimension=dimension,
        metric=metric,
        **kwargs,
    )


# =============================================================================
# 可用 Provider 列表
# =============================================================================

def list_available_providers() -> dict[str, list[str]]:
    """
    列出所有可用 Provider
    
    Returns:
        dict: {"embedders": [...], "llms": [...], "vectorstores": [...]}
    """
    detected = detect_provider_from_env()
    
    return {
        "embedders": [
            "minimax (auto)" if detected == ProviderType.MINIMAX else "minimax",
            "bailian (auto)" if detected == ProviderType.BAILIAN else "bailian",
            "openai (auto)" if detected == ProviderType.OPENAI else "openai",
            "mock (auto)" if detected == ProviderType.MOCK else "mock",
        ],
        "llms": [
            "minimax (auto)" if detected == ProviderType.MINIMAX else "minimax",
            "bailian (auto)" if detected == ProviderType.BAILIAN else "bailian",
            "openai (auto)" if detected == ProviderType.OPENAI else "openai",
            "mock (auto)" if detected == ProviderType.MOCK else "mock",
        ],
        "vectorstores": ["usearch", "np"],
        "detected_provider": detected.value,
    }
