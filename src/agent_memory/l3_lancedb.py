"""
AgentMemory v0.3 - L3 LanceDB Vector Store Layer

Provides semantic vector search using LanceDB with JSON fallback,
and optional BM25 hybrid retrieval.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import numpy as np

try:
    import lancedb
    import pyarrow as pa
    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False


# ============================================================================
# BM25 Indexer — pure Python, zero extra dependencies
# ============================================================================

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
        """Split text into lowercase tokens ( alphanumeric runs)."""
        return re.findall(r"[a-z0-9]+", text.lower())

    def _compute_idf(self, term_doc_freq: Counter) -> Dict[str, float]:
        """Compute IDF for each term: log((N - n_t + 0.5) / (n_t + 0.5) + 1)."""
        N = len(self._docs)
        idf = {}
        for term, df in term_doc_freq.items():
            # BM25 IDF formula (Lucene variant)
            idf[term] = math.log((N - df + 0.5) / (df + 0.5) + 1.0)
        return idf

    def index(self, texts: List[str]) -> None:
        """Build the BM25 index from a list of documents."""
        self._docs = texts
        self._doc_tokens = [self._tokenize(t) for t in texts]
        self._doc_len = [len(toks) for toks in self._doc_tokens]
        self._avgdl = sum(self._doc_len) / max(len(self._doc_len), 1)

        # Document frequency for each term
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
                doc_len_norm = self.k1 * (1.0 - self.b + self.b * self._doc_len[i] / max(self._avgdl, 1))
                score = idf * (tf * (self.k1 + 1.0)) / (tf + doc_len_norm)
                scores[i] += score

        # Pair (index, score) and sort descending
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


class L3LanceDBStore:
    """L3 Vector Store using LanceDB (or JSON fallback).

    Args:
        db_path: Directory for LanceDB or fallback JSON.
        table_name: LanceDB table name.
        force_fallback: If True, always use JSON fallback even if LanceDB is available.
    """

    def __init__(
        self,
        db_path: str = "data/lancedb",
        table_name: str = "memories",
        *,  # force keyword-only
        force_fallback: bool = False,
    ):
        self.db_path = db_path
        self.table_name = table_name
        self._db = None
        self._table = None

        if force_fallback:
            self._use_fallback = True
            self._init_fallback()
        elif not LANCEDB_AVAILABLE:
            self._use_fallback = True
            self._init_fallback()
        else:
            self._use_fallback = False
            self._init_lancedb()
    
    def _get_schema(self) -> pa.Schema:
        """Get PyArrow schema for LanceDB table."""
        return pa.schema([
            ("id", pa.string()),
            ("content", pa.string()),
            ("vector", pa.list_(pa.float32())),
            ("metadata", pa.string()),
            ("importance", pa.float32()),
            ("category_path", pa.string()),
            ("created_at", pa.string()),
        ])
    
    def _init_lancedb(self) -> None:
        try:
            db_path = Path(self.db_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._db = lancedb.connect(str(db_path))
            
            if self.table_name not in self._db.table_names():
                schema = self._get_schema()
                self._table = self._db.create_table(self.table_name, schema=schema)
            else:
                self._table = self._db.open_table(self.table_name)
        except Exception as e:
            print(f"[L3] LanceDB init failed: {e}, falling back to JSON")
            self._use_fallback = True
            self._init_fallback()
    
    def _init_fallback(self) -> None:
        self._fallback_path = Path(self.db_path).parent / "lancedb_fallback.json"
        self._fallback_path.parent.mkdir(parents=True, exist_ok=True)
        self._fallback_data = {}
        self._load_fallback()
    
    def _load_fallback(self) -> None:
        if self._fallback_path.exists():
            try:
                with open(self._fallback_path, "r", encoding="utf-8") as f:
                    self._fallback_data = json.load(f)
            except Exception:
                self._fallback_data = {}
    
    def _save_fallback(self) -> None:
        with open(self._fallback_path, "w", encoding="utf-8") as f:
            json.dump(self._fallback_data, f, ensure_ascii=False, indent=2)
    
    @property
    def table(self):
        return self._table
    
    @property
    def is_using_fallback(self) -> bool:
        return self._use_fallback
    
    def upsert(self, id: str, content: str, vector: List[float],
               metadata: Optional[Dict[str, Any]] = None,
               importance: float = 0.5, category_path: str = "general",
               created_at: Optional[str] = None) -> bool:
        """
        Insert or update a memory record.

        Returns True on success, False on failure.
        P1-10 fix: now returns bool so callers (e.g. sync.py) can detect
        and handle L3 upsert failures.
        """
        if created_at is None:
            created_at = datetime.now().isoformat()
        if metadata is None:
            metadata = {}

        if self._use_fallback:
            self._fallback_data[id] = {
                "id": id, "content": content, "vector": vector,
                "metadata": json.dumps(metadata, ensure_ascii=False),
                "importance": importance, "category_path": category_path,
                "created_at": created_at,
            }
            self._save_fallback()
            return True
        else:
            try:
                self._table.delete(f"id = '{id}'")
            except Exception:
                pass

            try:
                vector_arr = np.array(vector, dtype=np.float32)
                self._table.add([{
                    "id": id, "content": content, "vector": vector_arr,
                    "metadata": json.dumps(metadata, ensure_ascii=False),
                    "importance": float(importance), "category_path": category_path,
                    "created_at": created_at,
                }])
                return True
            except Exception as e:
                print(f"[L3] upsert error for {id}: {e}")
                return False
    
    def search(self, query_vector: List[float], top_k: int = 5,
               filter_expr: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for similar memories by vector."""
        if self._use_fallback:
            return self._search_fallback(query_vector, top_k, filter_expr)
        
        try:
            query_arr = np.array(query_vector, dtype=np.float32)
            # LanceDB 0.30+ requires explicit vector_column_name parameter
            query = self._table.search(query_arr, vector_column_name="vector")
            if filter_expr:
                query = query.where(filter_expr)
            results = query.limit(top_k).to_list()
            formatted = []
            for r in results:
                metadata = r.get("metadata", "{}")
                if isinstance(metadata, str):
                    metadata = json.loads(metadata)
                formatted.append({
                    "id": r.get("id", ""), "content": r.get("content", ""),
                    "score": r.get("_score", 0.0), "metadata": metadata,
                    "importance": r.get("importance", 0.5),
                    "category_path": r.get("category_path", ""),
                    "created_at": r.get("created_at", ""),
                })
            formatted.sort(key=lambda x: x["score"], reverse=True)
            return formatted
        except Exception as e:
            print(f"[L3] Search error: {e}")
            # Fallback to JSON search on error
            if not hasattr(self, "_fallback_data"):
                self._init_fallback()
            return self._search_fallback(query_vector, top_k, filter_expr)
    
    def _search_fallback(self, query_vector: List[float], top_k: int = 5,
                        filter_expr: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fallback search using JSON storage."""
        if not self._fallback_data:
            return []
        
        results = []
        query_arr = np.array(query_vector, dtype=np.float32)
        query_norm = np.linalg.norm(query_arr)
        
        for id_val, data in self._fallback_data.items():
            # Handle category filter
            if filter_expr and "category_path" in filter_expr:
                parts = filter_expr.split("=")
                if len(parts) >= 2:
                    filter_val = parts[1].strip().strip("'").strip('"')
                    if filter_val and data.get("category_path") != filter_val:
                        continue
            
            vec = np.array(data.get("vector", []), dtype=np.float32)
            if len(vec) == 0:
                continue
            norm = np.linalg.norm(vec)
            if norm == 0:
                continue
            # Cosine similarity
            score = float(np.dot(query_arr, vec) / (query_norm * norm))
            metadata = data.get("metadata", "{}")
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except Exception:
                    metadata = {}
            results.append({
                "id": id_val, "content": data.get("content", ""),
                "score": score, "metadata": metadata,
                "importance": data.get("importance", 0.5),
                "category_path": data.get("category_path", ""),
                "created_at": data.get("created_at", ""),
            })
        
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
    
    def delete(self, id: str) -> bool:
        """Delete a memory by ID."""
        if self._use_fallback:
            if id in self._fallback_data:
                del self._fallback_data[id]
                self._save_fallback()
                return True
            return False
        # P0-4 fix: main path must return bool, not None
        try:
            self._table.delete(f"id = '{id}'")
            return True
        except Exception as e:
            print(f"[L3] Delete error: {e}")
            return False


    def count(self) -> int:
        """Return the number of memories.

        P2-1 fix: try count_rows() first (O(1) in LanceDB 0.4+), fall back
        to len(to_list()) only when unavailable.
        """
        if self._use_fallback:
            return len(self._fallback_data)
        try:
            # LanceDB 0.4+ has count_rows() — use it when available
            return self._table.count_rows()
        except AttributeError:
            # count_rows not available in older LanceDB versions
            pass
        except Exception:
            pass
        try:
            return len(self._table.to_list())
        except Exception:
            return len(self._fallback_data)
    
    def drop_table(self) -> None:
        """Drop the table (for testing purposes)."""
        if self._use_fallback:
            self._fallback_data = {}
            self._save_fallback()
        else:
            try:
                self._db.drop_table(self.table_name)
            except Exception as e:
                print(f"[L3] Drop table error: {e}")
    
    def get_all(self) -> List[Dict[str, Any]]:
        """Get all memories (for debugging/testing)."""
        if self._use_fallback:
            return list(self._fallback_data.values())
        try:
            return self._table.to_list()
        except Exception:
            return list(self._fallback_data.values())

    def search_bm25(self, query: str, top_k: int = 5,
                   k1: float = 1.2, b: float = 0.75) -> List[Dict[str, Any]]:
        """Pure-BM25 keyword search across all stored content.

        Args:
            query: Search query text.
            top_k: Number of top results to return.
            k1: BM25 term frequency saturation parameter (default 1.2).
                Higher values give more weight to term frequency.
            b: BM25 document length normalization parameter (default 0.75).
                Higher values penalize longer documents more.

        Falls back to an empty list if no documents are indexed.
        """
        all_records = self.get_all()
        if not all_records:
            return []

        texts = [r.get("content", "") or "" for r in all_records]
        # P2-9 fix: k1 and b are now configurable (were hardcoded)
        indexer = BM25Indexer(k1=k1, b=b)
        indexer.index(texts)
        bm25_results = indexer.search(query, top_k=top_k)

        # Map back to full record fields
        results = []
        for bm in bm25_results:
            rec = all_records[bm["doc_index"]]
            metadata = rec.get("metadata", "{}")
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except Exception:
                    metadata = {}
            results.append({
                "id": rec.get("id", ""),
                "content": rec.get("content", ""),
                "score": bm["bm25_score"],
                "bm25_score": bm["bm25_score"],
                "metadata": metadata,
                "importance": rec.get("importance", 0.5),
                "category_path": rec.get("category_path", ""),
                "created_at": rec.get("created_at", ""),
            })
        return results

    def search_hybrid(
        self,
        query_vector: List[float],
        query_text: str,
        top_k: int = 5,
        alpha: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """Hybrid search: combine vector similarity and BM25 scores.

        Args:
            query_vector: Pre-computed embedding of the query.
            query_text: Raw query text for BM25.
            top_k: Number of results to return.
            alpha: Vector weight (0-1). BM25 weight = 1-alpha.
                Default 0.7 —偏向语义。
        """
        vec_results = self.search(query_vector, top_k=top_k * 2)
        bm25_results = self.search_bm25(query_text, top_k=top_k * 2)

        # Normalize vector scores to [0,1] via max
        if vec_results:
            max_vec = max(r.get("score", 0.0) for r in vec_results)
        else:
            max_vec = 1.0
        if bm25_results:
            max_bm = max(r.get("bm25_score", 0.0) for r in bm25_results)
        else:
            max_bm = 1.0

        # Build score maps
        vec_map = {r["id"]: r.get("score", 0.0) / max_vec for r in vec_results}
        bm_map = {r["id"]: r.get("bm25_score", 0.0) / max_bm for r in bm25_results}

        # Union of all IDs
        all_ids = set(vec_map) | set(bm_map)
        hybrid_scores = []
        for mid in all_ids:
            vs = vec_map.get(mid, 0.0)
            bs = bm_map.get(mid, 0.0)
            combined = alpha * vs + (1.0 - alpha) * bs
            hybrid_scores.append((mid, combined))

        hybrid_scores.sort(key=lambda x: x[1], reverse=True)

        # Build result list preserving full record data
        id_to_vec = {r["id"]: r for r in vec_results}
        id_to_bm = {r["id"]: r for r in bm25_results}
        output = []
        for mid, score in hybrid_scores[:top_k]:
            vr = id_to_vec.get(mid, {})
            br = id_to_bm.get(mid, {})
            metadata = vr.get("metadata") or br.get("metadata", {})
            output.append({
                "id": mid,
                "content": vr.get("content") or br.get("content", ""),
                "score": round(score, 6),
                "vector_score": vr.get("score", 0.0),
                "bm25_score": br.get("bm25_score", 0.0),
                "metadata": metadata,
                "importance": vr.get("importance") or br.get("importance", 0.5),
                "category_path": vr.get("category_path") or br.get("category_path", ""),
                "created_at": vr.get("created_at") or br.get("created_at", ""),
            })
        return output
