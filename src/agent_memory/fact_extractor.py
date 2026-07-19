"""
v0.3 FactType 提取器 — 支持规则和 LLM 双模式

提升点：
1. 可选 LLM 提取 — 配置了 LLM provider 时走 LLM，否则降级为规则
2. 内容 hash 缓存 — 同一段内容不重复跑 LLM
3. 批量接口 — extract_facts_batch() 一次性喂多条进 LLM，省 token

设计：
- FactExtractor 是一个独立类，由 L1LCMCompressor 持有
- 缓存用 LRU（保护内存不爆炸）
- 规则提取也走缓存（避免重复字符串扫描）
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from collections import OrderedDict
from typing import List, Optional, Protocol, runtime_checkable


# ---- FactType 枚举 ----

class FactType:
    GENERAL = "general"
    DECISION = "decision"
    PREFERENCE = "preference"
    PROJECT = "project"
    LEARNING = "learning"


# ---- 规则提取（中英双语关键词） ----

_RULE_KEYWORDS = {
    FactType.DECISION: [
        "决定", "确定了", "拍板", "就", "选用", "改用", "采用",
        "decided", "decided to", "chose", "selected", "going with",
    ],
    FactType.PREFERENCE: [
        "喜欢", "偏好", "倾向", "习惯", "我爱", "我常",
        "prefer", "like", "favorite", "tends to", "usually",
    ],
    FactType.PROJECT: [
        "项目", "任务", "需求", "目标", "计划", "里程碑",
        "project", "task", "goal", "milestone", "roadmap",
    ],
    FactType.LEARNING: [
        "学到", "发现", "意识到", "原来", "明白了", "搞清楚",
        "learned", "realized", "discovered", "figured out",
    ],
}


_RULE_SPLIT_PATTERN = re.compile(r"[。.!?！？；;\n]+")


def _rule_extract(content: str) -> List[str]:
    """规则提取：按句号切分，找含决策/偏好/项目/学习关键词的句子。"""
    if not content or len(content.strip()) < 10:
        return []
    sentences = [s.strip() for s in _RULE_SPLIT_PATTERN.split(content) if s.strip()]
    if not sentences:
        return []

    facts = []
    for sent in sentences:
        if len(sent) < 10:
            continue
        matched_type = None
        for ftype, keywords in _RULE_KEYWORDS.items():
            for kw in keywords:
                if kw in sent:
                    matched_type = ftype
                    break
            if matched_type:
                break
        if matched_type:
            facts.append(sent)
            if len(facts) >= 5:
                break
    return facts


# ---- LRU 缓存 ----

class _LRUCache(OrderedDict):
    def __init__(self, capacity: int = 128):
        super().__init__()
        self.capacity = capacity

    def get(self, key, default=None):
        if key in self:
            self.move_to_end(key)
            return self[key]
        return default

    def put(self, key, value):
        if key in self:
            self.move_to_end(key)
            self[key] = value
        else:
            self[key] = value
            if len(self) > self.capacity:
                self.popitem(last=False)


# ---- LLM 提取提示词 ----

_LLM_PROMPT_TMPL = """你是事实抽取助手。从以下内容中挑出有长期保留价值的语句（决策、偏好、项目进展、学习成果）。

每条事实独立成行，限 5 条以内。不带序号、不加注释。原句摘抄即可。

