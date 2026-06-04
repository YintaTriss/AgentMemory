"""
性能基准测试: 适配器绑定延迟

验收标准: 5 框架 bind 各 < 100ms
"""

import pytest
import sys
import os
import time
import tempfile
import shutil
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../..", "src"))


class MockMemoryHermes:
    """Mock MemoryHermes for adapter testing"""
    
    def __init__(self):
        self._memories = {}
    
    async def store(self, content: str, metadata: dict = None, importance: float = 0.5) -> str:
        import uuid
        return f"mem_{uuid.uuid4().hex[:12]}"
    
    async def query(self, query: str, limit: int = 5, filters: dict = None):
        return []
    
    def get_stats(self):
        return {"total_memories": 0}
    
    def prefetch(self, query: str):
        pass
    
    def get_prefetched(self, query: str):
        return None
    
    async def forget(self, memory_id: str, permanent: bool = False):
        return True
    
    async def execute(self, action: str, params: dict = None):
        return {"success": True}


# Framework configurations
FRAMEWORKS = {
    "claude_code": {
        "module": "adapters.claude_code",
        "class": "ClaudeCodeAdapter",
        "expected_return": "FastMCP",
    },
    "openclaw": {
        "module": "adapters.openclaw",
        "class": "OpenClawAdapter",
        "expected_return": "OpenClawAdapter",
    },
    "langchain": {
        "module": "adapters.langchain",
        "class": "LangChainAdapter",
        "expected_return": "AgentMemoryChatHistory",
    },
    "openai_agents": {
        "module": "adapters.openai_agents",
        "class": "OpenAIAgentsAdapter",
        "expected_return": "dict",
    },
    "crewai": {
        "module": "adapters.crewai",
        "class": "CrewAIAdapter",
        "expected_return": "list",
    },
}


@pytest.fixture
def mh():
    """Create mock MemoryHermes for testing"""
    return MockMemoryHermes()


@pytest.mark.benchmark
class TestPerfAdapterBind:
    """适配器绑定性能基准测试"""
    
    @pytest.mark.parametrize("framework", list(FRAMEWORKS.keys()))
    def test_bind_latency(self, framework, mh):
        """
        验收标准: 每个框架 bind 操作 < 100ms
        
        测试每个框架适配器的 bind() 方法性能
        """
        config = FRAMEWORKS[framework]
        
        try:
            # Lazy import
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
            pytest.skip(f"Cannot import {framework} adapter: {e}")
        
        # Warm up
        try:
            adapter.bind(mh)
        except:
            pass
        
        # Measure bind latency
        latencies = []
        for _ in range(10):
            # Re-create adapter for each iteration
            if framework == "claude_code":
                adapter = ClaudeCodeAdapter()
            elif framework == "openclaw":
                adapter = OpenClawAdapter()
            elif framework == "langchain":
                adapter = LangChainAdapter()
            elif framework == "openai_agents":
                adapter = OpenAIAgentsAdapter()
            elif framework == "crewai":
                adapter = CrewAIAdapter()
            
            start = time.perf_counter()
            result = adapter.bind(mh)
            end = time.perf_counter()
            latencies.append((end - start) * 1000)
        
        avg_latency = sum(latencies) / len(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
        
        print(f"\n=== {framework} Bind Performance ===")
        print(f"Avg: {avg_latency:.2f}ms (limit: 100ms)")
        print(f"P95: {p95_latency:.2f}ms")
        print(f"Min: {min(latencies):.2f}ms")
        print(f"Max: {max(latencies):.2f}ms")
        
        # Assert acceptance criteria
        assert avg_latency < 100, f"{framework} bind latency {avg_latency:.2f}ms exceeds 100ms limit"
    
    @pytest.mark.parametrize("framework", list(FRAMEWORKS.keys()))
    def test_export_tools_latency(self, framework, mh):
        """
        测试 export_tools() 方法性能
        """
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
            pytest.skip(f"Cannot import {framework} adapter: {e}")
        
        # Bind first
        adapter.bind(mh)
        
        # Measure export_tools latency
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            tools = adapter.export_tools()
            end = time.perf_counter()
            latencies.append((end - start) * 1000)
        
        avg_latency = sum(latencies) / len(latencies)
        
        print(f"\n=== {framework} export_tools Performance ===")
        print(f"Avg: {avg_latency:.2f}ms")
        
        # Should be very fast (< 5ms)
        assert avg_latency < 5, f"{framework} export_tools latency {avg_latency:.2f}ms too high"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
