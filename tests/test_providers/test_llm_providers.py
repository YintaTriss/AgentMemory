"""
LLM Provider 测试

测试 LLM Provider 实现：
- Protocol 满足性
- MockLLM 功能
- 环境变量检测
"""

import pytest
import os
import asyncio
from unittest.mock import patch

from agentmemory.v2_providers import (
    MockLLM,
    LLMProtocol,
)


class TestMockLLM:
    """MockLLM 测试"""
    
    def test_protocol_satisfaction(self):
        """测试满足 LLMProtocol"""
        llm = MockLLM()
        assert isinstance(llm, LLMProtocol)
    
    def test_has_complete_method(self):
        """测试有 complete 方法"""
        llm = MockLLM()
        assert hasattr(llm, "complete")
    
    def test_has_stream_complete_method(self):
        """测试有 stream_complete 方法"""
        llm = MockLLM()
        assert hasattr(llm, "stream_complete")
    
    def test_has_chat_method(self):
        """测试有 chat 方法"""
        llm = MockLLM()
        assert hasattr(llm, "chat")
    
    @pytest.mark.asyncio
    async def test_complete_returns_response(self):
        """测试 complete 返回响应"""
        llm = MockLLM()
        response = await llm.complete("Hello")
        
        assert response is not None
        assert hasattr(response, "content")
        assert hasattr(response, "model")
    
    @pytest.mark.asyncio
    async def test_chat_returns_response(self):
        """测试 chat 返回响应"""
        llm = MockLLM()
        messages = [{"role": "user", "content": "Hello"}]
        response = await llm.chat(messages)
        
        assert response is not None
        assert hasattr(response, "content")
    
    @pytest.mark.asyncio
    async def test_stream_complete_yields_tokens(self):
        """测试流式完成产生 token"""
        llm = MockLLM()
        tokens = []
        
        async for token in llm.stream_complete("Hello"):
            tokens.append(token)
        
        assert len(tokens) > 0
        full_content = "".join(tokens)
        assert len(full_content) > 0
    
    @pytest.mark.asyncio
    async def test_aclose(self):
        """测试关闭方法"""
        llm = MockLLM()
        await llm.aclose()
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """测试上下文管理器"""
        llm = MockLLM()
        async with llm:
            response = await llm.complete("test")
        
        assert response is not None


class TestMockLLMResponse:
    """MockLLM 响应测试"""
    
    @pytest.mark.asyncio
    async def test_response_has_required_fields(self):
        """测试响应包含必需字段"""
        llm = MockLLM()
        response = await llm.complete("test")
        
        assert hasattr(response, "content")
        assert hasattr(response, "usage")
        assert hasattr(response, "model")
        assert hasattr(response, "finish_reason")
    
    @pytest.mark.asyncio
    async def test_usage_structure(self):
        """测试 usage 结构"""
        llm = MockLLM()
        response = await llm.complete("test")
        
        assert isinstance(response.usage, dict)


class TestMockLLMDeterminism:
    """MockLLM 确定性测试"""
    
    @pytest.mark.asyncio
    async def test_same_prompt_same_response(self):
        """测试相同提示产生相同响应"""
        llm = MockLLM()
        
        response1 = await llm.complete("What is 2+2?")
        response2 = await llm.complete("What is 2+2?")
        
        assert response1.content == response2.content


class TestLLMProviderDetection:
    """LLM Provider 环境检测测试"""
    
    def test_list_llm_providers(self):
        """测试列出 LLM Provider"""
        from agentmemory.v2_providers import list_available_providers
        
        providers = list_available_providers()
        assert "mock" in providers
