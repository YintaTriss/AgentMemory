"""
测试 Pydantic v2 数据模型
验证 Memory/Fact/Entity/Relation 的实例化、序列化、严格模式
"""
import pytest
from datetime import datetime, timezone
from src.models import Memory, Fact, Entity, Relation


class TestMemory:
    """测试 Memory 模型"""
    
    def test_basic_instantiation(self):
        """基本实例化"""
        m = Memory(content="test memory")
        assert m.content == "test memory"
        assert m.importance == 0.5
        assert m.schema_version == 1
        assert m.id is not None
    
    def test_full_instantiation(self):
        """完整参数实例化"""
        m = Memory(
            id="01HX1234567890ABCDEFGHIJ23",
            content="test memory",
            importance=0.8,
            created_at=datetime.now(timezone.utc),
        )
        assert m.content == "test memory"
        assert m.importance == 0.8
    
    def test_serialization(self):
        """序列化测试"""
        m = Memory(content="test")
        d = m.model_dump()
        assert "schema_version" in d
        assert d["schema_version"] == 1
        assert "id" in d
        assert isinstance(d["id"], str)
    
    def test_importance_bounds(self):
        """重要性分数边界"""
        m = Memory(content="low", importance=0.0)
        assert m.importance == 0.0
        m = Memory(content="high", importance=1.0)
        assert m.importance == 1.0
    
    def test_strict_mode_rejects_extra(self):
        """严格模式拒绝额外字段"""
        with pytest.raises(Exception):  # Pydantic v2 raises ValidationError
            Memory(content="test", extra_field="should fail")
    
    def test_to_dict(self):
        """to_dict 兼容性方法"""
        m = Memory(content="test")
        d = m.to_dict()
        assert d["content"] == "test"


class TestFact:
    """测试 Fact 模型"""
    
    def test_basic_instantiation(self):
        """基本实例化"""
        f = Fact(
            content="John is the author of Python",
            subject="John",
            predicate="is author of",
            object="Python",
        )
        assert f.subject == "John"
        assert f.predicate == "is author of"
        assert f.object == "Python"
    
    def test_to_triple(self):
        """转换为三元组"""
        f = Fact(
            content="A relates to B",
            subject="A",
            predicate="relates to",
            object="B",
        )
        triple = f.to_triple()
        assert triple == ("A", "relates to", "B")
    
    def test_inherits_from_memory(self):
        """继承自 Memory"""
        f = Fact(content="test", subject="A", predicate="B", object="C")
        assert hasattr(f, "id")
        assert hasattr(f, "importance")
        assert f.schema_version == 1
    
    def test_serialization(self):
        """序列化测试"""
        f = Fact(content="test", subject="A", predicate="B", object="C")
        d = f.model_dump()
        assert "subject" in d
        assert "predicate" in d
        assert "object" in d
    
    def test_strict_mode_rejects_extra(self):
        """严格模式拒绝额外字段"""
        with pytest.raises(Exception):
            Fact(content="test", subject="A", predicate="B", object="C", extra="x")


class TestEntity:
    """测试 Entity 模型"""
    
    def test_basic_instantiation(self):
        """基本实例化"""
        e = Entity(
            name="John Doe",
            type="person",
            attributes={"age": 30},
        )
        assert e.name == "John Doe"
        assert e.type == "person"
        assert e.attributes == {"age": 30}
    
    def test_full_instantiation(self):
        """完整参数实例化"""
        e = Entity(
            id="01HX1234567890ABCDEFGHIJ23",
            name="Python",
            type="language",
            attributes={"year": 1991},
        )
        assert e.name == "Python"
        assert e.type == "language"
    
    def test_serialization(self):
        """序列化测试"""
        e = Entity(name="test", type="type")
        d = e.model_dump()
        assert "id" in d
        assert "name" in d
        assert "type" in d
        assert "attributes" in d
    
    def test_default_attributes(self):
        """默认属性为空字典"""
        e = Entity(name="test", type="type")
        assert e.attributes == {}
    
    def test_strict_mode_rejects_extra(self):
        """严格模式拒绝额外字段"""
        with pytest.raises(Exception):
            Entity(name="test", type="type", extra_field="should fail")


class TestRelation:
    """测试 Relation 模型"""
    
    def test_basic_instantiation(self):
        """基本实例化"""
        r = Relation(
            source="entity1",
            target="entity2",
            type="knows",
        )
        assert r.source == "entity1"
        assert r.target == "entity2"
        assert r.type == "knows"
    
    def test_with_weight(self):
        """带权重的实例化"""
        r = Relation(
            source="entity1",
            target="entity2",
            type="knows",
            weight=0.9,
        )
        assert r.weight == 0.9
    
    def test_weight_bounds(self):
        """权重边界"""
        r = Relation(source="A", target="B", type="T", weight=0.0)
        assert r.weight == 0.0
        r = Relation(source="A", target="B", type="T", weight=1.0)
        assert r.weight == 1.0
    
    def test_serialization(self):
        """序列化测试"""
        r = Relation(source="A", target="B", type="T")
        d = r.model_dump()
        assert "id" in d
        assert "source" in d
        assert "target" in d
        assert "type" in d
        assert "weight" in d
    
    def test_strict_mode_rejects_extra(self):
        """严格模式拒绝额外字段"""
        with pytest.raises(Exception):
            Relation(source="A", target="B", type="T", extra="x")
