"""
HTTP REST API 集成测试 (v2.1.0)

测试 FastAPI REST API 的各个端点。
2026-07-15: 适配新 MemoryManager API,移除 MemoryHermes mock
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
def mock_mm():
    """创建 Mock MemoryManager (v2.1.0)"""
    mm = MagicMock()
    # MemoryHermes.store(content, metadata, importance)
    #   → MemoryManager.add(content, importance, category_path, tags, source)
    mm.add = AsyncMock(return_value="mem_01AR8V9NZFYMPQKN3VXTYVZXX")
    # MemoryHermes.query(query, limit) → MemoryManager.search(query, limit)
    mm.search = AsyncMock(return_value=[
        {"id": "mem_001", "content": "test memory", "score": 0.95, "layer": "l3_vector"},
        {"id": "mem_002", "content": "another memory", "score": 0.85, "layer": "l3_vector"},
    ])
    # MemoryHermes.forget(mid, permanent=True) → MemoryManager.delete(mid)
    mm.delete = AsyncMock(return_value=True)
    # MemoryHermes.get_stats() (sync) → await mm.stats() (async)
    mm.stats = AsyncMock(return_value={
        "total": 100,
        "layers": {"l1_compress": True, "l2_graph": True, "l3_vector": True, "l4_files": True},
        "archive_count": 5,
    })
    # on_session_end / run_decay_check 已移除(2026-07-15)
    # endpoint 改为 stub 返回,不需要 mock
    return mm


@pytest.fixture
def api_client(mock_mm):
    """创建测试 API 客户端"""
    from fastapi.testclient import TestClient
    from api.app import create_app

    # Patch get_mm to return our mock
    with patch("api.app.MemoryManager", return_value=mock_mm):
        app = create_app()
        # Override internal state to short-circuit lazy init
        app.state._mm = mock_mm
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


def test_store_memory_success(api_client, mock_mm):
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
# Session End Tests (2026-07-15: stub,但 schema 兼容)
# ============================================================================


def test_session_end_success(api_client, mock_mm):
    """测试会话结束 — v2.1.0 改为 stub, schema 仍兼容"""
    response = api_client.post("/v1/session/end", json={"summary": "Test session"})
    assert response.status_code == 200
    data = response.json()
    assert "stored" in data
    assert "archived" in data
    assert "stats" in data


def test_session_end_no_summary(api_client, mock_mm):
    """测试不带摘要的会话结束"""
    response = api_client.post("/v1/session/end", json={})
    assert response.status_code == 200
    data = response.json()
    assert "stored" in data


# ============================================================================
# Decay Tests (2026-07-15: stub)
# ============================================================================


def test_run_decay_success(api_client):
    """测试运行遗忘检查 — v2.1.0 改为 stub"""
    response = api_client.post("/v1/decay")
    assert response.status_code == 200
    data = response.json()
    assert "forgotten" in data
    assert "archived" in data
    assert "remaining" in data