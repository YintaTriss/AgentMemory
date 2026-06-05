"""
异步辅助工具

提供测试中使用的异步辅助函数。
"""

import asyncio
import time
from typing import Callable, Any, Optional, TypeVar


T = TypeVar("T")


async def wait_for(
    coro_or_func: Callable[..., Any],
    timeout: float = 5.0,
    poll_interval: float = 0.1,
    *args,
    **kwargs,
) -> Any:
    """
    等待协程或函数返回真值
    
    Args:
        coro_or_func: 协程或同步函数
        timeout: 超时时间（秒）
        poll_interval: 轮询间隔（秒）
        *args: 位置参数
        **kwargs: 关键字参数
        
    Returns:
        函数的返回值
        
    Raises:
        TimeoutError: 等待超时
    """
    start = time.time()
    
    while time.time() - start < timeout:
        if asyncio.iscoroutinefunction(coro_or_func):
            result = await coro_or_func(*args, **kwargs)
        else:
            result = coro_or_func(*args, **kwargs)
        
        if result:
            return result
        
        await asyncio.sleep(poll_interval)
    
    raise TimeoutError(
        f"wait_for timed out after {timeout}s"
    )


async def poll_until(
    coro_or_func: Callable[..., T],
    condition: Callable[[T], bool],
    timeout: float = 5.0,
    poll_interval: float = 0.1,
    *args,
    **kwargs,
) -> T:
    """
    轮询直到条件满足
    
    Args:
        coro_or_func: 协程或同步函数
        condition: 条件检查函数
        timeout: 超时时间（秒）
        poll_interval: 轮询间隔（秒）
        *args: 位置参数
        **kwargs: 关键字参数
        
    Returns:
        满足条件的返回值
        
    Raises:
        TimeoutError: 轮询超时
    """
    start = time.time()
    
    while time.time() - start < timeout:
        if asyncio.iscoroutinefunction(coro_or_func):
            result = await coro_or_func(*args, **kwargs)
        else:
            result = coro_or_func(*args, **kwargs)
        
        if condition(result):
            return result
        
        await asyncio.sleep(poll_interval)
    
    raise TimeoutError(
        f"poll_until timed out after {timeout}s. "
        f"Last result: {result}"
    )


async def retry_async(
    func: Callable[..., Any],
    max_attempts: int = 3,
    delay: float = 0.1,
    exceptions: tuple = (Exception,),
) -> Any:
    """
    异步函数重试装饰器/函数
    
    Args:
        func: 要重试的异步函数
        max_attempts: 最大尝试次数
        delay: 重试间隔（秒）
        exceptions: 要捕获的异常类型
        
    Returns:
        函数执行结果
        
    Raises:
        最后一次执行的异常
    """
    last_exception = None
    
    for attempt in range(max_attempts):
        try:
            return await func()
        except exceptions as e:
            last_exception = e
            if attempt < max_attempts - 1:
                await asyncio.sleep(delay)
    
    raise last_exception


async def gather_with_timeout(
    *coros,
    timeout: float = 5.0,
    return_exceptions: bool = False,
) -> list:
    """
    带超时的一组协程执行
    
    Args:
        *coros: 协程列表
        timeout: 超时时间（秒）
        return_exceptions: 是否返回异常而非抛出
        
    Returns:
        结果列表
    """
    try:
        return await asyncio.wait_for(
            asyncio.gather(*coros, return_exceptions=return_exceptions),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        if return_exceptions:
            return [TimeoutError(f"Task timed out after {timeout}s")] * len(coros)
        raise


async def run_concurrently(
    func: Callable[..., Any],
    items: list,
    max_concurrency: int = 10,
    timeout: float = 30.0,
) -> list:
    """
    并发运行函数
    
    使用信号量限制并发数。
    
    Args:
        func: 要执行的异步函数
        items: 输入项列表
        max_concurrency: 最大并发数
        timeout: 单项超时时间
        
    Returns:
        结果列表
    """
    semaphore = asyncio.Semaphore(max_concurrency)
    
    async def bounded_func(item):
        async with semaphore:
            return await asyncio.wait_for(func(item), timeout=timeout)
    
    return await asyncio.gather(*[bounded_func(item) for item in items])


async def wait_for_state(
    get_state: Callable[[], Any],
    expected_state: Any,
    timeout: float = 5.0,
    poll_interval: float = 0.1,
) -> None:
    """
    等待状态变为预期值
    
    Args:
        get_state: 获取状态的函数
        expected_state: 期望的状态值
        timeout: 超时时间
        poll_interval: 轮询间隔
    """
    start = time.time()
    
    while time.time() - start < timeout:
        state = get_state()
        if state == expected_state:
            return
        await asyncio.sleep(poll_interval)
    
    raise TimeoutError(
        f"State did not become {expected_state} within {timeout}s"
    )
