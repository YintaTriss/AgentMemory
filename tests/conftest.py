"""
AgentMemory v2.0 测试配置和共享 Fixtures

统一管理所有测试的 fixtures，确保测试隔离、可重复和无副作用。
"""

import os
import sys
import json
import asyncio
import tempfile
import shutil
from pathlib import Path
from typing import Generator, AsyncGenerator
from unittest.mock import AsyncMock, Mock

import pytest

# ==================== 路径配置 ====================

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
# AgentMemory 源码目录
AGENTMEMORY_SRC = PROJECT_ROOT / "agentmemory"

# 添加到 Python 路径
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(AGENTMEMORY_SRC) not in sys.path:
    sys.path.insert(0, str(AGENTMEMORY_SRC))


# ==================== 异步事件循环 Fixtures ====================

@pytest.fixture(scope="session")
def event_loop_policy():
    """设置事件循环策略"""
    return asyncio.get_event_loop_policy()


@pytest.fixture
async def event_loop():
    """为每个测试创建新的事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ==================== 临时目录 Fixtures ====================

@pytest.fixture
def tmp_workspace(tmp_path) -> Path:
    """
    临时工作空间目录
    
    每个测试使用独立的临时目录，测试结束后自动清理。
    """
    workspace = tmp_path / "test_workspace"
    workspace.mkdir(exist_ok=True)
    yield workspace
    # 清理
    if workspace.exists():
        shutil.rmtree(workspace, ignore_errors=True)


@pytest.fixture
def tmp_memory_dir(tmp_workspace) -> Path:
    """
    临时记忆存储目录
    
    创建 memory 子目录用于模拟持久化存储。
    """
    memory_dir = tmp_workspace / "memory"
    memory_dir.mkdir(exist_ok=True)
    yield memory_dir
    # 清理
    if memory_dir.exists():
        shutil.rmtree(memory_dir, ignore_errors=True)


@pytest.fixture
def tmp_vectorstore_path(tmp_workspace) -> Path:
    """临时 VectorStore 文件路径"""
    return tmp_workspace / "test_vector.usearch"


@pytest.fixture
def tmp_library_index_path(tmp_workspace) -> Path:
    """临时图书馆索引文件路径"""
    return tmp_workspace / ".library_index.json"


# ==================== Mock Providers Fixtures ====================

class MockEmbedder:
    """
    Mock Embedder - 确定性 hash 向量
    
    用于测试，无 API Key 依赖。
    """
    
    def __init__(self, dimensions: int = 384):
        self._dimensions = dimensions
        self._model = "mock-embedder-v1"
    
    @property
    def dimensions(self) -> int:
        return self._dimensions
    
    @property
    def model(self) -> str:
        return self._model
    
    def embed(self, text: str) -> list[float]:
        """单文本嵌入"""
        import hashlib
        if not text:
            return [0.0] * self._dimensions
        
        hash_bytes = hashlib.sha256(text.encode("utf-8")).digest()
        vector = []
        for i in range(self._dimensions):
            byte_idx = (i * 2) % len(hash_bytes)
            high_byte = hash_bytes[byte_idx]
            low_byte = hash_bytes[(byte_idx + 1) % len(hash_bytes)]
            value = ((high_byte << 8) | low_byte) / 65535.0
            vector.append(value)
        
        # L2 归一化
        magnitude = sum(v * v for v in vector) ** 0.5
        if magnitude > 0:
            vector = [v / magnitude for v in vector]
        
        return vector
    
    async def embed_async(self, text: str) -> list[float]:
        """异步单文本嵌入"""
        await asyncio.sleep(0)
        return self.embed(text)
    
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量文本嵌入"""
        if not texts:
            return []
        return [self.embed(text) for text in texts]
    
    async def embed_batch_async(self, texts: list[str]) -> list[list[float]]:
        """异步批量文本嵌入"""
        await asyncio.sleep(0)
        return self.embed_batch(texts)


