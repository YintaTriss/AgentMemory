"""
Fuzzy Search — AgentMemory 第一层召回（对标 VCP 的 Fuse.js）

基于 rapidfuzz，提供：
- fuzzy_search(query, candidates) → hits
- prefix_search(query, candidates) → prefix matches

使用场景：搜索时的宽松匹配，错别字容错。
"""
from __future__ import annotations

from typing import List, Tuple
from rapidfuzz import fuzz, process


def fuzzy_search(
    query: str,
    candidates: List[str],
    limit: int = 10,
    score_cutoff: float = 30.0,
) -> List[Tuple[str, float]]:
    """
    Fuzzy match query against candidate strings.
    
    Returns: [(candidate, score)], sorted by score descending, score 0-100.
    
    Uses token_sort_ratio for best accuracy on multi-word queries.
    Falls back to partial_ratio for substring matching.
    """
    if not query or not candidates:
        return []

    scores = process.extract(
        query, candidates,
        scorer=fuzz.token_sort_ratio,
        limit=limit,
        score_cutoff=score_cutoff,
    )
    return [(text, score) for text, score, _ in scores]


def fuzzy_search_with_ids(
    query: str,
    items: List[tuple],
    limit: int = 10,
    score_cutoff: float = 30.0,
) -> List[Tuple[str, float, str]]:
    """
    Fuzzy match with associated IDs.
    
    items: [(text, id), ...]
    Returns: [(text, score, id), ...]
    """
    if not query or not items:
        return []

    texts = [item[0] for item in items]
    ids = [item[1] for item in items]

    results = process.extract(
        query, texts,
        scorer=fuzz.token_sort_ratio,
        limit=limit,
        score_cutoff=score_cutoff,
    )
    return [(text, score, ids[texts.index(text)]) for text, score, _ in results]


def prefix_search(
    query: str,
    candidates: List[str],
    limit: int = 10,
) -> List[Tuple[str, float]]:
    """
    Prefix-based matching (Fuse.js "prefix" mode).
    Candidates that START WITH query get priority.
    """
    if not query or not candidates:
        return []

    query_lower = query.lower()
    # Exact prefix matches first
    prefix_matches = [(c, 100.0) for c in candidates
                       if c.lower().startswith(query_lower)]
    # Then fuzzy
    fuzzy = fuzzy_search(query, candidates, limit=limit)
    
    # Deduplicate: fuzzy may already include prefix matches
    seen = set()
    result = []
    for item in prefix_matches + fuzzy:
        text = item[0]
        if text not in seen:
            seen.add(text)
            result.append(item)

    return result[:limit]


def similarity(a: str, b: str) -> float:
    """Quick similarity between two strings (0-100)."""
    return fuzz.token_sort_ratio(a, b)
