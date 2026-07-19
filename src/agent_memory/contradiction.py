r"""
Contradiction Detector — 方向 1 (2026-07-15)

自动检测新事实与已有事实的矛盾,标记旧事实为 invalidated。

设计:
- 不调 LLM,纯启发式(快速、零 token)
- 双信号触发:
  1. 否定/变更关键词命中("不再" / "换成" / "改为" / "已经" / "搬家" 等)
  2. 同 category + 关键词重合度 + 字符相似度都高

阈值:
- keyword_overlap >= 0.5
- char_similarity >= 0.6
- 必须有变更关键词才触发(防止误判)
"""
from __future__ import annotations

import asyncio
import re
from typing import List, Dict, Any, Optional, Set
from difflib import SequenceMatcher


# 触发矛盾的关键词
_CHANGE_KEYWORDS = {
    # 中文
    "不再", "不用", "改成", "换成", "改为", "换为", "现在", "已经", "搬家",
    "搬到了", "搬到", "迁移到", "从今以后", "今后", "改用", "弃用",
    # English
    "no longer", "don't use", "switched", "moved to", "now use",
    "migrated to", "instead of", "changed from",
}

# 否定词(可选,用于增强判断)
_NEGATION_KEYWORDS = {
    "不", "没", "无", "否", "未", "别", "不要",
    "not", "no", "never", "none", "n't",
}


class ContradictionDetector:
    """启发式矛盾检测器"""

    def __init__(
        self,
        keyword_overlap_threshold: float = 0.1,  # 2026-07-15: 进一步调低,启发式启发
        char_similarity_threshold: float = 0.3,
        min_keyword_chars: int = 2,
        min_overlap_keywords: int = 2,  # 至少 2 个重合关键词
    ):
        self.keyword_overlap_threshold = keyword_overlap_threshold
        self.char_similarity_threshold = char_similarity_threshold
        self.min_keyword_chars = min_keyword_chars
        self.min_overlap_keywords = min_overlap_keywords

    def has_change_intent(self, content: str) -> bool:
        """检测 content 是否含变更意图"""
        content_lower = content.lower()
        return any(kw.lower() in content_lower for kw in _CHANGE_KEYWORDS)

    async def find_and_invalidate(
        self,
        new_content: str,
        new_meta: Dict[str, Any],
        store,
        category_path: Optional[str] = None,
        limit: int = 50,
    ) -> List[str]:
        """找到与新事实矛盾的旧事实 ID,标记为 invalidated。

        Args:
            new_content: 新事实文本
            new_meta: 新事实的 meta dict(用于 category_path / tags)
            store: L4 store 实例(支持 load_existing 和 list_active)
            category_path: 可选,只在指定类别里搜
            limit: 候选事实最多看多少条

        Returns:
            旧事实 ID 列表(它们被新事实取代)
        """
        # 1. 必须有变更意图才触发矛盾检测(避免误判)
        if not self.has_change_intent(new_content):
            return []

        # 2. 获取候选旧事实
        try:
            if hasattr(store, "list_active"):
                candidates = await store.list_active(limit=limit, category_path=category_path)
            else:
                # fallback:同步 list ID + load_existing
                if hasattr(store, "list"):
                    ids = store.list() if not asyncio.iscoroutinefunction(store.list) else await store.list()
                else:
                    return []
                candidates = []
                for mid in (ids or [])[:limit]:
                    try:
                        mem = await store.load_existing(mid)
                        if mem:
                            candidates.append(mem)
                    except Exception:
                        continue
        except Exception:
            return []

        # 3. 启发式矛盾打分
        superseded_ids: List[str] = []
        new_kw = self._extract_keywords(new_content)

        for old in candidates or []:
            if not isinstance(old, dict):
                continue
            old_id = old.get("id")
            if not old_id:
                continue
            old_content = old.get("content", "")
            if not old_content:
                continue

            # 已 invalidated 的事实不再处理
            if old.get("meta", {}).get("invalidated_by"):
                continue

            # 同 category 才考虑矛盾
            old_category = old.get("meta", {}).get("category") or old.get("meta", {}).get("category_path")
            new_category = new_meta.get("category_path")
            if new_category and old_category and old_category != new_category:
                continue

            old_kw = self._extract_keywords(old_content)
            overlap = self._keyword_overlap(new_kw, old_kw)
            char_sim = SequenceMatcher(None, new_content, old_content).ratio()
            overlap_count = len(new_kw & old_kw)
            # 2026-07-15: 实体关键词(高特异性)重合是决定性信号
            new_ent = self._extract_entities(new_content)
            old_ent = self._extract_entities(old_content)
            entity_overlap = new_ent & old_ent

            if (overlap >= self.keyword_overlap_threshold
                    and char_sim >= self.char_similarity_threshold
                    and entity_overlap):
                superseded_ids.append(old_id)

        return superseded_ids

    @staticmethod
    def _extract_keywords(content: str) -> Set[str]:
        """从 content 提取关键词(简单中英分词)

        中文: 按 2-gram 切
        英文: 按 \w+ 切
        """
        words: Set[str] = set()
        # English words
        for w in re.findall(r"\w+", content.lower()):
            if len(w) >= 2:
                words.add(w)
        # Chinese 2-grams
        chinese_chars = re.findall(r"[\u4e00-\u9fff]+", content)
        for ch in chinese_chars:
            for i in range(len(ch) - 1):
                words.add(ch[i:i+2])
        return words

    @staticmethod
    def _extract_entities(content: str) -> Set[str]:
        """提取高特异性实体词

        用于矛盾检测的"决定性信号":产品名、地名、URL、专有名词。
        英文 3+ 字符、中文 3+ 连续字符,小写化后去重。
        """
        entities: Set[str] = set()
        # English 3+ chars
        for w in re.findall(r"[a-z0-9]+", content.lower()):
            if len(w) >= 3:
                entities.add(w)
        # Chinese 3-grams
        chinese_chars = re.findall(r"[\u4e00-\u9fff]+", content)
        for ch in chinese_chars:
            for i in range(len(ch) - 2):
                entities.add(ch[i:i+3])
        return entities

    @staticmethod
    def _keyword_overlap(kw_a: Set[str], kw_b: Set[str]) -> float:
        if not kw_a or not kw_b:
            return 0.0
        intersection = kw_a & kw_b
        smaller = min(len(kw_a), len(kw_b))
        return len(intersection) / smaller if smaller > 0 else 0.0