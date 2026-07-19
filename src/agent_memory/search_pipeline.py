"""
SearchPipeline — 四层搜索结果融合
Fuzzy → BM25 → Vector → Reranker
"""
from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class SearchResult:
    content: str
    score: float = 0.0
    id: str = ""
    source: str = ""  # fuzzy / bm25 / vector / reranker
    metadata: Dict[str, Any] = field(default_factory=dict)


class SearchPipeline:
    def __init__(
        self,
        fuzzy_fn: Optional[Callable] = None,
        bm25_fn: Optional[Callable] = None,
        vector_fn: Optional[Callable] = None,
        reranker_fn: Optional[Callable] = None,
    ):
        self.fuzzy_fn = fuzzy_fn
        self.bm25_fn = bm25_fn
        self.vector_fn = vector_fn
        self.reranker_fn = reranker_fn

    async def search(
        self,
        query: str,
        candidates: List[Dict],
        weights: Optional[Dict[str, float]] = None,
        top_k: int = 10,
    ) -> List[SearchResult]:
        w = weights or {"fuzzy": 0.2, "bm25": 0.3, "vector": 0.4, "reranker": 0.1}
        scored: Dict[str, SearchResult] = {}

        # Stage 1: Fuzzy
        if self.fuzzy_fn and w.get("fuzzy", 0) > 0 and candidates:
            fuzzy_results = self.fuzzy_fn(query, [c.get("content","") for c in candidates])
            for text, score in fuzzy_results:
                for c in candidates:
                    if c.get("content") == text:
                        key = c.get("id", text)
                        scored.setdefault(key, SearchResult(
                            content=text, id=c.get("id",""), source="fuzzy"
                        )).score += w["fuzzy"] * (score / 100.0)

        # Stage 2: BM25
        if self.bm25_fn and w.get("bm25", 0) > 0:
            try:
                bm25_results = await self.bm25_fn(query, top_k=top_k*2)
                for item in bm25_results:
                    text = item.get("content", item) if isinstance(item, dict) else str(item)
                    score = item.get("score", 0) if isinstance(item, dict) else 0.5
                    key = item.get("id", text) if isinstance(item, dict) else text
                    scored.setdefault(key, SearchResult(
                        content=text, id=key, source="bm25"
                    )).score += w["bm25"] * score
            except Exception:
                pass

        # Stage 3: Vector
        if self.vector_fn and w.get("vector", 0) > 0:
            try:
                vector_results = await self.vector_fn(query, top_k=top_k*2)
                for item in vector_results:
                    text = item.get("content", item) if isinstance(item, dict) else str(item)
                    score = item.get("score", 0) if isinstance(item, dict) else 0.5
                    key = item.get("id", text) if isinstance(item, dict) else text
                    scored.setdefault(key, SearchResult(
                        content=text, id=key, source="vector"
                    )).score += w["vector"] * score
            except Exception:
                pass

        # Stage 4: Reranker
        if self.reranker_fn and w.get("reranker", 0) > 0 and scored:
            reranked = self.reranker_fn(query, [
                {"content": r.content, "id": r.id, "_original_score": r.score}
                for r in scored.values()
            ])
            for item in reranked:
                key = item.get("id", "")
                if key in scored:
                    scored[key].score += w["reranker"] * item.get("_rerank_score", 0)

        return sorted(scored.values(), key=lambda x: x.score, reverse=True)[:top_k]
