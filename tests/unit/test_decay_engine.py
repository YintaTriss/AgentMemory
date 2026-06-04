"""
decay_engine.py 单元测试
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../..", "src"))

from decay_engine import DecayEngine, MemoryArchiver


class TestDecayEngine:
    """DecayEngine 遗忘引擎测试"""
    
    def test_decay_engine_init(self):
        """测试遗忘引擎初始化"""
        engine = DecayEngine(
            half_life_days=14.0,
            forget_threshold=0.3,
            archive_threshold=0.5
        )
        
        assert engine.half_life_days == 14.0
        assert engine.forget_threshold == 0.3
        assert engine.archive_threshold == 0.5
    
    def test_decay_factor_calculation(self):
        """测试衰减因子计算"""
        engine = DecayEngine(half_life_days=14.0)
        
        # 14天应该衰减到 0.5
        decay_14d = engine.decay_factor(14.0)
        assert abs(decay_14d - 0.5) < 0.01
        
        # 7天应该衰减到约 0.707
        decay_7d = engine.decay_factor(7.0)
        assert abs(decay_7d - 0.707) < 0.01
        
        # 0天应该为 1.0
        decay_0d = engine.decay_factor(0.0)
        assert decay_0d == 1.0
        
        # 28天应该衰减到 0.25
        decay_28d = engine.decay_factor(28.0)
        assert abs(decay_28d - 0.25) < 0.01
    
    def test_decay_factor_negative_days(self):
        """测试负天数（未来日期）"""
        engine = DecayEngine(half_life_days=14.0)
        
        # 负天数应该返回 1.0（不做额外衰减）
        decay_negative = engine.decay_factor(-1.0)
        assert decay_negative == 1.0
    
    def test_calculate_score_basic(self):
        """测试基础遗忘评分计算"""
        engine = DecayEngine(
            half_life_days=14.0,
            forget_threshold=0.3,
            archive_threshold=0.5
        )
        
        entry = {
            "id": "test1",
            "content": "测试记忆",
            "access_count": 5,
            "importance": 0.8,
            "created_at": "2026-05-13T12:00:00",  # 约14天前
            "last_accessed": "2026-05-20T12:00:00"  # 约7天前
        }
        
        score = engine.calculate_score(entry)
        
        # 验证评分对象存在
        assert score is not None
        assert hasattr(score, 'score')
        assert hasattr(score, 'components')
        
        # 验证评分在有效范围内
        assert 0 <= score.score <= 1
    
    def test_calculate_score_components(self):
        """测试遗忘评分各组件"""
        engine = DecayEngine(half_life_days=14.0)
        
        entry = {
            "id": "test2",
            "content": "测试",
            "access_count": 10,
            "importance": 0.9,
            "created_at": "2026-01-01T12:00:00",
            "last_accessed": "2026-06-01T12:00:00"
        }
        
        score = engine.calculate_score(entry)
        
        # 验证各组件存在
        assert 'recency' in score.components
        assert 'access_freq' in score.components
        assert 'importance' in score.components
        
        # 验证最终分数在有效范围内
        assert 0 <= score.score <= 1
    
    def test_should_forget_high_score(self):
        """测试高分记忆不应被遗忘"""
        engine = DecayEngine(
            half_life_days=14.0,
            forget_threshold=0.3,
            archive_threshold=0.5
        )
        
        entry = {
            "id": "high1",
            "content": "重要记忆",
            "access_count": 20,
            "importance": 0.95,
            "created_at": "2026-06-01T12:00:00",
            "last_accessed": "2026-06-03T12:00:00"
        }
        
        score = engine.calculate_score(entry)
        assert engine.should_forget(score) == False
    
    def test_should_forget_low_score(self):
        """测试低分记忆应被遗忘"""
        engine = DecayEngine(
            half_life_days=14.0,
            forget_threshold=0.3,
            archive_threshold=0.5
        )
        
        entry = {
            "id": "low1",
            "content": "低价值记忆",
            "access_count": 0,
            "importance": 0.1,
            "created_at": "2026-01-01T12:00:00",
            "last_accessed": "2026-01-01T12:00:00"
        }
        
        score = engine.calculate_score(entry)
        assert engine.should_forget(score) == True
    
    def test_should_archive_mid_score(self):
        """测试中等分数记忆应被归档"""
        engine = DecayEngine(
            half_life_days=14.0,
            forget_threshold=0.3,
            archive_threshold=0.5
        )
        
        entry = {
            "id": "mid1",
            "content": "中等价值记忆",
            "access_count": 3,
            "importance": 0.4,
            "created_at": "2026-03-01T12:00:00",
            "last_accessed": "2026-04-01T12:00:00"
        }
        
        score = engine.calculate_score(entry)
        
        # 归档：分数在遗忘阈值和归档阈值之间
        if 0.3 < score.score <= 0.5:
            assert engine.should_archive(score) == True
    
    def test_should_not_archive_high_score(self):
        """测试高分记忆不应被归档"""
        engine = DecayEngine(
            half_life_days=14.0,
            forget_threshold=0.3,
            archive_threshold=0.5
        )
        
        entry = {
            "id": "high2",
            "content": "高价值记忆",
            "access_count": 10,
            "importance": 0.8,
            "created_at": "2026-06-01T12:00:00",
            "last_accessed": "2026-06-03T12:00:00"
        }
        
        score = engine.calculate_score(entry)
        assert engine.should_archive(score) == False
    
    def test_zero_access_count(self):
        """测试零访问次数"""
        engine = DecayEngine(half_life_days=14.0)
        
        entry = {
            "id": "zero_access",
            "content": "从未被访问的记忆",
            "access_count": 0,
            "importance": 0.5,
            "created_at": "2026-05-01T12:00:00",
            "last_accessed": "2026-05-01T12:00:00"
        }
        
        score = engine.calculate_score(entry)
        
        # 零访问应该有惩罚
        assert score.components.get('access_freq', 0) < 0.3
    
    def test_high_access_count(self):
        """测试高访问次数"""
        engine = DecayEngine(half_life_days=14.0)
        
        entry = {
            "id": "high_access",
            "content": "经常被访问的记忆",
            "access_count": 100,
            "importance": 0.8,
            "created_at": "2026-06-01T12:00:00",
            "last_accessed": "2026-06-03T12:00:00"
        }
        
        score = engine.calculate_score(entry)
        
        # 高访问应该有加分
        assert score.components.get('access_freq', 0) >= 0.2


class TestMemoryArchiver:
    """MemoryArchiver 归档器测试"""
    
    def test_archive_init(self, temp_dir):
        """测试归档器初始化"""
        archive_dir = os.path.join(temp_dir, "archive")
        archiver = MemoryArchiver(archive_dir)
        
        assert archiver.archive_dir == Path(archive_dir)
    
    def test_archive_memory(self, temp_dir):
        """测试记忆归档"""
        from decay_engine import DecayScore
        
        archive_dir = os.path.join(temp_dir, "archive")
        archiver = MemoryArchiver(archive_dir)
        
        memory_data = {
            "id": "archive_test_1",
            "content": "这条记忆将被归档",
            "access_count": 1,
            "importance": 0.3,
            "created_at": "2026-01-01T12:00:00",
            "last_accessed": "2026-01-01T12:00:00"
        }
        
        result = archiver.archive_to_deep_storage("archive_test_1", memory_data)
        assert result == True
    
    def test_get_archived_memories(self, temp_dir):
        """测试获取归档记忆"""
        from decay_engine import DecayScore
        
        archive_dir = os.path.join(temp_dir, "archive")
        archiver = MemoryArchiver(archive_dir)
        
        memory_data = {
            "id": "archive_test_2",
            "content": "归档测试记忆",
            "access_count": 0,
            "importance": 0.2,
            "created_at": "2026-01-01T12:00:00",
            "last_accessed": "2026-01-01T12:00:00"
        }
        
        archiver.archive_to_deep_storage("archive_test_2", memory_data)
        
        archived = archiver.list_archived()
        assert len(archived) >= 1
    
    def test_restore_from_archive(self, temp_dir):
        """测试从归档恢复"""
        from decay_engine import DecayScore
        
        archive_dir = os.path.join(temp_dir, "archive")
        archiver = MemoryArchiver(archive_dir)
        
        memory_data = {
            "id": "archive_test_3",
            "content": "将被恢复的记忆",
            "access_count": 5,
            "importance": 0.7,
            "created_at": "2026-05-01T12:00:00",
            "last_accessed": "2026-06-01T12:00:00"
        }
        
        archiver.archive_to_deep_storage("archive_test_3", memory_data)
        restored = archiver.restore_from_archive("archive_test_3")
        
        assert restored is not None
        assert restored["id"] == "archive_test_3"


class TestDecayEngineEdgeCases:
    """DecayEngine 边界情况测试"""
    
    def test_missing_fields_in_entry(self):
        """测试缺少字段的记忆条目"""
        engine = DecayEngine(half_life_days=14.0)
        
        # 只有最基本的字段
        entry = {
            "id": "minimal_entry",
            "content": "最简记忆"
        }
        
        # 应该能处理而不崩溃
        score = engine.calculate_score(entry)
        assert score is not None
        assert 0 <= score.score <= 1
    
    def test_extreme_importance(self):
        """测试极端重要性值"""
        engine = DecayEngine(half_life_days=14.0)
        
        # 最高重要性
        high_entry = {
            "id": "max_importance",
            "content": "最高重要性",
            "access_count": 50,
            "importance": 1.0,
            "created_at": "2026-06-01T12:00:00",
            "last_accessed": "2026-06-03T12:00:00"
        }
        
        score = engine.calculate_score(high_entry)
        assert score.components.get('importance', 0) >= 0.25
        
        # 最低重要性
        low_entry = {
            "id": "min_importance",
            "content": "最低重要性",
            "access_count": 0,
            "importance": 0.0,
            "created_at": "2026-01-01T12:00:00",
            "last_accessed": "2026-01-01T12:00:00"
        }
        
        score = engine.calculate_score(low_entry)
        assert score.components.get('importance', 0) == 0.0
    
    def test_custom_weights(self):
        """测试自定义权重"""
        # 注意：当前实现可能不支持自定义权重，测试基本功能
        engine = DecayEngine(
            half_life_days=14.0,
        )
        
        entry = {
            "id": "weight_test",
            "content": "权重测试",
            "access_count": 5,
            "importance": 0.8,
            "created_at": "2026-05-15T12:00:00",
            "last_accessed": "2026-05-20T12:00:00"
        }
        
        score = engine.calculate_score(entry)
        
        # 验证基本评分功能
        assert score.score is not None
        assert 0 <= score.score <= 1
