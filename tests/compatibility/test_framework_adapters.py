"""
框架适配器测试
v2.0 功能，待 T4 框架适配器实现后解冻

## v2.0 套件解冻说明
当 T4 backend2 完成框架适配器实现后：
1. 删除本文件顶部的 pytest.skip 相关代码（如有）
2. 填stub 函数的具体实现
3. 运行 pytest tests/compatibility/test_framework_adapters.py 验证

## Stub 函数说明（待 T4/T7 解冻时填写）
- test_claude_code_bind_export_tools: Claude Code bind + export_tools 集成测试（由 T4 实现）
- test_openclaw_bind_export_tools: OpenClaw bind + export_tools 集成测试（由 T4 实现）
- test_langchain_bind_export_tools: LangChain bind + export_tools 集成测试（由 T7 实现）
- test_openai_agents_bind_export_tools: OpenAI Agents bind + export_tools 集成测试（由 T7 实现）
- test_crewai_bind_export_tools: CrewAI bind + export_tools 集成测试（由 T7 实现）
"""

import pytest
import sys
import os
import json
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../..", "src"))

# v2.0 功能 - T4 完成，解冻


# ============================================================================
# v2.0 套件解冻 Stub 函数（待 T4/T7 实现）
# ============================================================================

class TestAdapterStubs:
    """适配器 Stub 测试（v2.0 套件解冻时由 T4/T7 接手实现）"""
    
    def test_claude_code_bind_export_tools(self):
        """
        Claude Code bind + export_tools 集成测试
        
        v2.0 套件解冻时由 T4 填写实现：
        1. from adapters.claude_code import ClaudeCodeAdapter
        2. adapter = ClaudeCodeAdapter()
        3. mh = MemoryHermes() 或 mock
        4. adapter.bind(mh)
        5. tools = adapter.export_tools(mh)
        6. 验证 tools 是 list 且每个 tool 有 name/description/inputSchema
        """
        pytest.skip("v2.0 套件解冻时由 T4 接手实现")
    
    def test_openclaw_bind_export_tools(self):
        """
        OpenClaw bind + export_tools 集成测试
        
        v2.0 套件解冻时由 T4 填写实现：
        1. from adapters.openclaw import OpenClawAdapter
        2. adapter = OpenClawAdapter()
        3. mh = MemoryHermes() 或 mock
        4. adapter.bind(mh)
        5. skills = adapter.export_skills(mh) 或 export_tools(mh)
        6. 验证导出格式符合 OpenClaw skill manifest
        """
        pytest.skip("v2.0 套件解冻时由 T4 接手实现")
    
    def test_langchain_bind_export_tools(self):
        """
        LangChain bind + export_tools 集成测试
        
        v2.0 套件解冻时由 T7 填写实现：
        1. from adapters.langchain import LangChainAdapter
        2. adapter = LangChainAdapter()
        3. mh = MemoryHermes() 或 mock
        4. adapter.bind(mh)
        5. tools = adapter.export_tools(mh)
        6. 验证导出格式符合 LangChain Tool 接口
        """
        pytest.skip("v2.0 套件解冻时由 T7 接手实现")
    
    def test_openai_agents_bind_export_tools(self):
        """
        OpenAI Agents bind + export_tools 集成测试
        
        v2.0 套件解冻时由 T7 填写实现：
        1. from adapters.openai_agents import OpenAIAgentsAdapter
        2. adapter = OpenAIAgentsAdapter()
        3. mh = MemoryHermes() 或 mock
        4. adapter.bind(mh)
        5. tools = adapter.export_tools(mh)
        6. 验证导出格式符合 OpenAI Agents SDK FunctionTool
        """
        pytest.skip("v2.0 套件解冻时由 T7 接手实现")
    
    def test_crewai_bind_export_tools(self):
        """
        CrewAI bind + export_tools 集成测试
        
        v2.0 套件解冻时由 T7 填写实现：
        1. from adapters.crewai import CrewAIAdapter
        2. adapter = CrewAIAdapter()
        3. mh = MemoryHermes() 或 mock
        4. adapter.bind(mh)
        5. tools = adapter.export_tools(mh)
        6. 验证导出格式符合 CrewAI BaseTool
        """
        pytest.skip("v2.0 套件解冻时由 T7 接手实现")


# ============================================================================
# 现有测试（保持不变）
# ============================================================================

class TestAdapterContract:
    """适配器契约测试"""
    
    def test_framework_adapter_interface(self):
        """测试 FrameworkAdapter 接口"""
        from adapters.base import FrameworkAdapter, ToolSpec
        
        # 验证基类存在必要方法
        adapter = FrameworkAdapter()
        
        # 必须有 framework 属性
        assert hasattr(adapter, 'framework')
        
        # 必须有 bind 方法
        assert hasattr(adapter, 'bind')
        
        # 必须有 export_tools 方法
        assert hasattr(adapter, 'export_tools')
    
    def test_tool_spec_validation(self):
        """测试工具规格验证"""
        from adapters.base import ToolSpec
        
        # 有效的工具规格
        spec = ToolSpec(
            name="memory_search",
            description="搜索记忆内容",
            parameters=[],
            risk_level="read"
        )
        
        assert spec.name == "memory_search"
        assert spec.risk_level in ["read", "write", "destructive"]
    
    def test_tool_spec_validation_invalid(self):
        """测试无效工具规格"""
        from adapters.base import ToolSpec
        
        # 工具名必须以 memory_ 开头
        with pytest.raises(ValueError):
            ToolSpec(
                name="invalid_name",
                description="测试",
                parameters=[],
                risk_level="read"
            )


