"""
Temporal Intent + Recall — 方向 2 (2026-07-15)

让 search() 能理解时间相关的 query:
- "去年我说..." → intent=last_year
- "我搬到 Seattle 之前住哪?" → 先查"搬到 Seattle"时间,再去那之前查
- "最近的项目" → intent=recent
- "三月份我做了什么?" → time_range=(2026-03-01, 2026-04-01)

核心:
1. TemporalIntentDetector — 从 query 抽取时间意图 + 范围
2. MemoryManager.search() 加 time_range / only_valid 参数
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any, List


# 时间意图关键词
_TEMPORAL_KEYWORDS = {
    "today": ("today", "今天", "今日"),
    "yesterday": ("yesterday", "昨天", "昨日"),
    "last_week": ("last week", "上周", "上一周", "上星期", "上个星期"),
    "this_week": ("this week", "本周", "这周", "这个星期"),
    "last_month": ("last month", "上个月", "上月"),
    "this_month": ("this month", "本月", "这个月"),
    "last_year": ("last year", "去年", "上一年"),
    "this_year": ("this year", "今年", "本年"),
    "recent": ("recently", "lately", "最近", "近期", "不久前", "刚才", "早上"),
}


# 中文数字 → 数字 (1-31)
_CN_NUM = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7,
    "八": 8, "九": 9, "十": 10,
    "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15,
    "十六": 16, "十七": 17, "十八": 18, "十九": 19, "二十": 20,
    "二十一": 21, "二十二": 22, "二十三": 23, "二十四": 24, "二十五": 25,
    "二十六": 26, "二十七": 27, "二十八": 28, "二十九": 29, "三十": 30, "三十一": 31,
}


class TemporalIntentDetector:
    """从自然语言 query 抽取时间意图

    Returns:
        dict with keys:
          - intent: 时间意图类别 (today / yesterday / last_week / this_week / last_month /
                    this_month / last_year / this_year / recent / None)
          - time_range: (start_iso, end_iso) 或 None
          - confidence: 0.0 - 1.0
    """

    def __init__(self, now: Optional[datetime] = None):
        self.now = now or datetime.now()

    def detect(self, query: str) -> Dict[str, Any]:
        """检测 query 的时间意图

        Returns:
            {"intent": str|None, "time_range": (start_iso, end_iso)|None, "confidence": float}
        """
        q = query.lower().strip()

        # 1. 关键词匹配
        for intent, keywords in _TEMPORAL_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in q:
                    time_range = self._compute_range(intent)
                    return {
                        "intent": intent,
                        "time_range": time_range,
                        "confidence": 0.9,
                    }

        # 2. 中文月份表达:"三月份", "5月"
        m = re.search(r"(\d{1,2})\s*月(?:份)?", q)
        if m:
            month = int(m.group(1))
            if 1 <= month <= 12:
                year = self.now.year
                start = datetime(year, month, 1)
                if month == 12:
                    end = datetime(year + 1, 1, 1)
                else:
                    end = datetime(year, month + 1, 1)
                return {
                    "intent": f"month_{month}",
                    "time_range": (start.isoformat(), end.isoformat()),
                    "confidence": 0.85,
                }

        # 中文月份 + 中文数字
        m = re.search(r"([一二三四五六七八九十]+)\s*月(?:份)?", q)
        if m:
            cn_month = m.group(1)
            month = _CN_NUM.get(cn_month)
            if month and 1 <= month <= 12:
                year = self.now.year
                start = datetime(year, month, 1)
                end = datetime(year, month + 1, 1) if month < 12 else datetime(year + 1, 1, 1)
                return {
                    "intent": f"month_{month}",
                    "time_range": (start.isoformat(), end.isoformat()),
                    "confidence": 0.85,
                }

        # 3. "N 天前" / "N weeks ago"
        m = re.search(r"(\d+)\s*(?:天|days?)\s*前", q)
        if m:
            days = int(m.group(1))
            start = self.now - timedelta(days=days)
            return {
                "intent": f"days_ago_{days}",
                "time_range": (start.isoformat(), self.now.isoformat()),
                "confidence": 0.8,
            }

        # 4. "N 个月前"
        m = re.search(r"(\d+)\s*(?:个?月|months?)\s*前", q)
        if m:
            months = int(m.group(1))
            # 粗略:30 天/月
            start = self.now - timedelta(days=30 * months)
            return {
                "intent": f"months_ago_{months}",
                "time_range": (start.isoformat(), self.now.isoformat()),
                "confidence": 0.8,
            }

        # 5. 无时间意图
        return {"intent": None, "time_range": None, "confidence": 0.0}

    def _compute_range(self, intent: str) -> Optional[Tuple[str, str]]:
        """根据意图计算 (start, end) ISO 时间范围"""
        n = self.now
        if intent == "today":
            start = n.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif intent == "yesterday":
            start = (n - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif intent == "this_week":
            # ISO week: 周一是 1
            start = (n - timedelta(days=n.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=7)
        elif intent == "last_week":
            start_of_this_week = (n - timedelta(days=n.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            start = start_of_this_week - timedelta(days=7)
            end = start_of_this_week
        elif intent == "this_month":
            start = n.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if start.month == 12:
                end = start.replace(year=start.year + 1, month=1)
            else:
                end = start.replace(month=start.month + 1)
        elif intent == "last_month":
            first_of_this_month = n.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = first_of_this_month
            if first_of_this_month.month == 1:
                start = first_of_this_month.replace(year=first_of_this_month.year - 1, month=12)
            else:
                start = first_of_this_month.replace(month=first_of_this_month.month - 1)
        elif intent == "this_year":
            start = n.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = start.replace(year=start.year + 1)
        elif intent == "last_year":
            start = n.replace(year=n.year - 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = start.replace(year=start.year + 1)
        elif intent == "recent":
            # "最近" = 过去 7 天
            start = n - timedelta(days=7)
            end = n + timedelta(days=1)
        else:
            return None

        return (start.isoformat(), end.isoformat())


def filter_by_time_range(
    memories: List[Dict[str, Any]],
    start: Optional[str] = None,
    end: Optional[str] = None,
    time_field: str = "created_at",
) -> List[Dict[str, Any]]:
    """按时间范围过滤 memories。

    Args:
        memories: memory dicts 列表(必须有 meta.<time_field>)
        start: 起始 ISO 时间(含),None = 不限
        end: 结束 ISO 时间(不含),None = 不限
        time_field: 时间字段名,默认 'created_at',可改为 'valid_from' 等

    Returns:
        过滤后的 memories
    """
    if not start and not end:
        return memories

    out = []
    for m in memories:
        meta = m.get("meta", {}) or {}
        ts = meta.get(time_field, "")
        if not ts:
            continue
        if start and ts < start:
            continue
        if end and ts >= end:
            continue
        out.append(m)
    return out


def filter_only_valid(memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """过滤掉已被 invalidated 的记忆"""
    return [
        m for m in memories
        if not (m.get("meta", {}) or {}).get("invalidated_by")
    ]