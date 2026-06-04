"""
config.py 单元测试
"""

import pytest
import json
import tempfile
import os
from pathlib import Path


class TestConfig:
    """Config 配置管理测试"""
    
    def test_config_load_default(self):
        """测试默认配置加载"""
        from config import Config
        cfg = Config()
        
        # 验证默认配置项
        assert cfg.get("embedding.model") == "text-embedding-v3"
        assert cfg.get("embedding.dimensions") == 1024
        assert cfg.get("decay.threshold") == 0.3
        assert cfg.get("decay.half_life_days") == 14.0
    
    def test_config_load_custom_file(self, temp_dir):
        """测试自定义配置文件加载"""
        from config import Config
        
        config_path = os.path.join(temp_dir, "test_config.json")
        custom_config = {
            "embedding": {
                "model": "text-embedding-v4",
                "dimensions": 2048
            },
            "decay": {
                "threshold": 0.5,
                "half_life_days": 7.0
            }
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(custom_config, f)
        
        cfg = Config(config_path)
        
        assert cfg.get("embedding.model") == "text-embedding-v4"
        assert cfg.get("embedding.dimensions") == 2048
        assert cfg.get("decay.threshold") == 0.5
        assert cfg.get("decay.half_life_days") == 7.0
    
    def test_config_get_nested(self):
        """测试嵌套配置获取"""
        from config import Config
        cfg = Config()
        
        # 获取嵌套值
        embedding = cfg.get("embedding.model")
        assert embedding == "text-embedding-v3"
        
        hybrid = cfg.get("hybrid_search.vector_weight")
        assert hybrid == 0.6
    
    def test_config_get_with_default(self):
        """测试获取不存在的配置项时返回默认值"""
        from config import Config
        cfg = Config()
        
        result = cfg.get("nonexistent.key", default="default_value")
        assert result == "default_value"
    
    def test_config_set(self):
        """测试配置设置"""
        from config import Config
        cfg = Config()
        
        cfg.set("test.key", "test_value")
        assert cfg.get("test.key") == "test_value"
    
    def test_config_set_nested(self):
        """测试嵌套配置设置"""
        from config import Config
        cfg = Config()
        
        cfg.set("custom.embedding.model", "custom-model")
        assert cfg.get("custom.embedding.model") == "custom-model"
    
    def test_config_to_dict(self):
        """测试配置转字典"""
        from config import Config
        cfg = Config()
        
        config_dict = cfg.to_dict()
        assert isinstance(config_dict, dict)
        assert "embedding" in config_dict
        assert "decay" in config_dict
    
    def test_config_save(self, temp_dir):
        """测试配置保存"""
        from config import Config
        
        config_path = os.path.join(temp_dir, "saved_config.json")
        cfg = Config()
        
        cfg.set("test.save", "saved_value")
        cfg.save(config_path)
        
        # 重新加载验证
        cfg2 = Config(config_path)
        assert cfg2.get("test.save") == "saved_value"
    
    def test_config_validation(self):
        """测试配置验证"""
        from config import Config
        cfg = Config()
        
        # 验证必要配置项存在
        assert cfg.get("embedding.provider") is not None
        assert cfg.get("llm.provider") is not None
        assert cfg.get("decay.enabled") is not None
    
    def test_config_type_conversion(self):
        """测试配置类型转换"""
        from config import Config
        cfg = Config()
        
        # 确保数值类型正确
        vector_weight = cfg.get("hybrid_search.vector_weight")
        assert isinstance(vector_weight, (int, float))
        assert 0 <= vector_weight <= 1


class TestConfigEdgeCases:
    """Config 边界情况测试"""
    
    def test_empty_config_file(self, temp_dir):
        """测试空配置文件"""
        from config import Config
        
        config_path = os.path.join(temp_dir, "empty_config.json")
        with open(config_path, 'w') as f:
            f.write("{}")
        
        cfg = Config(config_path)
        # 应该使用默认配置
        assert cfg.get("embedding.model") is not None
    
    def test_invalid_json_config(self, temp_dir):
        """测试无效 JSON 配置文件"""
        from config import Config
        
        config_path = os.path.join(temp_dir, "invalid_config.json")
        with open(config_path, 'w') as f:
            f.write("{ invalid json }")
        
        # 应该回退到默认配置
        cfg = Config(config_path)
        assert cfg.get("embedding.model") == "text-embedding-v3"
    
    def test_missing_config_file(self):
        """测试缺失配置文件"""
        from config import Config
        
        # 不存在的配置文件，应该使用默认配置
        cfg = Config("/nonexistent/path/config.json")
        assert cfg.get("embedding.model") == "text-embedding-v3"
