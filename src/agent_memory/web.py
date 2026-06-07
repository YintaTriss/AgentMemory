# -*- coding: utf-8 -*-
"""
Web API Server — AgentMemory FastAPI Application

Exposes REST endpoints for memory operations.
"""

from __future__ import annotations

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

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": __version__}

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
        vec = embedder.embed(req.content)
        l3_store.upsert(
            id=mem_id,
            content=req.content,
            vector=vec,
            metadata=metadata,
            importance=req.importance,
            category_path=category,
        )

        return {"id": mem_id, "category_path": category}

    @app.get("/memories")
    async def list_memories(
        category_path: Optional[str] = None,
        limit: int = Query(20, ge=1, le=1000),
    ):
        """List memories, optionally filtered by category."""
        if category_path:
            records = await store.get_all_by_category(category_path)
        else:
            all_ids = await store.list_all()
            records = []
            for mid in all_ids[:limit]:
                content = await store.load(mid)
                meta = await store.get_meta(mid)
                records.append({"id": mid, "content": content, "meta": meta})

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
        """Get a single memory by ID."""
        content = await store.load(memory_id)
        if not content:
            raise HTTPException(status_code=404, detail="Memory not found")
        meta = await store.get_meta(memory_id)
        return {"id": memory_id, "content": content, "meta": meta or {}}

    @app.delete("/memories/{memory_id}")
    async def delete_memory(memory_id: str):
        """Delete a memory."""
        ok = await store.delete(memory_id)
        if ok:
            l3_store.delete(memory_id)
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

        query_vector = embedder.embed(q)

        if mode == "vector":
            filter_expr = f"category_path = '{category_path}'" if category_path else None
            raw = l3_store.search(query_vector, top_k=top_k, filter_expr=filter_expr)
            return {"mode": "vector", "query": q, "results": raw}

        # hybrid
        filter_expr = f"category_path = '{category_path}'" if category_path else None
        vec_results = l3_store.search(query_vector, top_k=top_k * 2, filter_expr=filter_expr)
        bm25_results = l3_store.search_bm25(q, top_k=top_k * 2)

        # Inline hybrid fusion (reuse search_hybrid logic inline to avoid extra import)
        # Normalize
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
