"""
2026-07-15: 时间有效性 (方向 1) 测试

- MemoryMeta.is_valid_at() 单元测试
- L4FilesStore.list_active / update_meta 单元测试
- ContradictionDetector 单元测试
- MemoryManager.add 自动矛盾检测(用 mock)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agent_memory.l4_files import MemoryMeta  # noqa: E402
from agent_memory.contradiction import ContradictionDetector  # noqa: E402


# ---------- MemoryMeta.is_valid_at() ----------

def test_default_meta_is_valid_now():
    """默认 meta 应该在当前时间有效"""
    m = MemoryMeta(id="01A")
    assert m.is_valid_at() is True


def test_invalidated_meta_invalid():
    m = MemoryMeta(id="01A", invalidated_by="01NEW")
    assert m.is_valid_at() is False


def test_valid_until_in_past_invalid():
    m = MemoryMeta(
        id="01A",
        valid_from="2026-01-01T00:00:00",
        valid_until="2026-06-01T00:00:00",
    )
    assert m.is_valid_at("2026-07-01T00:00:00") is False


def test_valid_until_in_future_valid():
    m = MemoryMeta(
        id="01A",
        valid_from="2026-01-01T00:00:00",
        valid_until="2026-12-31T00:00:00",
    )
    assert m.is_valid_at("2026-07-01T00:00:00") is True


def test_valid_from_falls_back_to_created_at():
    """valid_from 为 None 时用 created_at"""
    m = MemoryMeta(id="01A", created_at="2026-01-01T00:00:00")
    assert m.is_valid_at("2025-12-31T00:00:00") is False
    assert m.is_valid_at("2026-01-15T00:00:00") is True


def test_meta_to_dict_includes_validity_fields():
    m = MemoryMeta(id="01A", valid_from="2026-01-01", invalidated_by="01NEW")
    d = m.to_dict()
    assert "valid_from" in d
    assert "valid_until" in d
    assert "invalidated_by" in d
    assert "supersedes" in d


def test_meta_from_dict_roundtrip():
    m = MemoryMeta(
        id="01A",
        valid_from="2026-01-01",
        valid_until="2026-06-01",
        invalidated_by="01NEW",
        supersedes=["01OLD"],
    )
    d = m.to_dict()
    m2 = MemoryMeta.from_dict(d, id="01A")
    assert m2.valid_from == m.valid_from
    assert m2.valid_until == m.valid_until
    assert m2.invalidated_by == m.invalidated_by
    assert m2.supersedes == m.supersedes


# ---------- ContradictionDetector ----------

def test_has_change_intent_chinese():
    det = ContradictionDetector()
    assert det.has_change_intent("我不再用 Postgres 了") is True
    assert det.has_change_intent("我改用 SQLite 了") is True
    assert det.has_change_intent("我搬到 Seattle 了") is True


def test_has_change_intent_english():
    det = ContradictionDetector()
    assert det.has_change_intent("I switched to SQLite") is True
    assert det.has_change_intent("I no longer use Postgres") is True


def test_no_change_intent_for_plain_facts():
    det = ContradictionDetector()
    assert det.has_change_intent("我喜欢吃苹果") is False
    assert det.has_change_intent("今天天气很好") is False
    assert det.has_change_intent("I like apples") is False


def test_extract_keywords_chinese_2grams():
    det = ContradictionDetector()
    kws = det._extract_keywords("我喜欢吃苹果")
    assert "喜欢" in kws
    assert "欢吃" in kws
    assert "吃苹" in kws
    assert "苹果" in kws


def test_extract_keywords_english():
    det = ContradictionDetector()
    kws = det._extract_keywords("I switched to SQLite")
    assert "switched" in kws
    assert "sqlite" in kws


def test_keyword_overlap_full_match():
    det = ContradictionDetector()
    overlap = det._keyword_overlap({"a", "b"}, {"a", "b"})
    assert overlap == 1.0


def test_keyword_overlap_no_match():
    det = ContradictionDetector()
    overlap = det._keyword_overlap({"a", "b"}, {"c", "d"})
    assert overlap == 0.0


def test_keyword_overlap_empty():
    det = ContradictionDetector()
    assert det._keyword_overlap(set(), {"a"}) == 0.0
    assert det._keyword_overlap({"a"}, set()) == 0.0


@pytest.mark.asyncio
async def test_find_and_invalidate_returns_empty_when_no_change_intent():
    """没有变更意图时不触发矛盾检测"""
    det = ContradictionDetector()
    class FakeStore:
        async def list_active(self, limit=100, category_path=None):
            return [{"id": "01OLD", "content": "我喜欢 Postgres",
                     "meta": {"category": "decision"}}]
    result = await det.find_and_invalidate(
        "我喜欢苹果",
        {"category_path": "general"},
        FakeStore(),
    )
    assert result == []


@pytest.mark.asyncio
async def test_find_and_invalidate_detects_contradiction():
    """有变更意图 + 相似内容 → 检测到矛盾"""
    det = ContradictionDetector()
    class FakeStore:
        async def list_active(self, limit=100, category_path=None):
            return [{
                "id": "01OLD",
                "content": "我喜欢用 Postgres 作为主数据库",
                "meta": {"category": "decision", "tags": ["infra"]},
            }]
    result = await det.find_and_invalidate(
        "我不再用 Postgres 了,改用 SQLite",
        {"category_path": "decision"},
        FakeStore(),
    )
    assert "01OLD" in result


@pytest.mark.asyncio
async def test_find_and_invalidate_skips_different_category():
    """不同 category 不算矛盾"""
    det = ContradictionDetector()
    class FakeStore:
        async def list_active(self, limit=100, category_path=None):
            return [{
                "id": "01OLD",
                "content": "我改用 SQLite 替代 Postgres",
                "meta": {"category": "food"},
            }]
    result = await det.find_and_invalidate(
        "我不再用 Postgres 了",
        {"category_path": "infra"},
        FakeStore(),
    )
    assert result == []


@pytest.mark.asyncio
async def test_find_and_invalidate_skips_already_invalidated():
    """已 invalidate 的旧事实不被重复检测"""
    det = ContradictionDetector()
    class FakeStore:
        async def list_active(self, limit=100, category_path=None):
            return []  # list_active 已经过滤掉了 invalidated
    result = await det.find_and_invalidate(
        "我改用 SQLite 替代 Postgres",
        {"category_path": "infra"},
        FakeStore(),
    )
    assert result == []


@pytest.mark.asyncio
async def test_find_and_invalidate_fallback_to_list():
    """没有 list_active 时用 fallback"""
    det = ContradictionDetector()

    class FakeStore:
        def list(self):  # sync
            return ["01OLD"]

        async def load_existing(self, mid):
            return {
                "id": "01OLD",
                "content": "我喜欢用 Postgres 作为主数据库",
                "meta": {"category": "decision"},
            }

    result = await det.find_and_invalidate(
        "我不再用 Postgres 了,改用 SQLite",
        {"category_path": "decision"},
        FakeStore(),
    )
    assert "01OLD" in result


# ---------- L4FilesStore.list_active + update_meta ----------

@pytest.mark.asyncio
async def test_l4_list_active_skips_invalidated(tmp_path):
    """L4.list_active() 应跳过 invalidated 的记忆"""
    from agent_memory.l4_files import L4FilesStore
    store = L4FilesStore(str(tmp_path))
    # 添加 3 条记忆
    await store.save("01A", "fact 1", {
        "id": "01A", "created_at": "2026-07-15T00:00:00",
        "category_path": "general", "importance": 0.5, "tags": [],
    })
    await store.save("01B", "fact 2", {
        "id": "01B", "created_at": "2026-07-15T00:00:00",
        "category_path": "general", "importance": 0.5, "tags": [],
    })
    await store.save("01C", "fact 3", {
        "id": "01C", "created_at": "2026-07-15T00:00:00",
        "category_path": "general", "importance": 0.5, "tags": [],
    })
    # 把 01B 标记为 invalidated
    await store.update_meta("01B", {"invalidated_by": "01NEW"})
    active = await store.list_active(limit=10)
    ids = [m["id"] for m in active]
    assert "01A" in ids
    assert "01B" not in ids  # invalidated 跳过
    assert "01C" in ids


@pytest.mark.asyncio
async def test_l4_update_meta_preserves_content(tmp_path):
    """update_meta 不应改 content,只改 meta"""
    from agent_memory.l4_files import L4FilesStore
    store = L4FilesStore(str(tmp_path))
    await store.save("01A", "重要内容", {
        "id": "01A", "created_at": "2026-07-15T00:00:00",
        "category_path": "general", "importance": 0.9, "tags": [],
    })
    success = await store.update_meta("01A", {"invalidated_by": "01NEW"})
    assert success is True
    loaded = await store.load_existing("01A")
    assert loaded["content"] == "重要内容"  # content 不变
    assert loaded["meta"]["invalidated_by"] == "01NEW"


@pytest.mark.asyncio
async def test_l4_update_meta_nonexistent_returns_false(tmp_path):
    """update_meta 对不存在 ID 返回 False"""
    from agent_memory.l4_files import L4FilesStore
    store = L4FilesStore(str(tmp_path))
    success = await store.update_meta("01NONEXISTENT", {"invalidated_by": "01NEW"})
    assert success is False


@pytest.mark.asyncio
async def test_l4_list_active_filter_by_category(tmp_path):
    """list_active 按 category 过滤"""
    from agent_memory.l4_files import L4FilesStore
    store = L4FilesStore(str(tmp_path))
    await store.save("01A", "x", {
        "id": "01A", "created_at": "2026-07-15", "category_path": "decision",
        "importance": 0.5, "tags": []
    })
    await store.save("01B", "y", {
        "id": "01B", "created_at": "2026-07-15", "category_path": "food",
        "importance": 0.5, "tags": []
    })
    active = await store.list_active(limit=10, category_path="decision")
    ids = [m["id"] for m in active]
    assert "01A" in ids
    assert "01B" not in ids


# ---------- MemoryManager.add 自动矛盾检测(mock L4) ----------

@pytest.mark.asyncio
async def test_memory_manager_add_sets_validity_fields():
    """MemoryManager.add 应自动设置 valid_from/valid_until 字段"""
    from agent_memory import MemoryManager
    from unittest.mock import AsyncMock, MagicMock

    mm = MemoryManager.__new__(MemoryManager)
    mm.l4 = MagicMock()
    mm.l4.save = AsyncMock()
    mm.sync = MagicMock()
    mm.sync.sync_one = AsyncMock()
    mm.classifier = MagicMock()
    mm.classifier.classify = MagicMock(return_value="general")
    mm._generate_id = MagicMock(return_value="01NEW")
    mm._invalidate_cache = MagicMock()

    # 直接调 add 看 meta_dict
    from agent_memory.manager import MemoryManager
    import asyncio

    async def fake_save(mid, content, meta):
        # 验证 meta 包含 valid_from/valid_until
        assert "valid_from" in meta
        assert "valid_until" in meta
        assert "invalidated_by" in meta
        assert "supersedes" in meta

    mm.l4.save = fake_save

    await mm.add("test memory", importance=0.8)