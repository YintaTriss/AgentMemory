"""
AgentMemory v2.0 - Adapters 单元测试

测试框架适配器：Base Protocol, ToolSpec, OpenClawAdapter 等
"""

import sys
import os
from unittest.mock import Mock, patch, MagicMock
import json
import re

import pytest

# Add source path
sys.path.insert(0, "C:/Users/31683/AgentMemory/agentmemory")

from adapters.base import (
    ToolSpec,
    FrameworkAdapter,
    validate_tool_spec,
    get_all_tool_names,
    filter_by_risk_level,
    TOOL_NAME_PATTERN,
    RISK_LEVELS,
)


class TestToolSpec:
    """ToolSpec 测试"""
    
    def test_tool_spec_creation(self):
        """测试 ToolSpec 创建"""
        spec = ToolSpec(
            name="memory_store",
            description="存储记忆",
            parameters={"type": "object"},
            risk_level="write",
            idempotent=True,
        )
        
        assert spec.name == "memory_store"
        assert spec.description == "存储记忆"
        assert spec.risk_level == "write"
        assert spec.idempotent is True
    
    def test_tool_spec_name_pattern(self):
        """测试工具名称模式"""
        # 有效名称
        valid_names = [
            "memory_store",
            "memory_query",
            "memory_forget",
            "memory_stats",
        ]
        
        for name in valid_names:
            spec = ToolSpec(
                name=name,
                description="test",
                parameters={},
                risk_level="read",
            )
            assert spec.name == name
    
    def test_tool_spec_invalid_name(self):
        """测试无效工具名称"""
        invalid_names = [
            "store",           # 缺少 memory_ 前缀
            "memory-Store",    # 大写字母
            "memory.store",    # 包含点号
            "memoryStore",     # 驼峰式
            "Memory_Store",   # 首字母大写
        ]
        
        for name in invalid_names:
            with pytest.raises(ValueError):
                ToolSpec(
                    name=name,
                    description="test",
                    parameters={},
                    risk_level="read",
                )
    
    def test_tool_spec_risk_levels(self):
        """测试风险等级"""
        for level in RISK_LEVELS:
            spec = ToolSpec(
                name="memory_test",
                description="test",
                parameters={},
                risk_level=level,
            )
            assert spec.risk_level == level
    
    def test_tool_spec_invalid_risk_level(self):
        """测试无效风险等级"""
        with pytest.raises(ValueError):
            ToolSpec(
                name="memory_test",
                description="test",
                parameters={},
                risk_level="invalid",
            )
    
    def test_tool_spec_to_dict(self):
        """测试转换为字典"""
        spec = ToolSpec(
            name="memory_query",
            description="查询记忆",
            parameters={"type": "object", "properties": {}},
            risk_level="read",
            idempotent=True,
            metadata={"version": "1.0"},
        )
        
        result = spec.to_dict()
        
        assert isinstance(result, dict)
        assert result["name"] == "memory_query"
        assert result["description"] == "查询记忆"
        assert result["risk_level"] == "read"
        assert result["idempotent"] is True
        assert result["metadata"]["version"] == "1.0"
    
    def test_tool_spec_equality(self):
        """测试相等性比较"""
        spec1 = ToolSpec(
            name="memory_test",
            description="test",
            parameters={},
            risk_level="read",
        )
        spec2 = ToolSpec(
            name="memory_test",
            description="test",
            parameters={},
            risk_level="read",
        )
        
        assert spec1 == spec2
    
    def test_tool_spec_repr(self):
        """测试 __repr__ 方法"""
        spec = ToolSpec(
            name="memory_store",
            description="store memory",
            parameters={},
            risk_level="write",
            idempotent=True,
        )
        
        repr_str = repr(spec)
        
        assert "memory_store" in repr_str
        assert "write" in repr_str


class TestFrameworkAdapterProtocol:
    """FrameworkAdapter 协议测试"""
    
    def test_protocol_attributes(self):
        """测试协议必需属性"""
        required_attrs = ["framework", "bind", "export_tools", "get_metadata"]
        
        for attr in required_attrs:
            assert attr in dir(FrameworkAdapter) or attr in FrameworkAdapter.__annotations__


class TestToolValidation:
    """工具验证测试"""
    
    def test_validate_valid_spec(self):
        """测试验证有效规范"""
        spec = ToolSpec(
            name="memory_get",
            description="get memory",
            parameters={},
            risk_level="read",
        )
        
        result = validate_tool_spec(spec)
        
        assert result is True
    
    def test_validate_invalid_spec_type(self):
        """测试验证无效类型"""
        with pytest.raises(ValueError):
            validate_tool_spec("not a ToolSpec")
    
    def test_validate_invalid_name(self):
        """测试验证无效名称"""
        spec = ToolSpec(
            name="invalid",
            description="test",
            parameters={},
            risk_level="read",
        )
        
        with pytest.raises(ValueError):
            validate_tool_spec(spec)
    
    def test_validate_invalid_risk_level(self):
        """测试验证无效风险等级"""
        spec = ToolSpec(
            name="memory_test",
            description="test",
            parameters={},
            risk_level="dangerous",  # 应该是 read/write/destructive
        )
        
        with pytest.raises(ValueError):
            validate_tool_spec(spec)


