"""
MultiAgent 模块 — 多 Agent 共享与权限

v2.0 架构：§11 MultiAgent 机制
包含：MultiAgentLock / SharedLog / AgentRegistry + 权限模型
"""

# 从 multi_agent_core.py 导入原有类
from agentmemory.multi_agent_core import (
    MultiAgentLock,
    SharedLog,
    SharedLogEntry,
    AgentRegistry,
    TurnNotification,
    MultiAgent,
    MultiAgentLockTimeout,
    AgentNotRegisteredError,
    SharedLogError,
    generate_agent_id,
)

# 从 permissions.py 导入权限类
from agentmemory.multi_agent.permissions import (
    AgentPermission,
    PermissionContext,
    PermissionEngine,
)

__all__ = [
    # 原有类
    "MultiAgentLock",
    "SharedLog",
    "SharedLogEntry",
    "AgentRegistry",
    "TurnNotification",
    "MultiAgent",
    "MultiAgentLockTimeout",
    "AgentNotRegisteredError",
    "SharedLogError",
    "generate_agent_id",
    # 权限类
    "AgentPermission",
    "PermissionContext",
    "PermissionEngine",
]
