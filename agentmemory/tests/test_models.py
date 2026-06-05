"""
test_models.py — MemoryEntry 模型测试
验证 v2.0 schema_version=2 的所有字段和验证规则
"""
import pytest
from datetime import datetime, timezone
from agentmemory.models import MemoryEntry


class TestMemoryEntrySchemaV2:
    """测试 MemoryEntry v2.0 schema"""

    def test_memory_entry_schema_v2(self):
        """schema_version == 2，所有12个字段都存在，字段类型正确"""
        entry = MemoryEntry(
            content="测试记忆内容",
            category=["A.项目", "石榴籽"],
        )
        assert entry.schema_version == 2
        # 验证所有12个字段都存在
        assert hasattr(entry, "id")
        assert hasattr(entry, "content")
        assert hasattr(entry, "category")
        assert hasattr(entry, "tags")
        assert hasattr(entry, "metadata")
        assert hasattr(entry, "importance")
        assert hasattr(entry, "embedding_state")
        assert hasattr(entry, "created_at")
        assert hasattr(entry, "updated_at")
        assert hasattr(entry, "last_access_at")
        assert hasattr(entry, "access_count")
        assert hasattr(entry, "schema_version")
        # 字段类型
        assert isinstance(entry.id, str)
        assert isinstance(entry.content, str)
        assert isinstance(entry.category, list)
        assert isinstance(entry.tags, list)
        assert isinstance(entry.metadata, dict)
        assert isinstance(entry.importance, float)
        assert entry.embedding_state in ("pending", "generating", "completed", "failed", "permanent_failure")
        assert isinstance(entry.created_at, datetime)
        assert isinstance(entry.updated_at, datetime)
        assert entry.last_access_at is None
        assert isinstance(entry.access_count, int)
        assert entry.schema_version == 2

    def test_memory_entry_all_fields_explicit(self):
        """显式传入所有字段，验证完整构造"""
        now = datetime.now(timezone.utc)
        entry = MemoryEntry(
            id="01HX1234567890ABCDEFGHIJ23",
            content="完整测试",
            category=["B.个人", "日记"],
            tags=["重要", "工作"],
            metadata={"source": "test"},
            importance=0.9,
            embedding_state="completed",
            created_at=now,
            updated_at=now,
            last_access_at=now,
            access_count=5,
            schema_version=2,
        )
        assert entry.id == "01HX1234567890ABCDEFGHIJ23"
        assert entry.content == "完整测试"
        assert entry.category == ["B.个人", "日记"]
        assert entry.tags == ["重要", "工作"]
        assert entry.metadata == {"source": "test"}
        assert entry.importance == 0.9
        assert entry.embedding_state == "completed"
        assert entry.last_access_at == now
        assert entry.access_count == 5


class TestMemoryEntryValidation:
    """测试 MemoryEntry 字段验证"""

    def test_importance_bounds_valid(self):
        """importance 0.0 和 1.0 合法"""
        e1 = MemoryEntry(content="min", category=["A"], importance=0.0)
        assert e1.importance == 0.0
        e2 = MemoryEntry(content="max", category=["A"], importance=1.0)
        assert e2.importance == 1.0

    def test_importance_out_of_bounds_rejected(self):
        """importance 超出 [0, 1] 被拒绝"""
        with pytest.raises(Exception):
            MemoryEntry(content="test", category=["A"], importance=-0.1)
        with pytest.raises(Exception):
            MemoryEntry(content="test", category=["A"], importance=1.5)

    def test_category_must_be_list_str(self):
        """category 必须是 list[str]"""
        entry = MemoryEntry(content="test", category=["A.项目", "子分类"])
        assert all(isinstance(c, str) for c in entry.category)

    def test_category_empty_rejected(self):
        """category 空列表被拒绝"""
        with pytest.raises(Exception):
            MemoryEntry(content="test", category=[])

    def test_category_too_deep_rejected(self):
        """category 超过4层被拒绝"""
        with pytest.raises(Exception):
            MemoryEntry(content="test", category=["A", "B", "C", "D", "E"])

    def test_tags_must_be_list_str(self):
        """tags 必须是 list[str]"""
        entry = MemoryEntry(content="test", category=["A"], tags=["tag1", "tag2"])
        assert entry.tags == ["tag1", "tag2"]
        assert all(isinstance(t, str) for t in entry.tags)

    def test_tags_default_empty_list(self):
        """tags 默认空列表"""
        entry = MemoryEntry(content="test", category=["A"])
        assert entry.tags == []

    def test_content_min_length(self):
        """content 最小长度1"""
        entry = MemoryEntry(content="x", category=["A"])
        assert entry.content == "x"

    def test_content_empty_rejected(self):
        """content 为空被拒绝"""
        with pytest.raises(Exception):
            MemoryEntry(content="", category=["A"])

    def test_content_max_length(self):
        """content 最大长度 100_000"""
        long_content = "x" * 100_000
        entry = MemoryEntry(content=long_content, category=["A"])
        assert len(entry.content) == 100_000

    def test_content_too_long_rejected(self):
        """content 超过 100_000 被拒绝"""
        with pytest.raises(Exception):
            MemoryEntry(content="x" * 100_001, category=["A"])

    def test_to_dict(self):
        """to_dict 转换为字典"""
        entry = MemoryEntry(content="test", category=["A"])
        d = entry.to_dict()
        assert isinstance(d, dict)
        assert d["content"] == "test"
        assert d["schema_version"] == 2
