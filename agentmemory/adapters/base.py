"""
Framework Adapter 契约基类

定义所有框架适配器必须实现的接口：
- FrameworkAdapter Protocol: 适配器基类
- ToolSpec dataclass: 工具规格描述
"""

import re
from typing import Protocol, Any, Literal, runtime_checkable

# Tool name pattern: must match ^memory_[a-z_]+$
TOOL_NAME_PATTERN = re.compile(r"^memory_[a-z_]+$")

# Valid risk levels
RISK_LEVELS = {"read", "write", "destructive"}


class ToolSpec:
    """
    工具规格描述
    
    用于声明适配器暴露的工具的元信息。
    每个适配器通过 export_tools() 返回 ToolSpec 列表。
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict,
        risk_level: Literal["read", "write", "destructive"],
        idempotent: bool = True,
        metadata: dict = None,
    ):
        """
        Args:
            name: 工具名，必须匹配 ^memory_[a-z_]+$
            description: 工具描述
            parameters: JSON Schema 格式的参数定义
            risk_level: 风险等级
                - read: 只读操作，不修改数据
                - write: 写入操作，修改但不删除数据
                - destructive: 危险操作，可能删除数据
            idempotent: 是否幂等
            metadata: 额外元数据
        """
        # Validate name pattern
        if not TOOL_NAME_PATTERN.match(name):
            raise ValueError(
                f"Tool name must match pattern ^memory_[a-z_]+$, got: {name}"
            )
        
        # Validate risk_level
        if risk_level not in RISK_LEVELS:
            raise ValueError(
                f"risk_level must be one of {RISK_LEVELS}, got: {risk_level}"
            )
        
        self.name = name
        self.description = description
        self.parameters = parameters
        self.risk_level = risk_level
        self.idempotent = idempotent
        self.metadata = metadata or {}
    
    def to_dict(self) -> dict:
        """转换为字典格式（用于 MCP 协议）"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "risk_level": self.risk_level,
            "idempotent": self.idempotent,
            "metadata": self.metadata,
        }
    
    def __repr__(self) -> str:
        return (
            f"ToolSpec(name={self.name!r}, risk_level={self.risk_level!r}, "
            f"idempotent={self.idempotent})"
        )
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ToolSpec):
            return False
        return (
            self.name == other.name
            and self.description == other.description
            and self.risk_level == other.risk_level
        )


@runtime_checkable
class FrameworkAdapter(Protocol):
    """
    框架适配器协议
    
    所有框架适配器必须实现此协议。
    适配器负责：
    1. 将 MemoryHermes 绑定到目标框架
    2. 导出工具列表
    3. 提供元数据
    
    Example:
        class MyAdapter(FrameworkAdapter):
            framework = "my_framework"
            
            def bind(self, mh: MemoryHermes) -> Any:
                ...
            
            def export_tools(self) -> list[ToolSpec]:
                ...
            
            def get_metadata(self) -> dict:
                ...
    """
    
    @property
    def framework(self) -> str:
        """框架标识符，如 'claude_code', 'openclaw', 'langchain'"""
        ...
    
    def bind(self, mh: Any) -> Any:
        """
        将 MemoryHermes 绑定到目标框架
        
        Args:
            mh: MemoryHermes 实例
            
        Returns:
            绑定后的框架对象（如 MCP server、HTTP server 等）
        """
        ...
    
    def export_tools(self) -> list[ToolSpec]:
        """
        导出适配器暴露的工具列表
        
        Returns:
            ToolSpec 列表
        """
        ...
    
    def get_metadata(self) -> dict:
        """
        获取适配器元数据
        
        Returns:
            元数据字典，包含 version、framework、capabilities 等
        """
        ...


def validate_tool_spec(spec: ToolSpec) -> bool:
    """
    验证工具规格是否符合规范
    
    Args:
        spec: ToolSpec 实例
        
    Returns:
        True if valid
        
    Raises:
        ValueError: 验证失败
    """
    if not isinstance(spec, ToolSpec):
        raise ValueError(f"Expected ToolSpec, got {type(spec)}")
    
    if not TOOL_NAME_PATTERN.match(spec.name):
        raise ValueError(f"Invalid tool name: {spec.name}")
    
    if spec.risk_level not in RISK_LEVELS:
        raise ValueError(f"Invalid risk_level: {spec.risk_level}")
    
    return True


def get_all_tool_names(specs: list[ToolSpec]) -> list[str]:
    """从工具规格列表中提取所有工具名"""
    return [spec.name for spec in specs]


def filter_by_risk_level(
    specs: list[ToolSpec],
    level: Literal["read", "write", "destructive"]
) -> list[ToolSpec]:
    """按风险等级过滤工具"""
    return [spec for spec in specs if spec.risk_level == level]
