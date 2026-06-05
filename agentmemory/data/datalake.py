"""
DataLake - 数据湖核心模块
Version: v2.0 - Fixed + Permission Integration
"""

import asyncio
import json
import shutil
from pathlib import Path
from typing import Optional, List, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime
from ulid import ULID

import aiofiles

if TYPE_CHECKING:
    from agentmemory.agent_permissions.permissions import PermissionEngine
    from agentmemory.ai.classifier import AutoClassifier, ClassificationRecommendation


@dataclass
class MemoryFile:
    memory_id: str
    category_path: str
    created_at: datetime
    updated_at: datetime
    content_hash: Optional[str] = None


@dataclass
class MemoryContent:
    memory_id: str
    content: str
    metadata: dict = field(default_factory=dict)


@dataclass
class MemoryVector:
    memory_id: str
    vector: list[float]
    model: str
    dimensions: int


@dataclass
class MemoryMeta:
    memory_id: str
    category_path: str
    tags: list[str] = field(default_factory=list)
    importance: float = 1.0
    created_at: str = ""
    updated_at: str = ""
    embedding_state: str = "pending"
    retry_count: int = 0
    
    def to_dict(self) -> dict:
        return {
            "memory_id": self.memory_id,
            "category_path": self.category_path,
            "tags": self.tags,
            "importance": self.importance,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "embedding_state": self.embedding_state,
            "retry_count": self.retry_count,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "MemoryMeta":
        return cls(
            memory_id=data["memory_id"],
            category_path=data["category_path"],
            tags=data.get("tags", []),
            importance=data.get("importance", 1.0),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            embedding_state=data.get("embedding_state", "pending"),
            retry_count=data.get("retry_count", 0),
        )


class DataLakeError(Exception): pass
class PathSecurityError(DataLakeError): pass
class MemoryNotFoundError(DataLakeError): pass
class AtomicWriteError(DataLakeError): pass


class DataLake:
    EXT_CONTENT = ".md"
    EXT_VECTOR = ".vec.json"
    EXT_META = ".meta.json"
    EXT_TMP = ".tmp"
    
    def __init__(self, root_dir: str | Path, memory_library_name: str = "memory_library") -> None:
        self.root_dir = Path(root_dir).resolve()
        self.memory_library = self.root_dir / memory_library_name
        self._locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()
        self._permission_engine: "PermissionEngine | None" = None

    def set_permission_engine(self, engine: "PermissionEngine") -> None:
        """设置权限引擎"""
        self._permission_engine = engine
    
    def _validate_path(self, path: str | Path) -> Path:
        resolved = Path(path).resolve()
        try:
            resolved.relative_to(self.memory_library)
        except ValueError:
            raise PathSecurityError(f"Path not in whitelist: {self.memory_library}")
        return resolved
    
    async def _get_path_lock(self, path: str | Path) -> asyncio.Lock:
        path_str = str(Path(path).resolve())
        async with self._global_lock:
            if path_str not in self._locks:
                self._locks[path_str] = asyncio.Lock()
            return self._locks[path_str]
    
    async def init(self) -> None:
        await asyncio.to_thread(self.memory_library.mkdir, parents=True, exist_ok=True)
    
    async def create_category(self, category_path: str) -> Path:
        if category_path.startswith("/"):
            category_path = str(Path(category_path).relative_to(self.memory_library))
        category_dir = self.memory_library / category_path
        category_dir = self._validate_path(category_dir)
        await asyncio.to_thread(category_dir.mkdir, parents=True, exist_ok=True)
        return category_dir
    
    async def scan_category(self, category_path: str, recursive: bool = True) -> list[MemoryFile]:
        category_dir = self.memory_library / category_path
        category_dir = self._validate_path(category_dir)
        if not category_dir.exists():
            return []
        memories: list[MemoryFile] = []
        pattern = "**/*" + self.EXT_CONTENT if recursive else "*" + self.EXT_CONTENT
        for md_path in category_dir.glob(pattern):
            memory_id = md_path.stem
            meta_path = md_path.with_suffix(self.EXT_META)
            try:
                if meta_path.exists():
                    async with aiofiles.open(meta_path, "r", encoding="utf-8") as f:
                        meta_data = json.loads(await f.read())
                    created_at = datetime.fromisoformat(meta_data.get("created_at", "2000-01-01T00:00:00"))
                    updated_at = datetime.fromisoformat(meta_data.get("updated_at", "2000-01-01T00:00:00"))
                else:
                    stat = await asyncio.to_thread(md_path.stat)
                    created_at = datetime.fromtimestamp(stat.st_ctime)
                    updated_at = datetime.fromtimestamp(stat.st_mtime)
                rel_path = md_path.parent.relative_to(self.memory_library)
                memories.append(MemoryFile(memory_id=memory_id, category_path=str(rel_path), created_at=created_at, updated_at=updated_at))
            except Exception:
                continue
        return sorted(memories, key=lambda m: m.memory_id)

    async def list_memories(self, category_path: str = "", recursive: bool = True) -> list[MemoryFile]:
        """List memories under a category path. Alias for scan_category."""
        return await self.scan_category(category_path, recursive)

    async def list_categories(self, parent_path: str = "") -> list[str]:
        parent_dir = self.memory_library / parent_path if parent_path else self.memory_library
        try:
            parent_dir = self._validate_path(parent_dir)
        except PathSecurityError:
            return []
        if not parent_dir.exists():
            return []
        categories = [item.name for item in parent_dir.iterdir() if item.is_dir() and not item.name.startswith("_")]
        return sorted(categories)
    
    def _get_memory_paths(self, memory_id: str, category_path: str) -> dict:
        category_dir = self.memory_library / category_path
        base_path = category_dir / memory_id
        return {"content": base_path.with_suffix(self.EXT_CONTENT), "vector": base_path.with_suffix(self.EXT_VECTOR), "meta": base_path.with_suffix(self.EXT_META)}
    
    async def create_memory(self, category_path: str, content: str, tags: Optional[list[str]] = None, importance: float = 1.0, metadata: Optional[dict] = None) -> str:
        await self.create_category(category_path)
        memory_id = f"mem_{ULID()}"
        now = datetime.now().isoformat()
        paths = self._get_memory_paths(memory_id, category_path)
        lock = await self._get_path_lock(paths["content"].parent)
        async with lock:
            meta = MemoryMeta(memory_id=memory_id, category_path=category_path, tags=tags or [], importance=importance, created_at=now, updated_at=now, embedding_state="pending", retry_count=0)
            if metadata:
                meta_dict = meta.to_dict()
                meta_dict.update(metadata)
                meta = MemoryMeta.from_dict(meta_dict)
            tmp_content = paths["content"].with_suffix(self.EXT_TMP)
            async with aiofiles.open(tmp_content, "w", encoding="utf-8") as f:
                await f.write(content)
            await asyncio.to_thread(tmp_content.replace, paths["content"])
            tmp_meta = paths["meta"].with_suffix(self.EXT_TMP)
            async with aiofiles.open(tmp_meta, "w", encoding="utf-8") as f:
                await f.write(json.dumps(meta.to_dict(), ensure_ascii=False, indent=2))
            await asyncio.to_thread(tmp_meta.replace, paths["meta"])
        return memory_id
    
    async def get_memory(self, memory_id: str) -> Optional[MemoryContent]:
        for md_path in self.memory_library.rglob(memory_id + self.EXT_CONTENT):
            async with aiofiles.open(md_path, "r", encoding="utf-8") as f:
                content = await f.read()
            meta_path = md_path.with_suffix(self.EXT_META)
            meta_data = {}
            if meta_path.exists():
                async with aiofiles.open(meta_path, "r", encoding="utf-8") as f:
                    meta_data = json.loads(await f.read())
            return MemoryContent(memory_id=memory_id, content=content, metadata=meta_data)
        return None
    async def update_memory(self, memory_id: str, content=None, tags=None, importance=None) -> None:
        memory_content = await self.get_memory(memory_id)
        if memory_content is None:
            raise MemoryNotFoundError(f"Memory not found: {memory_id}")
        category_path = memory_content.metadata.get("category_path", "")
        paths = self._get_memory_paths(memory_id, category_path)
        lock = await self._get_path_lock(paths["content"].parent)
        async with lock:
            now = datetime.now().isoformat()
            if content is not None:
                tmp_content = paths["content"].with_suffix(self.EXT_TMP)
                async with aiofiles.open(tmp_content, "w", encoding="utf-8") as f:
                    await f.write(content)
                await asyncio.to_thread(tmp_content.replace, paths["content"])
            meta_path = paths["meta"]
            if meta_path.exists():
                async with aiofiles.open(meta_path, "r", encoding="utf-8") as f:
                    meta_dict = json.loads(await f.read())
            else:
                meta_dict = {"memory_id": memory_id, "category_path": category_path, "tags": [], "importance": 1.0, "created_at": now, "updated_at": now, "embedding_state": "pending", "retry_count": 0}
            meta_dict["updated_at"] = now
            if tags is not None:
                meta_dict["tags"] = tags
            if importance is not None:
                meta_dict["importance"] = importance
            tmp_meta = meta_path.with_suffix(self.EXT_TMP)
            async with aiofiles.open(tmp_meta, "w", encoding="utf-8") as f:
                await f.write(json.dumps(meta_dict, ensure_ascii=False, indent=2))
            await asyncio.to_thread(tmp_meta.replace, meta_path)

    async def delete_memory(self, memory_id: str) -> None:
        memory_content = await self.get_memory(memory_id)
        if memory_content is None:
            raise MemoryNotFoundError(f"Memory not found: {memory_id}")
        category_path = memory_content.metadata.get("category_path", "")
        paths = self._get_memory_paths(memory_id, category_path)
        lock = await self._get_path_lock(paths["content"].parent)
        async with lock:
            for key in ["content", "vector", "meta"]:
                file_path = paths[key]
                if file_path.exists():
                    file_path.unlink()

    async def get_memory_metadata(self, memory_id: str):
        memory_content = await self.get_memory(memory_id)
        if memory_content is None:
            return None
        return MemoryMeta.from_dict(memory_content.metadata)
    
    async def update_memory_metadata(self, memory_id: str, tags=None, importance=None, embedding_state=None) -> None:
        memory_content = await self.get_memory(memory_id)
        if memory_content is None:
            raise MemoryNotFoundError(f"Memory not found: {memory_id}")
        category_path = memory_content.metadata.get("category_path", "")
        paths = self._get_memory_paths(memory_id, category_path)
        meta_path = paths["meta"]
        if meta_path.exists():
            async with aiofiles.open(meta_path, "r", encoding="utf-8") as f:
                meta_dict = json.loads(await f.read())
        else:
            now = datetime.now().isoformat()
            meta_dict = {"memory_id": memory_id, "category_path": category_path, "tags": tags or [], "importance": importance or 1.0, "created_at": now, "updated_at": now, "embedding_state": embedding_state or "pending", "retry_count": 0}
        if tags is not None:
            meta_dict["tags"] = tags
        if importance is not None:
            meta_dict["importance"] = importance
        if embedding_state is not None:
            meta_dict["embedding_state"] = embedding_state
            if embedding_state == "generating":
                meta_dict["retry_count"] = meta_dict.get("retry_count", 0) + 1
        tmp_meta = meta_path.with_suffix(self.EXT_TMP)
        async with aiofiles.open(tmp_meta, "w", encoding="utf-8") as f:
            await f.write(json.dumps(meta_dict, ensure_ascii=False, indent=2))
        await asyncio.to_thread(tmp_meta.replace, meta_path)

    async def save_vector(self, memory_id: str, vector: list[float], model: str, dimensions: int) -> None:
        memory_content = await self.get_memory(memory_id)
        if memory_content is None:
            raise MemoryNotFoundError(f"Memory not found: {memory_id}")
        category_path = memory_content.metadata.get("category_path", "")
        paths = self._get_memory_paths(memory_id, category_path)
        vector_data = {"memory_id": memory_id, "vector": vector, "model": model, "dimensions": dimensions}
        tmp_path = paths["vector"].with_suffix(self.EXT_TMP)
        async with aiofiles.open(tmp_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(vector_data, ensure_ascii=False, indent=2))
        await asyncio.to_thread(tmp_path.replace, paths["vector"])

    async def get_vector(self, memory_id: str):
        memory_content = await self.get_memory(memory_id)
        if memory_content is None:
            return None
        category_path = memory_content.metadata.get("category_path", "")
        paths = self._get_memory_paths(memory_id, category_path)
        vector_path = paths["vector"]
        if not vector_path.exists():
            return None
        async with aiofiles.open(vector_path, "r", encoding="utf-8") as f:
            data = json.loads(await f.read())
        return MemoryVector(memory_id=data["memory_id"], vector=data["vector"], model=data["model"], dimensions=data["dimensions"])

    # ============================================================================
    # §5.1 DataLake 接口契约 — 架构别名包装（write/read/delete/list/hydrate/exists/move）
    # ============================================================================

    async def write(
        self,
        content: str,
        category: list[str],
        metadata: dict,
        importance: float,
    ) -> str:
        """§5.1 write — 写入一条记忆（同步，不含 embedding）

        Args:
            content: 记忆内容
            category: 分类路径列表 e.g. ["A.项目", "石榴籽", "语料"]
            metadata: 自由元数据
            importance: 重要性分数（0-1）

        Returns:
            mem_id: ULID 字符串
        """
        category_path = "/".join(category)
        return await self.create_memory(
            category_path=category_path,
            content=content,
            tags=metadata.get("tags", []),
            importance=importance,
            metadata=metadata,
        )

    # ============================================================================
    # AI 辅助分类集成
    # ============================================================================

    async def write_with_auto_classify(
        self,
        content: str,
        agent_id: str = None,
        auto_classify: bool = True,
        classifier: "AutoClassifier | None" = None,
    ) -> tuple[str, "ClassificationRecommendation | None"]:
        """
        写入记忆，自动推荐分类。

        Args:
            content: 记忆内容
            agent_id: Agent ID（可选）
            auto_classify: 是否自动分类
            classifier: AutoClassifier 实例

        Returns:
            (memory_id, recommendation)
            如果 auto_classify=False，recommendation 为 None
        """
        recommendation = None

        if auto_classify and classifier is not None:
            recommendation = await classifier.recommend(content)

        # 先用默认路径写入（后续可调整）
        default_category = recommendation.suggested_path if recommendation else "C.知识"
        category_parts = default_category.split("/")

        # 写入记忆
        memory_id = await self.write(
            content=content,
            category=category_parts,
            metadata={
                "agent_id": agent_id,
                "auto_classified": auto_classify,
                "classification_path": default_category,
                "classification_tags": recommendation.suggested_tags if recommendation else [],
                "classification_confidence": recommendation.confidence if recommendation else 0.0,
            },
            importance=1.0,
        )

        return memory_id, recommendation

    async def read(self, mem_id: str) -> "MemoryContent":
        """§5.1 read — 读取一条记忆的完整内容（.md + .meta.json）"""
        return await self.get_memory(mem_id)

    def _find_category_for_memory(self, memory_id: str) -> str:
        """根据 memory_id 查找其分类路径"""
        for md_path in self.memory_library.rglob(memory_id + self.EXT_CONTENT):
            rel = md_path.parent.relative_to(self.memory_library)
            return str(rel)
        return ""

    async def delete(self, mem_id: str) -> None:
        """§5.1 delete — 删除一条记忆的所有关联文件"""
        await self.delete_memory(mem_id)

    async def list_memories(
        self,
        category: List[str] | None = None,
        since=None,
        until=None,
        limit: int = 100,
    ) -> List[str]:
        """§5.1 list — 列出符合分类 + 时间范围的 mem_id"""
        if category is None:
            # 扫描所有分类
            all_ids = []
            for md_path in self.memory_library.rglob("*" + self.EXT_CONTENT):
                all_ids.append(md_path.stem)
            return sorted(all_ids)[:limit]

        category_path = "/".join(category)
        memories = await self.scan_category(category_path, recursive=True)
        ids = [m.memory_id for m in memories][:limit]

        # 时间过滤（简化：暂不支持 since/until）
        return ids

    async def hydrate(
        self,
        mem_ids: List[str],
        fields: List[str] | None = None,
    ) -> List[MemoryContent]:
        """§5.1 hydrate — 批量加载，fields=None 表示全字段"""
        results = []
        for mem_id in mem_ids:
            content = await self.get_memory(mem_id)
            if content is not None:
                results.append(content)
        return results

    async def exists(self, mem_id: str) -> bool:
        """§5.1 exists — 检查 memory_id 是否存在"""
        for md_path in self.memory_library.rglob(mem_id + self.EXT_CONTENT):
            return True
        return False

    async def move(self, mem_id: str, new_category: list[str]) -> None:
        """§5.1 move — 移动记忆到另一个分类"""
        old_category_path = self._find_category_for_memory(mem_id)
        if not old_category_path:
            raise MemoryNotFoundError(f"Memory not found: {mem_id}")

        old_paths = self._get_memory_paths(mem_id, old_category_path)
        new_category_path = "/".join(new_category)
        new_paths = self._get_memory_paths(mem_id, new_category_path)

        # 确保新目录存在
        new_dir = (self.memory_library / new_category_path).resolve()
        self._validate_path(new_dir)
        await asyncio.to_thread(new_dir.mkdir, parents=True, exist_ok=True)

        # 移动文件
        lock = await self._get_path_lock(new_paths["content"].parent)
        async with lock:
            for key in ["content", "vector", "meta"]:
                old_file = old_paths[key]
                new_file = new_paths[key]
                if old_file.exists():
                    await asyncio.to_thread(shutil.move, str(old_file), str(new_file))

            # 更新 meta
            meta_path = new_paths["meta"]
            if meta_path.exists():
                async with aiofiles.open(meta_path, "r", encoding="utf-8") as f:
                    meta_dict = json.loads(await f.read())
                meta_dict["category_path"] = new_category_path
                async with aiofiles.open(meta_path, "w", encoding="utf-8") as f:
                    await f.write(json.dumps(meta_dict, ensure_ascii=False, indent=2))

    # ============================================================================
    # 权限检查集成
    # ============================================================================

    async def check_access(self, agent_id: str, path: str, operation: str) -> bool:
        """检查 Agent 是否有权操作路径

        Args:
            agent_id: Agent 唯一标识
            path: 目标路径
            operation: 操作类型 "read" | "write" | "delete"

        Returns:
            True if allowed, False otherwise
        """
        if self._permission_engine is None:
            # 无权限引擎时默认允许
            return True
        ctx = await self._permission_engine.check(agent_id, operation, path)
        return ctx.granted

    async def list_for_agent(
        self,
        agent_id: str,
        category_path: str = "",
        recursive: bool = True,
    ) -> list[MemoryFile]:
        """只返回 agent 有权限看到的记忆

        Args:
            agent_id: Agent 唯一标识
            category_path: 分类路径（空表示根目录）
            recursive: 是否递归子分类

        Returns:
            MemoryFile 列表（仅包含有权限访问的记忆）
        """
        all_memories = await self.scan_category(category_path, recursive)

        if self._permission_engine is None:
            return all_memories

        # 过滤无权限的记忆
        allowed_memories: list[MemoryFile] = []
        for mem in all_memories:
            ctx = await self._permission_engine.check(
                agent_id, "read", mem.category_path
            )
            if ctx.granted:
                allowed_memories.append(mem)

        return allowed_memories
