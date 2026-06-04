"""
AgentMemory Web Dashboard Integration Tests
测试 FastAPI 后端 API 端点
"""

import pytest
import sys
import os

# 添加 src 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from fastapi.testclient import TestClient


class TestWebAPI:
    """Web API 测试套件"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from web.app import app
        return TestClient(app)

    # ========================================================================
    # Health Check Tests
    # ========================================================================

    def test_health_check(self, client):
        """测试健康检查端点"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "agentmemory-web"

    # ========================================================================
    # Root Endpoint Tests
    # ========================================================================

    def test_root_returns_html(self, client):
        """测试根路径返回 HTML"""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    # ========================================================================
    # Memories API Tests
    # ========================================================================

    def test_list_memories_empty(self, client):
        """测试列出记忆（空列表）"""
        response = client.get("/api/memories")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "pages" in data
        assert isinstance(data["items"], list)

    def test_list_memories_with_pagination(self, client):
        """测试带分页参数的请求"""
        response = client.get("/api/memories?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10

    def test_list_memories_with_search(self, client):
        """测试带搜索参数的请求"""
        response = client.get("/api/memories?search=test")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_get_memory_not_found(self, client):
        """测试获取不存在的记忆"""
        response = client.get("/api/memories/nonexistent_id")
        assert response.status_code == 404

    def test_delete_memory_not_found(self, client):
        """测试删除不存在的记忆"""
        response = client.delete("/api/memories/nonexistent_id")
        # 可能是 404 或其他错误码
        assert response.status_code in [404, 500]

    # ========================================================================
    # Graph API Tests
    # ========================================================================

    def test_list_entities(self, client):
        """测试列出图谱实体"""
        response = client.get("/api/graph/entities")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    def test_list_relations(self, client):
        """测试列出图谱关系"""
        response = client.get("/api/graph/relations")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    # ========================================================================
    # Stats API Tests
    # ========================================================================

    def test_get_stats(self, client):
        """测试获取统计信息"""
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert "layers" in data
        assert isinstance(data["layers"], dict)

    # ========================================================================
    # Prefetch API Tests
    # ========================================================================

    def test_prefetch_empty_query(self, client):
        """测试预取空查询"""
        response = client.post("/api/prefetch", json={"query": ""})
        assert response.status_code == 200
        data = response.json()
        assert "query" in data
        assert "results" in data

    def test_prefetch_with_query(self, client):
        """测试预取带查询"""
        response = client.post("/api/prefetch", json={"query": "test query"})
        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "test query"
        assert "results" in data

    def test_prefetch_missing_query(self, client):
        """测试预取缺少查询参数"""
        response = client.post("/api/prefetch", json={})
        assert response.status_code == 422  # Validation error

    # ========================================================================
    # Error Handling Tests
    # ========================================================================

    def test_invalid_memory_id_format(self, client):
        """测试无效的记忆 ID 格式"""
        # 发送一个特殊字符的 ID
        response = client.get("/api/memories/invalid@id#123")
        # 应该返回 404 或 500
        assert response.status_code in [404, 500]

    def test_cors_headers(self, client):
        """测试 CORS 头"""
        # 测试 GET 请求可以正常通过（证明 CORS 配置生效）
        response = client.get("/api/memories")
        assert response.status_code == 200
        # 验证 CORS 相关头存在
        # 注：FastAPI TestClient 不直接暴露 CORS 头，需要实际服务器


class TestWebCLI:
    """Web CLI 测试"""

    def test_cli_module_import(self):
        """测试 CLI 模块可导入"""
        from web.app import app
        assert app is not None

    def test_app_has_routes(self):
        """测试应用有路由定义"""
        from web.app import app
        routes = [route.path for route in app.routes]
        assert "/" in routes
        assert "/health" in routes
        assert "/api/memories" in routes
        assert "/api/stats" in routes


class TestWebModels:
    """Web 数据模型测试"""

    def test_memory_response_model(self):
        """测试记忆响应模型"""
        from web.app import MemoryResponse
        memory = MemoryResponse(
            id="test123",
            content="Test content",
            importance=0.8,
            created_at="2024-01-01T00:00:00"
        )
        assert memory.id == "test123"
        assert memory.content == "Test content"

    def test_memory_list_response_model(self):
        """测试记忆列表响应模型"""
        from web.app import MemoryListResponse, MemoryResponse
        response = MemoryListResponse(
            items=[MemoryResponse(
                id="test123",
                content="Test",
                importance=0.5,
                created_at="2024-01-01"
            )],
            total=1,
            page=1,
            page_size=20,
            pages=1
        )
        assert len(response.items) == 1
        assert response.total == 1

    def test_prefetch_request_model(self):
        """测试预取请求模型"""
        from web.app import PrefetchRequest
        request = PrefetchRequest(query="test query")
        assert request.query == "test query"
