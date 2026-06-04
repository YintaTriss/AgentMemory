"""
AgentMemory 框架适配器模块

提供与各种 Agent 框架的集成适配器：
- ClaudeCodeAdapter: Claude Code MCP 协议适配器
- OpenClawAdapter: OpenClaw CLI 适配器
"""

from .base import (
    FrameworkAdapter,
    ToolSpec,
    validate_tool_spec,
    get_all_tool_names,
    filter_by_risk_level,
)

__all__ = [
    "FrameworkAdapter",
    "ToolSpec",
    "validate_tool_spec",
    "get_all_tool_names",
    "filter_by_risk_level",
]

# Lazy imports for adapters
def get_claude_code_adapter():
    """获取 Claude Code 适配器（延迟导入）"""
    from .claude_code import ClaudeCodeAdapter
    return ClaudeCodeAdapter

def get_openclaw_adapter():
    """获取 OpenClaw 适配器（延迟导入）"""
    from .openclaw import OpenClawAdapter
    return OpenClawAdapter
