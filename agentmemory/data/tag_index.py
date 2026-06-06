"""
TagIndex - Tag 倒排索引模块
Version: v2.0
"""

import asyncio
import json
from pathlib import Path
from typing import Optional, AsyncIterator
from dataclasses import dataclass, field
from collections import defaultdict
import aiofiles


TAGS_INDEX_FILE = ".tags_index.json"


@dataclass
class TagEntry:
    tag: str
    memory_ids: list


@dataclass  
class TagStats:
    tag: str
    count: int
    categories: list


class TagIndexError(Exception): pass


class TagIndex:
    def __init__(self, root_dir):
        self.root_dir = Path(root_dir).resolve()
        self.index_file = self.root_dir / TAGS_INDEX_FILE
        self._lock = asyncio.Lock()
        self._index: dict = defaultdict(set)
        self._cooccurrence_graph = None  # optional TagCooccurrenceGraph reference

    async def init(self):
        self.root_dir.mkdir(parents=True, exist_ok=True)
        if self.index_file.exists():
            async with aiofiles.open(self.index_file, "r", encoding="utf-8") as f:
                data = json.loads(await f.read())
                self._load_from_dict(data)

    def _load_from_dict(self, data):
        self._index.clear()
        for tag, entries in data.items():
            for entry in entries:
                self._index[tag].add((entry["memory_id"], entry.get("category_path", "")))

    def _to_dict(self):
        return {tag: [{"memory_id": mid, "category_path": cp} for mid, cp in entries]
                for tag, entries in self._index.items()}

    async def _save_index(self):
        tmp = self.index_file.with_suffix('.tmp')
        async with aiofiles.open(tmp, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(self._to_dict(), ensure_ascii=False, indent=2))
        tmp.replace(self.index_file)

    async def add_tag(self, tag: str, memory_id: str, category_path: str):
        async with self._lock:
            self._index[tag].add((memory_id, category_path))
            await self._save_index()

    async def add_tags(self, tags: list, memory_id: str, category_path: str):
        async with self._lock:
            for tag in tags:
                self._index[tag].add((memory_id, category_path))
            await self._save_index()

    async def remove_tag(self, tag: str, memory_id: str):
        async with self._lock:
            to_remove = None
            for entry in self._index[tag]:
                if entry[0] == memory_id:
                    to_remove = entry
                    break
            if to_remove:
                self._index[tag].discard(to_remove)
                if not self._index[tag]:
                    del self._index[tag]
                await self._save_index()

    async def update_tags(self, memory_id: str, category_path: str, old_tags: list, new_tags: list):
        async with self._lock:
            for tag in old_tags:
                entry = (memory_id, category_path)
                self._index[tag].discard(entry)
                if not self._index[tag]:
                    del self._index[tag]
            for tag in new_tags:
                self._index[tag].add((memory_id, category_path))
            await self._save_index()

    async def remove_memory(self, memory_id: str):
        async with self._lock:
            for tag in list(self._index.keys()):
                to_remove = [e for e in self._index[tag] if e[0] == memory_id]
                for entry in to_remove:
                    self._index[tag].discard(entry)
                if not self._index[tag]:
                    del self._index[tag]
            await self._save_index()

    async def get_by_tag(self, tag: str) -> list:
        return list(self._index.get(tag, set()))

    async def get_tags_for_memory(self, memory_id: str) -> list:
        return [tag for tag, entries in self._index.items() if any(mid == memory_id for mid, _ in entries)]

    async def search_tags(self, prefix: str, limit: int = 50) -> list:
        prefix_lower = prefix.lower()
        matching = []
        for tag in self._index.keys():
            if tag.lower().startswith(prefix_lower):
                matching.append(tag)
            if len(matching) >= limit:
                break
        return sorted(matching)

    async def get_all_tags(self) -> list:
        return sorted(list(self._index.keys()))

    async def get_tag_stats(self, tag: str) -> Optional[TagStats]:
        entries = self._index.get(tag)
        if not entries:
            return None
        categories = list(set(cp for _, cp in entries))
        return TagStats(tag=tag, count=len(entries), categories=categories)

    # ============================================================================
    # §5.4 TagIndex 接口契约别名
    # ============================================================================

    async def add(self, memory_id: str, tag: str) -> None:
        """§5.4 add(memory_id, tag) → add_tag 别名"""
        await self.add_tag(tag, memory_id, category_path='')

    async def remove(self, memory_id: str, tag: str) -> None:
        """§5.4 remove(memory_id, tag) → remove_tag 别名"""
        await self.remove_tag(tag, memory_id)

    async def query(
        self,
        tag_or_pattern: str,
        op: str = "OR",
    ) -> list[str]:
        """§5.4 query(tag_or_pattern) — 搜索标签匹配的记忆 ID"""
        if '*' in tag_or_pattern or '?' in tag_or_pattern:
            # 通配符搜索
            pattern = tag_or_pattern.lower().replace('*', '').replace('?', '')
            results: set = set()
            for tag in self._index.keys():
                if tag.lower().startswith(pattern):
                    for mid, _ in self._index[tag]:
                        results.add(mid)
            return list(results)
        else:
            # 精确匹配
            entries = await self.get_by_tag(tag_or_pattern)
            return [mid for mid, _ in entries]

    async def save(self) -> None:
        """§5.4 save — 持久化索引文件"""
        await self._save_index()

    async def load(self) -> None:
        """§5.4 load — 加载索引文件"""
        await self.init()

    # ============================================================================
    # Tag Cooccurrence Graph Integration
    # ============================================================================

    def set_cooccurrence_graph(self, graph) -> None:
        """设置共现图谱引用，用于查询增强"""
        self._cooccurrence_graph = graph

    async def update_cooccurrence_graph(self, tags: list[str]) -> None:
        """写入 Tags 时同步更新共现图谱"""
        if not self._cooccurrence_graph or not tags:
            return
        await self._cooccurrence_graph.add_memory_tags(memory_id="", tags=tags)

    async def query_with_cooccurrence(
        self,
        tags: list[str],
        include_related: bool = True,
        max_related: int = 10,
    ) -> list[str]:
        """
        结合共现图谱查询。
        1. 查询包含 input_tags 的记忆
        2. 如果 include_related=True，扩展查询共现 Tags
        3. 返回扩展后的 memory_ids
        """
        # 1. 查询包含 input_tags 的记忆
        result: set = set()
        for tag in tags:
            entries = await self.get_by_tag(tag)
            for mid, _ in entries:
                result.add(mid)

        if not include_related or not self._cooccurrence_graph or not tags:
            return list(result)

        # 2. 扩展查询共现 Tags
        related_tags = await self._cooccurrence_graph.suggest_tags(tags, top_k=max_related)

        for related_tag, _ in related_tags:
            entries = await self.get_by_tag(related_tag)
            for mid, _ in entries:
                result.add(mid)

        return list(result)
