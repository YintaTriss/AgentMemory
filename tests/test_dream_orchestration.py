"""
2026-07-15: 梦境调度 + Temporal L1 + 可插拔 Embedding 测试

方向 7 + 扩展方向 3 + 方向 8
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


# ========== 方向 7: DreamScheduler ==========

from agent_memory.dream_scheduler import (  # noqa: E402
    DreamScheduler,
    ScheduleRule,
    DEFAULT_SCHEDULE,
)


def test_schedule_rule_every_hours_due():
    """every:6h 距上次 7 小时到期"""
    rule = ScheduleRule(phase="light", schedule="every:6h",
                        last_run_iso=(datetime.now() - timedelta(hours=7)).isoformat())
    assert rule.is_due() is True


def test_schedule_rule_every_hours_not_due():
    """every:6h 距上次 5 小时未到期"""
    rule = ScheduleRule(phase="light", schedule="every:6h",
                        last_run_iso=(datetime.now() - timedelta(hours=5)).isoformat())
    assert rule.is_due() is False


def test_schedule_rule_every_no_last_run_due():
    """首次运行到期"""
    rule = ScheduleRule(phase="light", schedule="every:6h", last_run_iso=None)
    assert rule.is_due() is True


def test_schedule_rule_daily_match_time():
    """daily:03:00 当前时间 03:00 到期"""
    now = datetime.now().replace(hour=3, minute=0, second=0, microsecond=0)
    rule = ScheduleRule(phase="deep", schedule="daily:03:00",
                        last_run_iso=None)
    assert rule.is_due(now=now) is True


def test_schedule_rule_daily_wrong_time():
    """daily:03:00 当前时间 05:00 未到期"""
    now = datetime.now().replace(hour=5, minute=0, second=0, microsecond=0)
    rule = ScheduleRule(phase="deep", schedule="daily:03:00",
                        last_run_iso=None)
    assert rule.is_due(now=now) is False


def test_schedule_rule_daily_already_ran_today():
    """daily:03:00 同一日已跑过"""
    now = datetime.now().replace(hour=3, minute=0, second=0, microsecond=0)
    rule = ScheduleRule(phase="deep", schedule="daily:03:00",
                        last_run_iso=now.isoformat())
    assert rule.is_due(now=now) is False


def test_schedule_rule_weekly_sunday_match():
    """weekly:sun:03:00 周日 03:00 到期"""
    # 找一个周日
    days_to_sunday = (6 - datetime.now().weekday()) % 7
    if days_to_sunday == 0:
        # 今天就是周日
        days_to_sunday = 7
    last_sunday = datetime.now() - timedelta(days=datetime.now().weekday() + 1)
    next_sunday = last_sunday + timedelta(days=7)
    now = next_sunday.replace(hour=3, minute=0, second=0, microsecond=0)
    rule = ScheduleRule(phase="rem", schedule="weekly:sun:03:00",
                        last_run_iso=None)
    assert rule.is_due(now=now) is True


def test_schedule_rule_weekly_wrong_day():
    """weekly:sun:03:00 周一未到期"""
    # 找一个周一
    days_since_monday = datetime.now().weekday()
    if days_since_monday == 0:
        days_since_monday = 7
    last_monday = datetime.now() - timedelta(days=days_since_monday)
    now = last_monday.replace(hour=3, minute=0, second=0, microsecond=0)
    rule = ScheduleRule(phase="rem", schedule="weekly:sun:03:00",
                        last_run_iso=None)
    assert rule.is_due(now=now) is False


def test_default_schedule_has_light_deep_rem():
    assert "light" in DEFAULT_SCHEDULE
    assert "deep" in DEFAULT_SCHEDULE
    assert "rem" in DEFAULT_SCHEDULE


def test_dream_scheduler_load_rules():
    """调度器从 store 加载规则"""
    store = MagicMock()
    store.kv_get = MagicMock(side_effect=lambda k: "2026-07-15T00:00:00" if "light" in k else None)
    sched = DreamScheduler(store=store, namespace="default")
    rules = sched._load_rules()
    assert "light" in rules
    assert rules["light"].last_run_iso == "2026-07-15T00:00:00"


def test_dream_scheduler_tick_no_trigger():
    """所有规则未到期时无触发"""
    store = MagicMock()
    now = datetime.now()
    store.kv_get = MagicMock(side_effect=lambda k: now.isoformat())  # 全部刚跑过
    sched = DreamScheduler(store=store, namespace="default")
    # mock _run_phase 避免真实执行
    with patch.object(sched, "_run_phase", return_value={"phase": "x", "decision": "ran"}):
        out = sched.tick()
    assert len(out["triggered"]) == 0
    assert len(out["skipped"]) == 3


def test_dream_scheduler_tick_with_callback():
    """tick 完成后调用 callback"""
    store = MagicMock()
    store.kv_get = MagicMock(return_value=None)  # 从未运行过,全部到期
    received = []
    sched = DreamScheduler(
        store=store, namespace="default",
        callback=lambda evt, out: received.append((evt, out)),
    )
    with patch.object(sched, "_run_phase", return_value={"phase": "x", "decision": "ran"}):
        out = sched.tick()
    assert len(received) == 1
    assert received[0][0] == "tick"


def test_dream_scheduler_saves_last_run():
    """触发后应保存 last_run 时间"""
    store = MagicMock()
    store.kv_get = MagicMock(return_value=None)
    store.kv_set = MagicMock()
    sched = DreamScheduler(store=store, namespace="default")
    with patch.object(sched, "_run_phase", return_value={"phase": "x", "decision": "ran"}):
        sched.tick()
    # 应至少调用了 3 次 kv_set(每个 phase 一次)
    assert store.kv_set.call_count >= 1


def test_dream_scheduler_explain_schedule():
    store = MagicMock()
    sched = DreamScheduler(store=store, namespace="myns")
    text = sched.explain_schedule()
    assert "myns" in text
    assert "light" in text
    assert "deep" in text
    assert "rem" in text


# ========== MemoryManager.get_dream_scheduler ==========

def test_memory_manager_get_dream_scheduler():
    from agent_memory import MemoryManager
    mm = MemoryManager.__new__(MemoryManager)
    mm._store = MagicMock()  # mock store, 避免 Windows 文件锁
    s = mm.get_dream_scheduler()
    assert isinstance(s, DreamScheduler)
    # 二次调用应返回同一实例(缓存)
    assert mm.get_dream_scheduler() is s


def test_memory_manager_get_dream_scheduler_custom_schedule():
    from agent_memory import MemoryManager
    mm = MemoryManager.__new__(MemoryManager)
    mm._store = MagicMock()
    custom = {"light": "every:1h", "deep": "daily:02:00", "rem": "weekly:sun:02:00"}
    s = mm.get_dream_scheduler(schedule=custom)
    assert s.schedule["light"] == "every:1h"


# ========== compress_for_context temporal 过滤 ==========

@pytest.mark.asyncio
async def test_compress_for_context_filters_invalidated():
    """默认 only_valid=True 应过滤 invalidated 记忆"""
    from agent_memory import MemoryManager
    with tempfile.TemporaryDirectory() as tmp:
        mm = MemoryManager.__new__(MemoryManager)
        mm._store_path = os.path.join(tmp, "test.db")
        # mock l4.load_existing
        mm.l4 = MagicMock()
        mm.l4.load_existing = AsyncMock(side_effect=[
            {"id": "a", "content": "valid fact", "meta": {"created_at": "2026-07-15"}},
            {"id": "b", "content": "invalidated", "meta": {
                "created_at": "2026-07-15", "invalidated_by": "01NEW"
            }},
            None,
        ])
        # mock l1.compress
        mm.l1 = MagicMock()
        mm.l1.compress = MagicMock(return_value="compressed text")
        result = await mm.compress_for_context(
            memory_ids=["a", "b", "c"],
            query="",
        )
        # l1.compress 只应收到 1 条(过滤了 invalidated)
        call_args = mm.l1.compress.call_args
        memories_arg = call_args[0][0]
        assert len(memories_arg) == 1
        assert memories_arg[0]["id"] == "a"


@pytest.mark.asyncio
async def test_compress_for_context_only_valid_false():
    """only_valid=False 应包含 invalidated"""
    from agent_memory import MemoryManager
    with tempfile.TemporaryDirectory() as tmp:
        mm = MemoryManager.__new__(MemoryManager)
        mm._store_path = os.path.join(tmp, "test.db")
        mm.l4 = MagicMock()
        mm.l4.load_existing = AsyncMock(side_effect=[
            {"id": "a", "content": "valid", "meta": {"created_at": "2026-07-15"}},
            {"id": "b", "content": "invalidated", "meta": {
                "created_at": "2026-07-15", "invalidated_by": "01NEW"
            }},
        ])
        mm.l1 = MagicMock()
        mm.l1.compress = MagicMock(return_value="x")
        await mm.compress_for_context(
            memory_ids=["a", "b"],
            query="",
            only_valid=False,
        )
        call_args = mm.l1.compress.call_args
        memories_arg = call_args[0][0]
        assert len(memories_arg) == 2


@pytest.mark.asyncio
async def test_compress_for_context_auto_detects_temporal():
    """query 含 '去年' 应自动应用 time_range"""
    from agent_memory import MemoryManager
    with tempfile.TemporaryDirectory() as tmp:
        mm = MemoryManager.__new__(MemoryManager)
        mm._store_path = os.path.join(tmp, "test.db")
        mm.l4 = MagicMock()
        mm.l4.load_existing = AsyncMock(side_effect=[
            {"id": "a", "content": "old", "meta": {"created_at": "2025-12-01"}},
            {"id": "b", "content": "recent", "meta": {"created_at": "2026-07-15"}},
        ])
        mm.l1 = MagicMock()
        mm.l1.compress = MagicMock(return_value="x")
        await mm.compress_for_context(
            memory_ids=["a", "b"],
            query="去年 12 月我做了什么",
        )
        call_args = mm.l1.compress.call_args
        memories_arg = call_args[0][0]
        ids = [m["id"] for m in memories_arg]
        # 去年 12 月范围只命中 2025-12-01,过滤掉 2026-07-15
        assert "a" in ids
        assert "b" not in ids


@pytest.mark.asyncio
async def test_compress_for_context_explicit_time_range():
    from agent_memory import MemoryManager
    with tempfile.TemporaryDirectory() as tmp:
        mm = MemoryManager.__new__(MemoryManager)
        mm._store_path = os.path.join(tmp, "test.db")
        mm.l4 = MagicMock()
        mm.l4.load_existing = AsyncMock(side_effect=[
            {"id": "a", "content": "march fact", "meta": {"created_at": "2026-03-15"}},
            {"id": "b", "content": "july fact", "meta": {"created_at": "2026-07-15"}},
        ])
        mm.l1 = MagicMock()
        mm.l1.compress = MagicMock(return_value="x")
        await mm.compress_for_context(
            memory_ids=["a", "b"],
            query="",
            time_range=("2026-03-01T00:00:00", "2026-04-01T00:00:00"),
            auto_detect_temporal=False,
        )
        call_args = mm.l1.compress.call_args
        memories_arg = call_args[0][0]
        ids = [m["id"] for m in memories_arg]
        assert "a" in ids
        assert "b" not in ids


# ========== 方向 8: Embedder Registry ==========

def test_list_models_includes_bge_m3():
    """bge-m3 应在列表里(中英双语原生)"""
    from agent_memory import list_models
    models = list_models()
    names = [m["name"] for m in models]
    assert "BAAI/bge-m3" in names


def test_list_models_includes_e5():
    """e5 多语言应支持"""
    from agent_memory import list_models
    models = list_models()
    names = [m["name"] for m in models]
    assert "intfloat/multilingual-e5-base" in names
    assert "intfloat/multilingual-e5-large" in names


def test_list_models_have_quality_info():
    """每个模型应有 lang + quality + size_mb"""
    from agent_memory import list_models
    models = list_models()
    for m in models:
        assert "lang" in m, f"{m['name']} 缺 lang"
        assert "quality" in m, f"{m['name']} 缺 quality"
        assert "size_mb" in m, f"{m['name']} 缺 size_mb"
        assert "dim" in m


def test_bge_m3_marked_recommended():
    """bge-m3 应被标记为推荐"""
    from agent_memory import list_models
    models = list_models()
    bge_m3 = next(m for m in models if m["name"] == "BAAI/bge-m3")
    assert bge_m3.get("recommended") is True


def test_get_recommended_model_returns_bge_m3():
    """默认推荐是 bge-m3"""
    from agent_memory import get_recommended_model
    rec = get_recommended_model()
    assert rec == "BAAI/bge-m3"


def test_get_model_from_env_default():
    """无环境变量时默认 bge-m3"""
    from agent_memory import get_model_from_env
    os.environ.pop("AGENTMEMORY_EMBED_MODEL", None)
    assert get_model_from_env() == "BAAI/bge-m3"


def test_get_model_from_env_custom(monkeypatch):
    """环境变量优先"""
    from agent_memory import get_model_from_env
    monkeypatch.setenv("AGENTMEMORY_EMBED_MODEL", "BAAI/bge-large-zh-v1.5")
    assert get_model_from_env() == "BAAI/bge-large-zh-v1.5"


def test_get_model_info_existing():
    from agent_memory.embedder_registry import get_model_info
    info = get_model_info("BAAI/bge-m3")
    assert info is not None
    assert info["dim"] == 1024
    assert info["lang"] == "zh+en"


def test_get_model_info_unknown():
    from agent_memory.embedder_registry import get_model_info
    info = get_model_info("nonexistent/model")
    assert info is None


def test_format_model_table_human_readable():
    from agent_memory.embedder_registry import format_model_table
    table = format_model_table()
    assert "BAAI/bge-m3" in table
    assert "维度" in table
    assert "推荐" in table


def test_create_embedder_default():
    """create_embedder 默认 bge-m3"""
    from agent_memory.embedder_registry import create_embedder
    from agent_memory.fastembed_embedder import FastEmbedEmbedder
    # 不实际加载模型 — 只验证构造参数
    with patch.object(FastEmbedEmbedder, "_ensure_model"):
        emb = create_embedder()
        assert emb._model_name == "BAAI/bge-m3"


def test_create_embedder_custom():
    """create_embedder 支持指定模型"""
    from agent_memory.embedder_registry import create_embedder
    from agent_memory.fastembed_embedder import FastEmbedEmbedder
    with patch.object(FastEmbedEmbedder, "_ensure_model"):
        emb = create_embedder("BAAI/bge-large-zh-v1.5")
        assert emb._model_name == "BAAI/bge-large-zh-v1.5"


def test_fastembed_query_prefix_bge():
    """BGE 模型 query 端加前缀"""
    from agent_memory.fastembed_embedder import FastEmbedEmbedder
    with patch.object(FastEmbedEmbedder, "_ensure_model"):
        emb = FastEmbedEmbedder(model_name="BAAI/bge-m3")
        assert "为这个句子" in emb._maybe_prefix_query("test", is_query=True)
        assert "为这个句子" not in emb._maybe_prefix_query("test", is_query=False)


def test_fastembed_query_prefix_e5():
    """E5 模型 query/document 端分别加前缀"""
    from agent_memory.fastembed_embedder import FastEmbedEmbedder
    with patch.object(FastEmbedEmbedder, "_ensure_model"):
        emb = FastEmbedEmbedder(model_name="intfloat/multilingual-e5-base")
        assert emb._maybe_prefix_query("test", is_query=True).startswith("query: ")
        assert emb._maybe_prefix_query("test", is_query=False).startswith("passage: ")


def test_fastembed_query_prefix_other_models():
    """其他模型不加前缀"""
    from agent_memory.fastembed_embedder import FastEmbedEmbedder
    with patch.object(FastEmbedEmbedder, "_ensure_model"):
        emb = FastEmbedEmbedder(model_name="sentence-transformers/all-MiniLM-L6-v2")
        assert emb._maybe_prefix_query("test", is_query=True) == "test"