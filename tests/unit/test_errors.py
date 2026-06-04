"""
测试 MemoryError 体系
验证所有异常类的实例化和错误传播
"""
import pytest
from src.errors import (
    MemoryError,
    ConfigError,
    ProviderError,
    StorageError,
    ValidationError,
    NotFoundError,
    PermissionError,
    RateLimitError,
)


class TestMemoryError:
    """测试 MemoryError 基类"""
    
    def test_basic_instantiation(self):
        """基本实例化"""
        err = MemoryError("test message")
        assert err.message == "test message"
        assert err.code == "E000"
        assert err.context == {}
    
    def test_with_code_override(self):
        """自定义错误码"""
        err = MemoryError("test", code="E999")
        assert err.code == "E999"
    
    def test_with_context(self):
        """带上下文的错误"""
        err = MemoryError("test", context={"key": "value"})
        assert err.context == {"key": "value"}
    
    def test_str_representation(self):
        """字符串表示"""
        err = MemoryError("test message", code="E000")
        assert "[E000] test message" in str(err)
    
    def test_error_propagation(self):
        """错误传播"""
        err = MemoryError("outer")
        try:
            raise err
        except MemoryError as e:
            assert e.message == "outer"


class TestConfigError:
    """测试 ConfigError (E001)"""
    
    def test_code_is_e001(self):
        """错误码为 E001"""
        err = ConfigError("config failed")
        assert err.code == "E001"
    
    def test_inheritance(self):
        """继承自 MemoryError"""
        err = ConfigError("test")
        assert isinstance(err, MemoryError)


class TestProviderError:
    """测试 ProviderError (E002)"""
    
    def test_code_is_e002(self):
        """错误码为 E002"""
        err = ProviderError("provider failed")
        assert err.code == "E002"
    
    def test_inheritance(self):
        """继承自 MemoryError"""
        err = ProviderError("test")
        assert isinstance(err, MemoryError)


class TestStorageError:
    """测试 StorageError (E003)"""
    
    def test_code_is_e003(self):
        """错误码为 E003"""
        err = StorageError("storage failed")
        assert err.code == "E003"
    
    def test_inheritance(self):
        """继承自 MemoryError"""
        err = StorageError("test")
        assert isinstance(err, MemoryError)


class TestValidationError:
    """测试 ValidationError (E004)"""
    
    def test_code_is_e004(self):
        """错误码为 E004"""
        err = ValidationError("validation failed")
        assert err.code == "E004"
    
    def test_inheritance(self):
        """继承自 MemoryError"""
        err = ValidationError("test")
        assert isinstance(err, MemoryError)


class TestNotFoundError:
    """测试 NotFoundError (E005)"""
    
    def test_code_is_e005(self):
        """错误码为 E005"""
        err = NotFoundError("not found")
        assert err.code == "E005"
    
    def test_inheritance(self):
        """继承自 MemoryError"""
        err = NotFoundError("test")
        assert isinstance(err, MemoryError)


class TestPermissionError:
    """测试 PermissionError (E006)"""
    
    def test_code_is_e006(self):
        """错误码为 E006"""
        err = PermissionError("permission denied")
        assert err.code == "E006"
    
    def test_inheritance(self):
        """继承自 MemoryError"""
        err = PermissionError("test")
        assert isinstance(err, MemoryError)


class TestRateLimitError:
    """测试 RateLimitError (E007)"""
    
    def test_code_is_e007(self):
        """错误码为 E007"""
        err = RateLimitError("rate limited")
        assert err.code == "E007"
    
    def test_inheritance(self):
        """继承自 MemoryError"""
        err = RateLimitError("test")
        assert isinstance(err, MemoryError)
