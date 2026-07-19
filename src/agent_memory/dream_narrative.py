"""
dream_narrative.py — LLM 梦境叙事生成

把梦境产物（结构化数据）转化为可读的自然语言"梦境日报"。
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class DreamNarrativeGenerator:
    """梦境叙事生成器"""

    def __init__(self, sqlite_store=None, llm_fn=None):
        self.store = sqlite_store
        self.llm_fn = llm_fn  # async callable: llm_fn(prompt) -> str

    def build_prompt(self, phase: str, report: Dict) -> str:
        """构建 LLM 提示词。"""
        artifacts = report.get("artifacts", [])
        data = report.get("data", {})
        sig = report.get("phases", {}).get("signal_decomposition", {}).get("aggregate", {})

        lines = [f"## 梦境 {phase.upper()} 简报"]
        lines.append(f"时间: {datetime.now(timezone.utc).isoformat()}")
        lines.append(f"记忆库: {data.get('memories', 0)} 条记忆, {data.get('tags', 0)} 个标签")
        if sig:
            lines.append(f"覆盖率: {sig.get('avg_coverage', 0):.2f}")
            lines.append(f"新颖度: {sig.get('avg_novelty', 0):.2f}")

        lines.append(f"\n### 梦境产物 ({len(artifacts)} 个)")
        for art in artifacts[:5]:
            a_type = art.get("type", art.get("category", "unknown"))
            a_conf = art.get("confidence", 0)
            a_tags = art.get("tags", [])
            lines.append(f"- [{a_type}] 置信度={a_conf:.2f} 标签={','.join(a_tags[:3])}")

        lines.append("\n请根据以上数据写一段自然语言的梦境日记（中文，100-200字）。")
        lines.append("风格：像人类在日记里记录梦境一样，但又像 AI 在分析自己的记忆信号。")
        return "\n".join(lines)

    async def generate(self, phase: str, report: Dict) -> Optional[str]:
        """生成梦境叙事并写入 kv_store。"""
        if not self.llm_fn:
            # fallback: 模板化叙事
            return self._template_narrative(phase, report)

        prompt = self.build_prompt(phase, report)
        try:
            narrative = await self.llm_fn(prompt)
            if narrative and self.store:
                self.store.kv_set(f"dream_narrative_{phase}_{datetime.now(timezone.utc).isoformat()}", {
                    "narrative": narrative,
                    "phase": phase,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
            return narrative
        except Exception as e:
            return self._template_narrative(phase, report)

    def _template_narrative(self, phase: str, report: Dict) -> str:
        """模板化叙事（无 LLM 时的回退）。"""
        artifacts = report.get("artifacts", [])
        data = report.get("data", {})
        cons = report.get("phases", {}).get("consolidation", {})
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

        phase_names = {"light": "浅眠", "deep": "深睡", "rem": "REM"}
        pn = phase_names.get(phase, phase)

        lines = [f"## {now} | {pn}梦境"]
        lines.append("")
        lines.append(f"梦境扫描了 {data.get('memories',0)} 条记忆和 {data.get('tags',0)} 个标签。")
        if artifacts:
            lines.append(f"产生了 {len(artifacts)} 个梦境产物：")
            for a in artifacts[:3]:
                lines.append(f"- {a.get('tags', ['未知'])}")
        written = cons.get("written", 0)
        drafted = cons.get("drafted", 0)
        if written or drafted:
            lines.append(f"其中 {written} 个固化写入，{drafted} 个存入草稿区。")

        return "\n".join(lines)

    def format_as_memory(self, narrative: str, phase: str) -> Dict:
        """把叙事格式化为可存储的记忆条目。"""
        return {
            "id": f"dream_narrative_{phase}_{int(datetime.now(timezone.utc).timestamp())}",
            "content": narrative,
            "tags": [f"梦境叙事", f"{phase}_dream"],
            "confidence": 1.0,
            "importance": 0.4,
            "category": "dream_narrative",
            "meta": {"phase": phase, "narrative": True},
        }
