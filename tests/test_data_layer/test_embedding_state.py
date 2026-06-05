"""
EmbeddingStateMachine 单元测试

测试 EmbeddingStateMachine 模块的核心功能：
- 状态转换
- 重试策略
- 永久失败升级
- 持久化
"""

import pytest
import json
from pathlib import Path

from agentmemory.data import EmbeddingStateMachine, EmbeddingState
from agentmemory.data.embedding_state import InvalidStateTransitionError


class TestEmbeddingStateMachineInit:
    """EmbeddingStateMachine 初始化测试"""
    
    def test_init_creates_state_file(self, embedding_state_machine: EmbeddingStateMachine):
        """测试初始化创建状态文件"""
        assert embedding_state_machine.state_file.exists()


class TestEmbeddingStateTransitions:
    """状态转换测试"""
    
    @pytest.mark.asyncio
    async def test_set_initial_state(self, embedding_state_machine: EmbeddingStateMachine):
        """测试设置初始状态"""
        sm = embedding_state_machine
        
        entry = await sm.set_state("mem_new", EmbeddingState.PENDING)
        
        assert entry.state == EmbeddingState.PENDING.value
        assert entry.retry_count == 0
    
    @pytest.mark.asyncio
    async def test_pending_to_generating(self, embedding_state_machine: EmbeddingStateMachine):
        """测试 pending -> generating 转换"""
        sm = embedding_state_machine
        
        await sm.set_state("mem_001", EmbeddingState.PENDING)
        entry = await sm.set_state("mem_001", EmbeddingState.GENERATING)
        
        assert entry.state == EmbeddingState.GENERATING.value
    
    @pytest.mark.asyncio
    async def test_generating_to_completed(self, embedding_state_machine: EmbeddingStateMachine):
        """测试 generating -> completed 转换"""
        sm = embedding_state_machine
        
        await sm.set_state("mem_001", EmbeddingState.GENERATING)
        entry = await sm.set_state("mem_001", EmbeddingState.COMPLETED)
        
        assert entry.state == EmbeddingState.COMPLETED.value
    
    @pytest.mark.asyncio
    async def test_generating_to_failed(self, embedding_state_machine: EmbeddingStateMachine):
        """测试 generating -> failed 转换"""
        sm = embedding_state_machine
        
        await sm.set_state("mem_001", EmbeddingState.GENERATING)
        entry = await sm.set_state("mem_001", EmbeddingState.FAILED, error_message="API Error")
        
        assert entry.state == EmbeddingState.FAILED.value
        assert entry.error_message == "API Error"
    
    @pytest.mark.asyncio
    async def test_failed_to_retry(self, embedding_state_machine: EmbeddingStateMachine):
        """测试 failed -> generating (重试) 转换"""
        sm = embedding_state_machine
        
        await sm.set_state("mem_001", EmbeddingState.FAILED)
        entry = await sm.set_state("mem_001", EmbeddingState.GENERATING)
        
        assert entry.state == EmbeddingState.GENERATING.value
    
    @pytest.mark.asyncio
    async def test_failed_to_permanent_failure(self, embedding_state_machine: EmbeddingStateMachine):
        """测试 failed -> permanent_failure 转换"""
        sm = embedding_state_machine
        
        await sm.set_state("mem_001", EmbeddingState.FAILED)
        entry = await sm.set_state("mem_001", EmbeddingState.PERMANENT_FAILURE)
        
        assert entry.state == EmbeddingState.PERMANENT_FAILURE.value


class TestEmbeddingStateMachineRetry:
    """重试策略测试"""
    
    @pytest.mark.asyncio
    async def test_retry_count_increments(self, embedding_state_machine: EmbeddingStateMachine):
        """测试重试计数递增"""
        sm = embedding_state_machine
        
        # 模拟重试
        await sm.set_state("mem_001", EmbeddingState.PENDING)
        await sm.set_state("mem_001", EmbeddingState.GENERATING)
        await sm.set_state("mem_001", EmbeddingState.FAILED)
        
        entry = await sm.set_state("mem_001", EmbeddingState.GENERATING)  # 重试
        assert entry.retry_count >= 1
    
    @pytest.mark.asyncio
    async def test_auto_upgrade_to_permanent_failure(self, embedding_state_machine: EmbeddingStateMachine):
        """测试自动升级为永久失败"""
        sm = embedding_state_machine
        
        # 手动设置失败状态和重试次数
        await sm.set_state("mem_001", EmbeddingState.PENDING)
        for _ in range(3):
            await sm.set_state("mem_001", EmbeddingState.GENERATING)
            await sm.set_state("mem_001", EmbeddingState.FAILED)
        
        entry = await sm.get_state("mem_001")
        assert entry.state == EmbeddingState.PERMANENT_FAILURE.value


class TestEmbeddingStateMachineQuery:
    """状态查询测试"""
    
    @pytest.mark.asyncio
    async def test_get_state(self, embedding_state_machine_with_states: EmbeddingStateMachine):
        """测试获取状态"""
        sm = embedding_state_machine_with_states
        
        entry = await sm.get_state("mem_001")
        assert entry is not None
        assert entry.state == EmbeddingState.PENDING.value
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_state(self, embedding_state_machine: EmbeddingStateMachine):
        """测试获取不存在的状态"""
        sm = embedding_state_machine
        
        entry = await sm.get_state("nonexistent")
        assert entry is None
    
    @pytest.mark.asyncio
    async def test_list_pending(self, embedding_state_machine_with_states: EmbeddingStateMachine):
        """测试列出待处理状态"""
        sm = embedding_state_machine_with_states
        
        pending = await sm.list_pending()
        memory_ids = [e.memory_id for e in pending]
        
        assert "mem_001" in memory_ids
    
    @pytest.mark.asyncio
    async def test_list_failed(self, embedding_state_machine_with_states: EmbeddingStateMachine):
        """测试列出失败状态"""
        sm = embedding_state_machine_with_states
        
        failed = await sm.list_failed()
        memory_ids = [e.memory_id for e in failed]
        
        assert "mem_004" in memory_ids
        assert "mem_005" in memory_ids


class TestEmbeddingStateMachinePersistence:
    """持久化测试"""
    
    @pytest.mark.asyncio
    async def test_state_persistence(self, embedding_state_machine_with_states: EmbeddingStateMachine):
        """测试状态持久化"""
        sm = embedding_state_machine_with_states
        
        # 读取状态文件
        with open(sm.state_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        assert isinstance(data, dict)
        assert "states" in data
        assert len(data["states"]) >= 5
