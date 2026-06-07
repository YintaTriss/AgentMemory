#!/usr/bin/env python3
"""CLI 入口 - AgentMemory 命令行工具

支持 add/search/list/show/delete/category/stats/sign/verify 子命令。
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional

from . import __version__
from .l4_files import L4FilesStore
from .library import LibraryClassifier, TOP_LEVEL_CATEGORIES
from .integrity import sign_file, verify_folder, sign_all_memories


# 默认工作目录（memory 存储位置）
DEFAULT_BASE_DIR = "memory"


def _build_parser() -> argparse.ArgumentParser:
    """构建 CLI 参数解析器"""
    parser = argparse.ArgumentParser(
        prog="agentmemory",
        description=f"AgentMemory v{__version__} - 四层闭环记忆系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--base-dir", default=DEFAULT_BASE_DIR, help="记忆存储目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式（机器可读）")

    subparsers = parser.add_subparsers(dest="command", title="commands", required=True)

    # add 命令
    add_parser = subparsers.add_parser("add", help="添加新记忆")
    add_parser.add_argument("content", help="记忆内容")
    add_parser.add_argument("--importance", type=float, default=0.5, help="重要性 (0-1)")
    add_parser.add_argument("--tags", help="标签，逗号分隔")
    add_parser.add_argument("--category", help="分类路径，如 项目/石榴籽")
    add_parser.add_argument("--source", default="cli", help="来源")

    # search 命令
    search_parser = subparsers.add_parser("search", help="搜索记忆")
    search_parser.add_argument("query", help="搜索查询")
    search_parser.add_argument("--limit", type=int, default=5, help="返回数量限制")
    search_parser.add_argument("--category", help="限定分类路径")

    # list 命令
    list_parser = subparsers.add_parser("list", help="列出记忆")
    list_parser.add_argument("--category", help="限定分类路径")
    list_parser.add_argument("--limit", type=int, default=20, help="返回数量限制")

    # show 命令
    show_parser = subparsers.add_parser("show", help="显示记忆详情")
    show_parser.add_argument("id", help="记忆 ID")

    # delete 命令
    delete_parser = subparsers.add_parser("delete", help="删除记忆")
    delete_parser.add_argument("id", help="记忆 ID")

    # category 命令
    cat_parser = subparsers.add_parser("category", help="分类管理")
    cat_parser.add_argument("--list", action="store_true", help="列出所有已用分类路径")
    cat_parser.add_argument("--show-all", action="store_true", help="显示所有顶层类别")

    # stats 命令
    stats_parser = subparsers.add_parser("stats", help="显示统计信息")

    # P0-4: sign 命令
    sign_parser = subparsers.add_parser("sign", help="对记忆目录进行 HMAC 签名")
    sign_parser.add_argument("dir", help="记忆存储目录")
    sign_parser.add_argument("--key", required=True, help="签名密钥（字符串）")

    # P0-4: verify 命令
    verify_parser = subparsers.add_parser("verify", help="验证记忆目录的 HMAC 签名")
    verify_parser.add_argument("dir", help="记忆存储目录")
    verify_parser.add_argument("--key", required=True, help="签名密钥（字符串）")

    return parser


def _format_json(data: dict, pretty: bool = True) -> str:
    """格式化 JSON 输出"""
    if pretty:
        return json.dumps(data, ensure_ascii=False, indent=2)
    return json.dumps(data, ensure_ascii=False)


def _print_result(data: dict, as_json: bool) -> None:
    """打印结果"""
    if as_json:
        print(_format_json(data))
    else:
        # 友好打印
        if "message" in data:
            print(data["message"])
        elif "content" in data:
            print(data["content"])
        elif "stats" in data:
            for key, val in data["stats"].items():
                print(f"  {key}: {val}")


async def cmd_add(
    content: str,
    importance: float,
    tags: Optional[str],
    category: Optional[str],
    source: str,
    base_dir: str,
    as_json: bool
) -> None:
    """处理 add 命令"""
    store = L4FilesStore(base_dir=base_dir)
    classifier = LibraryClassifier()

    # 解析标签
    tag_list = []
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    # 确定分类
    category_path = category
    if not category_path:
        category_path = classifier.classify(content)

    # 构建元数据
    metadata = {
        "importance": importance,
        "tags": tag_list,
        "category_path": category_path,
        "source": source,
    }

    # 保存记忆
    mem_id = await store.save(content, metadata)

    result = {
        "success": True,
        "id": mem_id,
        "category": category_path,
        "tags": tag_list,
        "message": f"OK: Memory saved with ID: {mem_id}"
    }

    if not as_json:
        result["message"] = f"OK: Memory saved (ID: {mem_id})\n  Category: {category_path}\n  Tags: {', '.join(tag_list) if tag_list else '(none)'}"

    _print_result(result, as_json)


async def cmd_search(
    query: str,
    limit: int,
    category: Optional[str],
    base_dir: str,
    as_json: bool
) -> None:
    """处理 search 命令"""
    store = L4FilesStore(base_dir=base_dir)

    # 获取所有记忆
    all_ids = await store.list_all()

    if not all_ids:
        result = {"success": True, "results": [], "message": "No memories found"}
        _print_result(result, as_json)
        return

    # 简单关键词匹配搜索（fallback 到 L3 未实现时）
    results = []
    for mem_id in all_ids:
        meta = await store.get_meta(mem_id)
        if not meta:
            continue

        # 分类过滤
        if category and not meta.get("category_path", "").startswith(category):
            continue

        content = await store.load(mem_id)
        if not content:
            continue

        # 简单包含匹配
        query_lower = query.lower()
        content_lower = content.lower()

        # 计算匹配分数
        score = 0
        if query_lower in content_lower:
            score = content_lower.count(query_lower)
        elif any(qw in content_lower for qw in query_lower.split()):
            score = 1

        if score > 0:
            results.append({
                "id": mem_id,
                "content": content[:100] + ("..." if len(content) > 100 else ""),
                "full_content": content,
                "score": score,
                "meta": meta,
            })

    # 按分数排序
    results.sort(key=lambda x: x["score"], reverse=True)
    results = results[:limit]

    result = {
        "success": True,
        "query": query,
        "count": len(results),
        "results": results,
    }

    if not as_json:
        if results:
            lines = [f"Found {len(results)} matching memories:\n"]
            for r in results:
                lines.append(f"  [{r['id']}] (score: {r['score']})")
                lines.append(f"    {r['content'][:80]}...")
                lines.append("")
            result["message"] = "\n".join(lines)
        else:
            result["message"] = f"No memories matching '{query}'"

    _print_result(result, as_json)


async def cmd_list(
    category: Optional[str],
    limit: int,
    base_dir: str,
    as_json: bool
) -> None:
    """处理 list 命令"""
    store = L4FilesStore(base_dir=base_dir)

    if category:
        all_memories = await store.get_all_by_category(category)
        mem_ids = [m["id"] for m in all_memories]
    else:
        mem_ids = await store.list_all()
        all_memories = []
        for mid in mem_ids:
            content = await store.load(mid)
            meta = await store.get_meta(mid)
            all_memories.append({"id": mid, "content": content, "meta": meta})

    # 限制数量
    mem_ids = mem_ids[:limit]
    all_memories = all_memories[:limit]

    result = {
        "success": True,
        "count": len(mem_ids),
        "memories": [
            {
                "id": m["id"],
                "preview": (m["content"][:60] + "...") if len(m["content"] or "") > 60 else m["content"],
                "category": m["meta"].get("category_path") if m["meta"] else None,
                "importance": m["meta"].get("importance") if m["meta"] else None,
            }
            for m in all_memories
        ],
    }

    if not as_json:
        if result["memories"]:
            lines = [f"Total {len(mem_ids)} memories:\n"]
            for m in result["memories"]:
                lines.append(f"  [{m['id']}]")
                lines.append(f"    Category: {m['category'] or '(none)'}")
                lines.append(f"    Preview: {m['preview']}")
                lines.append("")
            result["message"] = "\n".join(lines)
        else:
            result["message"] = "No memories"

    _print_result(result, as_json)


async def cmd_show(
    mem_id: str,
    base_dir: str,
    as_json: bool
) -> None:
    """处理 show 命令"""
    store = L4FilesStore(base_dir=base_dir)

    content = await store.load(mem_id)
    if not content:
        result = {"success": False, "message": f"Memory {mem_id} not found"}
        _print_result(result, as_json)
        return

    meta = await store.get_meta(mem_id)

    result = {
        "success": True,
        "id": mem_id,
        "content": content,
        "meta": meta or {},
        "message": f"[{mem_id}]\n  {content}",
    }

    _print_result(result, as_json)


async def cmd_delete(
    mem_id: str,
    base_dir: str,
    as_json: bool
) -> None:
    """处理 delete 命令"""
    store = L4FilesStore(base_dir=base_dir)

    success = await store.delete(mem_id)

    result = {
        "success": success,
        "id": mem_id,
        "message": f"OK: Memory {mem_id} deleted" if success else f"Failed: Memory {mem_id} not found",
    }

    _print_result(result, as_json)


async def cmd_category(
    list_cats: bool,
    show_all: bool,
    base_dir: str,
    as_json: bool
) -> None:
    """处理 category 命令"""
    store = L4FilesStore(base_dir=base_dir)

    if show_all:
        result = {
            "success": True,
            "top_level_categories": TOP_LEVEL_CATEGORIES,
        }
        if not as_json:
            result["message"] = "Top-level categories:\n  " + "\n  ".join(TOP_LEVEL_CATEGORIES)
        _print_result(result, as_json)
        return

    if list_cats:
        categories = store.get_categories()
        result = {
            "success": True,
            "categories": categories,
            "count": len(categories),
        }
        if not as_json:
            result["message"] = f"Used categories ({len(categories)}):\n  " + "\n  ".join(categories) if categories else "No categories used yet"
        _print_result(result, as_json)
        return

    # Default: show all
    result = {"success": True, "message": "Use --list or --show-all"}
    _print_result(result, as_json)


async def cmd_stats(
    base_dir: str,
    as_json: bool
) -> None:
    """处理 stats 命令"""
    store = L4FilesStore(base_dir=base_dir)

    stats = store.get_stats()
    categories = store.get_categories()

    result = {
        "success": True,
        "stats": {
            "memory_count": stats.get("memory_count", 0),
            "total_size_bytes": stats.get("total_size_bytes", 0),
            "category_count": len(categories),
        },
    }

    _print_result(result, as_json)


def cmd_sign(dir_path: str, key: str, as_json: bool) -> None:
    """P0-4: 处理 sign 命令 — 对目录中所有记忆文件进行 HMAC 签名"""
    root = Path(dir_path)
    if not root.is_dir():
        result = {"success": False, "message": f"Directory not found: {dir_path}"}
        _print_result(result, as_json)
        return

    key_bytes = key.encode("utf-8") if isinstance(key, str) else key

    try:
        signed_ids = sign_all_memories(root, key_bytes)
        result = {
            "success": True,
            "signed_count": len(signed_ids),
            "signed_ids": signed_ids,
            "message": f"OK: Signed {len(signed_ids)} memories in {dir_path}",
        }
        _print_result(result, as_json)
    except Exception as e:
        result = {"success": False, "message": f"Sign error: {e}"}
        _print_result(result, as_json)


def cmd_verify(dir_path: str, key: str, as_json: bool) -> None:
    """P0-4: 处理 verify 命令 — 验证目录中所有记忆文件的 HMAC 签名"""
    root = Path(dir_path)
    if not root.is_dir():
        result = {"success": False, "message": f"Directory not found: {dir_path}"}
        _print_result(result, as_json)
        return

    key_bytes = key.encode("utf-8") if isinstance(key, str) else key

    try:
        ok, bad_files = verify_folder(root, key_bytes)
        result = {
            "success": ok,
            "ok": ok,
            "bad_files": bad_files,
            "bad_file_count": len(bad_files),
            "message": "VERIFIED: All signatures valid" if ok else f"FAILED: {len(bad_files)} files with bad signatures",
        }
        _print_result(result, as_json)
    except Exception as e:
        result = {"success": False, "message": f"Verify error: {e}"}
        _print_result(result, as_json)


def main() -> int:
    """CLI 主入口"""
    parser = _build_parser()
    args = parser.parse_args()

    # Build command arguments
    kwargs = vars(args).copy()
    command = kwargs.pop("command")
    as_json = kwargs.pop("json", False)
    base_dir = kwargs.pop("base_dir", DEFAULT_BASE_DIR)

    if command == "sign":
        cmd_sign(kwargs["dir"], kwargs["key"], as_json)
        return 0

    if command == "verify":
        cmd_verify(kwargs["dir"], kwargs["key"], as_json)
        return 0

    # All other commands are async
    if command == "add":
        return asyncio.run(cmd_add(
            content=kwargs["content"],
            importance=kwargs.get("importance", 0.5),
            tags=kwargs.get("tags"),
            category=kwargs.get("category"),
            source=kwargs.get("source", "cli"),
            base_dir=base_dir,
            as_json=as_json,
        )) or 0

    if command == "search":
        return asyncio.run(cmd_search(
            query=kwargs["query"],
            limit=kwargs.get("limit", 5),
            category=kwargs.get("category"),
            base_dir=base_dir,
            as_json=as_json,
        )) or 0

    if command == "list":
        return asyncio.run(cmd_list(
            category=kwargs.get("category"),
            limit=kwargs.get("limit", 20),
            base_dir=base_dir,
            as_json=as_json,
        )) or 0

    if command == "show":
        return asyncio.run(cmd_show(
            mem_id=kwargs["id"],
            base_dir=base_dir,
            as_json=as_json,
        )) or 0

    if command == "delete":
        return asyncio.run(cmd_delete(
            mem_id=kwargs["id"],
            base_dir=base_dir,
            as_json=as_json,
        )) or 0

    if command == "category":
        return asyncio.run(cmd_category(
            list_cats=kwargs.get("list", False),
            show_all=kwargs.get("show_all", False),
            base_dir=base_dir,
            as_json=as_json,
        )) or 0

    if command == "stats":
        return asyncio.run(cmd_stats(
            base_dir=base_dir,
            as_json=as_json,
        )) or 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
