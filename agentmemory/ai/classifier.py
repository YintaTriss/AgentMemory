"""
AgentMemory AI 辅助分类推荐引擎

根据 v0.3 §2.4「Embedding 辅助分类」+ §3.1 写入指令设计。
在写入记忆时，AI 自动分析内容推荐分类路径和 Tags，用户确认后写入。
"""

import json
import re
from dataclasses import dataclass, field, asdict
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from agentmemory.data.datalake import DataLake
    from agentmemory.data.library import Library
    from agentmemory.providers.protocols import BaseLLMProvider


# =============================================================================
# 数据类定义
# =============================================================================


@dataclass
class ClassificationRecommendation:
    """分类推荐结果"""
    suggested_path: str  # 推荐的分类路径，如 "A.项目/石榴籽/语料"
    suggested_tags: list[str]  # 推荐的 Tags
    confidence: float  # 置信度 0.0~1.0
    reasoning: str  # 推荐理由
    alternatives: list[dict] = field(default_factory=list)  # 备选方案


@dataclass
class AutoClassifyResult:
    """自动分类结果"""
    memory_id: str
    recommendation: ClassificationRecommendation | None
    confirmed: bool = False  # 用户是否已确认
    final_path: str | None = None  # 最终确认的路径（确认后填充）
    final_tags: list[str] | None = None  # 最终确认的 Tags（确认后填充）


# =============================================================================
# 分类推荐 Prompt 模板
# =============================================================================


PROMPT_TEMPLATE = """你是一个记忆分类助手。根据用户输入的记忆内容，推荐最适合的分类路径和标签。

## 分类体系
A.项目 — 工作/项目相关记忆
  A.项目/石榴籽 — 石榴籽挑战杯相关
    A.项目/石榴籽/语料 — 语料相关
    A.项目/石榴籽/模型 — 模型训练相关
    A.项目/石榴籽/答辩 — 答辩准备相关
B.个人 — 私人记忆
  B.个人/日记 — 日常日记
  B.个人/收藏 — 收藏内容
C.知识 — 学习的知识
D.Agents — Agent 协作相关
Z.归档 — 已完成归档

## 记忆内容
{content}

## 要求
1. 根据内容判断最合适的分类路径
2. 推荐 3-5 个标签
3. 评估置信度（高/中/低）
4. 提供 1-2 个备选方案

请以 JSON 格式输出：
{{"path": "...", "tags": [...], "confidence": 0.x, "reasoning": "...", "alternatives": [...]}}
"""


# =============================================================================
# 关键词规则匹配（无 LLM 时的降级方案）
# =============================================================================


_KEYWORD_RULES = {
    "石榴籽": {"path": "A.项目/石榴籽", "tags": ["石榴籽", "挑战杯"]},
    "省赛": {"path": "A.项目/石榴籽/答辩", "tags": ["石榴籽", "省赛", "答辩"]},
    "答辩": {"path": "A.项目/石榴籽/答辩", "tags": ["石榴籽", "答辩"]},
    "语料": {"path": "A.项目/石榴籽/语料", "tags": ["石榴籽", "语料"]},
    "东乡语": {"path": "A.项目/石榴籽/模型", "tags": ["东乡语", "机器翻译"]},
    "机器翻译": {"path": "A.项目/石榴籽/模型", "tags": ["机器翻译", "模型"]},
    "模型": {"path": "A.项目/石榴籽/模型", "tags": ["模型", "训练"]},
    "训练": {"path": "A.项目/石榴籽/模型", "tags": ["训练", "模型"]},
    "日记": {"path": "B.个人/日记", "tags": ["日记"]},
    "个人": {"path": "B.个人", "tags": ["个人"]},
    "收藏": {"path": "B.个人/收藏", "tags": ["收藏"]},
    "学习": {"path": "C.知识", "tags": ["学习"]},
    "知识": {"path": "C.知识", "tags": ["知识"]},
    "技术": {"path": "C.知识", "tags": ["技术"]},
    "Agent": {"path": "D.Agents", "tags": ["Agent"]},
    "协作": {"path": "D.Agents", "tags": ["协作"]},
    "归档": {"path": "Z.归档", "tags": ["归档"]},
}


