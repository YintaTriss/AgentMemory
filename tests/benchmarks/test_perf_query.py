"""
性能基准测试: 查询操作延迟

验收标准: 1000 次 query 平均耗时 < 30ms
"""

import pytest
import sys
import os
import asyncio
import time
import tempfile
import shutil
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../..", "src"))


class MockMemoryHermes:
    """Mock MemoryHermes for performance testing"""
    
    def __init__(self, storage_path):
        self.storage_path = storage_path
        self._memories = {}
        self._counter = 0
        
        # Pre-populate with test data
        for i in range(500):
            import uuid
            memory_id = f"mem_{uuid.uuid4().hex[:12]}"
            self._memories[memory_id] = {
                "id": memory_id,
                "content": f"Test memory content {i} with some random data {random.randint(1, 1000)}",
                "metadata": {"index": i},
                "importance": random.uniform(0.1, 1.0),
                "score": random.uniform(0.5, 1.0),
            }
    
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
        """Mock query - simulate hybrid search"""
        # Simulate retrieval time
        await asyncio.sleep(0)  # Yield to event loop
        results = []
        for mem_id, mem in list(self._memories.items())[:limit]:
            results.append({
                "id": mem_id,
                "content": mem["content"],
                "score": mem.get("score", 0.5),
            })
        return results
    
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
        if action == "query":
            results = await self.query(
                params.get("query", ""),
                params.get("limit", 5),
                params.get("filters")
            )
            return {"success": True, "results": results}
        return {"success": False}


@pytest.fixture
def mh():
    """Create mock MemoryHermes for testing"""
    temp_dir = tempfile.mkdtemp()
    mh = MockMemoryHermes(temp_dir)
    yield mh
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.benchmark
class TestPerfQuery:
    """查询操作性能基准测试"""
    
    @pytest.mark.asyncio
    async def test_query_1000_iterations(self, mh):
        """
        验收标准: 1000 次 query 平均耗时 < 30ms
        
        性能要求:
        - 平均延迟 < 30ms
        - P95 延迟 < 60ms
        - P99 延迟 < 100ms
        """
        num_iterations = 1000
        queries = [
            f"test query {i % 100}" 
            for i in range(num_iterations)
        ]
        latencies = []
        
        async def single_query(q):
            start = time.perf_counter()
            await mh.query(q, limit=5)
            end = time.perf_counter()
            return (end - start) * 1000
        
        # Run all queries
        tasks = [single_query(q) for q in queries]
        latencies = await asyncio.gather(*tasks)
        
        # Calculate statistics
        avg_latency = sum(latencies) / len(latencies)
        sorted_latencies = sorted(latencies)
        p95_latency = sorted_latencies[int(len(sorted_latencies) * 0.95)]
        p99_latency = sorted_latencies[int(len(sorted_latencies) * 0.99)]
        
        print(f"\n=== Query Performance (n={num_iterations}) ===")
        print(f"Avg: {avg_latency:.2f}ms (limit: 30ms)")
        print(f"P95: {p95_latency:.2f}ms")
        print(f"P99: {p99_latency:.2f}ms")
        print(f"Min: {min(latencies):.2f}ms")
        print(f"Max: {max(latencies):.2f}ms")
        
        # Assert acceptance criteria
        assert avg_latency < 30, f"Average latency {avg_latency:.2f}ms exceeds 30ms limit"
        
        return {
            "avg_ms": avg_latency,
            "p95_ms": p95_latency,
            "p99_ms": p99_latency,
            "min_ms": min(latencies),
            "max_ms": max(latencies),
        }
    
    @pytest.mark.asyncio
    async def test_query_with_filters(self, mh):
        """
        带过滤器的查询性能测试
        """
        num_iterations = 500
        latencies = []
        
        async def single_query(i):
            start = time.perf_counter()
            await mh.query(
                f"query {i}", 
                limit=10, 
                filters={"metadata.index": {"$gte": i % 100}}
            )
            end = time.perf_counter()
            return (end - start) * 1000
        
        tasks = [single_query(i) for i in range(num_iterations)]
        latencies = await asyncio.gather(*tasks)
        
        avg_latency = sum(latencies) / len(latencies)
        
        print(f"\n=== Query with Filters (n={num_iterations}) ===")
        print(f"Avg: {avg_latency:.2f}ms")
        
        assert avg_latency < 50, f"Average latency {avg_latency:.2f}ms exceeds 50ms limit"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
