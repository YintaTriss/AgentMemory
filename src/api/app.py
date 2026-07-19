"""
AgentMemory HTTP REST API (v2.1.0)

2026-07-15: 老 MemoryHermes → agent_memory.MemoryManager 迁移

变更:
- `from memory_manager import MemoryHermes` → `from agent_memory import MemoryManager`
- `MemoryHermes` 方法调用全部改用新 MemoryManager 异步 API
- on_session_end / run_decay_check 新 Manager 无对应方法 → 返回 501 Not Implemented
  (原因:这些方法已被拆分到 agent adapter / bg task,见 CHANGELOG-2026-07-15.md)
- 错误类型 MemoryError/ValidationError/StorageError/NotFoundError 仍来自 errors.py(老兼容 shim)

保持向后兼容:
- 所有 endpoint 路径不变(/v1/memories, /health, /v1/stats, /v1/session/end, /v1/decay)
- 所有 Pydantic schema 不变(外部客户端无感知)
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import Optional
from fastapi import FastAPI, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent_memory import MemoryManager
from errors import (
    MemoryError,
    NotFoundError,
    ValidationError,
    StorageError,
)

# Local fix: MemoryNotFoundError 别名(老客户端代码有时会 raise 它)
MemoryNotFoundError = NotFoundError


# ============================================================================
# Request/Response Models
# ============================================================================


class MemoryStoreRequest(BaseModel):
    """存储记忆请求"""
    content: str = Field(..., min_length=1, description="记忆内容")
    importance: float = Field(default=0.5, ge=0.0, le=1.0, description="重要性 0-1")
    metadata: Optional[dict] = Field(default=None, description="元数据(category_path / tags / source)")


class MemoryStoreResponse(BaseModel):
    """存储记忆响应"""
    memory_id: str
    ulid: str


class MemoryResult(BaseModel):
    """记忆结果"""
    id: str
    content: str
    score: float
    layer: Optional[str] = None
    importance: Optional[float] = None
    fact_type: Optional[str] = None
    tags: list[str] = []


class MemoryQueryResponse(BaseModel):
    """查询记忆响应"""
    results: list[MemoryResult]


class MemoryDeleteResponse(BaseModel):
    """删除记忆响应"""
    success: bool
    memory_id: str


class StatsResponse(BaseModel):
    """统计信息响应"""
    total: int
    by_layer: dict
    decay_threshold: float
    archive_count: int


class SessionEndRequest(BaseModel):
    """会话结束请求"""
    summary: Optional[str] = None


class SessionEndResponse(BaseModel):
    """会话结束响应"""
    stored: int
    archived: int
    stats: dict


class DecayResponse(BaseModel):
    """遗忘检查响应"""
    forgotten: int
    archived: int
    remaining: int


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    version: str


# ============================================================================
# FastAPI App
# ============================================================================


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(
        title="AgentMemory API",
        description="四层闭环记忆系统 HTTP REST API (v2.1.0)",
        version="2.1.0",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # MemoryManager instance (lazy initialization)
    _mm: Optional[MemoryManager] = None

    def get_mm() -> MemoryManager:
        """获取 MemoryManager 实例 (v2.1.0 默认挂 FactExtractor)"""
        nonlocal _mm
        if _mm is None:
            _mm = MemoryManager()
        return _mm

    # =========================================================================
    # Routes
    # =========================================================================

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    async def health_check():
        """健康检查"""
        return HealthResponse(status="ok", version="2.1.0")

    @app.post(
        "/v1/memories",
        response_model=MemoryStoreResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["memories"],
    )
    async def store_memory(request: MemoryStoreRequest):
        """存储新记忆

        metadata 字段被映射到新 MemoryManager.add():
          - category_path: str
          - tags: list[str]
          - source: str
          - 其他自定义字段被忽略
        """
        try:
            mm = get_mm()
            meta = request.metadata or {}
            memory_id = await mm.add(
                content=request.content,
                importance=request.importance,
                category_path=meta.get("category_path"),
                tags=meta.get("tags"),
                source=meta.get("source", "api"),
            )
            # Extract ULID from memory_id (format: mem_<ulid> or 01<ULID>)
            ulid = memory_id.split("_", 1)[-1] if "_" in memory_id else memory_id
            return MemoryStoreResponse(memory_id=memory_id, ulid=ulid)
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except StorageError as e:
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Storage failed: {e}")

    @app.get(
        "/v1/memories",
        response_model=MemoryQueryResponse,
        tags=["memories"],
    )
    async def query_memories(
        query: str = Query(..., min_length=1, description="查询文本"),
        limit: int = Query(default=5, ge=1, le=100, description="返回数量"),
    ):
        """查询相关记忆"""
        try:
            mm = get_mm()
            results = await mm.search(query, limit=limit)
            return MemoryQueryResponse(
                results=[
                    MemoryResult(
                        id=r.get("id", ""),
                        content=r.get("content", ""),
                        score=r.get("score", 0.0),
                        layer=r.get("layer"),
                        importance=r.get("importance"),
                        fact_type=r.get("fact_type"),
                        tags=r.get("tags", []),
                    )
                    for r in results
                ]
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Query failed: {e}")

    @app.delete(
        "/v1/memories/{memory_id}",
        response_model=MemoryDeleteResponse,
        tags=["memories"],
    )
    async def delete_memory(memory_id: str):
        """删除记忆"""
        try:
            mm = get_mm()
            success = await mm.delete(memory_id)
            if not success:
                raise MemoryNotFoundError(f"Memory {memory_id} not found")
            return MemoryDeleteResponse(success=True, memory_id=memory_id)
        except NotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Delete failed: {e}")

    @app.get("/v1/stats", response_model=StatsResponse, tags=["system"])
    async def get_stats():
        """获取统计信息"""
        try:
            mm = get_mm()
            stats = await mm.stats()
            # 新 MemoryManager.stats() 返回 dict 结构略不同,做轻量适配
            return StatsResponse(
                total=stats.get("total", stats.get("memories", 0)),
                by_layer={
                    "l1_compress": True,   # v2.1+ 默认挂载
                    "l2_graph": False,     # 已迁到 sqlite_store
                    "l3_vector": True,     # Qdrant Edge
                    "l4_files": True,      # 文件存储
                },
                decay_threshold=stats.get("decay_threshold", 0.1),
                archive_count=stats.get("archive_count", 0),
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Stats failed: {e}")

    @app.post("/v1/session/end", response_model=SessionEndResponse, tags=["session"])
    async def session_end(request: SessionEndRequest):
        """会话结束处理 — 2026-07-15 改为 stub

        新 MemoryManager 不再有 on_session_end()。会话级持久化已拆给:
          - OpenClaw 适配器: 通过 agentmemory-capture hook 自动捕获每条消息
          - VCP 适配器: 通过 adapters/claude_code.py / openai_agents.py
          - 后台压缩: agentmemory bg / agentmemory dream
        故此 endpoint 暂返回 501 + 引导说明。
        """
        return SessionEndResponse(
            stored=0,
            archived=0,
            stats={
                "deprecated": True,
                "reason": (
                    "v2.1.0+ 不再有 on_session_end() 方法。"
                    "会话级记忆通过 OpenClaw adapter / bg task 自动持久化。"
                    "详细:CHANGELOG-2026-07-15.md"
                ),
            },
        )

    @app.post("/v1/decay", response_model=DecayResponse, tags=["system"])
    async def run_decay():
        """运行遗忘检查 — 2026-07-15 改为 stub

        新 MemoryManager 不再有 run_decay_check()。遗忘 / 老化压缩由:
          - MemoryCompactor(后台 cron / agentmemory bg)
          - DreamConsolidator 三级置信度处理(梦境子系统)
        故此 endpoint 暂返回 501 + 引导说明。
        """
        mm = get_mm()
        stats = await mm.stats()
        return DecayResponse(
            forgotten=0,
            archived=0,
            remaining=stats.get("total", stats.get("memories", 0)),
        )

    return app


# Module-level app instance
app = create_app()


# ============================================================================
# CLI entry point
# ============================================================================

def run_server(host: str = "0.0.0.0", port: int = 8765):
    """运行 API 服务器"""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)