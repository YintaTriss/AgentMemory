"""
VectorStore Provider 实现

提供 VectorStore 实现：
- USearchVectorStore: 基于 numpy 的向量存储，支持持久化

遵循 v0.5 架构：
- 文件即本体：向量数据持久化到 .usearch 文件
- 索引即缓存：向量索引是文件的视图
"""

import json
import os
import asyncio
import struct
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

import numpy as np

from .protocols import (
    VectorStoreProtocol,
    DistanceMetric,
    SearchResult,
    VectorStoreStats,
)


# ============================================================================
# USearch VectorStore
# ============================================================================

class USearchVectorStore:
    """
    USearch 兼容的向量存储实现
    
    基于 numpy 实现的高性能向量存储，支持：
    - 批量 upsert/search/delete
    - 余弦相似度 / L2 距离 / 内积
    - 异步操作
    - 磁盘持久化
    
    Example:
        >>> store = USearchVectorStore(path="./data/vectors.usearch", dimension=1024)
        >>> await store.upsert(
        ...     ids=["id1", "id2"],
        ...     vectors=[[0.1]*1024, [0.2]*1024],
        ...     payloads=[{"text": "hello"}, {"text": "world"}]
        ... )
        >>> results = await store.search(query=[0.1]*1024, limit=5)
        >>> await store.persist()
    """
    
    def __init__(
        self,
        path: Optional[str] = None,
        dimension: int = 1024,
        metric: str = "cosine",
        **kwargs
    ):
        """
        初始化 USearchVectorStore
        
        Args:
            path: 存储路径，默认 .vector_store.usearch
            dimension: 向量维度
            metric: 距离度量 (cosine/l2/ip)
        """
        self.dimension = dimension
        self.metric = DistanceMetric(metric)
        self.path = path or ".vector_store.usearch"
        
        # 内存中的数据
        self._vectors: dict[str, np.ndarray] = {}
        self._payloads: dict[str, dict] = {}
        self._index: Optional[np.ndarray] = None
        self._ids: list[str] = []
        
        # 锁保证并发安全
        self._lock = asyncio.Lock()
        
        # 加载已有数据
        if os.path.exists(self.path):
            asyncio.create_task(self.load(self.path))
    
    @property
    def count(self) -> int:
        """向量数量"""
        return len(self._vectors)
    
    async def upsert(
        self,
        ids: list[str],
        vectors: list[list[float]],
        payloads: Optional[list[dict]] = None
    ) -> None:
        """
        插入或更新向量
        
        Args:
            ids: 向量 ID 列表
            vectors: 向量列表
            payloads: 可选的负载数据列表
        """
        async with self._lock:
            for i, id_ in enumerate(ids):
                vec = np.array(vectors[i], dtype=np.float32)
                
                # 归一化（如果使用余弦相似度）
                if self.metric == DistanceMetric.COSINE:
                    norm = np.linalg.norm(vec)
                    if norm > 0:
                        vec = vec / norm
                
                self._vectors[id_] = vec
                self._payloads[id_] = payloads[i] if payloads and i < len(payloads) else {}
            
            # 重建索引
            self._rebuild_index()
    
    async def search(
        self,
        query: list[float],
        limit: int = 10,
        threshold: Optional[float] = None,
        filters: Optional[dict] = None,
        metric: DistanceMetric = DistanceMetric.COSINE,
    ) -> list[SearchResult]:
        """
        向量相似度搜索
        
        Args:
            query: 查询向量
            limit: 返回结果数量
            threshold: 相似度阈值
            filters: 元数据过滤器
            metric: 距离度量
            
        Returns:
            SearchResult 列表
        """
        async with self._lock:
            if not self._vectors:
                return []
            
            query_vec = np.array(query, dtype=np.float32)
            
            # 归一化
            if metric == DistanceMetric.COSINE:
                norm = np.linalg.norm(query_vec)
                if norm > 0:
                    query_vec = query_vec / norm
            
            # 计算所有距离/相似度
            scores: list[tuple[str, float]] = []
            
            for id_, vec in self._vectors.items():
                # 应用过滤器
                if filters:
                    payload = self._payloads.get(id_, {})
                    if not self._match_filters(payload, filters):
                        continue
                
                # 计算距离
                if metric == DistanceMetric.COSINE:
                    # 余弦相似度 = 1 - 余弦距离
                    score = float(np.dot(query_vec, vec))
                elif metric == DistanceMetric.L2:
                    # L2 距离
                    score = float(np.linalg.norm(query_vec - vec))
                elif metric == DistanceMetric.IP:
                    # 内积
                    score = float(np.dot(query_vec, vec))
                else:
                    score = float(np.dot(query_vec, vec))
                
                # 应用阈值
                if threshold is not None:
                    if metric == DistanceMetric.L2:
                        if score > threshold:
                            continue
                    else:
                        if score < threshold:
                            continue
                
                scores.append((id_, score))
            
            # 排序
            if metric == DistanceMetric.L2:
                # L2 距离越小越好
                scores.sort(key=lambda x: x[1])
            else:
                # 相似度越大越好
                scores.sort(key=lambda x: x[1], reverse=True)
            
            # 返回前 limit 个
            results = []
            for id_, score in scores[:limit]:
                payload = self._payloads.get(id_, {})
                
                # L2 距离转相似度
                if metric == DistanceMetric.L2:
                    # 归一化距离到 [0, 1]，越小越好
                    sim_score = 1.0 / (1.0 + score)
                else:
                    sim_score = score
                
                results.append(SearchResult(
                    id=id_,
                    score=sim_score,
                    payload=payload
                ))
            
            return results
    
    def _match_filters(self, payload: dict, filters: dict) -> bool:
        """检查 payload 是否匹配过滤器"""
        for key, value in filters.items():
            if key not in payload:
                return False
            if isinstance(value, list):
                if payload[key] not in value:
                    return False
            elif payload[key] != value:
                return False
        return True
    
    async def delete(self, ids: list[str]) -> None:
        """
        删除向量
        
        Args:
            ids: 要删除的向量 ID 列表
        """
        async with self._lock:
            for id_ in ids:
                if id_ in self._vectors:
                    del self._vectors[id_]
                if id_ in self._payloads:
                    del self._payloads[id_]
            
            self._rebuild_index()
    
    async def persist(self, path: Optional[str] = None) -> None:
        """
        持久化到磁盘
        
        Args:
            path: 可选的存储路径
        """
        target_path = path or self.path
        
        async with self._lock:
            data = {
                "dimension": self.dimension,
                "metric": self.metric.value,
                "ids": self._ids,
                "vectors": {
                    id_: vec.tolist() if isinstance(vec, np.ndarray) else vec
                    for id_, vec in self._vectors.items()
                },
                "payloads": self._payloads
            }
            
            # 原子写
            tmp_path = target_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            
            # rename 是原子操作
            os.replace(tmp_path, target_path)
    
    @classmethod
    async def load(cls, path: str) -> "USearchVectorStore":
        """
        从磁盘加载
        
        Args:
            path: 存储路径
            
        Returns:
            加载的 USearchVectorStore 实例
        """
        i
