"""
test_decay_engine.py — 衰减引擎测试
验证 score 公式、recency 半衰期、forget_threshold
"""
import pytest
import math
from datetime import datetime, timezone, timedelta
from agentmemory.decay_engine import (
    DecayEngine,
    DecayPolicy,
    DecayScore,
    create_decay_engine,
)


class TestDecayScoreFormula:
    """测试衰减分数公式"""

    def test_decay_score_formula(self):
        """score = log(1+access)^0.3 * importance^0.4 * recency^0.3
        验证几何乘积公式（各因子正确计算）"""
        # 创建一个 entry，使用固定的过去时间以便验证
        now = datetime.now(timezone.utc)
        entry = {
            "id": "test-001",
            "importance": 0.5,
            "access_count": 9,   # log(1+9) = log(10) ≈ 2.303
            "last_accessed": now.isoformat(),
            "created_at": now.isoformat(),
        }

        engine = DecayEngine(policy=DecayPolicy())
        score = engine.calculate_score(entry)

        # 验证返回 DecayScore 对象
        assert isinstance(score, DecayScore)
        assert isinstance(score.score, float)
        assert 0.0 <= score.score <= 1.0

        # 验证 components 包含三个因子
        assert "access_factor" in score.components
        assert "importance_factor" in score.components
        assert "recency_factor" in score.components

        # 验证公式计算
        # access_factor = log(1+9)^0.3 = log(10)^0.3 ≈ 2.303^0.3
        expected_access = math.log1p(9) ** 0.3
        assert abs(score.components["access_factor"] - expected_access) < 1e-6

        # importance_factor = 0.5^0.4
        expected_importance = 0.5 ** 0.4
        assert abs(score.components["importance_factor"] - expected_importance) < 1e-6

        # recency_factor: age=0, recency=1.0, 1.0^0.3 = 1.0
        expected_recency = 1.0
        assert abs(score.components["recency_factor"] - expected_recency) < 1e-6

    def test_decay_score_zero_access(self):
        """access_count=0 时，log(1+0)=0，access_factor=0^0.3=0"""
        now = datetime.now(timezone.utc)
        entry = {
            "id": "test-zero-access",
            "importance": 0.5,
            "access_count": 0,
            "last_accessed": now.isoformat(),
            "created_at": now.isoformat(),
        }
        engine = DecayEngine()
        score = engine.calculate_score(entry)
        # log(1+0) = 0, 0^0.3 在数学上为 0
        assert score.components["access_factor"] == 0.0

    def test_decay_score_high_importance(self):
        """importance=1.0 时，importance_factor = 1.0^0.4 = 1.0"""
        now = datetime.now(timezone.utc)
        entry = {
            "id": "test-high-imp",
            "importance": 1.0,
            "access_count": 0,
            "last_accessed": now.isoformat(),
            "created_at": now.isoformat(),
        }
        engine = DecayEngine()
        score = engine.calculate_score(entry)
        assert abs(score.components["importance_factor"] - 1.0) < 1e-6


class TestRecencyHalfLife:
    """测试时效性半衰期"""

    def test_recency_half_life(self):
        """half_life_days=30, 30天后 recency == 0.5, 60天后 == 0.25"""
        now = datetime.now(timezone.utc)

        # 30天前
        entry_30d = {
            "id": "test-30d",
            "importance": 0.5,
            "access_count": 0,
            "last_accessed": (now - timedelta(days=30)).isoformat(),
            "created_at": (now - timedelta(days=30)).isoformat(),
        }
        engine_30 = DecayEngine(policy=DecayPolicy(half_life_days=30.0))
        score_30 = engine_30.calculate_score(entry_30d)
        # recency = 0.5^(30/30) = 0.5^1 = 0.5
        assert abs(score_30.components["recency_factor"] - 0.5) < 1e-6

        # 60天前
        entry_60d = {
            "id": "test-60d",
            "importance": 0.5,
            "access_count": 0,
            "last_accessed": (now - timedelta(days=60)).isoformat(),
            "created_at": (now - timedelta(days=60)).isoformat(),
        }
        score_60 = engine_30.calculate_score(entry_60d)
        # recency = 0.5^(60/30) = 0.5^2 = 0.25
        assert abs(score_60.components["recency_factor"] - 0.25) < 1e-6

    def test_recency_half_life_14_days(self):
        """half_life_days=14, 14天后 recency == 0.5"""
        now = datetime.now(timezone.utc)
        entry = {
            "id": "test-14d",
            "importance": 0.5,
            "access_count": 0,
            "last_accessed": (now - timedelta(days=14)).isoformat(),
            "created_at": (now - timedelta(days=14)).isoformat(),
        }
        engine = DecayEngine(policy=DecayPolicy(half_life_days=14.0))
        score = engine.calculate_score(entry)
        # recency = 0.5^(14/14) = 0.5^1 = 0.5
        assert abs(score.components["recency_factor"] - 0.5) < 1e-6

    def test_recency_new_entry(self):
        """新条目（0天）recency == 1.0"""
        now = datetime.now(timezone.utc)
        entry = {
            "id": "test-new",
            "importance": 0.5,
            "access_count": 0,
            "last_accessed": now.isoformat(),
            "created_at": now.isoformat(),
        }
        engine = DecayEngine(policy=DecayPolicy(half_life_days=30.0))
        score = engine.calculate_score(entry)
        assert abs(score.components["recency_factor"] - 1.0) < 1e-6