class RuleBasedClassifier:
    """基于关键词规则的分类推荐（降级方案）"""

    def classify(self, content: str) -> ClassificationRecommendation:
        """
        提取关键词，匹配规则，返回推荐

        Args:
            content: 记忆内容

        Returns:
            ClassificationRecommendation
        """
        content_lower = content.lower()

        # 1. 直接在内容中搜索关键词（支持子串匹配）
        matched_rules: list[tuple[str, dict, int]] = []  # (keyword, rule, position)
        for keyword, rule in _KEYWORD_RULES.items():
            keyword_lower = keyword.lower()
            pos = content_lower.find(keyword_lower)
            if pos >= 0:
                matched_rules.append((keyword, rule, pos))

        if not matched_rules:
            # 没有匹配，返回默认分类
            return ClassificationRecommendation(
                suggested_path="C.知识",
                suggested_tags=["未分类"],
                confidence=0.3,
                reasoning="未匹配到特定关键词，使用默认分类",
                alternatives=[],
            )

        # 2. 按位置排序（越靠前的关键词越重要）
        matched_rules.sort(key=lambda x: x[2])

        # 3. 获取最高优先级匹配的路径和标签
        best_keyword, best_rule, _ = matched_rules[0]

        # 合并所有匹配的标签
        all_tags: set[str] = set()
        for keyword, rule, _ in matched_rules:
            all_tags.update(rule["tags"])

        # 避免重复添加 best keyword 本身
        if best_keyword not in all_tags:
            all_tags.add(best_keyword)

        # 计算置信度（匹配的关键词越多，置信度越高）
        confidence = min(0.3 + 0.2 * len(matched_rules), 0.9)

        # 构建备选方案
        alternatives = []
        seen_paths = {best_rule["path"]}
        for keyword, rule, _ in matched_rules[1:3]:  # 最多2个备选
            if rule["path"] not in seen_paths:
                alternatives.append({
                    "path": rule["path"],
                    "tags": rule["tags"],
                    "reason": f"匹配关键词: {keyword}",
                })
                seen_paths.add(rule["path"])

        return ClassificationRecommendation(
            suggested_path=best_rule["path"],
            suggested_tags=list(all_tags)[:5],  # 最多5个标签
            confidence=confidence,
            reasoning=f"匹配到关键词: {', '.join([k for k, _, _ in matched_rules[:3]])}",
            alternatives=alternatives,
        )

    def _tokenize(self, text: str) -> list[str]:
        """简单分词：保留中文词组，按标点和空格分割"""
        # 首先按空格和中英文标点分割，但保留 2-4 个字的词组
        # 使用更保守的分割策略
        tokens = re.split(r'[\s,。！？、：；""''（）【】.!?;:"\'()\[\]]+', text)
        
        # 进一步处理，保留连续的中文字符序列（2-4字词）
        result: list[str] = []
        for token in tokens:
            token = token.strip()
            if not token:
                continue
            # 如果是纯汉字或混合，保留原样
            if re.search(r'[\u4e00-\u9fff]', token):
                # 检查是否是短词组（2-4个汉字）
                chinese_chars = re.findall(r'[\u4e00-\u9fff]+', token)
                for chars in chinese_chars:
                    if chars:
                        result.append(chars)
            else:
                result.append(token)
        
        return result


# =============================================================================
# AI 辅助分类推荐引擎
# =============================================================================


