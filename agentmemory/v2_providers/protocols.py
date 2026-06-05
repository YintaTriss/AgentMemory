"""
Provider Protocols - v2.0 抽象层协议定义

定义了 Embedder、LLM、VectorStore 三大核心 Provider 的协议接口。
所有 Provider 必须实现对应 Protocol，Provider 之间不能互相 import。
"""

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable, AsyncIterator, Any, Optional
from dataclasses import dataclass
from enum import Enum


# =============================================================================
# Embedder Protocol
# =============================================================================

@runtime_checkable
class EmbedderProtocol(Protocol):
    """
    Embedder Provider 协议
    
    职责：将文本转换为向量表示
    
    方法:
    - embed: 批量将文本列表转为向量列表
    - embed_single: 单文本转向量
    - dimension: 获取向量维度
    """
    
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """批量将文本列表转为向量列表"""
        ...
    
    async def embed_single(self, text: str) -> list[float]:
        """将单个文本转为向量"""
        ...
    
    @property
    def dimension(self) -> int:
        """获取向量维度"""
        ...
    
    async def aclose(self) -> None:
        """关闭 provider，释放资源"""
        ...


@dataclass
class EmbedderResult:
    """Embedder 返回结果"""
    vectors: list[list[float]]
    model: str
    usage: Optional[dict] = None


# =============================================================================
# LLM Protocol  
# =============================================================================

@runtime_checkable
class LLMProtocol(Protocol):
    """
    LLM Provider 协议
    
    职责：调用大语言模型生成文本
    
    方法:
    - complete: 同步完成文本生成
    - stream_complete: 流式文本生成
    - chat: 对话模式
    """
    
    async def complete(
        self, 
        prompt: str, 
        **kwargs
    ) -> "LLMResponse":
        """根据 prompt 生成文本"""
        ...
    
    async def stream_complete(
        self, 
        prompt: str, 
        **kwargs
    ) -> AsyncIterator[str]:
        """流式生成文本，返回 token 迭代器"""
        ...
    
    async def chat(
        self, 
        messages: list[dict], 
        **kwargs
    ) -> "LLMResponse":
        """对话模式，messages = [{"role": "user", "content": "..."}]"""
        ...
    
    async def aclose(self) -> None:
        """关闭 provider，释放资源"""
        ...


@dataclass
class LLMResponse:
    """LLM 调用响应"""
    content: str
    usage: dict
    model: str
    raw: Optional[dict] = None
    finish_reason: Optional[str] = None


# =============================================================================
# VectorStore Protocol
# =============================================================================

class DistanceMetric(Enum):
    """向量距离度量"""
    COSINE = "cosine"      # 余弦相似度
    L2 = "l2"              # 欧氏距离
    IP = "ip"              # 内积


@runtime_checkable
class VectorStoreProtocol(Protocol):
    """
    VectorStore Provider 协议
    
    职责：向量存储和检索
    
    方法:
    - upsert: 插入/更新向量
    - search: 近似最近邻搜索
    - delete: 删除向量
    - persist: 持久化到磁盘
    - load: 从磁盘加载
    """
    
    async def upsert(
        self,
        ids: list[str],
        vectors: list[list[float]],
        payloads: Optional[list[dict]] = None,
    ) -> None:
        """插入或更新向量"""
        ...
    
    async def search(
        self,
        query: list[float],
        limit: int = 10,
        threshold: Optional[float] = None,
        filters: Optional[dict] = None,
        metric: DistanceMetric = DistanceMetric.COSINE,
    ) -> list["SearchResult"]:
        """向量相似度搜索"""
        ...
    
    async def delete(self, ids: list[str]) -> None:
        """根据 ID 删除向量"""
        ...
    
    async def persist(self, path: str) -> None:
        """持久化到磁盘"""
        ...
    
    @classmethod
    async def load(cls, path: str) -> "VectorStoreProtocol":
        """从磁盘加载"""
        ...
    
    @property
    def dimension(self) -> int:
        """向量维度"""
        ...
    
    @property
    def count(self) -> int:
        """向量数量"""
        ...


@dataclass
class SearchResult:
    """搜索结果"""
    id: str
    score: float
    payload: dict


@dataclass  
class VectorStoreStats:
    """向量存储统计"""
    count: int
    dimension: int
    metric: DistanceMetric
    path: Optional[str]


# =============================================================================
# 工厂函数类型声明
# =============================================================================

EmbedderFactory = type(EmbedderProtocol)
LLMFactory = type(LLMProtocol)
VectorStoreFactory = type(VectorStoreProtocol)
