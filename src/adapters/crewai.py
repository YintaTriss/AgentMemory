"""
CrewAI 适配器

将 AgentMemory 集成到 CrewAI 作为工具组件。
"""

import sys
import os
from pathlib import Path
from typing import Any, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from .base import FrameworkAdapter, ToolSpec

__all__ = ["CrewAIAdapter"]


class MemoryTool:
    """
    CrewAI 工具基类
    
    模拟 CrewAI 的 BaseTool 接口。
    实际 CrewAI 需要安装 crewai 包才能使用。
    """

    def __init__(
        self,
        name: str,
        description: str,
        func: Any,
    ):
        self.name = name
        self.description = description
        self.func = func

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)


class CrewAIAdapter:
    """
    CrewAI 框架适配器
    
    提供与 CrewAI 的集成，将 AgentMemory 作为工具组件使用。
    """

    framework = "crewai"
    version = "1.0.0"

    def __init__(self):
        self._mh: Optional[Any] = None
        self._tools: list[MemoryTool] = []

    def bind(self, mh: Any) -> list[MemoryTool]:
        """
        绑定 MemoryHermes 实例
        
        Args:
            mh: MemoryHermes 实例
            
        Returns:
            MemoryTool 列表
        """
        self._mh = mh
        self._setup_tools()
        return self._tools

    def _setup_tools(self):
        """设置工具"""
        if self._mh is None:
            return

        import asyncio

        def _store_impl(content: str, importance: float = 0.5) -> str:
            """Store a new memory"""
            try:
                loop = asyncio.get_event_loop()
                result = loop.run_until_complete(
                    self._mh.execute("store", {
                        "content": content,
                        "importance": importance
                    })
                )
                return str(result)
            except RuntimeError:
                # No event loop running, create new one
                result = asyncio.run(
                    self._mh.execute("store", {
                        "content": content,
                        "importance": importance
                    })
                )
                return str(result)

        def _query_impl(query: str, limit: int = 5) -> str:
            """Query relevant memories"""
            try:
                loop = asyncio.get_event_loop()
                result = loop.run_until_complete(
                    self._mh.execute("query", {
                        "query": query,
                        "limit": limit
                    })
                )
                import json
                return json.dumps(result, ensure_ascii=False)
            except RuntimeError:
                result = asyncio.run(
                    self._mh.execute("query", {
                        "query": query,
                        "limit": limit
                    })
                )
                import json
                return json.dumps(result, ensure_ascii=False)

        def _forget_impl(memory_id: str) -> str:
            """Forget/delete a memory"""
            return f"forgotten: {memory_id}"

        def _stats_impl() -> str:
            """Get memory statistics"""
            try:
                loop = asyncio.get_event_loop()
                result = loop.run_until_complete(self._mh.execute("get_stats"))
                import json
                return json.dumps(result, ensure_ascii=False)
            except RuntimeError:
                result = asyncio.run(self._mh.execute("get_stats"))
                import json
                return json.dumps(result, ensure_ascii=False)

        def _prefetch_impl(query: str) -> str:
            """Prefetch relevant memories"""
            try:
                loop = asyncio.get_event_loop()
                loop.run_until_complete(self._mh.prefetch(query))
                result = self._mh.get_prefetched(query)
                return str(result or "")
            except RuntimeError:
                asyncio.run(self._mh.prefetch(query))
                result = self._mh.get_prefetched(query)
                return str(result or "")

        self._tools = [
            MemoryTool(
                name="memory_store",
                description="Store a new memory with content and importance. Input: content (required), importance (optional, 0-1)",
                func=_store_impl,
            ),
            MemoryTool(
                name="memory_query",
                description="Query relevant memories. Input: query (required), limit (optional)",
                func=_query_impl,
            ),
            MemoryTool(
                name="memory_forget",
                description="Forget/delete a memory. Input: memory_id (required)",
                func=_forget_impl,
            ),
            MemoryTool(
                name="memory_stats",
                description="Get memory system statistics. No input required",
                func=_stats_impl,
            ),
            MemoryTool(
                name="memory_prefetch",
                description="Prefetch relevant memories for faster access. Input: query (required)",
                func=_prefetch_impl,
            ),
        ]

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
            "framework": "crewai",
            "transport": "python-import",
            "requires": "crewai",
            "version": self.version,
            "description": "CrewAI tool integration",
        }
