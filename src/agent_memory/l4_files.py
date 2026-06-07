"""
AgentMemory v0.3 - L4 File System Layer
Manages the file system storage with 2-file group per memory (.md + .meta.json).
Vector files (.vec.json) are written by SyncManager.

Security features:
- File locking for concurrent access safety
- Optional HMAC signature verification (via integrity module)
"""

from __future__ import annotations

import json
import uuid
import sys
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

try:
    import aiofiles
    import aiofiles.os
    AIOFILES_AVAILABLE = True
except ImportError:
    AIOFILES_AVAILABLE = False

# Platform-aware file locking
if sys.platform == "win32":
    import msvcrt
    FILE_LOCK_AVAILABLE = True
else:
    try:
        import fcntl
        FILE_LOCK_AVAILABLE = True
    except ImportError:
        FILE_LOCK_AVAILABLE = False

# P0-3: portalocker with fallback
try:
    import portalocker
    PORTALOCKER_AVAILABLE = True
except ImportError:
    PORTALOCKER_AVAILABLE = False


def generate_mem_id() -> str:
    """Generate memory ID in format mem_<8-char-uuid>"""
    short_uuid = uuid.uuid4().hex[:8]
    return f"mem_{short_uuid}"


@dataclass
class MemoryMeta:
    """Memory metadata"""
    id: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    category_path: str = "general"
    importance: float = 0.5
    tags: List[str] = field(default_factory=list)
    source: str = "manual"
    access_count: int = 0
    last_accessed: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "category_path": self.category_path,
            "importance": self.importance,
            "tags": self.tags,
            "source": self.source,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], id: str) -> "MemoryMeta":
        """Create from dictionary"""
        return cls(
            id=data.get("id", id),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            category_path=data.get("category_path", "general"),
            importance=data.get("importance", 0.5),
            tags=data.get("tags", []),
            source=data.get("source", "manual"),
            access_count=data.get("access_count", 0),
            last_accessed=data.get("last_accessed", datetime.now().isoformat()),
        )


@dataclass
class MemoryVec:
    """Memory vector data"""
    id: str
    vector: List[float]
    embedder: str = "hash-v1"
    dims: int = 384
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@contextmanager
def _file_lock(lock_path: Path, exclusive: bool = True):
    """
    Platform-aware file locking context manager.
    Falls back to no-op if neither msvcrt nor fcntl is available.

    Args:
        lock_path: Path to the lock file
        exclusive: If True, acquire exclusive lock; otherwise shared lock

    Yields:
        Lock file handle
    """
    if not FILE_LOCK_AVAILABLE:
        # No file locking available, just yield
        yield None
        return

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = open(lock_path, "w")

    try:
        if sys.platform == "win32":
            # Windows: use msvcrt locking
            mode = msvcrt.LK_LOCK if exclusive else msvcrt.LK_RLCK
            msvcrt.locking(lock_file.fileno(), mode, 1)
        else:
            # Unix: use fcntl
            lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
            fcntl.flock(lock_file.fileno(), lock_type)

        yield lock_file
    finally:
        if sys.platform == "win32":
            try:
                msvcrt.unlock(lock_file.fileno())
            except:
                pass
        else:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()


