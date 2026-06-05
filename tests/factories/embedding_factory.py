"""
Embedding Factory - Embedding 工厂方法

提供创建测试用 Embedding 的工厂方法。
"""

from typing import Optional
import numpy as np


class EmbeddingFactory:
    """Embedding 工厂类"""
    
    @classmethod
    def create_vector(cls, dimensions: int = 128) -> list[float]:
        """创建随机归一化向量"""
        vec = np.random.randn(dimensions).astype(np.float32)
        norm = np.linalg.norm(vec)
        return (vec / norm).tolist()
    
    @classmethod
    def create_vectors(cls, count: int, dimensions: int = 128) -> list[list[float]]:
        """创建多个随机归一化向量"""
        return [cls.create_vector(dimensions) for _ in range(count)]
    
    @classmethod
    def create_similar_vectors(cls, base_vector: list[float], count: int = 3, noise: float = 0.1) -> list[list[float]]:
        """创建与基向量相似的向量（添加噪声）"""
        base = np.array(base_vector)
        vectors = []
        for _ in range(count):
            noise_vec = np.random.randn(len(base_vector)).astype(np.float32) * noise
            new_vec = base + noise_vec
            norm = np.linalg.norm(new_vec)
            vectors.append((new_vec / norm).tolist())
        return vectors
    
    @classmethod
    def create_orthogonal_vectors(cls, dimensions: int = 128, count: int = 2) -> list[list[float]]:
        """创建正交向量"""
        vectors = []
        for i in range(count):
            vec = np.zeros(dimensions, dtype=np.float32)
            vec[i] = 1.0
            vectors.append(vec.tolist())
        return vectors
    
    @classmethod
    def compute_similarity(cls, vec1: list[float], vec2: list[float]) -> float:
        """计算两个向量的余弦相似度"""
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        return float(np.dot(v1, v2))
    
    @classmethod
    def create_text_embedding_pair(cls, text: str, dimensions: int = 128) -> tuple[str, list[float]]:
        """创建文本-向量对"""
        return text, cls.create_vector(dimensions)
    
    @classmethod
    def create_bm25_texts(cls, count: int = 5) -> list[str]:
        """创建用于 BM25 测试的文本集合"""
        texts = [
            "机器学习是人工智能的一个分支",
            "深度学习使用神经网络进行特征学习",
            "自然语言处理研究人机交互",
            "计算机视觉处理图像和视频",
            "强化学习通过试错优化策略"
        ]
        return texts[:min(count, len(texts))]