内容：
{content}
"""


@runtime_checkable
class _LLMClient(Protocol):
    """最小接口，避免拉取整个 LLM provider"""
    async def chat(self, messages: list, **kwargs) -> object:
        ...


# ---- 公开类：FactExtractor ----

class FactExtractor:
    """
    FactType 提取器（双模式）

    优先级：
      1. LLM（若 llm_client 可用） — 精度高、识别模糊语境
      2. 规则（fallback） — 零外部依赖、确定性

    缓存：内容 hash → facts 列表。同一段内容只跑一次（LLM 或规则）。
    """

    def __init__(
        self,
        llm_client: Optional[_LLMClient] = None,
        cache_size: int = 128,
        max_facts_per_request: int = 5,
        llm_max_tokens: int = 400,
    ):
        self._llm = llm_client
        self._cache: _LRUCache = _LRUCache(capacity=cache_size)
        self._max_facts = max_facts_per_request
        self._llm_max_tokens = llm_max_tokens

    @staticmethod
    def _hash(content: str) -> str:
        return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()

    async def extract(self, content: str) -> List[str]:
        """异步提取事实（LLM 或规则）。会缓存结果。"""
        if not content or not content.strip():
            return []

        key = self._hash(content)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        if self._llm is not None:
            try:
                facts = await self._extract_llm(content)
            except Exception:
                facts = _rule_extract(content)
        else:
            facts = _rule_extract(content)

        facts = facts[: self._max_facts]
        self._cache.put(key, facts)
        return facts

    async def extract_batch(self, contents: List[str]) -> List[List[str]]:
        """批量提取：对每个内容单独走缓存；缓存未命中的走 LLM 一次，规则退化为单条循环。"""
        if not contents:
            return []

        # 先查缓存
        uncached_idx = []
        uncached_texts = []
        results: List[Optional[List[str]]] = [None] * len(contents)
        for i, c in enumerate(contents):
            if not c or not c.strip():
                continue
            cached = self._cache.get(self._hash(c))
            if cached is not None:
                results[i] = cached
            else:
                uncached_idx.append(i)
                uncached_texts.append(c)

        if self._llm and uncached_texts:
            # 拼成单条 LLM 请求节约 token
            joined = "\n\n---ITEM---\n\n".join(uncached_texts)
            try:
                facts_list = await self._extract_llm_batch(joined, len(uncached_texts))
                for idx, facts in zip(uncached_idx, facts_list):
                    facts = (facts or [])[: self._max_facts]
                    self._cache.put(self._hash(contents[idx]), facts)
                    results[idx] = facts
            except Exception:
                # 失败 → 单条 fallback 规则
                for idx, c in zip(uncached_idx, uncached_texts):
                    f = _rule_extract(c)[: self._max_facts]
                    self._cache.put(self._hash(c), f)
                    results[idx] = f
        elif uncached_texts:
            # 无 LLM，纯规则
            for idx, c in zip(uncached_idx, uncached_texts):
                f = _rule_extract(c)[: self._max_facts]
                self._cache.put(self._hash(c), f)
                results[idx] = f

        # 把残留 None 填 []
        return [r if r is not None else [] for r in results]

    def invalidate_cache(self) -> None:
        self._cache.clear()

    # ---- 私有 ----

    async def _extract_llm(self, content: str) -> List[str]:
        messages = [{"role": "user", "content": _LLM_PROMPT_TMPL.format(content=content)}]
        resp = await self._llm.chat(messages, max_tokens=self._llm_max_tokens, temperature=0.2)
        text = getattr(resp, "content", str(resp))
        return self._parse_lines(text)

    async def _extract_llm_batch(self, joined: str, n: int) -> List[List[str]]:
        """拼接批量内容一次问 LLM，再用 ---ITEM--- 切回。

        健壮性：LLM 偶尔会在第一个 ---ITEM--- 前加一段 preamble
        （如“以下是事实：”、“好的”等）。实现思路：
          1. 先按 ---ITEM--- 切分
          2. 如果切出的 chunks 数 > n，说明多了 preamble，过滤掉首段
          3. 如果 chunks 数 <= n，用空字符串补齐到 n
        """
        prompt = (
            f"你是事实抽取助手。以下有 {n} 段内容（用 ---ITEM--- 分隔）。\n"
            "逐段处理：每段独立输出事实列表，多段之间再用 ---ITEM--- 分隔。\n"
            "每段 ≤5 条，不带序号，不加注释，原句摘抄。\n\n"
            f"{joined}"
        )
        messages = [{"role": "user", "content": prompt}]
        resp = await self._llm.chat(messages, max_tokens=self._llm_max_tokens * n, temperature=0.2)
        text = getattr(resp, "content", str(resp))
        chunks = text.split("---ITEM---")

        # 处理 preamble：多于 n 段 → 丢掉首段；少于 n → 补齐空串
        if len(chunks) > n:
            # 可能有 preamble + n items，或多了几段 trim 到最后 n 段
            chunks = chunks[-(n):]
        elif len(chunks) < n:
            chunks.extend([""] * (n - len(chunks)))

        return [self._parse_lines(c) for c in chunks[:n]]

    @staticmethod
    def _parse_lines(text: str) -> List[str]:
        """解析 LLM 输出：每行一条事实。"""
        out = []
        for raw in text.splitlines():
            line = raw.strip()
            # 去掉常见前缀
            for prefix in ("- ", "* ", "• ", "1. ", "2. ", "3. ", "4. ", "5. "):
                if line.startswith(prefix):
                    line = line[len(prefix):].strip()
                    break
            # 去掉数字前缀如 "1)"、"1："
            m = re.match(r"^\d+[\.\):：]\s*(.+)$", line)
            if m:
                line = m.group(1).strip()
            if line and len(line) >= 6 and len(line) <= 400:
                out.append(line)
        return out


def extract_facts(content: str) -> List[str]:
    """同步便捷函数：纯规则模式，无 LLM、无缓存。"""
    return _rule_extract(content)
