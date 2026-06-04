"""
L2_graph_store.py 单元测试
v1.0 API 对齐版本
"""

import pytest
import json
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.L2_graph_store import GraphStore, Entity, EntityType, RelationType, Relation


class TestEntity:
    """Entity 实体测试"""
    
    def test_entity_creation(self):
        """测试实体创建"""
        entity = Entity(
            name="优优",
            entity_type=EntityType.PERSON,
            properties={"role": "学生", "grade": "高三"}
        )
        
        assert entity.name == "优优"
        assert entity.entity_type == EntityType.PERSON
        assert entity.properties["role"] == "学生"
    
    def test_entity_type_enum(self):
        """测试实体类型枚举"""
        assert EntityType.PERSON.value == "PERSON"
        assert EntityType.PROJECT.value == "PROJECT"
        assert EntityType.CONCEPT.value == "CONCEPT"
        assert EntityType.LOCATION.value == "LOCATION"
        assert EntityType.ORGANIZATION.value == "ORGANIZATION"
    
    def test_entity_default_properties(self):
        """测试实体默认属性"""
        entity = Entity(name="测试实体", entity_type=EntityType.CONCEPT)
        
        assert entity.properties == {}
    
    def test_entity_to_dict(self):
        """测试实体序列化"""
        entity = Entity(
            name="测试",
            entity_type=EntityType.PROJECT,
            properties={"key": "value"}
        )
        d = entity.to_dict()
        
        assert d["name"] == "测试"
        assert d["entity_type"] == "PROJECT"
        assert d["properties"]["key"] == "value"
    
    def test_entity_from_dict(self):
        """测试实体反序列化"""
        data = {
            "name": "测试实体",
            "entity_type": "PERSON",
            "properties": {"role": "developer"},
            "aliases": ["alias1"]
        }
        entity = Entity.from_dict(data)
        
        assert entity.name == "测试实体"
        assert entity.entity_type == EntityType.PERSON
        assert entity.properties["role"] == "developer"


class TestRelation:
    """Relation 关系测试"""
    
    def test_relation_creation(self):
        """测试关系创建"""
        relation = Relation(
            source_entity_id="entity_1",
            target_entity_id="entity_2",
            relation_type=RelationType.WORKS_ON,
            properties={"since": "2024"}
        )
        
        assert relation.source_entity_id == "entity_1"
        assert relation.target_entity_id == "entity_2"
        assert relation.relation_type == RelationType.WORKS_ON
    
    def test_relation_type_enum(self):
        """测试关系类型枚举"""
        assert RelationType.KNOWS.value == "KNOWS"
        assert RelationType.WORKS_ON.value == "WORKS_ON"
        assert RelationType.PART_OF.value == "PART_OF"
        assert RelationType.CREATED.value == "CREATED"
        assert RelationType.BELONGS_TO.value == "BELONGS_TO"
    
    def test_relation_default_weight(self):
        """测试关系默认权重"""
        relation = Relation(
            source_entity_id="e1",
            target_entity_id="e2",
            relation_type=RelationType.KNOWS
        )
        
        assert relation.weight == 1.0


