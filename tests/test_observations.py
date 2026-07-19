"""
2026-07-15: Observations (方向 3) 测试

- ObservationsGenerator 直接测试
- MemoryManager.get_observations() 集成测试
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agent_memory.observations import ObservationsGenerator  # noqa: E402


def _mem(content, importance=0.5, source="", created_at="", tags=None,
         category="general"):
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


# ---------- ObservationsGenerator 单元测试 ----------

def test_empty_memories_no_observations():
    gen = ObservationsGenerator()
    assert gen.generate([]) == []


def test_finds_frequent_tags():
    gen = ObservationsGenerator(min_tag_freq=3)
    mems = [
        _mem(f"fact {i}", tags=["infra", "decision"] if i < 3 else ["infra"])
        for i in range(5)
    ]
    obs = gen.generate(mems)
    assert any("高频标签" in o for o in obs)
    assert any("infra" in o for o in obs)


def test_no_frequent_tag_observation_when_below_threshold():
    gen = ObservationsGenerator(min_tag_freq=10)
    mems = [_mem(f"f{i}", tags=["x"]) for i in range(5)]
    obs = gen.generate(mems)
    assert not any("高频标签" in o for o in obs)


def test_high_importance_count():
    gen = ObservationsGenerator(high_importance_threshold=0.8)
    mems = [
        _mem("important 1", importance=0.9),
        _mem("important 2", importance=0.85),
        _mem("normal", importance=0.5),
    ]
    obs = gen.generate(mems)
    assert any("高重要度" in o and "2 条" in o for o in obs)


def test_same_day_density():
    gen = ObservationsGenerator(same_day_density=2)
    mems = [
        _mem("a", created_at="2026-07-15T08:00:00"),
        _mem("b", created_at="2026-07-15T09:00:00"),
        _mem("c", created_at="2026-07-15T10:00:00"),
        _mem("d", created_at="2026-07-14T10:00:00"),
    ]
    obs = gen.generate(mems)
    assert any("高频日期" in o and "2026-07-15" in o for o in obs)


def test_category_distribution():
    gen = ObservationsGenerator()
    mems = [
        _mem("a", category="decision"),
        _mem("b", category="decision"),
        _mem("c", category="decision"),
        _mem("d", category="project"),
        _mem("e", category="general"),
    ]
    obs = gen.generate(mems)
    assert any("类别分布" in o and "decision" in o for o in obs)


def test_source_distribution_multiple_sources():
    gen = ObservationsGenerator()
    mems = [
        _mem("a", source="webchat"),
        _mem("b", source="webchat"),
        _mem("c", source="cli"),
    ]
    obs = gen.generate(mems)
    assert any("来源分布" in o for o in obs)


def test_single_source_no_distribution_observation():
    """只有一个来源时不应触发来源分布 observation"""
    gen = ObservationsGenerator()
    mems = [_mem(f"f{i}", source="webchat") for i in range(5)]
    obs = gen.generate(mems)
    assert not any("来源分布" in o for o in obs)


def test_max_observations_limit():
    gen = ObservationsGenerator(max_observations=2)
    # 给定 6 条记忆,有多个 observation 类型 → 应被截到 2
    mems = [_mem(
        f"f{i}",
        importance=0.9,
        source="src",
        created_at=f"2026-07-{15 - i % 5:02d}T00:00:00",
        tags=["t1", "t2"],
        category="decision",
    ) for i in range(6)]
    obs = gen.generate(mems)
    assert len(obs) <= 2


def test_handles_missing_meta():
    """容错:meta 缺失时不应崩"""
    gen = ObservationsGenerator()
    mems = [
        {"id": "a", "content": "no meta"},  # 没有 meta key
        _mem("with meta"),
    ]
    obs = gen.generate(mems)
    assert isinstance(obs, list)


def test_handles_empty_tags_list():
    gen = ObservationsGenerator()
    mems = [_mem(f"f{i}", tags=[]) for i in range(3)]
    obs = gen.generate(mems)
    assert not any("高频标签" in o for o in obs)


def test_chinese_tags_works():
    gen = ObservationsGenerator(min_tag_freq=2)
    mems = [
        _mem("决策 1", tags=["决策", "基础设施"]),
        _mem("决策 2", tags=["决策", "基础设施"]),
        _mem("决策 3", tags=["决策"]),
    ]
    obs = gen.generate(mems)
    assert any("决策" in o and "基础设施" in o for o in obs)


# ---------- MemoryManager.get_observations 集成测试 (mock,避免 Qdrant 锁冲突) ----------

@pytest.mark.asyncio
async def test_memory_manager_get_observations_empty():
    """空 manager 时 get_observations 应返回 [] (mock)"""
    from agent_memory import MemoryManager
    from unittest.mock import AsyncMock, MagicMock

    mm = MemoryManager.__new__(MemoryManager)
    mm.l4 = MagicMock()
    mm.l4.load_existing = AsyncMock(return_value=None)

    obs = await mm.get_observations(memory_ids=[])
    assert obs == []


@pytest.mark.asyncio
async def test_memory_manager_get_observations_with_memories():
    """有记忆时 get_observations 应生成 pattern (mock)"""
    from agent_memory import MemoryManager
    from unittest.mock import AsyncMock, MagicMock

    mm = MemoryManager.__new__(MemoryManager)
    # 5 条 mock memory
    mock_mems = [
        {
            "id": f"01ABC{i}",
            "content": f"事实 {i}",
            "meta": {
                "importance": 0.9,
                "category": "decision",
                "tags": ["infra", "decision"],
                "source": "test",
                "created_at": "2026-07-15T11:00:00",
            },
        }
        for i in range(5)
    ]
    mm.l4 = MagicMock()
    mm.l4.load_existing = AsyncMock(side_effect=mock_mems + [None])

    ids = [f"01ABC{i}" for i in range(5)]
    obs = await mm.get_observations(memory_ids=ids)
    assert any("高频标签" in o and "infra" in o for o in obs)