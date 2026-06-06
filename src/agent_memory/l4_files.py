"""
AgentMemory v0.3 - L4 File System Layer

Manages the file system storage with 3-file group per memory:
- <id>.md - Raw content (human-readable)
- <id>.vec.json - Vector data (embedding)
- <id>.meta.json - Metadata (timestamp, tags, category, source)

Design: Memory as Library
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict


@dataclass
class MemoryMeta:
    """Memory metadata"""
    id: str
    created_at: str
    updated_at: str
    category: str = "general"
    tags: List[str] = None
    source: str = "manual"
    importance: float = 0.5
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'MemoryMeta':
        return cls(**data)


@dataclass
class MemoryVec:
    """Memory vector data"""
    id: str
    vector: List[float]
    embedder: str = "hash"
    dims: int = 1536
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'MemoryVec':
        return cls(**data)


class L4FilesStore:
    """
    L4 File System Store
    
    Each memory = 3 files in the same directory:
    - <id>.md - Raw content
    - <id>.vec.json - Vector data
    - <id>.meta.json - Metadata
    """
    
    def __init__(self, memory_dir: str = "memory"):
        """
        Initialize L4 file store.
        
        Args:
            memory_dir: Directory for memory storage
        """
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_file_paths(self, memory_id: str) -> Dict[str, Path]:
        """Get paths for all 3 files of a memory."""
        return {
            "md": self.memory_dir / f"{memory_id}.md",
            "vec": self.memory_dir / f"{memory_id}.vec.json",
            "meta": self.memory_dir / f"{memory_id}.meta.json",
        }
    
    def save(self, memory_id: str, content: str, meta: MemoryMeta, vec: MemoryVec) -> str:
        """
        Save memory with all 3 files.
        
        Args:
            memory_id: Unique memory ID
            content: Raw content (markdown)
            meta: Metadata
            vec: Vector data
        
        Returns:
            memory_id: The saved memory ID
        """
        paths = self._get_file_paths(memory_id)
        
        # Save .md file
        with open(paths["md"], "w", encoding="utf-8") as f:
            f.write(content)
        
        # Save .vec.json file
        with open(paths["vec"], "w", encoding="utf-8") as f:
            json.dump(vec.to_dict(), f, ensure_ascii=False, indent=2)
        
        # Save .meta.json file
        with open(paths["meta"], "w", encoding="utf-8") as f:
            json.dump(meta.to_dict(), f, ensure_ascii=False, indent=2)
        
        return memory_id
    
    def load(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """
        Load memory by ID.
        
        Args:
            memory_id: Memory ID
        
        Returns:
            Dict with content, meta, vec or None if not found
        """
        paths = self._get_file_paths(memory_id)
        
        # Check if .md exists
        if not paths["md"].exists():
            return None
        
        # Read all 3 files
        with open(paths["md"], "r", encoding="utf-8") as f:
            content = f.read()
        
        with open(paths["vec"], "r", encoding="utf-8") as f:
            vec_data = json.load(f)
        
        with open(paths["meta"], "r", encoding="utf-8") as f:
            meta_data = json.load(f)
        
        return {
            "id": memory_id,
            "content": content,
            "meta": MemoryMeta.from_dict(meta_data),
            "vec": MemoryVec.from_dict(vec_data),
        }
    
    def list(self) -> List[str]:
        """
        List all memory IDs.
        
        Returns:
            List of memory IDs
        """
        ids = set()
        for f in self.memory_dir.glob("*.md"):
            ids.add(f.stem)
        return sorted(list(ids))
    
    def delete(self, memory_id: str) -> bool:
        """
        Delete memory (all 3 files).
        
        Args:
            memory_id: Memory ID
        
        Returns:
            True if deleted, False if not found
        """
        paths = self._get_file_paths(memory_id)
        
        if not paths["md"].exists():
            return False
        
        # Delete all 3 files
        for path in paths.values():
            if path.exists():
                path.unlink()
        
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about L4 storage.
        
        Returns:
            Statistics dict
        """
        ids = self.list()
        total_size = 0
        
        for memory_id in ids:
            paths = self._get_file_paths(memory_id)
            for path in paths.values():
                if path.exists():
                    total_size += path.stat().st_size
        
        return {
            "memory_count": len(ids),
            "total_size_bytes": total_size,
            "storage_dir": str(self.memory_dir),
        }
    
    def get_categories(self) -> List[str]:
        """
        Get all unique categories.
        
        Returns:
            List of categories
        """
        categories = set()
        for memory_id in self.list():
            paths = self._get_file_paths(memory_id)
            if paths["meta"].exists():
                with open(paths["meta"], "r", encoding="utf-8") as f:
                    meta_data = json.load(f)
                    if "category" in meta_data:
                        categories.add(meta_data["category"])
        return sorted(list(categories))
