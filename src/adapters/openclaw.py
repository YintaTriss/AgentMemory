"""
OpenClaw CLI 适配器

通过 subprocess 调用 agentmemory CLI 命令实现薄壳适配。
不实现 MCP server，直接转发到 SKILL.md 定义的 CLI 命令。
"""

import json
import subprocess
import sys
import os
from typing import Any, Optional

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .base import FrameworkAdapter, ToolSpec


class OpenClawAdapter:
    """
    OpenClaw CLI 薄壳适配器
    
    不实现 MCP server，而是通过 subprocess 调用 agentmemory CLI 命令：
    - agentmemory store <content> [--importance N]
    - agentmemory query <query> [--limit N]
    - agentmemory forget <memory_id>
    - agentmemory stats
    - agentmemory prefetch <query>
    - agentmemory session-end [--summary TEXT]
    """
    
    framework = "openclaw"
    version = "1.0.0"
    
    def __init__(self, cli_path: str = None):
        """
        初始化 OpenClaw 适配器
        
        Args:
            cli_path: agentmemory CLI 路径，默认使用系统 PATH 中的
        """
        self.cli_path = cli_path or "agentmemory"
    
    def bind(self, mh: Any) -> Any:
        """
        绑定 MemoryHermes（作为上下文，不直接使用）
        
        Args:
            mh: MemoryHermes 实例（仅作为上下文保留）
            
        Returns:
            self (适配器实例)
        """
        # OpenClaw adapter doesn't wrap MemoryHermes directly
        # It calls the CLI commands instead
        self._mh_context = mh
        return self
    
    def _run_cli(self, args: list[str], input_data: str = None) -> dict:
        """
        运行 CLI 命令
        
        Args:
            args: CLI 参数列表
            input_data: 可选的 stdin 输入
            
        Returns:
            命令执行结果字典
        """
        try:
            result = subprocess.run(
                [self.cli_path] + args,
                capture_output=True,
                text=True,
                input=input_data,
                timeout=30,
            )
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Command timeout",
                "returncode": -1,
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": f"CLI not found: {self.cli_path}",
                "returncode": -1,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "returncode": -1,
            }
    
    # Tool methods
    def store(self, content: str, importance: float = 0.5) -> dict:
        """
        存储记忆（v0.3: 使用 add 命令）
        """
        args = ["add", content, "--importance", str(importance)]
        result = self._run_cli(args)

        if result["success"]:
            try:
                data = json.loads(result["stdout"])
                return {
                    "success": data.get("success", False),
                    "memory_id": data.get("memory_id"),
                    "content": content,
                }
            except json.JSONDecodeError:
                return {"success": True, "raw": result["stdout"]}
        else:
            return {"success": False, "error": result.get("error") or result["stderr"]}

    def query(self, query_text: str, limit: int = 5) -> dict:
        """
        查询记忆（v0.3: 使用 search 命令）
        """
        args = ["search", query_text, "--limit", str(limit)]
        result = self._run_cli(args)

        if result["success"]:
            try:
                data = json.loads(result["stdout"])
                results = data.get("results", []) if isinstance(data, dict) else data
                return {
                    "success": True,
                    "results": results,
                    "count": len(results) if isinstance(results, list) else 0,
                }
            except json.JSONDecodeError:
                return {"success": True, "raw": result["stdout"]}
        else:
            return {"success": False, "error": result.get("error") or result["stderr"]}

    def forget(self, memory_id: str, permanent: bool = False) -> dict:
        """
        删除记忆（v0.3: 使用 delete 命令）
        """
        del_args = ["delete", memory_id]
        result = self._run_cli(del_args)

        if result["success"]:
            try:
                data = json.loads(result["stdout"])
                return {
                    "success": data.get("success", False),
                    "memory_id": memory_id,
                }
            except json.JSONDecodeError:
                return {"success": True, "raw": result["stdout"]}
        else:
            return {"success": False, "error": result.get("error") or result["stderr"]}
    
    def stats(self) -> dict:
        """
        获取统计信息
        
        Returns:
            统计结果
        """
        result = self._run_cli(["stats"])
        
        if result["success"]:
            try:
                return {
                    "success": True,
                    "stats": json.loads(result["stdout"]),
                }
            except json.JSONDecodeError:
                return {"success": True, "raw": result["stdout"]}
        else:
            return {"success": False, "error": result.get("error") or result["stderr"]}
    
    def prefetch(self, query: str) -> dict:
        """
        预取相关记忆
        
        Args:
            query: 查询文本
            
        Returns:
            预取结果
        """
        result = self._run_cli(["prefetch", query])
        
        if result["success"]:
            try:
                data = json.loads(result["stdout"])
                return {
                    "success": True,
                    "prefetched": data,
                }
            except json.JSONDecodeError:
                return {"success": True, "raw": result["stdout"]}
        else:
            return {"success": False, "error": result.get("error") or result["stderr"]}
    
    def session_end(self, summary: str = None) -> dict:
        """
        会话结束
        
        Args:
            summary: 可选的会话总结
            
        Returns:
            执行结果
        """
        args = ["session-end"]
        if summary:
            args.extend(["--summary", summary])
        
        result = self._run_cli(args)
        
        if result["success"]:
            return {
                "success": True,
                "status": "ended",
            }
        else:
            return {"success": False, "error": result.get("error") or result["stderr"]}
    
    def export_tools(self, mh: Any = None) -> list[dict]:
        """
        导出工具列表（CLI 格式）
        
        Returns:
            工具字典列表
        """
        return [
            {
                "name": "memory_store",
                "description": "通过 CLI 存储记忆",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                        "importance": {"type": "number", "default": 0.5}
                    },
                    "required": ["content"]
                },
                "risk_level": "write"
            },
            {
                "name": "memory_query",
                "description": "通过 CLI 查询记忆",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "default": 5}
                    },
                    "required": ["query"]
                },
                "risk_level": "read"
            },
            {
                "name": "memory_forget",
                "description": "通过 CLI 删除记忆",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "memory_id": {"type": "string"},
                        "permanent": {"type": "boolean", "default": False}
                    },
                    "required": ["memory_id"]
                },
                "risk_level": "destructive"
            },
            {
                "name": "memory_stats",
                "description": "通过 CLI 获取统计",
                "parameters": {"type": "object", "properties": {}},
                "risk_level": "read"
            },
            {
                "name": "memory_prefetch",
                "description": "通过 CLI 预取记忆",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"}
                    },
                    "required": ["query"]
                },
                "risk_level": "read"
            },
            {
                "name": "memory_session_end",
                "description": "通过 CLI 结束会话",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"}
                    }
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
            "protocol": "cli",
            "capabilities": {
                "tools": 6,
                "tool_names": [
                    "memory_store",
                    "memory_query",
                    "memory_forget",
                    "memory_stats",
                    "memory_prefetch",
                    "memory_session_end",
                ],
                "risk_levels": ["read", "write", "destructive"],
            },
            "description": "OpenClaw CLI adapter for AgentMemory",
            "cli_path": self.cli_path,
        }
    
    def _cli_manifest(self, mh: Any = None) -> dict:
        """
        生成 CLI manifest（SKILL.md 格式）
        
        Args:
            mh: MemoryHermes 实例（可选）
            
        Returns:
            CLI manifest 字典
        """
        return {
            "name": "agentmemory",
            "description": "四层闭环记忆系统 CLI 适配器",
            "commands": {
                "store": {
                    "description": "存储记忆",
                    "args": ["text"],
                    "flags": ["--importance", "--metadata"]
                },
                "query": {
                    "description": "查询记忆",
                    "args": ["text"],
                    "flags": ["--limit", "--tags"]
                },
                "forget": {
                    "description": "遗忘记忆",
                    "args": ["memory_id"],
                    "flags": ["--permanent"]
                },
                "stats": {
                    "description": "获取统计",
                    "args": [],
                    "flags": []
                },
                "prefetch": {
                    "description": "预取记忆",
                    "args": ["text"],
                    "flags": []
                },
                "session-end": {
                    "description": "会话结束",
                    "args": [],
                    "flags": ["--summary"]
                }
            }
        }
    
    def run_http_server(self, host: str = "localhost", port: int = 8765):
        """
        启动 HTTP REST API server
        
        Args:
            host: 监听地址
            port: 监听端口
        """
        import asyncio
        from aiohttp import web
        
        async def handle_store(request):
            data = await request.json()
            result = self.store(
                data.get("content", ""),
                data.get("importance", 0.5)
            )
            return web.json_response(result)
        
        async def handle_query(request):
            data = await request.json()
            result = self.query(
                data.get("query", ""),
                data.get("limit", 5)
            )
            return web.json_response(result)
        
        async def handle_forget(request):
            data = await request.json()
            result = self.forget(
                data.get("memory_id", ""),
                data.get("permanent", False)
            )
            return web.json_response(result)
        
        async def handle_stats(request):
            result = self.stats()
            return web.json_response(result)
        
        async def handle_prefetch(request):
            data = await request.json()
            result = self.prefetch(data.get("query", ""))
            return web.json_response(result)
        
        async def handle_session_end(request):
            data = await request.json()
            result = self.session_end(data.get("summary"))
            return web.json_response(result)
        
        app = web.Application()
        app.router.add_post("/memory/store", handle_store)
        app.router.add_post("/memory/query", handle_query)
        app.router.add_post("/memory/forget", handle_forget)
        app.router.add_get("/memory/stats", handle_stats)
        app.router.add_post("/memory/prefetch", handle_prefetch)
        app.router.add_post("/memory/session-end", handle_session_end)
        
        print(f"Starting HTTP server on {host}:{port}")
        web.run_app(app, host=host, port=port)


# Module-level convenience function
def create_adapter(cli_path: str = None) -> OpenClawAdapter:
    """创建并配置 OpenClaw 适配器"""
    return OpenClawAdapter(cli_path)
