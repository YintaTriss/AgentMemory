"""
LLM Provider 抽象层 v1
支持 Bailian / Minimax / OpenAI-Compatible 多 provider 可切换
"""

import os
import json
import httpx
from typing import Any, Optional, Protocol, runtime_checkable

from dataclasses import dataclass


@dataclass
class LLMResponse:
    """LLM 调用响应"""
    content: str
    usage: dict
    raw: Any | None = None
    model: str = ""


@runtime_checkable
class BaseLLMProvider(Protocol):
    """LLM Provider 协议"""

    async def chat(self, messages: list[dict], **kwargs) -> LLMResponse:
        """发送对话请求，返回 LLMResponse"""
        ...

    async def aclose(self) -> None:
        """关闭 provider，释放资源"""
        ...


class BailianProvider:
    """
    百炼（阿里云 DashScope）LLM Provider
    使用 openai-completions API 风格
    """

    DEFAULT_BASE_URL = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
    DEFAULT_MODEL = "qwen3.6-plus"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ):
        self.api_key = api_key or os.environ.get("BAILIAN_API_KEY") or os.environ.get("DASHSCOPE_API_KEY", "")
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.model = model or self.DEFAULT_MODEL
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
        return self._client

    async def chat(self, messages: list[dict], **kwargs) -> LLMResponse:
        """调用百炼 LLM"""
        client = self._get_client()
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 2048)

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        response = await client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        data = response.json()

        return LLMResponse(
            content=data["choices"][0]["message"]["content"],
            usage=data.get("usage", {}),
            raw=data,
            model=data.get("model", self.model),
        )

    async def aclose(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "BailianProvider":
        return self

    async def __aexit__(self, *args) -> None:
        await self.aclose()


class MinimaxProvider:
    """
    MiniMax LLM Provider
    使用 anthropic-messages API 风格
    """

    DEFAULT_BASE_URL = "https://api.minimaxi.com/anthropic"
    DEFAULT_MODEL = "MiniMax-M2.7-highspeed"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ):
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.model = model or self.DEFAULT_MODEL
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
        return self._client

    async def chat(self, messages: list[dict], **kwargs) -> LLMResponse:
        """调用 MiniMax LLM"""
        client = self._get_client()
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 4096)

        # 转换 messages 格式为 Anthropic 风格
        anthropic_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                anthropic_messages.append({"role": "user", "content": f"[System] {msg['content']}"})
            else:
                anthropic_messages.append(msg)

        payload = {
            "model": self.model,
            "messages": anthropic_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        response = await client.post(
            f"{self.base_url}/v1/messages",
            json=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "x-bm-client-flag": "promptize",
                "anthropic-version": "2023-06-01",
            },
        )
        response.raise_for_status()
        data = response.json()

        return LLMResponse(
            content=data["content"][0]["text"],
            usage={
                "input_tokens": data.get("usage", {}).get("input_tokens", 0),
                "output_tokens": data.get("usage", {}).get("output_tokens", 0),
            },
            raw=data,
            model=data.get("model", self.model),
        )

    async def aclose(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "MinimaxProvider":
        return self

    async def __aexit__(self, *args) -> None:
        await self.aclose()


class OpenAICompatProvider:
    """
    通用 OpenAI 兼容 LLM Provider
    适用于 OpenAI / vLLM / LocalAI 等支持 OpenAI Chat Completions API 的后端
    """

    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    DEFAULT_MODEL = "gpt-4o"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.model = model or self.DEFAULT_MODEL
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
        return self._client

    async def chat(self, messages: list[dict], **kwargs) -> LLMResponse:
        """调用 OpenAI 兼容 LLM"""
        client = self._get_client()
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 2048)

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        response = await client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        data = response.json()

        return LLMResponse(
            content=data["choices"][0]["message"]["content"],
            usage=data.get("usage", {}),
            raw=data,
            model=data.get("model", self.model),
        )

    async def aclose(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "OpenAICompatProvider":
        return self

    async def __aexit__(self, *args) -> None:
        await self.aclose()


# Provider 映射表（按 model 前缀）
_PROVIDER_MAP = {
    "bailian/": BailianProvider,
    "qwen": BailianProvider,  # qwen 系列默认走百炼
    "minimax/": MinimaxProvider,
    "MiniMax": MinimaxProvider,  # MiniMax 系列
    "openai/": OpenAICompatProvider,
    "gpt-": OpenAICompatProvider,  # GPT 系列
    "gpt4": OpenAICompatProvider,
}


def get_llm_provider(model: str = None, **kwargs) -> BaseLLMProvider:
    """
    工厂函数：根据 model 字符串返回对应 LLM provider
    
    Args:
        model: 模型 ID（如 "minimax/MiniMax-M2.7-highspeed" 或 "qwen3.6-plus"）
              若为 None，根据环境变量自动检测
        **kwargs: 传递给 provider 的额外参数（api_key, base_url 等）
    
    Returns:
        BaseLLMProvider 实例
    
    Examples:
        >>> provider = get_llm_provider("minimax/MiniMax-M2.7-highspeed")
        >>> provider = get_llm_provider("qwen3.6-plus")
        >>> provider = get_llm_provider("openai/gpt-4o")
    """
    # 自动检测 model
    if model is None:
        if os.environ.get("MINIMAX_API_KEY"):
            model = "minimax/MiniMax-M2.7-highspeed"
        elif os.environ.get("BAILIAN_API_KEY") or os.environ.get("DASHSCOPE_API_KEY"):
            model = "bailian/qwen3.6-plus"
        elif os.environ.get("OPENAI_API_KEY"):
            model = "openai/gpt-4o"
        else:
            model = "bailian/qwen3.6-plus"  # 默认
    
    # 根据前缀匹配 provider
    provider_class = None
    for prefix, cls in _PROVIDER_MAP.items():
        if model.startswith(prefix):
            provider_class = cls
            break
    
    # 默认使用 BailianProvider
    if provider_class is None:
        provider_class = BailianProvider
    
    return provider_class(model=model, **kwargs)


# 向后兼容：保留 LLMClient 作为兼容层
class LLMClient:
    """
    LLMClient 兼容层，内部调用 BailianProvider
    保留向后兼容，不推荐新代码使用
    """
    
    def __init__(self, model: str = None, api_key: str = None, base_url: str = None, provider: str = None):
        self.model = model
        self._provider = get_llm_provider(
            model=model,
            api_key=api_key,
            base_url=base_url,
        )
    
    async def chat(self, messages: list[dict], **kwargs) -> dict:
        """兼容旧接口，返回 dict 而非 LLMResponse"""
        response = await self._provider.chat(messages, **kwargs)
        return {
            "content": response.content,
            "model": response.model,
            "usage": response.usage,
        }
    
    async def close(self) -> None:
        await self._provider.aclose()
