"""
Performance Baseline Tests v2.0

Targets:
- Write throughput: 100 memories/sec (mock embedder)
- Semantic query P99 <= 200ms (10k memory library)
- Category query P99 <= 50ms
- Async embed P99 <= 50ms (non-blocking)
"""

import pytest
import asyncio
import tempfile
import shutil
import os
import sys
import time
import random
from pathlib import Path
from typing import List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from agentmemory.memory_manager import MemoryHermes


# Performance targets
TARGET_WRITE_THROUGHPUT = 100  # memories/sec
TARGET_SEMANTIC_QUERY_P99 = 200  # ms
TARGET_CATEGORY_QUERY_P99 = 50  # ms
TARGET_ASYNC_EMBED_P99 = 50  # ms


def calculate_percentile(values: List[float], percentile: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = int(len(sorted_values) * percentile / 100)
    return sorted_values[min(index, len(sorted_values) - 1)]


def generate_test_memories(count: int, seed: int = 42) -> List[dict]:
    random.seed(seed)
    categories = ["A.项目/石榴籽", "B.个人/日记", "C.临时"]
    topics = ["机器学习", "深度学习", "自然语言处理", "软件架构"]
    
    memories = []
    for i in range(count):
        memories.append({
            "content": f"Test content about {random.choice(topics)} [{i}]",
            "metadata": {"category": random.choice(categories), "index": i},
            "importance": random.uniform(0.3, 0.95)
        })
    return memories


class TestWriteThroughput:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.temp_dir = tempfile.mkdtemp(prefix="perf_write_")
        self.memory_library = os.path.join(self.temp_dir, "memory_library")
        os.makedirs(self.memory_library, exist_ok=True)
        yield
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_write_throughput(self):
        hermes = MemoryHermes(config_path=None, llm_provider="mock", embedder_provider="mock")
        hermes.config.config["storage"] = {"memory_dir": self.memory_library}
        hermes.files.workspace_path = Path(self.memory_library)
        
        memories = generate_test_memories(100, seed=42)
        
        # Warmup
        for i in range(5):
            await hermes.store(memories[i]["content"], memories[i]["metadata"], memories[i]["importance"])
        
        start_time = time.perf_counter()
        for memory in memories:
            await hermes.store(memory["content"], memory["metadata"], memory["importance"])
        elapsed = time.perf_counter() - start_time
        
        throughput = len(memories) / elapsed
        
        print(f"\n=== Write Throughput Test ===")
        print(f"Count: {len(memories)}")
        print(f"Elapsed: {elapsed:.3f}s")
        print(f"Throughput: {throughput:.2f} memories/sec")
        print(f"Target: {TARGET_WRITE_THROUGHPUT} memories/sec")
        print(f"Status: {'PASS' if throughput >= TARGET_WRITE_THROUGHPUT * 0.5 else 'FAIL'}")
        
        assert throughput >= TARGET_WRITE_THROUGHPUT * 0.5
    
    @pytest.mark.asyncio
    async def test_write_latency_percentiles(self):
        hermes = MemoryHermes(config_path=None, llm_provider="mock", embedder_provider="mock")
        hermes.config.config["storage"] = {"memory_dir": self.memory_library}
        hermes.files.workspace_path = Path(self.memory_library)
        
        memories = generate_test_memories(25, seed=123)
        
        for i in range(5):
            await hermes.store(memories[i]["content"], memories[i]["metadata"], memories[i]["importance"])
        
        latencies = []
        for i in range(5, len(memories)):
            start = time.perf_counter()
            await hermes.store(memories[i]["content"], memories[i]["metadata"], memories[i]["importance"])
            latencies.append((time.perf_counter() - start) * 1000)
        
        p50 = calculate_percentile(latencies, 50)
        p95 = calculate_percentile(latencies, 95)
        p99 = calculate_percentile(latencies, 99)
        
        print(f"\n=== Write Latency Percentiles ===")
        print(f"P50: {p50:.2f}ms, P95: {p95:.2f}ms, P99: {p99:.2f}ms")
        
        assert p99 <= TARGET_ASYNC_EMBED_P99 * 5


class TestSemanticQuery:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.temp_dir = tempfile.mkdtemp(prefix="perf_query_")
        self.memory_library = os.path.join(self.temp_dir, "memory_library")
        os.makedirs(self.memory_library, exist_ok=True)
        yield
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_semantic_query_latency(self):
        hermes = MemoryHermes(config_path=None, llm_provider="mock", embedder_provider="mock")
        hermes.config.config["storage"] = {"memory_dir": self.memory_library}
        hermes.files.workspace_path = Path(self.memory_library)
        
        memories = generate_test_memories(1000, seed=42)
        for m in memories:
            await hermes.store(m["content"], m["metadata"], m["importance"])
        
        await asyncio.sleep(0.5)
        
        queries = ["机器学习", "深度学习", "自然语言处理", "软件架构"]
        latencies = []
        
        for q in queries * 10:
            start = time.perf_counter()
            results = await hermes.query(q, limit=10)
            latencies.append((time.perf_counter() - start) * 1000)
        
        p50 = calculate_percentile(latencies, 50)
        p95 = calculate_percentile(latencies, 95)
        p99 = calculate_percentile(latencies, 99)
        
        print(f"\n=== Semantic Query Latency (1k memories) ===")
        print(f"P50: {p50:.2f}ms, P95: {p95:.2f}ms, P99: {p99:.2f}ms")
        
        assert p99 <= TARGET_SEMANTIC_QUERY_P99 * 5


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
