"""
HTTP REST API 集成测试

测试 FastAPI REST API 的各个端点。
"""

import pytest
import sys
import os
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../..", "src"))


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_mh():
    """创建 Mock MemoryHermes"""
    mh = MagicMock()
    mh.store = AsyncMock(return_value="mem_01AR8V9NZFYMPQKN3VXTYVZXX")
    mh.query = AsyncMock(return_value=[
        {"id": "mem_001", "content": "test memory", "score": 0.95, "layer": "l3_vector"},
        {"id": "mem_002", "content": "another memory", "score": 0.85, "layer": "l3_vector"},
    ])
    mh.forget = AsyncMock(return_value=True)
    mh.get_stats = MagicMock(return_value={
        "vector": {"total": 100},
        "layers": {"l1_compress": True, "l2_graph": True, "l3_vector": True, "l4_files": True},
        "archive": {"count": 5},
    })
    mh.on_session_end = AsyncMock()
    mh.run_decay_check = AsyncMock(return_value={"forgotten": 2, "archived": 1})
    return mh


@pytest.fixture
def api_client(mock_mh):
    """创建测试 API 客户端"""
    from fastapi.testclient import TestClient
    from api.app import create_app

    # Patch get_mh to return our mock
    with patch("api.app.MemoryHermes", return_value=mock_mh):
        app = create_app()
        # Override internal state
        app.state._mh = mock_mh
        client = TestClient(app)
        yield client


# ============================================================================
# Health Check Tests
# ============================================================================


def test_health_check(api_client):
    """测试健康检查端点"""
    response = api_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


# ============================================================================
# Memory Store Tests
# ============================================================================


def test_store_memory_success(api_client, mock_mh):
    """测试存储记忆成功"""
    response = api_client.post(
        "/v1/memories",
        json={"content": "Test memory content", "importance": 0.8}
    )
    assert response.status_code == 201
    data = response.json()
    assert "memory_id" in data
    assert "ulid" in data


def test_store_memory_with_metadata(api_client):
    """测试带元数据存储记忆"""
    response = api_client.post(
        "/v1/memories",
        json={
            "content": "Test memory",
            "importance": 0.7,
            "metadata": {"source": "test", "tags": ["api"]}
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert "memory_id" in data


def test_store_memory_empty_content(api_client):
    """测试空内容请求"""
    response = api_client.post(
        "/v1/memories",
        json={"content": ""}
    )
    assert response.status_code == 422  # Validation error


def test_store_memory_invalid_importance(api_client):
    """测试无效重要性值"""
    response = api_client.post(
        "/v1/memories",
        json={"content": "Test", "importance": 1.5}
    )
    assert response.status_code == 422  # Validation error


# ============================================================================
# Memory Query Tests
# ============================================================================


def test_query_memories_success(api_client):
    """测试查询记忆成功"""
    response = api_client.get("/v1/memories?query=test&limit=5")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data


def test_query_memories_default_limit(api_client):
    """测试默认查询限制"""
    response = api_client.get("/v1/memories?query=test")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data


# ============================================================================
# Stats Tests
# ============================================================================


def test_get_stats_success(api_client):
    """测试获取统计信息"""
    response = api_client.get("/v1/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "by_layer" in data
    assert "decay_threshold" in data
    assert "archive_count" in data


# ============================================================================
# Session End Tests
# ============================================================================


def test_session_end_success(api_client, mock_mh):
    """测试会话结束"""
    response = api_client.post("/v1/session/end", json={"summary": "Test session"})
    assert response.status_code == 200
    data = response.json()
    assert "stored" in data
    assert "archived" in data
    assert "stats" in data


def test_session_end_no_summary(api_client, mock_mh):
    """测试不带摘要的会话结束"""
    response = api_client.post("/v1/session/end", json={})
    assert response.status_code == 200
    data = response.json()
    assert "stored" in data


# ============================================================================
# Decay Tests
# ============================================================================


def test_run_decay_success(api_client):
    """测试运行遗忘检查"""
    response = api_client.post("/v1/decay")
    assert response.status_code == 200
    data = response.json()
    assert "forgotten" in data
    assert "archived" in data
    assert "remaining" in data