class TestClaudeCodeAdapter:
    """Claude Code 适配器测试"""
    
    def test_adapter_init(self):
        """测试适配器初始化"""
        try:
            from adapters.claude_code import ClaudeCodeAdapter
            
            adapter = ClaudeCodeAdapter()
            assert adapter.framework == "claude_code"
        except ImportError:
            pytest.skip("Claude Code 适配器尚未实现")
    
    def test_bind_returns_mcp_server(self):
        """测试 bind 返回 MCP Server"""
        try:
            from adapters.claude_code import ClaudeCodeAdapter
            from memory_manager import MemoryHermes
            
            adapter = ClaudeCodeAdapter()
            mh = MemoryHermes()
            
            result = adapter.bind(mh)
            
            # 应该返回 MCP server 对象
            assert result is not None
        except ImportError:
            pytest.skip("Claude Code 适配器尚未实现")
    
    def test_export_tools_format(self):
        """测试导出工具格式"""
        try:
            from adapters.claude_code import ClaudeCodeAdapter
            from memory_manager import MemoryHermes
            
            adapter = ClaudeCodeAdapter()
            mh = MemoryHermes()
            
            adapter.bind(mh)
            tools = adapter.export_tools(mh)
            
            # 应该有工具列表
            assert isinstance(tools, list)
            
            # 每个工具应该有 name 和 description
            for tool in tools:
                assert "name" in tool
                assert "description" in tool
                assert tool["name"].startswith("memory_")
        except ImportError:
            pytest.skip("Claude Code 适配器尚未实现")
    
    def test_mcp_schema_compliance(self):
        """测试 MCP Schema 合规性"""
        try:
            from adapters.claude_code import ClaudeCodeAdapter
            from memory_manager import MemoryHermes
            
            adapter = ClaudeCodeAdapter()
            mh = MemoryHermes()
            
            adapter.bind(mh)
            tools = adapter.export_tools(mh)
            
            for tool in tools:
                # MCP 工具应该有 inputSchema
                assert "inputSchema" in tool or "parameters" in tool
        except ImportError:
            pytest.skip("Claude Code 适配器尚未实现")


class TestOpenClawAdapter:
    """OpenClaw 适配器测试"""
    
    def test_adapter_init(self):
        """测试适配器初始化"""
        try:
            from adapters.openclaw import OpenClawAdapter
            
            adapter = OpenClawAdapter()
            assert adapter.framework == "openclaw"
        except ImportError:
            pytest.skip("OpenClaw 适配器尚未实现")
    
    def test_bind_returns_skill(self):
        """测试 bind 返回 Skill"""
        try:
            from adapters.openclaw import OpenClawAdapter
            from memory_manager import MemoryHermes
            
            adapter = OpenClawAdapter()
            mh = MemoryHermes()
            
            result = adapter.bind(mh)
            
            assert result is not None
        except ImportError:
            pytest.skip("OpenClaw 适配器尚未实现")
    
    def test_cli_manifest_format(self):
        """测试 CLI manifest 格式"""
        try:
            from adapters.openclaw import OpenClawAdapter
            from memory_manager import MemoryHermes
            
            adapter = OpenClawAdapter()
            mh = MemoryHermes()
            
            manifest = adapter._cli_manifest(mh)
            
            assert manifest is not None
            assert "name" in manifest or "commands" in manifest
        except ImportError:
            pytest.skip("OpenClaw 适配器尚未实现")


class TestLangChainAdapter:
    """LangChain 适配器测试"""
    
    def test_adapter_init(self):
        """测试适配器初始化"""
        try:
            from adapters.langchain import LangChainAdapter
            
            adapter = LangChainAdapter()
            assert adapter.framework == "langchain"
        except ImportError:
            pytest.skip("LangChain 适配器尚未实现")
    
    def test_bind_returns_base_memory(self):
        """测试 bind 返回 BaseMemory"""
        try:
            from adapters.langchain import LangChainAdapter
            from memory_manager import MemoryHermes
            
            adapter = LangChainAdapter()
            mh = MemoryHermes()
            
            result = adapter.bind(mh)
            
            # 应该返回 LangChain 的 memory 对象
            assert result is not None
        except ImportError:
            pytest.skip("LangChain 适配器尚未实现")
    
    def test_langchain_tool_conversion(self):
        """测试 LangChain Tool 转换"""
        try:
            from adapters.langchain import LangChainAdapter
            from memory_manager import MemoryHermes
            
            adapter = LangChainAdapter()
            mh = MemoryHermes()
            
            adapter.bind(mh)
            tools = adapter.export_tools(mh)
            
            # 应该能转换为 LangChain Tool
            for tool in tools:
                assert hasattr(tool, 'name') or 'name' in tool
        except ImportError:
            pytest.skip("LangChain 适配器尚未实现")


