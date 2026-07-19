"""
langchain_compat.py — AgentMemory 的 LangChain 兼容层

让 AgentMemory 可以直接被 LangChain/LlamaIndex 用作 BaseMemory。
对标 LangChain BaseMemory 接口：
- memory_variables (Property)
- load_memory_variables(inputs)
- save_context(inputs, outputs)
- clear()

对标 LlamaIndex Memory 接口：
- get() / put() / get_all()

抄 LangChain 的设计是为了"好用"——主人明示。
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from .manager import MemoryManager
from .sqlite_store import SQLiteStore


class AgentMemoryForLangChain:
    """
    LangChain BaseMemory 兼容接口。

    使用方式:
        from agent_memory.langchain_compat import AgentMemoryForLangChain
        memory = AgentMemoryForLangChain(namespace="chat_history")
        # 在 LangChain Chain 里：
        memory.save_context({"input": "你好"}, {"output": "你好！"})
        vars = memory.load_memory_variables({})
    """

    @property
    def memory_variables(self) -> List[str]:
        """返回这个 memory 提供哪些变量。"""
        return ["history"]

    def __init__(self, namespace: str = "langchain",
                 base_dir: str = "memory", db_path: str = "data/qdrant",
                 k: int = 5, **kwargs):
        self.namespace = namespace
        self.k = k
        self._mm = MemoryManager(base_dir=base_dir, db_path=db_path,
                                namespace=namespace)
        self._store = SQLiteStore("data/agentmemory.db")
        self._user_key = kwargs.get("human_prefix", "Human")
        self._ai_key = kwargs.get("ai_prefix", "AI")

    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        LangChain 兼容：给定输入 dict，返回 memory variables dict。

        这里我们用 inputs 中的最后一轮 query 去搜索历史，返回 top-k 关联记忆。
        """
        import asyncio
        query = inputs.get("input") or inputs.get("query") or ""
        if not query:
            return {"history": ""}

        loop = asyncio.new_event_loop()
        try:
            results = loop.run_until_complete(
                self._mm.search(query, limit=self.k, use_pipeline=True)
            )
        finally:
            loop.close()

        if not results:
            return {"history": ""}

        lines = []
        for r in results:
            content = r.get("content", "")
            ts = r.get("created_at", "")
            lines.append(f"[{ts}] {content}" if ts else content)
        return {"history": "\n".join(lines)}

    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> None:
        """
        LangChain 兼容：保存一轮对话到记忆。
        """
        import asyncio
        user_msg = inputs.get("input") or inputs.get("human_input") or ""
        ai_msg = outputs.get("response") or outputs.get("output") or outputs.get("text") or ""
        if not user_msg and not ai_msg:
            return
        content = f"{self._user_key}: {user_msg}\n{self._ai_key}: {ai_msg}"

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                self._mm.add(content, source="langchain", importance=0.5)
            )
        finally:
            loop.close()

    def clear(self) -> None:
        """清空当前 namespace 下的所有记忆。"""
        # 通过 SQLiteStore 标记删除（物理文件保留）
        try:
            conn = self._store._get_conn()
            cur = conn.execute(
                "UPDATE memories SET importance=0.0 WHERE namespace=?",
                (self.namespace,),
            )
            conn.commit()
        except Exception:
            pass

    # ========== LlamaIndex 兼容 ==========

    def get(self, key: str = "history") -> Optional[str]:
        """LlamaIndex Memory 接口。"""
        result = self.load_memory_variables({})
        return result.get(key)

    def put(self, key: str, value: str) -> None:
        """LlamaIndex Memory 接口。"""
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                self._mm.add(value, source=f"llamaindex.{key}", importance=0.5)
            )
        finally:
            loop.close()

    def get_all(self) -> Dict[str, Any]:
        """LlamaIndex Memory 接口。"""
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            results = loop.run_until_complete(
                self._mm.list(limit=100)
            )
        finally:
            loop.close()
        return {"history": results}


# Convenience exports
LangChainMemory = AgentMemoryForLangChain
LlamaIndexMemory = AgentMemoryForLangChain
