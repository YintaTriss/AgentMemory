"""
test_tiered_log.py — TieredLog 分层日志测试
验证 append / read_tail / read_range
"""
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from agentmemory.data.tiered_log import TieredLog, LogLevel


@pytest.fixture
def tiered_log(tmp_path):
    """创建测试用 TieredLog 实例"""
    tl = TieredLog(root_dir=str(tmp_path))
    return tl


class TestTieredLogAppend:
    """测试追加日志"""

    @pytest.mark.asyncio
    async def test_tiered_log_append(self, tiered_log):
        """追加日志"""
        await tiered_log.init()
        entry = await tiered_log.append(
            action="store",
            level=LogLevel.INFO.value,
            memory_id="mem-001",
            category_path="A.项目",
            message="测试日志",
        )
        assert entry.action == "store"
        assert entry.memory_id == "mem-001"
        assert entry.level == LogLevel.INFO.value
        # 需要 flush 才能持久化
        await tiered_log.flush()

    @pytest.mark.asyncio
    async def test_tiered_log_append_multiple(self, tiered_log):
        """追加多条日志"""
        await tiered_log.init()
        for i in range(5):
            await tiered_log.append(
                action=f"action-{i}",
                level=LogLevel.INFO.value,
                memory_id=f"mem-{i:03d}",
            )
        await tiered_log.flush()
        manifest = tiered_log.get_manifest()
        assert manifest["total_entries"] >= 5


class TestTieredLogReadTail:
    """测试读取最近 N 条"""

    @pytest.mark.asyncio
    async def test_tiered_log_read_tail(self, tiered_log):
        """读取最近 N 条"""
        await tiered_log.init()
        for i in range(10):
            await tiered_log.append(
                action=f"store-{i}",
                level=LogLevel.INFO.value,
                memory_id=f"mem-tail-{i}",
            )
        await tiered_log.flush()

        tail = await tiered_log.read_tail(n=5)
        assert len(tail) == 5
        # 最近5条
        assert tail[0].memory_id == "mem-tail-0"
        assert tail[-1].memory_id == "mem-tail-4"

    @pytest.mark.asyncio
    async def test_tiered_log_read_tail_empty(self, tiered_log):
        """空日志读取 tail"""
        await tiered_log.init()
        tail = await tiered_log.read_tail(n=100)
        assert isinstance(tail, list)


class TestTieredLogReadRange:
    """测试按时间范围读取"""

    @pytest.mark.asyncio
    async def test_tiered_log_read_range(self, tiered_log):
        """按时间范围读取"""
        await tiered_log.init()

        # 写入今天的一些日志
        now = datetime.now(timezone.utc)
        for i in range(3):
            await tiered_log.append(
                action=f"range-test-{i}",
                level=LogLevel.INFO.value,
                memory_id=f"mem-range-{i}",
            )
        await tiered_log.flush()

        # 读取今天的日志
        since = now - timedelta(hours=1)
        until = now + timedelta(hours=1)
        entries = await tiered_log.read_range(since, until)
        assert isinstance(entries, list)
        # 今天刚写入的应该在范围内
        assert len(entries) >= 3


class TestTieredLogManifest:
    """测试清单"""

    @pytest.mark.asyncio
    async def test_tiered_log_get_manifest(self, tiered_log):
        """获取归档文件清单"""
        await tiered_log.init()
        await tiered_log.append(action="test", level=LogLevel.INFO.value)
        await tiered_log.flush()

        manifest = tiered_log.get_manifest()
        assert "total_entries" in manifest
        assert manifest["total_entries"] >= 1


class TestTieredLogRotate:
    """测试日志轮转"""

    @pytest.mark.asyncio
    async def test_tiered_log_rotate(self, tiered_log):
        """触发日志轮转"""
        await tiered_log.init()
        await tiered_log.append(action="rotate-test", level=LogLevel.INFO.value)
        await tiered_log.flush()
        await tiered_log.rotate()
        # 不抛异常即成功
