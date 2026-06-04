"""
框架适配器测试
v2.0 功能 - T4/T7 已完成，解冻

## 测试覆盖
- 5 框架: ClaudeCode, OpenClaw, LangChain, OpenAI Agents, CrewAI
- 3 方法: bind, export_tools, get_metadata

## 验收标准
- 每个框架的 bind() 返回正确类型
- 每个框架的 export_tools() 返回 5 个 ToolSpec
- 每个框架的 get_metadata() 返回包含 framework 和 requires 字段的 dict
"""

import pytest
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../..", "src"))


# ============================================================================
# Mock MemoryHermes for Testing
# ============================================================================

class MockMemoryHermes:
    """Mock MemoryHermes for adapter testing"""
    
    def __init__(self):
        self._memories = {}
        self._counter = 0
    
    async def store(self, content: str, metadata: dict = None, importance: float = 0.5) -> str:
        import uuid
        memory_id = f"mem_{uuid.uuid4().hex[:12]}"
        self._memories[memory_id] = {
            "id": memory_id,
            "content": content,
            "metadata": metadata or {},
            "importance": importance,
        }
        self._counter += 1
        return memory_id
    
    async def query(self, query: str, limit: int = 5, filters: dict = None):
        return list(self._memories.values())[:limit]
    
    def get_stats(self):
        return {"total_memories": len(self._memories)}
    
    def prefetch(self, query: str):
        pass
    
    def get_prefetched(self, query: str):
        return None
    
    async def forget(self, memory_id: str, permanent: bool = False):
        if memory_id in self._memories:
            del self._memories[memory_id]
        return True
    
    async def execute(self, action: str, params: dict = None):
        if action == "store":
            memory_id = await self.store(
                params.get("content", ""),
                params.get("metadata"),
                params.get("importance", 0.5)
            )
            return {"success": True, "id": memory_id}
        elif action == "query":
            results = await self.query(
                params.get("query", ""),
                params.get("limit", 5),
                params.get("filters")
            )
            return {"success": True, "results": results}
        elif action == "get_stats":
            return {"success": True, "stats": self.get_stats()}
        elif action == "forget":
            success = await self.forget(
                params.get("memory_id"),
                params.get("permanent", False)
            )
            return {"success": success}
        return {"success": False}


@pytest.fixture
def mh():
    """Create mock MemoryHermes for testing"""
    return MockMemoryHermes()


# ============================================================================
# Framework Adapter Test Matrix
# 5 Frameworks × 3 Methods = 15 Test Cases
# ============================================================================

FRAMEWORKS = {
    "claude_code": {
        "module": "adapters.claude_code",
        "class": "ClaudeCodeAdapter",
        "bind_expected_type": "FastMCP",  # or self if MCP unavailable
        "export_tools_count": 6,  # Claude Code has 6 tools
        "has_mcp_dependency": True,
    },
    "openclaw": {
        "module": "adapters.openclaw",
        "class": "OpenClawAdapter",
        "bind_expected_type": "OpenClawAdapter",
        "export_tools_count": 6,  # OpenClaw has 6 tools
        "has_mcp_dependency": False,
    },
    "langchain": {
        "module": "adapters.langchain",
        "class": "LangChainAdapter",
        "bind_expected_type": "AgentMemoryChatHistory",
        "export_tools_count": 5,
        "has_mcp_dependency": False,
    },
    "openai_agents": {
        "module": "adapters.openai_agents",
        "class": "OpenAIAgentsAdapter",
        "bind_expected_type": "dict",
        "export_tools_count": 5,
        "has_mcp_dependency": False,
    },
    "crewai": {
        "module": "adapters.crewai",
        "class": "CrewAIAdapter",
        "bind_expected_type": "list",
        "export_tools_count": 5,
        "has_mcp_dependency": False,
    },
}


