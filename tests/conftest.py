"""
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
    return config_path


@pytest.fixture
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
