"""
AgentMemory Web Dashboard (v2.1.0)

2026-07-15: 老 MemoryHermes → agent_memory.MemoryManager 迁移

变更:
- `from src.memory_manager import MemoryHermes` → `from agent_memory import MemoryManager`
- list_memories: 用 await mm.list() 替代 mh.vector.memories 直接访问
- delete_memory: await mm.delete(mid)
- list_entities/list_relations: 新架构下 entity/relation 由 SQLiteStore 管理
  MemoryManager 未暴露此 API → 暂返回空 list + deprecation notice
- prefetch: 改用 await mm.compress_for_context(...)
- get_stats: await mm.stats()

保持向后兼容:
- 所有 endpoint 路径不变
- 所有 Pydantic schema 不变
"""

import asyncio
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent_memory import MemoryManager

try:
    from errors import (
        MemoryError,
        NotFoundError,
        ValidationError,
        ConfigError,
        ProviderError,
        StorageError,
    )
except ImportError:
    class MemoryError(Exception):
        pass
    class NotFoundError(MemoryError):
        pass
    class ValidationError(MemoryError):
        pass
    class ConfigError(MemoryError):
        pass
    class ProviderError(MemoryError):
        pass
    class StorageError(MemoryError):
        pass


# ============================================================================
# Pydantic Request/Response Models
# ============================================================================

class PrefetchRequest(BaseModel):
    """预取请求"""
    query: str = Field(..., description="查询文本")


class MemoryResponse(BaseModel):
    """记忆响应"""
    id: str
    content: str
    importance: float
    created_at: str
    schema_version: int = 1
    metadata: Optional[dict] = None
    tags: Optional[list] = None
    fact_type: Optional[str] = None
    score: Optional[float] = None


class MemoryListResponse(BaseModel):
    """记忆列表响应（分页）"""
    items: list[MemoryResponse]
    total: int
    page: int
    page_size: int
    pages: int


class EntityResponse(BaseModel):
    """实体响应"""
    id: str
    name: str
    type: str
    attributes: dict = {}


class RelationResponse(BaseModel):
    """关系响应"""
    id: str
    source: str
    target: str
    type: str
    weight: float = 1.0


class GraphEntitiesResponse(BaseModel):
    """图谱实体列表响应"""
    items: list[EntityResponse]
    total: int
    deprecated: bool = False
    note: Optional[str] = None


class GraphRelationsResponse(BaseModel):
    """图谱关系列表响应"""
    items: list[RelationResponse]
    total: int
    deprecated: bool = False
    note: Optional[str] = None


class StatsResponse(BaseModel):
    """统计信息响应"""
    layers: dict
    graph: Optional[dict] = None
    vector: Optional[dict] = None


class PrefetchResponse(BaseModel):
    """预取响应"""
    query: str
    results: list[dict]


class ErrorResponse(BaseModel):
    """错误响应"""
    error: str
    code: str
    detail: Optional[str] = None


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="AgentMemory Web Dashboard",
    description="可视化 AgentMemory 记忆系统的 Web 面板 (v2.1.0)",
    version="2.1.0",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 获取静态文件路径
_current_dir = Path(__file__).parent
_static_dir = _current_dir / "static"
_template_dir = _current_dir / "templates"


def _get_memory_manager() -> MemoryManager:
    """获取 MemoryManager 实例 (v2.1.0 默认挂 FactExtractor)"""
    return MemoryManager()


def _handle_memory_error(e: Exception) -> HTTPException:
    """将 MemoryError 转换为 HTTPException"""
    if isinstance(e, NotFoundError):
        return HTTPException(status_code=404, detail=str(e))
    elif isinstance(e, ValidationError):
        return HTTPException(status_code=422, detail=str(e))
    elif isinstance(e, (ConfigError, ProviderError, StorageError)):
        return HTTPException(status_code=400, detail=str(e))
    else:
        return HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Routes
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """返回 index.html"""
    index_path = _template_dir / "index.html"
    if index_path.exists():
        return index_path.read_text(encoding="utf-8")
    return """
    <!DOCTYPE html>
    <html>
    <head><title>AgentMemory Dashboard</title></head>
    <body>
        <h1>AgentMemory Web Dashboard</h1>
        <p>Frontend files not found. Please ensure templates/index.html exists.</p>
    </body>
    </html>
    """