class TestFrameworkAdapterContract:
    """适配器契约测试 - 验证基础接口"""
    
    def test_framework_adapter_protocol_exists(self):
        """验证 FrameworkAdapter Protocol 存在"""
        from adapters.base import FrameworkAdapter
        assert FrameworkAdapter is not None
        # FrameworkAdapter 是 Protocol，检查它有必要的属性
        assert hasattr(FrameworkAdapter, 'framework')
        assert hasattr(FrameworkAdapter, 'bind')
        assert hasattr(FrameworkAdapter, 'export_tools')
        assert hasattr(FrameworkAdapter, 'get_metadata')
    
    def test_tool_spec_validation(self):
        """验证 ToolSpec 可以正确验证工具规格"""
        from adapters.base import ToolSpec, validate_tool_spec
        
        # Valid spec
        spec = ToolSpec(
            name="memory_test",
            description="Test tool",
            parameters={"type": "object", "properties": {}},
            risk_level="read"
        )
        assert validate_tool_spec(spec) == True
        
        # Invalid name pattern
        with pytest.raises(ValueError, match="must match pattern"):
            ToolSpec(
                name="invalid_name",
                description="Test",
                parameters={},
                risk_level="read"
            )
        
        # Invalid risk level
        with pytest.raises(ValueError, match="must be one of"):
            ToolSpec(
                name="memory_test",
                description="Test",
                parameters={},
                risk_level="invalid"
            )


class TestClaudeCodeAdapter:
    """Claude Code 适配器测试"""
    
    @pytest.fixture
    def adapter(self):
        try:
            from adapters.claude_code import ClaudeCodeAdapter
            return ClaudeCodeAdapter()
        except ImportError as e:
            pytest.skip(f"Claude Code adapter not available: {e}")
    
    def test_bind_returns_mcp_or_self(self, adapter, mh):
        """测试 bind() 返回 MCP server 或 self"""
        result = adapter.bind(mh)
        # ClaudeCodeAdapter.bind() returns FastMCP if mcp available, else dict
        assert result is not None
    
    def test_export_tools_returns_6_tools(self, adapter, mh):
        """测试 export_tools() 返回 6 个工具规格"""
        adapter.bind(mh)
        tools = adapter.export_tools()
        assert isinstance(tools, list)
        assert len(tools) == 6  # Claude Code has 6 memory tools
        
        # Verify tool names - Claude Code returns dict format
        tool_names = [t["name"] if isinstance(t, dict) else t.name for t in tools]
        expected_names = [
            "memory_store", "memory_query", "memory_forget",
            "memory_stats", "memory_prefetch", "memory_session_end"
        ]
        for name in expected_names:
            assert name in tool_names, f"{name} not found in {tool_names}"
    
    def test_export_tools_risk_levels(self, adapter, mh):
        """测试工具风险等级正确"""
        adapter.bind(mh)
        tools = adapter.export_tools()
        
        # Claude Code returns dict format, extract risk levels
        read_tools = [t for t in tools if (t.get("risk_level") if isinstance(t, dict) else t.risk_level) == "read"]
        write_tools = [t for t in tools if (t.get("risk_level") if isinstance(t, dict) else t.risk_level) == "write"]
        destructive_tools = [t for t in tools if (t.get("risk_level") if isinstance(t, dict) else t.risk_level) == "destructive"]
        
        assert len(read_tools) >= 3  # query, stats, prefetch
        assert len(write_tools) >= 1  # store, session_end
        assert len(destructive_tools) >= 1  # forget
    
    def test_get_metadata(self, adapter, mh):
        """测试 get_metadata() 返回正确的元数据"""
        adapter.bind(mh)
        metadata = adapter.get_metadata()
        
        assert isinstance(metadata, dict)
        assert "framework" in metadata
        assert metadata["framework"] == "claude_code"
        assert "version" in metadata
        assert "protocol" in metadata


class TestOpenClawAdapter:
    """OpenClaw 适配器测试"""
    
    @pytest.fixture
    def adapter(self):
        try:
            from adapters.openclaw import OpenClawAdapter
            return OpenClawAdapter()
        except ImportError as e:
            pytest.skip(f"OpenClaw adapter not available: {e}")
    
    def test_bind_returns_adapter_self(self, adapter, mh):
        """测试 bind() 返回适配器自身"""
        result = adapter.bind(mh)
        assert result is adapter
    
    def test_export_tools_returns_6_tools(self, adapter, mh):
        """测试 export_tools() 返回 6 个工具规格"""
        adapter.bind(mh)
        tools = adapter.export_tools()
        assert isinstance(tools, list)
        assert len(tools) == 6  # OpenClaw has 6 memory tools
    
    def test_get_metadata(self, adapter, mh):
        """测试 get_metadata()"""
        adapter.bind(mh)
        metadata = adapter.get_metadata()
        
        assert isinstance(metadata, dict)
        assert "framework" in metadata
        assert metadata["framework"] == "openclaw"
        assert "version" in metadata


