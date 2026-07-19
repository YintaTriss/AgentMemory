"""
Dream CLI — 2026-07-15 方向 2 (扩展)

梦境子系统命令行工具,与现有 cli.py 并存。

子命令:
  dream auto          — 自动选择并执行梦境阶段
  dream explain       — 解释梦境产物的因果
  dream trace         — 追溯梦境产物因果链
  dream schedule      — 显示调度表
  dream list-provenance — 列出已记录的梦境产物
  dream record        — 手动记录梦境产物

用法(独立命令):
  python -m agent_memory.dream_cli auto
  python -m agent_memory.dream_cli explain emergent_001
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional


def _make_manager(db_path: str = "data/agentmemory.db"):
    """构造 MemoryManager

    db_path 可接受: 目录路径 或 文件路径
    - 如果传入是目录: base_dir = db_path, db_path 用 db_path/agentmemory.sqlite
    - 如果传入是文件(.db/.sqlite 后缀 且 父目录): base_dir = parent, db_path = 原值

    【Bug Fix 2026-07-15 调7】避免同名路径被 l3 创建为目录导致的 sqlite conflict。
    """
    from . import MemoryManager
    db_path = os.path.abspath(db_path)
    if os.path.isdir(db_path):
        # 传入是目录 -> base_dir=目录, sqlite = <目录>/agentmemory.sqlite
        base_dir = db_path
        sqlite_file = os.path.join(db_path, "agentmemory.sqlite")
    else:
        # 传入是文件路径 -> base_dir=父目录, sqlite = 原值
        sqlite_file = db_path
        base_dir = os.path.dirname(db_path) or "."
    if not os.path.exists(base_dir):
        os.makedirs(base_dir, exist_ok=True)
    # MemoryManager 内部会创建 l3 db_path 同名目录, 改为子目录
    l3_dir = os.path.join(base_dir, "_l3_qdrant")
    if not os.path.exists(l3_dir):
        os.makedirs(l3_dir, exist_ok=True)
    mm = MemoryManager(base_dir=base_dir, db_path=l3_dir)
    # 【Bug Fix 2026-07-15 调7】覆写 _store_path 为我们计算的 sqlite 文件
    mm._store_path = sqlite_file
    return mm


def cmd_auto(args) -> int:
    """dream auto [--force light|deep|rem|skip]"""
    mm = _make_manager(args.db)
    out = mm.auto_dream(force=args.force)
    decision = out["decision"]
    if args.json:
        print(json.dumps({
            "phase": decision.phase,
            "reason": decision.reason,
            "priority": decision.priority,
            "signals": decision.signals,
            "result_phase": (out.get("result") or {}).get("phase"),
        }, ensure_ascii=False, indent=2))
    else:
        print(f"梦境阶段: {decision.phase}")
        print(f"理由: {decision.reason}")
        print(f"优先级: {decision.priority}")
        print(f"\n信号:")
        for k, v in decision.signals.items():
            print(f"  {k} = {v}")
    return 0


def cmd_explain(args) -> int:
    """dream explain <artifact_id>"""
    mm = _make_manager(args.db)
    explanation = mm.explain_artifact(args.artifact_id)
    print(explanation)
    return 0


def cmd_trace(args) -> int:
    """dream trace <artifact_id> [--json]"""
    mm = _make_manager(args.db)
    chain = mm.trace_artifact_chain(args.artifact_id)
    if args.json:
        print(json.dumps(chain, ensure_ascii=False, indent=2))
    else:
        print(f"因果链 ({len(chain)} 跳):")
        for i, p in enumerate(chain):
            print(f"  {i+1}. [{p['phase']}] {p['artifact_id']} ({p['artifact_type']})")
            print(f"     方法: {p['method']}, 置信度: {p['confidence']:.2f}")
    return 0


def cmd_schedule(args) -> int:
    """dream schedule [--list] [--run-once]"""
    mm = _make_manager(args.db)
    scheduler = mm.get_dream_scheduler()
    print(scheduler.explain_schedule())
    if args.run_once:
        out = scheduler.tick()
        print(f"\n触发: {len(out['triggered'])} 个")
        for t in out["triggered"]:
            print(f"  - {t.get('phase')}: {t.get('decision')}")
        print(f"跳过: {len(out['skipped'])} 个")
        for s in out["skipped"]:
            print(f"  - {s['phase']}: {s['reason']}")
    return 0


def cmd_list_provenance(args) -> int:
    """dream list-provenance [--type emergent_node|association|implicit_tag]"""
    from .dream_provenance import DreamProvenanceTracker
    mm = _make_manager(args.db)
    tracker = mm._get_provenance_tracker()

    if args.type:
        items = tracker.list_by_type(args.type)
    else:
        # 列出全部
        tracker._ensure_loaded()
        items = list(tracker._cache.values())

    if args.json:
        print(json.dumps([p.to_dict() for p in items], ensure_ascii=False, indent=2))
    else:
        print(f"梦境产物 ({len(items)} 个):")
        for p in items:
            print(f"  - [{p.phase}/{p.artifact_type}] {p.artifact_id} (conf={p.confidence:.2f})")
    return 0


def cmd_record(args) -> int:
    """dream record <id> --type X --phase Y [--inputs ...]"""
    mm = _make_manager(args.db)
    inputs = args.inputs.split(",") if args.inputs else []
    result = mm.record_dream_provenance(
        artifact_id=args.id,
        artifact_type=args.type,
        phase=args.phase,
        inputs=inputs,
        method=args.method or "manual",
        confidence=args.confidence,
        explanation=args.explanation or "",
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"已记录梦境产物: {result['artifact_id']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="agent_memory.dream_cli",
        description="AgentMemory 梦境子系统 CLI",
    )
    parser.add_argument("--db", default="data/agentmemory.db",
                        help="SQLite 数据库路径")
    parser.add_argument("--json", action="store_true",
                        help="JSON 输出")

    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # auto
    # 【Bug Fix 2026-07-15】将 --db/--json 暴露到每个子命令
    # python -m agent_memory.dream_cli list-provenance --db xxx
    # argparse 子命令默认不接受父级选项
    def add_common(sp):
        sp.add_argument("--db", default=None,
                        help="SQLite 数据库路径(覆盖全局)")
        sp.add_argument("--json", action="store_true",
                        help="JSON 输出(覆盖全局)")

    p_auto = subparsers.add_parser("auto", help="自动选择并执行梦境阶段")
    p_auto.add_argument("--force", choices=["light", "deep", "rem", "skip"],
                        help="强制指定阶段")
    add_common(p_auto)
    p_auto.set_defaults(func=cmd_auto)

    # explain
    p_exp = subparsers.add_parser("explain", help="解释梦境产物因果")
    p_exp.add_argument("artifact_id", help="产物 ID")
    add_common(p_exp)
    p_exp.set_defaults(func=cmd_explain)

    # trace
    p_trace = subparsers.add_parser("trace", help="追溯因果链")
    p_trace.add_argument("artifact_id", help="产物 ID")
    add_common(p_trace)
    p_trace.set_defaults(func=cmd_trace)

    # schedule
    p_sched = subparsers.add_parser("schedule", help="查看/触发调度")
    p_sched.add_argument("--run-once", action="store_true",
                         help="触发一次 tick 检查")
    add_common(p_sched)
    p_sched.set_defaults(func=cmd_schedule)

    # list-provenance
    p_list = subparsers.add_parser("list-provenance", help="列出梦境产物")
    p_list.add_argument("--type", choices=["emergent_node", "association",
                                            "implicit_tag", "narrative"],
                        help="按类型过滤")
    add_common(p_list)
    p_list.set_defaults(func=cmd_list_provenance)

    # record
    p_rec = subparsers.add_parser("record", help="手动记录梦境产物")
    p_rec.add_argument("id", help="产物 ID")
    p_rec.add_argument("--type", required=True,
                       choices=["emergent_node", "association", "implicit_tag", "narrative"])
    p_rec.add_argument("--phase", required=True,
                       choices=["light", "deep", "rem"])
    p_rec.add_argument("--inputs", help="输入 ID 列表(逗号分隔)")
    p_rec.add_argument("--method", help="产生方法")
    p_rec.add_argument("--confidence", type=float, default=1.0)
    p_rec.add_argument("--explanation", help="解释文本")
    add_common(p_rec)
    p_rec.set_defaults(func=cmd_record)

    args = parser.parse_args()
    # 子命令未传 --db/--json 时 fallback 到全局值
    if getattr(args, "db", None) is None:
        args.db = parser.get_default("db")
    args.json = getattr(args, "json", False) or parser.get_default("json")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())