"""
测试断言辅助工具

提供向量相似度、文件存在等自定义断言。
"""

import os
import numpy as np
from typing import List, Optional


def assert_vectors_similar(
    vec1: List[float],
    vec2: List[float],
    threshold: float = 0.95,
    message: Optional[str] = None
) -> None:
    """
    断言两个向量相似（余弦相似度 >= threshold）。
    
    Args:
        vec1: 第一个向量
        vec2: 第二个向量
        threshold: 相似度阈值，默认 0.95
        message: 自定义错误消息
        
    Raises:
        AssertionError: 向量不相似
    """
    v1 = np.array(vec1)
    v2 = np.array(vec2)
    
    # 归一化
    v1_norm = v1 / np.linalg.norm(v1)
    v2_norm = v2 / np.linalg.norm(v2)
    
    similarity = float(np.dot(v1_norm, v2_norm))
    
    msg = message or f"向量相似度 {similarity:.4f} < 阈值 {threshold}"
    assert similarity >= threshold, msg


def assert_vectors_equal(
    vec1: List[float],
    vec2: List[float],
    tolerance: float = 1e-6,
    message: Optional[str] = None
) -> None:
    """
    断言两个向量相等（在容差范围内）。
    
    Args:
        vec1: 第一个向量
        vec2: 第二个向量
        tolerance: 容差，默认 1e-6
        message: 自定义错误消息
        
    Raises:
        AssertionError: 向量不相等
    """
    v1 = np.array(vec1)
    v2 = np.array(vec2)
    
    diff = np.abs(v1 - v2)
    max_diff = float(np.max(diff))
    
    msg = message or f"向量差异 {max_diff:.6f} > 容差 {tolerance}"
    assert max_diff <= tolerance, msg


def assert_memory_files_exist(
    base_dir: str,
    memory_id: str,
    check_content: bool = True,
    check_vector: bool = True,
    check_meta: bool = True
) -> None:
    """
    断言记忆文件三件套存在。
    
    Args:
        base_dir: 基础目录
        memory_id: 记忆 ID
        check_content: 是否检查 .md 文件
        check_vector: 是否检查 .vec.json 文件
        check_meta: 是否检查 .meta.json 文件
        
    Raises:
        AssertionError: 文件不存在
    """
    errors = []
    
    if check_content:
        content_path = os.path.join(base_dir, f"{memory_id}.md")
        if not os.path.exists(content_path):
            errors.append(f"内容文件不存在: {content_path}")
    
    if check_vector:
        vector_path = os.path.join(base_dir, f"{memory_id}.vec.json")
        if not os.path.exists(vector_path):
            errors.append(f"向量文件不存在: {vector_path}")
    
    if check_meta:
        meta_path = os.path.join(base_dir, f"{memory_id}.meta.json")
        if not os.path.exists(meta_path):
            errors.append(f"元数据文件不存在: {meta_path}")
    
    assert not errors, "\n".join(errors)


def assert_memory_files_not_exist(
    base_dir: str,
    memory_id: str
) -> None:
    """
    断言记忆文件三件套不存在。
    
    Args:
        base_dir: 基础目录
        memory_id: 记忆 ID
        
    Raises:
        AssertionError: 文件存在
    """
    content_path = os.path.join(base_dir, f"{memory_id}.md")
    vector_path = os.path.join(base_dir, f"{memory_id}.vec.json")
    meta_path = os.path.join(base_dir, f"{memory_id}.meta.json")
    
    for path in [content_path, vector_path, meta_path]:
        assert not os.path.exists(path), f"文件意外存在: {path}"


def assert_valid_vector(
    vec: List[float],
    expected_dimensions: Optional[int] = None,
    normalized: bool = True
) -> None:
    """
    断言向量格式正确。
    
    Args:
        vec: 要检查的向量
        expected_dimensions: 期望的维度
        normalized: 是否检查归一化
        
    Raises:
        AssertionError: 向量格式不正确
    """
    assert isinstance(vec, list), "向量必须是 list 类型"
    assert len(vec) > 0, "向量不能为空"
    
    if expected_dimensions is not None:
        assert len(vec) == expected_dimensions, \
            f"向量维度 {len(vec)} != 期望维度 {expected_dimensions}"
    
    for i, val in enumerate(vec):
        assert isinstance(val, (int, float)), f"向量元素 {i} 类型错误: {type(val)}"
        assert -1.0 <= val <= 1.0, f"向量元素 {i} 超出范围: {val}"
    
    if normalized:
        norm = float(np.linalg.norm(vec))
        assert abs(norm - 1.0) < 1e-6, f"向量未归一化: 范数 = {norm}"