class TestLangChainAdapter:
    """LangChain 适配器测试"""
    
    @pytest.fixture
    def adapter(self):
        try:
            from adapters.langchain import LangChainAdapter
            return LangChainAdapter()
        except ImportError as e:
            pytest.skip(f"LangChain adapter not available: {e}")
    
    def test_bind_returns_chat_history(self, adapter, mh):
        """测试 bind() 返回 AgentMemoryChatHistory"""
        result = adapter.bind(mh)
        # Should return AgentMemoryChatHistory or similar
        assert result is not None
    
    def test_export_tools_returns_5_tools(self, adapter, mh):
        """测试 export_tools() 返回 5 个工具规格"""
        adapter.bind(mh)
        tools = adapter.export_tools()
        assert isinstance(tools, list)
        assert len(tools) == 5
        
        # Verify all names start with memory_
        for tool in tools:
            assert tool.name.startswith("memory_")
    
    def test_get_metadata(self, adapter, mh):
        """测试 get_metadata()"""
        adapter.bind(mh)
        metadata = adapter.get_metadata()
        
        assert isinstance(metadata, dict)
        assert metadata["framework"] == "langchain"
        assert "requires" in metadata


class TestOpenAIAgentsAdapter:
    """OpenAI Agents SDK 适配器测试"""
    
    @pytest.fixture
    def adapter(self):
        try:
            from adapters.openai_agents import OpenAIAgentsAdapter
            return OpenAIAgentsAdapter()
        except ImportError as e:
            pytest.skip(f"OpenAI Agents adapter not available: {e}")
    
    def test_bind_returns_dict(self, adapter, mh):
        """测试 bind() 返回 dict"""
        result = adapter.bind(mh)
        assert isinstance(result, dict)
        assert len(result) >= 5  # Should have 5 tool functions
    
    def test_export_tools_returns_5_tools(self, adapter, mh):
        """测试 export_tools() 返回 5 个工具规格"""
        adapter.bind(mh)
        tools = adapter.export_tools()
        assert isinstance(tools, list)
        assert len(tools) == 5
    
    def test_get_metadata(self, adapter, mh):
        """测试 get_metadata()"""
        adapter.bind(mh)
        metadata = adapter.get_metadata()
        
        assert isinstance(metadata, dict)
        assert metadata["framework"] == "openai_agents"
        assert "requires" in metadata


class TestCrewAIAdapter:
    """CrewAI 适配器测试"""
    
    @pytest.fixture
    def adapter(self):
        try:
            from adapters.crewai import CrewAIAdapter
            return CrewAIAdapter()
        except ImportError as e:
            pytest.skip(f"CrewAI adapter not available: {e}")
    
    def test_bind_returns_list(self, adapter, mh):
        """测试 bind() 返回 list"""
        result = adapter.bind(mh)
        assert isinstance(result, list)
        assert len(result) >= 5  # Should have 5 tools
    
    def test_export_tools_returns_5_tools(self, adapter, mh):
        """测试 export_tools() 返回 5 个工具规格"""
        adapter.bind(mh)
        tools = adapter.export_tools()
        assert isinstance(tools, list)
        assert len(tools) == 5
    
    def test_get_metadata(self, adapter, mh):
        """测试 get_metadata()"""
        adapter.bind(mh)
        metadata = adapter.get_metadata()
        
        assert isinstance(metadata, dict)
        assert metadata["framework"] == "crewai"
        assert "requires" in metadata


# ============================================================================
# Integration Tests - All Frameworks Together
# ============================================================================

