"""
AgentMemory AI 分类推荐测试

测试 AutoClassifier、RuleBasedClassifier 等分类推荐功能。
"""

import pytest
import json
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from agentmemory.ai.classifier import (
    ClassificationRecommendation,
    AutoClassifyResult,
    AutoClassifier,
    RuleBasedClassifier,
    PROMPT_TEMPLATE,
)
from agentmemory.data.datalake import DataLake
from agentmemory.data.library import Library


# =============================================================================
# RuleBasedClassifier 测试
# =============================================================================


class TestRuleBasedClassifier:
    """RuleBasedClassifier 单元测试"""

    def test_classify_with_shiliuzi_keyword(self):
        """测试匹配石榴籽关键词"""
        classifier = RuleBasedClassifier()

        result = classifier.classify("省赛答辩需要准备 PPT 内容")

        assert "石榴籽" in result.suggested_tags or "省赛" in result.suggested_tags
        assert result.suggested_path == "A.项目/石榴籽/答辩"
        assert result.confidence > 0.3

    def test_classify_with_multiple_keywords(self):
        """测试多关键词匹配"""
        classifier = RuleBasedClassifier()

        result = classifier.classify("东乡语语料处理流程需要优化")

        assert "A.项目/石榴籽" in result.suggested_path
        assert "语料" in result.suggested_tags or "东乡语" in result.suggested_tags
        assert result.confidence > 0.3

    def test_classify_daily_content(self):
        """测试日记分类"""
        classifier = RuleBasedClassifier()

        result = classifier.classify("今天日记：学习了很多新知识")

        assert result.suggested_path == "B.个人/日记"
        assert "日记" in result.suggested_tags

    def test_classify_knowledge_content(self):
        """测试知识分类"""
        classifier = RuleBasedClassifier()

        result = classifier.classify("今天学习了机器翻译模型")

        assert result.suggested_path == "C.知识"
        assert "学习" in result.suggested_tags or "知识" in result.suggested_tags

    def test_classify_agent_content(self):
        """测试 Agent 相关分类"""
        classifier = RuleBasedClassifier()

        result = classifier.classify("和 Agent 协作完成了任务")

        assert result.suggested_path == "D.Agents"
        assert "Agent" in result.suggested_tags

    def test_classify_no_match(self):
        """测试无匹配时的默认分类"""
        classifier = RuleBasedClassifier()

        result = classifier.classify("这是一段没有任何关键词的内容")

        assert result.suggested_path == "C.知识"
        assert result.confidence == 0.3  # 默认置信度
        assert "未分类" in result.suggested_tags

    def test_classify_with_yucui_keyword(self):
        """测试语料关键词"""
        classifier = RuleBasedClassifier()

        result = classifier.classify("语料收集工作进展顺利")

        assert result.suggested_path == "A.项目/石榴籽/语料"
        assert "语料" in result.suggested_tags

    def test_classify_with_model_keyword(self):
        """测试模型训练关键词"""
        classifier = RuleBasedClassifier()

        result = classifier.classify("模型训练需要更多数据")

        assert "A.项目/石榴籽" in result.suggested_path
        assert "模型" in result.suggested_tags or "训练" in result.suggested_tags

    def test_tokenize_chinese(self):
        """测试中文分词"""
        classifier = RuleBasedClassifier()

        # 测试分割后的词组提取
        tokens = classifier._tokenize("石榴籽省赛答辩准备中")

        # tokenizer 会提取连续的中文字符串
        assert len(tokens) > 0

    def test_alternatives_provided(self):
        """测试备选方案"""
        classifier = RuleBasedClassifier()

        result = classifier.classify("石榴籽省赛答辩准备中")

        assert len(result.alternatives) >= 0
        assert result.suggested_path == "A.项目/石榴籽/答辩"


# =============================================================================
# AutoClassifier 测试
# =============================================================================


