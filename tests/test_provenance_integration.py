"""
2026-07-15: Provenance 暴露 (方向 4) 测试

L1LCMCompressor.compress() 在 Key Facts 段每条事实后追加 [Source: ..., date] 标注。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agent_memory.l1_lcm import L1LCMCompressor  # noqa: E402


def _mem(content, importance=0.9, source="", created_at="", tags=None, category="general"):
    return {
        "id": content[:8],
        "content": content,
        "meta": {
            "importance": importance,
            "category": category,
            "tags": tags or [],
            "source": source,
            "created_at": created_at,
        },
    }


def test_provenance_with_source_and_date():
    l1 = L1LCMCompressor()
    out = l1.compress([_mem(
        "我决定改用 NewAPI",
        importance=0.9,
        source="openclaw-webchat",
        created_at="2026-07-14T23:25:00",
    )])
    assert "[Source: openclaw-webchat, 2026-07-14]" in out


def test_provenance_with_source_only():
    l1 = L1LCMCompressor()
    out = l1.compress([_mem(
        "我决定改用 NewAPI", importance=0.9, source="openclaw-webchat"
    )])
    assert "[Source: openclaw-webchat]" in out


def test_provenance_with_date_only():
    l1 = L1LCMCompressor()
    out = l1.compress([_mem(
        "我决定改用 NewAPI", importance=0.9, created_at="2026-07-14T23:25:00"
    )])
    assert "[Source: 2026-07-14]" in out


def test_no_provenance_when_neither():
    l1 = L1LCMCompressor()
    out = l1.compress([_mem("我决定改用 NewAPI", importance=0.9)])
    # 没有任何 source/date 时不显示 [Source: ...]
    assert "[Source:" not in out


def test_provenance_uses_italics_marker():
    l1 = L1LCMCompressor()
    out = l1.compress([_mem(
        "x", importance=0.9, source="openclaw-webchat", created_at="2026-07-14T23:25:00"
    )])
    # 用 *[Source: ...]* 斜体 markdown,让 prompt 渲染更柔和
    assert "*[Source:" in out


def test_provenance_only_in_important_section():
    l1 = L1LCMCompressor()
    important = _mem(
        "important fact", importance=0.9,
        source="openclaw-webchat", created_at="2026-07-14T23:25:00"
    )
    background = _mem(
        "background fact", importance=0.3,
        source="openclaw-webchat", created_at="2026-07-15T11:00:00"
    )
    out = l1.compress([important, background])
    # 关键事实段有 Provenance;背景段没有
    assert "[Source:" in out
    # 但 Background 段不应有
    bg_idx = out.find("## Background")
    bg_section = out[bg_idx:]
    assert "[Source:" not in bg_section


def test_provenance_with_iso_datetime_truncates_to_date():
    """created_at 是 ISO datetime,只显示 YYYY-MM-DD 部分"""
    l1 = L1LCMCompressor()
    out = l1.compress([_mem(
        "x", importance=0.9, created_at="2026-07-14T23:25:00.123456+08:00"
    )])
    assert "[Source: 2026-07-14]" in out


def test_provenance_with_empty_string_source_skipped():
    l1 = L1LCMCompressor()
    out = l1.compress([_mem(
        "x", importance=0.9, source="", created_at="2026-07-14T23:25:00"
    )])
    assert "[Source: 2026-07-14]" in out
    assert "[Source: , " not in out  # 不应有空 source + , 的形式


def test_provenance_preserves_tags_order():
    l1 = L1LCMCompressor()
    out = l1.compress([_mem(
        "x", importance=0.9,
        source="openclaw-webchat", created_at="2026-07-14T23:25:00",
        tags=["infra", "decision"]
    )])
    # tags 在 category 后面;Provenance 在 content 后面
    assert "[general] [infra, decision] x  *[Source: openclaw-webchat, 2026-07-14]*" in out


def test_provenance_multiple_memories_each_have_source():
    l1 = L1LCMCompressor()
    mems = [
        _mem("fact 1", importance=0.9, source="webchat", created_at="2026-07-14T00:00:00"),
        _mem("fact 2", importance=0.85, source="cli", created_at="2026-07-15T00:00:00"),
    ]
    out = l1.compress(mems)
    assert "[Source: webchat, 2026-07-14]" in out
    assert "[Source: cli, 2026-07-15]" in out


def test_provenance_limit_to_10_important_memories():
    """只前 10 条重要记忆有 Provenance 标注"""
    l1 = L1LCMCompressor()
    mems = [
        _mem(f"fact {i}", importance=0.9,
             source=f"src-{i}", created_at=f"2026-07-{15-i:02d}T00:00:00")
        for i in range(15)
    ]
    out = l1.compress(mems)
    # 前 10 条重要记忆有 [Source: ...]
    source_count = out.count("[Source:")
    assert source_count <= 10