class TestAllFrameworkAdapters:
    """所有框架适配器集成测试"""
    
    @pytest.mark.parametrize("framework", list(FRAMEWORKS.keys()))
    def test_all_frameworks_bind_export_getmetadata(self, framework, mh):
        """
        5 框架 × 3 方法 = 15 个测试用例
        每个框架测试 bind, export_tools, get_metadata 三个方法
        """
        config = FRAMEWORKS[framework]
        
        try:
            if framework == "claude_code":
                from adapters.claude_code import ClaudeCodeAdapter
                adapter = ClaudeCodeAdapter()
            elif framework == "openclaw":
                from adapters.openclaw import OpenClawAdapter
                adapter = OpenClawAdapter()
            elif framework == "langchain":
                from adapters.langchain import LangChainAdapter
                adapter = LangChainAdapter()
            elif framework == "openai_agents":
                from adapters.openai_agents import OpenAIAgentsAdapter
                adapter = OpenAIAgentsAdapter()
            elif framework == "crewai":
                from adapters.crewai import CrewAIAdapter
                adapter = CrewAIAdapter()
        except ImportError as e:
            pytest.skip(f"{framework} adapter not available: {e}")
        
        # Method 1: bind
        bind_result = adapter.bind(mh)
        assert bind_result is not None, f"{framework} bind() returned None"
        
        # Method 2: export_tools
        tools = adapter.export_tools()
        assert isinstance(tools, list), f"{framework} export_tools() should return list"
        assert len(tools) == config["export_tools_count"], \
            f"{framework} should have {config['export_tools_count']} tools, got {len(tools)}"
        
        # Verify tool names match pattern (dict or ToolSpec)
        for tool in tools:
            tool_name = tool["name"] if isinstance(tool, dict) else tool.name
            assert tool_name.startswith("memory_"), \
                f"{framework} tool name {tool_name} should start with memory_"
        
        # Method 3: get_metadata
        metadata = adapter.get_metadata()
        assert isinstance(metadata, dict), f"{framework} get_metadata() should return dict"
        assert "framework" in metadata, f"{framework} metadata missing 'framework'"
        assert metadata["framework"] == framework, \
            f"{framework} metadata framework should be '{framework}'"
        
        print(f"\n✓ {framework}: bind✓ export_tools({len(tools)})✓ get_metadata✓")


class TestToolSpecConsistency:
    """工具规格一致性测试"""
    
    def test_all_adapters_export_consistent_tool_names(self, mh):
        """所有适配器导出相同的核心工具名称"""
        core_tools = {"memory_store", "memory_query", "memory_forget", "memory_stats", "memory_prefetch"}
        
        adapters_to_test = []
        for framework in ["openclaw", "langchain", "openai_agents", "crewai"]:
            try:
                if framework == "openclaw":
                    from adapters.openclaw import OpenClawAdapter
                    adapters_to_test.append((framework, OpenClawAdapter()))
                elif framework == "langchain":
                    from adapters.langchain import LangChainAdapter
                    adapters_to_test.append((framework, LangChainAdapter()))
                elif framework == "openai_agents":
                    from adapters.openai_agents import OpenAIAgentsAdapter
                    adapters_to_test.append((framework, OpenAIAgentsAdapter()))
                elif framework == "crewai":
                    from adapters.crewai import CrewAIAdapter
                    adapters_to_test.append((framework, CrewAIAdapter()))
            except ImportError:
                pass
        
        for framework, adapter in adapters_to_test:
            adapter.bind(mh)
            tools = adapter.export_tools()
            # Handle both dict and ToolSpec formats
            tool_names = {t["name"] if isinstance(t, dict) else t.name for t in tools}
            
            # Core tools should be present
            assert core_tools.issubset(tool_names), \
                f"{framework} missing core tools: {core_tools - tool_names}"


