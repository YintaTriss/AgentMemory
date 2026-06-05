"""
AgentMemory v2.0 RESTful API

FastAPI application providing CRUD + search + decay API for the memory system.
"""
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Pydantic Models (existing + new request/response models)
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    version: str


class LibraryNodeModel(BaseModel):
    id: str
    name: str
    path: str
    type: str
    parentId: Optional[str] = None
    children: Optional[List] = []
    memoryCount: int = 0
    memorySize: int = 0
    createdAt: str
    updatedAt: str


class MemoryModel(BaseModel):
    id: str
    content: str
    summary: Optional[str] = None
    category: str
    tags: List[str] = []
    importance: int = 3
    embeddingStatus: str = "completed"
    embeddingScore: Optional[float] = None
    filePath: str
    createdAt: str
    updatedAt: str
    accessCount: int = 0
    lastAccessAt: Optional[str] = None


# --- Request Models ---

class MemoryCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=100_000)
    category: str = Field(..., description="Category path, e.g. 'A.项目/石榴籽/语料'")
    tags: List[str] = Field(default_factory=list, max_length=50)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)


class MemoryUpdateRequest(BaseModel):
    content: Optional[str] = Field(None, min_length=1, max_length=100_000)
    tags: Optional[List[str]] = None
    importance: Optional[float] = Field(None, ge=0.0, le=1.0)


class CategoryCreateRequest(BaseModel):
    path: str = Field(..., description="Category path, e.g. 'A.项目/石榴籽'")
    description: Optional[str] = ""


# --- Response Models ---

class MemoryListResponse(BaseModel):
    items: List[MemoryModel]
    total: int
    limit: int
    offset: int


class CategoryListResponse(BaseModel):
    categories: List[str]


class CategoryCreateResponse(BaseModel):
    path: str
    created: bool


class SearchResultItem(BaseModel):
    id: str
    content: str
    category: str
    tags: List[str] = []
    importance: float = 0.5
    score: float
    createdAt: Optional[str] = None


class SearchResponse(BaseModel):
    query: str
    items: List[SearchResultItem]
    total: int


class StatsResponse(BaseModel):
    total_memories: int
    total_categories: int
    embedding_pending: int
    embedding_completed: int
    embedding_failed: int


class DecayRunResponse(BaseModel):
    scanned: int
    forgotten: int
    archived: int
    errors: List[str] = []


# ---------------------------------------------------------------------------
# Dependency Injection
# ---------------------------------------------------------------------------

# Lazy singletons (created on first request)
_datalake_instance: Optional["DataLake"] = None
_search_engine_instance: Optional["SearchEngine"] = None
_hermes_instance: Optional["MemoryHermes"] = None
_init_lock = asyncio.Lock()


def _get_datalake_root() -> Path:
    """Get DataLake root directory from config."""
    try:
        from agentmemory.config import get_config
        config = get_config()
        data_root = config.config.get("storage", {}).get("data_dir", "data")
        pkg_dir = Path(__file__).parent.parent.parent.resolve()
        return (pkg_dir / data_root).resolve()
    except Exception:
        # Fallback
        pkg_dir = Path(__file__).parent.parent.parent.resolve()
        return (pkg_dir / "data").resolve()


async def get_datalake() -> "DataLake":
    """DataLake singleton dependency."""
    global _datalake_instance
    if _datalake_instance is None:
        async with _init_lock:
            if _datalake_instance is None:
                from agentmemory.data.datalake import DataLake
                root = _get_datalake_root()
                _datalake_instance = DataLake(root_dir=str(root))
                await _datalake_instance.init()
    return _datalake_instance


async def get_search_engine() -> "SearchEngine":
    """SearchEngine singleton dependency."""
    global _search_engine_instance
    if _search_engine_instance is None:
        async with _init_lock:
            if _search_engine_instance is None:
                from agentmemory.search.search_engine import SearchEngine
                try:
                    from agentmemory.config import get_config
                    config = get_config()
                    memory_dir = config.config.get("storage", {}).get("memory_dir", "memory")
                    pkg_dir = Path(__file__).parent.parent.parent.resolve()
                    mem_dir = (pkg_dir / memory_dir).resolve()
                except Exception:
                    pkg_dir = Path(__file__).parent.parent.parent.resolve()
                    mem_dir = (pkg_dir / "memory").resolve()
                _search_engine_instance = SearchEngine(memory_dir=str(mem_dir))
    return _search_engine_instance


