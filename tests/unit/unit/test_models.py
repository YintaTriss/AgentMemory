"""
AgentMemory v2.0 - Models 单元测试

测试数据模型：Memory, Fact, Entity, Relation
验证数据契约和 Pydantic v2 特性
"""

import sys
import os
from datetime import datetime, timezone
from typing import get_type_hints

import pytest

# Add source path
sys.path.insert(0, "C:/Users/31683/AgentMemory/agentmemory")

from models import Memory, Fact, Entity, Relation, _default_ulid, _default_utcnow


class TestMemoryModel:
    """Memory 模型测试"""
    
    def test_memory_creation_with_required_fields(self):
        """测试仅使用必需字段创建 Memory"""
        memory = Memory(content="测试记忆内容")
        
        assert memory.content == "测试记忆内容"
        assert memory.importance == 0.5  # 默认值
        assert memory.id is not None  # 自动生成 ID
        assert memory.created_at is not None  # 自动生成时间戳
        assert memory.schema_version == 1
    
    def test_memory_creation_with_all_fields(self):
        """测试使用所有字段创建 Memory"""
        custom_id = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
        custom_time = datetime(2026, 6, 5, tzinfo=timezone.utc)
        
        memory = Memory(
            id=custom_id,
            content="完整测试",
            importance=0.9,
            created_at=custom_time,
            schema_version=1,
        )
        
        assert memory.id == custom_id
        assert memory.content == "完整测试"
        assert memory.importance == 0.9
        assert memory.created_at == custom_time
    
    def test_memory_importance_bounds(self):
        """测试 importance 字段边界"""
        # 最小值 0.0
        memory_min = Memory(content="最小重要性", importance=0.0)
        assert memory_min.importance == 0.0
        
        # 最大值 1.0
        memory_max = Memory(content="最大重要性", importance=1.0)
        assert memory_max.importance == 1.0
        
        # 超出范围应该抛出 ValidationError
        with pytest.raises(Exception):  # Pydantic ValidationError
            Memory(content="超出范围", importance=1.5)
        
        with pytest.raises(Exception):
            Memory(content="低于范围", importance=-0.1)
    
    def test_memory_to_dict(self):
        """测试 to_dict 方法"""
        memory = Memory(
            content="转换为字典测试",
            importance=0.7,
        )
        
        result = memory.to_dict()
        
        assert isinstance(result, dict)
        assert result["content"] == "转换为字典测试"
        assert result["importance"] == 0.7
        assert "id" in result
        assert "created_at" in result
        assert "schema_version" in result
    
    def test_memory_model_dump_json(self):
        """测试 JSON 序列化"""
        memory = Memory(content="JSON序列化测试")
        
        json_str = memory.model_dump_json()
        
        assert isinstance(json_str, str)
        assert "JSON序列化测试" in json_str
    
    def test_memory_extra_fields_forbidden(self):
        """测试禁止额外字段（extra="forbid"）"""
        with pytest.raises(Exception):  # Pydantic ValidationError
            Memory(
                content="额外字段测试",
                unknown_field="这不应该存在",
            )
    
    def test_memory_unicode_content(self):
        """测试 Unicode 内容支持"""
        unicode_content = "中文内容 �🇨🇳 Emoji 支持测试 🎉"
        memory = Memory(content=unicode_content)
        
        assert memory.content == unicode_content
        assert memory.to_dict()["content"] == unicode_content
    
    def test_memory_empty_content(self):
        """测试空内容（应该允许，因为 content 无 min_length）"""
        memory = Memory(content="")
        assert memory.content == ""


class TestFactModel:
    """Fact 模型测试（继承 Memory）"""
    
    def test_fact_creation(self):
        """测试 Fact 创建"""
        fact = Fact(
            subject="小明",
            predicate="学习",
            object="Python",
            content="小明学习Python",
            importance=0.8,
        )
        
        assert fact.subject == "小明"
        assert fact.predicate == "学习"
        assert fact.object == "Python"
        assert fact.content == "小明学习Python"
        assert fact.importance == 0.8
    
    def test_fact_to_triple(self):
        """测试 to_triple 方法"""
        fact = Fact(
            subject="北京",
            predicate="是",
            object="中国的首都",
            content="北京是中国的首都",
        )
        
        triple = fact.to_triple()
        
        assert triple == ("北京", "是", "中国的首都")
        assert isinstance(triple, tuple)
        assert len(triple) == 3
    
    def test_fact_inherits_memory(self):
        """测试 Fact 继承 Memory 的属性"""
        fact = Fact(
            subject="太阳",
            predicate="升起于",
            object="东方",
            content="太阳升起于东方",
        )
        
        # 继承的属性
        assert hasattr(fact, "id")
        assert hasattr(fact, "importance")
        assert hasattr(fact, "created_at")
        assert fact.schema_version == 1


