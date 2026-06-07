"""
AgentMemory v0.3 - L3 LanceDB Vector Store Layer

Provides semantic vector search using LanceDB with JSON fallback.
"""

from __future__ import annotations

import json
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


class L3LanceDBStore:
    """L3 Vector Store using LanceDB (or JSON fallback)."""
    
    def __init__(self, db_path: str = "data/lancedb", table_name: str = "memories"):
        self.db_path = db_path
        self.table_name = table_name
        self._db = None
        self._table = None
        self._use_fallback = not LANCEDB_AVAILABLE
        self._fallback_data: Dict[str, Dict[str, Any]] = {}
        
        if not self._use_fallback:
            self._init_lancedb()
        else:
            self._init_fallback()
    
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
               created_at: Optional[str] = None) -> None:
        """Insert or update a memory record."""
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
        else:
            try:
                self._table.delete(f"id = '{id}'")
            except Exception:
                pass
            
            vector_arr = np.array(vector, dtype=np.float32)
            self._table.add([{
                "id": id, "content": content, "vector": vector_arr,
                "metadata": json.dumps(metadata, ensure_ascii=False),
                "importance": float(importance), "category_path": category_path,
                "created_at": created_at,
            }])
    
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
        """Return the number of memories."""
        if self._use_fallback:
            return len(self._fallback_data)
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
