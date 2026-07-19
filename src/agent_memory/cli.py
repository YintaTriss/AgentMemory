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
from datetime import datetime
from typing import Optional

from . import __version__
from .l4_files import L4FilesStore
from .library import LibraryClassifier, TOP_LEVEL_CATEGORIES
from .bm25 import BM25Indexer
from .integrity import sign_file, verify_folder, sign_all_memories
from .embedder import get_embedder
from .observability import metrics


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
    add_parser.add_argument("--namespace", help="命名空间")

    # search 命令
    search_parser = subparsers.add_parser("search", help="搜索记忆")
    search_parser.add_argument("query", help="搜索查询")
    search_parser.add_argument("--limit", type=int, default=5, help="返回数量限制")
    search_parser.add_argument("--category", help="限定分类路径")
    search_parser.add_argument(
        "--mode",
        choices=["vector", "bm25", "hybrid"],
        default="vector",
        help="搜索模式: vector=语义, bm25=关键词, hybrid=混合 (default: vector)",
    )
    search_parser.add_argument("--namespace", help="命名空间")

    # list 命令
    list_parser = subparsers.add_parser("list", help="列出记忆")
    list_parser.add_argument("--category", help="限定分类路径")
    list_parser.add_argument("--limit", type=int, default=20, help="返回数量限制")
    list_parser.add_argument("--namespace", help="命名空间")

    # show 命令
    show_parser = subparsers.add_parser("show", help="显示记忆详情")
    show_parser.add_argument("id", help="记忆 ID")
    show_parser.add_argument("--namespace", help="命名空间")

    # delete 命令
    delete_parser = subparsers.add_parser("delete", help="删除记忆")
    delete_parser.add_argument("id", help="记忆 ID")
    delete_parser.add_argument("--namespace", help="命名空间")

    # category 命令
    cat_parser = subparsers.add_parser("category", help="分类管理")
    cat_parser.add_argument("--list", action="store_true", help="列出所有已用分类路径")
    cat_parser.add_argument("--show-all", action="store_true", help="显示所有顶层类别")

    # stats 命令
    stats_parser = subparsers.add_parser("stats", help="显示统计信息")
    stats_parser.add_argument("--namespace", help="命名空间")

    # doctor 命令 — 环境诊断
    doctor_parser = subparsers.add_parser("doctor", help="运行环境诊断（依赖/路径/环境变量）")
    doctor_parser.add_argument("--strict", action="store_true", help="严格模式：警告也算失败")

    # P0-4: sign 命令
    sign_parser = subparsers.add_parser("sign", help="对记忆目录进行 HMAC 签名")
    sign_parser.add_argument("dir", help="记忆存储目录")
    sign_parser.add_argument("--key", required=True, help="签名密钥（字符串）")

    # P0-4: verify 命令
    verify_parser = subparsers.add_parser("verify", help="验证记忆目录的 HMAC 签名")
    verify_parser.add_argument("dir", help="记忆存储目录")
    verify_parser.add_argument("--key", required=True, help="签名密钥（字符串）")

    # reembed 命令
    reembed_parser = subparsers.add_parser("reembed", help="重新向量化所有记忆")
    reembed_parser.add_argument(
        "--embedder",
        choices=["hash", "dashscope"],
        default="hash",
        help="使用的 Embedder 类型 (default: hash)",
    )

    # mcp 命令
    mcp_parser = subparsers.add_parser("mcp", help="启动 MCP Server（Claude Code / Codex 兼容）")
    mcp_parser.add_argument("--http", action="store_true", help="启动 HTTP/SSE 模式（默认 stdio）")
    mcp_parser.add_argument("--port", type=int, default=8765, help="HTTP 模式端口 (default: 8765)")
    mcp_parser.add_argument("--host", default="127.0.0.1", help="HTTP 模式主机 (default: 127.0.0.1)")

    # bg 命令（透明后台）
    bg_parser = subparsers.add_parser("bg", help="启动透明后台记忆捕获器")
    bg_parser.add_argument("--agent-id", default="default", help="Agent ID")
    bg_parser.add_argument("--base-dir", default=DEFAULT_BASE_DIR, help="记忆存储目录")
    bg_parser.add_argument("--importance", type=float, default=0.6, help="默认重要性 (default: 0.6)")
    bg_parser.add_argument("--interval", type=int, default=5, help="心跳间隔分钟数 (default: 5)")
    bg_parser.add_argument("--once", action="store_true", help="只运行一次然后退出")

    # dream 命令
    dream_parser = subparsers.add_parser("dream", help="启动梦境处理循环")
    dream_parser.add_argument("--namespace", default="default", help="命名空间")
    dream_parser.add_argument("--phase", choices=["light", "deep", "rem"], default="deep", help="梦境阶段")
    dream_parser.add_argument("--dry-run", action="store_true", help="仅模拟，不写入")
    dream_parser.add_argument("--once", action="store_true", default=True, help="只运行一次 (default: True)")
    dream_parser.add_argument("--interval", type=int, default=300, help="循环间隔秒数 (default: 300)")
    dream_parser.add_argument("--db-path", default="data/agentmemory.db", help="SQLite 数据库路径")

    # serve 命令
    serve_parser = subparsers.add_parser("serve", help="启动 Web API 服务器")
    serve_parser.add_argument("--port", type=int, default=8765, help="监听端口 (default: 8765)")
    serve_parser.add_argument("--host", default="0.0.0.0", help="监听地址 (default: 0.0.0.0)")

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
        if "message" in data:
            print(data["message"])
        elif "content" in data:
            print(data["content"])
        elif "stats" in data:
            for key, val in data["stats"].items():
                print(f"  {key}: {val}")


