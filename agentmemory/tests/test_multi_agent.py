"""
test_multi_agent.py — MultiAgent 测试
验证文件锁 / NDJSON 日志 / AgentRegistry 心跳
"""
import pytest
import asyncio
import tempfile
import time
from pathlib import Path
from agentmemory.multi_agent import (
    MultiAgentLock,
    MultiAgentLockTimeout,
    SharedLog,
    SharedLogEntry,
    AgentRegistry,
    MultiAgent,
    generate_agent_id,
)


@pytest.fixture
def multi_agent_lock(tmp_path):
    """创建测试用 MultiAgentLock"""
    lock = MultiAgentLock(lock_path=tmp_path / "test.lock", timeout=5.0)
    return lock


@pytest.fixture
def shared_log(tmp_path, multi_agent_lock):
    """创建测试用 SharedLog"""
    log = SharedLog(data_root=tmp_path, lock=multi_agent_lock)
    return log


@pytest.fixture
def agent_registry(tmp_path):
    """创建测试用 AgentRegistry"""
    return AgentRegistry(data_root=tmp_path)


@pytest.fixture
def multi_agent_instance(tmp_path):
    """创建 MultiAgent 实例"""
    ma = MultiAgent(data_root=tmp_path)
    return ma


class TestMultiAgentLock:
    """测试 MultiAgentLock 文件锁"""

    def test_multi_agent_lock_acquire_release(self, multi_agent_lock):
        """文件锁获取和释放"""
        result = multi_agent_lock.acquire()
        assert result is True
        assert multi_agent_lock.is_locked() is True
        multi_agent_lock.release()
        assert multi_agent_lock.is_locked() is False

    def test_multi_agent_lock_context_manager(self, multi_agent_lock):
        """使用上下文管理器"""
        with multi_agent_lock:
            assert multi_agent_lock.is_locked() is True
        assert multi_agent_lock.is_locked() is False

    def test_multi_agent_lock_timeout(self, tmp_path):
        """获取锁超时"""
        lock1 = MultiAgentLock(lock_path=tmp_path / "timeout.lock", timeout=1.0)
        lock2 = MultiAgentLock(lock_path=tmp_path / "timeout.lock", timeout=1.0)

        lock1.acquire()
        try:
            with pytest.raises(MultiAgentLockTimeout):
                lock2.acquire(timeout=0.5)
        finally:
            lock1.release()

    def test_multi_agent_lock_reentrant(self, multi_agent_lock):
        """同一进程重入"""
        multi_agent_lock.acquire(memory_id="mem-001")
        multi_agent_lock.acquire(memory_id="mem-001")  # 重入不阻塞
        multi_agent_lock.release(memory_id="mem-001")
        multi_agent_lock.release(memory_id="mem-001")  # 第二次 release 才真正释放


class TestSharedLog:
    """测试 SharedLog NDJSON 日志"""

    def test_shared_log_append_event(self, shared_log):
        """追加日志"""
        offset = shared_log.append_event(
            agent_id="agent-001",
            event_type="store",
            content="测试内容",
            memory_id="mem-001",
        )
        assert isinstance(offset, int)
        assert offset > 0

    def test_shared_log_tail(self, shared_log):
        """读取最近 N 条"""
        for i in range(5):
            shared_log.append_event(
                agent_id=f"agent-{i}",
                event_type="store",
                content=f"内容 {i}",
            )
        tail = shared_log.tail(n=3)
        assert len(tail) == 3
        assert all(isinstance(e, SharedLogEntry) for e in tail)

    def test_shared_log_read_since(self, shared_log):
        """从 offset 增量读取"""
        offset1 = shared_log.append_event(
            agent_id="agent-read",
            event_type="store",
            content="第一条",
        )
        shared_log.append_event(
            agent_id="agent-read",
            event_type="store",
            content="第二条",
        )

        records, new_offset = shared_log.read_since(offset1)
        assert len(records) >= 1
        assert new_offset > offset1

    def test_shared_log_current_offset(self, shared_log):
        """获取当前 offset"""
        initial_offset = shared_log.current_offset()
        shared_log.append_event(agent_id="agent-off", event_type="test")
        new_offset = shared_log.current_offset()
        assert new_offset > initial_offset


