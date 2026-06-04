"""
L2_graph_store.py 单元测试
"""

import pytest
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../..", "src"))

from L2_graph_store import GraphStore, Entity, EntityType, RelationType, Relation


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
        assert EntityType.EVENT.value == "EVENT"
        assert EntityType.OTHER.value == "OTHER"
    
    def test_entity_default_properties(self):
        """测试实体默认属性"""
        entity = Entity(name="测试实体", entity_type=EntityType.OTHER)
        
        assert entity.properties == {}


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
        assert RelationType.WORKS_ON.value == "WORKS_ON"
        assert RelationType.PARTICIPATES_IN.value == "PARTICIPATES_IN"
        assert RelationType.CREATES.value == "CREATES"
        assert RelationType.HAS_GOAL.value == "HAS_GOAL"
        assert RelationType.KNOWS.value == "KNOWS"
        assert RelationType.RELATED_TO.value == "RELATED_TO"


class TestGraphStore:
    """GraphStore 图谱存储测试"""
    
    def test_graph_store_init(self, temp_dir):
        """测试图谱存储初始化"""
        graph_path = os.path.join(temp_dir, "test_graph.json")
        store = GraphStore(graph_path)
        
        assert store.graph_path == graph_path
        assert store.get_entity_count() == {"total": 0}
    
    def test_add_entity(self, temp_dir):
        """测试添加实体"""
        graph_path = os.path.join(temp_dir, "test_graph.json")
        store = GraphStore(graph_path)
        
        entity = Entity(name="石榴籽", entity_type=EntityType.PROJECT, properties={"category": "AI翻译"})
        entity_id = store.add_entity(entity)
        
        assert entity_id is not None
        assert entity_id.startswith("ent_")
        
        # 验证实体数量增加
        counts = store.get_entity_count()
        assert counts["PROJECT"] == 1
    
    def test_add_multiple_entities(self, temp_dir):
        """测试添加多个实体"""
        graph_path = os.path.join(temp_dir, "test_graph.json")
        store = GraphStore(graph_path)
        
        e1 = Entity(name="优优", entity_type=EntityType.PERSON)
        e2 = Entity(name="石榴籽", entity_type=EntityType.PROJECT)
        e3 = Entity(name="AI", entity_type=EntityType.CONCEPT)
        
        id1 = store.add_entity(e1)
        id2 = store.add_entity(e2)
        id3 = store.add_entity(e3)
        
        assert id1 != id2 != id3
        assert store.get_entity_count()["total"] == 3
    
    def test_add_relation(self, temp_dir):
        """测试添加关系"""
        graph_path = os.path.join(temp_dir, "test_graph.json")
        store = GraphStore(graph_path)
        
        # 先添加两个实体
        e1 = Entity(name="优优", entity_type=EntityType.PERSON)
        e2 = Entity(name="石榴籽", entity_type=EntityType.PROJECT)
        
        id1 = store.add_entity(e1)
        id2 = store.add_entity(e2)
        
        # 添加关系
        relation = Relation(
            source_entity_id=id1,
            target_entity_id=id2,
            relation_type=RelationType.WORKS_ON
        )
        
        relation_id = store.add_relation(relation)
        assert relation_id is not None
        assert relation_id.startswith("rel_")
    
    def test_get_neighbors(self, temp_dir):
        """测试获取邻居实体"""
        graph_path = os.path.join(temp_dir, "test_graph.json")
        store = GraphStore(graph_path)
        
        # 创建实体和关系
        e1 = Entity(name="优优", entity_type=EntityType.PERSON)
        e2 = Entity(name="石榴籽", entity_type=EntityType.PROJECT)
        e3 = Entity(name="团队", entity_type=EntityType.ORGANIZATION)
        
        id1 = store.add_entity(e1)
        id2 = store.add_entity(e2)
        id3 = store.add_entity(e3)
        
        store.add_relation(Relation(id1, id2, RelationType.WORKS_ON))
        store.add_relation(Relation(id1, id3, RelationType.PART_OF))
        
        # 获取优优的邻居
        neighbors = store.get_neighbors(id1)
        
        assert len(neighbors) == 2
        neighbor_names = [n.name for n in neighbors]
        assert "石榴籽" in neighbor_names
        assert "团队" in neighbor_names
    
    def test_get_neighbors_empty(self, temp_dir):
        """测试获取无邻居的实体"""
        graph_path = os.path.join(temp_dir, "test_graph.json")
        store = GraphStore(graph_path)
        
        entity = Entity(name="孤立实体", entity_type=EntityType.OTHER)
        entity_id = store.add_entity(entity)
        
        neighbors = store.get_neighbors(entity_id)
        assert len(neighbors) == 0
    
    def test_search_entities(self, temp_dir):
        """测试搜索实体"""
        graph_path = os.path.join(temp_dir, "test_graph.json")
        store = GraphStore(graph_path)
        
        # 添加多个实体
        store.add_entity(Entity(name="优优", entity_type=EntityType.PERSON))
        store.add_entity(Entity(name="优优的朋友", entity_type=EntityType.PERSON))
        store.add_entity(Entity(name="石榴籽项目", entity_type=EntityType.PROJECT))
        store.add_entity(Entity(name="其他", entity_type=EntityType.OTHER))
        
        # 搜索名称包含"优优"的实体
        results = store.search_entities("优优")
        
        assert len(results) >= 2
        names = [e.name for e in results]
        assert "优优" in names
        assert "优优的朋友" in names
    
    def test_search_entities_by_type(self, temp_dir):
        """测试按类型搜索实体"""
        graph_path = os.path.join(temp_dir, "test_graph.json")
        store = GraphStore(graph_path)
        
        store.add_entity(Entity(name="优优", entity_type=EntityType.PERSON))
        store.add_entity(Entity(name="小李", entity_type=EntityType.PERSON))
        store.add_entity(Entity(name="石榴籽", entity_type=EntityType.PROJECT))
        
        person_results = store.search_entities("", entity_type=EntityType.PERSON)
        
        assert len(person_results) == 2
        for entity in person_results:
            assert entity.entity_type == EntityType.PERSON
    
    def test_get_entity_by_id(self, temp_dir):
        """测试按 ID 获取实体"""
        graph_path = os.path.join(temp_dir, "test_graph.json")
        store = GraphStore(graph_path)
        
        original = Entity(name="测试实体", entity_type=EntityType.CONCEPT, properties={"key": "value"})
        entity_id = store.add_entity(original)
        
        retrieved = store.get_entity_by_id(entity_id)
        
        assert retrieved is not None
        assert retrieved.name == "测试实体"
        assert retrieved.entity_type == EntityType.CONCEPT
    
    def test_update_entity(self, temp_dir):
        """测试更新实体"""
        graph_path = os.path.join(temp_dir, "test_graph.json")
        store = GraphStore(graph_path)
        
        entity = Entity(name="原名称", entity_type=EntityType.PERSON)
        entity_id = store.add_entity(entity)
        
        # 更新实体
        success = store.update_entity(entity_id, name="新名称", properties={"updated": True})
        assert success == True
        
        updated = store.get_entity_by_id(entity_id)
        assert updated.name == "新名称"
        assert updated.properties["updated"] == True
    
    def test_delete_entity(self, temp_dir):
        """测试删除实体"""
        graph_path = os.path.join(temp_dir, "test_graph.json")
        store = GraphStore(graph_path)
        
        entity = Entity(name="待删除实体", entity_type=EntityType.OTHER)
        entity_id = store.add_entity(entity)
        
        assert store.get_entity_count()["total"] == 1
        
        success = store.delete_entity(entity_id)
        assert success == True
        assert store.get_entity_count()["total"] == 0
    
    def test_delete_entity_with_relations(self, temp_dir):
        """测试删除有关联关系的实体"""
        graph_path = os.path.join(temp_dir, "test_graph.json")
        store = GraphStore(graph_path)
        
        e1 = Entity(name="实体1", entity_type=EntityType.PERSON)
        e2 = Entity(name="实体2", entity_type=EntityType.PROJECT)
        
        id1 = store.add_entity(e1)
        id2 = store.add_entity(e2)
        
        store.add_relation(Relation(id1, id2, RelationType.WORKS_ON))
        
        # 删除实体1
        store.delete_entity(id1)
        
        # 实体2应该仍然存在
        assert store.get_entity_by_id(id2) is not None
    
    def test_get_relation_count(self, temp_dir):
        """测试获取关系数量"""
        graph_path = os.path.join(temp_dir, "test_graph.json")
        store = GraphStore(graph_path)
        
        e1 = Entity(name="A", entity_type=EntityType.PERSON)
        e2 = Entity(name="B", entity_type=EntityType.PROJECT)
        e3 = Entity(name="C", entity_type=EntityType.OTHER)
        
        id1 = store.add_entity(e1)
        id2 = store.add_entity(e2)
        id3 = store.add_entity(e3)
        
        store.add_relation(Relation(id1, id2, RelationType.WORKS_ON))
        store.add_relation(Relation(id1, id3, RelationType.KNOWS))
        
        assert store.get_relation_count() == 2
    
    def test_shortest_path(self, temp_dir):
        """测试最短路径查询"""
        graph_path = os.path.join(temp_dir, "test_graph.json")
        store = GraphStore(graph_path)
        
        # 创建链式关系: A -> B -> C -> D
        entities = []
        for i, name in enumerate(["A", "B", "C", "D"]):
            e = Entity(name=name, entity_type=EntityType.OTHER)
            entities.append(store.add_entity(e))
        
        for i in range(len(entities) - 1):
            store.add_relation(Relation(entities[i], entities[i+1], RelationType.RELATED_TO))
        
        # 查找 A 到 D 的最短路径
        path = store.shortest_path(entities[0], entities[3])
        
        assert path is not None
        assert len(path) >= 2  # 至少包含起点和终点
    
    def test_merge_entities(self, temp_dir):
        """测试实体合并"""
        graph_path = os.path.join(temp_dir, "test_graph.json")
        store = GraphStore(graph_path)
        
        e1 = Entity(name="优优", entity_type=EntityType.PERSON, properties={"alias": "UU"})
        e2 = Entity(name="UU", entity_type=EntityType.PERSON, properties={"note": "同一人"})
        
        id1 = store.add_entity(e1)
        id2 = store.add_entity(e2)
        
        merged_id = store.merge_entities(id1, id2)
        
        assert merged_id == id1
        assert store.get_entity_count()["PERSON"] == 1


