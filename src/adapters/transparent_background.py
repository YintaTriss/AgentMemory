"""
AgentMemory 透明后台适配器

用途：
1. OpenClaw 后台模式 — 自动存取记忆，无需关键词触发
2. 心跳钩子 — 每 N 分钟自动分析对话上下文并存储
3. 上下文预取 — 回复前自动注入相关记忆

使用方式（OpenClaw skill）：
    skill: agent-memory (transparent)
    触发：自动（心跳 cron 每 5 分钟一次）

Python API：
    from src.adapters.transparent_background import TransparentBackground
    tb = TransparentBackground(agent_id="main")
    await tb.capture_current_context()   # 手动触发一次
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent_memory import MemoryManager

DEFAULT_IMPORTANCE = 0.6
HEARTBEAT_INTERVAL_MINUTES = 5
AUTO_SUMMARY_THRESHOLD_TURNS = 20


class TransparentBackground:
    """
    透明后台记忆捕获器。

    不需要用户显式触发，自动：
    - 跟踪会话状态
    - 提取关键事实
    - 周期性存储摘要记忆
    - 预取相关记忆供上下文使用
    """

    def __init__(
        self,
        agent_id: str = "default",
        base_dir: str = "memory",
        importance: float = DEFAULT_IMPORTANCE,
        heartbeat_minutes: int = HEARTBEAT_INTERVAL_MINUTES,
    ):
        self.agent_id = agent_id
        self.mm = MemoryManager(base_dir=base_dir)
        self.importance = importance
        self.heartbeat_minutes = heartbeat_minutes
        self._last_capture_at: Optional[str] = None
        self._turn_count = 0
        self._pending_user_messages: list[str] = []
        self._pending_assistant_messages: list[str] = []
        self._last_summary_id: Optional[str] = None

    async def capture_current_context(
        self,
        user_message: Optional[str] = None,
        assistant_message: Optional[str] = None,
    ) -> dict:
        """
        捕获当前上下文消息并自动决定是否存储。

        存储策略：
        - 用户消息 → 记录到待处理队列
        - 助理回复 → 尝试与用户消息配对存储
        - 每 20 轮自动生成会话摘要
        - 心跳间隔超过阈值时强制摘要

        Returns:
            dict with keys: stored (bool), reason (str), memory_id (str, optional)
        """
        result = {"stored": False, "reason": "no_op", "memory_id": None}

        if user_message:
            self._pending_user_messages.append(user_message)
            self._turn_count += 1

        if assistant_message:
            self._pending_assistant_messages.append(assistant_message)

        # 尝试配对存储（用户问 + 助理答）
        if self._pending_user_messages and self._pending_assistant_messages:
            user_msg = self._pending_user_messages[-1]
            assistant_msg = self._pending_assistant_messages[-1]

            # 只存储有实质内容的对话
            if len(user_msg) > 10 and len(assistant_msg) > 10:
                pair_content = (
                    f"用户问：{user_msg}\n"
                    f"助理答：{assistant_msg}"
                )
                try:
                    mem_id = await self.mm.add(
                        content=pair_content,
                        importance=self.importance * 0.8,  # 对话重要性略低
                        category_path="会话/对话记录",
                        tags=["auto-capture", "dialogue"],
                        source="transparent-background",
                    )
                    result = {
                        "stored": True,
                        "reason": "dialogue_pair",
                        "memory_id": mem_id,
                    }
                except Exception:
                    pass  # 静默失败，不打断主流程

        # 强制摘要条件
        should_summary = (
            self._turn_count >= AUTO_SUMMARY_THRESHOLD_TURNS
            or self._should_force_summary()
        )

        if should_summary:
            summary_id = await self._generate_session_summary()
            result = {
                "stored": True,
                "reason": "periodic_summary",
                "memory_id": summary_id,
            }
            self._turn_count = 0

        return result

    def _should_force_summary(self) -> bool:
        """检查是否应该强制生成摘要（心跳超时）"""
        if self._last_capture_at is None:
            return False
        try:
            last = datetime.fromisoformat(self._last_capture_at)
            elapsed = datetime.now() - last
            return elapsed.total_seconds() > self.heartbeat_minutes * 60 * 2
        except Exception:
            return False

    async def _generate_session_summary(self) -> Optional[str]:
        """生成当前会话摘要记忆"""
        # 合并所有待处理的对话
        all_user = "\n".join(self._pending_user_messages)
        all_assistant = "\n".join(self._pending_assistant_messages)

        if not all_user and not all_assistant:
            return None

        # L1 压缩（如果可用）
        try:
            all_content = f"=== 会话摘要 ===\n\n用户：{all_user}\n\n助手：{all_assistant}"
        except Exception:
            all_content = all_user or all_assistant

        self._pending_user_messages.clear()
        self._pending_assistant_messages.clear()

        try:
            mem_id = await self.mm.add(
                content=all_content[:2000],  # 截断避免过长
                importance=self.importance,
                category_path="会话/定期摘要",
                tags=["auto-capture", "summary", "session"],
                source="transparent-background",
            )
            self._last_summary_id = mem_id
            self._last_capture_at = datetime.now().isoformat()
            return mem_id
        except Exception:
            return None

    async def prefetch_for_context(self, current_query: str, limit: int = 5) -> list[dict]:
        """
        预取与当前上下文相关的记忆。

        在 agent 回复前调用，结果可直接注入到 AI Context。

        Returns:
            相关记忆列表，每项含 content/score/category_path
        """
        try:
            results = await self.mm.search(current_query, limit=limit)
            return [
                {
                    "content": r.get("content"),
                    "score": round(r.get("score", 0), 4),
                    "category_path": r.get("category_path"),
                    "memory_id": r.get("id"),
                }
                for r in results
            ]
        except Exception:
            return []

    async def get_recent_memories(self, limit: int = 10) -> list[dict]:
        """获取最近添加的记忆"""
        try:
            memories = await self.mm.list(category_path=None, limit=limit)
            return [
                {
                    "memory_id": m.get("id"),
                    "content": m.get("content", "")[:200],
                    "category_path": m.get("category_path"),
                    "created_at": m.get("created_at"),
                }
                for m in reversed(memories)  # newest first
            ]
        except Exception:
            return []

    def get_stats(self) -> dict:
        """获取统计（同步）"""
        try:
            # 同步封装
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果已在运行，创建一个新任务
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.mm.stats())
                    return future.result(timeout=5)
            else:
                return asyncio.run(self.mm.stats())
        except Exception:
            return {"error": "stats_unavailable"}

    async def inject_context_for_prompt(
        self,
        current_message: str,
        max_memories: int = 5,
        max_chars: int = 2000,
    ) -> str:
        """
        生成记忆增强的上下文字符串，可直接拼接到 system prompt。

        使用方式：
            enhanced_system = base_system_prompt + "\\n\\n" + await tb.inject_context_for_prompt(user_msg)

        Args:
            current_message: 当前用户消息
            max_memories: 最多注入几条记忆
            max_chars: 最多注入多少字符

        Returns:
            格式化的记忆注入字符串，如果无相关记忆则返回空字符串
        """
        memories = await self.prefetch_for_context(current_message, limit=max_memories)
        if not memories:
            return ""

        lines = ["\n\n[相关记忆]"]
        total_chars = 0

        for m in memories:
            content = m["content"]
            cat = m.get("category_path", "未分类")
            score = m["score"]

            entry = f"- [{cat}] {content}"
            if total_chars + len(entry) > max_chars:
                break

            lines.append(entry)
            total_chars += len(entry)

        lines.append("[/相关记忆]\n")
        return "\n".join(lines)


# ── CLI 命令 ────────────────────────────────────────────────────────────────
def main():
    import argparse

    parser = argparse.ArgumentParser(description="AgentMemory 透明后台记忆捕获器")
    parser.add_argument("--agent-id", default="default", help="Agent ID")
    parser.add_argument("--base-dir", default="memory", help="记忆存储目录")
    parser.add_argument("--importance", type=float, default=0.6, help="默认重要性")
    parser.add_argument("--interval", type=int, default=5, help="心跳间隔（分钟）")
    parser.add_argument("--once", action="store_true", help="只运行一次捕获然后退出")
    args = parser.parse_args()

    tb = TransparentBackground(
        agent_id=args.agent_id,
        base_dir=args.base_dir,
        importance=args.importance,
        heartbeat_minutes=args.interval,
    )

    if args.once:
        result = asyncio.run(tb.capture_current_context())
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(
            f"AgentMemory 透明后台已启动（心跳 {args.interval} 分钟，Agent: {args.agent_id}）",
            file=sys.stderr,
        )
        print("按 Ctrl+C 停止", file=sys.stderr)
        try:
            while True:
                asyncio.run(asyncio.sleep(args.interval * 60))
                result = asyncio.run(tb.capture_current_context())
                print(
                    f"[{datetime.now().isoformat()}] captured: {result}",
                    file=sys.stderr,
                )
        except KeyboardInterrupt:
            print("\n已停止", file=sys.stderr)


if __name__ == "__main__":
    main()
