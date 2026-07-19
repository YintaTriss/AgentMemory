"""
Reranker — AgentMemory 第三层精排（对标 VCP 的 Reranker）

实现一个简单的**距离加权重新排序**作为轻量版。
完整 cross-encoder 需要额外下载模型，架构预留插槽。

重排算法：
1. BM25 score（若可用）
2. Query-candidate token overlap ratio（通用）
3. 位置加权（越靠前的项目越靠前）
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple


def rerank(
    query: str,
    candidates: List[Dict],
    text_field: str = "content",
    score_field: str = "_rerank_score",
    alpha: float = 0.6,
) -> List[Dict]:
    """
    简单重排：基于 token 重叠 + 位置衰减。

    Args:
        query: 搜索查询
        candidates: 原始候选列表
        text_field: 候选文本字段名
        score_field: 重排分数写入字段
        alpha: 重叠分的权重 (0-1)，剩余权重给位置

    Returns:
        按重排分数降序的候选列表
    """
    if not candidates:
        return []

    query_tokens = set(tokenize_simple(query))
    max_score = 0.0
    results = []

    for i, cand in enumerate(candidates):
        text = cand.get(text_field, "")
        if not text:
            continue

        # 1) Token overlap
        text_tokens = set(tokenize_simple(text))
        if query_tokens and text_tokens:
            overlap = len(query_tokens & text_tokens)
            ratio = overlap / max(len(query_tokens), 1)
        else:
            ratio = 0.0

        # 2) Position decay (early = higher)
        position_score = 1.0 - (i / max(len(candidates), 1))

        # 3) Combined
        combined = alpha * ratio + (1 - alpha) * position_score
        cand[score_field] = combined
        max_score = max(max_score, combined)
        results.append(cand)

    # Normalize to 0-1
    if max_score > 0:
        for r in results:
            r[score_field] = r.get(score_field, 0) / max_score

    results.sort(key=lambda x: x.get(score_field, 0), reverse=True)
    return results


def tokenize_simple(text: str) -> List[str]:
    """使用 jieba 分词（中文）+ 英文 word 切分。"""
    tokens = []
    import re
    # English/alphanumeric
    eng_tokens = re.findall(r"[a-z0-9]+", text.lower())
    tokens.extend(eng_tokens)
    # Chinese via jieba
    cjk = re.findall(r"[\u4e00-\u9fff]+", text)
    if cjk:
        try:
            import jieba
            for run in cjk:
                for w in jieba.lcut(run):
                    w = w.strip()
                    if w:
                        tokens.append(w)
        except ImportError:
            # fallback: single char
            for run in cjk:
                for c in run:
                    tokens.append(c)
    return tokens


def _cross_encoder_rerank(
    query: str,
    candidates: List[Dict],
    text_field: str = "content",
    score_field: str = "_rerank_score",
    model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
) -> List[Dict]:
    """
    预留：cross-encoder 重排接口。
    需要安装 sentence-transformers: pip install sentence-transformers
    """
    try:
        from sentence_transformers import CrossEncoder
    except ImportError:
        raise ImportError(
            "cross-encoder requires sentence-transformers. "
            "Install: pip install sentence-transformers"
        )

    model = CrossEncoder(model_name)
    pairs = [(query, c.get(text_field, "")) for c in candidates]
    scores = model.predict(pairs)

    for c, s in zip(candidates, scores):
        c[score_field] = float(s)
    candidates.sort(key=lambda x: x.get(score_field, 0), reverse=True)
    return candidates
