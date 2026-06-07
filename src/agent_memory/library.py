"""
Library Classifier - 图书馆分类系统
基于关键词匹配的简单分类器，用于将记忆自动归类到层级路径
"""

import re
from typing import Optional


# 预定义分类词典
CATEGORY_DICTIONARY: dict[str, list[str]] = {
    "项目": [
        "项目", "开发", "开发中", "已完成", "进行中", "迭代", "版本",
        "bug", "feature", "任务", "里程碑", "sprint", "冲刺",
        "石榴籽", "agentmemory", "spectrai", "openclaw",
        "git", "github", "repo", "仓库", "代码", "模块",
    ],
    "学习": [
        "学习", "课程", "教程", "读书", "笔记", "知识点",
        "python", "rust", "javascript", "typescript", "java",
        "ai", "ml", "llm", "模型", "训练", "训练集",
        "论文", "paper", "research", "研究",
    ],
    "人物": [
        "人", "朋友", "同事", "领导", "老板", "客户", "用户",
        "联系人", "团队", "成员", "工程师", "设计师", "产品",
        "cto", "ceo", "pm", "老板", "楚灵", "tmc",
    ],
    "决策": [
        "决定", "决策", "选择", "方案", "策略",
        "技术选型", "架构决策", "adr", "decision",
        "评估", "权衡", "取舍", "优化方向",
        "采用", "放弃", "使用", "不使用",
    ],
    "偏好": [
        "喜欢", "偏好", "倾向", "习惯", "最爱",
        "favorite", "prefer", "always", "从不",
        "风格", "品味", "审美", "口味",
        "工作方式", "作息", "时间安排",
    ],
}

# 顶层类别固定
TOP_LEVEL_CATEGORIES = ["项目", "学习", "人物", "决策", "偏好"]


