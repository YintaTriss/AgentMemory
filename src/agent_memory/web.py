# -*- coding: utf-8 -*-
"""
Web API Server — AgentMemory FastAPI Application

Exposes REST endpoints for memory operations.
"""

from __future__ import annotations

import asyncio
from typing import Optional

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

from . import __version__
from .l4_files import L4FilesStore
from .l3_lancedb import L3LanceDBStore
from .library import LibraryClassifier


# ============================================================================
# Pydantic Models
# ============================================================================

class MemoryAddRequest(BaseModel):
    content: str = Field(..., min_length=1, description="记忆内容")
    importance: float = Field(0.5, ge=0.0, le=1.0)
    tags: Optional[list[str]] = None
    category_path: Optional[str] = None


class MemorySearchRequest(BaseModel):
    query: str
    mode: str = Field("vector", pattern="^(vector|bm25|hybrid)$")
    top_k: int = Field(5, ge=1, le=100)
    category_path: Optional[str] = None


# ============================================================================
# FastAPI App Factory
# ============================================================================

def create_app(base_dir: str = "memory", db_path: str = "data/lancedb") -> FastAPI:
    """Create and configure the FastAPI application."""
    if not FASTAPI_AVAILABLE:
        raise RuntimeError(
            "FastAPI is not installed. Install with: pip install agentmemory[web]"
        )

    app = FastAPI(
        title="AgentMemory API",
        version=__version__,
        description="双轨 + 图书馆记忆系统的 HTTP API",
    )

    # Initialize stores on startup
    store = L4FilesStore(base_dir=base_dir)
    l3_store = L3LanceDBStore(db_path=db_path)
    classifier = LibraryClassifier()

    # ---- Internal helpers ----

    async def _get_embedding(embedder, text: str) -> list:
        """
        Get embedding vector, handling both sync and async embedders.

        P0-5 fix: DashScopeEmbedder.embed() is async (returns coroutine),
        HashEmbedder.embed() is sync. Detect and handle both correctly.
        """
        if asyncio.iscoroutinefunction(embedder.embed):
            return await embedder.embed(text)
        return embedder.embed(text)

    def _escape_filter(value: str) -> str:
        """
        Escape single quotes in filter values to prevent LanceDB injection.

        P1-2 fix: category_path in f-string filter_expr had SQL injection risk.
        Escape single quotes by doubling them (SQL standard).
        """
        return value.replace("'", "''")

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": __version__}

    @app.get("/healthz")
    async def healthz():
        from agent_memory.observability import healthz as do_health_check
        return await do_health_check()

    @app.get("/metrics")
    async def metrics():
        from agent_memory.observability import metrics as get_metrics
        return get_metrics.get_stats()

    # ---- Memory CRUD ----

    @app.post("/memories")
    async def add_memory(req: MemoryAddRequest):
        """Add a new memory."""
        category = req.category_path or classifier.classify(req.content)
        metadata = {
            "importance": req.importance,
            "tags": req.tags or [],
            "category_path": category,
            "source": "api",
        }
        mem_id = await store.save(req.content, metadata)

        # Also index in L3
        from .embedder import get_embedder
        embedder = get_embedder()
        # P0-5 fix: handle async embedder (DashScope) vs sync (HashEmbedder)
        vec = await _get_embedding(embedder, req.content)
        # P1-1 fix: rollback L4 if L3 upsert fails to maintain consistency
        try:
            l3_store.upsert(
                id=mem_id,
                content=req.content,
                vector=vec,
                metadata=metadata,
                importance=req.importance,
                category_path=category,
            )
        except Exception as e:
            await store.delete(mem_id)
            raise HTTPException(status_code=500, detail=f"L3 indexing failed: {e}")

        return {"id": mem_id, "category_path": category}

    @app.get("/memories")
    async def list_memories(
        category_path: Optional[str] = None,
        limit: int = Query(20, ge=1, le=1000),
    ):
        """
        List memories, optionally filtered by category.

        P0-1/2 fix: get_all_by_category() and list_all() do not exist on
        L4FilesStore. Replaced with list() + load_existing() approach.
        """
        all_ids = store.list()  # sync, returns List[str]
        # P2-4 fix: load each memory ONCE (was loading twice when category_path
        # was set — once for filter, once for record building = N+1 query problem).
        # Build mem_map upfront, then filter and build records in a single pass.
        mem_map = {}
        for mid in all_ids[:limit]:
            mem = await store.load_existing(mid)
            if mem:
                mem_map[mid] = mem

        if category_path:
            filtered_ids = [
                mid for mid, mem in mem_map.items()
                if mem.get("meta", {}).get("category_path") == category_path
            ]
        else:
            filtered_ids = list(mem_map.keys())

        records = [
            {
                "id": mid,
                "content": mem_map[mid].get("content", ""),
                "meta": mem_map[mid].get("meta", {}),
            }
            for mid in filtered_ids
        ]

        return {
            "count": len(records),
            "memories": [
                {
                    "id": r["id"],
                    "preview": (r["content"][:80] + "...") if len(r["content"] or "") > 80 else r["content"],
                    "category_path": r["meta"].get("category_path") if r["meta"] else None,
                    "importance": r["meta"].get("importance") if r["meta"] else None,
                }
                for r in records
            ],
        }

    @app.get("/memories/{memory_id}")
    async def get_memory(memory_id: str):
        """
        Get a single memory by ID.

        P0-3 fix: get_meta() does not exist on L4FilesStore.
        Use load_existing() which returns {content, meta} in one call.
        """
        mem = await store.load_existing(memory_id)
        if not mem:
            raise HTTPException(status_code=404, detail="Memory not found")
        return {
            "id": memory_id,
            "content": mem.get("content", ""),
            "meta": mem.get("meta", {}),
        }

    @app.delete("/memories/{memory_id}")
    async def delete_memory(memory_id: str):
        """Delete a memory from both L4 and L3."""
        ok = await store.delete(memory_id)
        if ok:
            l3_store.delete(memory_id)  # sync, no await needed
        return {"deleted": ok}

    # ---- Search ----

    @app.get("/search")
    async def search_memories(
        q: str = Query(..., min_length=1),
        mode: str = Query("vector", pattern="^(vector|bm25|hybrid)$"),
        top_k: int = Query(5, ge=1, le=100),
        category_path: Optional[str] = None,
    ):
        """Search memories by text query."""
        from .embedder import get_embedder
        embedder = get_embedder()

        if mode == "bm25":
            raw = l3_store.search_bm25(q, top_k=top_k)
            return {"mode": "bm25", "query": q, "results": raw}

        # P0-5 fix: handle async embedder
        query_vector = await _get_embedding(embedder, q)

        # P1-2 fix: escape single quotes in category_path to prevent injection
        filter_expr = None
        if category_path:
            filter_expr = f"category_path = '{_escape_filter(category_path)}'"

        if mode == "vector":
            raw = l3_store.search(query_vector, top_k=top_k, filter_expr=filter_expr)
            return {"mode": "vector", "query": q, "results": raw}

        # hybrid
        vec_results = l3_store.search(query_vector, top_k=top_k * 2, filter_expr=filter_expr)
        bm25_results = l3_store.search_bm25(q, top_k=top_k * 2)

        # Inline hybrid fusion
        max_vec = max((r.get("score", 0) for r in vec_results), default=1.0)
        max_bm = max((r.get("bm25_score", 0) for r in bm25_results), default=1.0)
        alpha = 0.7
        vec_map = {r["id"]: r.get("score", 0) / max_vec for r in vec_results}
        bm_map = {r["id"]: r.get("bm25_score", 0) / max_bm for r in bm25_results}
        all_ids = set(vec_map) | set(bm_map)
        scores = []
        for mid in all_ids:
            vs = vec_map.get(mid, 0.0)
            bs = bm_map.get(mid, 0.0)
            scores.append((mid, alpha * vs + (1 - alpha) * bs))
        scores.sort(key=lambda x: x[1], reverse=True)

        id_to_v = {r["id"]: r for r in vec_results}
        id_to_b = {r["id"]: r for r in bm25_results}
        results = []
        for mid, score in scores[:top_k]:
            vr = id_to_v.get(mid, {})
            br = id_to_b.get(mid, {})
            results.append({
                "id": mid,
                "content": vr.get("content") or br.get("content", ""),
                "score": round(score, 6),
                "vector_score": vr.get("score", 0.0),
                "bm25_score": br.get("bm25_score", 0.0),
                "metadata": vr.get("metadata") or {},
                "category_path": vr.get("category_path") or br.get("category_path", ""),
            })
        return {"mode": "hybrid", "query": q, "alpha": alpha, "results": results}

    # ---- Stats ----

    @app.get("/stats")
    async def get_stats():
        """Return memory statistics."""
        stats = store.get_stats()
        categories = store.get_categories()
        return {
            "memory_count": stats.get("memory_count", 0),
            "total_size_bytes": stats.get("total_size_bytes", 0),
            "category_count": len(categories),
            "l3_count": l3_store.count(),
            "l3_fallback": l3_store.is_using_fallback,
        }

    return app
