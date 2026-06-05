"""
test_memory_hermes.py — MemoryHermes 核心测试
验证 store_and_query / forget / stats / list
"""
import pytest
import asyncio
from agentmemory.memory_manager import MemoryHermes


@pytest.fixture
def memory_hermes(tmp_path):
    """创建测试用 MemoryHermes 实例"""
    # 使用临时目录作为 workspace
    import tempfile
    workspace = tmp_path / "hermes_test"
    workspace.mkdir()
    hermes = MemoryHermes()
    return hermes


class TestMemoryHermesStoreAndQuery:
    """测试 store_and_query"""

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_memory_hermes_store_and_query(self, memory_hermes):
        """存储记忆，查询返回结果"""
        memory_id = await memory_hermes.store(
            content="这是一个测试记忆",
            metadata={"source": "test"},
            importance=0.8,
        )
        assert memory_id is not None

        results = await memory_hermes.query("测试记忆", limit=5)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_memory_hermes_store_multiple(self, memory_hermes):
        """存储多条记忆"""
        ids = []
        for i in range(3):
            mid = await memory_hermes.store(
                content=f"记忆 {i}",
                metadata={},
                importance=0.5,
            )
            ids.append(mid)
        assert len(set(ids)) == 3


class TestMemoryHermesForget:
    """测试 forget"""

    @pytest.mark.asyncio
    async def test_memory_hermes_forget(self, memory_hermes):
        """遗忘记忆"""
        memory_id = await memory_hermes.store(
            content="将被遗忘的记忆",
            metadata={},
            importance=0.5,
        )
        assert memory_id is not None
        # 遗忘（永久）
        success = await memory_hermes.forget(memory_id, permanent=True)
        assert success is True

    @pytest.mark.asyncio
    async def test_memory_hermes_forget_archive(self, memory_hermes):
        """遗忘记忆（归档）"""
        memory_id = await memory_hermes.store(
            content="将被归档的记忆",
            metadata={},
            importance=0.5,
        )
        success = await memory_hermes.forget(memory_id, permanent=False)
        assert success is True


class TestMemoryHermesStats:
    """测试 stats"""

    @pytest.mark.asyncio
    async def test_memory_hermes_stats(self, memory_hermes):
        """统计信息"""
        stats = memory_hermes.get_stats()
        assert isinstance(stats, dict)
        assert "layers" in stats
        assert stats["layers"] is not None

    @pytest.mark.asyncio
    async def test_memory_hermes_stats_sync(self, memory_hermes):
        """stats 同步方法"""
        stats = memory_hermes.stats()
        assert isinstance(stats, dict)


class TestMemoryHermesList:
    """测试 list"""

    @pytest.mark.asyncio
    async def test_memory_hermes_list(self, memory_hermes):
        """列出记忆"""
        # 先存储一些记忆
        for i in range(3):
            await memory_hermes.store(
                content=f"列表测试 {i}",
                metadata={},
                importance=0.5,
            )
        ids = await memory_hermes.list(limit=100)
        assert isinstance(ids, list)


class TestMemoryHermesSession:
    """测试 session 管理"""

    @pytest.mark.asyncio
    async def test_memory_hermes_prefetch(self, memory_hermes):
        """预取相关记忆"""
        await memory_hermes.store(
            content="预取测试内容",
            metadata={},
            importance=0.5,
        )
        prefetch_text = await memory_hermes.prefetch("预取")
        # 预取结果可能是空字符串（取决于 retriever 实现）
        assert isinstance(prefetch_text, str)

    @pytest.mark.asyncio
    async def test_memory_hermes_on_session_end(self, memory_hermes):
        """会话结束"""
        await memory_hermes.store(content="会话测试", metadata={}, importance=0.5)
        stats = await memory_hermes.on_session_end(summary="测试会话总结")
        assert isinstance(stats, dict)
        assert "total_turns" in stats

    @pytest.mark.asyncio
    async def test_memory_hermes_run_decay_check(self, memory_hermes):
        """运行衰减检查"""
        result = await memory_hermes.run_decay_check()
        assert isinstance(result, dict)


class TestMemoryHermesExecute:
    """测试 execute 统一接口"""

    @pytest.mark.asyncio
    async def test_memory_hermes_execute_store(self, memory_hermes):
        """execute store"""
        result = await memory_hermes.execute(
            "store",
            {"content": "execute 测试", "importance": 0.7},
        )
        assert result.get("success") is True

    @pytest.mark.asyncio
    async def test_memory_hermes_execute_query(self, memory_hermes):
        """execute query"""
        await memory_hermes.store(content="execute query 测试", metadata={}, importance=0.5)
        result = await memory_hermes.execute("query", {"query": "execute", "limit": 5})
        assert result.get("success") is True

    @pytest.mark.asyncio
    async def test_memory_hermes_execute_get_stats(self, memory_hermes):
        """execute get_stats"""
        result = await memory_hermes.execute("get_stats")
        assert result.get("success") is True

    @pytest.mark.asyncio
    async def test_memory_hermes_execute_unknown_action(self, memory_hermes):
        """execute 未知 action"""
        result = await memory_hermes.execute("unknown_action")
        assert result.get("success") is False
