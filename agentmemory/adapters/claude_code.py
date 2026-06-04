"""
Claude Code MCP 协议适配器

使用 MCP (Model Context Protocol) 协议将 MemoryHermes 暴露为 Claude Code 工具。
使用 mcp.server.fastmcp.FastMCP 实现。
"""

import os
import sys
from typing import Any, Optional

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    # Graceful degradation if mcp is not installed
    FastMCP = None

from .base import FrameworkAdapter, ToolSpec


class ClaudeCodeAdapter:
    """
    Claude Code MCP 协议适配器
    
    将 MemoryHermes 包装为 MCP server，暴露 6 个工具：
    - memory_store: 存储记忆
    - memory_query: 查询记忆
    - memory_forget: 遗忘记忆
    - memory_stats: 获取统计
    - memory_prefetch: 预取相关记忆
    - memory_session_end: 会话结束
    """
    
    framework = "claude_code"
    version = "1.0.0"
    
    # Tool definitions in MCP format
    TOOLS = [
        {
            "name": "memory_store",
            "description": "存储新的记忆内容到记忆系统",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "要存储的记忆内容"
                    },
                    "importance": {
                        "type": "number",
                        "description": "重要性评分 (0-1)",
                        "default": 0.5
                    }
                },
                "required": ["content"]
            }
        },
        {
            "name": "memory_query",
            "description": "查询相关记忆（使用混合检索）",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "查询文本"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回结果数量上限",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "memory_forget",
            "description": "删除指定的记忆",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "string",
                        "description": "要删除的记忆 ID"
                    }
                },
                "required": ["memory_id"]
            }
        },
        {
            "name": "memory_stats",
            "description": "获取记忆系统统计信息",
            "inputSchema": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "name": "memory_prefetch",
            "description": "预取相关记忆到缓存",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "预取相关记忆的查询文本"
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "memory_session_end",
            "description": "标记会话结束，生成总结记忆",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "会话 ID"
                    }
                },
                "required": ["session_id"]
            }
        },
    ]
    
    def __init__(self, config_path: str = None):
        """
        初始化 Claude Code 适配器
        
        Args:
            config_path: 可选的配置文件路径
        """
        self.config_path = config_path
        self._mh: Optional[Any] = None
        self._mcp: Optional[Any] = None
        self._mcp_available = FastMCP is not None
        self._mcp_module = FastMCP  # Store for later use when running
    
    def bind(self, mh: Any) -> Any:
        """
        将 MemoryHermes 绑定到 MCP server
        
        Args:
            mh: MemoryHermes 实例
            
        Returns:
            FastMCP server 实例
        """
        self._mh = mh
        
        if not self._mcp_available:
            # MCP not available, return a mock server
            class MockMCP:
                name = "AgentMemory"
                def run(self, transport=None, host=None, port=None):
                    raise RuntimeError("mcp package not installed. Run: pip install mcp>=1.0")
            self._mcp = MockMCP()
            return self._mcp
        
        # Create FastMCP server
        self._mcp = FastMCP(
            name="AgentMemory",
            description="四层闭环记忆系统 - Hermes + Mem0 融合",
        )
        
        # Register tools
        self._register_tools()
        
        return self._mcp
    
    def _register_tools(self):
        """注册所有工具到 MCP server"""
        if self._mcp is None:
            return
        
        # memory_store
        @self._mcp.tool(
            name="memory_store",
            description="存储新的记忆内容",
            risk_level="write"
        )
        async def memory_store(content: str, importance: float = 0.5) -> str:
            """存储记忆"""
            if self._mh is None:
                return '{"error": "MemoryHermes not bound"}'
            
            import asyncio
            result = await self._mh.store(content, importance=importance)
            return f'{{"memory_id": "{result}", "content": "{content[:100]}..."}}'
        
        # memory_query
        @self._mcp.tool(
            name="memory_query",
            description="查询相关记忆",
            risk_level="read"
        )
        async def memory_query(query: str, limit: int = 5) -> str:
            """查询记忆"""
            if self._mh is None:
                return '{"error": "MemoryHermes not bound"}'
            
            import asyncio
            results = await self._mh.query(query, limit)
            
            import json
            out = []
            for r in results:
                out.append({
                    "id": r.get("id"),
                    "content": r.get("content"),
                    "score": round(r.get("score", 0), 4),
                })
            return json.dumps(out, ensure_ascii=False)
        
        # memory_forget
        @self._mcp.tool(
            name="memory_forget",
            description="删除记忆",
            risk_level="destructive"
        )
        async def memory_forget(memory_id: str) -> str:
            """删除记忆"""
            if self._mh is None:
                return '{"error": "MemoryHermes not bound"}'
            
            import asyncio
            success = await self._mh.forget(memory_id)
            return f'{{"success": {str(success).lower()}, "memory_id": "{memory_id}"}}'
        
        # memory_stats
        @self._mcp.tool(
            name="memory_stats",
            description="获取统计信息",
            risk_level="read"
        )
        def memory_stats() -> str:
            """获取统计"""
            if self._mh is None:
                return '{"error": "MemoryHermes not bound"}'
            
            import json
            stats = self._mh.get_stats()
            return json.dumps(stats, ensure_ascii=False)
        
        # memory_prefetch
        @self._mcp.tool(
            name="memory_prefetch",
            description="预取相关记忆",
            risk_level="read"
        )
        async def memory_prefetch(query: str) -> str:
            """预取记忆"""
            if self._mh is None:
                return '{"error": "MemoryHermes not bound"}'
            
            import asyncio
            await self._mh.prefetch(query)
            result = self._mh.get_prefetched(query)
            
            import json
            return json.dumps({"prefetched": result or []}, ensure_ascii=False)
        
        # memory_session_end
        @self._mcp.tool(
            name="memory_session_end",
            description="会话结束",
            risk_level="write"
        )
        async def memory_session_end(session_id: str) -> str:
            """会话结束"""
            if self._mh is None:
                return '{"error": "MemoryHermes not bound"}'
            
            import asyncio
            await self._mh.on_session_end()
            return f'{{"session_id": "{session_id}", "status": "ended"}}'
    
    def export_tools(self, mh: Any = None) -> list[dict]:
        """
        导出工具列表（MCP 格式）
        
        Returns:
            工具字典列表
        """
        return [
            {
                "name": "memory_store",
                "description": "存储新的记忆内容到记忆系统",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "要存储的记忆内容"},
                        "importance": {"type": "number", "description": "重要性评分 (0-1)", "default": 0.5}
                    },
                    "required": ["content"]
                },
                "risk_level": "write"
            },
            {
                "name": "memory_query",
                "description": "查询相关记忆（使用混合检索）",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "查询文本"},
                        "limit": {"type": "integer", "description": "返回结果数量上限", "default": 5}
                    },
                    "required": ["query"]
                },
                "risk_level": "read"
            },
            {
                "name": "memory_forget",
                "description": "删除指定的记忆",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "memory_id": {"type": "string", "description": "要删除的记忆 ID"}
                    },
                    "required": ["memory_id"]
                },
                "risk_level": "destructive"
            },
            {
                "name": "memory_stats",
                "description": "获取记忆系统统计信息",
                "inputSchema": {"type": "object", "properties": {}},
                "risk_level": "read"
            },
            {
                "name": "memory_prefetch",
                "description": "预取相关记忆到缓存",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "预取相关记忆的查询文本"}
                    },
                    "required": ["query"]
                },
                "risk_level": "read"
            },
            {
                "name": "memory_session_end",
                "description": "标记会话结束，生成总结记忆",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string", "description": "会话 ID"}
                    },
                    "required": ["session_id"]
                },
                "risk_level": "write"
            },
        ]
    
    def get_metadata(self) -> dict:
        """
        获取适配器元数据
        
        Returns:
            元数据字典
        """
        return {
            "framework": self.framework,
            "version": self.version,
            "protocol": "mcp",
            "capabilities": {
                "tools": len(self.TOOLS),
                "tool_names": [t["name"] for t in self.TOOLS],
                "risk_levels": ["read", "write", "destructive"],
            },
            "description": "Claude Code MCP protocol adapter for AgentMemory",
        }
    
    def run_stdio(self):
        """启动 stdio 模式的 MCP server"""
        if self._mcp is None:
            raise RuntimeError("Call bind() before run_stdio()")
        
        # Run the MCP server with stdio transport
        self._mcp.run(transport="stdio")
    
    def run_http(self, host: str = "localhost", port: int = 8765):
        """启动 HTTP 模式的 MCP server"""
        if self._mcp is None:
            raise RuntimeError("Call bind() before run_http()")
        
        # Run the MCP server with HTTP/SSE transport
        self._mcp.run(transport="sse", host=host, port=port)


# Module-level convenience function
def create_adapter(config_path: str = None) -> ClaudeCodeAdapter:
    """创建并配置 Claude Code 适配器"""
    adapter = ClaudeCodeAdapter(config_path)
    return adapter
