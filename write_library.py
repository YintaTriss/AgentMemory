content = '''"""
Library - 图书馆分类管理模块

负责分类树的 CRUD 操作和分类白名单校验。
遵循 v0.5 架构：分类白名单约束，AI 推荐时只能选不能创。

核心功能：
- 分类树 CRUD（最多 4 层深度）
- .library_index.json 索引持久化
- 分类白名单校验（AI 推荐分类时只能选不能创）

Author: backend engineer
Version: v2.0
"""

import asyncio
import json
from pathlib import Path
from typing import Optional, AsyncIterator, List
from dataclasses import dataclass, field, asdict
from datetime import datetime

import aiofiles


# ============================================================================
# Constants
# ============================================================================

MAX_CATEGORY_DEPTH = 4
LIBRARY_INDEX_FILE = ".library_index.json"
CATEGORY_SEPARATOR = "/"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class CategoryNode:
    """分类树节点"""
    name: str
    path: str
    children: dict[str, "CategoryNode"] = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


@dataclass
class CategoryInfo:
    """分类信息"""
    path: str
    name: str
    depth: int
    parent: Optional[str]
    children_count: int


# ============================================================================
# Exceptions
# ============================================================================

class LibraryError(Exception):
    """Library 基础异常"""
    pass


class CategoryNotFoundError(LibraryError):
    """分类不存在"""
    pass


class CategoryDepthExceededError(LibraryError):
    """分类层级超限"""
    pass


class CategoryNotInWhitelistError(LibraryError):
    """分类不在白名单内"""
    pass


class CategoryAlreadyExistsError(LibraryError):
    """分类已存在"""
    pass


# ============================================================================
# Library Core
# ============================================================================

class Library:
    """
    图书馆分类管理类
    
    负责分类树的 CRUD 操作和分类白名单校验。
    分类最多支持 4 层深度。
    
    分类白名单：
    - 白名单内的分类可以创建
    - 白名单外的分类需要用户确认才能创建
    - AI 推荐时只能从白名单中选择，不能创建新分类
    
    Example:
        >>> library = Library(root_dir="/data/agentmemory")
        >>> await library.init()
        >>> categories = await library.list_categories()
        >>> await library.create_category("A.项目/石榴籽")
    """
    
    def __init__(
        self,
        root_dir: str | Path,
        whitelist: Optional[list[str]] = None
    ) -> None:
        """
        初始化 Library
        
        Args:
            root_dir: 数据根目录
            whitelist: 分类白名单列表
        """
        self.root_dir = Path(root_dir).resolve()
        self.index_file = self.root_dir / LIBRARY_INDEX_FILE
        self._lock = asyncio.Lock()
        
        self._whitelist: set[str] = set(whitelist or [
            "A.项目",
            "B.个人", 
            "C.临时"
        ])
        
        self._tree: dict[str, CategoryNode] = {}
    
    async def init(self) -> None:
        """初始化分类索引"""
        self.root_dir.mkdir(parents=True, exist_ok=True)
        
        if self.index_file.exists():
            async with aiofiles.open(self.index_file, "r", encoding="utf-8") as f:
                content = await f.read()
                data = json.loads(content)
                self._tree = self._deserialize_tree(data)
        else:
            await self._save_index()
    
    def _serialize_tree(self) -> dict:
        return {
            name: self._node_to_dict(node)
            for name, node in self._tree.items()
        }
    
    def _node_to_dict(self, node: CategoryNode) -> dict:
        return {
            "name": node.name,
            "path": node.path,
            "metadata": node.metadata,
            "children": {
                name: self._node_to_dict(child)
                for name, child in node.children.items()
            }
        }
    
    def _deserialize_tree(self, data: dict) -> dict[str, CategoryNode]:
        result = {}
        for name, node_data in data.items():
            result[name] = self._dict_to_node(node_data)
        return result
    
    def _dict_to_node(self, data: dict) -> CategoryNode:
        children = {
            name: self._dict_to_node(child)
            for name, child in data.get("children", {}).items()
        }
        return CategoryNode(
            name=data["name"],
            path=data["path"],
            metadata=data.get("metadata", {}),
            children=children
        )
    
    async def _save_index(self) -> None:
        async with self._lock:
            data = self._serialize_tree()
            content = json.dumps(data, ensure_ascii=False, indent=2)
            tmp_file = self.index_file.with_suffix(".tmp")
            async with aiofiles.open(tmp_file, "w", encoding="utf-8") as f:
                await f.write(content)
            tmp_file.replace(self.index_file)
    
    def get_whitelist(self) -> list[str]:
        return sorted(list(self._whitelist))
    
    def add_to_whitelist(self, category: str) -> None:
        self._whitelist.add(category)
    
    def remove_from_whitelist(self, category: str) -> None:
        self._whitelist.discard(category)
    
    def is_in_whitelist(self, category: str) -> bool:
        if category in self._whitelist:
            return True
        top_level = category.split(CATEGORY_SEPARATOR)[0]
        return top_level in self._whitelist
    
    def is_top_level_allowed(self, category: str) -> bool:
        return category in self._whitelist
    
    def requires_confirmation(self, category: str) -> bool:
        return not self.is_in_whitelist(category)
    
    def _get_depth(self, path: str) -> int:
        return len(path.split(CATEGORY_SEPARATOR))
    
    def _get_parent_path(self, path: str) -> Optional[str]:
        parts = path.split(CATEGORY_SEPARATOR)
        if len(parts) <= 1:
            return None
        return CATEGORY_SEPARATOR.join(parts[:-1])
    
    def _get_category_name(self, path: str) -> str:
        return path.split(CATEGORY_SEPARATOR)[-1]
    
    def _category_exists(self, path: str) -> bool:
        parts = path.split(CATEGORY_SEPARATOR)
        current = self._tree
        for i, part in enumerate(parts):
            if part not in current:
                return False
            if i < len(parts) - 1:
                current = current[part].children
        return True
    
    def _get_node(self, path: str) -> Optional[CategoryNode]:
        parts = path.split(CATEGORY_SEPARATOR)
        current = self._tree
        for i, part in enumerate(parts):
            if part not in current:
                return None
            if i < len(parts) - 1:
                current = current[part].children
            else:
                return current[part]
        return None
    
    async def create_category(
        self,
        path: str,
        metadata: Optional[dict] = None,
        allow_new_top_level: bool = False
    ) -> CategoryInfo:
        async with self._lock:
            depth = self._get_depth(path)
            if depth > MAX_CATEGORY_DEPTH:
                raise CategoryDepthExceededError(
                    f"Category depth {depth} exceeds maximum {MAX_CATEGORY_DEPTH}"
                )
            
            if self._category_exists(path):
                raise CategoryAlreadyExistsError(f"Category already exists: {path}")
            
            top_level = path.split(CATEGORY_SEPARATOR)[0]
            if not allow_new_top_level and top_level not in self._whitelist:
                raise CategoryNotInWhitelistError(
                    f"Top-level category '{top_level}' is not in whitelist"
                )
            
            parts = path.split(CATEGORY_SEPARATOR)
            current = self._tree
            for i, part in enumerate(parts):
                if part not in current:
                    current[part] = CategoryNode(
                        name=part,
                        path=CATEGORY_SEPARATOR.join(parts[:i+1]),
                        metadata=metadata if i == len(parts) - 1 else {},
                    )
                current = current[part].children
 
