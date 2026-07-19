"""
AgentMemory v0.3 - L1 LCM (Long-term Context Memory) Compressor

Compresses multiple memories into a concise context for AI prompts.
Output format: narrative paragraphs + key facts list.

This is a simplified implementation that works without external LLM APIs.
"""

from __future__ import annotations

import re
from typing import List, Dict, Any, Optional
from datetime import datetime


# ---- FactExtractor 协议（避免循环 import） ----

class _FactExtractorProtocol:
    """Minimal structural type for FactExtractor bound to L1.

    L1LCMCompressor 不需要 FactExtractor 全部功能,只需要判断对象存在。
    真正的 FactExtractor 类在 fact_extractor.py。
    """
    pass


# ---- Module-level helper (DRY: extracted from compress()) ----

def _parse_timestamp(meta: Dict[str, Any]) -> datetime:
    """Parse created_at from memory meta dict; return datetime.min on failure."""
    ts = meta.get("created_at", "")
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return datetime.min


class L1LCMCompressor:
    """
    L1 Memory Compressor

    Compresses multiple memories into a concise summary for AI context.
    Uses simple extractive summarization (no external API required).
    """

    def __init__(
        self,
        max_context_chars: int = 4000,
        fact_extractor: Optional[Any] = None,
    ):
        """
        Initialize L1 compressor.

        Args:
            max_context_chars: Maximum characters in compressed output.
            fact_extractor: 可选的 FactExtractor 实例(2026-07-15+ 支持)。
                            挂上后,extract_facts_v2() 会优先走 extractor 的
                            sync 规则路径;真正的 async + LLM 路径在
                            MemoryManager.compress_with_facts() 中调用。
                            不传 = 纯规则,完全向后兼容。
        """
        self.max_context_chars = max_context_chars
        # 用 object.__setattr__ 风格避免和 property 冲突
        self._fact_extractor = fact_extractor

    @property
    def fact_extractor(self):
        """当前注入的 FactExtractor 实例(可能为 None)。"""
        return getattr(self, "_fact_extractor", None)

    @property
    def has_fact_extractor(self) -> bool:
        """是否挂上了 FactExtractor。"""
        return self.fact_extractor is not None

    def bind_fact_extractor(self, extractor: Any) -> "L1LCMCompressor":
        """动态绑定 FactExtractor 实例。返回 self 便于链式。"""
        self._fact_extractor = extractor
        return self

    def unbind_fact_extractor(self) -> "L1LCMCompressor":
        """卸下 FactExtractor。返回 self。"""
        self._fact_extractor = None
        return self

    def extract_facts_v2(self, content: str) -> List[str]:
        """优先用 FactExtractor 的规则路径;否则回退 self.extract_facts。

        注:FactExtractor.extract() 是 async;这里 L1 永远走 sync 规则路径,
        以保持 compress() 同步语义。LLM 抽取走 compress_with_facts() async。
        """
        ext = self.fact_extractor
        if ext is None:
            return self.extract_facts(content)
        # 复用 FactExtractor 的内部规则函数
        from .fact_extractor import _rule_extract  # noqa: E402
        return _rule_extract(content)

    def compress(self, memories: List[Dict[str, Any]], query: str = "") -> str:
        """
        Compress multiple memories into a concise context.

        Args:
            memories: List of memory dicts with 'id', 'content', 'meta' keys
            query: Optional query string to focus/prioritize relevant memories.
                Memories whose content contains query keywords are boosted to
                the front of each group (P2-3 fix: query param now used).

        Returns:
            Compressed context string
        """
        # P0-7 fix: guard against None (if not memories raises TypeError on None)
        if not memories:
            return "No relevant memories found."

        # P0-8 fix: filter out non-dict items to prevent AttributeError
        # when mem.get() is called on non-dict objects
        memories = [m for m in memories if isinstance(m, dict)]

        # P2-3 fix: compute optional query-relevance boost.
        # Simple keyword-overlap approach: memories with more query tokens in
        # their content get boosted within their importance tier.
        query_toks: set[str] = set()
        if query:
            query_toks = set(re.findall(r"[\w]{2,}", query.lower()))

        def _relevance_score(mem: Dict[str, Any]) -> int:
            """Count how many query tokens appear in memory content."""
            if not query_toks:
                return 0
            content_lower = mem.get("content", "").lower()
            return sum(1 for tok in query_toks if tok in content_lower)

        # Group by importance
        important_memories = []
        normal_memories = []

        for mem in memories:
            importance = mem.get("meta", {}).get("importance", 0.5)
            if importance >= 0.7:
                important_memories.append(mem)
            else:
                normal_memories.append(mem)

        # P2-2 fix: use module-level _parse_timestamp instead of duplicating
        # the same nested function twice (DRY violation)
        important_memories.sort(
            key=lambda m: (_relevance_score(m), _parse_timestamp(m)),
            reverse=True,
        )
        normal_memories.sort(
            key=lambda m: (_relevance_score(m), _parse_timestamp(m)),
            reverse=True,
        )

        # Build output
        lines = []
        lines.append("# Relevant Memories")
        lines.append("")

        # Add important memories first
        if important_memories:
            lines.append("## Key Facts")
            for mem in important_memories[:10]:  # Limit to 10
                content = mem.get("content", "")
                category = mem.get("meta", {}).get("category", "general")
                tags = mem.get("meta", {}).get("tags", [])
                tags_str = f" [{', '.join(tags)}]" if tags else ""
                # 2026-07-15: Provenance 暴露 — 在每条重要事实后面标 [Source: ..., date]
                meta = mem.get("meta", {})
                source = meta.get("source", "")
                created_at = meta.get("created_at", "")
                date_str = created_at[:10] if created_at else ""  # YYYY-MM-DD
                provenance = ""
                if source or date_str:
                    parts = [p for p in (source, date_str) if p]
                    provenance = f"  *[Source: {', '.join(parts)}]*"
                lines.append(f"- [{category}]{tags_str} {content}{provenance}")
            lines.append("")

        # Add normal memories
        if normal_memories:
            lines.append("## Background")
            for mem in normal_memories[:20]:  # Limit to 20
                content = mem.get("content", "")
                category = mem.get("meta", {}).get("category", "general")
                lines.append(f"- [{category}] {content}")
            lines.append("")

        # Join and truncate if needed
        result = "\n".join(lines)
        if len(result) > self.max_context_chars:
            # P2-7 fix: truncate at line boundary instead of arbitrary char boundary
            truncated = result[:self.max_context_chars - 100]
            last_newline = truncated.rfind("\n")
            if last_newline > self.max_context_chars * 0.7:
                truncated = truncated[:last_newline]
            result = truncated + "\n\n... (truncated)"

        return result

    def extract_facts(self, content: str) -> List[str]:
        """
        Extract key facts from content (simple rule-based).

        Args:
            content: Text content

        Returns:
            List of extracted facts
        """
        facts = []
        # 2026-07-15: 如果挂上了 FactExtractor,委托给它的事实分类更精细。
        # 这里走 sync 路径(_rule_extract),与 extract_facts_v2 一致。
        ext = self.fact_extractor
        if ext is not None:
            from .fact_extractor import _rule_extract  # noqa: E402
            return _rule_extract(content)
        # P1-7 fix: handle both Chinese AND English punctuation for sentence splitting
        sentences = re.split(r'[。.!?！？]', content)

        for sent in sentences:
            sent = sent.strip()
            if len(sent) > 10:  # Skip very short sentences
                # P1-8 fix: add English keywords so extract_facts() works for English content
                chinese_kw = ["应该", "必须", "重要", "决定", "计划", "完成", "成功", "失败"]
                english_kw = ["should", "must", "important", "decided", "plan",
                              "completed", "success", "failed", "need to", "remember"]
                if any(kw in sent for kw in chinese_kw + english_kw):
                    facts.append(sent)

        return facts[:5]  # Limit to 5 facts


class FactType:
    """Fact type constants"""
    GENERAL = "general"
    DECISION = "decision"
    PREFERENCE = "preference"
    PROJECT = "project"
    LEARNING = "learning"
