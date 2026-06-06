"""
<<<<<<< HEAD
pytest 配置和共享 fixtures
"""

import pytest
import sys
import os
import tempfile
import shutil
import copy
from pathlib import Path

# 添加 src 到 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture(autouse=True)
def reset_config():
    """每个测试前重置全局配置"""
    import importlib
    from config import DEFAULT_CONFIG
    
    # 保存原始默认配置的深拷贝
    original_default = copy.deepcopy(DEFAULT_CONFIG)
    
    # 重置全局配置
    import config
    if hasattr(config, '_config'):
        config._config = None
    
    yield
    
    # 测试后恢复默认配置
    DEFAULT_CONFIG.clear()
    DEFAULT_CONFIG.update(original_default)
    if hasattr(config, '_config'):
        config._config = None


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
    
=======
共享测试 fixtures
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Generator, Any
from unittest.mock import MagicMock, AsyncMock, patch
import pytest

# 确保 src 在 sys.path 中
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


@pytest.fixture
def tmp_memory_dir(tmp_path) -> Path:
    """创建临时记忆目录"""
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    return memory_dir


@pytest.fixture
def tmp_data_dir(tmp_path) -> Path:
    """创建临时数据目录"""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def mock_embedder():
    """Mock Embedder - 不依赖真实 API Key"""
    mock = MagicMock()
    mock.embed = MagicMock(return_value=[0.1] * 1024)
    mock.embed_batch = MagicMock(side_effect=lambda texts: [[0.1] * 1024 for _ in texts])
    mock.dim = 1024
    return mock


@pytest.fixture
def mock_dashscope_embedder(mock_embedder):
    """Mock DashScope Embedder"""
    with patch("src.L3_vector_store.DashScopeEmbedder", return_value=mock_embedder):
        yield mock_embedder


@pytest.fixture
def sample_memory() -> dict:
    """示例记忆数据"""
    return {
        "content": "测试记忆内容",
        "metadata": {
            "source": "test",
            "importance": 0.8,
            "tags": ["test", "sample"],
            "fact_type": "general"
        }
    }


@pytest.fixture
def sample_memories() -> list[dict]:
    """多个示例记忆"""
    return [
        {
            "content": "用户参加石榴籽省赛",
            "metadata": {"importance": 0.9, "tags": ["比赛", "石榴籽"], "fact_type": "event"}
        },
        {
            "content": "用户喜欢用 VSCode 写代码",
            "metadata": {"importance": 0.7, "tags": ["工具", "偏好"], "fact_type": "preference"}
        },
        {
            "content": "决定使用 LanceDB 作为向量存储",
            "metadata": {"importance": 0.8, "tags": ["决策", "技术"], "fact_type": "decision"}
        },
    ]


@pytest.fixture
def temp_config_file(tmp_path) -> Path:
    """创建临时配置文件"""
    config_path = tmp_path / "config.json"
    config = {
        "storage": {
            "data_dir": "data",
            "memory_dir": "memory"
        },
        "embedding": {
            "model": "text-embedding-v3",
            "dimensions": 1024
        }
    }
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f)
>>>>>>> daa3482 (feat: v0.3 - simplify to 3-layer architecture (L4/L3/L1))
    return config_path


@pytest.fixture
<<<<<<< HEAD
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
=======
def hash_embedder():
    """创建 HashEmbedder 用于确定性测试"""
    from src.L3_vector_store import HashEmbedder
    return HashEmbedder(dim=128)


@pytest.fixture
def isolated_store(tmp_path, mock_embedder):
    """创建完全隔离的 VectorStore 实例"""
    from src.L3_vector_store import VectorStore, BM25Indexer
    data_path = tmp_path / "vectors.json"
    store = VectorStore.__new__(VectorStore)
    store.storage_path = str(data_path)
    store.embedder = mock_embedder
    store.data = {"vectors": [], "metadata": {}}
    store._lock = MagicMock()
    return store
>>>>>>> daa3482 (feat: v0.3 - simplify to 3-layer architecture (L4/L3/L1))
