"""
断言辅助工具

提供常用的断言函数和带重试的断言。
"""

import asyncio
import math
from typing import Callable, Any, Optional


async def assert_with_retry(
    coro,
    condition: Callable[[Any], bool],
    max_attempts: int = 10,
    delay: float = 0.1,
    error_message: Optional[str] = None,
) -> Any:
    """
    带重试的异步断言
    
    等待异步操作的结果满足条件。
    
    Args:
        coro: 返回协程的函数或协程对象
        condition: 条件检查函数
        max_attempts: 最大重试次数
        delay: 重试间隔（秒）
        error_message: 失败时的错误消息
        
    Raises:
        AssertionError: 条件不满足
    """
    last_result = None
    
    for attempt in range(max_attempts):
        if asyncio.iscoroutine(coro):
            result = await coro
        else:
            result = await coro()
        
        last_result = result
        
        if condition(result):
            return result
        
        if attempt < max_attempts - 1:
            await asyncio.sleep(delay)
    
    raise AssertionError(
        error_message or f"Condition not met after {max_attempts} attempts. "
        f"Last result: {last_result}"
    )


def assert_vectors_equal(
    vec1: list[float],
    vec2: list[float],
    tolerance: float = 1e-6,
    msg: Optional[str] = None,
) -> None:
    """
    断言两个向量相等
    
    Args:
        vec1: 第一个向量
        vec2: 第二个向量
        tolerance: 允许的误差
        msg: 失败消息
        
    Raises:
        AssertionError: 向量不相等
    """
    assert len(vec1) == len(vec2), (
        msg or f"Vector length mismatch: {len(vec1)} vs {len(vec2)}"
    )
    
    for i, (v1, v2) in enumerate(zip(vec1, vec2)):
        assert abs(v1 - v2) <= tolerance, (
            msg or f"Vectors differ at index {i}: {v1} vs {v2}"
        )


def assert_vectors_close(
    vec1: list[float],
    vec2: list[float],
    cosine_threshold: float = 0.99,
    msg: Optional[str] = None,
) -> None:
    """
    断言两个向量相似（余弦相似度高）
    
    Args:
        vec1: 第一个向量
        vec2: 第二个向量
        cosine_threshold: 余弦相似度阈值
        msg: 失败消息
        
    Raises:
        AssertionError: 向量不相似
    """
    cosine_sim = _cosine_similarity(vec1, vec2)
    assert cosine_sim >= cosine_threshold, (
        msg or f"Cosine similarity {cosine_sim} below threshold {cosine_threshold}"
    )


def assert_scores_decreasing(
    scores: list[float],
    allow_equal: bool = True,
    msg: Optional[str] = None,
) -> None:
    """
    断言分数列表是递减的
    
    Args:
        scores: 分数列表
        allow_equal: 是否允许相等
        msg: 失败消息
        
    Raises:
        AssertionError: 分数不是递减的
    """
    for i in range(len(scores) - 1):
        if allow_equal:
            assert scores[i] >= scores[i + 1], (
                msg or f"Scores not decreasing at index {i}: "
                f"{scores[i]} < {scores[i + 1]}"
            )
        else:
            assert scores[i] > scores[i + 1], (
                msg or f"Scores not strictly decreasing at index {i}: "
                f"{scores[i]} <= {scores[i + 1]}"
            )


def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """计算余弦相似度"""
    dot_product = sum(v1 * v2 for v1, v2 in zip(vec1, vec2))
    mag1 = math.sqrt(sum(v * v for v in vec1))
    mag2 = math.sqrt(sum(v * v for v in vec2))
    
    if mag1 == 0 or mag2 == 0:
        return 0.0
    
    return dot_product / (mag1 * mag2)


def assert_search_results_valid(
    results: list,
    expected_min_count: int = 0,
    expected_max_count: Optional[int] = None,
    score_range: tuple[float, float] = (0.0, 1.0),
    msg: Optional[str] = None,
) -> None:
    """
    断言搜索结果有效
    
    Args:
        results: 搜索结果列表
        expected_min_count: 期望的最小结果数
        expected_max_count: 期望的最大结果数
        score_range: 分数范围 (min, max)
        msg: 失败消息
        
    Raises:
        AssertionError: 结果无效
    """
    assert len(results) >= expected_min_count, (
        msg or f"Result count {len(results)} below minimum {expected_min_count}"
    )
    
    if expected_max_count is not None:
        assert len(results) <= expected_max_count, (
            msg or f"Result count {len(results)} above maximum {expected_max_count}"
        )
    
    for i, result in enumerate(results):
        assert hasattr(result, 'id'), (
            msg or f"Result {i} missing 'id' attribute"
        )
        assert hasattr(result, 'score'), (
            msg or f"Result {i} missing 'score' attribute"
        )
        assert score_range[0] <= result.score <= score_range[1], (
            msg or f"Result {i} score {result.score} outside range {score_range}"
        )


def assert_memory_entries_valid(
    entries: list,
    expected_min_count: int = 0,
    check_vectors: bool = False,
    msg: Optional[str] = None,
) -> None:
    """
    断言记忆条目有效
    
    Args:
        entries: 记忆条目列表
        expected_min_count: 期望的最小条目数
        check_vectors: 是否检查向量
        msg: 失败消息
        
    Raises:
        AssertionError: 条目无效
    """
    assert len(entries) >= expected_min_count, (
        msg or f"Entry count {len(entries)} below minimum {expected_min_count}"
    )
    
    for i, entry in enumerate(entries):
        assert hasattr(entry, 'id'), (
            msg or f"Entry {i} missing 'id' attribute"
        )
        assert hasattr(entry, 'content'), (
            msg or f"Entry {i} missing 'content' attribute"
        )
        assert hasattr(entry, 'metadata'), (
            msg or f"Entry {i} missing 'metadata' attribute"
        )
        
        if check_vectors:
            assert entry.vector is not None, (
                msg or f"Entry {i} missing vector"
            )
            assert len(entry.vector) > 0, (
                msg or f"Entry {i} has empty vector"
            )
