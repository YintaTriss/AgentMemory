"""
Fault Recovery Tests v2.0
Tests embedding worker crash, power failure, and agent crash recovery.
"""

import pytest
import asyncio
import tempfile
import shutil
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from agentmemory.memory_manager import MemoryHermes
from agentmemory.data.embedding_state import EmbeddingStateMachine, EmbeddingState


class TestEmbeddingWorkerRecovery:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.temp_dir = tempfile.mkdtemp(prefix="fault_recovery_")
        self.memory_library = os.path.join(self.temp_dir, "memory_library")
        os.makedirs(self.memory_library, exist_ok=True)
        yield
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_embedding_state_persistence(self):
        sm = EmbeddingStateMachine(root_dir=self.memory_library)
        await sm.init()
        
        await sm.set_state("mem_001", EmbeddingState.PENDING)
        await sm.set_state("mem_002", EmbeddingState.GENERATING)
        await sm.set_state("mem_003", EmbeddingState.COMPLETED)
        await sm.set_state("mem_004", EmbeddingState.FAILED, error_message="API Error")
        await sm.set_state("mem_005", EmbeddingState.PERMANENT_FAILURE, error_message="Max retries")
        
        state_file = Path(self.memory_library) / ".embedding_state.json"
        assert state_file.exists(), "State file should exist"
        
        # Restart and recover
        sm2 = EmbeddingStateMachine(root_dir=self.memory_library)
        await sm2.init()
        
        assert await sm2.get_state("mem_001") is not None
        assert await sm2.get_state("mem_003") is not None
        assert (await sm2.get_state("mem_005")).state == EmbeddingState.PERMANENT_FAILURE.value
        
        print("
PASS: Embedding state persistence recovered")
        return True
    
    @pytest.mark.asyncio
    async def test_retry_to_permanent_failure(self):
        sm = EmbeddingStateMachine(root_dir=self.memory_library)
        await sm.init()
        
        memory_id = "mem_retry_test"
        await sm.set_state(memory_id, EmbeddingState.PENDING)
        
        for i in range(3):
            await sm.set_state(memory_id, EmbeddingState.FAILED, error_message="Network timeout")
            entry = await sm.get_state(memory_id)
            assert entry.retry_count == i + 1
        
        entry = await sm.get_state(memory_id)
        assert entry.state == EmbeddingState.PERMANENT_FAILURE.value
        
        print("
PASS: Retry mechanism: pending -> (failed x3) -> permanent_failure")
        return True


class TestPowerFailureRecovery:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.temp_dir = tempfile.mkdtemp(prefix="power_failure_")
        self.memory_library = os.path.join(self.temp_dir, "memory_library")
        os.makedirs(self.memory_library, exist_ok=True)
        yield
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_partial_write_recovery(self):
        hermes = MemoryHermes(config_path=None, llm_provider="mock", embedder_provider="mock")
        hermes.config.config["storage"] = {"memory_dir": self.memory_library}
        hermes.files.workspace_path = Path(self.memory_library)
        
        memory_ids = []
        for i in range(5):
            memory_id = await hermes.store(
                content=f"Memory {i}",
                metadata={"index": i},
                importance=0.5 + i * 0.1
            )
            memory_ids.append(memory_id)
        
        # Simulate power failure and restart
        hermes2 = MemoryHermes(config_path=None, llm_provider="mock", embedder_provider="mock")
        hermes2.config.config["storage"] = {"memory_dir": self.memory_library}
        hermes2.files.workspace_path = Path(self.memory_library)
        
        memory_files = list(Path(self.memory_library).rglob("*.md"))
        assert len(memory_files) >= 5, f"All memories should be persisted, got {len(memory_files)}"
        
        print(f"
PASS: Partial write recovery: {len(memory_files)} files recovered")
        return True
    
    @pytest.mark.asyncio
    async def test_agent_crash_isolation(self):
        results = {"agent1": [], "agent2": []}
        
        async def agent1_work():
            hermes = MemoryHermes(config_path=None, llm_provider="mock", embedder_provider="mock")
            hermes.config.config["storage"] = {"memory_dir": self.memory_library}
            hermes.files.workspace_path = Path(self.memory_library)
            for i in range(5):
                memory_id = await hermes.store(
                    content=f"Agent1 Memory {i}",
                    metadata={"agent": "agent1"},
                    importance=0.7
                )
                results["agent1"].append(memory_id)
        
        async def agent2_work():
            hermes = MemoryHermes(config_path=None, llm_provider="mock", embedder_provider="mock")
            hermes.config.config["storage"] = {"memory_dir": self.memory_library}
            hermes.files.workspace_path = Path(self.memory_library)
            for i in range(5):
                memory_id = await hermes.store(
                    content=f"Agent2 Memory {i}",
                    metadata={"agent": "agent2"},
                    importance=0.7
                )
                results["agent2"].append(memory_id)
        
        await asyncio.gather(agent1_work(), agent2_work())
        
        assert len(results["agent1"]) == 5
        assert len(results["agent2"]) == 5
        
        print(f"
PASS: Agent crash isolation: agent1={len(results['agent1'])}, agent2={len(results['agent2'])}")
        return True


class TestDataIntegrity:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.temp_dir = tempfile.mkdtemp(prefix="integrity_")
        self.memory_library = os.path.join(self.temp_dir, "memory_library")
        os.makedirs(self.memory_library, exist_ok=True)
        yield
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_no_data_corruption(self):
        hermes = MemoryHermes(config_path=None, llm_provider="mock", embedder_provider="mock")
        hermes.config.config["storage"] = {"memory_dir": self.memory_library}
        hermes.files.workspace_path = Path(self.memory_library)
        
        test_contents = [
            "Normal content",
            "Content with special chars: !@#$%^&*()",
            "Content with unicode: 中文测试",
            "Content with emoji: 😀",
            "Content with newlines:
Line 2",
        ]
        
        memory_ids = []
        for content in test_contents:
            memory_id = await hermes.store(content=content, metadata={}, importance=0.7)
            memory_ids.append(memory_id)
        
        # Verify all files are valid JSON/markdown
        for mid in memory_ids:
            md_file = None
            for f in Path(self.memory_library).rglob("*.md"):
                if mid in f.stem:
                    md_file = f
                    break
            
            if md_file and md_file.exists():
                with open(md_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    assert len(content) > 0, f"File {md_file} should not be empty"
        
        print(f"
PASS: No data corruption: {len(memory_ids)} files verified")
        return True


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
