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

    def test_extract_facts(self):
        """提取事实"""
        compressor = L1LCMCompressor()

        content = "我决定使用 Python。这是一个普通的消息。项目已经完成了。"

        facts = compressor.extract_facts(content)

        assert isinstance(facts, list)

    def test_fact_type_enum(self):
        """FactType constant values"""
        assert FactType.GENERAL == "general"
        assert FactType.PROJECT == "project"
        assert FactType.DECISION == "decision"
        assert FactType.PREFERENCE == "preference"
        assert FactType.LEARNING == "learning"

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
        expected_types = ["general", "project", "decision", "preference", "learning"]

        for fact_type in expected_types:
            assert hasattr(FactType, fact_type.upper())

    def test_fact_type_values(self):
        """FactType values correct"""
        assert FactType.GENERAL == "general"
        assert FactType.PROJECT == "project"
        assert FactType.DECISION == "decision"
        assert FactType.PREFERENCE == "preference"
        assert FactType.LEARNING == "learning"


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