class AutoClassifier:
    """AI 辅助分类推荐引擎"""

    def __init__(
        self,
        llm_provider: "BaseLLMProvider | None" = None,
        library: "Library | None" = None,
    ):
        """
        初始化分类推荐引擎

        Args:
            llm_provider: LLM Provider，不提供时用规则方式
            library: Library 实例，用于获取已有分类结构
        """
        self.llm = llm_provider
        self.library = library
        self._rule_classifier = RuleBasedClassifier()

    async def recommend(
        self,
        content: str,
        current_path: str = "",
    ) -> ClassificationRecommendation:
        """
        分析内容，推荐分类路径和 Tags

        策略：
        1. 有 LLMProvider → 调用 LLM 分析
        2. 无 LLMProvider → 基于关键词规则匹配

        Args:
            content: 记忆内容
            current_path: 当前分类路径（可选）

        Returns:
            ClassificationRecommendation
        """
        if self.llm is not None:
            return await self._recommend_with_llm(content, current_path)
        else:
            return self._rule_classifier.classify(content)

    async def _recommend_with_llm(
        self,
        content: str,
        current_path: str = "",
    ) -> ClassificationRecommendation:
        """使用 LLM 进行分类推荐"""
        prompt = PROMPT_TEMPLATE.format(content=content)

        messages = [{"role": "user", "content": prompt}]

        response = await self.llm.chat_async(messages)

        try:
            # 解析 JSON 响应
            result = json.loads(response.content)

            # 转换为 ClassificationRecommendation
            alternatives = result.get("alternatives", [])
            if isinstance(alternatives, list):
                # 确保 alternatives 是 dict 列表
                alternatives = [
                    alt if isinstance(alt, dict) else {"path": str(alt), "tags": [], "reason": ""}
                    for alt in alternatives
                ]

            return ClassificationRecommendation(
                suggested_path=result.get("path", "C.知识"),
                suggested_tags=result.get("tags", []),
                confidence=result.get("confidence", 0.5),
                reasoning=result.get("reasoning", ""),
                alternatives=alternatives,
            )
        except (json.JSONDecodeError, KeyError) as e:
            # 解析失败，降级到规则匹配
            return self._rule_classifier.classify(content)

    async def recommend_with_library_context(
        self,
        content: str,
        existing_paths: list[str],
    ) -> ClassificationRecommendation:
        """
        结合已有分类结构推荐

        Args:
            content: 记忆内容
            existing_paths: 已有的分类路径列表

        Returns:
            ClassificationRecommendation
        """
        # 先获取基础推荐
        recommendation = await self.recommend(content)

        # 如果 LLM 可用，可以让 LLM 参考 existing_paths 进行更精细的推荐
        if self.llm is not None:
            # 构建上下文 prompt
            context_prompt = PROMPT_TEMPLATE.format(content=content)
            context_prompt += f"\n\n## 已有的分类路径\n{chr(10).join(existing_paths)}\n\n请结合以上已有路径进行推荐。"

            messages = [{"role": "user", "content": context_prompt}]
            response = await self.llm.chat_async(messages)

            try:
                result = json.loads(response.content)
                alternatives = result.get("alternatives", [])
                if isinstance(alternatives, list):
                    alternatives = [
                        alt if isinstance(alt, dict) else {"path": str(alt), "tags": [], "reason": ""}
                        for alt in alternatives
                    ]

                return ClassificationRecommendation(
                    suggested_path=result.get("path", recommendation.suggested_path),
                    suggested_tags=result.get("tags", recommendation.suggested_tags),
                    confidence=result.get("confidence", recommendation.confidence),
                    reasoning=result.get("reasoning", recommendation.reasoning),
                    alternatives=alternatives,
                )
            except (json.JSONDecodeError, KeyError):
                return recommendation

        return recommendation

    async def confirm(
        self,
        memory_id: str,
        confirmed_path: str,
        confirmed_tags: list[str],
        datalake: "DataLake | None" = None,
    ) -> None:
        """
        确认推荐结果，写入记忆的 classification 字段

        Args:
            memory_id: 记忆 ID
            confirmed_path: 用户确认的路径
            confirmed_tags: 用户确认的标签
            datalake: DataLake 实例（如果提供则直接更新）
        """
        if datalake is not None:
            # 获取记忆内容
            memory = await datalake.get_memory(memory_id)
            if memory:
                # 读取当前 metadata 并更新
                meta_dict = memory.metadata.copy()
                meta_dict["tags"] = confirmed_tags
                meta_dict["classification_path"] = confirmed_path
                
                # 直接写入文件
                import aiofiles
                # 找到 memory 文件路径
                for md_path in datalake.memory_library.rglob(memory_id + ".md"):
                    meta_path = md_path.with_suffix(".meta.json")
                    async with aiofiles.open(meta_path, "w", encoding="utf-8") as f:
                        await f.write(json.dumps(meta_dict, ensure_ascii=False, indent=2))
                    break

    async def reject_and_adjust(
        self,
        memory_id: str,
        adjusted_path: str,
        adjusted_tags: list[str],
        datalake: "DataLake | None" = None,
    ) -> None:
        """
        用户拒绝推荐，自行调整

        Args:
            memory_id: 记忆 ID
            adjusted_path: 用户调整后的路径
            adjusted_tags: 用户调整后的标签
            datalake: DataLake 实例
        """
        await self.confirm(memory_id, adjusted_path, adjusted_tags, datalake)
