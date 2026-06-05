"""
测试多 Agent 权限模型

pytest agentmemory/tests/test_permissions.py
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from datetime import datetime, timezone

from agentmemory.multi_agent.permissions import (
    AgentPermission,
    PermissionContext,
    PermissionEngine,
)


@pytest.fixture
def tmp_path():
    """创建临时目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def engine(tmp_path):
    """创建权限引擎实例"""
    return PermissionEngine(tmp_path)


# ============================================================================
# AgentPermission 数据类测试
# ============================================================================

def test_agent_permission_creation():
    """测试 AgentPermission 创建"""
    perm = AgentPermission(
        agent_id="test_agent",
        allowed_paths=["A.项目/**", "B.个人/**"],
        read_only_paths=["Z.归档/**"],
        denied_paths=["C.私有/**"],
        max_write_per_day=500,
    )
    
    assert perm.agent_id == "test_agent"
    assert len(perm.allowed_paths) == 2
    assert len(perm.read_only_paths) == 1
    assert len(perm.denied_paths) == 1
    assert perm.max_write_per_day == 500
    assert perm.created_at != ""


def test_agent_permission_to_dict():
    """测试 AgentPermission 序列化"""
    perm = AgentPermission(
        agent_id="test_agent",
        allowed_paths=["A.项目/**"],
    )
    
    d = perm.to_dict()
    assert d["agent_id"] == "test_agent"
    assert d["allowed_paths"] == ["A.项目/**"]


def test_agent_permission_from_dict():
    """测试 AgentPermission 反序列化"""
    data = {
        "agent_id": "test_agent",
        "allowed_paths": ["A.项目/**"],
        "read_only_paths": [],
        "denied_paths": [],
        "max_write_per_day": 1000,
        "created_at": "2026-06-05T12:00:00+00:00",
    }
    
    perm = AgentPermission.from_dict(data)
    assert perm.agent_id == "test_agent"
    assert perm.allowed_paths == ["A.项目/**"]


# ============================================================================
# PermissionEngine 注册测试
# ============================================================================

@pytest.mark.asyncio
async def test_permission_register(engine):
    """测试注册新 Agent"""
    perm = await engine.register("agent_alice", ["A.项目/**"])
    
    assert perm.agent_id == "agent_alice"
    assert "A.项目/**" in perm.allowed_paths


@pytest.mark.asyncio
async def test_permission_register_with_defaults(engine):
    """测试注册 Agent 使用默认权限"""
    perm = await engine.register("agent_bob")
    
    assert perm.agent_id == "agent_bob"
    assert perm.allowed_paths == []
    assert perm.read_only_paths == []
    assert perm.denied_paths == []


@pytest.mark.asyncio
async def test_permission_get(engine):
    """测试获取 Agent 权限"""
    await engine.register("agent_alice", ["A.项目/**"])
    
    perm = await engine.get("agent_alice")
    assert perm is not None
    assert perm.agent_id == "agent_alice"


@pytest.mark.asyncio
async def test_permission_get_not_found(engine):
    """测试获取不存在的 Agent"""
    perm = await engine.get("nonexistent_agent")
    assert perm is None


@pytest.mark.asyncio
async def test_permission_unregister(engine):
    """测试注销 Agent"""
    await engine.register("agent_alice")
    
    result = await engine.unregister("agent_alice")
    assert result is True
    
    perm = await engine.get("agent_alice")
    assert perm is None


@pytest.mark.asyncio
async def test_permission_unregister_not_found(engine):
    """测试注销不存在的 Agent"""
    result = await engine.unregister("nonexistent_agent")
    assert result is False


@pytest.mark.asyncio
async def test_permission_list_agents(engine):
    """测试列出所有 Agent"""
    await engine.register("agent_alice")
    await engine.register("agent_bob")
    
    agents = await engine.list_agents()
    assert "agent_alice" in agents
    assert "agent_bob" in agents


# ============================================================================
# PermissionEngine 权限授予/撤销测试
# ============================================================================

@pytest.mark.asyncio
async def test_permission_grant(engine):
    """测试授予路径权限"""
    await engine.register("agent_alice")
    
    await engine.grant("agent_alice", ["A.项目/**", "B.个人/**"])
    
    perm = await engine.get("agent_alice")
    assert "A.项目/**" in perm.allowed_paths
    assert "B.个人/**" in perm.allowed_paths


@pytest.mark.asyncio
async def test_permission_grant_append(engine):
    """测试授予权限是追加而非覆盖"""
    await engine.register("agent_alice", ["A.项目/**"])
    
    await engine.grant("agent_alice", ["B.个人/**"])
    
    perm = await engine.get("agent_alice")
    assert "A.项目/**" in perm.allowed_paths
    assert "B.个人/**" in perm.allowed_paths


