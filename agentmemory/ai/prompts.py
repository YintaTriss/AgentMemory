"""
AgentMemory AI 模块 - Prompt 模板

定义分类推荐等 AI 功能使用的 Prompt 模板。
"""

# =============================================================================
# 分类推荐 Prompt
# =============================================================================

CLASSIFY_PROMPT_TEMPLATE = """你是一个记忆分类助手。根据用户输入的记忆内容，推荐最适合的分类路径和标签。

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


CLASSIFY_WITH_CONTEXT_PROMPT_TEMPLATE = """你是一个记忆分类助手。根据用户输入的记忆内容，结合已有的分类结构，推荐最适合的分类路径和标签。

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

## 已有的分类路径
{existing_paths}

## 记忆内容
{content}

## 要求
1. 根据内容判断最合适的分类路径
2. 优先使用与内容最相关的已有分类
3. 推荐 3-5 个标签
4. 评估置信度（高/中/低）
5. 提供 1-2 个备选方案

请以 JSON 格式输出：
{{"path": "...", "tags": [...], "confidence": 0.x, "reasoning": "...", "alternatives": [...]}}
"""


def get_classify_prompt(content: str) -> str:
    """获取分类推荐 Prompt"""
    return CLASSIFY_PROMPT_TEMPLATE.format(content=content)


def get_classify_with_context_prompt(content: str, existing_paths: list[str]) -> str:
    """获取带上下文的分类推荐 Prompt"""
    paths_str = "\n".join(f"- {p}" for p in existing_paths)
    return CLASSIFY_WITH_CONTEXT_PROMPT_TEMPLATE.format(
        content=content,
        existing_paths=paths_str,
    )
