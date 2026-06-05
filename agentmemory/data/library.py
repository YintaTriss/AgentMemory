"""
Library - 图书馆分类管理模块
Version: v2.0 + Permission Integration

§5.2 接口契约别名：
- validate(path) → 检查路径是否在白名单内
- suggest(content, embedder) → 推荐候选分类
- add_subcategory(parent, child) → 添加子分类
- get_descendants(path) → 获取所有后代分类
- save() / load() → 持久化白名单
"""

import asyncio
import json
from pathlib import Path
from typing import Optional, AsyncIterator, Protocol, TYPE_CHECKING
from dataclasses import dataclass, field
import aiofiles

if TYPE_CHECKING:
    from agentmemory.agent_permissions.permissions import PermissionEngine


MAX_CATEGORY_DEPTH = 4
LIBRARY_INDEX_FILE = ".library_index.json"
CATEGORY_SEPARATOR = "/"


@dataclass
class CategoryNode:
    """§5.2 CategoryNode — 分类树节点

    Attributes:
        code: 分类代码（顶级为单字母如 'A'，子级为名称）
        path: 完整路径，如 ["A.项目", "石榴籽", "语料"]
        depth: 深度（0 = 顶级）
        children: 子分类 dict[name, CategoryNode]
        description: 分类描述
    """
    code: str
    path: list[str]
    depth: int
    children: dict = field(default_factory=dict)
    description: str = ''


@dataclass
class CategoryInfo:
    path: str
    name: str
    depth: int
    parent: Optional[str]
    children_count: int


class LibraryError(Exception): pass
class CategoryNotFoundError(LibraryError): pass
class CategoryDepthExceededError(LibraryError): pass
class CategoryNotInWhitelistError(LibraryError): pass
class CategoryAlreadyExistsError(LibraryError): pass


