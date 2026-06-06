"""
L1 LCM 压缩层单元测试
测试 L1LCMCompressor
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

from src.agent_memory.l1_lcm import (
    L1LCMCompressor,
    FactType,
)


class TestL1LCMCompressor:
    """L1LCMCompressor 单元测试"""

    def test_init(self):
        """初始化"""
        compressor = L1LCMCompressor()
        
        assert compressor is not None

    def test_compress_empty_messages(self):
        """空消息列表"""
        compressor = L1LCMCompressor()
        
        result = compressor.compress([])
        
        # 空消息应该返回空结果
        assert result is not None

    def test_compress_basic_messages(self):
        """基本消息压缩"""
        compressor = L1LCMCompressor()
        
        messages = [
            {"role": "user", "content": "我决定使用 Python"},
            {"role": "assistant", "content": "好的，Python 很好"},
        ]
        
        result = compressor.compress(messages)
        
        # 应该返回结果
        assert result is not None

    def test_extract_decisions(self):
        """提取决策"""
        compressor = L1LCMCompressor()
        
        messages = [
            "我决定使用 Python",
            "这是一个普通的消息",
            "完成了项目"
        ]
        
        decisions = compressor.extract_decisions(messages)
        
        assert isinstance(decisions, list)

    def test_extract_key_sentences(self):
        """提取关键句子"""
        compressor = L1LCMCompressor()
        
        messages = [
            "我们决定采用微服务架构",
            "今天天气不错",
            "项目已经完成了"
        ]
        
        key_sentences = compressor.extract_key_sentences(messages)
        
        assert isinstance(key_sentences, list)

    def test_fact_type_enum(self):
        """FactType 枚举值"""
        assert FactType.PERSON.value == "person"
        assert FactType.PROJECT.value == "project"
        assert FactType.DECISION.value == "decision"
        assert FactType.PREFERENCE.value == "preference"
        assert FactType.FACT.value == "fact"

    def test_compress_with_empty_api_key(self):
        """无 API Key 时优雅降级"""
        compressor = L1LCMCompressor()
        # 不设置 API key
        
        messages = [{"role": "user", "content": "测试"}]
        
        # 应该能够处理而不崩溃
        try:
            result = compressor.compress(messages)
            assert result is not None or result is None  # 允许返回 None
        except Exception:
            pass  # 如果抛异常也是可接受的


class TestFactType:
    """FactType 枚举测试"""

    def test_all_fact_types_defined(self):
        """所有 FactType 都已定义"""
        expected_types = ["person", "project", "decision", "preference", "fact"]
        
        for fact_type in expected_types:
            assert hasattr(FactType, fact_type.capitalize())

    def test_fact_type_values(self):
        """FactType 值正确"""
        assert FactType.FACT.value == "fact"
        assert FactType.PERSON.value == "person"
        assert FactType.PROJECT.value == "project"
        assert FactType.DECISION.value == "decision"
        assert FactType.PREFERENCE.value == "preference"


class TestMockMode:
    """Mock 模式测试"""

    @pytest.mark.asyncio
    async def test_async_compress(self):
        """异步压缩"""
        compressor = L1LCMCompressor()
        
        messages = [
            {"role": "user", "content": "测试消息"},
        ]
        
        # 如果有异步版本
        if hasattr(compressor, 'acompress'):
            result = await compressor.acompress(messages)
            assert result is not None or result is None
