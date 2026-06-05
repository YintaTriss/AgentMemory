"""
Embedding Worker - 后台异步 Embedding 生成器

遵循 v0.5 架构：
- 写入不阻塞：异步生成 embedding，立即返回
- 状态机：pending→generating→completed/failed→permanent_failure
- 重试机制：失败自动重试，最多 3 次

核心功能：
- 后台队列处理 embedding 任务
- 状态持久化到 .vec.json 文件
- 失败追踪和永久失败标记
"""

import asyncio
import json
import time
import uuid
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Optional, Callable, Awaitable
from pathlib import Path

from .protocols import EmbedderProtocol, SearchResult
from .vectorstore_provider import USearchVectorStore


# ============================================================================
# Embedding 状态机
# ============================================================================

class EmbeddingState(str, Enum):
    """Embedding 状态枚举"""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    PERMANENT_FAILURE = "permanent_failure"


@dataclass
class EmbeddingTask:
    """Embedding 任务"""
    task_id: str
    memory_id: str
    content: str
    category_path: str
    tags: list[str] = field(default_factory=list)
    state: EmbeddingState = EmbeddingState.PENDING
    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    
    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "memory_id": self.memory_id,
            "content": self.content,
            "category_path": self.category_path,
            "tags": self.tags,
            "state": self.state.value,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "error_message": self.error_message,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "EmbeddingTask":
        data = data.copy()
        data["state"] = EmbeddingState(data.get("state", "pending"))
        return cls(**data)


@dataclass
class EmbeddingStats:
    """Embedding 统计信息"""
    total: int = 0
    pending: int = 0
    generating: int = 0
    completed: int = 0
    failed: int = 0
    permanent_failure: int = 0
    success_rate: float = 0.0
    avg_processing_time: float = 0.0


class EmbeddingWorker:
    """
    后台异步 Embedding Worker
    
    Example:
        >>> worker = EmbeddingWorker(embedder, vector_store, "./data")
        >>> task_id = await worker.submit("mem_xxx", "content", "A.项目")
        >>> await worker.start()
    """
    
    def __init__(
        self,
        embedder: EmbedderProtocol,
        vector_store: USearchVectorStore,
        root_dir: str | Path,
        max_concurrent: int = 5,
        poll_interval: float = 1.0,
        on_task_complete: Optional[Callable[[EmbeddingTask], Awaitable[None]]] = None,
        on_task_fail: Optional[Callable[[EmbeddingTask], Awaitable[None]]] = None,
    ):
        self.embedder = embedder
        self.vector_store = vector_store
        self.root_dir = Path(root_dir)
        self.max_concurrent = max_concurrent
        self.poll_interval = poll_interval
        self.on_task_complete = on_task_complete
        self.on_task_fail = on_task_fail
        self._pending_tasks: asyncio.Queue[str] = asyncio.Queue()
        self._tasks: dict[str, EmbeddingTask] = {}
        self._stats = EmbeddingStats()
        self._state_file = self.root_dir / ".embedding_state.json"
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._semaphore = asyncio.Semaphore(max_concurrent)
    
    async def init(self) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)
        await self._load_state()
    
    async def submit(
        self,
        memory_id: str,
        content: str,
        category_path: str,
        tags: list[str] | None = None,
    ) -> str:
        task_id = str(uuid.uuid4())
        task = EmbeddingTask(
            task_id=task_id,
            memory_id=memory_id,
            content=content,
            category_path=category_path,
            tags=tags or [],
        )
        self._tasks[task_id] = task
        await self._pending_tasks.put(task_id)
        await self._save_state()
        return task_id
    
    async def submit_batch(self, items: list[dict]) -> list[str]:
        task_ids = []
        for item in items:
            task_id = await self.submit(
                memory_id=item["memory_id"],
                content=item["content"],
                category_path=item.get("category_path", ""),
                tags=item.get("tags", []),
            )
            task_ids.append(task_id)
        return task_ids
    
    async def _process_task(self, task_id: str) -> None:
        async with self._semaphore:
            task = self._tasks.get(task_id)
            if not task:
                return
            
            task.state = EmbeddingState.GENERATING
            task.updated_at = time.time()
            await self._save_state()
            
            try:
                vector = await self.embedder.embed_single(task.content)
                await self.vector_store.upsert(
                    ids=[task.memory_id],
                    vectors=[vector],
                    payloads=[{
                        "content": task.content,
                        "category_path": task.category_path,
                        "tags": task.tags,
                        "task_id": task_id,
                    }],
                )
                task.state = EmbeddingState.COMPLETED
                task.completed_at = time.time()
                task.updated_at = time.time()
                task.error_message = None
                await self._save_state()
                self._update_stats()
                if self.on_task_complete:
                    await self.on_task_complete(task)
            except Exception as e:
                task.retry_count += 1
                task.error_message = str(e)
                task.updated_at = time.time()
                if task.retry_count >= task.max_retries:
                    task.state = EmbeddingState.PERMANENT_FAILURE
                else:
                    task.state = EmbeddingState.FAILED
                    await self._pending_tasks.put(task_id)
                await self._save_state()
                self._update_stats()
                if self.on_task_fail and task.state == EmbeddingState.PERMANENT_FAILURE:
                    await self.on_task_fail(task)
    
    async def _worker_loop(self) -> None:
        while self._running:
            try:
                try:
                    task_id = await asyncio.wait_for(
                        self._pending_tasks.get(),
                        timeout=self.poll_interval
                    )
                except asyncio.TimeoutError:
                    continue
                asyncio.create_task(self._process_task(task_id))
            except Exception as e:
                print(f"[EmbeddingWorker] Error: {e}")
                await asyncio.sleep(1)
    
    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._shutdown_event.clear()
        workers = [asyncio.create_task(self._worker_loop()) for _ in range(self.max_concurrent)]
        await self._shutdown_event.wait()
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
    
    async def stop(self) -> None:
        self._running = False
        self._shutdown_event.set()
    
    async def _load_state(self) -> None:
        if not self._state_file.exists():
            return
        try:
            with open(self._state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            tasks_data = data.get("tasks", {})
            for task_id, task_data in tasks_data.items():
                self._ta
