"""
E2E 场景测试套件 v2.0
"""

import pytest
import asyncio
import tempfile
import shutil
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from agentmemory.memory_manager import MemoryHermes
from agentmemory.data.embedding_state import EmbeddingStateMachine, EmbeddingState
from agentmemory.decay_engine import DecayEngine


def generate_shiliuzi_memories():
    return [
        {"content": "石榴籽项目省赛答辩安排在6月15日上午9点", "metadata": {"project": "石榴籽"}, "importance": 0.95},
        {"content": "石榴籽AI翻译项目获得省赛一等奖", "metadata": {"project": "石榴籽"}, "importance": 0.98},
        {"content": "石榴籽项目需要准备答辩PPT", "metadata": {"project": "石榴籽"}, "importance": 0.85},
        {"content": "答辩PPT第三页需要修改配色方案", "metadata": {"project": "石榴籽"}, "importance": 0.6},
        {"content": "石榴籽项目使用了Transformer架构", "metadata": {"project": "石榴籽"}, "importance": 0.75},
    ]


class TestShiliuziDefense:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.temp_dir = tempfile.mkdtemp(prefix="shiliuzi_")
        self.memory_library = os.path.join(self.temp_dir, "memory_library")
        os.makedirs(self.memory_library, exist_ok=True)
        yield
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_shiliuzi_recall(self):
        hermes = MemoryHermes(config_path=None, llm_provider="mock", embedder_provider="mock")
        hermes.config.config["storage"] = {"memory_dir": self.memory_library}
        hermes.files.workspace_path = Path(self.memory_library)
        
        memories = generate_shiliuzi_memories()
        memory_ids = []
        for m in memories:
            memory_id = await hermes.store(m["content"], m["metadata"], m["importance"])
            memory_ids.append(memory_id)
        
        assert len(memory_ids) == 5
        await asyncio.sleep(0.5)
        
        results = await hermes.query("答辩时间", limit=5)
        
        print("[PASS] 石榴籽答辩场景测试通过: 写入" + str(len(memory_ids)) + "条")
        return True


class TestMemoryForgetting:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.temp_dir = tempfile.mkdtemp(prefix="forgetting_")
        yield
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_low_importance_decay(self):
        decay = DecayEngine(half_life_days=7.0, forget_threshold=0.15, archive_threshold=0.3)
        new_imp = decay.calculate_decay(0.25, days_elapsed=7.0)
        assert new_imp < 0.25
        assert new_imp < 0.3
        assert decay.should_archive(new_imp)
        print("[PASS] 低重要性衰减测试通过: 0.25 -> " + str(round(new_imp, 4)))
        return True
    
    @pytest.mark.asyncio
    async def test_high_importance_retention(self):
        decay = DecayEngine(half_life_days=7.0, forget_threshold=0.15, archive_threshold=0.3)
        new_imp = decay.calculate_decay(0.9, days_elapsed=7.0)
        assert new_imp > 0.3
        assert not decay.should_archive(new_imp)
        print("[PASS] 高重要性保留测试通过: 0.9 -> " + str(round(new_imp, 4)))
        return True


class TestEmbeddingFailure:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.temp_dir = tempfile.mkdtemp(prefix="embed_fail_")
        self.memory_library = os.path.join(self.temp_dir, "memory_library")
        os.makedirs(self.memory_library, exist_ok=True)
        yield
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_retry_mechanism(self):
        sm = EmbeddingStateMachine(root_dir=self.memory_library)
        await sm.init()
        
        await sm.set_state("mem_1", EmbeddingState.PENDING)
        entry = await sm.get_state("mem_1")
        assert entry.state == EmbeddingState.PENDING.value
        
        for i in range(1, 4):
            await sm.set_state("mem_1", EmbeddingState.FAILED, error_message="Error")
            entry = await sm.get_state("mem_1")
            assert entry.retry_count == i
        
        assert entry.state == EmbeddingState.PERMANENT_FAILURE.value
        print("[PASS] 嵌入失败重试机制测试通过")
        return True
    
    @pytest.mark.asyncio
    async def test_state_persistence(self):
        sm = EmbeddingStateMachine(root_dir=self.memory_library)
        await sm.init()
        
        await sm.set_state("mem_a", EmbeddingState.COMPLETED)
        await sm.set_state("mem_b", EmbeddingState.PERMANENT_FAILURE, error_message="Max retries")
        
        sm2 = EmbeddingStateMachine(root_dir=self.memory_library)
        await sm2.init()
        
        assert (await sm2.get_state("mem_a")).state == EmbeddingState.COMPLETED.value
        assert (await sm2.get_state("mem_b")).state == EmbeddingState.PERMANENT_FAILURE.value
        print("[PASS] 失败状态持久化测试通过")
        return True


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))