def _get_l3_store(db_path: str):
    """返回 L3 store 实例（仅 Qdrant Edge）。"""
    from .l3_qdrant import L3QdrantStore
    return L3QdrantStore(db_path=db_path)


def _qdrant_path(base_dir: str) -> str:
    """返回 Qdrant data 目录路径。"""
    return os.path.join(os.path.dirname(base_dir.rstrip("/\\")), "data", "qdrant")


async def cmd_add(
    content: str,
    importance: float,
    tags: Optional[str],
    category: Optional[str],
    source: str,
    base_dir: str,
    as_json: bool,
) -> None:
    """处理 add 命令"""
    # BUG-3 (P2) fix: reject empty/whitespace content before saving to L4 or L3.
    # Without this, agentmemory add "    " creates phantom memories.
    if not isinstance(content, str) or not content.strip():
        raise ValueError(
            f"cmd_add: content must be a non-empty string "
            f"(got {type(content).__name__}: {content!r})"
        )

    store = L4FilesStore(base_dir=base_dir)
    classifier = LibraryClassifier()

    tag_list = []
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    category_path = category
    if not category_path:
        category_path = classifier.classify(content)

    metadata = {
        "importance": importance,
        "tags": tag_list,
        "category_path": category_path,
        "source": source,
    }

    import ulid
    memory_id = str(ulid.ULID())
    now = datetime.now().isoformat()
    full_meta = {
        "id": memory_id,
        "created_at": now,
        "updated_at": now,
        **metadata,
    }
    mem_id = await store.save(memory_id, content, full_meta)

    # 同步到 L3（Qdrant Edge 向量存储）
    _db_path = _qdrant_path(base_dir)
    _l3 = _get_l3_store(_db_path)
    _embedder = get_embedder()
    _embed_fn = _embedder.embed_sync if hasattr(_embedder, "embed_sync") else _embedder.embed
    _vec = _embed_fn(content)

    # BUG-4 (P1) fix: validate embedder output before passing to L3.
    # HashEmbedder may return None or non-list on whitespace-only content.
    if not _vec or not isinstance(_vec, list) or not all(
        isinstance(x, (int, float)) for x in _vec
    ):
        if isinstance(_vec, list):
            vec_repr = f"list[{len(_vec)}]"
        else:
            vec_repr = repr(_vec)
        raise ValueError(
            f"cmd_add: embedder returned invalid vector for content={content!r}: "
            f"{type(_vec).__name__} ({vec_repr})"
        )

    _l3.upsert(
        id=memory_id, content=content, vector=_vec, metadata=full_meta,
        importance=full_meta.get("importance", 0.5),
        category_path=full_meta.get("category_path", "general"),
        created_at=full_meta.get("created_at"),
    )

    metrics.inc_add()

    result = {
        "success": True,
        "id": mem_id,
        "category": category_path,
        "tags": tag_list,
        "message": f"OK: Memory saved with ID: {mem_id}",
    }

    if not as_json:
        result["message"] = (
            f"OK: Memory saved (ID: {mem_id})\n"
            f"  Category: {category_path}\n"
            f"  Tags: {', '.join(tag_list) if tag_list else '(none)'}"
        )

    _print_result(result, as_json)


