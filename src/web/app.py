"""
AgentMemory Web Dashboard
FastAPI 后端服务，提供 RESTful API 访问记忆系统数据
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

# 尝试导入 MemoryHermes（支持包安装或源码运行）
try:
    from src.memory_manager import MemoryHermes
except ImportError:
    try:
        from memory_manager import MemoryHermes
    except ImportError:
        MemoryHermes = None

try:
    from src.errors import (
        MemoryError,
        NotFoundError,
        ValidationError,
        ConfigError,
        ProviderError,
        StorageError,
    )
except ImportError:
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
        # 定义基础错误类（如果 errors 模块不可用）
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


class GraphRelationsResponse(BaseModel):
    """图谱关系列表响应"""
    items: list[RelationResponse]
    total: int


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
    description="可视化 AgentMemory 记忆系统的 Web 面板",
    version="1.0.0",
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


def _get_memory_hermes() -> MemoryHermes:
    """获取 MemoryHermes 实例"""
    if MemoryHermes is None:
        raise HTTPException(
            status_code=500,
            detail="MemoryHermes not available. Please install agentmemory package."
        )
    return MemoryHermes()


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
    # 如果模板不存在，返回简单提示
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
    
    返回记忆列表，支持关键词搜索和分页
    """
    try:
        mh = _get_memory_hermes()
        
        # 获取统计信息中的记忆数量
        stats = mh.get_stats()
        total = stats.get("vector", {}).get("total", 0)
        
        # 计算分页
        pages = max(1, (total + page_size - 1) // page_size)
        
        # 获取记忆列表（如果有向量存储）
        items = []
        if mh.vector and hasattr(mh.vector, 'memories'):
            memories = mh.vector.memories
            
            # 过滤
            if search:
                search_lower = search.lower()
                memories = [
                    m for m in memories 
                    if search_lower in m.get("content", "").lower()
                ]
            
            # 分页
            start = (page - 1) * page_size
            end = start + page_size
            page_memories = memories[start:end]
            
            for m in page_memories:
                items.append(MemoryResponse(
                    id=m.get("id", ""),
                    content=m.get("content", ""),
                    importance=m.get("importance", 0.5),
                    created_at=m.get("created_at", ""),
                    schema_version=m.get("schema_version", 1),
                    metadata=m.get("metadata"),
                    tags=m.get("tags", []),
                    fact_type=m.get("fact_type"),
                ))
        
        return MemoryListResponse(
            items=items,
            total=total if not search else len(items),
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
    """
    获取单个记忆详情
    
    通过 memory_id 获取记忆的完整信息
    """
    try:
        mh = _get_memory_hermes()
        
        # 从向量存储中查找
        memory = None
        if mh.vector and hasattr(mh.vector, 'memories'):
            for m in mh.vector.memories:
                if m.get("id") == memory_id:
                    memory = m
                    break
        
        if memory is None:
            raise NotFoundError(f"Memory not found: {memory_id}")
        
        return MemoryResponse(
            id=memory.get("id", ""),
            content=memory.get("content", ""),
            importance=memory.get("importance", 0.5),
            created_at=memory.get("created_at", ""),
            schema_version=memory.get("schema_version", 1),
            metadata=memory.get("metadata"),
            tags=memory.get("tags", []),
            fact_type=memory.get("fact_type"),
        )
    
    except MemoryError as e:
        raise _handle_memory_error(e)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/memories/{memory_id}")
async def delete_memory(memory_id: str):
    """
    遗忘记忆
    
    删除指定的记忆（支持永久删除）
    """
    try:
        mh = _get_memory_hermes()
        
        # 先检查记忆是否存在
        memory = None
        if mh.vector and hasattr(mh.vector, 'memories'):
            for m in mh.vector.memories:
                if m.get("id") == memory_id:
                    memory = m
                    break
        
        if memory is None:
            raise NotFoundError(f"Memory not found: {memory_id}")
        
        success = await mh.forget(memory_id, permanent=True)
        return {"ok": True, "message": f"Memory {memory_id} deleted"}
    
    except MemoryError as e:
        raise _handle_memory_error(e)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/graph/entities", response_model=GraphEntitiesResponse)
async def list_entities():
    """
    列出图谱中的所有实体
    
    返回实体列表
    """
    try:
        mh = _get_memory_hermes()
        
        entities = []
        if mh.graph and hasattr(mh.graph, 'entities'):
            entities = [
                EntityResponse(
                    id=e.get("id", ""),
                    name=e.get("name", ""),
                    type=e.get("type", "unknown"),
                    attributes=e.get("attributes", {}),
                )
                for e in mh.graph.entities
            ]
        
        return GraphEntitiesResponse(
            items=entities,
            total=len(entities),
        )
    
    except MemoryError as e:
        raise _handle_memory_error(e)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/graph/relations", response_model=GraphRelationsResponse)
async def list_relations():
    """
    列出图谱中的所有关系
    
    返回关系列表
    """
    try:
        mh = _get_memory_hermes()
        
        relations = []
        if mh.graph and hasattr(mh.graph, 'relations'):
            relations = [
                RelationResponse(
                    id=r.get("id", ""),
                    source=r.get("source", ""),
                    target=r.get("target", ""),
                    type=r.get("type", "unknown"),
                    weight=r.get("weight", 1.0),
                )
                for r in mh.graph.relations
            ]
        
        return GraphRelationsResponse(
            items=relations,
            total=len(relations),
        )
    
    except MemoryError as e:
        raise _handle_memory_error(e)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats", response_model=StatsResponse)
async def get_stats():
    """
    获取记忆系统统计信息
    
    返回各层状态和统计信息
    """
    try:
        mh = _get_memory_hermes()
        stats = mh.get_stats()
        return StatsResponse(**stats)
    
    except MemoryError as e:
        raise _handle_memory_error(e)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/prefetch", response_model=PrefetchResponse)
async def prefetch(request: PrefetchRequest):
    """
    预取相关记忆
    
    根据查询文本预取相关记忆
    """
    try:
        mh = _get_memory_hermes()
        
        # 执行预取（如果 prefetch 方法存在）
        if hasattr(mh, 'prefetch'):
            await mh.prefetch(request.query)
        
        # 获取预取结果
        results = []
        if hasattr(mh, 'get_prefetched'):
            results = mh.get_prefetched(request.query) or []
        
        return PrefetchResponse(
            query=request.query,
            results=results,
        )
    
    except MemoryError as e:
        raise _handle_memory_error(e)
    except Exception as e:
        # 返回空结果而不是 500 错误
        return PrefetchResponse(
            query=request.query,
            results=[],
        )


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "agentmemory-web"}


# ============================================================================
# Main Entry Point
# ============================================================================

def run_server(host: str = "0.0.0.0", port: int = 8765):
    """启动服务器"""
    import uvicorn
    uvicorn.run(app, host=host, port=port, reload=False)


if __name__ == "__main__":
    run_server()