@app.get("/api/memories", response_model=MemoryListResponse)
async def list_memories(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    search: Optional[str] = Query(None, description="关键词搜索"),
):
    """
    列出记忆（分页 + 搜索）

    2026-07-15: 用 await mm.list() 替代老 mh.vector.memories 直接访问
    """
    try:
        mm = _get_memory_manager()
        # 用 MemoryManager.list() (新接口)
        items_raw = await mm.list(limit=page_size, category_path=None)
        # 客户端过滤 (轻量级,完整搜索走 /v1/memories endpoint)
        if search:
            s = search.lower()
            items_raw = [m for m in items_raw if s in (m.get("content", "") or "").lower()]
        # 取 page
        start = (page - 1) * page_size
        page_items = items_raw[start:start + page_size]
        # 拿 stats 算 total
        stats = await mm.stats()
        total = stats.get("total", stats.get("memories", len(items_raw)))
        pages = max(1, (total + page_size - 1) // page_size)

        return MemoryListResponse(
            items=[
                MemoryResponse(
                    id=m.get("id", ""),
                    content=m.get("content", ""),
                    importance=m.get("importance", m.get("meta", {}).get("importance", 0.5)),
                    created_at=m.get("created_at", m.get("meta", {}).get("created_at", "")),
                    schema_version=m.get("schema_version", 1),
                    metadata=m.get("metadata", m.get("meta")),
                    tags=m.get("tags", m.get("meta", {}).get("tags", [])),
                    fact_type=m.get("fact_type", m.get("meta", {}).get("fact_type")),
                )
                for m in page_items
            ],
            total=total if not search else len(items_raw),
            page=page,
            page_size=page_size,
            pages=pages if not search else 1,
        )

    except MemoryError as e:
        raise _handle_memory_error(e)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/memories/{memory_id}", response_model=MemoryResponse)
async def get_memory(memory_id: str):
    """获取单个记忆详情 (2026-07-15: 改用 await mm.get)"""
    try:
        mm = _get_memory_manager()
        memory = await mm.get(memory_id)
        if memory is None:
            raise NotFoundError(f"Memory not found: {memory_id}")
        meta = memory.get("meta", {}) or {}
        return MemoryResponse(
            id=memory.get("id", ""),
            content=memory.get("content", ""),
            importance=memory.get("importance", meta.get("importance", 0.5)),
            created_at=memory.get("created_at", meta.get("created_at", "")),
            schema_version=memory.get("schema_version", 1),
            metadata=memory.get("metadata", meta),
            tags=memory.get("tags", meta.get("tags", [])),
            fact_type=memory.get("fact_type", meta.get("fact_type")),
        )

    except MemoryError as e:
        raise _handle_memory_error(e)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/memories/{memory_id}")
async def delete_memory(memory_id: str):
    """遗忘记忆 (2026-07-15: 改用 await mm.delete)"""
    try:
        mm = _get_memory_manager()
        # 先确认存在,再删除
        existing = await mm.get(memory_id)
        if existing is None:
            raise NotFoundError(f"Memory not found: {memory_id}")
        success = await mm.delete(memory_id)
        return {"ok": True, "message": f"Memory {memory_id} deleted"}

    except MemoryError as e:
        raise _handle_memory_error(e)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/graph/entities", response_model=GraphEntitiesResponse)
async def list_entities():
    """列出图谱中的所有实体

    2026-07-15: 新架构下 entity/relation 由 SQLiteStore + LibraryClassifier 管理。
    MemoryManager 未暴露 entity API;此处暂返回 deprecation notice + 空 list,
    后续版本(2026-08)会通过 mm.classifier.list_entities() 暴露。
    """
    return GraphEntitiesResponse(
        items=[],
        total=0,
        deprecated=True,
        note=(
            "v2.1.0+ 不再独立维护 entity/relation 表。"
            "标签/共现矩阵已迁到 SQLiteStore,使用 mm.classifier 或 mm._l4.store 查询。"
        ),
    )


@app.get("/api/graph/relations", response_model=GraphRelationsResponse)
async def list_relations():
    """列出图谱中的所有关系

    2026-07-15: 同 list_entities,暂返回 deprecation notice。
    """
    return GraphRelationsResponse(
        items=[],
        total=0,
        deprecated=True,
        note=(
            "v2.1.0+ 不再独立维护 relation 表。"
            "共现关系由 SQLiteStore 共现矩阵维护。"
        ),
    )


@app.get("/api/stats", response_model=StatsResponse)
async def get_stats():
    """获取记忆系统统计信息 (2026-07-15: await mm.stats)"""
    try:
        mm = _get_memory_manager()
        stats = await mm.stats()
        # 适配老 schema
        return StatsResponse(
            layers={
                "l1_compress": True,
                "l3_vector": True,
                "l4_files": True,
            },
            vector={"total": stats.get("total", stats.get("memories", 0))},
            graph={"note": "已迁到 SQLiteStore"},
        )

    except MemoryError as e:
        raise _handle_memory_error(e)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/prefetch", response_model=PrefetchResponse)
async def prefetch(request: PrefetchRequest):
    """预取相关记忆 (2026-07-15: 改用 compress_for_context + search)"""
    try:
        mm = _get_memory_manager()
        # 搜相关 memory
        candidates = await mm.search(request.query, limit=20)
        # 拿到 id 后用 compress_for_context 聚合
        ids = [m.get("id", "") for m in candidates if m.get("id")]
        if ids:
            ctx = await mm.compress_for_context(ids, query=request.query)
            results = [{"context": ctx, "hits": candidates}]
        else:
            results = []

        return PrefetchResponse(query=request.query, results=results)

    except MemoryError as e:
        raise _handle_memory_error(e)
    except Exception as e:
        return PrefetchResponse(query=request.query, results=[])


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "agentmemory-web", "version": "2.1.0"}


# ============================================================================
# Main Entry Point
# ============================================================================

def run_server(host: str = "0.0.0.0", port: int = 8765):
    """启动服务器"""
    import uvicorn
    uvicorn.run(app, host=host, port=port, reload=False)


if __name__ == "__main__":
    run_server()