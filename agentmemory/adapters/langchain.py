"""
LangChain 适配器

将 AgentMemory 集成到 LangChain 作为聊天记忆组件。
"""

import sys
import os
from pathlib import Path
from typing import Any, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from .base import FrameworkAdapter, ToolSpec, validate_tool_spec

__all__ = ["LangChainAdapter"]


class AgentMemoryChatHistory:
    """
    LangChain BaseChatMemory 实现
    
    将 AgentMemory 作为 LangChain 的聊天记忆组件使用。
    """

    def __init__(self, memory_hermes: Any):
        self.mh = memory_hermes
        self.messages: list[dict] = []

    @property
    def memory_variables(self) -> list[str]:
        """LangChain 要求返回可用的内存变量名"""
        return ["chat_history"]

    def load_memory_variables(self, inputs: dict) -> dict:
        """加载记忆变量"""
        return {"chat_history": self.messages}

    async def aload_memory_variables(self, inputs: dict) -> dict:
        """异步加载记忆变量"""
        return self.load_memory_variables(inputs)

    def save_context(self, inputs: dict, outputs: dict) -> None:
        """保存对话上下文"""
        user_msg = inputs.get("input", "")
        ai_msg = outputs.get("output", "")
        
        if user_msg:
            self.messages.append({"role": "user", "content": user_msg})
        if ai_msg:
            self.messages.append({"role": "assistant", "content": ai_msg})

    async def asent_context(self, inputs: dict, outputs: dict) -> None:
        """异步保存对话上下文"""
        self.save_context(inputs, outputs)

    def clear(self) -> None:
        """清空记忆"""
        self.messages = []


class LangChainAdapter:
    """
    LangChain 框架适配器
    
    提供与 LangChain 的集成，将 AgentMemory 作为聊天记忆组件使用。
    """

    framework = "langchain"
    version = "1.0.0"

    def __init__(self):
        self._mh: Optional[Any] = None
        self._chat_history: Optional[AgentMemoryChatHistory] = None

    def bind(self, mh: Any) -> AgentMemoryChatHistory:
        """
        绑定 MemoryHermes 实例
        
        Args:
            mh: MemoryHermes 实例
            
        Returns:
            AgentMemoryChatHistory 实例
        """
        self._mh = mh
        self._chat_history = AgentMemoryChatHistory(mh)
        return self._chat_history

    def export_tools(self) -> list[ToolSpec]:
        """
        导出工具列表
        
        Returns:
            5 个 ToolSpec 实例
        """
        return [
            ToolSpec(
                name="memory_store",
                description="Store a new memory with content and importance",
                parameters={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Memory content"},
                        "importance": {
                            "type": "number",
                            "description": "Importance 0-1",
                            "default": 0.5,
                        },
                        "metadata": {
                            "type": "object",
                            "description": "Additional metadata",
                        },
                    },
                    "required": ["content"],
                },
                risk_level="write",
            ),
            ToolSpec(
                name="memory_query",
                description="Query relevant memories",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Query text"},
                        "limit": {
                            "type": "integer",
                            "description": "Max results",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
                risk_level="read",
            ),
            ToolSpec(
                name="memory_forget",
                description="Forget/delete a memory",
                parameters={
                    "type": "object",
                    "properties": {
                        "memory_id": {"type": "string", "description": "Memory ID"},
                        "permanent": {
                            "type": "boolean",
                            "description": "Permanent deletion",
                            "default": True,
                        },
                    },
                    "required": ["memory_id"],
                },
                risk_level="destructive",
            ),
            ToolSpec(
                name="memory_stats",
                description="Get memory system statistics",
                parameters={"type": "object", "properties": {}},
                risk_level="read",
            ),
            ToolSpec(
                name="memory_prefetch",
                description="Prefetch relevant memories for faster access",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Query text"},
                    },
                    "required": ["query"],
                },
                risk_level="read",
            ),
        ]

    def get_metadata(self) -> dict:
        """
        获取适配器元数据
        
        Returns:
            元数据字典
        """
        return {
            "framework": "langchain",
            "transport": "python-import",
            "requires": "langchain>=0.1",
            "version": self.version,
            "description": "LangChain chat memory integration",
        }

    @property
    def chat_history(self) -> Optional[AgentMemoryChatHistory]:
        """获取聊天历史实例"""
        return self._chat_history