async def cmd_search(
    query: str,
    limit: int,
    category: Optional[str],
    mode: str,
    base_dir: str,
    as_json: bool,
) -> None:
    """处理 search 命令 — 支持 vector / bm25 / hybrid 三种模式"""
    store = L4FilesStore(base_dir=base_dir)
    db_path = _qdrant_path(base_dir)
    l3_store = _get_l3_store(db_path)
    # Use L3's embedder (FastEmbed with correct dimensions) — not get_embedder()
    # get_embedder() returns HashEmbedder(384-dim) without API key, causing
    # dimension mismatch with 512-dim FastEmbed vectors stored in Qdrant
    embedder = l3_store._embedder

    if mode == "bm25":
        all_records = l3_store.get_all()
        if not all_records:
            raw = []
        else:
            texts = [r.get("content", "") or "" for r in all_records]
            indexer = BM25Indexer(k1=1.2, b=0.75)
            indexer.index(texts)
            bm25_results = indexer.search(query, top_k=limit)
            raw = []
            for bm in bm25_results:
                rec = all_records[bm["doc_index"]]
                raw.append({
                    "id": rec.get("id", ""),
                    "content": rec.get("content", ""),
                    "bm25_score": bm["bm25_score"],
                    "category_path": rec.get("category_path", ""),
                })
        results = [
            {
                "id": r["id"],
                "content": (r["content"][:100] + "...") if len(r["content"] or "") > 100 else r.get("content", ""),
                "score": r.get("bm25_score", r.get("score", 0)),
                "category_path": r.get("category_path", ""),
            }
            for r in raw
        ]
        metrics.inc_search("bm25")
        metrics.inc_bm25_fallback()
    elif mode == "hybrid":
        # Proper hybrid: RRF (Reciprocal Rank Fusion) - industry standard
        # RRF = 1/(k+rank_vector) + 1/(k+rank_bm25), k=60
        RRF_K = 60
        query_vector = embedder.embed(query)
        vector_results = l3_store.search(query_vector, top_k=limit * 2)
        all_records = l3_store.get_all()
        bm_id_scores = {}
        if all_records:
            texts = [r.get("content", "") or "" for r in all_records]
            bm25_indexer = BM25Indexer(k1=1.2, b=0.75)
            bm25_indexer.index(texts)
            bm_raw = bm25_indexer.search(query, top_k=limit * 2)
            for rank, bm in enumerate(bm_raw):
                rec = all_records[bm["doc_index"]]
                bm_id_scores[rec["id"]] = bm["bm25_score"]

        # Build RRF scores using rank position (not raw scores)
        vec_rank = {r["id"]: rank for rank, r in enumerate(vector_results)}
        bm_rank = {mid: rank for rank, bm in enumerate(bm_raw) for mid in [all_records[bm["doc_index"]]["id"]]}
        all_ids = set(vec_rank.keys()) | set(bm_rank.keys())
        rrf_scores = {}
        for id_ in all_ids:
            vr = vec_rank.get(id_, 9999)
            br = bm_rank.get(id_, 9999)
            vec_s = 1.0 / (RRF_K + vr) if vr < 9999 else 0.0
            bm_s = 1.0 / (RRF_K + br) if br < 9999 else 0.0
            rrf_scores[id_] = vec_s + bm_s

        sorted_ids = sorted(rrf_scores, key=rrf_scores.__getitem__, reverse=True)
        id_to_vec = {r["id"]: r for r in vector_results}
        id_to_bm_rec = {all_records[bm["doc_index"]]["id"]: all_records[bm["doc_index"]] for bm in bm_raw}
        results = []
        for id_ in sorted_ids[:limit]:
            vr = id_to_vec.get(id_, {})
            br = id_to_bm_rec.get(id_, {})
            content = vr.get("content") or br.get("content", "")
            results.append({
                "id": id_,
                "content": (content[:100] + "...") if len(content or "") > 100 else content,
                "score": round(rrf_scores[id_], 6),
                "vector_score": vr.get("score", 0.0),
                "bm25_score": bm_id_scores.get(id_, 0.0),
                "category_path": vr.get("category_path") or br.get("category_path", ""),
            })
        metrics.inc_search("hybrid")
    else:
        # vector mode
        query_vector = embedder.embed(query)
        filter_expr = None
        if category:
            safe_cat = category.replace("'", "\\'")
            filter_expr = f"category_path = '{safe_cat}'"
        raw = l3_store.search(query_vector, top_k=limit, filter_expr=filter_expr)
        results = [
            {
                "id": r["id"],
                "content": (r["content"][:100] + "...") if len(r["content"] or "") > 100 else r.get("content", ""),
                "score": r["score"],
                "category_path": r.get("category_path", ""),
            }
            for r in raw
        ]
        metrics.inc_search("vector")

    result = {
        "success": True,
        "mode": mode,
        "query": query,
        "count": len(results),
        "results": results,
    }

    if not as_json:
        if results:
            lines = [f"Found {len(results)} memories (mode={mode}):\n"]
            for r in results:
                lines.append(f"  [{r['id']}] score={r['score']:.4f}")
                lines.append(f"    {r['content'][:80]}")
                lines.append("")
            result["message"] = "\n".join(lines)
        else:
            result["message"] = f"No memories matching '{query}'"

    _print_result(result, as_json)


