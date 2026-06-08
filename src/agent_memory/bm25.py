"""
AgentMemory v0.3 - Pure Python BM25 Indexer

Zero extra dependencies. Used as fallback when vector search returns
zero-quality scores, and for keyword-only search mode (--mode bm25).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import List, Dict, Any


class BM25Indexer:
    """Pure-Python BM25 indexer for keyword search.

    Scoring formula (Lucene BM25):
        score = IDF(t) * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * |d| / avgdl))

    Attributes:
        k1: Term frequency saturation parameter (default 1.2).
        b:  Document length normalization (default 0.75).
    """

    def __init__(self, k1: float = 1.2, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._docs: List[str] = []        # original texts
        self._doc_tokens: List[List[str]] = []  # tokenized
        self._doc_len: List[int] = []     # token counts
        self._avgdl: float = 0.0
        self._idf: Dict[str, float] = {}  # term -> IDF

    def _tokenize(self, text: str) -> List[str]:
        """
        Split text into tokens.
        - English/alphanumeric: lowercase runs
        - Chinese/CJK: character bigrams for sub-word matching
        """
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        # Chinese/CJK characters: collect runs of non-ASCII chars
        cjk_runs = re.findall(
            r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff\u3000-\u303f\uff00-\uffef]+",
            text,
        )
        for run in cjk_runs:
            for i in range(len(run) - 1):
                tokens.append(run[i : i + 2])
        return tokens

    def _compute_idf(self, term_doc_freq: Counter) -> Dict[str, float]:
        """Compute IDF for each term: log((N - n_t + 0.5) / (n_t + 0.5) + 1)."""
        N = len(self._docs)
        idf = {}
        for term, df in term_doc_freq.items():
            idf[term] = math.log((N - df + 0.5) / (df + 0.5) + 1.0)
        return idf

    def index(self, texts: List[str]) -> None:
        """Build the BM25 index from a list of documents."""
        self._docs = texts
        self._doc_tokens = [self._tokenize(t) for t in texts]
        self._doc_len = [len(toks) for toks in self._doc_tokens]
        self._avgdl = sum(self._doc_len) / max(len(self._doc_len), 1)

        term_doc_freq: Counter = Counter()
        for tokens in self._doc_tokens:
            for term in set(tokens):
                term_doc_freq[term] += 1

        self._idf = self._compute_idf(term_doc_freq)

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Score all documents against *query* and return top-k results.

        Returns list of dicts with keys: doc_index, doc_text, bm25_score.
        """
        if not self._docs or not self._idf:
            return []

        query_tokens = self._tokenize(query)
        scores: List[float] = [0.0] * len(self._docs)

        for term in query_tokens:
            if term not in self._idf:
                continue
            idf = self._idf[term]
            for i, tokens in enumerate(self._doc_tokens):
                tf = tokens.count(term)
                if tf == 0:
                    continue
                doc_len_norm = self.k1 * (
                    1.0 - self.b + self.b * self._doc_len[i] / max(self._avgdl, 1)
                )
                score = idf * (tf * (self.k1 + 1.0)) / (tf + doc_len_norm)
                scores[i] += score

        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        results = []
        for idx, score in ranked[:top_k]:
            if score > 0:
                results.append({
                    "doc_index": idx,
                    "doc_text": self._docs[idx],
                    "bm25_score": round(score, 6),
                })
        return results