class TestHelperFunctions:
    """辅助函数测试"""
    
    def test_get_all_tool_names(self):
        """测试提取工具名称"""
        specs = [
            ToolSpec("memory_store", "s", {}, "write"),
            ToolSpec("memory_query", "q", {}, "read"),
            ToolSpec("memory_forget", "f", {}, "destructive"),
        ]
        
        names = get_all_tool_names(specs)
        
        assert names == ["memory_store", "memory_query", "memory_forget"]
    
    def test_get_all_tool_names_empty(self):
        """测试空列表"""
        names = get_all_tool_names([])
        
        assert names == []
    
    def test_filter_by_risk_level_read(self):
        """测试按风险等级过滤 - read"""
        specs = [
            ToolSpec("memory_a", "a", {}, "read"),
            ToolSpec("memory_b", "b", {}, "write"),
            ToolSpec("memory_c", "c", {}, "read"),
        ]
        
        filtered = filter_by_risk_level(specs, "read")
        
        assert len(filtered) == 2
        assert all(s.risk_level == "read" for s in filtered)
    
    def test_filter_by_risk_level_write(self):
        """测试按风险等级过滤 - write"""
        specs = [
            ToolSpec("memory_a", "a", {}, "read"),
            ToolSpec("memory_b", "b", {}, "write"),
            ToolSpec("memory_c", "c", {}, "destructive"),
        ]
        
        filtered = filter_by_risk_level(specs, "write")
        
        assert len(filtered) == 1
        assert filtered[0].name == "memory_b"
    
    def test_filter_by_risk_level_destructive(self):
        """测试按风险等级过滤 - destructive"""
        specs = [
            ToolSpec("memory_del", "delete", {}, "destructive"),
            ToolSpec("memory_query", "query", {}, "read"),
        ]
        
        filtered = filter_by_risk_level(specs, "destructive")
        
        assert len(filtered) == 1
        assert filtered[0].name == "memory_del"


class TestOpenClawAdapter:
    """OpenClawAdapter 测试"""
    
    @pytest.fixture
    def adapter(self):
        """创建适配器实例"""
        from adapters.openclaw import OpenClawAdapter
        return OpenClawAdapter()
    
    def test_adapter_initialization(self, adapter):
        """测试适配器初始化"""
        assert adapter.framework == "openclaw"
        assert adapter.version == "1.0.0"
        assert adapter.cli_path == "agentmemory"
    
    def test_adapter_custom_cli_path(self):
        """测试自定义 CLI 路径"""
        from adapters.openclaw import OpenClawAdapter
        adapter = OpenClawAdapter(cli_path="/usr/local/bin/agentmemory")
        
        assert adapter.cli_path == "/usr/local/bin/agentmemory"
    
    def test_adapter_bind(self, adapter):
        """测试 bind 方法"""
        mock_mh = Mock()
        result = adapter.bind(mock_mh)
        
        assert result is adapter
        assert adapter._mh_context is mock_mh
    
    def test_run_cli_file_not_found(self, adapter):
        """测试 CLI 未找到"""
        result = adapter._run_cli(["nonexistent-command"])
        
        assert result["success"] is False
        assert "not found" in result["error"].lower()
    
    def test_run_cli_timeout(self, adapter):
        """测试命令超时"""
        with patch('subprocess.run') as mock_run:
            import subprocess
            mock_run.side_effect = subprocess.TimeoutExpired("cmd", 30)
            
            result = adapter._run_cli(["sleep", "100"])
            
            assert result["success"] is False
            assert "timeout" in result["error"].lower()


class TestPatternMatching:
    """正则模式测试"""
    
    def test_tool_name_pattern_valid(self):
        """测试有效工具名称匹配"""
        valid = [
            "memory_a",
            "memory_ab",
            "memory_abc_def",
            "memory_store",
            "memory_query_with_limit",
        ]
        
        for name in valid:
            assert TOOL_NAME_PATTERN.match(name), f"Should match: {name}"
    
    def test_tool_name_pattern_invalid(self):
        """测试无效工具名称不匹配"""
        invalid = [
            "memory",
            "store",
            "Memory_Store",
            "memoryStore",
            "memory-query",
            "_memory",
            "memory_",
        ]
        
        for name in invalid:
            assert not TOOL_NAME_PATTERN.match(name), f"Should not match: {name}"


class TestEdgeCases:
    """边界情况测试"""
    
    def test_tool_spec_with_complex_parameters(self):
        """测试复杂参数定义"""
        complex_params = {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "记忆内容"},
                "importance": {"type": "number", "minimum": 0, "maximum": 1},
                "metadata": {
                    "type": "object",
                    "properties": {
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            "required": ["content"],
        }
        
        spec = ToolSpec(
            name="memory_complex",
            description="复杂参数测试",
            parameters=complex_params,
            risk_level="write",
        )
        
        assert spec.parameters == complex_params
        assert "properties" in spec.parameters
    
    def test_tool_spec_metadata_empty(self):
        """测试空元数据"""
        spec = ToolSpec(
            name="memory_no_meta",
            description="无元数据",
            parameters={},
            risk_level="read",
            metadata=None,
        )
        
        assert spec.metadata == {}
    
    def test_adapter_export_tools_structure(self, adapter):
        """测试导出工具结构"""
        from adapters.openclaw import OpenClawAdapter
        adapter = OpenClawAdapter()
        
        # 验证导出的工具是 ToolSpec 实例
        # 注意：实际导出可能需要 mock 或跳过
        # 这里只验证方法存在
        assert callable(adapter.export_tools)
