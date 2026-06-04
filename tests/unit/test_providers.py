"""
Provider 抽象层测试
测试 LLM 和 Embedder Provider 的工厂函数和实现类
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock


# 测试目标模块（使用 src 前缀，与 pytest.ini pythonpath 配置一致）
from src.providers.llm import (
    BaseLLMProvider,
    LLMResponse,
    BailianProvider,
    MinimaxProvider,
    OpenAICompatProvider,
    get_llm_provider,
)
from src.providers.embedder import (
    BaseEmbedderProvider,
    DashScopeEmbedder,
    MockEmbedder,
    get_embedder,
)


# ============================================================================
# LLM Response Tests
# ============================================================================

class TestLLMResponse:
    """测试 LLMResponse 数据类"""

    def test_llm_response_creation(self):
        """测试 LLMResponse 创建"""
        response = LLMResponse(
            content="Hello, world!",
            usage={"input_tokens": 10, "output_tokens": 20},
            raw={"id": "test"},
            model="test-model",
        )
        assert response.content == "Hello, world!"
        assert response.usage["input_tokens"] == 10
        assert response.raw["id"] == "test"
        assert response.model == "test-model"

    def test_llm_response_defaults(self):
        """测试 LLMResponse 默认值"""
        response = LLMResponse(content="Test", usage={})
        assert response.raw is None
        assert response.model == ""


# ============================================================================
# LLM Provider Tests
# ============================================================================

class TestBailianProvider:
    """测试 BailianProvider"""

    def test_bailian_provider_init(self):
        """测试 BailianProvider 初始化"""
        provider = BailianProvider(
            api_key="test-key",
            base_url="https://test.com",
            model="test-model",
        )
        assert provider.api_key == "test-key"
        assert provider.base_url == "https://test.com"
        assert provider.model == "test-model"

    def test_bailian_provider_defaults(self):
        """测试 BailianProvider 默认值"""
        provider = BailianProvider()
        assert provider.base_url == BailianProvider.DEFAULT_BASE_URL
        assert provider.model == BailianProvider.DEFAULT_MODEL

    @pytest.mark.asyncio
    async def test_bailian_provider_context_manager(self):
        """测试 BailianProvider 上下文管理器"""
        provider = BailianProvider(api_key="test")
        async with provider as p:
            assert p is provider
        # 验证关闭
        assert provider._client is None or provider._client.is_closed


class TestMinimaxProvider:
    """测试 MinimaxProvider"""

    def test_minimax_provider_init(self):
        """测试 MinimaxProvider 初始化"""
        provider = MinimaxProvider(
            api_key="test-key",
            base_url="https://test.com",
            model="MiniMax-M2",
        )
        assert provider.api_key == "test-key"
        assert provider.base_url == "https://test.com"
        assert provider.model == "MiniMax-M2"

    def test_minimax_provider_defaults(self):
        """测试 MinimaxProvider 默认值"""
        provider = MinimaxProvider()
        assert provider.base_url == MinimaxProvider.DEFAULT_BASE_URL
        assert provider.model == MinimaxProvider.DEFAULT_MODEL


class TestOpenAICompatProvider:
    """测试 OpenAICompatProvider"""

    def test_openai_provider_init(self):
        """测试 OpenAICompatProvider 初始化"""
        provider = OpenAICompatProvider(
            api_key="test-key",
            base_url="https://custom.com",
            model="gpt-4",
        )
        assert provider.api_key == "test-key"
        assert provider.base_url == "https://custom.com"
        assert provider.model == "gpt-4"

    def test_openai_provider_defaults(self):
        """测试 OpenAICompatProvider 默认值"""
        provider = OpenAICompatProvider()
        assert provider.base_url == OpenAICompatProvider.DEFAULT_BASE_URL
        assert provider.model == OpenAICompatProvider.DEFAULT_MODEL


# ============================================================================
# LLM Provider Factory Tests
# ============================================================================

class TestLLMProviderFactory:
    """测试 LLM Provider 工厂函数"""

    def test_get_llm_provider_bailian_prefix(self):
        """测试 bailian/ 前缀返回 BailianProvider"""
        provider = get_llm_provider("bailian/qwen3.6-plus")
        assert isinstance(provider, BailianProvider)

    def test_get_llm_provider_qwen_prefix(self):
        """测试 qwen 前缀返回 BailianProvider"""
        provider = get_llm_provider("qwen3.6-plus")
        assert isinstance(provider, BailianProvider)

    def test_get_llm_provider_minimax_prefix(self):
        """测试 minimax/ 前缀返回 MinimaxProvider"""
        provider = get_llm_provider("minimax/MiniMax-M2.7-highspeed")
        assert isinstance(provider, MinimaxProvider)

    def test_get_llm_provider_minimax_model(self):
        """测试 MiniMax 模型名返回 MinimaxProvider"""
        provider = get_llm_provider("MiniMax-M2.7-highspeed")
        assert isinstance(provider, MinimaxProvider)

    def test_get_llm_provider_openai_prefix(self):
        """测试 openai/ 前缀返回 OpenAICompatProvider"""
        provider = get_llm_provider("openai/gpt-4o")
        assert isinstance(provider, OpenAICompatProvider)

    def test_get_llm_provider_gpt_prefix(self):
        """测试 gpt- 前缀返回 OpenAICompatProvider"""
        provider = get_llm_provider("gpt-4o")
        assert isinstance(provider, OpenAICompatProvider)

    def test_get_llm_provider_unknown_defaults_to_bailian(self):
        """测试未知模型默认返回 BailianProvider"""
        provider = get_llm_provider("unknown-model")
        assert isinstance(provider, BailianProvider)

    def test_get_llm_provider_passes_kwargs(self):
        """测试 kwargs 传递给 provider"""
        provider = get_llm_provider(
            "bailian/test",
            api_key="my-key",
            base_url="https://custom.com",
        )
        assert provider.api_key == "my-key"
        assert provider.base_url == "https://custom.com"


# ============================================================================
# MockEmbedder Tests
# ============================================================================

class TestMockEmbedder:
    """测试 MockEmbedder"""

    def test_mock_embedder_init(self):
        """测试 MockEmbedder 初始化"""
        embedder = MockEmbedder(dimensions=512, seed=123)
        assert embedder.dimensions == 512
        assert embedder.seed == 123

    def test_mock_embedder_default_dimensions(self):
        """测试 MockEmbedder 默认维度"""
        embedder = MockEmbedder()
        assert embedder.dimensions == MockEmbedder.DEFAULT_DIMENSIONS

    @pytest.mark.asyncio
    async def test_mock_embedder_single(self):
        """测试 MockEmbedder 单条 embedding"""
        embedder = MockEmbedder(dimensions=128, seed=42)
        vector = await embedder.embed_single("Hello world")
        assert len(vector) == 128
        # 验证是确定性的
        vector2 = await embedder.embed_single("Hello world")
        assert vector == vector2

    @pytest.mark.asyncio
    async def test_mock_embedder_batch(self):
        """测试 MockEmbedder 批量 embedding"""
        embedder = MockEmbedder(dimensions=128, seed=42)
        vectors = await embedder.embed(["Hello", "World"])
        assert len(vectors) == 2
        assert all(len(v) == 128 for v in vectors)

    @pytest.mark.asyncio
    async def test_mock_embedder_different_texts_different_vectors(self):
        """测试不同文本产生不同向量"""
        embedder = MockEmbedder(dimensions=128, seed=42)
        v1 = await embedder.embed_single("Hello")
        v2 = await embedder.embed_single("World")
        assert v1 != v2

    @pytest.mark.asyncio
    async def test_mock_embedder_empty_list(self):
        """测试 MockEmbedder 空列表"""
        embedder = MockEmbedder()
        vectors = await embedder.embed([])
        assert vectors == []

    @pytest.mark.asyncio
    async def test_mock_embedder_normalized(self):
        """测试 MockEmbedder 向量归一化"""
        embedder = MockEmbedder(dimensions=128, seed=42)
        vector = await embedder.embed_single("test")
        # L2 归一化后模为 1
        norm = sum(v**2 for v in vector) ** 0.5
        assert abs(norm - 1.0) < 1e-6

    @pytest.mark.asyncio
    async def test_mock_embedder_context_manager(self):
        """测试 MockEmbedder 上下文管理器"""
        embedder = MockEmbedder()
        async with embedder as e:
            assert e is embedder
        # Mock 无需清理，验证不报错
        await embedder.aclose()


# ============================================================================
# DashScopeEmbedder Tests
# ============================================================================

class TestDashScopeEmbedder:
    """测试 DashScopeEmbedder"""

    def test_dashscope_embedder_init(self):
        """测试 DashScopeEmbedder 初始化"""
        embedder = DashScopeEmbedder(
            api_key="test-key",
            base_url="https://test.com",
            model="text-embedding-v4",
            dimensions=2048,
        )
        assert embedder.api_key == "test-key"
        assert embedder.base_url == "https://test.com"
        assert embedder.model == "text-embedding-v4"
        assert embedder.dimensions == 2048

    def test_dashscope_embedder_defaults(self):
        """测试 DashScopeEmbedder 默认值"""
        embedder = DashScopeEmbedder()
        assert embedder.base_url == DashScopeEmbedder.DEFAULT_BASE_URL
        assert embedder.model == DashScopeEmbedder.DEFAULT_MODEL
        assert embedder.dimensions == DashScopeEmbedder.DEFAULT_DIMENSIONS


# ============================================================================
# Embedder Provider Factory Tests
# ============================================================================

class TestEmbedderProviderFactory:
    """测试 Embedder Provider 工厂函数"""

    def test_get_embedder_with_no_api_key_returns_mock(self):
        """测试无 API key 时返回 MockEmbedder"""
        with patch.dict("os.environ", {}, clear=True):
            embedder = get_embedder()
            assert isinstance(embedder, MockEmbedder)

    def test_get_embedder_with_dashscope_key_returns_dashscope(self):
        """测试有 DASHSCOPE_API_KEY 时返回 DashScopeEmbedder"""
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "test-key"}):
            embedder = get_embedder()
            assert isinstance(embedder, DashScopeEmbedder)
            assert embedder.api_key == "test-key"

    def test_get_embedder_with_bailian_key_returns_dashscope(self):
        """测试有 BAILIAN_API_KEY 时返回 DashScopeEmbedder"""
        with patch.dict("os.environ", {"BAILIAN_API_KEY": "test-key"}):
            embedder = get_embedder()
            assert isinstance(embedder, DashScopeEmbedder)

    def test_get_embedder_passes_model(self):
        """测试 model 参数传递"""
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "test-key"}):
            embedder = get_embedder(model="text-embedding-v4")
            assert embedder.model == "text-embedding-v4"

    def test_get_embedder_passes_dimensions(self):
        """测试 dimensions 参数传递"""
        with patch.dict("os.environ", {}, clear=True):
            embedder = get_embedder(dimensions=2048)
            assert embedder.dimensions == 2048


# ============================================================================
# Protocol Compliance Tests
# ============================================================================

class TestProtocolCompliance:
    """测试 Provider 是否符合协议"""

    def test_bailian_provider_is_base_llm_provider(self):
        """测试 BailianProvider 符合 BaseLLMProvider 协议"""
        provider = BailianProvider(api_key="test")
        assert isinstance(provider, BaseLLMProvider)

    def test_minimax_provider_is_base_llm_provider(self):
        """测试 MinimaxProvider 符合 BaseLLMProvider 协议"""
        provider = MinimaxProvider(api_key="test")
        assert isinstance(provider, BaseLLMProvider)

    def test_openai_provider_is_base_llm_provider(self):
        """测试 OpenAICompatProvider 符合 BaseLLMProvider 协议"""
        provider = OpenAICompatProvider(api_key="test")
        assert isinstance(provider, BaseLLMProvider)

    def test_dashscope_embedder_is_base_embedder_provider(self):
        """测试 DashScopeEmbedder 符合 BaseEmbedderProvider 协议"""
        embedder = DashScopeEmbedder(api_key="test")
        assert isinstance(embedder, BaseEmbedderProvider)

    def test_mock_embedder_is_base_embedder_provider(self):
        """测试 MockEmbedder 符合 BaseEmbedderProvider 协议"""
        embedder = MockEmbedder()
        assert isinstance(embedder, BaseEmbedderProvider)


# ============================================================================
# Integration Tests
# ============================================================================

class TestProviderIntegration:
    """测试 Provider 集成"""

    @pytest.mark.asyncio
    async def test_mock_embedder_integration_with_vector_store(self):
        """测试 MockEmbedder 与 VectorStore 集成"""
        from src.L3_vector_store import VectorStore
        import tempfile
        import os

        embedder = MockEmbedder(dimensions=128, seed=42)
        
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = f.name
        
        try:
            store = VectorStore(
                storage_path=temp_path,
                embedding_dims=128,
                embedder_provider=embedder,
            )
            
            # 验证 store 使用了 embedder
            assert store._embedder_provider is embedder
            
            # 存储一条记忆
            memory_id = store.store("Test memory content")
            assert memory_id is not None
            
            # 验证记忆已存储
            entry = store.get(memory_id)
            assert entry is not None
            assert entry["content"] == "Test memory content"
            assert len(entry["id"]) > 0
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_factory_returns_correct_provider_type(self):
        """测试工厂函数返回正确的 provider 类型"""
        # 测试各种 model 前缀
        test_cases = [
            ("minimax/MiniMax-M2", MinimaxProvider),
            ("bailian/qwen3", BailianProvider),
            ("openai/gpt-4", OpenAICompatProvider),
            ("qwen3.6-plus", BailianProvider),
            ("gpt-4o", OpenAICompatProvider),
        ]
        
        for model, expected_type in test_cases:
            provider = get_llm_provider(model)
            assert isinstance(provider, expected_type), f"Model {model} should return {expected_type}"


# ============================================================================
# Provider Close Tests
# ============================================================================

class TestProviderClose:
    """测试 Provider 关闭行为"""

    @pytest.mark.asyncio
    async def test_bailian_provider_close(self):
        """测试 BailianProvider 关闭"""
        provider = BailianProvider(api_key="test")
        provider._client = AsyncMock()
        await provider.aclose()
        assert provider._client is None

    @pytest.mark.asyncio
    async def test_minimax_provider_close(self):
        """测试 MinimaxProvider 关闭"""
        provider = MinimaxProvider(api_key="test")
        provider._client = AsyncMock()
        await provider.aclose()
        assert provider._client is None

    @pytest.mark.asyncio
    async def test_openai_provider_close(self):
        """测试 OpenAICompatProvider 关闭"""
        provider = OpenAICompatProvider(api_key="test")
        provider._client = AsyncMock()
        await provider.aclose()
        assert provider._client is None

    @pytest.mark.asyncio
    async def test_dashscope_embedder_close(self):
        """测试 DashScopeEmbedder 关闭"""
        embedder = DashScopeEmbedder(api_key="test")
        embedder._client = AsyncMock()
        await embedder.aclose()
        assert embedder._client is None