class TestAgentRegistryHeartbeat:
    """测试 AgentRegistry 心跳"""

    def test_agent_registry_register(self, agent_registry):
        """注册 Agent"""
        record = agent_registry.register(
            agent_id="test-agent-001",
            capabilities=["read", "write"],
        )
        assert record["agent_id"] == "test-agent-001"
        assert "read" in record["capabilities"]
        assert record["status"] == "active"

    def test_agent_registry_heartbeat(self, agent_registry):
        """心跳注册和超时"""
        agent_registry.register(agent_id="heartbeat-agent")
        success = agent_registry.heartbeat("heartbeat-agent")
        assert success is True

        # 不存在的 agent 心跳返回 False
        success = agent_registry.heartbeat("non-existent-agent")
        assert success is False

    def test_agent_registry_list_active(self, agent_registry):
        """列出活跃 Agent"""
        agent_registry.register(agent_id="active-1")
        agent_registry.register(agent_id="active-2")
        active = agent_registry.list_active()
        agent_ids = [r["agent_id"] for r in active]
        assert "active-1" in agent_ids
        assert "active-2" in agent_ids

    def test_agent_registry_unregister(self, agent_registry):
        """注销 Agent"""
        agent_registry.register(agent_id="to-unregister")
        success = agent_registry.unregister("to-unregister")
        assert success is True
        # 再次注销返回 False
        success = agent_registry.unregister("to-unregister")
        assert success is False

    def test_agent_registry_get(self, agent_registry):
        """获取指定 Agent"""
        agent_registry.register(agent_id="get-test")
        record = agent_registry.get("get-test")
        assert record is not None
        assert record["agent_id"] == "get-test"

    def test_agent_registry_stale_cleanup(self, agent_registry):
        """心跳超时清理"""
        agent_registry.register(agent_id="stale-agent")
        # 手动修改 last_heartbeat 为过去时间（触发超时）
        agent_registry._registry["stale-agent"]["last_heartbeat"] = (
            "2020-01-01T00:00:00+00:00"
        )
        active = agent_registry.list_active()
        agent_ids = [r["agent_id"] for r in active]
        assert "stale-agent" not in agent_ids


class TestSharedLogEntry:
    """测试 SharedLogEntry 模型"""

    def test_shared_log_entry_to_dict(self):
        """序列化 SharedLogEntry"""
        entry = SharedLogEntry(
            agent_id="agent-001",
            event_type="store",
            content="测试",
            memory_id="mem-001",
        )
        d = entry.to_dict()
        assert d["agent_id"] == "agent-001"
        assert d["event_type"] == "store"
        assert d["memory_id"] == "mem-001"

    def test_shared_log_entry_from_dict(self):
        """反序列化 SharedLogEntry"""
        data = {
            "agent_id": "agent-002",
            "event_type": "query",
            "content": "内容",
            "memory_id": "mem-002",
            "timestamp": "2024-01-01T00:00:00+00:00",
        }
        entry = SharedLogEntry.from_dict(data)
        assert entry.agent_id == "agent-002"
        assert entry.event_type == "query"

    def test_shared_log_entry_to_json_line(self):
        """序列化为 NDJSON 单行"""
        entry = SharedLogEntry(agent_id="agent-003", event_type="test")
        line = entry.to_json_line()
        assert line.endswith("\n")
        import json
        parsed = json.loads(line.strip())
        assert parsed["agent_id"] == "agent-003"


class TestMultiAgentIntegration:
    """测试 MultiAgent 整合类"""

    def test_multi_agent_init(self, multi_agent_instance):
        """MultiAgent 初始化"""
        assert multi_agent_instance.agent_id is not None
        assert isinstance(multi_agent_instance.agent_id, str)

    def test_generate_agent_id(self):
        """生成唯一 Agent ID"""
        ids = [generate_agent_id() for _ in range(10)]
        assert len(set(ids)) == 10  # 全部唯一

    def test_multi_agent_register_unregister(self, multi_agent_instance):
        """注册和注销"""
        record = multi_agent_instance.register_agent(capabilities=["read"])
        assert record["agent_id"] == multi_agent_instance.agent_id

        success = multi_agent_instance.unregister_agent()
        assert success is True

    def test_multi_agent_append_log(self, multi_agent_instance):
        """追加日志"""
        offset = multi_agent_instance.append_log(
            event_type="store",
            content="测试",
            memory_id="mem-001",
        )
        assert isinstance(offset, int)

    def test_multi_agent_read_since(self, multi_agent_instance):
        """从 offset 读取"""
        multi_agent_instance.append_log(event_type="store", content="内容")
        records, offset = multi_agent_instance.read_since(0)
        assert isinstance(records, list)
        assert isinstance(offset, int)