class Library:
    def __init__(self, root_dir, whitelist=None):
        self.root_dir = Path(root_dir).resolve()
        self.index_file = self.root_dir / LIBRARY_INDEX_FILE
        self._lock = asyncio.Lock()
        self._whitelist = set(whitelist or ["A.项目", "B.个人", "C.临时"])
        self._tree = {}
        self._permission_engine: "PermissionEngine | None" = None

    def set_permission_engine(self, engine: "PermissionEngine") -> None:
        """设置权限引擎"""
        self._permission_engine = engine

    async def init(self):
        self.root_dir.mkdir(parents=True, exist_ok=True)
        if self.index_file.exists():
            async with aiofiles.open(self.index_file, 'r', encoding='utf-8') as f:
                data = json.loads(await f.read())
                self._tree = self._deserialize_tree(data)
        else:
            await self._save_index()

    def _serialize_tree(self):
        return {name: self._node_to_dict(node) for name, node in self._tree.items()}

    def _node_to_dict(self, node):
        return {
            'name': node.name, 'path': node.path, 'metadata': node.metadata,
            'children': {n: self._node_to_dict(c) for n, c in node.children.items()}
        }

    def _deserialize_tree(self, data):
        return {name: self._dict_to_node(d) for name, d in data.items()}

    def _dict_to_node(self, data):
        children = {n: self._dict_to_node(c) for n, c in data.get('children', {}).items()}
        return CategoryNode(name=data['name'], path=data['path'], 
                          metadata=data.get('metadata', {}), children=children)

    async def _save_index(self):
        async with self._lock:
            tmp = self.index_file.with_suffix('.tmp')
            async with aiofiles.open(tmp, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(self._serialize_tree(), ensure_ascii=False, indent=2))
            tmp.replace(self.index_file)

    def get_whitelist(self): return sorted(list(self._whitelist))
    def add_to_whitelist(self, c): self._whitelist.add(c)
    def remove_from_whitelist(self, c): self._whitelist.discard(c)
    def is_in_whitelist(self, c): return c in self._whitelist or c.split(CATEGORY_SEPARATOR)[0] in self._whitelist
    def is_top_level_allowed(self, c): return c in self._whitelist
    def requires_confirmation(self, c): return not self.is_in_whitelist(c)
    def _get_depth(self, p): return len(p.split(CATEGORY_SEPARATOR))
    def _get_parent_path(self, p): parts = p.split(CATEGORY_SEPARATOR); return None if len(parts) <= 1 else CATEGORY_SEPARATOR.join(parts[:-1])
    def _get_category_name(self, p): return p.split(CATEGORY_SEPARATOR)[-1]

    def _category_exists(self, path):
        parts = path.split(CATEGORY_SEPARATOR)
        current = self._tree
        for i, part in enumerate(parts):
            if part not in current: return False
            if i < len(parts) - 1: current = current[part].children
        return True

    def _get_node(self, path):
        parts = path.split(CATEGORY_SEPARATOR)
        current = self._tree
        for i, part in enumerate(parts):
            if part not in current: return None
            if i < len(parts) - 1: current = current[part].children
            else: return current[part]
        return None

    async def create_category(self, path, metadata=None, allow_new_top_level=False):
        async with self._lock:
            depth = self._get_depth(path)
            if depth > MAX_CATEGORY_DEPTH:
                raise CategoryDepthExceededError(f'分类深度 {depth} 超过最大限制 {MAX_CATEGORY_DEPTH}')
            if self._category_exists(path):
                raise CategoryAlreadyExistsError(f'分类已存在: {path}')
            top_level = path.split(CATEGORY_SEPARATOR)[0]
            if not self.is_in_whitelist(path) and not allow_new_top_level:
                if not self.is_top_level_allowed(top_level):
                    raise CategoryNotInWhitelistError(f'不允许创建分类: {path}')
            parts = path.split(CATEGORY_SEPARATOR)
            current = self._tree
            for i, part in enumerate(parts):
                if part not in current:
                    current[part] = CategoryNode(name=part, path=CATEGORY_SEPARATOR.join(parts[:i+1]),
                                               children={}, metadata=metadata if i == len(parts)-1 else {})
                current = current[part].children
            await self._save_index()
            return CategoryInfo(path=path, name=self._get_category_name(path), depth=depth,
                               parent=self._get_parent_path(path), children_count=0)

    async def get_category_info(self, path):
        node = self._get_node(path)
        if node is None: raise CategoryNotFoundError(f'分类不存在: {path}')
        return CategoryInfo(path=path, name=node.name, depth=self._get_depth(path),
                           parent=self._get_parent_path(path), children_count=len(node.children))

    async def delete_category(self, path, recursive=False):
        async with self._lock:
            if not self._category_exists(path): raise CategoryNotFoundError(f'分类不存在: {path}')
            parts = path.split(CATEGORY_SEPARATOR)
            current = self._tree
            for i, part in enumerate(parts):
                if i < len(parts) - 1: current = current[part].children
            if current[parts[-1]].children and not recursive:
                raise LibraryError(f'分类 {path} 有子分类，请使用 recursive=True 删除')
            del current[parts[-1]]
            await self._save_index()

    async def list_categories(self, parent_path=''):
        async with self._lock:
            if parent_path == '': return list(self._tree.keys())
            node = self._get_node(parent_path)
            return [] if node is None else list(node.children.keys())

    async def iterate_categories(self, parent_path=''):
        async with self._lock:
            if parent_path == '':
                for name in self._tree: yield name
            else:
                node = self._get_node(parent_path)
                if node:
                    for name in node.children: yield name

    async def update_category_metadata(self, path, metadata):
        async with self._lock:
            node = self._get_node(path)
            if node is None: raise CategoryNotFoundError(f'分类不存在: {path}')
            node.metadata = metadata
            await self._save_index()
            return CategoryInfo(path=path, name=node.name, depth=self._get_depth(path),
                               parent=self._get_parent_path(path), children_count=len(node.children))

    async def get_all_categories_recursive(self):
        result = []
        def _traverse(node_dict, prefix=''):
            for name, node in node_dict.items():
                path = f'{prefix}/{name}' if prefix else name
                result.append(path)
                if node.children: _traverse(node.children, path)
        _traverse(self._tree)
        return result

    # ============================================================================
    # §5.2 Library 接口契约实现
    # ============================================================================

    def validate(self, path: list[str]) -> CategoryNode:
        """§5.2 validate — 校验分类路径合法性

        Args:
            path: 分类路径列表，如 ["A.项目", "石榴籽", "语料"]

        Returns:
            CategoryNode

        Raises:
            CategoryNotInWhitelistError: 路径不在白名单
            CategoryDepthExceededError: 深度 > MAX_DEPTH
        """
        path_str = CATEGORY_SEPARATOR.join(path)
        depth = len(path)
        if depth > MAX_CATEGORY_DEPTH:
            raise CategoryDepthExceededError(f'分类深度 {depth} 超过最大限制 {MAX_CATEGORY_DEPTH}')
        top_level = path[0] if path else ''
        if not self.is_in_whitelist(path_str):
            raise CategoryNotInWhitelistError(f'分类不在白名单: {path_str}')
        node = self._get_node(path_str)
        return CategoryNode(
            name=self._get_category_name(path_str),
            path=path_str,
            depth=depth,
            children=node.children if node else {},
            description=node.metadata.get('description', '') if node else '',
        )

    async def suggest(self, content: str, embedder: "Protocol" = None) -> list[tuple[list[str], float]]:
        """§5.2 suggest — 基于内容推荐候选分类

        Args:
            content: 内容文本
            embedder: Embedder（可选，如果不提供则用关键词匹配）

        Returns:
            [(path, score), ...] 按相似度降序，最多 3 个
        """
        # 简单关键词匹配 fallback（无 embedder 时）
        keywords_map = {
            '项目': ['A.项目'],
            '工作': ['A.项目'],
            '个人': ['B.个人'],
            '日记': ['B.个人', '日记'],
            '知识': ['C.知识'],
            '技术': ['C.知识', '技术'],
            '学习': ['C.知识', '技术'],
        }
        scores: dict[str, float] = {}
        for kw, cats in keywords_map.items():
            if kw in content:
                for cat in cats:
                    scores[cat] = scores.get(cat, 0.0) + 1.0
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        result = []
        for cat, score in sorted_scores[:3]:
            path_list = cat.split(CATEGORY_SEPARATOR)
            result.append((path_list, score / max(sum(scores.values()), 1)))
        return result

    async def add_subcategory(
        self,
        parent: list[str],
        name: str,
        description: str = '',
        require_confirm: bool = True,
    ) -> CategoryNode:
        """§5.2 add_subcategory — 添加子分类

        Args:
            parent: 父分类路径
            name: 子分类名称
            description: 分类描述
            require_confirm: True 时若 parent 不在白名单抛异常
        """
        parent_str = CATEGORY_SEPARATOR.join(parent)
        if require_confirm and not self._category_exists(parent_str):
            raise CategoryNotFoundError(f'父分类不存在: {parent_str}')
        new_path = parent + [name]
        new_path_str = CATEGORY_SEPARATOR.join(new_path)
        depth = len(new_path)
        if depth > MAX_CATEGORY_DEPTH:
            raise CategoryDepthExceededError(f'分类深度 {depth} 超过最大限制 {MAX_CATEGORY_DEPTH}')
        if self._category_exists(new_path_str):
            raise CategoryAlreadyExistsError(f'分类已存在: {new_path_str}')
        await self.create_category(
            path=new_path_str,
            metadata={'description': description},
            allow_new_top_level=False,
        )
        return CategoryNode(
            name=name,
            path=new_path_str,
            depth=depth,
            children={},
            description=description,
        )

    def get_descendants(self, path: list[str]) -> set[str]:
        """§5.2 get_descendants — 返回该分类下所有 mem_id 集合（递归）

        Returns:
            set[str]: 该分类下所有记忆 ID
        """
        path_str = CATEGORY_SEPARATOR.join(path)
        node = self._get_node(path_str)
        if node is None:
            return set()
        result: set[str] = set()

        def _collect_memory_ids(node_dict, prefix=''):
            for name, n in node_dict.items():
                child_path = f'{prefix}/{name}' if prefix else name
                if n.metadata.get('memory_ids'):
                    result.update(n.metadata['memory_ids'])
                if n.children:
                    _collect_memory_ids(n.children, child_path)

        if node.metadata.get('memory_ids'):
            result.update(node.metadata['memory_ids'])
        if node.children:
            _collect_memory_ids(node.children, path_str)
        return result

    async def save(self) -> None:
        """§5.2 save — 持久化 .library_index.json"""
        await self._save_index()

    async def load(self) -> None:
        """§5.2 load — 加载白名单"""
        await self.init()

    # ============================================================================
    # 权限检查集成
    # ============================================================================

    def suggest_paths_for_agent(self, agent_id: str, partial: str = "") -> list[str]:
        """只推荐 agent 有权限的路径

        Args:
            agent_id: Agent 唯一标识
            partial: 部分路径（用于过滤）

        Returns:
            匹配的路径列表
        """
        all_categories = []

        def _collect_paths(node_dict, prefix=''):
            for name, node in node_dict.items():
                path = f'{prefix}/{name}' if prefix else name
                all_categories.append(path)
                if node.children:
                    _collect_paths(node.children, path)

        _collect_paths(self._tree)

        if self._permission_engine is None:
            # 无权限引擎时返回所有匹配的部分路径
            if partial:
                return [c for c in all_categories if c.startswith(partial)]
            return all_categories

        # 过滤无权限的路径
        allowed_paths: list[str] = []
        for path in all_categories:
            if partial and not path.startswith(partial):
                continue
            if self._permission_engine.is_path_visible(agent_id, path):
                allowed_paths.append(path)

        return allowed_paths
