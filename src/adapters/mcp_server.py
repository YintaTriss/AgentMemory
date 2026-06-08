"""
AgentMemory MCP Server 适配器

使用 MCP (Model Context Protocol) 将 v0.3 的 MemoryManager 暴露为工具。
支持 Claude Code、Codex、Cursor、WindSurf 等所有 MCP 兼容客户端。

运行方式：
    agentmemory mcp                    # stdio 模式（Claude Code / Codex）
    agentmemory mcp --http --port 8765 # HTTP 模式（其他客户端）

MCP 工具列表：
    memory_add      添加记忆
    memory_search   语义/关键词/混合搜索
    memory_list     按分类列出记忆
    memory_get      获取单条记忆详情
    memory_delete   删除记忆
    memory_stats    系统统计
    memory_compress L1 上下文压缩
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import os
from typing import Any, List, Optional

# ── path bootstrap ────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
from src.agent_memory import MemoryManager

# ── global manager instance (created once per server run) ───────────────────
_manager: Optional[MemoryManager] = None


def get_manager() -> MemoryManager:
    global _manager
    if _manager is None:
        _manager = MemoryManager()
    return _manager


# ── MCP server definition ────────────────────────────────────────────────────
mcp = FastMCP(
    name="AgentMemory",
    instructions=(
        "AgentMemory v0.3 — 双轨 + 图书馆记忆系统。\n"
        "所有记忆同时存在于：1) 图书馆分类轨（精确）2) Embedding 向量轨（语义）。\n"
        "默认使用语义搜索；可选 --mode bm25（关键词）或 hybrid（混合）。\n"
        "分类路径最少 3 层，如 项目/石榴籽/进度。"
    ),
)

# ── tool: memory_add ─────────────────────────────────────────────────────────
@mcp.tool(name="memory_add", description="添加新记忆到双轨记忆系统")
async def memory_add(
    content: str,
    importance: float = 0.5,
    tags: str = "",
    category: str = "",
    source: str = "mcp",
) -> str:
    """
    添加一条新记忆。

    Args:
        content: 记忆内容（必填）
        importance: 重要性 0-1（默认 0.5）
        tags: 逗号分隔标签（可选）
        category: 分类路径，最少 3 层如 项目/石榴籽（可选，自动归类）
        source: 来源标记（默认 mcp）
    """
    mm = get_manager()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    cat = category or None

    try:
        mem_id = await mm.add(
            content=content,
            importance=importance,
            category_path=cat,
            tags=tag_list,
            source=source,
        )
        return json.dumps({"success": True, "memory_id": mem_id}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


# ── tool: memory_search ──────────────────────────────────────────────────────
@mcp.tool(
    name="memory_search",
    description="搜索记忆（语义/关键词/混合，默认语义向量搜索）",
)
async def memory_search(
    query: str,
    limit: int = 5,
    mode: str = "vector",
    category: str = "",
) -> str:
    """
    搜索记忆。

    Args:
        query: 搜索查询文本
        limit: 返回数量上限（默认 5）
        mode: 搜索模式 — vector=语义（默认）, bm25=关键词, hybrid=混合
        category: 限定分类路径（可选）
    """
    if mode not in ("vector", "bm25", "hybrid"):
        mode = "vector"

    mm = get_manager()
    cat = category or None

    try:
        results = await mm.search(query, limit=limit, category_path=cat)
        output = []
        for r in results:
            output.append({
                "memory_id": r.get("id"),
                "content": r.get("content"),
                "score": round(r.get("score", 0), 4),
                "category_path": r.get("category_path"),
                "tags": r.get("tags", []),
            })
        return json.dumps({"success": True, "results": output, "count": len(output)}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


# ── tool: memory_list ────────────────────────────────────────────────────────
@mcp.tool(name="memory_list", description="按分类路径列出记忆")
async def memory_list(
    category: str = "",
    limit: int = 20,
) -> str:
    """
    按分类列出记忆。

    Args:
        category: 分类路径前缀（如 项目/石榴籽），空则列出全部
        limit: 返回数量上限（默认 20）
    """
    mm = get_manager()
    cat = category or None

    try:
        memories = await mm.list(category_path=cat, limit=limit)
        output = []
        for m in memories:
            output.append({
                "memory_id": m.get("id"),
                "content": m.get("content"),
                "category_path": m.get("category_path"),
                "tags": m.get("tags", []),
                "created_at": m.get("created_at"),
            })
        return json.dumps({"success": True, "memories": output, "count": len(output)}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


# ── tool: memory_get ────────────────────────────────────────────────────────
@mcp.tool(name="memory_get", description="获取单条记忆的完整内容")
async def memory_get(memory_id: str) -> str:
    """
    获取单条记忆详情。

    Args:
        memory_id: 记忆 ID
    """
    mm = get_manager()

    try:
        mem = await mm.get(memory_id)
        if mem is None:
            return json.dumps({"success": False, "error": "Memory not found"}, ensure_ascii=False)
        return json.dumps({"success": True, "memory": mem}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


# ── tool: memory_delete ─────────────────────────────────────────────────────
@mcp.tool(name="memory_delete", description="删除指定记忆")
async def memory_delete(memory_id: str) -> str:
    """
    删除一条记忆（L4 文件 + L3 向量同时清除）。

    Args:
        memory_id: 要删除的记忆 ID
    """
    mm = get_manager()

    try:
        ok = await mm.delete(memory_id)
        return json.dumps({"success": ok, "memory_id": memory_id}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


# ── tool: memory_stats ──────────────────────────────────────────────────────
@mcp.tool(name="memory_stats", description="获取记忆系统统计信息")
async def memory_stats() -> str:
    """返回当前记忆总数、各分类数量、总大小等统计。"""
    mm = get_manager()

    try:
        stats = await mm.stats()
        return json.dumps({"success": True, "stats": stats}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


# ── tool: memory_compress ──────────────────────────────────────────────────
@mcp.tool(
    name="memory_compress",
    description="将多条记忆压缩为 L1 摘要，用于注入 AI Context（带 query 相关性增强）",
)
async def memory_compress(
    memory_ids: List[str],
    query: str = "",
) -> str:
    """
    L1 上下文压缩。

    Args:
        memory_ids: 要压缩的记忆 ID 列表
        query: 查询关键词（影响摘要相关性排序，可为空）
    """
    mm = get_manager()

    try:
        compressed = await mm.compress_for_context(memory_ids, query=query)
        return json.dumps({"success": True, "compressed": compressed}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


# ── CLI 入口 ────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(prog="agentmemory mcp", description="AgentMemory MCP Server")
    parser.add_argument("--http", action="store_true", help="启动 HTTP/SSE 模式（默认 stdio）")
    parser.add_argument("--port", type=int, default=8765, help="HTTP 模式端口（默认 8765）")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP 模式主机（默认 127.0.0.1）")
    args = parser.parse_args()

    if args.http:
        print(f"Starting AgentMemory MCP server on http://{args.host}:{args.port}", file=sys.stderr)
        mcp.run_streamable_http_async(
            host=args.host,
            port=args.port,
            path="/mcp",
        )
    else:
        # stdio 模式 — Claude Code / Codex 标准模式
        mcp.run_stdio_async()


if __name__ == "__main__":
    main()
