"""
AgentMemory AI 模块

提供 AI 辅助功能：
- 分类推荐（AutoClassifier）
"""

from .classifier import (
    ClassificationRecommendation,
    AutoClassifyResult,
    AutoClassifier,
    RuleBasedClassifier,
    PROMPT_TEMPLATE,
)

__all__ = [
    "ClassificationRecommendation",
    "AutoClassifyResult",
    "AutoClassifier",
    "RuleBasedClassifier",
    "PROMPT_TEMPLATE",
]