class MockLLMProvider:
    """
    Mock LLM Provider - 用于测试
    
    返回预定义的响应。
    """
    
    def __init__(
        self,
        response_content: str = "Mock LLM response",
        model: str = "mock-model"
    ):
        self._response_content = response_content
        self._model = model
        self._call_count = 0
    
    @property
    def model(self) -> str:
        return self._model
    
    @property
    def call_count(self) -> int:
        return self._call_count
    
    def chat(self, messages: list[dict]) -> dict:
        """同步聊天"""
        self._call_count += 1
        return {
            "content": self._response_content,
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20
            },
            "model": self._model,
        }
    
    async def chat_async(self, messages: list[dict]) -> dict:
        """异步聊天"""
        await asyncio.sleep(0)
        return self.chat(messages)
    
    async def stream_complete(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
        """流式补全"""
        for chunk in self._response_content.split():
            yield chunk + " "
    
    async def aclose(self) -> None:
        """清理资源"""
        pass


@pytest.fixture
def mock_embedder() -> MockEmbedder:
    """标准 Mock Embedder（384维）"""
    return MockEmbedder(dimensions=384)


@pytest.fixture
def mock_embedder_1536() -> MockEmbedder:
    """1536维 Mock Embedder"""
    return MockEmbedder(dimensions=1536)


@pytest.fixture
def mock_llm_provider() -> MockLLMProvider:
    """标准 Mock LLM Provider"""
    return MockLLMProvider()


@pytest.fixture
def mock_llm_with_response() -> callable:
    """创建带自定义响应的 Mock LLM Provider 工厂"""
    def factory(response_content: str = "test response", model: str = "test-model") -> MockLLMProvider:
        return MockLLMProvider(response_content=response_content, model=model)
    return factory


# ==================== 测试数据 Fixtures ====================

@pytest.fixture
def sample_texts() -> list[str]:
    """示例文本列表"""
    return [
        "今天学习了机器学习中的神经网络概念",
        "神经网络的核心是反向传播算法",
        "深度学习在图像识别领域有广泛应用",
        "Python 是一种广泛使用的编程语言",
        "人工智能正在改变我们的生活方式",
    ]


@pytest.fixture
def sample_query() -> str:
    """示例查询文本"""
    return "神经网络 深度学习"


@pytest.fixture
def sample_vectors(mock_embedder, sample_texts) -> list[list[float]]:
    """为示例文本生成的向量"""
    return mock_embedder.embed_batch(sample_texts)


@pytest.fixture
def sample_metadata() -> dict:
    """示例元数据"""
    return {
        "source": "test",
        "category": "learning",
        "tags": ["AI", "机器学习"],
        "importance": 0.75,
        "language": "zh-CN",
    }


@pytest.fixture
def sample_vector_entries(mock_embedder, sample_texts, sample_metadata) -> list:
    """示例 VectorEntry 列表"""
    from agentmemory.providers.protocols import VectorEntry
    
    entries = []
    for i, (text, vector) in enumerate(zip(sample_texts, mock_embedder.embed_batch(sample_texts))):
        entry = VectorEntry(
            id=f"memory-{i}",
            vector=vector,
            metadata={
                **sample_metadata,
                "content": text,
                "index": i,
            }
        )
        entries.append(entry)
    
    return entries


@pytest.fixture
def sample_category_tree() -> dict:
    """示例分类树"""
    return {
        "root": {
            "children": ["技术", "生活", "工作"],
        },
        "技术": {
            "children": ["编程", "AI", "硬件"],
            "parent": "root",
        },
        "编程": {
            "children": ["Python", "JavaScript", "Go"],
            "parent": "技术",
        },
        "Python": {
            "parent": "编程",
        },
        "AI": {
            "children": ["机器学习", "深度学习"],
            "parent": "技术",
        },
        "机器学习": {
            "parent": "AI",
        },
        "深度学习": {
            "parent": "AI",
        },
        "JavaScript": {
            "parent": "编程",
        },
        "Go": {
            "parent": "编程",
        },
        "硬件": {
            "parent": "技术",
        },
        "生活": {
            "children": ["饮食", "运动"],
            "parent": "root",
        },
        "饮食": {
            "parent": "生活",
        },
        "运动": {
            "parent": "生活",
        },
        "工作": {
            "parent": "root",
        },
    }


# ==================== 配置 Fixtures ====================

@pytest.fixture
def embedder_config() -> dict:
    """Embedder 配置"""
    return {
        "model": "mock-hash-v1",
        "dimensions": 384,
        "batch_size": 32,
    }


@pytest.fixture
def vectorstore_config(tmp_vectorstore_path) -> dict:
    """VectorStore 配置"""
    return {
        "path": str(tmp_vectorstore_path),
        "dimensions": 384,
    }


@pytest.fixture
def search_config(tmp_memory_dir, tmp_vectorstore_path, tmp_library_index_path) -> dict:
    """SearchEngine 配置"""
    return {
        "memory_dir": str(tmp_memory_dir),
        "vectorstore_path": str(tmp_vectorstore_path),
        "library_index_path": str(tmp_library_index_path),
    }


# ==================== 搜索相关 Fixtures ====================

@pytest.fixture
def sample_memory_entries(sample_texts, sample_metadata, mock_embedder) -> list:
    """示例 MemoryEntry 列表"""
    from agentmemory.search.search_engine import MemoryEntry
    
    entries = []
    for i, text in enumerate(sample_texts):
        entry = MemoryEntry(
            id=f"mem-{i}",
            content=text,
            metadata={
                **sample_metadata,
                "index": i,
            },
            vector=mock_embedder.embed(text),
            score=0.0,
        )
        entries.append(entry)
    
    return entries


# ==================== 辅助工具 Fixtures ====================

@pytest.fixture
def assert_with_retry():
    """
    带重试的断言辅助函数
    
    用于异步操作的结果验证。
    """
    async def _assert_with_retry(
        coro,
        condition: callable,
        max_attempts: int = 10,
        delay: float = 0.1,
    ):
        """重试断言直到条件满足或超时"""
        for attempt in range(max_attempts):
            result = await coro
            if condition(result):
                return result
            if attempt < max_attempts - 1:
                await asyncio.sleep(delay)
        
        raise AssertionError(
            f"Condition not met after {max_attempts} attempts. "
            f"Last result: {result}"
        )
    
    return _assert_with_retry


@pytest.fixture
def wait_for_condition():
    """
    等待条件满足的辅助函数
    
    用于等待异步状态变化。
    """
    async def _wait_for_condition(
        condition: callable,
        timeout: float = 5.0,
        poll_interval: float = 0.1,
    ):
        """等待条件满足或超时"""
        import time
        start = time.time()
        while time.time() - start < timeout:
            if condition():
                return True
            await asyncio.sleep(poll_interval)
        
        raise TimeoutError(f"Condition not met within {timeout}s")
    
    return _wait_for_condition


# ==================== 环境清理 Fixtures ====================

@pytest.fixture(autouse=True)
def cleanup_env():
    """测试后清理环境变量"""
    original_env = os.environ.copy()
    yield
    # 恢复原始环境
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def clean_memory_dir(tmp_memory_dir):
    """确保内存目录干净"""
    # 清空目录
    for item in tmp_memory_dir.iterdir():
        if item.is_file():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)
    yield tmp_memory_dir


# ==================== 导入辅助 ====================

@pytest.fixture
def import_agentmemory():
    """导入 agentmemory 模块的辅助函数"""
    def _import(name: str):
        return __import__(f"agentmemory.{name}", fromlist=[name.split('.')[-1]])
    return _import