async def cmd_list(
    category: Optional[str],
    limit: int,
    base_dir: str,
    as_json: bool,
) -> None:
    """处理 list 命令"""
    store = L4FilesStore(base_dir=base_dir)

    mem_ids = store.list()
    all_memories = []
    for mid in mem_ids:
        mem = await store.load_existing(mid)
        if mem:
            all_memories.append({"id": mid, **mem})

    if category:
        all_memories = [m for m in all_memories if m.get("meta", {}).get("category_path") == category]

    all_memories = all_memories[:limit]
    mem_ids = [m["id"] for m in all_memories]

    result = {
        "success": True,
        "count": len(mem_ids),
        "memories": [
            {
                "id": m["id"],
                "preview": (m["content"][:60] + "...") if len(m["content"] or "") > 60 else m["content"],
                "category": m.get("meta", {}).get("category_path"),
                "importance": m.get("meta", {}).get("importance"),
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
    as_json: bool,
) -> None:
    """处理 show 命令"""
    store = L4FilesStore(base_dir=base_dir)

    mem = await store.load_existing(mem_id)
    if not mem:
        result = {"success": False, "message": f"Memory {mem_id} not found"}
        _print_result(result, as_json)
        return

    result = {
        "success": True,
        "id": mem_id,
        "content": mem.get("content", ""),
        "meta": mem.get("meta", {}),
        "message": f"[{mem_id}]\n  {mem.get('content', '')}",
    }

    _print_result(result, as_json)


async def cmd_delete(
    mem_id: str,
    base_dir: str,
    as_json: bool,
) -> None:
    """处理 delete 命令"""
    from .manager import MemoryManager

    db_path = _qdrant_path(base_dir)
    mm = MemoryManager(base_dir=base_dir, db_path=db_path)

    success = await mm.delete(mem_id)
    if success:
        metrics.inc_delete()

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
    as_json: bool,
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
            result["message"] = (
                f"Used categories ({len(categories)}):\n  " + "\n  ".join(categories)
                if categories else "No categories used yet"
            )
        _print_result(result, as_json)
        return

    result = {"success": True, "message": "Use --list or --show-all"}
    _print_result(result, as_json)


async def cmd_stats(
    base_dir: str,
    as_json: bool,
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


# === doctor ===

# 必装依赖（缺失会报错）
_DOCTOR_REQUIRED = [
    ("httpx", "HTTP 客户端（NewAPI / Embedder 调用）"),
    ("aiofiles", "异步文件 IO"),
    ("pydantic", "数据校验"),
    ("jieba", "中文分词（BM25 + Reranker）"),
    ("numpy", "梦境信号分解依赖"),
    ("ulid", "记忆 ID 生成（依赖 python-ulid）"),
]

# 可选依赖（缺失会警告但不影响 CLI）
_DOCTOR_OPTIONAL = [
    ("qdrant_client", "L3 向量存储（Qdrant Edge）", "qdrant"),
    ("fastembed", "本地 Embedding 推理（fastembed 路由）", "embed"),
    ("sentence_transformers", "本地 Embedding 推理（sentence-transformers 路由）", "embed"),
    ("fastapi", "Web API 服务器", "web"),
    ("uvicorn", "Web API 服务器运行时", "web"),
    ("jinja2", "Web 模板引擎", "web"),
    ("watchdog", "文件监听（MemoryWatcher）", "web"),
    ("rapidfuzz", "模糊搜索（fuzzy_search.py）", "web"),
]


def _check_import(module_name: str) -> tuple[bool, str]:
    """检测单个模块是否可导入。

    Returns:
        (ok, version_or_error)
    """
    try:
        mod = __import__(module_name)
        ver = getattr(mod, "__version__", None) or getattr(mod, "VERSION", None)
        return True, str(ver) if ver else "unknown"
    except ImportError as e:
        return False, str(e)
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


def _check_path_writable(path: Path) -> tuple[bool, str]:
    """检测路径是否可写（不存在则尝试创建）。"""
    try:
        path.mkdir(parents=True, exist_ok=True)
        test_file = path / ".agentmemory_doctor.tmp"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink()
        return True, "writable"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


async def cmd_doctor(strict: bool, base_dir: str, as_json: bool) -> None:
    """处理 doctor 命令 — 环境诊断。

    检查项：
      1. Python 版本（>= 3.10）
      2. 必装依赖（缺失会报 fail）
      3. 可选依赖（缺失会报 warn，标记可用特性）
      4. 环境变量（LLM_BASE_URL / LLM_API_KEY / EMBEDDING_API_KEY 等）
      5. 路径可写性（base_dir / data 目录）
      6. Embedder 状态（HashEmbedder fallback 是否正常）
      7. 关键模块导入（agent_memory 主入口）
    """
    import sys
    import shutil
    from . import __version__ as am_version

    checks: list[dict] = []

    def _add(status: str, name: str, detail: str, **extra) -> None:
        checks.append({"status": status, "name": name, "detail": detail, **extra})

    # 1. Python 版本
    py_ver = sys.version_info
    py_str = f"{py_ver.major}.{py_ver.minor}.{py_ver.micro}"
    if (py_ver.major, py_ver.minor) >= (3, 10):
        _add("ok", "python", py_str)
    else:
        _add("fail", "python", f"{py_str} (< 3.10 不支持)")

    # 2. 必装依赖
    for mod_name, desc in _DOCTOR_REQUIRED:
        # ulid 在 import 时可能是 ulid 或 python-ulid，但导入名是 ulid
        import_name = "ulid" if mod_name == "ulid" else mod_name
        ok, ver = _check_import(import_name)
        if ok:
            _add("ok", f"dep:{mod_name}", f"{ver} — {desc}")
        else:
            _add("fail", f"dep:{mod_name}", f"missing — {desc} ({ver})")

    # 3. 可选依赖
    for mod_name, desc, _ in _DOCTOR_OPTIONAL:
        ok, ver = _check_import(mod_name)
        if ok:
            _add("ok", f"opt:{mod_name}", f"{ver} — {desc}")
        else:
            _add("warn", f"opt:{mod_name}", f"missing — {desc}")

    # 4. 环境变量
    env_checks = {
        "LLM_BASE_URL": "LLM 服务地址（NewAPI 接入）",
        "LLM_API_KEY": "LLM 服务密钥",
        "EMBEDDING_API_KEY": "云端 Embedding 密钥",
        "EMBEDDING_API_URL": "云端 Embedding 地址",
        "LOCAL_EMBED_ROUTES": "本地 Embedding 多 route 链 JSON",
        "AGENTMEMORY_BASE_DIR": "CLI/库默认存储目录覆盖",
    }
    for env_name, desc in env_checks.items():
        val = os.environ.get(env_name)
        if val:
            # 隐藏 API key 的中间部分
            if "KEY" in env_name and len(val) > 8:
                masked = val[:4] + "***" + val[-4:]
            else:
                masked = val
            _add("ok", f"env:{env_name}", f"set — {desc} = {masked}")
        else:
            _add("warn", f"env:{env_name}", f"unset — {desc}")

    # 5. 路径可写性
    paths_to_check = {
        "base_dir": Path(base_dir),
        "data_dir": Path("data"),
        "cwd": Path("."),
    }
    for name, p in paths_to_check.items():
        ok, detail = _check_path_writable(p)
        status = "ok" if ok else "fail"
        _add(status, f"path:{name}", f"{p.resolve()} — {detail}")

    # 6. Embedder fallback 状态
    try:
        from .embedder import get_embedder
        embedder = get_embedder()
        embedder_name = type(embedder).__name__
        # HashEmbedder 总是 384 维；FastEmbed 是 512；其他按实际
        if hasattr(embedder, "dim"):
            dim = embedder.dim
        elif hasattr(embedder, "dimension"):
            dim = embedder.dimension
        else:
            # 尝试 embed 一段文字
            try:
                sample = embedder.embed_sync("agentmemory doctor test")
                dim = len(sample) if sample else 0
            except Exception:  # noqa: BLE001
                dim = -1
        if embedder_name == "HashEmbedder" and not os.environ.get("EMBEDDING_API_KEY"):
            _add("warn", "embedder", f"{embedder_name} (dim={dim}) — fallback 模式，无 API key")
        else:
            _add("ok", "embedder", f"{embedder_name} (dim={dim})")
    except Exception as e:  # noqa: BLE001
        _add("fail", "embedder", f"{type(e).__name__}: {e}")

    # 7. 主入口模块
    try:
        from . import MemoryManager, L4FilesStore, SearchPipeline, DreamEngine
        _add("ok", "module:agent_memory", f"v{am_version} — 核心类可导入")
    except ImportError as e:
        _add("fail", "module:agent_memory", f"导入失败: {e}")

    # 汇总
    fail_count = sum(1 for c in checks if c["status"] == "fail")
    warn_count = sum(1 for c in checks if c["status"] == "warn")
    ok_count = sum(1 for c in checks if c["status"] == "ok")

    if strict:
        overall = "ok" if fail_count == 0 and warn_count == 0 else "fail"
    else:
        overall = "ok" if fail_count == 0 else "fail"

    result = {
        "success": overall == "ok",
        "status": overall,
        "version": am_version,
        "python": py_str,
        "summary": {
            "ok": ok_count,
            "warn": warn_count,
            "fail": fail_count,
        },
        "checks": checks,
    }

    if not as_json:
        # 人可读输出
        lines = [f"AgentMemory Doctor v{am_version} (Python {py_str})", ""]
        status_emoji = {"ok": "✓", "warn": "⚠", "fail": "✗"}
        for c in checks:
            emoji = status_emoji.get(c["status"], "?")
            lines.append(f"  {emoji} [{c['status'].upper():4s}] {c['name']}: {c['detail']}")
        lines.append("")
        lines.append(
            f"Summary: {ok_count} ok, {warn_count} warn, {fail_count} fail"
        )
        if strict and warn_count > 0 and fail_count == 0:
            lines.append("(strict mode: warn treated as fail)")
        result["message"] = "\n".join(lines)

    _print_result(result, as_json)


def cmd_sign(dir_path: str, key: str, as_json: bool) -> None:
    """处理 sign 命令"""
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
    """处理 verify 命令"""
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


async def cmd_reembed(
    embedder_type: str,
    base_dir: str,
    as_json: bool,
) -> None:
    """处理 reembed 命令 — 重新向量化所有记忆"""
    store = L4FilesStore(base_dir=base_dir)
    embedder = get_embedder(backend=embedder_type)
    db_path = _qdrant_path(base_dir)
    l3_store = _get_l3_store(db_path)

    all_ids = store.list()
    if not all_ids:
        result = {"success": True, "message": "No memories to reembed", "count": 0}
        _print_result(result, as_json)
        return

    updated = 0
    errors = 0
    for mem_id in all_ids:
        try:
            _efn = embedder.embed_sync if hasattr(embedder, "embed_sync") else embedder.embed
            record = await store.load_existing(mem_id)
            if not record:
                continue
            content = record.get("content", "")
            meta = record.get("meta", {})
            vec = _efn(content)
            l3_store.upsert(
                id=mem_id, content=content, vector=vec, metadata=meta,
                importance=meta.get("importance", 0.5),
                category_path=meta.get("category_path", "general"),
                created_at=meta.get("created_at"),
            )
            updated += 1
            if not as_json:
                print(f"  [{updated}/{len(all_ids)}] reembedded: {mem_id}")
        except Exception as e:
            errors += 1
            if not as_json:
                print(f"  [ERROR] {mem_id}: {e}")

    result = {
        "success": True,
        "count": updated,
        "errors": errors,
        "embedder": embedder_type,
        "message": f"OK: reembedded {updated} memories ({errors} errors) with {embedder_type}",
    }
    _print_result(result, as_json)


def cmd_serve(port: int, host: str, base_dir: str, as_json: bool) -> None:
    """处理 serve 命令 — 启动 FastAPI Web 服务器"""
    try:
        from .web import create_app
        import uvicorn
    except ImportError as e:
        result = {
            "success": False,
            "message": f"FastAPI not installed: {e}. Run: pip install agentmemory[web]",
        }
        _print_result(result, as_json)
        return

    db_path = _qdrant_path(base_dir)
    app = create_app(base_dir=base_dir, db_path=db_path)

    if as_json:
        print(json.dumps({"success": True, "message": f"Starting server on {host}:{port}"}))

    uvicorn.run(app, host=host, port=port, log_level="info")


def main() -> int:
    """CLI 主入口"""
    parser = _build_parser()
    args = parser.parse_args()

    kwargs = vars(args).copy()
    command = kwargs.pop("command")
    as_json = kwargs.pop("json", False)
    base_dir = kwargs.pop("base_dir", DEFAULT_BASE_DIR)
    namespace = kwargs.pop("namespace", None)
    
    # Apply namespace isolation: base_dir → base_dir/{namespace}/
    # Security: validate namespace cannot escape base_dir via path traversal
    if namespace:
        import re
        # Filter: only allow word chars (alphanumeric+_), Chinese chars, /, -, space
        ns_filtered = re.sub(r'[^\w\-一-\u9fff\s/]', '', namespace)
        ns_clean = ns_filtered.strip('/\\')
        if not ns_clean or ns_clean.startswith('.'):
            raise ValueError(f"Invalid namespace: {namespace!r}")
        ns_path = Path(base_dir) / ns_clean
        # Verify resolved path stays within base_dir (prevents /etc/passwd, ../../../etc attacks)
        try:
            ns_path = ns_path.resolve()
            base_dir_resolved = Path(base_dir).resolve()
            # Must be under base_dir (is_relative_to available Python 3.9+)
            if not str(ns_path).startswith(str(base_dir_resolved)):
                raise ValueError(f"Namespace escapes base_dir: {namespace!r}")
        except Exception:
            raise ValueError(f"Invalid namespace path: {namespace!r}")
        base_dir = str(ns_path)

    if command == "sign":
        cmd_sign(kwargs["dir"], kwargs["key"], as_json)
        return 0

    if command == "verify":
        cmd_verify(kwargs["dir"], kwargs["key"], as_json)
        return 0

    if command == "reembed":
        return asyncio.run(cmd_reembed(
            embedder_type=kwargs["embedder"],
            base_dir=base_dir,
            as_json=as_json,
        )) or 0

    if command == "mcp":
        from src.adapters.mcp_server import main as mcp_main
        mcp_main()
        return 0

    if command == "bg":
        from src.adapters.transparent_background import main as bg_main
        bg_main(
            agent_id=kwargs.get("agent_id", "default"),
            base_dir=base_dir,
            importance=kwargs.get("importance", 0.6),
            heartbeat_minutes=kwargs.get("interval", 5),
            once=kwargs.get("once", False),
        )
        return 0

    if command == "serve":
        cmd_serve(
            port=kwargs["port"],
            host=kwargs["host"],
            base_dir=base_dir,
            as_json=as_json,
        )
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
            mode=kwargs.get("mode", "vector"),
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

    if command == "doctor":
        return asyncio.run(cmd_doctor(
            strict=kwargs.get("strict", False),
            base_dir=base_dir,
            as_json=as_json,
        )) or 0

    if command == "dream":
        from .sqlite_store import SQLiteStore
        from .dream_engine import DreamEngine
        store = SQLiteStore(kwargs.get("db_path", "data/agentmemory.db"))
        engine = DreamEngine(sqlite_store=store, namespace=kwargs.get("namespace", "default"))
        once = kwargs.get("once", True)
        interval = kwargs.get("interval", 300)
        dry_run = kwargs.get("dry_run", False)

        import time
        while True:
            cycle = engine.dream_cycle(
                phase=kwargs.get("phase", "deep"),
                dry_run=dry_run,
                candidate_names=[
                    "信号", "记忆", "关联", "模式", "结构", "动态",
                    "语义", "概念", "关系", "序列", "上下文", "意图",
                ],
            )
            if as_json:
                print(json.dumps(cycle, indent=2, ensure_ascii=False))
            else:
                total = cycle.get("total_ms", 0)
                artifacts = len(cycle.get("artifacts", []))
                cons = cycle.get("phases", {}).get("consolidation", {})
                data = cycle.get("data", {})
                print(f"梦境循环完成: {total:.0f}ms | {data.get('memories',0)}条记忆 {data.get('tags',0)}个标签")
                print(f"  产物: {artifacts}个 | 写入: {cons.get('written',0)} 草稿: {cons.get('drafted',0)} 丢弃: {cons.get('rejected',0)}")
            if once:
                break
            print(f"下次梦境: {interval}s后...")
            time.sleep(interval)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