async def get_hermes() -> "MemoryHermes":
    """MemoryHermes singleton dependency (created per-request for thread-safety)."""
    global _hermes_instance
    if _hermes_instance is None:
        async with _init_lock:
            if _hermes_instance is None:
                from agentmemory.memory_manager import MemoryHermes
                _hermes_instance = MemoryHermes()
    return _hermes_instance


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _memory_content_to_model(content_obj, memory_library_path: str) -> MemoryModel:
    """Convert DataLake MemoryContent + meta to MemoryModel."""
    meta = content_obj.metadata or {}
    cat_path = meta.get("category_path", "")
    category_parts = cat_path.split("/") if cat_path else []
    category_str = "/".join(category_parts)

    # Build a plausible file path
    file_path = str(Path(memory_library_path) / cat_path / content_obj.memory_id)

    return MemoryModel(
        id=content_obj.memory_id,
        content=content_obj.content,
        summary=meta.get("summary"),
        category=category_str,
        tags=meta.get("tags", []),
        importance=int(meta.get("importance", 0.5) * 5),
        embeddingStatus=meta.get("embedding_state", "pending"),
        embeddingScore=meta.get("embedding_score"),
        filePath=file_path,
        createdAt=meta.get("created_at", ""),
        updatedAt=meta.get("updated_at", ""),
        accessCount=meta.get("access_count", 0),
        lastAccessAt=meta.get("last_access_at"),
    )


