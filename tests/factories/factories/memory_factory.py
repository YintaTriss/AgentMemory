"""
Memory Factory - 记忆对象工厂

用于创建测试中使用的记忆对象。
"""

import uuid
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

from agentmemory.search.search_engine import MemoryEntry


@dataclass
class MemoryFactory:
    """
    MemoryEntry 工厂类
    
    提供便捷的方法来创建测试用的 MemoryEntry 对象。
    """
    
    base_id: str = "mem"
    base_content: str = "这是一条测试记忆内容"
    base_category: str = "test"
    base_tags: list = field(default_factory=lambda: ["test", "sample"])
    base_importance: float = 0.5
    base_metadata: dict = field(default_factory=dict)
    
    @classmethod
    def create(
        cls,
        id: Optional[str] = None,
        content: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[list] = None,
        importance: Optional[float] = None,
        metadata: Optional[dict] = None,
        vector: Optional[list[float]] = None,
        score: float = 0.0,
        **kwargs,
    ) -> MemoryEntry:
        """
        创建单个 MemoryEntry
        
        Args:
            id: 记忆 ID（默认自动生成）
            content: 记忆内容
            category: 分类路径
            tags: 标签列表
            importance: 重要性分数
            metadata: 元数据字典
            vector: 向量（可选）
            score: 相似度分数
            **kwargs: 其他元数据字段
            
        Returns:
            MemoryEntry 对象
        """
        meta = dict(cls.base_metadata)
        
        if category is not None:
            meta["category"] = category
        elif "category" not in meta:
            meta["category"] = cls.base_category
            
        if tags is not None:
            meta["tags"] = tags
        elif "tags" not in meta:
            meta["tags"] = cls.base_tags.copy()
            
        if importance is not None:
            meta["importance"] = importance
        elif "importance" not in meta:
            meta["importance"] = cls.base_importance
        
        if metadata:
            meta.update(metadata)
        
        if kwargs:
            meta.update(kwargs)
        
        return MemoryEntry(
            id=id or f"{cls.base_id}-{uuid.uuid4().hex[:8]}",
            content=content or cls.base_content,
            metadata=meta,
            vector=vector,
            score=score,
        )
    
    @classmethod
    def create_batch(
        cls,
        count: int = 5,
        content_prefix: str = "记忆内容",
        **kwargs,
    ) -> list[MemoryEntry]:
        """
        创建批量 MemoryEntry
        
        Args:
            count: 创建数量
            content_prefix: 内容前缀
            **kwargs: 传递给 create 的参数
            
        Returns:
            MemoryEntry 列表
        """
        entries = []
        for i in range(count):
            entry = cls.create(
                id=f"{cls.base_id}-{i}",
                content=f"{content_prefix} {i+1}",
                **kwargs,
            )
            entries.append(entry)
        
        return entries
    
    @classmethod
    def create_with_category_tree(
        cls,
        tree: dict,
        base_id: str = "cat",
    ) -> list[MemoryEntry]:
        """
        根据分类树创建记忆
        
        Args:
            tree: 分类树字典，key 是分类名，value 是包含 children 的字典
            base_id: ID 前缀
            
        Returns:
            MemoryEntry 列表
        """
        entries = []
        category_id = 0
        
        def traverse(node_name: str, path: str = ""):
            nonlocal category_id
            current_path = f"{path}/{node_name}" if path else node_name
            
            # 为每个分类节点创建记忆
            entry = cls.create(
                id=f"{base_id}-{category_id}",
                content=f"关于 {node_name} 的记忆",
                category=current_path,
            )
            entries.append(entry)
            category_id += 1
            
            # 遍历子节点
            children = tree.get(node_name, {}).get("children", [])
            for child in children:
                traverse(child, current_path)
        
        # 找到根节点并开始遍历
        roots = [k for k, v in tree.items() if v.get("parent") is None or v.get("parent") == "root"]
        for root in roots:
            traverse(root)
        
        return entries
    
    @classmethod
    def create_with_tags(
        cls,
        tags: list[str],
        tag_assignment_rate: float = 0.7,
        **kwargs,
    ) -> list[MemoryEntry]:
        """
        创建带标签的记忆
        
        Args:
            tags: 可用的标签列表
            tag_assignment_rate: 每个标签被分配的概率
            **kwargs: 其他参数
            
        Returns:
            MemoryEntry 列表
        """
        import random
        entries = []
        
        for i, tag in enumerate(tags):
            selected_tags = [t for t in tags if random.random() < tag_assignment_rate]
            if not selected_tags:
                selected_tags = [tag]  # 确保至少有一个
            
            entry = cls.create(
                id=f"tag-{i}",
                content=f"记忆内容 {i+1}",
                tags=selected_tags,
                **kwargs,
            )
            entries.append(entry)
        
        return entries
    
    @classmethod
    def create_diverse(
        cls,
        count: int = 10,
        importance_range: tuple[float, float] = (0.1, 1.0),
        **kwargs,
    ) -> list[MemoryEntry]:
        """
        创建多样化的记忆
        
        包含不同的重要性、分类和标签组合。
        
        Args:
            count: 创建数量
            importance_range: 重要性范围
            **kwargs: 其他参数
            
        Returns:
            MemoryEntry 列表
        """
        import random
        
        categories = ["技术", "生活", "工作", "学习", "娱乐"]
        tag_pools = [
            ["AI", "编程"],
            ["健康", "运动"],
            ["会议", "项目"],
            ["读书", "课程"],
            ["游戏", "电影"],
        ]
        
        entries = []
        for i in range(count):
            importance = random.uniform(*importance_range)
            category = categories[i % len(categories)]
            tags = tag_pools[i % len(tag_pools)]
            
            entry = cls.create(
                id=f"div-{i}",
                content=f"多样化的测试记忆 {i+1}",
                category=category,
                tags=tags,
                importance=importance,
                **kwargs,
            )
            entries.append(entry)
        
        return entries
