"""
Framework Adapters 单元测试

测试 Framework Adapter 契约和实现：
- base.py: FrameworkAdapter Protocol + ToolSpec
- claude_code.py: Claude Code MCP 适配器
- openclaw.py: OpenClaw CLI 适配器
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../..", "src"))

from adapters.base import (
    FrameworkAdapter,
    ToolSpec,
    validate_tool_spec,
    get_all_tool_names,
    filter_by_risk_level,
    TOOL_NAME_PATTERN,
)


# ==================== base.py Tests ====================

class TestToolSpec:
    """ToolSpec dataclass 测试"""
    
    def test_tool_spec_create_valid(self):
        """测试创建有效的 ToolSpec"""
        spec = ToolSpec(
            name="memory_test",
            description="测试工具",
            parameters={"type": "object"},
            risk_level="read"
        )
        assert spec.name == "memory_test"
        assert spec.description == "测试工具"
        assert spec.risk_level == "read"
        assert spec.idempotent == True
    
    def test_tool_spec_name_pattern_valid(self):
        """测试工具名符合模式 memory_[a-z_]+"""
        for valid_name in ["memory_store", "memory_query", "memory_test_one"]:
            spec = ToolSpec(
                name=valid_name,
                description="测试",
                parameters={},
                risk_level="read"
            )
            assert spec.name == valid_name
    
    def test_tool_spec_name_pattern_invalid(self):
        """测试无效工具名抛出异常"""
        invalid_names = ["store", "memory", "memoryStore", "memory-query", "MEMORY_STORE"]
        for invalid in invalid_names:
            with pytest.raises(ValueError, match="must match pattern"):
                ToolSpec(
                    name=invalid,
                    description="测试",
                    parameters={},
                    risk_level="read"
                )
    
    def test_tool_spec_risk_level_valid(self):
        """测试有效的 risk_level"""
        for level in ["read", "write", "destructive"]:
            spec = ToolSpec(
                name="memory_test",
                description="测试",
                parameters={},
                risk_level=level
            )
            assert spec.risk_level == level
    
    def test_tool_spec_risk_level_invalid(self):
        """测试无效的 risk_level 抛出异常"""
        with pytest.raises(ValueError):
            ToolSpec(
                name="memory_test",
                description="测试",
                parameters={},
                risk_level="invalid"
            )
    
    def test_tool_spec_idempotent_default(self):
        """测试 idempotent 默认值"""
        spec = ToolSpec(
            name="memory_test",
            description="测试",
            parameters={},
            risk_level="read"
        )
        assert spec.idempotent == True
    
    def test_tool_spec_idempotent_custom(self):
        """测试自定义 idempotent"""
        spec = ToolSpec(
            name="memory_test",
            description="测试",
            parameters={},
            risk_level="read",
            idempotent=False
        )
        assert spec.idempotent == False
    
    def test_tool_spec_to_dict(self):
        """测试 to_dict 方法"""
        spec = ToolSpec(
            name="memory_test",
            description="测试工具",
            parameters={"type": "object"},
            risk_level="write"
        )
        d = spec.to_dict()
        assert d["name"] == "memory_test"
        assert d["risk_level"] == "write"
        assert d["idempotent"] == True
    
    def test_tool_spec_repr(self):
        """测试 __repr__"""
        spec = ToolSpec(
            name="memory_test",
            description="测试",
            parameters={},
            risk_level="read"
        )
        repr_str = repr(spec)
        assert "memory_test" in repr_str
        assert "read" in repr_str
    
    def test_tool_spec_equality(self):
        """测试 __eq__"""
        spec1 = ToolSpec(
            name="memory_test",
            description="测试",
            parameters={},
            risk_level="read"
        )
        spec2 = ToolSpec(
            name="memory_test",
            description="测试",
            parameters={},
            risk_level="read"
        )
        assert spec1 == spec2


class TestFrameworkAdapter:
    """FrameworkAdapter Protocol 测试"""
    
    def test_framework_adapter_protocol_exists(self):
        """测试 FrameworkAdapter Protocol 存在"""
        assert FrameworkAdapter is not None
    
    def test_framework_adapter_has_framework_property(self):
        """测试 Protocol 有 framework 属性"""
        assert hasattr(FrameworkAdapter, "framework")
    
    def test_framework_adapter_has_bind_method(self):
        """测试 Protocol 有 bind 方法"""
        assert hasattr(FrameworkAdapter, "bind")
    
    def test_framework_adapter_has_export_tools_method(self):
        """测试 Protocol 有 export_tools 方法"""
        assert hasattr(FrameworkAdapter, "export_tools")
    
    def test_framework_adapter_has_get_metadata_method(self):
        """测试 Protocol 有 get_metadata 方法"""
        assert hasattr(FrameworkAdapter, "get_metadata")


class TestHelperFunctions:
    """辅助函数测试"""
    
    def test_validate_tool_spec_valid(self):
        """测试 validate_tool_spec 接受有效规范"""
        spec = ToolSpec(
            name="memory_test",
            description="测试",
            parameters={},
            risk_level="read"
        )
        assert validate_tool_spec(spec) == True
    
    def test_validate_tool_spec_invalid_type(self):
        """测试 validate_tool_spec 拒绝非 ToolSpec"""
        with pytest.raises(ValueError):
            validate_tool_spec("not a tool spec")
    
    def test_validate_tool_spec_invalid_name(self):
        """测试创建无效名称的 ToolSpec 抛出异常"""
        # ToolSpec 在初始化时就验证名称，所以直接测试创建
        with pytest.raises(ValueError, match="must match pattern"):
            ToolSpec(
                name="invalid",
                description="测试",
                parameters={},
                risk_level="read"
            )
    
    def test_get_all_tool_names(self):
        """测试 get_all_tool_names"""
        specs = [
            ToolSpec(name="memory_store", description="1", parameters={}, risk_level="write"),
            ToolSpec(name="memory_query", description="2", parameters={}, risk_level="read"),
        ]
        names = get_all_tool_names(specs)
        assert names == ["memory_store", "memory_query"]
    
    def test_filter_by_risk_level_read(self):
        """测试按 risk_level 过滤 - read"""
        specs = [
            ToolSpec(name="memory_store", description="1", parameters={}, risk_level="write"),
            ToolSpec(name="memory_query", description="2", parameters={}, risk_level="read"),
            ToolSpec(name="memory_forget", description="3", parameters={}, risk_level="destructive"),
        ]
        filtered = filter_by_risk_level(specs, "read")
        assert len(filtered) == 1
        assert filtered[0].name == "memory_query"
    
    def test_filter_by_risk_level_write(self):
        """测试按 risk_level 过滤 - write"""
        specs = [
            ToolSpec(name="memory_store", description="1", parameters={}, risk_level="write"),
            ToolSpec(name="memory_query", description="2", parameters={}, risk_level="read"),
            ToolSpec(name="memory_session", description="3", parameters={}, risk_level="write"),
        ]
        filtered = filter_by_risk_level(specs, "write")
        assert len(filtered) == 2


# ==================== ClaudeCodeAdapter Tests ====================

class TestClaudeCodeAdapter:
    """Claude Code 适配器测试"""
    
    def test_adapter_import(self):
        """测试导入 ClaudeCodeAdapter"""
        from adapters.claude_code import ClaudeCodeAdapter
        assert ClaudeCodeAdapter is not None
    
    def test_adapter_framework_property(self):
        """测试 framework 属性"""
        from adapters.claude_code import ClaudeCodeAdapter
        adapter = ClaudeCodeAdapter()
        assert adapter.framework == "claude_code"
    
    def test_adapter_version_property(self):
        """测试 version 属性"""
        from adapters.claude_code import ClaudeCodeAdapter
        adapter = ClaudeCodeAdapter()
        assert hasattr(adapter, "version")
        assert adapter.version == "1.0.0"
    
    def test_adapter_init_without_config(self):
        """测试无参数初始化"""
        from adapters.claude_code import ClaudeCodeAdapter
        adapter = ClaudeCodeAdapter()
        assert adapter.config_path is None
    
    def test_adapter_init_with_config(self):
        """测试带参数初始化"""
        from adapters.claude_code import ClaudeCodeAdapter
        adapter = ClaudeCodeAdapter(config_path="/path/to/config")
        assert adapter.config_path == "/path/to/config"
    
    def test_adapter_tools_list(self):
        """测试 TOOLS 列表存在"""
        from adapters.claude_code import ClaudeCodeAdapter
        assert hasattr(ClaudeCodeAdapter, "TOOLS")
        assert len(ClaudeCodeAdapter.TOOLS) == 6
    
    def test_adapter_tool_names(self):
        """测试所有工具名符合规范"""
        from adapters.claude_code import ClaudeCodeAdapter
        expected_names = [
            "memory_store", "memory_query", "memory_forget",
            "memory_stats", "memory_prefetch", "memory_session_end"
        ]
        for tool in ClaudeCodeAdapter.TOOLS:
            assert tool["name"] in expected_names
    
    def test_export_tools_returns_list(self):
        """测试 export_tools 返回列表"""
        from adapters.claude_code import ClaudeCodeAdapter
        adapter = ClaudeCodeAdapter()
        tools = adapter.export_tools()
        assert isinstance(tools, list)
        assert len(tools) == 6
    
    def test_export_tools_returns_tool_specs(self):
        """测试 export_tools 返回 ToolSpec 列表"""
        from adapters.claude_code import ClaudeCodeAdapter
        from adapters.base import ToolSpec
        adapter = ClaudeCodeAdapter()
        tools = adapter.export_tools()
        for tool in tools:
            # ClaudeCode adapter now returns ToolSpec objects to match base contract
            assert isinstance(tool, ToolSpec), f"Expected ToolSpec, got {type(tool)}"
            assert tool.name.startswith("memory_")
            assert hasattr(tool, "description")
            assert hasattr(tool, "risk_level")
    
    def test_get_metadata_returns_dict(self):
        """测试 get_metadata 返回字典"""
        from adapters.claude_code import ClaudeCodeAdapter
        adapter = ClaudeCodeAdapter()
        metadata = adapter.get_metadata()
        assert isinstance(metadata, dict)
        assert metadata["framework"] == "claude_code"
        assert "capabilities" in metadata
    
    def test_bind_requires_mh(self):
        """测试 bind 需要 MemoryHermes"""
        from adapters.claude_code import ClaudeCodeAdapter
        # Mock MemoryHermes for testing
        class MockMH:
            pass
        adapter = ClaudeCodeAdapter()
        mh = MockMH()
        # bind should not raise
        result = adapter.bind(mh)
        assert result is not None


# ==================== OpenClawAdapter Tests ====================

class TestOpenClawAdapter:
    """OpenClaw CLI 适配器测试"""
    
    def test_adapter_import(self):
        """测试导入 OpenClawAdapter"""
        from adapters.openclaw import OpenClawAdapter
        assert OpenClawAdapter is not None
    
    def test_adapter_framework_property(self):
        """测试 framework 属性"""
        from adapters.openclaw import OpenClawAdapter
        adapter = OpenClawAdapter()
        assert adapter.framework == "openclaw"
    
    def test_adapter_version_property(self):
        """测试 version 属性"""
        from adapters.openclaw import OpenClawAdapter
        adapter = OpenClawAdapter()
        assert hasattr(adapter, "version")
        assert adapter.version == "1.0.0"
    
    def test_adapter_init_default_cli(self):
        """测试默认 CLI 路径"""
        from adapters.openclaw import OpenClawAdapter
        adapter = OpenClawAdapter()
        assert adapter.cli_path == "agentmemory"
    
    def test_adapter_init_custom_cli(self):
        """测试自定义 CLI 路径"""
        from adapters.openclaw import OpenClawAdapter
        adapter = OpenClawAdapter(cli_path="/custom/cli")
        assert adapter.cli_path == "/custom/cli"
    
    def test_bind_returns_self(self):
        """测试 bind 返回 self"""
        from adapters.openclaw import OpenClawAdapter
        class MockMH:
            pass
        adapter = OpenClawAdapter()
        mh = MockMH()
        result = adapter.bind(mh)
        assert result is adapter
    
    def test_export_tools_returns_list(self):
        """测试 export_tools 返回列表"""
        from adapters.openclaw import OpenClawAdapter
        adapter = OpenClawAdapter()
        tools = adapter.export_tools()
        assert isinstance(tools, list)
        assert len(tools) == 6
    
    def test_export_tools_returns_dicts(self):
        """测试 export_tools 返回字典列表"""
        from adapters.openclaw import OpenClawAdapter
        adapter = OpenClawAdapter()
        tools = adapter.export_tools()
        for tool in tools:
            assert isinstance(tool, dict)
            assert "name" in tool
            assert "description" in tool
    
    def test_get_metadata_returns_dict(self):
        """测试 get_metadata 返回字典"""
        from adapters.openclaw import OpenClawAdapter
        adapter = OpenClawAdapter()
        metadata = adapter.get_metadata()
        assert isinstance(metadata, dict)
        assert metadata["framework"] == "openclaw"
        assert metadata["protocol"] == "cli"
    
    def test_run_cli_handles_not_found(self):
        """测试 _run_cli 处理 CLI 不存在"""
        from adapters.openclaw import OpenClawAdapter
        adapter = OpenClawAdapter(cli_path="nonexistent_command_xyz")
        result = adapter._run_cli(["store", "test"])
        assert result["success"] == False
        assert "not found" in result["error"].lower()
    
    def test_store_returns_structure(self):
        """测试 store 方法返回结构"""
        from adapters.openclaw import OpenClawAdapter
        adapter = OpenClawAdapter(cli_path="nonexistent")  # Use nonexistent to avoid actual execution
        result = adapter.store("test content")
        # 即使 CLI 不存在，也应该返回结构化结果
        assert isinstance(result, dict)
        assert "success" in result
    
    def test_query_returns_structure(self):
        """测试 query 方法返回结构"""
        from adapters.openclaw import OpenClawAdapter
        adapter = OpenClawAdapter(cli_path="nonexistent")
        result = adapter.query("test query")
        assert isinstance(result, dict)
        assert "success" in result
    
    def test_stats_returns_structure(self):
        """测试 stats 方法返回结构"""
        from adapters.openclaw import OpenClawAdapter
        adapter = OpenClawAdapter(cli_path="nonexistent")
        result = adapter.stats()
        assert isinstance(result, dict)
        assert "success" in result
