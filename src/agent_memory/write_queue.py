"""
AsyncWriteQueue — 异步批量写入队列，带优先级。
AgentMemory 的写入缓冲层。
"""
from __future__ import annotations
import asyncio
import time
from typing import Any, Callable, List, Optional, Tuple
from enum import IntEnum


class Priority(IntEnum):
    HIGH = 0     # 必须立即写入（如用户主动保存）
    NORMAL = 1   # 常规写入（hook 捕获）
    LOW = 2      # 批量后台写入（cron/fg 进程）


class AsyncWriteQueue:
    def __init__(self, flush_fn: Callable, max_batch: int = 20, interval_ms: int = 5000):
        self._flush_fn = flush_fn
        self._max_batch = max_batch
        self._interval = interval_ms / 1000
        self._queues: List[List[Tuple]] = [[], [], []]  # HIGH, NORMAL, LOW
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._last_flush = time.time()

    def push(self, item: Any, priority: Priority = Priority.NORMAL):
        self._queues[priority].append((time.time(), item))

    def push_batch(self, items: List[Any], priority: Priority = Priority.NORMAL):
        for item in items:
            self._queues[priority].append((time.time(), item))

    async def flush_now(self) -> List[Any]:
        items = []
        for q in self._queues:
            while q:
                items.append(q.pop(0)[1])
        if items:
            await self._flush_fn(items)
        return items

    def _drain_queue(self) -> List[Any]:
        items = []
        for q in self._queues:
            take = min(len(q), self._max_batch - len(items))
            for _ in range(take):
                items.append(q.pop(0)[1])
            if len(items) >= self._max_batch:
                break
        return items

    async def _loop(self):
        while self._running:
            items = self._drain_queue()
            if items or time.time() - self._last_flush >= 60:
                if items:
                    try:
                        await self._flush_fn(items)
                    except Exception:
                        pass
                self._last_flush = time.time()
            await asyncio.sleep(self._interval)

    def start(self):
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._loop())

    async def stop(self):
        self._running = False
        await self.flush_now()
        if self._task:
            self._task.cancel()
            self._task = None

    @property
    def size(self) -> int:
        return sum(len(q) for q in self._queues)
