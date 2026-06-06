"""
AgentMemory v0.3 - L3 LanceDB Vector Store Layer

Provides semantic search via vector embeddings.
Uses LanceDB for local vector storage (no server required).

Note: LanceDB is optional. If not installed, falls back to simple JSON storage.
"""

import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
import hashlib

try:
    import lancedb
    from lancedb.embeddings import getEmbeddingFunction
    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False


class SimpleVectorStore:
    """
    Simple JSON-based vector store (fallback when LanceDB unavailable).
    
    Uses hash-based "vectors" for simple text matching.
    """
    
    def __init__(self, storage_path: str = "data/vectors.json"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._load()
    
    def _load(self):
        """Load vectors from disk."""
        if self.storage_path.exists():
            with open(self.storage_path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = {}
    
    def _save(self):
        """Save vectors to disk."""
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def _text_to_hash_vector(self, text: str, dims: int = 1536) -> List[float]:
        """Convert text to a hash-based pseudo-vector for simple matching."""
        text_hash = hashlib.sha256(text.encode()).digest()
        vector = []
        for i in range(min(dims, len(text_hash) * 8)):
            byte_idx = i // 8
            bit_idx = i % 8
            if byte_idx < len(text_hash):
                vector.append((text_hash[byte_idx] >> bit_idx) & 1)
            else:
                vector.append(0)
        # Normalize to -1 to 1 range
        return [v * 2 - 1 for v in vector]
    
    def upsert(self, memory_id: str, content: str, vector: List[float] = None):
        """Insert or update a memory vector."""
        if vector is None:
            vector = self._text_to_hash_vector(content)
        
        self.data[memory_id] = {
            "content": content,
            "vector": vector,
        }
        self._save()
    
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for similar memories using simple text matching."""
        results = []
        query_words = set(query.lower().split())
        
        for memory_id, data in self.data.items():
            content_lower = data["content"].lower()
            content_words = set(content_lower.split())
            
            # Simple word overlap score
            if query_words & content_words:
                overlap = len(query_words & content_words)
                score = overlap / max(len(query_words), 1)
                results.append({
                    "id": memory_id,
                    "content": data["content"],
                    "score": score,
                })
        
        # Sort by score
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
    
    def delete(self, memory_id: str) -> bool:
        """Delete a memory vector."""
        if memory_id in self.data:
            del self.data[memory_id]
            self._save()
            return True
        return False
    
    def get_all_ids(self) -> List[str]:
        """Get all memory IDs."""
        return list(self.data.keys())
    
    def count(self) -> int:
        """Get total count."""
        return len(self.data)


class L3LanceDBStore:
    """
    L3 Vector Store using LanceDB (or SimpleVectorStore fallback).
    
    Provides semantic search via embeddings.
    """
    
    def __init__(self, storage_path: str = "data/lancedb", embedder: str = "hash"):
        """
        Initialize L3 vector store.
        
        Args:
            storage_path: Path for LanceDB storage
            embedder: Embedder type ("hash", "openai", "dashscope", "local")
        """
        self.storage_path = storage_path
        self.embedder = embedder
        
        if LANCEDB_AVAILABLE and embedder != "hash":
            self._init_lancedb()
        else:
            # Use simple JSON fallback
            json_path = str(Path(storage_path).parent / "vectors.json")
            self.vector_store = SimpleVectorStore(json_path)
    
    def _init_lancedb(self):
        """Initialize LanceDB with embedding function."""
        # Configure embedding function based on type
        if self.embedder == "openai":
            self.embedding_function = getEmbeddingFunction("openai")
        elif self.embedder == "dashscope":
            # DashScope uses text2vec model
            self.embedding_function = getEmbeddingFunction("text2vec")
        else:
            self.embedding_function = None
        
        # Initialize LanceDB
        db_path = Path(self.storage_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = lancedb.connect(str(db_path))
        
        # Create or open table
        if "memories" in self.db.table_names():
            self.table = self.db.open_table("memories")
        else:
            schema = {
                "vector": self.embedding_function,
                "text": "string",
                "memory_id": "string",
            }
            self.table = self.db.create_table("memories", schema=schema)
    
    def upsert(self, memory_id: str, content: str, vector: List[float] = None):
        """
        Insert or update a memory vector.
        
        Args:
            memory_id: Unique memory ID
            content: Memory content
            vector: Pre-computed vector (optional)
        """
        if hasattr(self, 'table'):
            # LanceDB mode
            self.table.insert({
                "memory_id": memory_id,
                "text": content,
            })
        else:
            # Simple fallback
            self.vector_store.upsert(memory_id, content, vector)
    
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for similar memories.
        
        Args:
            query: Query text
            top_k: Number of results
        
        Returns:
            List of matching memories with scores
        """
        if hasattr(self, 'table'):
            # LanceDB mode
            results = self.table.search(query, limit=top_k).to_list()
            return [{"id": r["memory_id"], "content": r["text"], "score": r.get("_score", 0)} for r in results]
        else:
            # Simple fallback
            return self.vector_store.search(query, top_k)
    
    def delete(self, memory_id: str) -> bool:
        """Delete a memory vector."""
        if hasattr(self, 'table'):
            self.table.delete(f"memory_id = '{memory_id}'")
            return True
        else:
            return self.vector_store.delete(memory_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics."""
        if hasattr(self, 'table'):
            return {
                "memory_count": self.table.count_rows(),
                "engine": "lancedb",
            }
        else:
            return {
                "memory_count": self.vector_store.count(),
                "engine": "simple-json",
            }
