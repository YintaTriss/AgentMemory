"""
AgentMemory v0.3 - L3 Qdrant Vector Store Layer (Edge Mode)

Provides semantic vector search using Qdrant Edge (embedded, no Docker required)
with FastEmbed for embeddings.

Qdrant Edge = Rust内核，嵌入进程，零Docker，零独立进程。
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import numpy as np

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, Filter, FieldCondition, MatchValue, PointStruct
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False

try:
    from fastembed import TextEmbedding
    FASTEMBED_AVAILABLE = True
except ImportError:
    FASTEMBED_AVAILABLE = False

# Known FastEmbed model dimensions (model_name -> vector_dim)
# Used to pre-set _vector_dim before first upsert, avoiding dimension mismatches
KNOWN_MODEL_DIMS = {
    "BAAI/bge-small-en-v1.5": 384,
    "BAAI/bge-small-zh-v1.5": 512,
    "BAAI/bge-base-en-v1.5": 768,
    "BAAI/bge-base-en": 768,
    "BAAI/bge-large-en-v1.5": 1024,
}


class L3QdrantStore:
    """L3 Vector Store using Qdrant Edge (embedded, no Docker).

    Qdrant Edge advantages:
    - Rust内核，高性能
    - 嵌入Python进程，不需要Docker/独立进程
    - 持久化存储，本地文件夹
    - 完整HNSW索引，向量搜索质量高
    - 兼容Qdrant服务器版数据格式

    Args:
        db_path: Directory for Qdrant storage (local folder).
        collection_name: Qdrant collection name.
        embedder_model: FastEmbed model name.
                       Chinese: "BAAI/bge-small-zh-v1.5" (90MB, 512维, 推荐中文)
                       English: "BAAI/bge-small-en-v1.5" (67MB, 384维)
                       English large: "BAAI/bge-base-en-v1.5" (220MB, 768维)
        vector_dim: Embedding dimension (default: 512 for bge-small-zh-v1.5).
                   bge-small-en-v1.5 uses 384.
        force_fallback: If True and Qdrant init fails, use in-memory JSON fallback.
    """

    # Default vector dimension for FastEmbed bge-small-zh-v1.5 (Chinese model).
    # NOTE: The actual dimension is set by the first upserted vector.
    # HashEmbedder uses 384; bge-small-zh-v1.5 uses 512; bge-base-en-v1.5 uses 768.
    DEFAULT_DIM = 512

    def __init__(
        self,
        db_path: str = "data/qdrant",
        collection_name: str = "memories",
        *,
        embedder_model: str = "BAAI/bge-small-zh-v1.5",
        vector_dim: Optional[int] = None,
        force_fallback: bool = False,
    ):
        self.db_path = db_path
        self.collection_name = collection_name
        self.embedder_model = embedder_model
        # If vector_dim not provided, will be auto-detected from first upsert vector
        self._vector_dim = vector_dim
        self._client: Optional[QdrantClient] = None
        self._embedder: Optional[TextEmbedding] = None
        self._use_fallback = False
        self._fallback_data: Dict[str, Any] = {}
        self._fallback_path: Optional[Path] = None
        self._collection_created = False

        if force_fallback or not QDRANT_AVAILABLE:
            self._use_fallback = True
            self._init_fallback()
        else:
            self._init_qdrant()

    def _init_qdrant(self) -> None:
        """Initialize Qdrant Edge client with local persistent storage."""
        try:
            storage_path = Path(self.db_path).resolve()
            storage_path.mkdir(parents=True, exist_ok=True)

            # Qdrant Edge: use path= for local file storage (no Docker, no network)
            self._client = QdrantClient(
                path=str(storage_path),
            )

            # FastEmbed is optional — used for hybrid search if available.
            # If it fails, the manager's embedder provides vectors.
            if FASTEMBED_AVAILABLE:
                try:
                    self._embedder = TextEmbedding(model_name=self.embedder_model)
                    # Set _vector_dim based on known model dimensions to avoid
                    # relying solely on auto-detection from first upsert
                    self._vector_dim = self._vector_dim or KNOWN_MODEL_DIMS.get(
                        self.embedder_model, self.DEFAULT_DIM
                    )
                except Exception:
                    self._embedder = None
            else:
                self._embedder = None

        except Exception as e:
            self._use_fallback = True
            self._init_fallback()

    def _ensure_collection(self, vector_dim: int) -> None:
        """Lazily create the Qdrant collection with the given vector dimension."""
        if self._collection_created:
            return
        try:
            collections = self._client.get_collections().collections
            collection_names = [c.name for c in collections]
            if self.collection_name not in collection_names:
                self._client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=vector_dim,
                        distance=Distance.COSINE,
                    ),
                )
                self._collection_created = True
        except Exception as e:
            # Collection may already exist (race condition or same-name check)
            # Mark as created to avoid repeated attempts
            self._collection_created = True

    def _init_fallback(self) -> None:
        """Initialize in-memory JSON fallback when Qdrant is unavailable."""
        self._fallback_path = Path(self.db_path).parent / "qdrant_fallback.json"
        self._fallback_path.parent.mkdir(parents=True, exist_ok=True)
        self._fallback_data = {}
        self._load_fallback()

    def _load_fallback(self) -> None:
        if self._fallback_path and self._fallback_path.exists():
            try:
                with open(self._fallback_path, "r", encoding="utf-8") as f:
                    self._fallback_data = json.load(f)
            except Exception:
                self._fallback_data = {}

    def _save_fallback(self) -> None:
        if self._fallback_path:
            with open(self._fallback_path, "w", encoding="utf-8") as f:
                json.dump(self._fallback_data, f, ensure_ascii=False, indent=2)

    @property
    def is_using_fallback(self) -> bool:
        return self._use_fallback

    def _parse_filter_expr(self, filter_expr: Optional[str]) -> Optional[Filter]:
        """Parse LanceDB-style filter expression to Qdrant Filter.

        Supports: category_path = 'value'
        Example: "category_path = '测试/石榴籽'" -> Filter(category_path='测试/石榴籽')
        """
        if not filter_expr:
            return None

        try:
            # Simple parse: "category_path = 'value'" or 'category_path = "value"'
            parts = filter_expr.split("=")
            if len(parts) != 2:
                return None

            field = parts[0].strip()
            value = parts[1].strip().strip("'").strip('"')

            if not field or not value:
                return None

            return Filter(
                must=[
                    FieldCondition(
                        key=field,
                        match=MatchValue(value=value),
                    )
                ]
            )
        except Exception:
            return None

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts using FastEmbed.

        Returns list of normalized vectors.
        """
        if self._use_fallback or self._embedder is None:
            dim = self._vector_dim or DEFAULT_DIM
            return [[0.0] * dim] * len(texts)

        try:
            vectors = list(self._embedder.embed(texts))
            normalized = []
            for v in vectors:
                norm = np.linalg.norm(v)
                if norm > 0:
                    v = v / norm
                normalized.append(v.tolist())
            return normalized
        except Exception as e:
            dim = self._vector_dim or DEFAULT_DIM
            return [[0.0] * dim] * len(texts)

    def _zero_vector(self) -> List[float]:
        return [0.0] * (self._vector_dim or DEFAULT_DIM)

    def upsert(
        self,
        id: str,
        content: str,
        vector: List[float],
        metadata: Optional[Dict[str, Any]] = None,
        importance: float = 0.5,
        category_path: str = "general",
        created_at: Optional[str] = None,
    ) -> bool:
        """Insert or update a memory record.

        Returns True on success, False on failure.
        """
        if created_at is None:
            created_at = datetime.now().isoformat()
        if metadata is None:
            metadata = {}

        if self._use_fallback:
            self._fallback_data[id] = {
                "id": id,
                "content": content,
                "vector": vector,
                "metadata": json.dumps(metadata, ensure_ascii=False),
                "importance": importance,
                "category_path": category_path,
                "created_at": created_at,
            }
            self._save_fallback()
            return True

        try:
            # Ensure vector is correct length and normalized
            vec = np.array(vector, dtype=np.float32)
            actual_dim = len(vec)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm

            # Lazily create collection with correct dimension on first upsert
            self._ensure_collection(actual_dim)
            self._vector_dim = actual_dim

            payload = {
                "id": id,
                "content": content,
                "metadata": json.dumps(metadata, ensure_ascii=False),
                "importance": float(importance),
                "category_path": category_path,
                "created_at": created_at,
            }

            self._client.upsert(
                collection_name=self.collection_name,
                points=[
                    PointStruct(
                        id=self._mem_id_to_point_id(id),
                        vector=vec.tolist(),
                        payload=payload,
                    )
                ],
                wait=True,  # Ensure data is flushed to disk in local mode
            )
            return True

        except Exception as e:
            return False

    def _mem_id_to_point_id(self, mem_id: str) -> str:
        """Derive a deterministic UUID from a memory ID for Qdrant point ID."""
        return str(uuid.UUID(bytes=uuid.uuid5(uuid.NAMESPACE_DNS, mem_id).bytes[:16]))

    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filter_expr: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search for similar memories by vector.

        Args:
            query_vector: Query embedding vector.
            top_k: Maximum number of results to return.
            filter_expr: LanceDB-style filter expression (e.g. "category_path = '测试'").

        Returns:
            List of dicts with keys: id, content, score, metadata, importance, category_path, created_at.
        """
        if self._use_fallback:
            return self._search_fallback(query_vector, top_k, filter_expr)

        try:
            # Normalize query vector
            vec = np.array(query_vector, dtype=np.float32)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm

            qdrant_filter = self._parse_filter_expr(filter_expr)

            # Use query_points (works in local/embedded mode)
            results = self._client.query_points(
                collection_name=self.collection_name,
                query=vec.tolist(),
                limit=top_k,
                query_filter=qdrant_filter,
                with_payload=True,
            )

            formatted = []
            for r in results.points:
                payload = r.payload or {}
                metadata = payload.get("metadata", "{}")
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except Exception:
                        metadata = {}
                formatted.append({
                    "id": payload.get("id", ""),
                    "content": payload.get("content", ""),
                    "score": r.score,
                    "metadata": metadata,
                    "importance": payload.get("importance", 0.5),
                    "category_path": payload.get("category_path", ""),
                    "created_at": payload.get("created_at", ""),
                })

            return formatted

        except Exception as e:
            return self._search_fallback(query_vector, top_k, filter_expr)

    def _search_fallback(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filter_expr: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fallback search using JSON storage + cosine similarity."""
        if not self._fallback_data:
            return []

        results = []
        query_arr = np.array(query_vector, dtype=np.float32)
        qnorm = np.linalg.norm(query_arr)
        if qnorm == 0:
            qnorm = 1.0

        for id_val, data in self._fallback_data.items():
            # Handle category filter
            if filter_expr and "category_path" in filter_expr:
                parts = filter_expr.split("=")
                if len(parts) >= 2:
                    filter_val = parts[1].strip().strip("'").strip('"')
                    if filter_val and data.get("category_path") != filter_val:
                        continue

            vec = np.array(data.get("vector", []), dtype=np.float32)
            # Skip vectors with dimension mismatch (protect against old data残留)
            if len(vec) != len(query_arr):
                continue
            if len(vec) == 0:
                continue
            norm = np.linalg.norm(vec)
            if norm == 0:
                continue

            score = float(np.dot(query_arr, vec) / (qnorm * norm))
            metadata = data.get("metadata", "{}")
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except Exception:
                    metadata = {}

            results.append({
                "id": id_val,
                "content": data.get("content", ""),
                "score": score,
                "metadata": metadata,
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

        try:
            point_id = self._mem_id_to_point_id(id)
            self._client.delete(
                collection_name=self.collection_name,
                points_selector=[point_id],
                wait=True,  # Ensure deletion is processed before returning
            )
            return True
        except Exception as e:
            return False

    def count(self) -> int:
        """Return the number of memories."""
        if self._use_fallback:
            return len(self._fallback_data)

        try:
            info = self._client.get_collection(self.collection_name)
            return info.points_count
        except Exception:
            return len(self._fallback_data)

    def get_all(self) -> List[Dict[str, Any]]:
        """Get all memories (for debugging/testing)."""
        if self._use_fallback:
            return list(self._fallback_data.values())

        try:
            results = self._client.scroll(
                collection_name=self.collection_name,
                limit=10000,
                with_payload=True,
            )
            records = []
            for point in results[0]:
                payload = point.payload or {}
                metadata = payload.get("metadata", "{}")
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except Exception:
                        metadata = {}
                records.append({
                    "id": payload.get("id", str(point.id)),
                    "content": payload.get("content", ""),
                    "vector": point.vector if hasattr(point, "vector") else [],
                    "metadata": metadata,
                    "importance": payload.get("importance", 0.5),
                    "category_path": payload.get("category_path", ""),
                    "created_at": payload.get("created_at", ""),
                })
            return records
        except Exception:
            return list(self._fallback_data.values())

    def drop_table(self) -> None:
        """Drop the collection (for testing purposes)."""
        if self._use_fallback:
            self._fallback_data = {}
            self._save_fallback()
            return

        try:
            self._client.delete_collection(self.collection_name)
        except Exception:
            pass  # Silently ignore drop errors

    def get_embedder(self):
        """Return the FastEmbed embedder instance (for direct use by manager)."""
        return self._embedder
