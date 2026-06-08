"""
AgentMemory x AgentTeam 对接模块

功能：
- AgentTeamMemoryProvider: 实现 AgentTeam MemoryProvider 接口
- TeamContext: 从环境变量读取 AgentTeam 团队上下文
- get_memory_provider(): 工厂函数，根据环境变量创建合适的 provider

使用方式：
  1. AgentTeam spawn 时注入环境变量：
     AGENTMEMORY_BASE_DIR=/path/to/memory
     AGENTMEMORY_NAMESPACE=my-team/agent-1
     AGENTTEAM_TEAM_NAME=my-team
     AGENTTEAM_AGENT_ID=agent-1
     AGENTTEAM_SHARED_DIR=/path/to/shared
  2. Agent 端：
     from agent_memory.agentteam_integration import get_memory_provider
     provider = get_memory_provider()
     context = provider.prefetch("用户项目信息")  # 注入记忆到上下文
     provider.sync_turn(user_msg, assistant_msg)   # 同步对话到记忆
"""

from __future__ import annotations

import os
import logging
from typing import TYPE_CHECKING, List, Optional

# AgentTeam 的 MemoryProvider 接口（可选依赖）
if TYPE_CHECKING:
    from agentteam.memory.provider import MemoryProvider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 环境变量键名
# ---------------------------------------------------------------------------
ENV_AGENTMEMORY_BASE_DIR = "AGENTMEMORY_BASE_DIR"
ENV_AGENTMEMORY_NAMESPACE = "AGENTMEMORY_NAMESPACE"
ENV_AGENTMEMORY_DB_PATH = "AGENTMEMORY_DB_PATH"
ENV_AGENTTEAM_TEAM = "AGENTTEAM_TEAM_NAME"
ENV_AGENTTEAM_AGENT = "AGENTTEAM_AGENT_ID"
ENV_AGENTTEAM_SHARED_DIR = "AGENTTEAM_SHARED_DIR"


# ---------------------------------------------------------------------------
# TeamContext — 从环境变量读取团队上下文
# ---------------------------------------------------------------------------

class TeamContext:
    """从环境变量构建的团队上下文"""

    def __init__(
        self,
        team: Optional[str] = None,
        agent_id: Optional[str] = None,
        shared_dir: Optional[str] = None,
    ):
        self.team = team
        self.agent_id = agent_id
        self.shared_dir = shared_dir

    @classmethod
    def from_env(cls) -> "TeamContext":
        """从当前进程环境变量构建上下文"""
        return cls(
            team=os.environ.get(ENV_AGENTTEAM_TEAM),
            agent_id=os.environ.get(ENV_AGENTTEAM_AGENT),
            shared_dir=os.environ.get(ENV_AGENTTEAM_SHARED_DIR),
        )

    @property
    def is_in_team(self) -> bool:
        """是否在团队中运行"""
        return bool(self.team and self.agent_id)

    @property
    def namespace(self) -> str:
        """AgentMemory namespace: team/agent_id"""
        if self.team and self.agent_id:
            return f"{self.team}/{self.agent_id}"
        ns = os.environ.get(ENV_AGENTMEMORY_NAMESPACE)
        if ns:
            return ns
        return os.environ.get("USER") or "default"

    def __repr__(self) -> str:
        return (
            f"TeamContext(team={self.team!r}, agent_id={self.agent_id!r}, "
            f"shared_dir={self.shared_dir!r}, namespace={self.namespace!r})"
        )


# ---------------------------------------------------------------------------
# AgentTeamMemoryProvider — AgentTeam MemoryProvider 接口实现
# ---------------------------------------------------------------------------

