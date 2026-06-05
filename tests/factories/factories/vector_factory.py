"""
Vector Factory - 向量存储对象工厂

用于创建测试中使用的 VectorEntry 和相关对象。
"""

from typing import Optional
import uuid

from agentmemory.providers.protocols import (
    VectorEntry,
    SearchResult,
    VectorStoreConfig,
    DistanceMetric,
)


class VectorFactory:
    """
    Vector 工厂类
    
    提供便捷的方法来创建测试用的 Vector 对象。
    """
    
    @staticmethod
    def create_entry(
        id: Optional[str] = None,
        vector: Optional[list[float]] = None,
        dimensions: int = 384,
        metadata: Optional[dict] = None,
        content: Optional[str] = None,
    ) -> VectorEntry:
        """
        创建 VectorEntry
        
        Args:
            id: 向量 ID（默认自动生成）
            vector: 向量数据
            dimensions: 向量维度（用于生成随机向量）
            metadata: 元数据
            content: 内容（添加到元数据）
            
        Returns:
            VectorEntry 对象
        """
        if vector is None:
            from .embedder_factory import EmbedderFactory
            vector = EmbedderFactory.create_random_vector(dimensions)
        
        meta = dict(metadata) if metadata else {}
        if content:
            meta["content"] = content
        
        return VectorEntry(
            id=id or f"vec-{uuid.uuid4().hex[:8]}",
            vector=vector,
            metadata=meta,
        )
    
    @staticmethod
    def create_search_result(
        id: Optional[str] = None,
        score: float = 0.0,
        metadata: Optional[dict] = None,
        vector: Optional[list[float]] = None,
    ) -> SearchResult:
        """
        创建 SearchResult
        
        Args:
            id: 向量 ID
            score: 相似度分数
            metadata: 元数据
            vector: 向量数据
            
        Returns:
            SearchResult 对象
        """
        return SearchResult(
            id=id or f"result-{uuid.uuid4().hex[:8]}",
            score=score,
            metadata=metadata or {},
            vector=vector,
        )
    
    @staticmethod
    def create_batch_entries(
        count: int = 10,
        dimensions: int = 384,
        id_prefix: str = "batch",
        start_index: int = 0,
        with_content: bool = True,
    ) -> list[VectorEntry]:
        """
        创建批量 VectorEntry
        
        Args:
            count: 创建数量
            dimensions: 向量维度
            id_prefix: ID 前缀
            start_index: 起始索引
            with_content: 是否添加 content 字段
            
        Returns:
            VectorEntry 列表
        """
        entries = []
        for i in range(count):
            index = start_index + i
            content = f"内容 {index}" if with_content else None
            
            entry = VectorFactory.create_entry(
                id=f"{id_prefix}-{index}",
                dimensions=dimensions,
                metadata={
                    "index": index,
                    "batch": id_prefix,
                },
                content=content,
            )
            entries.append(entry)
        
        return entries
    
    @staticmethod
    def create_entries_with_scores(
        base_entries: list[VectorEntry],
        scores: list[float],
    ) -> list[SearchResult]:
        """
        为 VectorEntry 创建对应的 SearchResult
        
        Args:
            base_entries: 基础 VectorEntry 列表
            scores: 相似度分数列表
            
        Returns:
            SearchResult 列表
        """
        results = []
        for entry, score in zip(base_entries, scores):
            result = VectorFactory.create_search_result(
                id=entry.id,
                score=score,
                metadata=entry.metadata,
                vector=entry.vector,
            )
            results.append(result)
        
        return results
    
    @staticmethod
    def create_config(
        path: str = "test.usearch",
        metric: DistanceMetric = DistanceMetric.COSINE,
        dimensions: int = 384,
        **kwargs,
    ) -> VectorStoreConfig:
        """
        创建 VectorStoreConfig
        
        Args:
            path: 存储路径
            metric: 距离度量
            dimensions: 向量维度
            **kwargs: 其他配置字段
            
        Returns:
            VectorStoreConfig 对象
        """
        return VectorStoreConfig(
            path=path,
            metric=metric,
            dimensions=dimensions,
            **kwargs,
        )
    
    @staticmethod
    def create_entries_with_categories(
        categories: list[str],
        dimensions: int = 384,
        entries_per_category: int = 3,
    ) -> list[VectorEntry]:
        """
        创建按分类组织的 VectorEntry
        
        Args:
            categories: 分类列表
            dimensions: 向量维度
            entries_per_category: 每个分类的条目数
            
        Returns:
            VectorEntry 列表
        """
        entries = []
        entry_id = 0
        
        for category in categories:
            for i in range(entries_per_category):
                entry = VectorFactory.create_entry(
                    id=f"cat-{entry_id}",
                    dimensions=dimensions,
                    metadata={
                        "category": category,
                        "index": i,
                    },
                    content=f"{category} 相关内容 {i+1}",
                )
                entries.append(entry)
                entry_id += 1
        
        return entries
    
    @staticmethod
    def create_entries_with_tags(
        all_tags: list[str],
        dimensions: int = 384,
        tags_per_entry: int = 2,
    ) -> list[VectorEntry]:
        """
        创建带标签的 VectorEntry
        
        Args:
            all_tags: 所有可用标签
            dimensions: 向量维度
            tags_per_entry: 每个条目的标签数
            
        Returns:
            VectorEntry 列表
        """
        import random
        
        entries = []
        entry_id = 0
        
        for tag in all_tags:
            selected_tags = random.sample(all_tags, min(tags_per_entry, len(all_tags)))
            
            entry = VectorFactory.create_entry(
                id=f"tag-{entry_id}",
                dimensions=dimensions,
                metadata={
                    "tags": selected_tags,
                    "primary_tag": tag,
                },
                content=f"标签 {tag} 的内容",
            )
            entries.append(entry)
            entry_id += 1
        
        return entries