class TestGraphStore:
    """GraphStore 图谱存储测试"""
    
    @pytest.fixture
    def store_path(self):
        """创建临时图谱存储路径"""
        temp_dir = tempfile.mkdtemp()
        path = os.path.join(temp_dir, "test_graph.json")
        yield path
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_graph_store_init(self, store_path):
        """测试图谱存储初始化"""
        store = GraphStore(store_path)
        
        assert str(store._store_path) == store_path
        assert store.get_entity_count() == {}
    
    def test_add_entity(self, store_path):
        """测试添加实体"""
        store = GraphStore(store_path)
        
        entity = Entity(name="石榴籽", entity_type=EntityType.PROJECT, properties={"category": "AI翻译"})
        entity_id = store.add_entity(entity)
        
        assert entity_id is not None
        assert len(entity_id) > 0
        
        # 验证实体数量增加
        counts = store.get_entity_count()
        assert counts.get("PROJECT", 0) == 1
    
    def test_add_multiple_entities(self, store_path):
        """测试添加多个实体"""
        store = GraphStore(store_path)
        
        e1 = Entity(name="优优", entity_type=EntityType.PERSON)
        e2 = Entity(name="石榴籽", entity_type=EntityType.PROJECT)
        e3 = Entity(name="AI", entity_type=EntityType.CONCEPT)
        
        id1 = store.add_entity(e1)
        id2 = store.add_entity(e2)
        id3 = store.add_entity(e3)
        
        assert id1 != id2
        assert id2 != id3
        assert store.get_entity_count().get("PERSON", 0) == 1
        assert store.get_entity_count().get("PROJECT", 0) == 1
        assert store.get_entity_count().get("CONCEPT", 0) == 1
    
    def test_add_relation(self, store_path):
        """测试添加关系 - 注意：Relation 作为对象传入"""
        store = GraphStore(store_path)
        
        # 先添加两个实体
        e1 = Entity(name="优优", entity_type=EntityType.PERSON)
        e2 = Entity(name="石榴籽", entity_type=EntityType.PROJECT)
        
        id1 = store.add_entity(e1)
        id2 = store.add_entity(e2)
        
        # 添加关系 - 使用 Relation 对象
        relation = Relation(
            source_entity_id=id1,
            target_entity_id=id2,
            relation_type=RelationType.WORKS_ON,
            properties={"role": "developer"}
        )
        relation_id = store.add_relation(relation)
        
        assert relation_id is not None
        assert len(relation_id) > 0
    
    def test_get_neighbors(self, store_path):
        """测试获取邻居实体"""
        store = GraphStore(store_path)
        
        e1 = Entity(name="A", entity_type=EntityType.PERSON)
        e2 = Entity(name="B", entity_type=EntityType.PERSON)
        e3 = Entity(name="C", entity_type=EntityType.PROJECT)
        
        id1 = store.add_entity(e1)
        id2 = store.add_entity(e2)
        id3 = store.add_entity(e3)
        
        # A -> C, B -> C
        store.add_relation(Relation(source_entity_id=id1, target_entity_id=id3, relation_type=RelationType.WORKS_ON))
        store.add_relation(Relation(source_entity_id=id2, target_entity_id=id3, relation_type=RelationType.WORKS_ON))
        
        # C 的邻居
        neighbors = store.get_neighbors(id3)
        assert len(neighbors) == 2
    
    def test_get_neighbors_empty(self, store_path):
        """测试无邻居的实体"""
        store = GraphStore(store_path)
        
        e = Entity(name="孤点", entity_type=EntityType.CONCEPT)
        entity_id = store.add_entity(e)
        
        neighbors = store.get_neighbors(entity_id)
        assert neighbors == []
    
    def test_find_entities(self, store_path):
        """测试搜索实体（v1.0 使用 find_entities - 精确匹配）"""
        store = GraphStore(store_path)
        
        store.add_entity(Entity(name="Alice", entity_type=EntityType.PERSON))
        store.add_entity(Entity(name="Bob", entity_type=EntityType.PERSON))
        store.add_entity(Entity(name="Charlie", entity_type=EntityType.PERSON))
        
        results = store.find_entities("Alice")
        assert len(results) == 1
        assert results[0].name == "Alice"
        
        # 精确匹配，不支持前缀
        results2 = store.find_entities("ali")  # 这不会匹配 "Alice"
        assert len(results2) == 0
    
    def test_find_entities_by_type(self, store_path):
        """测试按类型搜索实体（通过 find_entities 然后过滤）"""
        store = GraphStore(store_path)
        
        e1 = Entity(name="ProjectAlpha", entity_type=EntityType.PROJECT)
        e2 = Entity(name="ProjectBeta", entity_type=EntityType.PROJECT)
        e3 = Entity(name="PersonGamma", entity_type=EntityType.PERSON)
        
        store.add_entity(e1)
        store.add_entity(e2)
        store.add_entity(e3)
        
        # 使用精确匹配
        results = store.find_entities("ProjectAlpha")
        assert len(results) == 1
        assert results[0].entity_type == EntityType.PROJECT
        
        results2 = store.find_entities("ProjectBeta")
        assert len(results2) == 1
        assert results2[0].entity_type == EntityType.PROJECT
    
    def test_get_entity(self, store_path):
        """测试按 ID 获取实体"""
        store = GraphStore(store_path)
        
        e = Entity(name="测试实体", entity_type=EntityType.CONCEPT)
        entity_id = store.add_entity(e)
        
        retrieved = store.get_entity(entity_id)
        assert retrieved is not None
        assert retrieved.name == "测试实体"
    
    def test_remove_entity(self, store_path):
        """测试删除实体"""
        store = GraphStore(store_path)
        
        e = Entity(name="待删除", entity_type=EntityType.CONCEPT)
        entity_id = store.add_entity(e)
        
        store.remove_entity(entity_id)
        
        # 再次获取应该抛异常
        from L2_graph_store import EntityNotFoundError
        with pytest.raises(EntityNotFoundError):
            store.get_entity(entity_id)
    
    def test_remove_entity_with_relations(self, store_path):
        """测试删除带关系的实体"""
        store = GraphStore(store_path)
        
        e1 = Entity(name="A", entity_type=EntityType.PERSON)
        e2 = Entity(name="B", entity_type=EntityType.PROJECT)
        
        id1 = store.add_entity(e1)
        id2 = store.add_entity(e2)
        
        store.add_relation(Relation(source_entity_id=id1, target_entity_id=id2, relation_type=RelationType.WORKS_ON))
        
        # 删除 A
        store.remove_entity(id1)
        
        # B 仍然存在
        assert store.get_entity(id2).name == "B"
    
    def test_get_relations(self, store_path):
        """测试获取实体所有关系"""
        store = GraphStore(store_path)
        
        e1 = Entity(name="A", entity_type=EntityType.PERSON)
        e2 = Entity(name="B", entity_type=EntityType.PERSON)
        
        id1 = store.add_entity(e1)
        id2 = store.add_entity(e2)
        
        store.add_relation(Relation(source_entity_id=id1, target_entity_id=id2, relation_type=RelationType.KNOWS))
        
        relations = store.get_relations(id1)
        assert len(relations) == 1
    
    def test_find_path(self, store_path):
        """测试查找最短路径"""
        store = GraphStore(store_path)
        
        # A -> B -> C
        id_a = store.add_entity(Entity(name="A", entity_type=EntityType.CONCEPT))
        id_b = store.add_entity(Entity(name="B", entity_type=EntityType.CONCEPT))
        id_c = store.add_entity(Entity(name="C", entity_type=EntityType.CONCEPT))
        
        store.add_relation(Relation(source_entity_id=id_a, target_entity_id=id_b, relation_type=RelationType.KNOWS))
        store.add_relation(Relation(source_entity_id=id_b, target_entity_id=id_c, relation_type=RelationType.KNOWS))
        
        path = store.find_path(id_a, id_c)
        assert len(path) == 3
        assert path[0] == id_a
        assert path[-1] == id_c