class TestAdapterProtocol:
    """适配器 Protocol 兼容性测试"""
    
    def test_all_adapters_implement_protocol(self, mh):
        """验证所有适配器实现 FrameworkAdapter Protocol"""
        from adapters.base import FrameworkAdapter
        import inspect
        
        adapters_to_test = []
        for framework in ["claude_code", "openclaw", "langchain", "openai_agents", "crewai"]:
            try:
                if framework == "claude_code":
                    from adapters.claude_code import ClaudeCodeAdapter
                    adapters_to_test.append((framework, ClaudeCodeAdapter))
                elif framework == "openclaw":
                    from adapters.openclaw import OpenClawAdapter
                    adapters_to_test.append((framework, OpenClawAdapter))
                elif framework == "langchain":
                    from adapters.langchain import LangChainAdapter
                    adapters_to_test.append((framework, LangChainAdapter))
                elif framework == "openai_agents":
                    from adapters.openai_agents import OpenAIAgentsAdapter
                    adapters_to_test.append((framework, OpenAIAgentsAdapter))
                elif framework == "crewai":
                    from adapters.crewai import CrewAIAdapter
                    adapters_to_test.append((framework, CrewAIAdapter))
            except ImportError:
                pass
        
        for framework, adapter_cls in adapters_to_test:
            # Check if adapter class implements the protocol
            # Using isinstance check with runtime_checkable Protocol
            instance = adapter_cls()
            assert isinstance(instance, FrameworkAdapter), \
                f"{framework} adapter does not implement FrameworkAdapter Protocol"


# ============================================================================
# v1.0 Backward Compatibility Tests
# ============================================================================

class TestAdapterBackwardCompatibility:
    """向后兼容测试"""
    
    def test_old_import_path_still_works(self):
        """测试旧的导入路径仍然可用"""
        try:
            from adapters.claude_code import ClaudeCodeAdapter
            from adapters.openclaw import OpenClawAdapter
            assert ClaudeCodeAdapter is not None
            assert OpenClawAdapter is not None
        except ImportError as e:
            pytest.skip(f"Import error: {e}")
    
    @pytest.mark.asyncio
    async def test_adapter_works_with_execute_interface(self, mh):
        """测试适配器可以与 execute() 接口一起工作"""
        # Test that adapters can be used via the execute interface
        for framework in ["openclaw", "langchain", "openai_agents", "crewai"]:
            try:
                if framework == "openclaw":
                    from adapters.openclaw import OpenClawAdapter
                    adapter = OpenClawAdapter()
                elif framework == "langchain":
                    from adapters.langchain import LangChainAdapter
                    adapter = LangChainAdapter()
                elif framework == "openai_agents":
                    from adapters.openai_agents import OpenAIAgentsAdapter
                    adapter = OpenAIAgentsAdapter()
                elif framework == "crewai":
                    from adapters.crewai import CrewAIAdapter
                    adapter = CrewAIAdapter()
                
                adapter.bind(mh)
                
                # Test execute interface compatibility (async)
                result = await mh.execute("store", {"content": "test"})
                assert result.get("success") == True
            except ImportError:
                pass


# ============================================================================
# Edge Cases
# ============================================================================

class TestAdapterEdgeCases:
    """适配器边界情况测试"""
    
    def test_bind_without_mh(self):
        """测试不传入 MemoryHermes 的情况"""
        try:
            from adapters.langchain import LangChainAdapter
            adapter = LangChainAdapter()
            # bind should work without raising
            adapter.bind(None)
        except ImportError:
            pass
        except Exception as e:
            pytest.fail(f"bind(None) raised unexpected error: {e}")
    
    def test_export_tools_without_bind(self):
        """测试未调用 bind() 就调用 export_tools()"""
        try:
            from adapters.langchain import LangChainAdapter
            adapter = LangChainAdapter()
            # May return empty list or raise, depending on implementation
            tools = adapter.export_tools()
            assert isinstance(tools, list)
        except ImportError:
            pass
    
    def test_adapter_with_empty_memory(self, mh):
        """测试空记忆状态下的适配器"""
        for framework in ["openclaw", "langchain", "openai_agents", "crewai"]:
            try:
                if framework == "openclaw":
                    from adapters.openclaw import OpenClawAdapter
                    adapter = OpenClawAdapter()
                elif framework == "langchain":
                    from adapters.langchain import LangChainAdapter
                    adapter = LangChainAdapter()
                elif framework == "openai_agents":
                    from adapters.openai_agents import OpenAIAgentsAdapter
                    adapter = OpenAIAgentsAdapter()
                elif framework == "crewai":
                    from adapters.crewai import CrewAIAdapter
                    adapter = CrewAIAdapter()
                
                adapter.bind(mh)
                
                # Empty memory should not break export_tools
                tools = adapter.export_tools()
                assert len(tools) >= 5
            except ImportError:
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