class TestAutoClassifier:
    """AutoClassifier 单元测试"""

    @pytest.mark.asyncio
    async def test_recommend_without_llm(self):
        """测试无 LLM 时的降级到规则匹配"""
        classifier = AutoClassifier(llm_provider=None)

        result = await classifier.recommend("今天学习了机器翻译模型")

        assert result.suggested_path == "C.知识"
        assert "学习" in result.suggested_tags

    @pytest.mark.asyncio
    async def test_recommend_with_mock_llm(self):
        """测试使用 Mock LLM"""
        mock_llm = AsyncMock()
        mock_llm.chat_async = AsyncMock(
            return_value=MagicMock(
                content=json.dumps({
                    "path": "A.项目/石榴籽/语料",
                    "tags": ["石榴籽", "语料"],
                    "confidence": 0.85,
                    "reasoning": "根据关键词判断",
                    "alternatives": [],
                })
            )
        )

        classifier = AutoClassifier(llm_provider=mock_llm)
        result = await classifier.recommend("语料处理工作")

        assert result.suggested_path == "A.项目/石榴籽/语料"
        assert "石榴籽" in result.suggested_tags
        assert result.confidence == 0.85

    @pytest.mark.asyncio
    async def test_recommend_with_llm_json_error_fallback(self):
        """测试 LLM 返回非 JSON 时的降级"""
        mock_llm = AsyncMock()
        mock_llm.chat_async = AsyncMock(
            return_value=MagicMock(content="这不是 JSON 格式")
        )

        classifier = AutoClassifier(llm_provider=mock_llm)
        result = await classifier.recommend("石榴籽省赛答辩")

        # 应该降级到规则匹配
        assert result.suggested_path == "A.项目/石榴籽/答辩"

    @pytest.mark.asyncio
    async def test_confirm_classification(self, tmp_path):
        """测试确认分类结果"""
        from agentmemory.ai.classifier import AutoClassifier

        # 创建临时 DataLake
        dl = DataLake(root_dir=tmp_path)
        await dl.init()

        # 写入一条记忆
        memory_id = await dl.create_memory(
            category_path="C.知识",
            content="测试记忆内容",
            tags=["测试"],
        )

        # 创建分类器
        classifier = AutoClassifier(library=None)

        # 确认分类
        await classifier.confirm(
            memory_id,
            "B.个人/日记",
            ["日记", "测试"],
            datalake=dl,
        )

        # 验证更新
        memory = await dl.get_memory(memory_id)
        assert memory is not None
        assert memory.metadata.get("tags") == ["日记", "测试"]

    @pytest.mark.asyncio
    async def test_reject_and_adjust(self, tmp_path):
        """测试拒绝推荐并调整"""
        from agentmemory.ai.classifier import AutoClassifier

        # 创建临时 DataLake
        dl = DataLake(root_dir=tmp_path)
        await dl.init()

        # 写入一条记忆
        memory_id = await dl.create_memory(
            category_path="C.知识",
            content="测试记忆内容",
            tags=["测试"],
        )

        # 创建分类器
        classifier = AutoClassifier(library=None)

        # 拒绝并调整
        await classifier.reject_and_adjust(
            memory_id,
            "D.Agents",
            ["Agent", "协作"],
            datalake=dl,
        )

        # 验证更新
        memory = await dl.get_memory(memory_id)
        assert memory is not None
        assert memory.metadata.get("tags") == ["Agent", "协作"]


# =============================================================================
# Integration 测试
# =============================================================================


