"""
AgentMemory v0.3 - L1 LCM (Long-term Context Memory) Compressor

Compresses multiple memories into a concise context for AI prompts.
Output format: narrative paragraphs + key facts list.

This is a simplified implementation that works without external LLM APIs.
"""

import re
from typing import List, Dict, Any
from datetime import datetime


class L1LCMCompressor:
    """
    L1 Memory Compressor

    Compresses multiple memories into a concise summary for AI context.
    Uses simple extractive summarization (no external API required).
    """

    def __init__(self, max_context_chars: int = 4000):
        """
        Initialize L1 compressor.

        Args:
            max_context_chars: Maximum characters in compressed output
        """
        self.max_context_chars = max_context_chars

    def compress(self, memories: List[Dict[str, Any]], query: str = "") -> str:
        """
        Compress multiple memories into a concise context.

        Args:
            memories: List of memory dicts with 'id', 'content', 'meta' keys
            query: Optional query to focus compression (currently unused; P2-3)

        Returns:
            Compressed context string
        """
        # P0-7 fix: guard against None (if not memories raises TypeError on None)
        if not memories:
            return "No relevant memories found."

        # P0-8 fix: filter out non-dict items to prevent AttributeError
        # when mem.get() is called on non-dict objects
        memories = [m for m in memories if isinstance(m, dict)]

        # Group by importance
        important_memories = []
        normal_memories = []

        for mem in memories:
            importance = mem.get("meta", {}).get("importance", 0.5)
            if importance >= 0.7:
                important_memories.append(mem)
            else:
                normal_memories.append(mem)

        # Sort by recency (most recent first)
        def get_timestamp(mem):
            meta = mem.get("meta", {})
            ts = meta.get("created_at", "")
            try:
                return datetime.fromisoformat(ts)
            except ValueError:
                # P1-6 fix: catch only ValueError, not bare except: which
                # would catch KeyboardInterrupt, SystemExit, AttributeError, etc.
                return datetime.min

        important_memories.sort(key=get_timestamp, reverse=True)
        normal_memories.sort(key=get_timestamp, reverse=True)

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
                lines.append(f"- [{category}]{tags_str} {content}")
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