class AgentTeamMemoryProvider:
    """
    AgentMemory 实现的 AgentTeam MemoryProvider 接口。

    对齐 AgentTeam 的 MemoryProvider 抽象：
    - prefetch(query): 预取相关记忆，注入 AI 上下文
    - sync_turn(user_msg, assistant_msg): 同步对话轮到记忆
    - on_session_end(messages): 会话结束时提取事实
    - on_pre_compress(messages): 上下文压缩前提取洞察

    使用示例（AgentTeam agent 端）：
        from agent_memory.agentteam_integration import get_memory_provider

        # 创建 provider（读取环境变量自动配置）
        provider = get_memory_provider()

        # prefetch 在每次 AI 调用前调用，注入相关记忆
        context = provider.prefetch("石榴籽项目 答辩")
        # → 返回格式化的记忆文本，注入系统提示

        # sync_turn 在每次对话回合后调用
        provider.sync_turn(user_msg, assistant_msg)
    """

    def __init__(
        self,
        base_dir: Optional[str] = None,
        db_path: Optional[str] = None,
        namespace: Optional[str] = None,
        team: Optional[str] = None,
        agent_id: Optional[str] = None,
        shared_dir: Optional[str] = None,
        auto_commit: bool = True,
    ):
        self._ctx = TeamContext(
            team=team,
            agent_id=agent_id,
            shared_dir=shared_dir,
        )
        self._base_dir = base_dir
        self._db_path = db_path
        self._namespace = namespace or self._ctx.namespace
        self._shared_dir = shared_dir or self._ctx.shared_dir
        self._auto_commit = auto_commit
        self._manager = None
        self._shared_manager = None
        self._initialized = False

    @property
    def name(self) -> str:
        return "agentmemory"

    # ---------------------------------------------------------------------------
    # AgentTeam MemoryProvider 接口
    # ---------------------------------------------------------------------------

    def prefetch(self, query: str) -> str:
        """
        后台预取记忆，注入 AI 上下文。

        Args:
            query: 查询关键词/问题

        Returns:
            格式化记忆文本，可直接拼接到系统提示词
        """
        if not self._ensure_initialized():
            return ""
        try:
            import asyncio
            results = asyncio.get_event_loop().run_until_complete(
                self._manager.search(query, limit=5)
            )
            if not results:
                return ""
            lines = ["[相关记忆]"]
            for r in results:
                score = r.get("score", 0)
                content = r.get("content", "")
                cat = r.get("category", "")
                lines.append(f"- [{cat}] {content}")
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"prefetch failed: {e}")
            return ""

    def sync_turn(self, user_msg: str, assistant_msg: str) -> None:
        """
        同步对话到记忆（每次对话回合后调用）。

        Args:
            user_msg: 用户消息
            assistant_msg: 助手回复
        """
        if not self._ensure_initialized():
            return
        try:
            import asyncio
            combined = f"用户: {user_msg}\n助手: {assistant_msg}"
            asyncio.get_event_loop().run_until_complete(
                self._manager.add(
                    content=combined,
                    importance=0.5,
                    category_path="conversation",
                    tags=["dialogue"],
                    source="agentteam",
                )
            )
        except Exception as e:
            logger.warning(f"sync_turn failed: {e}")

    def on_session_end(self, messages: List[dict]) -> None:
        """
        会话结束时从对话历史提取关键事实。

        Args:
            messages: 完整对话历史 [{role, content}, ...]
        """
        if not self._ensure_initialized():
            return
        try:
            import asyncio
            # 提取关键信息（简单启发式：含数字/日期/名称的句子）
            facts = []
            for msg in messages:
                content = msg.get("content", "") if isinstance(msg, dict) else str(msg)
                if any(c.isdigit() for c in content) and len(content) > 10:
                    facts.append(content)
            for fact in facts[:10]:
                asyncio.get_event_loop().run_until_complete(
                    self._manager.add(
                        content=fact,
                        importance=0.6,
                        category_path="fact/extracted",
                        tags=["extracted", "session-end"],
                        source="agentteam:session-end",
                    )
                )
        except Exception as e:
            logger.warning(f"on_session_end failed: {e}")

    def on_pre_compress(self, messages: List[dict]) -> str:
        """
        上下文压缩前提取核心洞察。

        Args:
            messages: 即将被压缩的对话历史

        Returns:
            提炼的洞察文本
        """
        if not self._ensure_initialized():
            return ""
        try:
            import asyncio
            # 用 L1 压缩器提炼
            texts = []
            for msg in messages:
                content = msg.get("content", "") if isinstance(msg, dict) else str(msg)
                if content:
                    texts.append(content)
            combined = "\n".join(texts[-10:])  # 最近10条
            if not combined:
                return ""
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(
                self._manager.compress_for_context(
                    memory_ids=[],  # 无需指定 ID，用 query=""
                    query="核心决策/结论/重要事实",
                )
            )
            return result or ""
        except Exception as e:
            logger.warning(f"on_pre_compress failed: {e}")
            return ""

    # ---------------------------------------------------------------------------
    # 团队协作扩展
    # ---------------------------------------------------------------------------

    def get_shared_memory(self) -> Optional[str]:
        """
        获取团队共享记忆（预取团队上下文）。
        在 agent 启动时调用，注入团队共同知识。
        """
        if not self._ensure_initialized():
            return None
        try:
            import asyncio
            if self._shared_manager:
                shared = asyncio.get_event_loop().run_until_complete(
                    self._shared_manager.get_shared(limit=10)
                )
                if shared:
                    lines = ["[团队共享记忆]"]
                    for r in shared:
                        lines.append(f"- {r.get('content', '')}")
                    return "\n".join(lines)
        except Exception as e:
            logger.warning(f"get_shared_memory failed: {e}")
        return None

    def share_to_team(self, memory_id: str) -> bool:
        """将当前 agent 的记忆共享到团队空间"""
        if not self._ensure_initialized() or not self._shared_manager:
            return False
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(
                self._shared_manager.share_to_team(self._ctx.agent_id, memory_id)
            )
        except Exception as e:
            logger.warning(f"share_to_team failed: {e}")
            return False

    # ---------------------------------------------------------------------------
    # 内部
    # ---------------------------------------------------------------------------

    def _ensure_initialized(self) -> bool:
        """延迟初始化 MemoryManager"""
        if self._initialized:
            return self._manager is not None
        self._initialized = True
        try:
            import asyncio
            from . import create_memory_manager, create_team_memory_manager

            base_dir = self._base_dir or os.environ.get(ENV_AGENTMEMORY_BASE_DIR, "memory")
            db_path = self._db_path or os.environ.get(ENV_AGENTMEMORY_DB_PATH, "data/qdrant")

            if self._ctx.is_in_team and self._ctx.team:
                # 团队模式：注册到 TeamMemoryManager
                team_mgr = create_team_memory_manager(
                    team=self._ctx.team,
                    base_dir=self._shared_dir or base_dir,
                    db_path=db_path,
                )
                self._shared_manager = team_mgr
                self._manager = team_mgr.register_agent(self._ctx.agent_id)
            else:
                # 单 agent 模式
                self._manager = create_memory_manager(
                    base_dir=base_dir,
                    db_path=db_path,
                    namespace=self._namespace,
                )

            # 测试连接
            asyncio.get_event_loop().run_until_complete(self._manager.stats())
            logger.info(
                f"AgentMemory initialized: namespace={self._namespace}, "
                f"team={self._ctx.team}, agent={self._ctx.agent_id}"
            )
            return True
        except Exception as e:
            logger.error(f"AgentMemory initialization failed: {e}")
            return False

    def __repr__(self) -> str:
        return f"AgentTeamMemoryProvider(namespace={self._namespace!r})"