class TestGraphStorePersistence:
    """图谱持久化测试"""
    
    @pytest.fixture
    def store_path(self):
        """创建临时图谱存储路径"""
        temp_dir = tempfile.mkdtemp()
        path = os.path.join(temp_dir, "persist_graph.json")
        yield path
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_save_and_load(self, store_path):
        """测试保存和加载"""
        # 创建并添加数据
        store1 = GraphStore(store_path)
        e = Entity(name="持久化测试", entity_type=EntityType.CONCEPT)
        entity_id = store1.add_entity(e)
        
        # 重新加载
        store2 = GraphStore(store_path)
        retrieved = store2.get_entity(entity_id)
        
        assert retrieved is not None
        assert retrieved.name == "持久化测试"
    
    def test_auto_save(self, store_path):
        """测试自动保存"""
        store = GraphStore(store_path)
        e = Entity(name="自动保存测试", entity_type=EntityType.CONCEPT)
        store.add_entity(e)
        
        # 确认文件已创建
        assert os.path.exists(store_path)


class TestGraphStoreEdgeCases:
    """图谱边界情况测试"""
    
    @pytest.fixture
    def store_path(self):
        """创建临时图谱存储路径"""
        temp_dir = tempfile.mkdtemp()
        path = os.path.join(temp_dir, "edge_graph.json")
        yield path
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_empty_graph(self, store_path):
        """测试空图谱"""
        store = GraphStore(store_path)
        
        assert store.get_entity_count() == {}
        assert store.find_entities("任意") == []
    
    def test_nonexistent_entity(self, store_path):
        """测试不存在的实体"""
        store = GraphStore(store_path)
        
        from L2_graph_store import EntityNotFoundError
        with pytest.raises(EntityNotFoundError):
            store.get_entity("nonexistent_id")
    
    def test_self_relation(self, store_path):
        """测试自引用关系"""
        store = GraphStore(store_path)
        
        entity = Entity(name="自引用实体", entity_type=EntityType.CONCEPT)
        entity_id = store.add_entity(entity)
        
        # 添加自引用关系
        relation = Relation(source_entity_id=entity_id, target_entity_id=entity_id, relation_type=RelationType.KNOWS)
        relation_id = store.add_relation(relation)
        
        assert relation_id is not None
    
    def test_unicode_entities(self, store_path):
        """测试 Unicode 实体名称"""
        store = GraphStore(store_path)
        
        store.add_entity(Entity(name="UserOne", entity_type=EntityType.PERSON))
        store.add_entity(Entity(name="TestProject", entity_type=EntityType.PROJECT))
        
        results = store.find_entities("UserOne")
        assert len(results) >= 1
    
    def test_large_properties(self, store_path):
        """测试大属性"""
        store = GraphStore(store_path)
        
        large_prop = {"key": "x" * 10000}
        entity = Entity(name="大属性实体", entity_type=EntityType.CONCEPT, properties=large_prop)
        entity_id = store.add_entity(entity)
        
        retrieved = store.get_entity(entity_id)
        assert len(retrieved.properties["key"]) == 10000
    
    def test_find_path_no_path(self, store_path):
        """测试无路径情况"""
        store = GraphStore(store_path)
        
        id_a = store.add_entity(Entity(name="A", entity_type=EntityType.CONCEPT))
        id_b = store.add_entity(Entity(name="B", entity_type=EntityType.CONCEPT))
        
        # A 和 B 没有连接
        path = store.find_path(id_a, id_b)
        assert path == []
    
    def test_merge_entities(self, store_path):
        """测试合并实体"""
        store = GraphStore(store_path)
        
        e1 = Entity(name="源", entity_type=EntityType.CONCEPT, properties={"key1": "value1"})
        e2 = Entity(name="目标", entity_type=EntityType.CONCEPT, properties={"key2": "value2"})
        
        id1 = store.add_entity(e1)
        id2 = store.add_entity(e2)
        
        store.merge_entities(id1, id2)
        
        # 源应该被删除
        from L2_graph_store import EntityNotFoundError
        with pytest.raises(EntityNotFoundError):
            store.get_entity(id1)
        
        # 目标应该存在且 properties 合并
        merged = store.get_entity(id2)
        assert "key1" in merged.properties
        assert "key2" in merged.properties