class TestGraphStorePersistence:
    """GraphStore 持久化测试"""
    
    def test_save_and_load(self, temp_dir):
        """测试保存和加载"""
        graph_path = os.path.join(temp_dir, "persist_graph.json")
        
        # 创建并保存
        store1 = GraphStore(graph_path)
        store1.add_entity(Entity(name="持久化测试", entity_type=EntityType.CONCEPT))
        store1.save()
        
        # 重新加载
        store2 = GraphStore(graph_path)
        
        entities = store2.search_entities("持久化测试")
        assert len(entities) == 1
        assert entities[0].name == "持久化测试"
    
    def test_auto_save(self, temp_dir):
        """测试自动保存"""
        graph_path = os.path.join(temp_dir, "auto_save.json")
        store = GraphStore(graph_path)
        
        store.add_entity(Entity(name="自动保存测试", entity_type=EntityType.OTHER))
        
        # 重新加载验证
        store2 = GraphStore(graph_path)
        entities = store2.search_entities("自动保存测试")
        
        assert len(entities) == 1


class TestGraphStoreEdgeCases:
    """GraphStore 边界情况测试"""
    
    def test_empty_graph(self, temp_dir):
        """测试空图"""
        graph_path = os.path.join(temp_dir, "empty.json")
        store = GraphStore(graph_path)
        
        assert store.get_entity_count()["total"] == 0
        assert store.get_relation_count() == 0
        assert len(store.get_neighbors("nonexistent")) == 0
    
    def test_nonexistent_entity(self, temp_dir):
        """测试不存在的实体"""
        graph_path = os.path.join(temp_dir, "nonexistent.json")
        store = GraphStore(graph_path)
        
        assert store.get_entity_by_id("nonexistent_id") is None
    
    def test_self_relation(self, temp_dir):
        """测试自引用关系"""
        graph_path = os.path.join(temp_dir, "self_ref.json")
        store = GraphStore(graph_path)
        
        entity = Entity(name="自引用实体", entity_type=EntityType.CONCEPT)
        entity_id = store.add_entity(entity)
        
        # 添加自引用关系
        relation = Relation(entity_id, entity_id, RelationType.RELATED_TO)
        relation_id = store.add_relation(relation)
        
        assert relation_id is not None
    
    def test_unicode_entities(self, temp_dir):
        """测试 Unicode 实体名称"""
        graph_path = os.path.join(temp_dir, "unicode.json")
        store = GraphStore(graph_path)
        
        store.add_entity(Entity(name="优优", entity_type=EntityType.PERSON))
        store.add_entity(Entity(name="石榴籽项目", entity_type=EntityType.PROJECT))
        store.add_entity(Entity(name="测试emoji😀", entity_type=EntityType.OTHER))
        
        assert store.get_entity_count()["total"] == 3
    
    def test_large_properties(self, temp_dir):
        """测试大属性"""
        graph_path = os.path.join(temp_dir, "large_props.json")
        store = GraphStore(graph_path)
        
        large_prop = {"key": "x" * 10000}
        entity = Entity(name="大属性实体", entity_type=EntityType.OTHER, properties=large_prop)
        entity_id = store.add_entity(entity)
        
        retrieved = store.get_entity_by_id(entity_id)
        assert len(retrieved.properties["key"]) == 10000
