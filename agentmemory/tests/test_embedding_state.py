"""
test_embedding_state.py — EmbeddingStateMachine 测试
验证状态转换、队列管理
"""
import pytest
from datetime import datetime, timezone
from agentmemory.data.embedding_state import (
    EmbeddingStateMachine,
    EmbeddingState,
    EmbeddingTask,
)


@pytest.fixture
def embedding_state(tmp_path):
    """创建测试用 EmbeddingStateMachine 实例"""
    es = EmbeddingStateMachine(root_dir=str(tmp_path))
    return es


class TestEmbeddingStateMachine:
    """测试 EmbeddingStateMachine"""

    @pytest.mark.asyncio
    async def test_embedding_state_add_task(self, embedding_state):
        """添加任务"""
        await embedding_state.init()
        task = await embedding_state.add_task("mem-001", "测试文本内容")
        assert task.mem_id == "mem-001"
        assert task.text == "测试文本内容"
        assert task.state == EmbeddingState.PENDING.value

    @pytest.mark.asyncio
    async def test_embedding_state_update_state(self, embedding_state):
        """更新状态"""
        await embedding_state.init()
        await embedding_state.add_task("mem-002", "测试")
        success = await embedding_state.update_state("mem-002", EmbeddingState.GENERATING)
        assert success is True

    @pytest.mark.asyncio
    async def test_embedding_state_complete(self, embedding_state):
        """完成任务"""
        await embedding_state.init()
        await embedding_state.add_task("mem-003", "测试完成")
        await embedding_state.update_state("mem-003", EmbeddingState.GENERATING)
        await embedding_state.update_state("mem-003", EmbeddingState.COMPLETED)

        state = await embedding_state.get_state("mem-003")
        assert state == EmbeddingState.COMPLETED.value

    @pytest.mark.asyncio
    async def test_embedding_state_retry(self, embedding_state):
        """失败重试"""
        await embedding_state.init()
        await embedding_state.add_task("mem-004", "测试失败")
        await embedding_state.update_state("mem-004", EmbeddingState.FAILED)
        task = await embedding_state.retry_task("mem-004")
        assert task is not None
        assert task.retry_count == 1

    @pytest.mark.asyncio
    async def test_embedding_state_max_retries(self, embedding_state):
        """超过最大重试次数"""
        await embedding_state.init()
        await embedding_state.add_task("mem-005", "测试max")
        # 设置为已重试3次（MAX_RETRY_COUNT=3）
        for _ in range(3):
            await embedding_state.update_state("mem-005", EmbeddingState.FAILED)
            await embedding_state.retry_task("mem-005")

        task = await embedding_state.retry_task("mem-005")
        assert task is None  # 返回 None 表示已达最大重试

    @pytest.mark.asyncio
    async def test_embedding_state_get_pending(self, embedding_state):
        """获取待处理任务"""
        await embedding_state.init()
        await embedding_state.add_task("mem-pending-1", "text1")
        await embedding_state.add_task("mem-pending-2", "text2")
        await embedding_state.update_state("mem-pending-1", EmbeddingState.GENERATING)

        pending = await embedding_state.get_pending()
        assert len(pending) >= 1

    @pytest.mark.asyncio
    async def test_embedding_state_get_state(self, embedding_state):
        """获取单条状态"""
        await embedding_state.init()
        await embedding_state.add_task("mem-state", "测试状态")
        state = await embedding_state.get_state("mem-state")
        assert state == EmbeddingState.PENDING.value

    @pytest.mark.asyncio
    async def test_embedding_state_get_state_nonexistent(self, embedding_state):
        """获取不存在记忆的状态"""
        await embedding_state.init()
        state = await embedding_state.get_state("non_existent_mem")
        assert state is None


class TestEmbeddingTask:
    """测试 EmbeddingTask 模型"""

    def test_embedding_task_to_dict(self):
        """序列化 EmbeddingTask"""
        task = EmbeddingTask(
            mem_id="mem-001",
            text="测试文本",
            state=EmbeddingState.PENDING.value,
        )
        d = task.to_dict()
        assert d["mem_id"] == "mem-001"
        assert d["text"] == "测试文本"
        assert d["state"] == EmbeddingState.PENDING.value

    def test_embedding_task_from_dict(self):
        """反序列化 EmbeddingTask"""
        data = {
            "mem_id": "mem-002",
            "text": "文本",
            "state": "completed",
            "retry_count": 2,
        }
        task = EmbeddingTask.from_dict(data)
        assert task.mem_id == "mem-002"
        assert task.retry_count == 2
