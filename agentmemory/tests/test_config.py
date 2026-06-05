"""
test_config.py — MemoryConfig 配置测试
验证 v2.0 配置默认值、字段结构和 DecayConfig 值
"""
import pytest
from agentmemory.config import (
    MemoryConfig,
    DecayConfig,
    LibraryConfig,
    TieredLogConfig,
    DataLakeConfig,
    ProvidersConfig,
)


class TestMemoryConfigDefaults:
    """测试 MemoryConfig 默认值"""

    def test_memory_config_defaults(self):
        """version == 2.0.0，有 library / decay / providers 字段"""
        config = MemoryConfig()
        assert config.version == "2.0.0"
        # 有 library 字段
        assert hasattr(config, "library")
        assert isinstance(config.library, LibraryConfig)
        # 有 decay 字段
        assert hasattr(config, "decay")
        assert isinstance(config.decay, DecayConfig)
        # 有 providers 字段
        assert hasattr(config, "providers")
        assert isinstance(config.providers, ProvidersConfig)
        # 有 datalake 字段
        assert hasattr(config, "datalake")
        assert isinstance(config.datalake, DataLakeConfig)
        # 有 tiered_log 字段
        assert hasattr(config, "tiered_log")
        assert isinstance(config.tiered_log, TieredLogConfig)

    def test_memory_config_to_dict(self):
        """to_dict 正常序列化"""
        config = MemoryConfig()
        d = config.to_dict()
        assert d["version"] == "2.0.0"
        assert "decay" in d
        assert "providers" in d

    def test_memory_config_from_dict(self):
        """from_dict 正常反序列化"""
        data = {"version": "2.0.0", "data_root": "/tmp/test"}
        config = MemoryConfig.from_dict(data)
        assert config.version == "2.0.0"
        assert config.data_root == "/tmp/test"

    def test_memory_config_validate_valid(self):
        """合法配置通过验证"""
        config = MemoryConfig()
        config.validate()  # 不抛异常

    def test_memory_config_validate_invalid_version(self):
        """不支持的版本号被拒绝"""
        config = MemoryConfig(version="1.0.0")
        with pytest.raises(ValueError, match="unsupported config version"):
            config.validate()

    def test_memory_config_validate_invalid_decay_threshold(self):
        """decay.forget_threshold 超出 [0,1] 被拒绝"""
        config = MemoryConfig()
        config.decay.forget_threshold = 1.5
        with pytest.raises(ValueError, match="forget_threshold must be 0-1"):
            config.validate()

    def test_memory_config_validate_invalid_half_life(self):
        """decay.half_life_days <= 0 被拒绝"""
        config = MemoryConfig()
        config.decay.half_life_days = 0.0
        with pytest.raises(ValueError, match="half_life_days must be positive"):
            config.validate()


class TestDecayConfigValues:
    """测试 DecayConfig 值"""

    def test_decay_config_defaults(self):
        """half_life_days == 30.0, forget_threshold == 0.2, archive_threshold == 0.5"""
        config = MemoryConfig()
        assert config.decay.half_life_days == 30.0
        assert config.decay.forget_threshold == 0.2
        assert config.decay.archive_threshold == 0.5

    def test_decay_config_custom_values(self):
        """自定义 DecayConfig 值"""
        config = MemoryConfig()
        config.decay.half_life_days = 14.0
        config.decay.forget_threshold = 0.3
        config.decay.archive_threshold = 0.6
        assert config.decay.half_life_days == 14.0
        assert config.decay.forget_threshold == 0.3
        assert config.decay.archive_threshold == 0.6

    def test_decay_config_forget_gt_archive_rejected(self):
        """forget_threshold > archive_threshold 被拒绝"""
        config = MemoryConfig()
        config.decay.forget_threshold = 0.8
        config.decay.archive_threshold = 0.3
        with pytest.raises(ValueError, match="forget_threshold .* must be <= archive_threshold"):
            config.validate()

    def test_decay_config_archive_threshold_bounds(self):
        """archive_threshold 超出 [0,1] 被拒绝"""
        config = MemoryConfig()
        config.decay.archive_threshold = -0.1
        with pytest.raises(ValueError, match="archive_threshold must be 0-1"):
            config.validate()


class TestLibraryConfig:
    """测试 LibraryConfig"""

    def test_library_config_defaults(self):
        """LibraryConfig 默认值"""
        config = MemoryConfig()
        assert config.library.enabled is True
        assert config.library.max_depth == 4
        assert isinstance(config.library.whitelist_path, str)

    def test_library_config_custom_max_depth(self):
        """max_depth 可自定义"""
        config = MemoryConfig()
        config.library.max_depth = 3
        assert config.library.max_depth == 3


class TestTieredLogConfig:
    """测试 TieredLogConfig"""

    def test_tiered_log_config_defaults(self):
        """TieredLogConfig 默认值"""
        config = MemoryConfig()
        assert config.tiered_log.enabled is True
        assert config.tiered_log.hot_ttl_seconds == 3600
        assert config.tiered_log.warm_ttl_seconds == 86400
        assert config.tiered_log.cold_ttl_seconds == 604800
        assert config.tiered_log.max_hot_size == 1000
        assert config.tiered_log.max_warm_size == 5000
        assert config.tiered_log.max_cold_size == 50000


class TestDataLakeConfig:
    """测试 DataLakeConfig"""

    def test_datalake_config_defaults(self):
        """DataLakeConfig 默认值"""
        config = MemoryConfig()
        assert config.datalake.enabled is True
        assert config.datalake.data_root == "./memory_library"
        assert config.datalake.auto_commit is True
        assert config.datalake.commit_interval_seconds == 300
