"""
AgentMemory v0.3 - L1 LCM Compressor
Compresses multiple memories into a concise context for AI prompts.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple


class L1LCMCompressor:
    """L1 Memory Compressor - rule-based summarization."""
    
    def __init__(self, llm_client=None, max_context_chars: int = 4000):
        self.llm_client = llm_client
        self.max_context_chars = max_context_chars
    
    def compress(self, memory_ids: List[str], l4_store, l3_store) -> str:
        """
        Compress multiple memories into a concise summary.
        L4 store should have load_existing() method.
        """
        if not memory_ids:
            return "No relevant memories found."
        
        memories = []
        for mid in memory_ids:
            # Try load_existing first (returns dict), fallback to load (returns str)
            if hasattr(l4_store, 'load_existing'):
                mem = self._sync_load_existing(mid, l4_store)
            else:
                mem = self._sync_load(mid, l4_store)
            
            if mem:
                memories.append({
                    "id": mid,
                    "content": mem.get("content", ""),
                    "importance": mem.get("meta", {}).get("importance", 0.5),
                    "category_path": mem.get("meta", {}).get("category_path", "general"),
                    "tags": mem.get("meta", {}).get("tags", []),
                    "created_at": mem.get("meta", {}).get("created_at", ""),
                })
        
        if not memories:
            return "No memories found for the given IDs."
        
        # Group by category
        categories = {}
        for mem in memories:
            cat = mem.get("category_path", "general")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(mem)
        
        # Sort by importance within each category
        for cat in categories:
            categories[cat].sort(key=lambda x: x.get("importance", 0), reverse=True)
        
        lines = ["# Relevant Memories", ""]
        
        # Key facts section (high importance)
        important = [m for m in memories if m.get("importance", 0) >= 0.7]
        if important:
            important.sort(key=lambda x: x.get("importance", 0), reverse=True)
            lines.append("## Key Facts")
            for mem in important[:10]:
                tags = mem.get("tags", [])
                tags_str = f" [{', '.join(tags)}]" if tags else ""
                lines.append(f"- {mem.get('content', '')}{tags_str}")
            lines.append("")
        
        # Category sections
        for cat, cat_memories in sorted(categories.items()):
            if cat == "general" and not cat_memories:
                continue
            lines.append(f"## {cat}")
            for mem in cat_memories[:5]:
                lines.append(f"- {mem.get('content', '')}")
            lines.append("")
        
        result = "\n".join(lines)
        if len(result) > self.max_context_chars:
            result = result[:self.max_context_chars - 100] + "\n\n... (truncated)"
        return result
    
    def _sync_load_existing(self, memory_id: str, l4_store) -> Optional[Dict[str, Any]]:
        """Sync wrapper for async load_existing"""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create a new loop in a thread if we're already in an async context
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, l4_store.load_existing(memory_id))
                    return future.result()
            else:
                return asyncio.run(l4_store.load_existing(memory_id))
        except Exception:
            return None
    
    def _sync_load(self, memory_id: str, l4_store) -> Optional[Dict[str, Any]]:
        """Sync wrapper for async load"""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, l4_store.load(memory_id))
                    content = future.result()
                    if content:
                        return {"content": content, "meta": {}}
                    return None
            else:
                content = asyncio.run(l4_store.load(memory_id))
                if content:
                    return {"content": content, "meta": {}}
                return None
        except Exception:
            return None
    
    def compress_session(self, turns: List[Tuple[str, str]]) -> str:
        """Summarize a conversation session."""
        if not turns:
            return "No conversation turns to summarize."
        
        important_keywords = [
            "决定", "决策", "选择", "重要", "必须", "应该",
            "完成", "成功", "失败", "计划", "目标", "下周",
            "记住", "别忘了", "下次", "之后",
        ]
        
        key_sentences = []
        for i, (user, assistant) in enumerate(turns):
            combined = f"{user} {assistant}"
            sentences = self._split_sentences(combined)
            for sent in sentences:
                sent = sent.strip()
                if len(sent) > 5:
                    for kw in important_keywords:
                        if kw in sent:
                            key_sentences.append(f"[Turn {i+1}] {sent}")
                            break
        
        lines = ["# Session Summary", ""]
        if key_sentences:
            lines.append("## Key Points")
            for sent in key_sentences[:10]:
                lines.append(f"- {sent}")
            lines.append("")
        else:
            if turns:
                first = turns[0]
                lines.append(f"- Started: {first[0][:100]}")
                if len(turns) > 1:
                    last = turns[-1]
                    lines.append(f"- Recent: {last[0][:100]}")
            lines.append("")
        return "\n".join(lines)
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences using Chinese punctuation."""
        text = text.replace("！", "。").replace("？", "。")
        return [s.strip() for s in text.split("。") if s.strip()]
    
    def extract_facts(self, text: str) -> List[Dict[str, Any]]:
        """Extract facts from text using rules."""
        facts = []
        sentences = self._split_sentences(text)
        
        type_keywords = {
            "decision": ["决定", "决策", "选择", "采用", "放弃"],
            "preference": ["喜欢", "偏好", "倾向", "不要", "想要"],
            "project": ["项目", "开发", "完成", "进行中", "迭代"],
            "learning": ["学习", "课程", "训练", "研究"],
            "general": [],
        }
        
        high_importance_kw = ["重要", "必须", "关键", "核心"]
        medium_importance_kw = ["应该", "建议", "最好"]
        
        for sent in sentences:
            sent = sent.strip()
            if len(sent) < 5:
                continue
            
            fact_type = "general"
            for ftype, keywords in type_keywords.items():
                if ftype != "general":
                    for kw in keywords:
                        if kw in sent:
                            fact_type = ftype
                            break
                    if fact_type != "general":
                        break
            
            importance = 0.5
            for kw in high_importance_kw:
                if kw in sent:
                    importance = 0.9
                    break
            if importance == 0.5:
                for kw in medium_importance_kw:
                    if kw in sent:
                        importance = 0.7
                        break
            
            facts.append({"content": sent, "fact_type": fact_type, "impor