class LibraryClassifier:
    """
    图书馆分类器
    基于关键词匹配将内容归类到层级路径，动态层数范围 [min_depth, max_depth]。
    默认最少 2 层（顶层 + 子层），最多 4 层。
    """

    def __init__(
        self,
        min_depth: int = 2,
        max_depth: int = 4,
        dictionary: Optional[dict[str, list[str]]] = None,
    ):
        """
        初始化分类器

        Args:
            min_depth: 最少分类深度（默认 2 层，顶层 + 子层）
            max_depth: 最大分类深度（默认 4 层）
            dictionary: 可选的分类词典，格式为 {分类名: [关键词列表]}
        """
        if min_depth < 1:
            raise ValueError("min_depth must be >= 1")
        if max_depth < min_depth:
            raise ValueError("max_depth must be >= min_depth")
        self.min_depth = min_depth
        self.max_depth = max_depth
        self.dictionary = dictionary or CATEGORY_DICTIONARY.copy()

    def _tokenize(self, text: str) -> set[str]:
        """
        简单分词：小写化 + 提取词
        
        Args:
            text: 输入文本
        
        Returns:
            分词后的词集合
        """
        text = text.lower()
        # 提取英文单词和中文词（至少2个字符）
        tokens = set()
        # 英文词
        tokens.update(re.findall(r'\b[a-z][a-z0-9_.-]*\b', text))
        # 中文字（至少2个连续字符）
        tokens.update(re.findall(r'[\u4e00-\u9fff]{2,}', text))
        return tokens

    def _validate_path(self, path: str) -> str:
        """
        验证并修正分类路径

        Args:
            path: 分类路径，如 "项目/石榴籽/语料"

        Returns:
            修正后的路径，保证 min_depth <= 层数 <= max_depth
        """
        if not path or not path.strip():
            return "未分类/通用" if self.min_depth <= 1 else "未分类"

        # 分割路径
        parts = [p.strip() for p in path.split("/") if p.strip()]

        if not parts:
            return "未分类/通用" if self.min_depth <= 1 else "未分类"

        # 第一层必须为顶层类别之一，否则加"未分类"前缀
        if parts[0] not in TOP_LEVEL_CATEGORIES:
            parts.insert(0, "未分类")

        # 限制最大深度
        if len(parts) > self.max_depth:
            parts = parts[:self.max_depth]

        # 补足最小深度（不够层时用"通用"填充）
        while len(parts) < self.min_depth:
            parts.append("通用")

        return "/".join(parts)

    def classify(self, content: str) -> str:
        """
        根据内容自动分类
        
        Args:
            content: 要分类的内容文本
        
        Returns:
            分类路径，如 "项目/石榴籽/语料/NLLB训练"
            如果无法分类，返回 "未分类"
        """
        if not content or not content.strip():
            return "未分类"

        tokens = self._tokenize(content)

        # 统计每个顶层类别的匹配分数
        scores: dict[str, int] = {cat: 0 for cat in TOP_LEVEL_CATEGORIES}

        for category, keywords in self.dictionary.items():
            for keyword in keywords:
                kw_lower = keyword.lower()
                # 检查关键词是否在 token 集合中
                if kw_lower in tokens:
                    scores[category] += 2  # 精确匹配给 2 分
                # 检查关键词是否在原文（不区分大小写）
                elif kw_lower in content.lower():
                    scores[category] += 1  # 包含给 1 分

        # 找出得分最高的类别
        max_score = max(scores.values())
        if max_score == 0:
            return "未分类"

        # 可能有多个类别得分相同，选择第一个
        best_category = None
        for cat in TOP_LEVEL_CATEGORIES:
            if scores[cat] == max_score:
                best_category = cat
                break

        if not best_category:
            return "未分类"

        # 根据最高分类进行二级分类推断
        sub_path = self._infer_subcategory(best_category, content, tokens)

        if sub_path:
            full_path = f"{best_category}/{sub_path}"
        else:
            full_path = best_category

        return self._validate_path(full_path)

    def _infer_subcategory(self, top_category: str, content: str, tokens: set[str]) -> Optional[str]:
        """
        根据顶层类别推断二级或更深的子分类
        
        Args:
            top_category: 顶层类别
            content: 原始内容
            tokens: 分词后的 token 集合
        
        Returns:
            子分类路径（不含顶层），如 "石榴籽/语料"
        """
        content_lower = content.lower()

        # 根据顶层类别进行更细粒度的推断
        if top_category == "项目":
            # 尝试识别项目名称
            project_keywords = {
                "石榴籽": ["石榴籽", "石榴"],
                "SpectrAI": ["spectrai", "spectr-ai"],
                "AgentMemory": ["agentmemory", "agent_memory", "memory"],
                "OpenClaw": ["openclaw", "open_claw", "claw"],
            }
            for sub, kws in project_keywords.items():
                for kw in kws:
                    if kw in tokens or kw in content_lower:
                        return sub

        elif top_category == "学习":
            # 尝试识别学习主题
            learning_keywords = {
                "技术": ["python", "rust", "代码", "编程", "api", "sdk"],
                "AI": ["ai", "llm", "大模型", "模型", "人工智能", "ml"],
                "语言": ["英语", "日语", "中文", "language"],
            }
            for sub, kws in learning_keywords.items():
                for kw in kws:
                    if kw in tokens or kw in content_lower:
                        return sub

        elif top_category == "人物":
            # 尝试识别人物
            person_keywords = {
                "团队": ["团队", "team", "成员", "同事"],
                "外部": ["客户", "用户", "合作", "partner"],
            }
            for sub, kws in person_keywords.items():
                for kw in kws:
                    if kw in tokens or kw in content_lower:
                        return sub

        return None

    def add_keyword(self, category: str, keyword: str) -> None:
        """
        添加分类关键词
        
        Args:
            category: 分类名称（必须是顶层类别之一）
            keyword: 要添加的关键词
        """
        if category not in self.dictionary:
            self.dictionary[category] = []
        if keyword not in self.dictionary[category]:
            self.dictionary[category].append(keyword)

    def get_categories(self) -> list[str]:
        """
        获取所有顶层类别
        
        Returns:
            顶层类别列表
        """
        return TOP_LEVEL_CATEGORIES.copy()

    def get_all_paths(self) -> list[str]:
        """
        获取所有可能的分类路径
        
        Returns:
            所有分类路径列表
        """
        paths = []
        for cat in TOP_LEVEL_CATEGORIES:
            paths.append(cat)
        return paths