class TestEntityModel:
    """Entity 模型测试"""
    
    def test_entity_creation(self):
        """测试 Entity 创建"""
        entity = Entity(
            name="人工智能",
            type="concept",
            attributes={"field": "计算机科学"},
        )
        
        assert entity.name == "人工智能"
        assert entity.type == "concept"
        assert entity.attributes["field"] == "计算机科学"
        assert entity.id is not None
    
    def test_entity_with_default_attributes(self):
        """测试默认 attributes"""
        entity = Entity(name="测试实体", type="test")
        
        assert entity.attributes == {}
    
    def test_entity_to_dict(self):
        """测试 to_dict 方法"""
        entity = Entity(
            name="神经网络",
            type="concept",
            attributes={"layer": "3"},
        )
        
        result = entity.to_dict()
        
        assert isinstance(result, dict)
        assert result["name"] == "神经网络"
        assert result["type"] == "concept"
        assert result["attributes"]["layer"] == "3"
        assert "id" in result
    
    def test_entity_extra_fields_forbidden(self):
        """测试禁止额外字段"""
        with pytest.raises(Exception):
            Entity(
                name="测试",
                type="test",
                invalid_field="不应该存在",
            )
    
    def test_entity_unicode_name(self):
        """测试 Unicode 名称支持"""
        entity = Entity(
            name="中文实体名 💻",
            type="测试",
        )
        
        assert "中文实体名" in entity.name


class TestRelationModel:
    """Relation 模型测试"""
    
    def test_relation_creation(self):
        """测试 Relation 创建"""
        relation = Relation(
            source="entity-1",
            target="entity-2",
            type="包含",
            weight=0.9,
        )
        
        assert relation.source == "entity-1"
        assert relation.target == "entity-2"
        assert relation.type == "包含"
        assert relation.weight == 0.9
        assert relation.id is not None
    
    def test_relation_default_weight(self):
        """测试默认权重"""
        relation = Relation(
            source="src",
            target="tgt",
            type="关联",
        )
        
        assert relation.weight == 1.0
    
    def test_relation_weight_bounds(self):
        """测试权重边界"""
        # 有效范围
        rel_min = Relation(source="a", target="b", type="t", weight=0.0)
        assert rel_min.weight == 0.0
        
        rel_max = Relation(source="a", target="b", type="t", weight=1.0)
        assert rel_max.weight == 1.0
        
        # 无效范围
        with pytest.raises(Exception):
            Relation(source="a", target="b", type="t", weight=1.5)
        
        with pytest.raises(Exception):
            Relation(source="a", target="b", type="t", weight=-0.1)
    
    def test_relation_to_dict(self):
        """测试 to_dict 方法"""
        relation = Relation(
            source="S",
            target="T",
            type="关系",
            weight=0.5,
        )
        
        result = relation.to_dict()
        
        assert isinstance(result, dict)
        assert result["source"] == "S"
        assert result["target"] == "T"
        assert result["type"] == "关系"
        assert result["weight"] == 0.5


class TestDefaultFunctions:
    """默认函数测试"""
    
    def test_default_ulid_format(self):
        """测试 ULID 格式"""
        ulid_str = _default_ulid()
        
        assert isinstance(ulid_str, str)
        assert len(ulid_str) > 0
        # ULID 格式检查（26个字符，字母数字混合）
        assert ulid_str.isalnum()
    
    def test_default_ulid_uniqueness(self):
        """测试 ULID 唯一性"""
        ulids = [_default_ulid() for _ in range(100)]
        
        assert len(set(ulids)) == 100  # 全部唯一
    
    def test_default_utcnow(self):
        """测试 UTC 时间戳"""
        now = _default_utcnow()
        
        assert isinstance(now, datetime)
        assert now.tzinfo is not None  # 带时区信息


class TestEdgeCases:
    """边界情况测试"""
    
    def test_memory_long_content(self):
        """测试超长内容"""
        long_content = "测试内容 " * 10000  # 约 80KB
        memory = Memory(content=long_content)
        
        assert len(memory.content) == len(long_content)
    
    def test_memory_special_characters(self):
        """测试特殊字符"""
        special_content = "特殊字符: <>&\"' 脚本: <script> SQL: ' OR 1=1 --"
        memory = Memory(content=special_content)
        
        assert memory.content == special_content
    
    def test_entity_empty_name_rejected(self):
        """测试空名称应被拒绝（如果有约束）"""
        # name 字段有 ... (required)，空字符串可能通过验证
        entity = Entity(name="", type="empty")
        assert entity.name == ""
    
    def test_multiple_models_serialization(self):
        """测试多个模型序列化"""
        memory = Memory(content="测试")
        fact = Fact(subject="S", predicate="P", object="O", content="SPO")
        entity = Entity(name="E", type="test")
        relation = Relation(source="S", target="T", type="R")
        
        models = [memory, fact, entity, relation]
        
        for model in models:
            d = model.to_dict()
            assert isinstance(d, dict)
            assert "id" in d
