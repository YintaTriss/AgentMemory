"""
OpenAI Agents SDK 适配器

将 AgentMemory 集成到 OpenAI Agents SDK 作为工具函数。
"""

import sys
import os
from pathlib import Path
from typing import Any, Optional, Callable

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from .base import FrameworkAdapter, ToolSpec

__all__ = ["OpenAIAgentsAdapter"]


class OpenAIAgentsAdapter:
    """
    OpenAI Agents SDK 框架适配器
    
    提供与 OpenAI Agents SDK 的集成，将 AgentMemory 作为工具函数使用。
    """

    framework = "openai_agents"
    version = "1.0.0"

    def __init__(self):
        self._mh: Optional[Any] = None
        self._tools: dict[str, Callable] = {}

    def bind(self, mh: Any) -> dict[str, Callable]:
        """
        绑定 MemoryHermes 实例
        
        Args:
            mh: MemoryHermes 实例
            
        Returns:
            工具函数字典 {tool_name: function}
        """
        self._mh = mh
        self._setup_tools()
        return self._tools

    def _setup_tools(self):
        """设置工具函数"""
        if self._mh is None:
            return

        # Import asyncio for async operations
        import asyncio

        async def _store(content: str, importance: float = 0.5, metadata: dict = None) -> str:
            """Store a new memory"""
            result = await self._mh.execute("store", {
                "content": content,
                "importance": importance,
                "metadata": metadata or {}
            })
            return str(result)

        async def _query(query: str, limit: int = 5) -> str:
            """Query relevant memories"""
            result = await self._mh.execute("query", {
                "query": query,
                "limit": limit
            })
            import json
            return json.dumps(result, ensure_ascii=False)

        async def _forget(memory_id: str) -> str:
            """Forget/delete a memory"""
            return f"forgotten: {memory_id}"

        async def _stats() -> str:
            """Get memory statistics"""
            result = await self._mh.execute("get_stats")
            import json
            return json.dumps(result, ensure_ascii=False)

        async def _prefetch(query: str) -> str:
            """Prefetch relevant memories"""
            await self._mh.prefetch(query)
            result = self._mh.get_prefetched(query)
            return str(result or "")

        self._tools = {
            "memory_store": _store,
            "memory_query": _query,
            "memory_forget": _forget,
            "memory_stats": _stats,
            "memory_prefetch": _prefetch,
        }

    def export_tools(self) -> list[ToolSpec]:
        """
        导出工具列表
        
        Returns:
            5 个 ToolSpec 实例
        """
        return [
            ToolSpec(
                name="memory_store",
                description="Store a new memory with content and importance",
                parameters={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Memory content"},
                        "importance": {
                            "type": "number",
                            "description": "Importance 0-1",
                            "default": 0.5,
                        },
                        "metadata": {
                            "type": "object",
                            "description": "Additional metadata",
                        },
                    },
                    "required": ["content"],
                },
                risk_level="write",
            ),
            ToolSpec(
                name="memory_query",
                description="Query relevant memories",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Query text"},
                        "limit": {
                            "type": "integer",
                            "description": "Max results",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
                risk_level="read",
            ),
            ToolSpec(
                name="memory_forget",
                description="Forget/delete a memory",
                parameters={
                    "type": "object",
                    "properties": {
                        "memory_id": {"type": "string", "description": "Memory ID"},
                    },
                    "required": ["memory_id"],
                },
                risk_level="destructive",
            ),
            ToolSpec(
                name="memory_stats",
                description="Get memory system statistics",
                parameters={"type": "object", "properties": {}},
                risk_level="read",
            ),
            ToolSpec(
                name="memory_prefetch",
                description="Prefetch relevant memories for faster access",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Query text"},
                    },
                    "required": ["query"],
                },
                risk_level="read",
            ),
        ]

    def get_metadata(self) -> dict:
        """
        获取适配器元数据
        
        Returns:
            元数据字典
        """
        return {
            "framework": "openai_agents",
            "transport": "python-import",
            "requires": "openai>=1.0",
            "version": self.version,
            "description": "OpenAI Agents SDK function tools integration",
        }