# ---------------------------------------------------------------------------
# App Factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(
        title="AgentMemory API v2",
        version="2.0.0",
        description="RESTful API for AgentMemory v2.0 — CRUD, Search, Categories, Decay",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---------------------------------------------------------------------------
    # Health
    # ---------------------------------------------------------------------------

    @app.get("/health", response_model=HealthResponse, tags=["System"])
    async def health_check():
        return HealthResponse(status="ok", version="2.0.0")

    # ---------------------------------------------------------------------------
    # Memories CRUD
    # ---------------------------------------------------------------------------

    @app.get("/memories", response_model=MemoryListResponse, tags=["Memories"])
    async def list_memories(
        category: Optional[str] = Query(None, description="Filter by category prefix"),
        limit: int = Query(20, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ):
        dl = await get_datalake()
        library_path = str(dl.memory_library)

        if category:
            ids = await dl.list_memories(category=category.split("/"), limit=limit + offset)
        else:
            ids = await dl.list_memories(limit=limit + offset)

        total = len(ids)
        page_ids = ids[offset:offset + limit]

        items = []
        for mid in page_ids:
            content = await dl.read(mid)
            if content is not None:
                items.append(_memory_content_to_model(content, library_path))

        return MemoryListResponse(items=items, total=total, limit=limit, offset=offset)

    @app.post("/memories", response_model=MemoryModel, status_code=201, tags=["Memories"])
    async def create_memory(req: MemoryCreateRequest, background_tasks: BackgroundTasks):
        dl = await get_datalake()
        library_path = str(dl.memory_library)

        memory_id = await dl.write(
            content=req.content,
            category=req.category.split("/"),
            metadata={"tags": req.tags},
            importance=req.importance,
        )

        # Trigger async embedding update in background
        async def update_embedding_state():
            try:
                hermes = await get_hermes()
                if hermes.vector:
                    from agentmemory.providers.embedder import get_embedder
                    embedder = get_embedder()
                    vector = embedder.embed(req.content)
                    await dl.save_vector(
                        memory_id,
                        vector,
                        model=embedder.model,
                        dimensions=embedder.dimensions,
                    )
                    await dl.update_memory_metadata(memory_id, embedding_state="completed")
            except Exception:
                await dl.update_memory_metadata(memory_id, embedding_state="failed")

        background_tasks.add_task(update_embedding_state)

        content = await dl.read(memory_id)
        if content is None:
            raise HTTPException(status_code=500, detail="Failed to read created memory")
        return _memory_content_to_model(content, library_path)

    @app.get("/memories/{memory_id}", response_model=MemoryModel, tags=["Memories"])
    async def get_memory(memory_id: str):
        dl = await get_datalake()
        content = await dl.read(memory_id)
        if content is None:
            raise HTTPException(status_code=404, detail="Memory not found")
        return _memory_content_to_model(content, str(dl.memory_library))

    @app.put("/memories/{memory_id}", response_model=MemoryModel, tags=["Memories"])
    async def update_memory(memory_id: str, req: MemoryUpdateRequest):
        dl = await get_datalake()
        exists = await dl.exists(memory_id)
        if not exists:
            raise HTTPException(status_code=404, detail="Memory not found")

        if req.content is not None:
            await dl.update_memory(memory_id, content=req.content)
        if req.tags is not None or req.importance is not None:
            await dl.update_memory_metadata(
                memory_id,
                tags=req.tags,
                importance=req.importance,
            )

        content = await dl.read(memory_id)
        if content is None:
            raise HTTPException(status_code=500, detail="Failed to read updated memory")
        return _memory_content_to_model(content, str(dl.memory_library))

    @app.delete("/memories/{memory_id}", status_code=204, tags=["Memories"])
    async def delete_memory(memory_id: str):
        dl = await get_datalake()
        try:
            await dl.delete(memory_id)
        except Exception as e:
            if "not found" in str(e).lower():
                raise HTTPException(status_code=404, detail="Memory not found")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/memories/{memory_id}/access", response_model=MemoryModel, tags=["Memories"])
    async def access_memory(memory_id: str):
        """Mark a memory as accessed (updates last_access_at and access_count)."""
        dl = await get_datalake()
        content = await dl.read(memory_id)
        if content is None:
            raise HTTPException(status_code=404, detail="Memory not found")

        meta = content.metadata or {}
        access_count = meta.get("access_count", 0) + 1
        last_access_at = datetime.now().isoformat()
        meta["access_count"] = access_count
        meta["last_access_at"] = last_access_at

        # Update metadata
        await dl.update_memory_metadata(memory_id, tags=meta.get("tags"))

        # Re-read to get updated content
        content = await dl.read(memory_id)
        return _memory_content_to_model(content, str(dl.memory_library))

    # ---------------------------------------------------------------------------
    # Categories
    # ---------------------------------------------------------------------------

    @app.get("/categories", response_model=CategoryListResponse, tags=["Categories"])
    async def list_categories():
        dl = await get_datalake()
        categories = await dl.list_categories()
        return CategoryListResponse(categories=categories)

    @app.post("/categories", response_model=CategoryCreateResponse, status_code=201, tags=["Categories"])
    async def create_category(req: CategoryCreateRequest):
        dl = await get_datalake()
        await dl.create_category(req.path)
        return CategoryCreateResponse(path=req.path, created=True)

    # ---------------------------------------------------------------------------
    # Search
    # ---------------------------------------------------------------------------

    @app.get("/search", response_model=SearchResponse, tags=["Search"])
    async def search_memories(
        q: str = Query(..., min_length=1, description="Search query"),
        category: Optional[str] = Query(None, description="Filter by category"),
        limit: int = Query(10, ge=1, le=100),
    ):
        se = await get_search_engine()
        from agentmemory.search.search_engine import SearchOptions

        opts = SearchOptions(limit=limit, category=category)
        results = await se.search_semantic(q, opts)

        items = []
        for entry in results:
            items.append(SearchResultItem(
                id=entry.id,
                content=entry.content[:500],  # truncate for response
                category=str(entry.category or ""),
                tags=entry.tags,
                importance=entry.importance,
                score=entry.score,
                createdAt=entry.metadata.get("created_at") if entry.metadata else None,
            ))

        return SearchResponse(query=q, items=items, total=len(items))

    # ---------------------------------------------------------------------------
    # Stats
    # ---------------------------------------------------------------------------

    @app.get("/stats", response_model=StatsResponse, tags=["System"])
    async def get_stats():
        dl = await get_datalake()
        all_ids = await dl.list_memories(limit=100000)
        pending = 0
        completed = 0
        failed = 0

        for mid in all_ids:
            meta = await dl.get_memory_metadata(mid)
            if meta is None:
                continue
            state = meta.embedding_state
            if state == "pending":
                pending += 1
            elif state == "completed":
                completed += 1
            elif state in ("failed", "permanent_failure"):
                failed += 1

        categories = await dl.list_categories()

        return StatsResponse(
            total_memories=len(all_ids),
            total_categories=len(categories),
            embedding_pending=pending,
            embedding_completed=completed,
            embedding_failed=failed,
        )

    # ---------------------------------------------------------------------------
    # Decay
    # ---------------------------------------------------------------------------

    @app.post("/decay/run", response_model=DecayRunResponse, tags=["System"])
    async def run_decay_check(background_tasks: BackgroundTasks):
        """Trigger decay check asynchronously."""

        async def _decay_task() -> dict:
            errors = []
            try:
                hermes = await get_hermes()
                if hermes.decay is None:
                    return {"scanned": 0, "forgotten": 0, "archived": 0, "errors": []}

                dl = await get_datalake()
                all_ids = await dl.list_memories(limit=100000)
                scanned = len(all_ids)
                forgotten = 0
                archived = 0

                for mid in all_ids:
                    try:
                        meta = await dl.get_memory_metadata(mid)
                        if meta is None:
                            continue
                        score = hermes.decay.calculate_score(
                            memory_id=mid,
                            access_count=meta.retry_count,  # reuse retry_count field
                            importance=meta.importance,
                            created_at=datetime.fromisoformat(meta.created_at) if meta.created_at else datetime.now(),
                        )
                        if score < hermes.decay.policy.forget_threshold:
                            await dl.delete(mid)
                            forgotten += 1
                        elif score < hermes.decay.policy.archive_threshold:
                            if hermes.archiver:
                                await hermes.archiver.archive(mid)
                            archived += 1
                    except Exception:
                        errors.append(f"Failed to process {mid}")

                return {"scanned": scanned, "forgotten": forgotten, "archived": archived, "errors": errors}
            except Exception as e:
                return {"scanned": 0, "forgotten": 0, "archived": 0, "errors": [str(e)]}

        # Run in background and return immediately
        background_tasks.add_task(_decay_task)
        return DecayRunResponse(scanned=0, forgotten=0, archived=0, errors=[])

    return app


# Module-level app instance (for uvicorn / FastAPI static analysis)
app = create_app()
