"""
pytest 配置和共享 fixtures
"""

import pytest
import sys
import os
import tempfile
import shutil
from pathlib import Path

# 添加 src 到 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def temp_dir():
    """创建临时目录用于测试"""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def mock_config(temp_dir):
    """创建测试用配置"""
    config_path = os.path.join(temp_dir, "config.json")
    config_content = {
        "embedding": {
            "provider": "mock",
            "model": "text-embedding-mock",
            "dimensions": 1024
        },
        "llm": {
            "provider": "mock",
            "model": "mock-model"
        },
        "decay": {
            "enabled": True,
            "threshold": 0.3,
            "half_life_days": 14.0
        },
        "hybrid_search": {
            "vector_weight": 0.6,
            "bm25_weight": 0.3,
            "importance_weight": 0.1
        },
        "storage": {
            "base_path": temp_dir
        }
    }
    
    import json
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config_content, f, indent=2)
    
    return config_path


@pytest.fixture
def sample_memory_entry():
    """示例记忆条目"""
    return {
        "id": "mem_test_001",
        "content": "用户喜欢简洁的回复风格",
        "metadata": {
            "source": "test",
            "category": "preference"
        },
        "importance": 0.8,
        "entities": ["用户"],
        "tags": ["preference", "style"]
    }


@pytest.fixture
def sample_fact():
    """示例事实"""
    return {
        "id": "fac_test_001",
        "content": "石榴籽项目省赛结果需要等待几天",
        "fact_type": "project_status",
        "entities": ["石榴籽", "省赛"],
        "confidence": 0.95
    }


@pytest.fixture
def sample_entities():
    """示例实体列表"""
    return [
        {
            "id": "ent_test_001",
            "name": "优优",
            "entity_type": "PERSON",
            "properties": {"role": "学生", "grade": "高三"}
        },
        {
            "id": "ent_test_002",
            "name": "石榴籽",
            "entity_type": "PROJECT",
            "properties": {"category": "AI翻译", "status": "进行中"}
        }
    ]


@pytest.fixture
def sample_relations():
    """示例关系列表"""
    return [
        {
            "id": "rel_test_001",
            "source_entity_id": "ent_test_001",
            "target_entity_id": "ent_test_002",
            "relation_type": "WORKS_ON",
            "properties": {}
        }
    ]
