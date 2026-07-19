"""
LLM Provider 抽象层 v2
支持 Bailian / MiniMax / OpenAI-Compatible 多 provider，可选 NewAPI 统一网关
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


def _resolve_base_url(default: str, env_var: str, key: str) -> str:
    """
    解析 base_url，优先级：
      1. 显式传入参数（已在调用端处理）
      2. 环境变量 LLM_BASE_URL（NewAPI 等统一网关）
      3. 厂商特定环境变量（MINIMAX_BASE_URL 等）
      4. 显式默认值
    """
    general = os.environ.get("LLM_BASE_URL", "").strip()
    if general:
        return general.rstrip("/")

    specific = os.environ.get(env_var, "").strip()
    if specific:
        return specific.rstrip("/")

    return default


def _resolve_api_key(*keys: str) -> str:
    """按优先级取第一个非空 key；通用 LLM_API_KEY 优先级最高。"""
    return os.environ.get("LLM_API_KEY", "").strip() or next(
        (os.environ.get(k, "").strip() for k in keys if os.environ.get(k, "").strip()),
        "",
    )


class BailianProvider:
    """
    百炼（阿里云 DashScope）LLM Provider — OpenAI 兼容格式

    通过 LLM_BASE_URL 或 BAILIAN_BASE_URL 可指向 NewAPI 等统一网关。
    """
    DEFAULT_BASE_URL = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
    DEFAULT_MODEL = "qwen3.6-plus"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 120.0,
        **kwargs,
    ):
        self.api_key = api_key or _resolve_api_key(
            "BAILIAN_API_KEY", "DASHSCOPE_API_KEY", "QWEN_API_KEY"
        )
        self.base_url = base_url or _resolve_base_url(self.DEFAULT_BASE_URL, "BAILIAN_BASE_URL", "bailian")
        self.model = model or self.DEFAULT_MODEL
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout))
        return self._client

    async def chat(self, messages: list[dict], **kwargs) -> LLMResponse:
        client = self._get_client()
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2048),
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
    MiniMax LLM Provider — 默认 OpenAI 兼容格式（api.minimaxi.com/v1）

    支持两种格式：
      - OpenAI 兼容（默认）→ api.minimaxi.com/v1/chat/completions
      - Anthropic 兼容（legacy）→ api.minimaxi.com/anthropic/v1/messages

    通过 LLM_BASE_URL / MINIMAX_BASE_URL 可指向 NewAPI 等统一网关。
    通过环境变量 MINIMAX_FORMAT=anthropic 切换到 Anthropic 格式。
    """
    DEFAULT_BASE_URL = "https://api.minimaxi.com"
    DEFAULT_MODEL = "MiniMax-M2.7-highspeed"
    DEFAULT_FORMAT = "openai"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 120.0,
        **kwargs,
    ):
        self.api_key = api_key or _resolve_api_key(
            "MINIMAX_API_KEY", "MINIMAX_CN_API_KEY"
        )
        self.base_url = base_url or _resolve_base_url(
            self.DEFAULT_BASE_URL, "MINIMAX_BASE_URL", "minimax"
        )
        self.model = model or self.DEFAULT_MODEL
        self.timeout = timeout
        self.format = (os.environ.get("MINIMAX_FORMAT", "") or self.DEFAULT_FORMAT).lower()
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout))
        return self._client

    async def chat(self, messages: list[dict], **kwargs) -> LLMResponse:
        client = self._get_client()
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 4096)

        if self.format == "anthropic":
            return await self._chat_anthropic(client, messages, temperature, max_tokens)
        return await self._chat_openai(client, messages, temperature, max_tokens)

    async def _chat_openai(self, client, messages, temperature, max_tokens) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        response = await client.post(
            f"{self.base_url}/v1/chat/completions",
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

    async def _chat_anthropic(self, client, messages, temperature, max_tokens) -> LLMResponse:
        # 转换 system message 为 user-prefix
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
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        # LLM_BASE_URL 已经把 /anthropic 后缀推上去了，但 Anthropic
        # 格式端点是 /v1/messages，OpenAI 端点是 /chat/completions。
        # 为简化：当 base_url 含 /anthropic 时直接 POST /v1/messages；
        # 否则假定已是 Anthropic 网关，直接 POST /v1/messages。
        if self.base_url.endswith("/anthropic"):
            url = f"{self.base_url}/v1/messages"
        else:
            url = f"{self.base_url}/v1/messages"
        response = await client.post(url, json=payload, headers=headers)
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
    适用于 OpenAI / vLLM / LocalAI / NewAPI 等
    """
    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    DEFAULT_MODEL = "gpt-4o"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 120.0,
        **kwargs,
    ):
        self.api_key = api_key or _resolve_api_key("OPENAI_API_KEY")
        self.base_url = base_url or _resolve_base_url(
            self.DEFAULT_BASE_URL, "OPENAI_BASE_URL", "openai"
        )
        self.model = model or self.DEFAULT_MODEL
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout))
        return self._client

    async def chat(self, messages: list[dict], **kwargs) -> LLMResponse:
        client = self._get_client()
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2048),
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


# Provider 映射（按 model 前缀）。注意：MINIMAX/MiniMax → MinimaxProvider
# 主要匹配 OpenAI 格式（更常见，向 NewAPI 兼容）。
_PROVIDER_MAP = {
    "bailian/": BailianProvider,
    "qwen": BailianProvider,
    "minimax/": MinimaxProvider,
    "MiniMax": MinimaxProvider,
    "openai/": OpenAICompatProvider,
    "gpt-": OpenAICompatProvider,
    "gpt4": OpenAICompatProvider,
}


def get_llm_provider(model: str = None, **kwargs) -> BaseLLMProvider:
    """
    工厂函数：根据 model 字符串返回对应 LLM provider

    优先级：
      1. 显式 model 字符串 → 按前缀匹配
      2. 环境变量 LLM_BASE_URL 设定 → 用该 URL，所有 provider 共用
      3. 自动检测环境变量 → 按 KEY 选择默认 provider

    示例:
        >>> p = get_llm_provider("minimax/MiniMax-M3")     # → NewAPI/直连 MiniMax
        >>> p = get_llm_provider("bailian/qwen3.6-plus")
        >>> p = get_llm_provider("gpt-4o")
        >>> p = get_llm_provider()  # 自动检测
    """
    if model is None:
        # 优先 LLM_API_KEY（NewAPI 场景）
        if os.environ.get("LLM_API_KEY") and os.environ.get("LLM_BASE_URL"):
            # 用 OpenAI 兼容格式作为默认
            model = os.environ.get("LLM_DEFAULT_MODEL", "openai/gpt-4o")
        elif os.environ.get("MINIMAX_API_KEY"):
            model = os.environ.get("MINIMAX_DEFAULT_MODEL", "minimax/MiniMax-M2.7-highspeed")
        elif os.environ.get("BAILIAN_API_KEY") or os.environ.get("DASHSCOPE_API_KEY"):
            model = os.environ.get("BAILIAN_DEFAULT_MODEL", "bailian/qwen3.6-plus")
        elif os.environ.get("OPENAI_API_KEY"):
            model = "openai/gpt-4o"
        else:
            model = "bailian/qwen3.6-plus"

    provider_class = None
    matched_prefix = None
    for prefix, cls in _PROVIDER_MAP.items():
        if model.startswith(prefix):
            provider_class = cls
            matched_prefix = prefix
            break

    if provider_class is None:
        provider_class = BailianProvider

    # 给上游送 model 名时要去掉 AgentMemory 内部前缀（如 minimax/、bailian/、openai/），
    # 因为 NewAPI 等中转渠道按全名匹配，不识别带前缀的 ID。
    upstream_model = model
    if matched_prefix and model.startswith(matched_prefix):
        upstream_model = model[len(matched_prefix):]

    return provider_class(model=upstream_model, **kwargs)


# 向后兼容
class LLMClient:
    """LLMClient 兼容层，内部调用 get_llm_provider"""
    def __init__(self, model: str = None, api_key: str = None, base_url: str = None, provider: str = None):
        self.model = model
        self._provider = get_llm_provider(
            model=model,
            api_key=api_key,
            base_url=base_url,
        )

    async def chat(self, messages: list[dict], **kwargs) -> dict:
        response = await self._provider.chat(messages, **kwargs)
        return {
            "content": response.content,
            "model": response.model,
            "usage": response.usage,
        }

    async def close(self) -> None:
        await self._provider.aclose()
