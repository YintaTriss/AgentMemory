"""
AgentMemoryTool — agent 框架可调用的记忆工具接口。
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional


class AgentMemoryTool:
    """给 agent（OpenClaw/Claude Code/VCP）用的记忆工具接口。"""

    def __init__(self, memory_manager=None):
        self._mm = memory_manager

    async def add(
        self, content: str, category: str = "general",
        tags: Optional[List[str]] = None, importance: float = 0.5,
        namespace: str = "default",
    ) -> Dict[str, Any]:
        if not self._mm:
            return {"error": "memory_manager not configured"}
        mem_id = await self._mm.add(content, namespace=namespace, meta={
            "category": category, "tags": tags or [], "importance": importance,
        })
        return {"id": mem_id, "status": "ok"}

    async def search(
        self, query: str, top_k: int = 5, namespace: str = "default",
        mode: str = "hybrid",
    ) -> List[Dict[str, Any]]:
        if not self._mm:
            return [{"error": "memory_manager not configured"}]
        results = await self._mm.search(query, top_k=top_k, namespace=namespace)
        return [{
            "content": r.get("content", ""),
            "id": r.get("id", ""),
            "score": r.get("score", 0),
            "category": r.get("meta", {}).get("category", ""),
            "tags": r.get("meta", {}).get("tags", []),
        } for r in results]

    async def recent(
        self, limit: int = 5, namespace: str = "default",
    ) -> List[Dict[str, Any]]:
        if not self._mm:
            return [{"error": "memory_manager not configured"}]
        results = await self._mm.list(limit=limit, namespace=namespace)
        return [{
            "content": r.get("content", ""),
            "id": r.get("id", ""),
            "created_at": r.get("meta", {}).get("created_at", ""),
        } for r in results]

    async def stats(self, namespace: str = "default") -> Dict[str, Any]:
        if not self._mm:
            return {"error": "memory_manager not configured"}
        mems = await self._mm.list(limit=10000, namespace=namespace)
        return {
            "total": len(mems),
            "namespace": namespace,
        }

    def tool_definition(self) -> Dict[str, Any]:
        return {
            "name": "agentmemory",
            "description": "记忆系统：添加、搜索、列出记忆",
            "functions": [
                {
                    "name": "add",
                    "params": {
                        "content": {"type": "string", "required": True},
                        "category": {"type": "string", "default": "general"},
                        "tags": {"type": "array", "items": "string"},
                        "importance": {"type": "number", "default": 0.5},
                    },
                },
                {
                    "name": "search",
                    "params": {
                        "query": {"type": "string", "required": True},
                        "top_k": {"type": "number", "default": 5},
                        "mode": {"type": "string", "default": "hybrid"},
                    },
                },
                {
                    "name": "recent",
                    "params": {"limit": {"type": "number", "default": 5}},
                },
            ],
        }
