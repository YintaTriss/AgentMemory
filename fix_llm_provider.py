# -*- coding: utf-8 -*-
"""Fix llm_provider.py by truncating and writing fixed version"""

import os

content = '''"""
LLM Provider 实现
"""

import os
import json
import asyncio
import httpx
from typing import Optional, AsyncIterator, Any

from .protocols import LLMProtocol, LLMResponse


class MockLLM:
    DEFAULT_MODEL = "mock/gpt-3.5"
    
    def __init__(self, model: Optional[str] = None, **kwargs):
        self.model = model or self.DEFAULT_MODEL
    
    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        return LLMResponse(
            content=f"[Mock Response]你说:{prompt[:50]}...",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            model=self.model,
            raw={"mock": True}
        )
    
    async def stream_complete(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        response = f"[Mock Streaming]你说:{prompt[:30]}..."
        for char in response:
            yield char
            await asyncio.sleep(0.01)
    
    async def chat(self, messages: list[dict], **kwargs) -> LLMResponse:
        last_msg = messages[-1]["content"] if messages else ""
        return LLMResponse(
            content=f"[Mock Chat]你说:{last_msg[:50]}...",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            model=self.model,
            raw={"mock": True}
        )
    
    async def aclose(self) -> None:
        pass
    
    async def __aenter__(self) -> "MockLLM":
        return self
    
    async def __aexit__(self, *args) -> None:
        await self.aclose()


class OpenAILLM:
    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    DEFAULT_MODEL = "gpt-4o"
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None,
                 model: Optional[str] = None, **kwargs):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.model = model or self.DEFAULT_MODEL
        self._client: Optional[httpx.AsyncClient] = None
    
    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
        return self._client
    
    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(messages, **kwargs)
    
    async def stream_complete(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        messages = [{"role": "user", "content": prompt}]
        client = self._get_client()
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 2048)
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }
        
        async with client.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    if "choices" in chunk and len(chunk["choices"]) > 0:
                        delta = chunk["choices"][0].get("delta", {})
                        if "content" in delta:
                            yield delta["content"]
    
    async def chat(self, messages: list[dict], **kwargs) -> LLMResponse:
        client = self._get_client()
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 2048)
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        response = await client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        )
        response.raise_for_status()
        data = response.json()
        
        return LLMResponse(
            content=data["choices"][0]["message"]["content"],
            usage=data.get("usage", {}),
            model=data.get("model", self.model),
            raw=data,
            finish_reason=data["choices"][0].get("finish_reason")
        )
    
    async def aclose(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def __aenter__(self) -> "OpenAILLM":
        return self
    
    async def __aexit__(self, *args) -> None:
        await self.aclose()


class BailianLLM:
    DEFAULT_BASE_URL = "https://token-plan.cn-beijing.maas.aliyun.com/compatible-mode/v1"
    DEFAULT_MODEL = "qwen3.6-plus"
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None,
                 model: Optional[str] = None, **kwargs):
        self.api_key = api_key or os.environ.get("BAILIAN_API_KEY") or os.environ.get("DASHSCOPE_API_KEY", "")
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.model = model or self.DEFAULT_MODEL
        self._client: Optional[httpx.AsyncClient] = None
    
    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
        return self._client
    
    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(messages, **kwargs)
    
    async def stream_complete(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        messages = [{"role": "user", "content": prompt}]
        client = self._get_client()
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 2048)
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }
        
        async with client.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    if "choices" in chunk and len(chunk["choices"]) > 0:
                        delta = chunk["choices"][0].get("delta", {})
                        if "content" in delta:
                            yield delta["content"]
    
    async def chat(self, messages: list[dict], **kwargs) -> LLMResponse:
        client = self._get_client()
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 2048)
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        response = await client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        )
        response.raise_for_status()
        data = response.json()
        
        return LLMResponse(
            content=data["choices"][0]["message"]["content"],
            usage=data.get("usage", {}),
            model=data.get("model", self.model),
        