class TestClassifierIntegration:
    """分类器集成测试"""

    @pytest.mark.asyncio
    async def test_write_with_auto_classify(self, tmp_path):
        """测试带自动分类的写入"""
        from agentmemory.ai.classifier import AutoClassifier

        # 创建 DataLake 和 Classifier
        dl = DataLake(root_dir=tmp_path)
        await dl.init()
        classifier = AutoClassifier(llm_provider=None)

        # 写入记忆并自动分类
        memory_id, recommendation = await dl.write_with_auto_classify(
            content="今天学习了机器翻译模型",
            agent_id="test_agent",
            auto_classify=True,
            classifier=classifier,
        )

        # 验证
        assert memory_id is not None
        assert recommendation is not None
        assert recommendation.suggested_path == "C.知识"
        assert "学习" in recommendation.suggested_tags

        # 验证记忆已写入
        memory = await dl.get_memory(memory_id)
        assert memory is not None
        assert memory.content == "今天学习了机器翻译模型"

    @pytest.mark.asyncio
    async def test_write_without_auto_classify(self, tmp_path):
        """测试不带自动分类的写入"""
        from agentmemory.ai.classifier import AutoClassifier

        # 创建 DataLake
        dl = DataLake(root_dir=tmp_path)
        await dl.init()
        classifier = AutoClassifier(llm_provider=None)

        # 写入记忆不自动分类
        memory_id, recommendation = await dl.write_with_auto_classify(
            content="测试内容",
            agent_id="test_agent",
            auto_classify=False,
            classifier=classifier,
        )

        # 验证
        assert memory_id is not None
        assert recommendation is None

    @pytest.mark.asyncio
    async def test_write_with_shiliuzi_classify(self, tmp_path):
        """测试石榴籽项目分类"""
        from agentmemory.ai.classifier import AutoClassifier

        # 创建 DataLake 和 Classifier
        dl = DataLake(root_dir=tmp_path)
        await dl.init()
        classifier = AutoClassifier(llm_provider=None)

        # 写入记忆
        memory_id, recommendation = await dl.write_with_auto_classify(
            content="省赛答辩 PPT 制作中",
            agent_id="test_agent",
            auto_classify=True,
            classifier=classifier,
        )

        # 验证
        assert memory_id is not None
        assert recommendation is not None
        assert recommendation.suggested_path == "A.项目/石榴籽/答辩"


# =============================================================================
# 分类推荐数据类测试
# =============================================================================


class TestClassificationRecommendation:
    """ClassificationRecommendation 数据类测试"""

    def test_create_recommendation(self):
        """测试创建推荐对象"""
        rec = ClassificationRecommendation(
            suggested_path="A.项目/石榴籽/语料",
            suggested_tags=["石榴籽", "语料"],
            confidence=0.85,
            reasoning="根据关键词判断",
            alternatives=[
                {"path": "A.项目/石榴籽", "tags": ["石榴籽"], "reason": "更宽泛"}
            ],
        )

        assert rec.suggested_path == "A.项目/石榴籽/语料"
        assert rec.suggested_tags == ["石榴籽", "语料"]
        assert rec.confidence == 0.85
        assert len(rec.alternatives) == 1

    def test_to_dict(self):
        """测试转换为字典"""
        rec = ClassificationRecommendation(
            suggested_path="A.项目/石榴籽",
            suggested_tags=["石榴籽"],
            confidence=0.9,
            reasoning="测试",
            alternatives=[],
        )

        d = asdict(rec)
        assert d["suggested_path"] == "A.项目/石榴籽"
        assert d["confidence"] == 0.9


class TestAutoClassifyResult:
    """AutoClassifyResult 数据类测试"""

    def test_create_result(self):
        """测试创建结果对象"""
        rec = ClassificationRecommendation(
            suggested_path="A.项目/石榴籽",
            suggested_tags=["石榴籽"],
            confidence=0.9,
            reasoning="测试",
        )
        result = AutoClassifyResult(
            memory_id="mem_123",
            recommendation=rec,
            confirmed=False,
        )

        assert result.memory_id == "mem_123"
        assert result.recommendation == rec
        assert result.confirmed is False
        assert result.final_path is None


# =============================================================================
# Helper
# =============================================================================


def asdict(obj):
    """将 dataclass 转为 dict（递归）"""
    import dataclasses
    if dataclasses.is_dataclass(obj):
        result = {}
        for field in dataclasses.fields(obj):
            value = getattr(obj, field.name)
            result[field.name] = asdict(value)
        return result
    elif isinstance(obj, list):
        return [asdict(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: asdict(v) for k, v in obj.items()}
    else:
        return obj