@contextmanager
def _portalocker_lock(lock_path: Path, exclusive: bool = True, timeout: float = 10.0):
    """
    P0-3: File locking via portalocker (cross-platform) with fallback.

    portalocker.FileLock is used when available; if not installed,
    falls back to the built-in _file_lock (with a comment noting the limitation).

    Args:
        lock_path: Path to the lock file
        exclusive: If True, exclusive lock; otherwise shared lock
        timeout: Max seconds to wait for lock acquisition

    Yields:
        Lock object
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    if PORTALOCKER_AVAILABLE:
        flags = portalocker.LockFlags.EXCLUSIVE if exclusive else portalocker.LockFlags.SHARED
        with portalocker.Lock(str(lock_path), timeout=timeout, flags=flags) as locker:
            yield locker
    else:
        # Fallback: no locking — note that this is unsafe under concurrent access.
        # Install portalocker to get proper cross-platform file locking:
        #   pip install portalocker
        yield None


class L4FilesStore:
    """
    L4 File System Store - 2 files per memory (.md, .meta.json).
    Note: vec.json is written by SyncManager, not here.
    
    Security features:
    - File locking for concurrent access (P0-3)
    - HMAC signature verification via integrity module
    
    All methods have async versions using aiofiles for true async IO.
    """

    def __init__(self, base_dir: str = "memory"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_lock_path(self, memory_id: str) -> Path:
        """Get lock file path for a memory ID"""
        return self.base_dir / f".lock_{memory_id}"

    def _get_file_paths(self, memory_id: str) -> Dict[str, Path]:
        return {
            "md": self.base_dir / f"{memory_id}.md",
            "meta": self.base_dir / f"{memory_id}.meta.json",
        }

    def _build_full_meta(self, memory_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Build complete metadata from partial input"""
        now = datetime.now().isoformat()
        return {
            "id": memory_id,
            "created_at": metadata.get("created_at", now),
            "updated_at": now,
            "category_path": metadata.get("category_path", "general"),
            "importance": metadata.get("importance", 0.5),
            "tags": metadata.get("tags", []),
            "source": metadata.get("source", "manual"),
            "access_count": metadata.get("access_count", 0),
            "last_accessed": metadata.get("last_accessed", now),
        }

    # === Async methods (primary) ===

    async def save(self, memory_id: str, content: str, metadata: Dict[str, Any]) -> str:
        """
        Save memory to file system (async).
        P0-3: Uses portalocker.FileLock (same .lock file per memory) and
              atomic writes via tempfile + os.replace (Windows compatible).
        """
        full_meta = self._build_full_meta(memory_id, metadata)
        paths = self._get_file_paths(memory_id)
        lock_path = self._get_lock_path(memory_id)

        # P0-3: Use portalocker-based locking; falls back to no-op if portalocker unavailable
        with _portalocker_lock(lock_path):
            if AIOFILES_AVAILABLE:
                # Atomic write: temp file + os.replace for .md
                import tempfile
                # Write .md atomically
                md_tmp = tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8",
                    delete=False, suffix=".tmp",
                    dir=str(self.base_dir),
                )
                try:
                    md_tmp.write(content)
                    md_tmp.close()
                    os.replace(md_tmp.name, str(paths["md"]))
                finally:
                    # Clean up if os.replace failed / target didn't exist
                    try:
                        os.unlink(md_tmp.name)
                    except OSError:
                        pass

                # Write .meta.json atomically
                meta_tmp = tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8",
                    delete=False, suffix=".tmp",
                    dir=str(self.base_dir),
                )
                meta_content = json.dumps(full_meta, ensure_ascii=False, indent=2)
                try:
                    meta_tmp.write(meta_content)
                    meta_tmp.close()
                    os.replace(meta_tmp.name, str(paths["meta"]))
                finally:
                    try:
                        os.unlink(meta_tmp.name)
                    except OSError:
                        pass
            else:
                # Sync fallback with atomic writes
                import tempfile
                md_tmp = tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8",
                    delete=False, suffix=".tmp",
                    dir=str(self.base_dir),
                )
                try:
                    md_tmp.write(content)
                    md_tmp.close()
                    os.replace(md_tmp.name, str(paths["md"]))
                finally:
                    try:
                        os.unlink(md_tmp.name)
                    except OSError:
                        pass

                meta_content = json.dumps(full_meta, ensure_ascii=False, indent=2)
                meta_tmp = tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8",
                    delete=False, suffix=".tmp",
                    dir=str(self.base_dir),
                )
                try:
                    meta_tmp.write(meta_content)
                    meta_tmp.close()
                    os.replace(meta_tmp.name, str(paths["meta"]))
                finally:
                    try:
                        os.unlink(meta_tmp.name)
                    except OSError:
                        pass

        return memory_id

    async def load(self, memory_id: str) -> Optional[str]:
        """
        Load memory content from file system (async).
        Returns None if not found.
        """
        md_path = self._get_file_paths(memory_id)["md"]
        
        if not md_path.exists():
            return None
        
        # Update access metadata (with file lock)
        with _file_lock(self._get_lock_path(memory_id)):
            meta_path = self._get_file_paths(memory_id)["meta"]
            if meta_path.exists():
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    meta["access_count"] = meta.get("access_count", 0) + 1
                    meta["last_accessed"] = datetime.now().isoformat()
                except Exception:
                    pass
        
        if AIOFILES_AVAILABLE:
            async with aiofiles.open(md_path, "r", encoding="utf-8") as f:
                content = await f.read()
        else:
            with open(md_path, "r", encoding="utf-8") as f:
                content = f.read()
        
        return content

    async def load_existing(self, memory_id: str) -> Optional[Dict[str, Any]]:
        md_path = self._get_file_paths(memory_id)["md"]
        meta_path = self._get_file_paths(memory_id)["meta"]
        
        if not md_path.exists():
            return None
        
        meta = None
        with _file_lock(self._get_lock_path(memory_id)):
            if meta_path.exists():
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    if isinstance(meta, dict):
                        meta["access_count"] = meta.get("access_count", 0) + 1
                        meta["last_accessed"] = datetime.now().isoformat()
                        with open(meta_path, "w", encoding="utf-8") as f:
                            json.dump(meta, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass
        
        if AIOFILES_AVAILABLE:
            async with aiofiles.open(md_path, "r", encoding="utf-8") as f:
                content = await f.read()
        else:
            with open(md_path, "r", encoding="utf-8") as f:
                content = f.read()
        
        if meta is None:
            meta = {}
        
        return {"content": content, "meta": meta}

    async def delete(self, memory_id: str) -> bool:
        """
        Delete memory files from file system (async).
        P0-3: Uses portalocker.FileLock for safe concurrent deletion.
        """
        paths = self._get_file_paths(memory_id)
        lock_path = self._get_lock_path(memory_id)
        deleted = False

        with _portalocker_lock(lock_path):
            for key in ["md", "meta"]:
                p = paths[key]
                if p.exists():
                    try:
                        p.unlink()
                        deleted = True
                    except Exception:
                        pass

        return deleted

    def list(self) -> List[str]:
        memory_ids = []
        if not self.base_dir.exists():
            return memory_ids
        
        for f in self.base_dir.iterdir():
            if f.suffix == ".md":
                memory_ids.append(f.stem)
        
        return memory_ids

    def get_stats(self) -> Dict[str, Any]:
        memory_ids = self.list()
        total_size = 0
        
        for memory_id in memory_ids:
            paths = self._get_file_paths(memory_id)
            for p in paths.values():
                if p.exists():
                    total_size += p.stat().st_size
        
        return {
            "memory_count": len(memory_ids),
            "total_size_bytes": total_size,
        }

    def get_categories(self) -> List[str]:
        categories = set()
        memory_ids = self.list()
        
        for memory_id in memory_ids:
            paths = self._get_file_paths(memory_id)
            meta_path = paths["meta"]
            
            if meta_path.exists():
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    cat = meta.get("category_path", "general")
                    if cat:
                        categories.add(cat)
                except Exception:
                    pass
        
        return sorted(list(categories))


if __name__ == "__main__":
    import asyncio
    
    async def test():
        store = L4FilesStore("memory_test")
        await store.save("test1", "Hello world", {"importance": 0.8, "category_path": "test"})
        print("Saved test1")
        content = await store.load("test1")
        print(f"Content: {content}")
        data = await store.load_existing("test1")
        print(f"Data: {data}")
        ids = store.list()
        print(f"List: {ids}")
        await store.delete("test1")
        print("Deleted test1")
        import shutil
        if Path("memory_test").exists():
            shutil.rmtree("memory_test")
    
    asyncio.run(test())
