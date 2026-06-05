"""
异步测试辅助工具

提供异步测试中常用的轮询、等待等辅助函数。
"""

import asyncio
import time
from typing import Optional, Callable, Awaitable, Any


class AsyncTestHelper:
    """异步测试辅助类"""
    
    @staticmethod
    async def wait_for(
        condition: Callable[[], Awaitable[bool]],
        timeout: float = 5.0,
        interval: float = 0.05,
        error_message: Optional[str] = None
    ) -> bool:
        """
        等待条件满足。
        
        Args:
            condition: 返回布尔值的异步函数
            timeout: 超时时间（秒）
            interval: 轮询间隔（秒）
            error_message: 超时时显示的错误消息
            
        Returns:
            True if condition met
            
        Raises:
            TimeoutError: 等待超时
        """
        start = time.time()
        last_error = None
        
        while time.time() - start < timeout:
            try:
                if await condition():
                    return True
            except Exception as e:
                last_error = e
            
            await asyncio.sleep(interval)
        
        msg = error_message or f"条件在 {timeout} 秒内未满足"
        if last_error:
            msg += f" (最后错误: {last_error})"
        raise TimeoutError(msg)
    
    @staticmethod
    async def retry_async(
        func: Callable[..., Awaitable[Any]],
        max_attempts: int = 3,
        delay: float = 0.1,
        exceptions: tuple = (Exception,)
    ) -> Any:
        """
        重试异步函数直到成功或达到最大次数。
        
        Args:
            func: 要重试的异步函数
            max_attempts: 最大尝试次数
            delay: 重试间隔（秒）
            exceptions: 要捕获的异常类型
            
        Returns:
            函数返回值
            
        Raises:
            最后一次尝试的异常
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


async def wait_for_condition(
    condition: Callable[[], Awaitable[bool]],
    timeout: float = 5.0,
    interval: float = 0.05
) -> bool:
    """
    等待条件满足的便捷函数。
    
    Args:
        condition: 返回布尔值的异步函数
        timeout: 超时时间（秒）
        interval: 轮询间隔（秒）
        
    Returns:
        True if condition met
        
    Raises:
        TimeoutError: 等待超时
    """
    return await AsyncTestHelper.wait_for(condition, timeout, interval)