# ---------------------------------------------------------------------------
# 工厂函数
# ---------------------------------------------------------------------------

def get_memory_provider(
    base_dir: Optional[str] = None,
    db_path: Optional[str] = None,
    namespace: Optional[str] = None,
    auto_commit: bool = True,
) -> AgentTeamMemoryProvider:
    """
    工厂函数：根据环境变量或参数创建 AgentTeamMemoryProvider。

    优先使用显式参数，其次环境变量。

    环境变量（AgentTeam spawn 自动注入）：
        AGENTMEMORY_BASE_DIR    - 记忆存储根目录
        AGENTMEMORY_NAMESPACE   - 命名空间
        AGENTMEMORY_DB_PATH    - 向量库路径
        AGENTTEAM_TEAM_NAME    - 团队名
        AGENTTEAM_AGENT_ID     - agent ID
        AGENTTEAM_SHARED_DIR   - 团队共享记忆目录

    Returns:
        AgentTeamMemoryProvider 实例

    使用示例：
        # 方式1：环境变量自动（AgentTeam spawn 注入）
        provider = get_memory_provider()

        # 方式2：显式参数
        provider = get_memory_provider(
            base_dir="/data/memory",
            namespace="石榴籽/技术",
        )
    """
    ctx = TeamContext.from_env()
    return AgentTeamMemoryProvider(
        base_dir=base_dir,
        db_path=db_path,
        namespace=namespace,
        team=ctx.team,
        agent_id=ctx.agent_id,
        shared_dir=ctx.shared_dir,
        auto_commit=auto_commit,
    )


def is_agentteam_environment() -> bool:
    """检测是否在 AgentTeam 环境中运行"""
    return TeamContext.from_env().is_in_team
