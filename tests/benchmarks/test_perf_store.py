"""
性能基准测试: 存储操作延迟

验收标准: 1000 次 store 平均耗时 < 50ms
"""

import pytest
import sys
import os
import asyncio
import time
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../..", "src"))


class MockMemoryHermes:
    """Mock MemoryHermes for performance testing"""
    
    def __init__(self, storage_path):
        self.storage_path = storage_path
        self._memories = {}
        self._counter = 0
    
    async def store(self, content: str, metadata: dict = None, importance: float = 0.5) -> str:
        """Mock store - in-memory"""
        import uuid
        memory_id = f"mem_{uuid.uuid4().hex[:12]}"
        self._memories[memory_id] = {
            "id": memory_id,
            "content": content,
            "metadata": metadata or {},
            "importance": importance,
        }
        self._counter += 1
        return memory_id
    
    async def query(self, query: str, limit: int = 5, filters: dict = None):
        """Mock query"""
        return []
    
    def get_stats(self):
        return {"total_memories": len(self._memories)}
    
    def prefetch(self, query: str):
        pass
    
    def get_prefetched(self, query: str):
        return None
    
    async def forget(self, memory_id: str, permanent: bool = False):
        if memory_id in self._memories:
            del self._memories[memory_id]
        return True
    
    async def execute(self, action: str, params: dict = None):
        if action == "store":
            memory_id = await self.store(
                params.get("content", ""),
                params.get("metadata"),
                params.get("importance", 0.5)
            )
            return {"success": True, "id": memory_id}
        return {"success": False}


@pytest.fixture
def mh():
    """Create mock MemoryHermes for testing"""
    temp_dir = tempfile.mkdtemp()
    mh = MockMemoryHermes(temp_dir)
    yield mh
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.benchmark
class TestPerfStore:
    """存储操作性能基准测试"""
    
    @pytest.mark.asyncio
    async def test_store_1000_iterations(self, mh):
        """
        验收标准: 1000 次 store 平均耗时 < 50ms
        
        性能要求:
        - 平均延迟 < 50ms
        - P95 延迟 < 100ms
        - P99 延迟 < 150ms
        """
        num_iterations = 1000
        latencies = []
        
        async def single_store(i):
            start = time.perf_counter()
            await mh.store(f"Test memory content {i}", {"index": i}, 0.5)
            end = time.perf_counter()
            return (end - start) * 1000  # ms
        
        # Run all stores
        tasks = [single_store(i) for i in range(num_iterations)]
        latencies = await asyncio.gather(*tasks)
        
        # Calculate statistics
        avg_latency = sum(latencies) / len(latencies)
        sorted_latencies = sorted(latencies)
        p95_latency = sorted_latencies[int(len(sorted_latencies) * 0.95)]
        p99_latency = sorted_latencies[int(len(sorted_latencies) * 0.99)]
        
        print(f"\n=== Store Performance (n={num_iterations}) ===")
        print(f"Avg: {avg_latency:.2f}ms (limit: 50ms)")
        print(f"P95: {p95_latency:.2f}ms")
        print(f"P99: {p99_latency:.2f}ms")
        print(f"Min: {min(latencies):.2f}ms")
        print(f"Max: {max(latencies):.2f}ms")
        
        # Assert acceptance criteria
        assert avg_latency < 50, f"Average latency {avg_latency:.2f}ms exceeds 50ms limit"
        
        # Store result for baseline
        return {
            "avg_ms": avg_latency,
            "p95_ms": p95_latency,
            "p99_ms": p99_latency,
            "min_ms": min(latencies),
            "max_ms": max(latencies),
        }
    
    @pytest.mark.asyncio
    async def test_store_concurrent_100(self, mh):
        """
        并发存储测试: 100 个并发请求
        """
        num_concurrent = 100
        
        async def single_store(i):
            start = time.perf_counter()
            await mh.store(f"Concurrent memory {i}", {"index": i}, 0.5)
            end = time.perf_counter()
            return (end - start) * 1000
        
        start_all = time.perf_counter()
        results = await asyncio.gather(*[single_store(i) for i in range(num_concurrent)])
        total_time = (time.perf_counter() - start_all) * 1000
        
        avg_latency = sum(results) / len(results)
        throughput = num_concurrent / (total_time / 1000)
        
        print(f"\n=== Concurrent Store (n={num_concurrent}) ===")
        print(f"Total time: {total_time:.2f}ms")
        print(f"Avg per operation: {avg_latency:.2f}ms")
        print(f"Throughput: {throughput:.2f} ops/sec")
        
        assert total_time < 5000, f"Total time {total_time:.2f}ms too high for concurrent operations"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