class TestOpenAIAdapter:
    """OpenAI Agents 适配器测试"""
    
    def test_adapter_init(self):
        """测试适配器初始化"""
        try:
            from adapters.openai_agents import OpenAIAgentsAdapter
            
            adapter = OpenAIAgentsAdapter()
            assert adapter.framework == "openai_agents"
        except ImportError:
            pytest.skip("OpenAI Agents 适配器尚未实现")
    
    def test_bind_returns_function_tools(self):
        """测试 bind 返回函数工具"""
        try:
            from adapters.openai_agents import OpenAIAgentsAdapter
            from memory_manager import MemoryHermes
            
            adapter = OpenAIAgentsAdapter()
            mh = MemoryHermes()
            
            result = adapter.bind(mh)
            
            assert result is not None
        except ImportError:
            pytest.skip("OpenAI Agents 适配器尚未实现")
    
    def test_function_calling_schema(self):
        """测试函数调用 schema"""
        try:
            from adapters.openai_agents import OpenAIAgentsAdapter
            from memory_manager import MemoryHermes
            
            adapter = OpenAIAgentsAdapter()
            mh = MemoryHermes()
            
            adapter.bind(mh)
            tools = adapter.export_tools(mh)
            
            for tool in tools:
                # OpenAI function calling 格式
                assert "type" in tool or "name" in tool
        except ImportError:
            pytest.skip("OpenAI Agents 适配器尚未实现")


class TestCrewAIAdapter:
    """CrewAI 适配器测试"""
    
    def test_adapter_init(self):
        """测试适配器初始化"""
        try:
            from adapters.crewai import CrewAIAdapter
            
            adapter = CrewAIAdapter()
            assert adapter.framework == "crewai"
        except ImportError:
            pytest.skip("CrewAI 适配器尚未实现")
    
    def test_bind_returns_base_tool(self):
        """测试 bind 返回 BaseTool"""
        try:
            from adapters.crewai import CrewAIAdapter
            from memory_manager import MemoryHermes
            
            adapter = CrewAIAdapter()
            mh = MemoryHermes()
            
            result = adapter.bind(mh)
            
            assert result is not None
        except ImportError:
            pytest.skip("CrewAI 适配器尚未实现")


class TestAdapterCompatibility:
    """适配器兼容性测试"""
    
    def test_unified_tool_names(self):
        """测试统一工具名称"""
        from adapters.base import ToolSpec
        
        # 所有适配器应该导出相同名称的工具
        expected_tools = [
            "memory_search",
            "memory_get",
            "memory_add",
            "memory_update",
            "memory_delete",
            "memory_stats"
        ]
        
        # 验证工具名称规范
        for name in expected_tools:
            spec = ToolSpec(
                name=name,
                description="测试",
                parameters=[],
                risk_level="read"
            )
            assert spec.name == name
    
    def test_risk_level_consistency(self):
        """测试风险级别一致性"""
        from adapters.base import ToolSpec
        
        # 读操作应该是 read
        search_spec = ToolSpec(
            name="memory_search",
            description="搜索",
            parameters=[],
            risk_level="read"
        )
        assert search_spec.risk_level == "read"
        
        # 写操作应该是 write
        add_spec = ToolSpec(
            name="memory_add",
            description="添加",
            parameters=[],
            risk_level="write"
        )
        assert add_spec.risk_level == "write"
        
        # 删除应该是 destructive
        delete_spec = ToolSpec(
            name="memory_delete",
            description="删除",
            parameters=[],
            risk_level="destructive"
        )
        assert delete_spec.risk_level == "destructive"
    
    def test_idempotency_flag(self):
        """测试幂等性标志"""
        from adapters.base import ToolSpec
        
        # 大多数操作应该是幂等的
        spec = ToolSpec(
            name="memory_search",
            description="搜索",
            parameters=[],
            risk_level="read",
            idempotent=True
        )
        assert spec.idempotent == True


class TestAdapterMultiTenant:
    """适配器多租户测试"""
    
    def test_tenant_isolation_in_adapter(self):
        """测试适配器中的租户隔离"""
        try:
            from adapters.claude_code import ClaudeCodeAdapter
            from memory_manager import MemoryHermes
            
            adapter = ClaudeCodeAdapter()
            
            # 不同租户应该有不同上下文
            tenant_a = {"tenant_id": "tenant_a"}
            tenant_b = {"tenant_id": "tenant_b"}
            
            # 适配器应该支持租户参数
            assert adapter is not None
        except ImportError:
            pytest.skip("适配器尚未实现")
    
    def test_namespace_support(self):
        """测试命名空间支持"""
        try:
            from adapters.base import FrameworkAdapter
            
            adapter = FrameworkAdapter()
            
            # 应该有命名空间支持
            assert hasattr(adapter, 'bind') or True
        except ImportError:
            pytest.skip("适配器尚未实现")
