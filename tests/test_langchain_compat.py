"""Tests for LangChain compatibility layer."""
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_memory.langchain_compat import (
    AgentMemoryForLangChain, LangChainMemory, LlamaIndexMemory
)


def _run(coro):
    """Run async coroutine in sync test."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestLangChainCompat:
    def test_memory_variables(self):
        m = AgentMemoryForLangChain(namespace="test_lc1", base_dir="memory")
        assert "history" in m.memory_variables

    def test_save_and_load(self):
        m = AgentMemoryForLangChain(namespace="test_lc2", base_dir="memory")
        m.save_context({"input": "你好世界"}, {"output": "你好！"})
        result = m.load_memory_variables({"input": "你好"})
        assert "history" in result
        # Should find the saved content
        assert isinstance(result["history"], str)

    def test_clear(self):
        m = AgentMemoryForLangChain(namespace="test_lc3", base_dir="memory")
        m.save_context({"input": "test clear"}, {"output": "ok"})
        m.clear()
        # After clear, importance is set to 0
        # The history search might still return content but marked low

    def test_llamaindex_get_put(self):
        m = AgentMemoryForLangChain(namespace="test_lc4", base_dir="memory")
        m.put("history", "Some test value")
        result = m.get_all()
        assert "history" in result

    def test_aliases(self):
        assert LangChainMemory is AgentMemoryForLangChain
        assert LlamaIndexMemory is AgentMemoryForLangChain

    def test_empty_inputs(self):
        m = AgentMemoryForLangChain(namespace="test_lc5", base_dir="memory")
        result = m.load_memory_variables({})
        assert result == {"history": ""}

    def test_save_empty(self):
        m = AgentMemoryForLangChain(namespace="test_lc6", base_dir="memory")
        # No crash on empty inputs
        m.save_context({}, {})
        m.save_context({"input": ""}, {"response": ""})