@pytest.mark.asyncio
async def test_permission_revoke(engine):
    """测试撤销路径权限"""
    await engine.register("agent_alice", ["A.项目/**", "B.个人/**"])
    
    await engine.revoke("agent_alice", ["B.个人/**"])
    
    perm = await engine.get("agent_alice")
    assert "A.项目/**" in perm.allowed_paths
    assert "B.个人/**" not in perm.allowed_paths


# ============================================================================
# PermissionEngine 权限检查测试
# ============================================================================

@pytest.mark.asyncio
async def test_permission_check_grant(engine):
    """测试允许的读操作"""
    await engine.register("agent_alice", ["A.项目/**"])
    
    ctx = await engine.check("agent_alice", "read", "A.项目/石榴籽/mem_001.md")
    assert ctx.granted is True
    assert ctx.reason == "Access granted"


@pytest.mark.asyncio
async def test_permission_check_deny(engine):
    """测试拒绝未授权路径的写操作"""
    await engine.register("agent_alice", ["A.项目/**"])
    
    ctx = await engine.check("agent_alice", "write", "B.个人/日记/mem_001.md")
    assert ctx.granted is False
    assert ctx.reason == "Path not in allowed paths"


@pytest.mark.asyncio
async def test_permission_check_deny_not_registered(engine):
    """测试拒绝未注册的 Agent"""
    ctx = await engine.check("nonexistent_agent", "read", "A.项目/test.md")
    assert ctx.granted is False
    assert ctx.reason == "Agent not registered"


@pytest.mark.asyncio
async def test_permission_read_only(engine):
    """测试只读路径拒绝写操作"""
    await engine.register(
        "agent_alice",
        ["A.项目/**"],
        read_only_paths=["A.项目/归档/**"],
    )
    
    ctx = await engine.check("agent_alice", "write", "A.项目/归档/mem_001.md")
    assert ctx.granted is False
    assert ctx.reason == "Path is read-only"


@pytest.mark.asyncio
async def test_permission_read_only_allow_read(engine):
    """测试只读路径允许读操作"""
    await engine.register(
        "agent_alice",
        ["A.项目/**"],
        read_only_paths=["A.项目/归档/**"],
    )
    
    ctx = await engine.check("agent_alice", "read", "A.项目/归档/mem_001.md")
    assert ctx.granted is True


@pytest.mark.asyncio
async def test_permission_denied_path(engine):
    """测试显式拒绝的路径"""
    await engine.register(
        "agent_alice",
        ["A.项目/**", "B.个人/**"],
        denied_paths=["A.项目/私有/**"],
    )
    
    ctx = await engine.check("agent_alice", "read", "A.项目/私有/mem_001.md")
    assert ctx.granted is False
    assert ctx.reason == "Path explicitly denied"


@pytest.mark.asyncio
async def test_permission_denied_overrides_allowed(engine):
    """测试 denied_paths 优先于 allowed_paths"""
    await engine.register(
        "agent_alice",
        ["A.项目/**"],
        denied_paths=["A.项目/石榴籽/**"],
    )
    
    # 虽然 A.项目/** 允许，但 A.项目/石榴籽/** 被显式拒绝
    ctx = await engine.check("agent_alice", "read", "A.项目/石榴籽/mem_001.md")
    assert ctx.granted is False
    assert ctx.reason == "Path explicitly denied"


@pytest.mark.asyncio
async def test_permission_check_delete_read_only(engine):
    """测试只读路径拒绝删除操作"""
    await engine.register(
        "agent_alice",
        ["A.项目/**"],
        read_only_paths=["A.项目/归档/**"],
    )
    
    ctx = await engine.check("agent_alice", "delete", "A.项目/归档/mem_001.md")
    assert ctx.granted is False
    assert ctx.reason == "Path is read-only"


# ============================================================================
# 路径匹配测试
# ============================================================================

@pytest.mark.asyncio
async def test_permission_path_exact_match(engine):
    """测试精确路径匹配"""
    await engine.register("agent_alice", ["A.项目/石榴籽"])
    
    # 精确匹配
    ctx = await engine.check("agent_alice", "read", "A.项目/石榴籽")
    assert ctx.granted is True


@pytest.mark.asyncio
async def test_permission_path_glob_single_level(engine):
    """测试单层通配符匹配"""
    await engine.register("agent_alice", ["A.项目/*"])
    
    # 应该匹配 A.项目/石榴籽
    ctx = await engine.check("agent_alice", "read", "A.项目/石榴籽")
    assert ctx.granted is True
    
    # 不应该匹配 A.项目/石榴籽/语料（双层）
    ctx = await engine.check("agent_alice", "read", "A.项目/石榴籽/语料")
    assert ctx.granted is False


