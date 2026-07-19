"""
2026-07-15: Temporal 召回 (方向 2) 测试

- TemporalIntentDetector 单元测试
- filter_by_time_range / filter_only_valid 单元测试
- MemoryManager.search() 集成测试(mock L4)
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agent_memory.temporal import (  # noqa: E402
    TemporalIntentDetector,
    filter_by_time_range,
    filter_only_valid,
)


def _mem(mid, content, created_at="2026-07-15T10:00:00",
         invalidated_by=None):
    return {
        "id": mid,
        "content": content,
        "meta": {
            "created_at": created_at,
            "invalidated_by": invalidated_by,
        },
    }


# ---------- TemporalIntentDetector ----------

def test_detect_today_chinese():
    det = TemporalIntentDetector(now=datetime(2026, 7, 15, 14, 30))
    r = det.detect("今天我做了什么?")
    assert r["intent"] == "today"
    assert r["time_range"] is not None
    start, end = r["time_range"]
    assert start.startswith("2026-07-15T00:00:00")


def test_detect_yesterday():
    det = TemporalIntentDetector(now=datetime(2026, 7, 15, 14, 30))
    r = det.detect("昨天我做了什么?")
    assert r["intent"] == "yesterday"
    start, end = r["time_range"]
    assert "2026-07-14" in start
    assert "2026-07-15" in end


def test_detect_last_week():
    det = TemporalIntentDetector(now=datetime(2026, 7, 15, 14, 30))
    r = det.detect("上周发生了什么?")
    assert r["intent"] == "last_week"
    assert r["time_range"] is not None


def test_detect_this_week():
    det = TemporalIntentDetector(now=datetime(2026, 7, 15, 14, 30))  # 周三
    r = det.detect("本周的项目")
    assert r["intent"] == "this_week"


def test_detect_last_month():
    det = TemporalIntentDetector(now=datetime(2026, 7, 15))
    r = det.detect("上个月我做了什么?")
    assert r["intent"] == "last_month"
    start, end = r["time_range"]
    assert "2026-06-01" in start
    assert "2026-07-01" in end


def test_detect_this_month():
    det = TemporalIntentDetector(now=datetime(2026, 7, 15))
    r = det.detect("本月的进展")
    assert r["intent"] == "this_month"


def test_detect_last_year():
    det = TemporalIntentDetector(now=datetime(2026, 7, 15))
    r = det.detect("去年 12 月的决定")
    assert r["intent"] == "last_year"
    start, end = r["time_range"]
    assert "2025-01-01" in start
    assert "2026-01-01" in end


def test_detect_recent():
    det = TemporalIntentDetector(now=datetime(2026, 7, 15))
    r = det.detect("最近的项目进展")
    assert r["intent"] == "recent"


def test_detect_specific_month_arabic():
    det = TemporalIntentDetector(now=datetime(2026, 7, 15))
    r = det.detect("5 月份我做了什么?")
    assert r["intent"] == "month_5"
    start, end = r["time_range"]
    assert "2026-05-01" in start
    assert "2026-06-01" in end


def test_detect_specific_month_chinese():
    det = TemporalIntentDetector(now=datetime(2026, 7, 15))
    r = det.detect("三月份的项目")
    assert r["intent"] == "month_3"
    start, end = r["time_range"]
    assert "2026-03-01" in start


def test_detect_days_ago():
    det = TemporalIntentDetector(now=datetime(2026, 7, 15, 14, 30))
    r = det.detect("3 天前我说了什么")
    assert r["intent"] == "days_ago_3"
    assert r["time_range"] is not None


def test_detect_months_ago():
    det = TemporalIntentDetector(now=datetime(2026, 7, 15))
    r = det.detect("2 个月前")
    assert r["intent"] == "months_ago_2"


def test_detect_no_temporal_intent():
    det = TemporalIntentDetector(now=datetime(2026, 7, 15))
    r = det.detect("Postgres 和 SQLite 哪个好")
    assert r["intent"] is None
    assert r["time_range"] is None
    assert r["confidence"] == 0.0


def test_detect_english_last_week():
    det = TemporalIntentDetector(now=datetime(2026, 7, 15))
    r = det.detect("What did I do last week?")
    assert r["intent"] == "last_week"


def test_compute_range_december_january_boundary():
    """12 月到 1 月跨年的月份计算"""
    det = TemporalIntentDetector(now=datetime(2026, 12, 15))
    r = det.detect("上个月做了什么")
    assert r["intent"] == "last_month"
    start, end = r["time_range"]
    assert "2026-11-01" in start
    assert "2026-12-01" in end


def test_compute_range_year_boundary():
    """跨年的 last_year"""
    det = TemporalIntentDetector(now=datetime(2026, 1, 15))
    r = det.detect("去年做了什么")
    assert r["intent"] == "last_year"
    start, end = r["time_range"]
    assert "2025-01-01" in start


# ---------- filter_by_time_range ----------

def test_filter_by_time_range_within_range():
    mems = [
        _mem("a", "x", "2026-07-15T10:00:00"),
        _mem("b", "y", "2026-07-10T10:00:00"),
        _mem("c", "z", "2026-07-20T10:00:00"),
    ]
    out = filter_by_time_range(
        mems, start="2026-07-12T00:00:00", end="2026-07-18T00:00:00"
    )
    ids = [m["id"] for m in out]
    assert "a" in ids
    assert "b" not in ids
    assert "c" not in ids


def test_filter_by_time_range_no_bounds():
    mems = [_mem("a", "x", "2026-07-15T10:00:00")]
    out = filter_by_time_range(mems)
    assert out == mems


def test_filter_by_time_range_skips_no_timestamp():
    """没有 created_at 的记忆被跳过"""
    mems = [
        _mem("a", "x", "2026-07-15T10:00:00"),
        {"id": "b", "content": "no meta", "meta": {}},
    ]
    out = filter_by_time_range(mems, start="2026-07-01", end="2026-07-31")
    ids = [m["id"] for m in out]
    assert "a" in ids
    assert "b" not in ids


def test_filter_by_time_range_custom_field():
    mems = [
        {"id": "a", "content": "x", "meta": {"valid_from": "2026-07-15T10:00:00"}},
        {"id": "b", "content": "y", "meta": {"valid_from": "2026-06-01T00:00:00"}},
    ]
    out = filter_by_time_range(
        mems, start="2026-07-01", end="2026-07-31", time_field="valid_from"
    )
    ids = [m["id"] for m in out]
    assert "a" in ids
    assert "b" not in ids


# ---------- filter_only_valid ----------

def test_filter_only_valid_skips_invalidated():
    mems = [
        _mem("a", "x", invalidated_by=None),
        _mem("b", "y", invalidated_by="01NEW"),
        _mem("c", "z", invalidated_by=None),
    ]
    out = filter_only_valid(mems)
    ids = [m["id"] for m in out]
    assert "a" in ids
    assert "b" not in ids
    assert "c" in ids


def test_filter_only_valid_handles_no_meta():
    mems = [
        {"id": "a", "content": "x", "meta": {}},
        {"id": "b", "content": "y", "meta": None},
    ]
    out = filter_only_valid(mems)
    assert len(out) == 2  # 没有 meta = 视为 valid


# ---------- MemoryManager.search 集成 (mock L4) ----------

@pytest.mark.asyncio
async def test_search_auto_detects_temporal():
    """query 含 '去年' 应自动应用时间过滤"""
    from agent_memory import MemoryManager
    from unittest.mock import AsyncMock, MagicMock

    mm = MemoryManager.__new__(MemoryManager)
    mm._search_raw = AsyncMock(return_value=[
        _mem("a", "old fact", "2025-12-01T10:00:00"),
        _mem("b", "recent fact", "2026-07-15T10:00:00"),
    ])

    # "去年" → 2025 时间范围,旧 fact 命中,新 fact 不命中
    results = await mm.search("去年 12 月我做了什么", limit=10)
    # 由于 mock 返回固定结果,_search_raw 被调,后过滤应只保留 2025 的
    # 但 mock 返回是固定的 2 条,2025 的有 "old fact",2026 的被过滤掉
    ids = [r["id"] for r in results]
    assert "a" in ids
    assert "b" not in ids


@pytest.mark.asyncio
async def test_search_only_valid_false_includes_invalidated():
    """only_valid=False 时包含 invalidated"""
    from agent_memory import MemoryManager
    from unittest.mock import AsyncMock, MagicMock

    mm = MemoryManager.__new__(MemoryManager)
    mm._search_raw = AsyncMock(return_value=[
        _mem("a", "x", invalidated_by=None),
        _mem("b", "y", invalidated_by="01NEW"),
    ])

    results = await mm.search("test", limit=10, only_valid=False)
    ids = [r["id"] for r in results]
    assert "a" in ids
    assert "b" in ids


@pytest.mark.asyncio
async def test_search_explicit_time_range():
    """显式传 time_range 时覆盖 auto_detect"""
    from agent_memory import MemoryManager
    from unittest.mock import AsyncMock, MagicMock

    mm = MemoryManager.__new__(MemoryManager)
    mm._search_raw = AsyncMock(return_value=[
        _mem("a", "fact in range", "2026-03-15T10:00:00"),
        _mem("b", "fact out of range", "2026-07-15T10:00:00"),
    ])

    # 显式传 3 月范围,不依赖 auto_detect
    results = await mm.search(
        "test", limit=10,
        time_range=("2026-03-01T00:00:00", "2026-04-01T00:00:00"),
        auto_detect_temporal=False,
    )
    ids = [r["id"] for r in results]
    assert "a" in ids
    assert "b" not in ids


@pytest.mark.asyncio
async def test_search_no_temporal_returns_all():
    """无时间意图 + only_valid=True 默认行为"""
    from agent_memory import MemoryManager
    from unittest.mock import AsyncMock, MagicMock

    mm = MemoryManager.__new__(MemoryManager)
    mm._search_raw = AsyncMock(return_value=[
        _mem("a", "valid fact"),
        _mem("b", "invalidated fact", invalidated_by="01NEW"),
    ])

    # 查询无时间关键词,只过滤 invalidated
    results = await mm.search("Postgres vs SQLite", limit=10)
    ids = [r["id"] for r in results]
    assert "a" in ids
    assert "b" not in ids