class TestForgetThreshold:
    """测试遗忘阈值"""

    def test_forget_threshold(self):
        """score < 0.2 应该被标记为遗忘"""
        now = datetime.now(timezone.utc)
        # 非常老的、低重要性的条目
        entry = {
            "id": "test-forget",
            "importance": 0.1,
            "access_count": 0,
            "last_accessed": (now - timedelta(days=365)).isoformat(),
            "created_at": (now - timedelta(days=365)).isoformat(),
        }
        engine = DecayEngine(
            policy=DecayPolicy(
                half_life_days=30.0,
                forget_threshold=0.2,
            )
        )
        score = engine.calculate_score(entry)
        assert score.score < 0.2
        assert engine.should_forget(score) is True

    def test_should_not_forget_high_score(self):
        """高分不应被遗忘"""
        now = datetime.now(timezone.utc)
        entry = {
            "id": "test-keep",
            "importance": 1.0,
            "access_count": 100,
            "last_accessed": now.isoformat(),
            "created_at": now.isoformat(),
        }
        engine = DecayEngine(policy=DecayPolicy(half_life_days=30.0))
        score = engine.calculate_score(entry)
        assert score.score >= 0.2
        assert engine.should_forget(score) is False

    def test_should_archive(self):
        """0.2 <= score < 0.5 应被归档"""
        now = datetime.now(timezone.utc)
        # 中等时间、中等重要性的条目
        entry = {
            "id": "test-archive",
            "importance": 0.3,
            "access_count": 5,
            "last_accessed": (now - timedelta(days=60)).isoformat(),
            "created_at": (now - timedelta(days=60)).isoformat(),
        }
        engine = DecayEngine(
            policy=DecayPolicy(
                half_life_days=30.0,
                forget_threshold=0.2,
                archive_threshold=0.5,
            )
        )
        score = engine.calculate_score(entry)
        assert engine.should_archive(score) is True

    def test_run_decay_check(self):
        """run_decay_check 分类正确"""
        now = datetime.now(timezone.utc)
        entries = [
            {
                "id": "forget-me",
                "importance": 0.1,
                "access_count": 0,
                "last_accessed": (now - timedelta(days=365)).isoformat(),
                "created_at": (now - timedelta(days=365)).isoformat(),
            },
            {
                "id": "keep-me",
                "importance": 1.0,
                "access_count": 100,
                "last_accessed": now.isoformat(),
                "created_at": now.isoformat(),
            },
        ]
        engine = DecayEngine(
            policy=DecayPolicy(half_life_days=30.0, forget_threshold=0.2, archive_threshold=0.5)
        )
        result = engine.run_decay_check(entries)
        assert "forget" in result
        assert "archive" in result
        assert "keep" in result


class TestDecayPolicy:
    """测试 DecayPolicy"""

    def test_decay_policy_defaults(self):
        """DecayPolicy 默认权重"""
        policy = DecayPolicy()
        assert policy.weight_access == 0.3
        assert policy.weight_importance == 0.4
        assert policy.weight_recency == 0.3
        assert policy.half_life_days == 30.0
        assert policy.forget_threshold == 0.2
        assert policy.archive_threshold == 0.5

    def test_calculate_score_from_fields(self):
        """calculate_score_from_fields 直接从字段计算"""
        now = datetime.now(timezone.utc)
        engine = DecayEngine(policy=DecayPolicy(half_life_days=30.0))
        score = engine.calculate_score_from_fields(
            importance=0.5,
            access_count=0,
            last_accessed=now.isoformat(),
            created_at=now.isoformat(),
        )
        assert 0.0 <= score <= 1.0


class TestCreateDecayEngine:
    """测试 create_decay_engine 工厂函数"""

    def test_create_decay_engine_defaults(self):
        """默认参数创建引擎"""
        engine = create_decay_engine()
        assert engine.policy.half_life_days == 30.0
        assert engine.forget_threshold == 0.2
        assert engine.archive_threshold == 0.5

    def test_create_decay_engine_custom(self):
        """自定义参数创建引擎"""
        engine = create_decay_engine(half_life_days=14.0, forget_threshold=0.3, archive_threshold=0.6)
        assert engine.policy.half_life_days == 14.0
        assert engine.forget_threshold == 0.3
        assert engine.archive_threshold == 0.6
