"""
EmbeddingStateMachine - Embedding 状态机模块
Version: v2.0
"""

import asyncio
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import aiofiles


EMBEDDING_STATE_FILE = ".embedding_state.json"
MAX_RETRY_COUNT = 3
EMBEDDING_QUEUE_FILE = ".embedding_queue.jsonl"
EMBEDDING_FAILURES_FILE = ".embedding_failures.jsonl"


class EmbeddingState(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    PERMANENT_FAILURE = "permanent_failure"


@dataclass
class EmbeddingTask:
    """§5.3 EmbeddingTask — 待处理任务"""
    mem_id: str
    text: str
    state: str
    retry_count: int = 0
    last_error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    worker_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "mem_id": self.mem_id, "text": self.text, "state": self.state,
            "retry_count": self.retry_count, "last_error": self.last_error,
            "created_at": self.created_at, "updated_at": self.updated_at, "worker_id": self.worker_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EmbeddingTask":
        return cls(
            mem_id=data["mem_id"], text=data["text"], state=data["state"],
            retry_count=data.get("retry_count", 0), last_error=data.get("last_error"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            worker_id=data.get("worker_id"),
        )


@dataclass
class EmbeddingStateEntry:
    memory_id: str
    state: str
    retry_count: int = 0
    error_message: Optional[str] = None
    model: Optional[str] = None
    dimensions: Optional[int] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        return {
            "memory_id": self.memory_id, "state": self.state,
            "retry_count": self.retry_count, "error_message": self.error_message,
            "model": self.model, "dimensions": self.dimensions,
            "created_at": self.created_at, "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "EmbeddingStateEntry":
        return cls(
            memory_id=data["memory_id"], state=data["state"],
            retry_count=data.get("retry_count", 0), error_message=data.get("error_message"),
            model=data.get("model"), dimensions=data.get("dimensions"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
        )


class EmbeddingStateError(Exception): pass
class InvalidStateTransitionError(EmbeddingStateError): pass


class EmbeddingStateMachine:
    def __init__(
        self,
        root_dir,
        queue_max_size: int = 10000,
        max_retries: int = 3,
        timeout_seconds: float = 60.0,
    ):
        self.root_dir = Path(root_dir).resolve()
        self.state_file = self.root_dir / EMBEDDING_STATE_FILE
        self.queue_file = self.root_dir / EMBEDDING_QUEUE_FILE
        self.failures_file = self.root_dir / EMBEDDING_FAILURES_FILE
        self._queue_max_size = queue_max_size
        self._max_retries = max_retries
        self._timeout_seconds = timeout_seconds
        self._lock = asyncio.Lock()
        self._states: dict = {}
        self._vectors: dict = {}
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=queue_max_size)
        self._worker_task: Optional[asyncio.Task] = None

    async def init(self):
        self.root_dir.mkdir(parents=True, exist_ok=True)
        if self.state_file.exists():
            async with aiofiles.open(self.state_file, "r", encoding="utf-8") as f:
                data = json.loads(await f.read())
                self._load_from_dict(data)

    def _load_from_dict(self, data: dict):
        self._states.clear()
        for mid, state_data in data.get("states", {}).items():
            self._states[mid] = EmbeddingStateEntry.from_dict(state_data)
        self._vectors.clear()
        self._vectors = data.get("vectors", {})

    def _to_dict(self) -> dict:
        return {
            "states": {mid: entry.to_dict() for mid, entry in self._states.items()},
            "vectors": self._vectors,
        }

    async def _save_state(self):
        async with self._lock:
            tmp = self.state_file.with_suffix('.tmp')
            async with aiofiles.open(tmp, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(self._to_dict(), ensure_ascii=False, indent=2))
            tmp.replace(self.state_file)

    def _is_valid_transition(self, from_state: Optional[EmbeddingState], to_state: EmbeddingState) -> bool:
        if from_state is None:
            return to_state == EmbeddingState.PENDING
        valid = {
            EmbeddingState.PENDING: {EmbeddingState.GENERATING},
            EmbeddingState.GENERATING: {EmbeddingState.COMPLETED, EmbeddingState.FAILED},
            EmbeddingState.FAILED: {EmbeddingState.GENERATING, EmbeddingState.PERMANENT_FAILURE},
            EmbeddingState.COMPLETED: set(),
            EmbeddingState.PERMANENT_FAILURE: set(),
        }
        return to_state in valid.get(from_state, set())

    async def set_state(self, memory_id: str, state: EmbeddingState, error_message: Optional[str] = None,
                       model: Optional[str] = None, dimensions: Optional[int] = None) -> EmbeddingStateEntry:
        async with self._lock:
            current = self._states.get(memory_id)
            from_state = EmbeddingState(current.state) if current else None
            
            if not self._is_valid_transition(from_state, state):
                raise InvalidStateTransitionError(f"Invalid transition from {from_state} to {state}")
            
            if state == EmbeddingState.FAILED and current:
                retry_count = current.retry_count + 1
                if retry_count >= MAX_RETRY_COUNT:
                    state = EmbeddingState.PERMANENT_FAILURE
            else:
                retry_count = current.retry_count if current else 0
            
            entry = EmbeddingStateEntry(
                memory_id=memory_id, state=state.value, retry_count=retry_count,
                error_message=error_message, model=model, dimensions=dimensions,
                created_at=current.created_at if current else datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
            )
            self._states[memory_id] = entry
            await self._save_state()
            return entry

    async def get_state(self, memory_id: str) -> Optional[EmbeddingStateEntry]:
        entry = self._states.get(memory_id)
        if entry and entry.state == EmbeddingState.PERMANENT_FAILURE.value and entry.retry_count < MAX_RETRY_COUNT:
            entry.retry_count = MAX_RETRY_COUNT
        return entry

    async def list_pending(self) -> list:
        return [e for e in self._states.values() if e.state == EmbeddingState.PENDING.value]

    async def list_failed(self) -> list:
        return [e for e in self._states.values() if e.state in (EmbeddingState.FAILED.value, EmbeddingState.PERMANENT_FAILURE.value)]

    async def list_completed(self) -> list:
        return [e for e in self._states.values() if e.state == EmbeddingState.COMPLETED.value]

    async def save_vector(self, memory_id: str, vector: list):
        async with self._lock:
            self._vectors[memory_id] = vector
            await self._save_state()

    async def get_vector(self, memory_id: str) -> Optional[list]:
        return self._vectors.get(memory_id)

    async def remove_state(self, memory_id: str):
        async with self._lock:
            if memory_id in self._states:
                del self._states[memory_id]
            if memory_id in self._vectors:
                del self._vectors[memory_id]
            await self._save_state()

    # ============================================================================
    # §5.3 EmbeddingStateMachine 接口契约实现
    # ============================================================================

    async def enqueue(self, mem_id: str, text: str) -> EmbeddingTask:
        """§5.3 enqueue — 加入处理队列"""
        task = EmbeddingTask(
            mem_id=mem_id, text=text,
            state=EmbeddingState.PENDING.value,
        )
        # 持久化到队列文件
        async with aiofiles.open(self.queue_file, 'a', encoding='utf-8') as f:
            await f.write(json.dumps(task.to_dict(), ensure_ascii=False) + '\n')
        # 入内存队列
        await self._queue.put(task)
        # 设置初始状态
        entry = EmbeddingStateEntry(
            memory_id=mem_id,
            state=EmbeddingState.PENDING.value,
        )
        self._states[mem_id] = entry
        await self._save_state()
        return task

    async def worker_loop(self, embedder, store) -> None:
        """§5.3 worker_loop — 后台 worker 循环

        Args:
            embedder: Embedder provider
            store: VectorStore provider
        """
        import os
        worker_id = f"worker-{os.getpid()}-{id(asyncio.current_task())}"
        while True:
            try:
                task: EmbeddingTask = await asyncio.wait_for(
                    self._queue.get(), timeout=self._timeout_seconds
                )
            except asyncio.TimeoutError:
                continue

            task.worker_id = worker_id
            task.state = EmbeddingState.GENERATING.value
            task.updated_at = datetime.now().isoformat()

            # 更新状态
            entry = EmbeddingStateEntry(
                memory_id=task.mem_id,
                state=EmbeddingState.GENERATING.value,
                retry_count=task.retry_count,
            )
            self._states[task.mem_id] = entry
            await self._save_state()

            try:
                # 调用 embedder
                vector = await embedder.embed(task.text)
                # 写入向量存储
                await store.upsert(task.mem_id, vector, {})
                await store.persist()
                # 更新为完成
                task.state = EmbeddingState.COMPLETED.value
                entry = EmbeddingStateEntry(
                    memory_id=task.mem_id,
                    state=EmbeddingState.COMPLETED.value,
                    retry_count=task.retry_count,
                    model=getattr(embedder, 'model', None),
                    dimensions=len(vector) if vector else None,
                )
                self._states[task.mem_id] = entry
                self._vectors[task.mem_id] = vector
            except Exception as e:
                task.retry_count += 1
                task.last_error = str(e)
                task.updated_at = datetime.now().isoformat()

                if task.retry_count >= self._max_retries:
                    task.state = EmbeddingState.PERMANENT_FAILURE.value
                    entry = EmbeddingStateEntry(
                        memory_id=task.mem_id,
                        state=EmbeddingState.PERMANENT_FAILURE.value,
                        retry_count=task.retry_count,
                        error_message=str(e),
                    )
                    self._states[task.mem_id] = entry
                    # 写入 permanent failure 文件
                    async with aiofiles.open(self.failures_file, 'a', encoding='utf-8') as f:
                        await f.write(json.dumps(task.to_dict(), ensure_ascii=False) + '\n')
                else:
                    task.state = EmbeddingState.FAILED.value
                    entry = EmbeddingStateEntry(
                        memory_id=task.mem_id,
                        state=EmbeddingState.FAILED.value,
                        retry_count=task.retry_count,
                        error_message=str(e),
                    )
                    self._states[task.mem_id] = entry
                    # 重新入队
                    await self._queue.put(task)

            await self._save_state()

    def list_by_state(self, state: EmbeddingState) -> list[EmbeddingStateEntry]:
        """§5.3 list_by_state — 按状态列出记忆"""
        state_value = state.value if isinstance(state, EmbeddingState) else state
        return [
            e for e in self._states.values()
            if e.state == state_value
        ]

    def stats(self) -> dict[str, int]:
        """§5.3 stats — 统计各状态数量"""
        counts: dict[str, int] = {s.value: 0 for s in EmbeddingState}
        for entry in self._states.values():
            counts[entry.state] = counts.get(entry.state, 0) + 1
        return counts
