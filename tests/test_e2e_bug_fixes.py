"""
2026-07-15 14:42 调 7 - 真 e2e 验证发现的 Bug 修复回归测试

本文件锁住 7 个真 bug 的修复,确保不会再回归。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


# ========== Bug #1: argparse 子命令不接受父级选项 ==========

def test_dream_cli_subcommand_accepts_db_option():
    """Bug #1: --db 在子命令中必须可用"""
    from agent_memory.dream_cli import main
    import argparse

    # 模拟 list-provenance --db xxx
    sys.argv = ["dream_cli", "list-provenance", "--db", "data/x.db"]
    try:
        main()
    except SystemExit as e:
        # 如果 exit code != 0 也是错误(但 type-check 应该过)
        assert e.code == 0 or e.code is None, f"exit code: {e.code}"


# ========== Bug #2: MemoryManager.__init__ 真实参数 ==========

def test_memory_manager_real_init_params():
    """Bug #2: MemoryManager 真实接受 base_dir + db_path,不是 store_path"""
    from agent_memory import MemoryManager
    import inspect
    sig = inspect.signature(MemoryManager.__init__)
    assert "base_dir" in sig.parameters
    assert "db_path" in sig.parameters
    assert "store_path" not in sig.parameters


# ========== Bug #3: _store_path 在 __init__ 中显式设置 ==========

def test_memory_manager_init_sets_store_path():
    """Bug #3: mm._store_path 必须在 __init__ 设置,不是 getattr fallback"""
    from agent_memory import MemoryManager
    mm = MemoryManager(base_dir="data/test_x", db_path="data/test_x/_l3")
    assert hasattr(mm, "_store_path")
    assert mm._store_path.endswith(".sqlite") or mm._store_path.endswith(".db")


# ========== Bug #4: SQLiteStore 应接受 db_path 关键字 ==========

def test_sqlite_store_accepts_db_path():
    """Bug #4: SQLiteStore(db_path=...) 工作正常"""
    from agent_memory.sqlite_store import SQLiteStore
    import tempfile, gc
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "test.db")
        store = SQLiteStore(db_path=db)
        # 应能 query
        cur = store._get_conn().execute("SELECT 1")
        assert cur.fetchone()[0] == 1
        # 手动释放连接避免 Windows 文件锁
        try:
            store._local.conn.close()
        except Exception:
            pass
        del store
        gc.collect()


# ========== Bug #5: Windows GBK 编码安全 ==========

def test_embedder_registry_no_emoji_in_table():
    """Bug #5: Windows GBK 不能编码 ⭐,应使用 ASCII *"""
    from agent_memory.embedder_registry import format_model_table
    table = format_model_table()
    assert "⭐" not in table
    assert "*推荐" in table or "推荐" in table


# ========== Bug #6: DreamEngine 参数名 sqlite_store ==========

def test_dream_engine_param_name_sqlite_store():
    """Bug #6: DreamEngine 真实参数是 sqlite_store 不是 store"""
    from agent_memory.dream_engine import DreamEngine
    import inspect
    sig = inspect.signature(DreamEngine.__init__)
    assert "sqlite_store" in sig.parameters


def test_dream_scheduler_passes_correct_param():
    """Bug #6 fix: DreamScheduler 用 sqlite_store= 调用 DreamEngine"""
    from agent_memory import dream_scheduler
    import inspect
    src = inspect.getsource(dream_scheduler)
    # 不应该再用 store= 调用(应该是 sqlite_store=)
    assert "DreamEngine(sqlite_store=" in src


# ========== Bug #7: dream_cli 用真文件路径避免 l3 目录冲突 ==========

def test_dream_cli_make_manager_creates_distinct_paths():
    """Bug #7: _make_manager 应让 l3 和 sqlite 用不同路径"""
    from agent_memory.dream_cli import _make_manager
    import tempfile, gc
    with tempfile.TemporaryDirectory() as tmp:
        # 传入目录
        mm = _make_manager(tmp)
        # sqlite 文件路径不应等于 l3 db_path
        assert mm._store_path != mm.db_path
        # 释放资源避免 Windows 文件锁
        try:
            if hasattr(mm, 'l4'):
                pass
            if hasattr(mm, '_dream_scheduler'):
                mm._dream_scheduler = None
            if hasattr(mm, '_provenance_tracker'):
                mm._provenance_tracker = None
        except Exception:
            pass
        del mm
        gc.collect()


# ========== 综合:CLI 真实 e2e ==========

def test_dream_cli_record_then_list_e2e():
    """端到端: record → list-provenance → explain 应全通"""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "test_e2e.db")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent / "src")
        env["AGENTMEMORY_EMBED_MODEL"] = "BAAI/bge-small-zh-v1.5"  # 不用真实下载

        # record
        r1 = subprocess.run(
            [sys.executable, "-m", "agent_memory.dream_cli",
             "record", "test_e2e_001", "--type", "emergent_node",
             "--phase", "rem", "--inputs", "A,B", "--confidence", "0.9",
             "--db", db],
            capture_output=True, text=True, env=env, cwd=str(Path(__file__).resolve().parent.parent),
        )
        assert "已记录" in r1.stdout, f"record failed: {r1.stdout} | {r1.stderr}"

        # list-provenance
        r2 = subprocess.run(
            [sys.executable, "-m", "agent_memory.dream_cli",
             "list-provenance", "--db", db],
            capture_output=True, text=True, env=env, cwd=str(Path(__file__).resolve().parent.parent),
        )
        assert "test_e2e_001" in r2.stdout, f"list failed: {r2.stdout} | {r2.stderr}"

        # explain
        r3 = subprocess.run(
            [sys.executable, "-m", "agent_memory.dream_cli",
             "explain", "test_e2e_001", "--db", db],
            capture_output=True, text=True, env=env, cwd=str(Path(__file__).resolve().parent.parent),
        )
        assert "test_e2e_001" in r3.stdout, f"explain failed: {r3.stdout} | {r3.stderr}"