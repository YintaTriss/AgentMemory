"""
agentmemory CLI - 技能入口
将 MemoryHermes 的所有方法暴露为命令行接口，供 OpenClaw skill 系统调用。
"""

import argparse
import asyncio
import json
import sys
import traceback

import os
sys.path.insert(0, os.path.dirname(__file__))

from memory_manager import MemoryHermes


def parse_args():
    parser = argparse.ArgumentParser(
        prog="agentmemory",
        description="agentmemory 四层闭环记忆系统 CLI"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # store <text>
    store = sub.add_parser("store", help="存储记忆（自动 LLM 事实提取）")
    store.add_argument("text", help="要记忆的内容")
    store.add_argument("--importance", type=float, default=0.5)
    store.add_argument("--metadata", type=str, default="{}")

    # query <text>
    q = sub.add_parser("query", help="查询记忆（混合检索）")
    q.add_argument("text", help="查询文本")
    q.add_argument("--limit", type=int, default=5)
    q.add_argument("--tags", type=str, default="", help="逗号分隔标签")

    # prefetch <text>
    p = sub.add_parser("prefetch", help="预取相关记忆（后台异步）")
    p.add_argument("text", help="查询文本")

    # forget <memory_id>
    f = sub.add_parser("forget", help="遗忘记忆")
    f.add_argument("memory_id", help="记忆 ID")
    f.add_argument("--permanent", action="store_true", help="永久删除")

    # sync-turn <user_msg> <assistant_msg>
    sync = sub.add_parser("sync-turn", help="对话轮次同步（LLM 事实提取）")
    sync.add_argument("user_msg", help="用户消息")
    sync.add_argument("assistant_msg", help="助手消息")

    # session-end
    se = sub.add_parser("session-end", help="会话结束总结")
    se.add_argument("--summary", default=None, help="会话总结")

    # decay-check
    sub.add_parser("decay-check", help="遗忘引擎检查")

    # stats
    sub.add_parser("stats", help="记忆系统统计")

    # layer-status
    sub.add_parser("layer-status", help="查看各层状态")

    # execute <action> <params_json>
    ex = sub.add_parser("execute", help="通用动作接口（兼容 AgentSymphony）")
    ex.add_argument("action", help="动作名")
    ex.add_argument("params", nargs="?", default="{}", help="参数字典 JSON")

    # serve [--adapter] [--port] - 启动框架适配器服务
    serve = sub.add_parser("serve", help="启动框架适配器服务")
    serve.add_argument(
        "--adapter",
        choices=["claude_code", "openclaw"],
        default="claude_code",
        help="选择适配器类型 (default: claude_code)"
    )
    serve.add_argument(
        "--port",
        type=str,
        default="stdio",
        help="传输类型或端口: stdio (MCP) 或端口号如 8765 (HTTP)"
    )
    serve.add_argument(
        "--host",
        default="localhost",
        help="HTTP server 监听地址 (default: localhost)"
    )

    return parser.parse_args()


async def cmd_store(args):
    mh = MemoryHermes()
    metadata = {}
    try:
        metadata = json.loads(args.metadata)
    except json.JSONDecodeError:
        pass
    memory_id = await mh.store(args.text, metadata, args.importance)
    print(json.dumps({"memory_id": memory_id, "content": args.text}, ensure_ascii=False, indent=2))


async def cmd_query(args):
    mh = MemoryHermes()
    filters = None
    if args.tags:
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        filters = {"tags": tags}
    results = await mh.query(args.text, args.limit, filters)
    out = []
    for r in results:
        out.append({
            "id": r.get("id"),
            "content": r.get("content"),
            "score": round(r.get("score", 0), 4),
            "importance": r.get("importance"),
            "fact_type": r.get("fact_type"),
            "tags": r.get("tags", []),
        })
    print(json.dumps(out, ensure_ascii=False, indent=2))


async def cmd_prefetch(args):
    mh = MemoryHermes()
    await mh.prefetch(args.text)
    result = mh.get_prefetched(args.text)
    print(json.dumps(result or [], ensure_ascii=False, indent=2))


async def cmd_forget(args):
    mh = MemoryHermes()
    result = await mh.forget(args.memory_id, permanent=args.permanent)
    print(json.dumps({"ok": result}, ensure_ascii=False, indent=2))


async def cmd_sync_turn(args):
    mh = MemoryHermes()
    results = await mh.sync_turn(args.user_msg, args.assistant_msg)
    print(f"提取了 {len(results)} 条事实")
    for r in results:
        print(f"  - [{r.get('fact_type')}] {r.get('content')}")


async def cmd_session_end(args):
    mh = MemoryHermes()
    results = await mh.on_session_end(args.summary)
    print(f"会话结束，生成了总结记忆")


async def cmd_decay_check(args):
    mh = MemoryHermes()
    result = await mh.run_decay_check()
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_stats(args):
    mh = MemoryHermes()
    result = mh.get_stats()
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_layer_status(args):
    mh = MemoryHermes()
    stats = mh.get_stats()
    status = {
        "L1_LCM_Compress": stats["layers"]["l1_compress"],
        "L2_Graph_Store": stats["layers"]["l2_graph"],
        "L3_Vector_Store": stats["layers"]["l3_vector"],
        "L4_File_Persist": stats["layers"]["l4_files"],
    }
    if "graph" in stats:
        status["L2_entities"] = stats["graph"]
    if "vector" in stats:
        status["L3_memory_count"] = stats["vector"]["total"]
    print(json.dumps(status, ensure_ascii=False, indent=2))


async def cmd_execute(args):
    mh = MemoryHermes()
    params = {}
    try:
        params = json.loads(args.params)
    except json.JSONDecodeError:
        pass
    result = await mh.execute(args.action, params)
    print(json.dumps(result, ensure_ascii=False, indent=2))


async def cmd_serve(args):
    """启动框架适配器服务"""
    from memory_manager import MemoryHermes
    from adapters.claude_code import ClaudeCodeAdapter
    from adapters.openclaw import OpenClawAdapter
    
    mh = MemoryHermes()
    
    if args.adapter == "claude_code":
        adapter = ClaudeCodeAdapter()
        adapter.bind(mh)
        
        if args.port == "stdio":
            # 启动 MCP stdio server
            print("Starting Claude Code MCP adapter in stdio mode...", file=sys.stderr)
            adapter.run_stdio()
        else:
            # 启动 HTTP server
            try:
                port = int(args.port)
            except ValueError:
                port = 8765
            print(f"Starting Claude Code MCP adapter in HTTP mode on {args.host}:{port}...", file=sys.stderr)
            adapter.run_http(host=args.host, port=port)
    
    elif args.adapter == "openclaw":
        adapter = OpenClawAdapter()
        adapter.bind(mh)
        
        if args.port == "stdio":
            print("OpenClaw adapter does not support stdio mode, starting HTTP...", file=sys.stderr)
            port = 8765
        else:
            try:
                port = int(args.port)
            except ValueError:
                port = 8765
        
        print(f"Starting OpenClaw HTTP adapter on {args.host}:{port}...", file=sys.stderr)
        adapter.run_http_server(host=args.host, port=port)


async def main_async():
    args = parse_args()
    try:
        if args.command == "store":
            await cmd_store(args)
        elif args.command == "query":
            await cmd_query(args)
        elif args.command == "prefetch":
            await cmd_prefetch(args)
        elif args.command == "forget":
            await cmd_forget(args)
        elif args.command == "sync-turn":
            await cmd_sync_turn(args)
        elif args.command == "session-end":
            await cmd_session_end(args)
        elif args.command == "decay-check":
            await cmd_decay_check(args)
        elif args.command == "stats":
            cmd_stats(args)
        elif args.command == "layer-status":
            cmd_layer_status(args)
        elif args.command == "execute":
            await cmd_execute(args)
        elif args.command == "serve":
            await cmd_serve(args)
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
