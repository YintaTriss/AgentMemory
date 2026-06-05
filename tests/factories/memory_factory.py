"""
Memory Factory - 记忆工厂方法

提供创建测试用记忆对象的工厂方法。
"""

from typing import Optional
from datetime import datetime
from dataclasses import dataclass, field
import hashlib


class MemoryFactory:
    """记忆工厂类"""
    
    _counter = 0
    
    @classmethod
    def reset_counter(cls):
        """重置计数器"""
        cls._counter = 0
    
    @classmethod
    def create_memory_id(cls) -> str:
        """生成唯一的记忆 ID"""
        cls._counter += 1
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        return f"mem_{timestamp}_{cls._counter}"
    
    @classmethod
    def create_content(
        cls,
        title: str = "测试记忆",
        body: str = "这是测试记忆的内容。"
    ) -> str:
        """创建记忆内容（Markdown 格式）"""
        return f"# {title}\n\n{body}"
    
    @classmethod
    def create_tags(cls, count: int = 3) -> list[str]:
        """创建随机 tags"""
        base_tags = ["重要", "AI", "个人", "项目", "工作", "学习", "测试", "临时"]
        import random
        return random.sample(base_tags, min(count, len(base_tags)))
    
    @classmethod
    def create_metadata(
        cls,
        source: str = "test",
        category: str = "test",
        custom: Optional[dict] = None
    ) -> dict:
        """创建记忆元数据"""
        metadata = {
            "source": source,
            "category": category,
            "created_by": "MemoryFactory"
        }
        if custom:
            metadata.update(custom)
        return metadata
    
    @classmethod
    def create_importance(cls) -> float:
        """创建随机重要性分数"""
        import random
        return round(random.uniform(0.1, 1.0), 2)
    
    @classmethod
    def create_vector(cls, dimensions: int = 128) -> list[float]:
        """创建随机向量"""
        import numpy as np
        vec = np.random.randn(dimensions).astype(np.float32)
        norm = np.linalg.norm(vec)
        return (vec / norm).tolist()
    
    @classmethod
    def create_category_path(cls, depth: int = 2) -> str:
        """创建随机分类路径"""
        import random
        categories = ["A.项目", "B.个人", "C.临时"]
        parts = [random.choice(categories)]
        
        sub_categories = {
            "A.项目": ["石榴籽", "AgentMemory", "测试项目"],
            "B.个人": ["日记", "笔记", "收藏"],
            "C.临时": ["草稿", "待整理"]
        }
        
        for _ in range(depth - 1):
            parent = parts[-1]
            children = sub_categories.get(parent, ["子分类"])
            parts.append(random.choice(children))
        
        return "/".join(parts)


@dataclass
class MemoryFactoryResult:
    """工厂方法创建结果的容器"""
    memory_id: str
    content: str
    tags: list[str]
    metadata: dict
    importance: float
    category_path: str
    vector: list[float]
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "memory_id": self.memory_id,
            "content": self.content,
            "tags": self.tags,
            "metadata": self.metadata,
            "importance": self.importance,
            "category_path": self.category_path,
            "vector": self.vector
        }
