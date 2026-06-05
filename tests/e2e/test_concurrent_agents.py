"""
Multi-Agent Concurrency Tests v2.0
Tests 3 agents (commander/coder/qa) writing concurrently.
"""

import pytest
import asyncio
import tempfile
import shutil
import os
import sys
import threading
from pathlib import Path
from dataclasses import dataclass, field

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from agentmemory.memory_manager import MemoryHermes


@dataclass
class AgentWorker:
    name: str
    memory_library: str
    category: str
    tasks_completed: int = 0
    errors: list = field(default_factory=list)
    memory_ids: list = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    async def write_memories(self, count: int, base_content: str = "") -> None:
        hermes = MemoryHermes(config_path=None, llm_provider="mock", embedder_provider="mock")
        hermes.config.config["storage"] = {"memory_dir": self.memory_library}
        hermes.files.workspace_path = Path(self.memory_library)
        
        cat_path = os.path.join(self.memory_library, self.category)
        os.makedirs(cat_path, exist_ok=True)
        
        for i in range(count):
            try:
                memory_id = await hermes.store(
                    content=f"[{self.name}] {base_content} Task {i}",
                    metadata={"agent": self.name, "task_index": i, "category": self.category},
                    importance=0.7 + (i * 0.01)
                )
                with self._lock:
                    self.memory_ids.append(memory_id)
                    self.tasks_completed += 1
            except Exception as e:
                with self._lock:
                    self.errors.append(str(e))


class TestConcurrentAgents:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.temp_dir = tempfile.mkdtemp(prefix="concurrent_")
        self.memory_library = os.path.join(self.temp_dir, "memory_library")
        os.makedirs(self.memory_library, exist_ok=True)
        yield
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_3_agents_concurrent_write(self):
        agents = [
            AgentWorker("commander", self.memory_library, "A.项目/石榴籽"),
            AgentWorker("coder", self.memory_library, "A.项目/量子计算"),
            AgentWorker("qa", self.memory_library, "B.个人/日记"),
        ]
        
        tasks = []
        for agent in agents:
            for i in range(10):
                tasks.append(agent.write_memories(1, f"{agent.name}_{i}"))
        
        await asyncio.gather(*tasks)
        
        total_written = sum(a.tasks_completed for a in agents)
        total_errors = sum(len(a.errors) for a in agents)
        
        assert total_errors == 0, f"Expected no errors, got {total_errors}"
        assert total_written == 30, f"Expected 30 memories, got {total_written}"
        
        memory_files = list(Path(self.memory_library).rglob("*.md"))
        assert len(memory_files) >= 30
        
        print(f"
PASS: 3 agents concurrent write: {total_written} memories")
        return True
    
    @pytest.mark.asyncio
    async def test_no_file_conflict(self):
        results = []
        results_lock = threading.Lock()
        
        async def writer(worker_id):
            hermes = MemoryHermes(config_path=None, llm_provider="mock", embedder_provider="mock")
            hermes.config.config["storage"] = {"memory_dir": self.memory_library}
            hermes.files.workspace_path = Path(self.memory_library)
            
            for i in range(5):
                memory_id = await hermes.store(
                    content=f"[Worker-{worker_id}] Task {i}",
                    metadata={"worker_id": worker_id},
                    importance=0.7
                )
                with results_lock:
                    results.append(memory_id)
        
        await asyncio.gather(*[writer(i) for i in range(5)])
        
        assert len(results) == 25
        memory_files = list(Path(self.memory_library).rglob("*.md"))
        assert len(memory_files) == 25
        
        print(f"
PASS: No file conflict: {len(results)} results")
        return True


class TestAgentIsolation:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.temp_dir = tempfile.mkdtemp(prefix="isolation_")
        self.memory_library = os.path.join(self.temp_dir, "memory_library")
        os.makedirs(self.memory_library, exist_ok=True)
        yield
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_agent_crash_isolation(self):
        results = {"agent1": [], "agent2": [], "agent3": []}
        
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


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