@pytest.mark.asyncio
async def test_permission_path_glob_double_star(engine):
    """测试双层通配符匹配"""
    await engine.register("agent_alice", ["A.项目/**"])
    
    # 应该匹配 A.项目/石榴籽
    ctx = await engine.check("agent_alice", "read", "A.项目/石榴籽")
    assert ctx.granted is True
    
    # 应该匹配 A.项目/石榴籽/语料
    ctx = await engine.check("agent_alice", "read", "A.项目/石榴籽/语料")
    assert ctx.granted is True
    
    # 应该匹配更深层的路径
    ctx = await engine.check("agent_alice", "read", "A.项目/石榴籽/语料/xxx")
    assert ctx.granted is True


# ============================================================================
# is_path_visible 测试
# ============================================================================

@pytest.mark.asyncio
async def test_is_path_visible(engine):
    """测试快速路径可见性检查"""
    await engine.register("agent_alice", ["A.项目/**", "B.个人/**"])
    
    assert engine.is_path_visible("agent_alice", "A.项目/石榴籽") is True
    assert engine.is_path_visible("agent_alice", "B.个人/日记") is True
    assert engine.is_path_visible("agent_alice", "C.私有/数据") is False


@pytest.mark.asyncio
async def test_is_path_visible_denied(engine):
    """测试 is_path_visible 包含 denied 检查"""
    await engine.register(
        "agent_alice",
        ["A.项目/**"],
        denied_paths=["A.项目/私有/**"],
    )
    
    assert engine.is_path_visible("agent_alice", "A.项目/石榴籽") is True
    assert engine.is_path_visible("agent_alice", "A.项目/私有") is False


# ============================================================================
# list_allowed 测试
# ============================================================================

@pytest.mark.asyncio
async def test_list_allowed(engine):
    """测试列出允许的路径"""
    await engine.register("agent_alice", ["A.项目/**", "B.个人/**"])
    
    allowed = await engine.list_allowed("agent_alice")
    assert "A.项目/**" in allowed
    assert "B.个人/**" in allowed


@pytest.mark.asyncio
async def test_list_allowed_not_found(engine):
    """测试列出不存在 Agent 的允许路径"""
    allowed = await engine.list_allowed("nonexistent_agent")
    assert allowed == []


# ============================================================================
# 持久化测试
# ============================================================================

@pytest.mark.asyncio
async def test_permission_persistence(engine):
    """测试权限配置持久化"""
    await engine.register("agent_alice", ["A.项目/**"])
    await engine.grant("agent_alice", ["B.个人/**"])
    
    # 创建新的引擎实例加载数据
    new_engine = PermissionEngine(engine.storage_path)
    perm = await new_engine.get("agent_alice")
    
    assert perm is not None
    assert "A.项目/**" in perm.allowed_paths
    assert "B.个人/**" in perm.allowed_paths


# ============================================================================
# PermissionContext 测试
# ============================================================================

def test_permission_context():
    """测试 PermissionContext 数据类"""
    ctx = PermissionContext(
        agent_id="agent_alice",
        operation="read",
        target_path="A.项目/test.md",
        granted=True,
        reason="Access granted",
    )
    
    assert ctx.agent_id == "agent_alice"
    assert ctx.operation == "read"
    assert ctx.target_path == "A.项目/test.md"
    assert ctx.granted is True
    assert ctx.reason == "Access granted"


def test_permission_context_denied():
    """测试拒绝的 PermissionContext"""
    ctx = PermissionContext(
        agent_id="agent_alice",
        operation="write",
        target_path="A.项目/归档/test.md",
        granted=False,
        reason="Path is read-only",
    )
    
    assert ctx.granted is False
    assert ctx.reason == "Path is read-only"


# ============================================================================
# 集成测试
# ============================================================================

@pytest.mark.asyncio
async def test_multi_agent_permission_scenario(engine):
    """测试多 Agent 权限隔离场景"""
    # 注册多个 Agent，每个有不同权限
    await engine.register("agent_alice", [
        "A.项目/**",
        "B.个人/日记/**",
    ])
    
    await engine.register("agent_bob", [
        "A.项目/**",
        "C.知识/**",
    ])
    
    await engine.register("agent_charlie", [
        "C.知识/**",
    ])
    
    # Alice 可以访问自己的日记
    ctx = await engine.check("agent_alice", "read", "B.个人/日记/mem_001.md")
    assert ctx.granted is True
    
    # Bob 不能访问 Alice 的日记
    ctx = await engine.check("agent_bob", "read", "B.个人/日记/mem_001.md")
    assert ctx.granted is False
    
    # Charlie 只能访问知识库
    ctx = await engine.check("agent_charlie", "read", "A.项目/mem_001.md")
    assert ctx.granted is False
    
    ctx = await engine.check("agent_charlie", "read", "C.知识/mem_001.md")
    assert ctx.granted is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
