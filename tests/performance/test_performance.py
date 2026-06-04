"""
性能基准测试
v2.0 功能，待 T8 性能优化完成后解冻
"""

import pytest
import time
import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../..", "src"))

# v2.0 待实现功能 - 标记整个文件
pytestmark = pytest.mark.skip(reason="v2.0 性能基准待 T8 实现，解冻条件：完成 Provider 抽象重构后进行基准测试")


class TestBenchmark:
    """基准测试"""
    
    @pytest.mark.asyncio
    async def test_store_latency(self, temp_dir):
        """测试存储延迟"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        latencies = []
        
        for i in range(100):
            start = time.time()
            await mh.execute("store", {
                "content": f"性能测试 {i}",
                "importance": 0.5
            })
            elapsed = time.time() - start
            latencies.append(elapsed * 1000)  # 转换为毫秒
        
        avg_latency = sum(latencies) / len(latencies)
        p50_latency = sorted(latencies)[len(latencies) // 2]
        p99_latency = sorted(latencies)[int(len(latencies) * 0.99)]
        
        print(f"\n存储延迟:")
        print(f"  平均: {avg_latency:.2f}ms")
        print(f"  P50:  {p50_latency:.2f}ms")
        print(f"  P99:  {p99_latency:.2f}ms")
        
        # 平均延迟应该小于 100ms
        assert avg_latency < 100, f"平均延迟过高: {avg_latency:.2f}ms"
    
    @pytest.mark.asyncio
    async def test_query_latency(self, temp_dir):
        """测试查询延迟"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        # 先存储数据
        for i in range(100):
            await mh.execute("store", {
                "content": f"测试内容 {i}",
                "importance": 0.5
            })
        
        latencies = []
        
        for i in range(100):
            start = time.time()
            await mh.execute("query", {
                "query": "测试",
                "limit": 10
            })
            elapsed = time.time() - start
            latencies.append(elapsed * 1000)
        
        avg_latency = sum(latencies) / len(latencies)
        p99_latency = sorted(latencies)[int(len(latencies) * 0.99)]
        
        print(f"\n查询延迟:")
        print(f"  平均: {avg_latency:.2f}ms")
        print(f"  P99:  {p99_latency:.2f}ms")
        
        # 平均延迟应该小于 200ms
        assert avg_latency < 200, f"平均延迟过高: {avg_latency:.2f}ms"
    
    @pytest.mark.asyncio
    async def test_throughput(self, temp_dir):
        """测试吞吐量"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        start = time.time()
        count = 0
        
        # 30秒内尽可能多存储
        while time.time() - start < 10:  # 使用 10 秒作为测试
            await mh.execute("store", {
                "content": f"吞吐量测试 {count}",
                "importance": 0.5
            })
            count += 1
        
        elapsed = time.time() - start
        tps = count / elapsed
        
        print(f"\n吞吐量:")
        print(f"  操作数: {count}")
        print(f"  耗时:   {elapsed:.2f}s")
        print(f"  TPS:    {tps:.2f}")
        
        # TPS 应该大于 5
        assert tps > 5, f"吞吐量过低: {tps:.2f} TPS"
    
    @pytest.mark.asyncio
    async def test_memory_usage(self, temp_dir):
        """测试内存使用"""
        import tracemalloc
        
        from memory_manager import MemoryHermes
        
        tracemalloc.start()
        
        mh = MemoryHermes()
        
        # 存储 1000 条记忆
        for i in range(1000):
            await mh.execute("store", {
                "content": f"内存测试内容 {i}",
                "importance": 0.5
            })
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        print(f"\n内存使用:")
        print(f"  当前: {current / 1024 / 1024:.2f}MB")
        print(f"  峰值: {peak / 1024 / 1024:.2f}MB")
        
        # 峰值内存应该小于 500MB
        assert peak < 500 * 1024 * 1024, f"内存使用过高: {peak / 1024 / 1024:.2f}MB"


class TestScalability:
    """可扩展性测试"""
    
    @pytest.mark.asyncio
    async def test_small_dataset(self, temp_dir):
        """测试小数据集"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        # 存储 10 条
        for i in range(10):
            await mh.execute("store", {
                "content": f"小数据集 {i}",
                "importance": 0.5
            })
        
        # 查询
        result = await mh.execute("query", {"query": "小数据集", "limit": 10})
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_medium_dataset(self, temp_dir):
        """测试中等数据集"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        # 存储 100 条
        for i in range(100):
            await mh.execute("store", {
                "content": f"中等数据集测试内容 {i}",
                "importance": 0.5
            })
        
        # 查询
        result = await mh.execute("query", {"query": "中等", "limit": 20})
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_large_dataset(self, temp_dir):
        """测试大数据集"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        # 存储 1000 条
        for i in range(1000):
            await mh.execute("store", {
                "content": f"大数据集测试内容 {i}",
                "importance": 0.5
            })
        
        # 查询
        result = await mh.execute("query", {"query": "大数据集", "limit": 50})
        
        assert result is not None
        
        # 统计
        stats = await mh.execute("get_stats")
        assert stats is not None
    
    @pytest.mark.asyncio
    async def test_concurrent_writes(self, temp_dir):
        """测试并发写入"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        async def write_batch(start_idx, count):
            for i in range(count):
                await mh.execute("store", {
                    "content": f"并发写入 {start_idx + i}",
                    "importance": 0.5
                })
        
        # 5 个并发任务，每个写 20 条
        tasks = [write_batch(i * 20, 20) for i in range(5)]
        
        start = time.time()
        await asyncio.gather(*tasks)
        elapsed = time.time() - start
        
        print(f"\n并发写入:")
        print(f"  总数:  100")
        print(f"  耗时:  {elapsed:.2f}s")
        
        # 应该能在 30 秒内完成
        assert elapsed < 30, f"并发写入太慢: {elapsed:.2f}s"


class TestDecayPerformance:
    """遗忘引擎性能测试"""
    
    @pytest.mark.asyncio
    async def test_decay_check_performance(self, temp_dir):
        """测试遗忘检查性能"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        # 存储多条记忆
        for i in range(100):
            await mh.execute("store", {
                "content": f"遗忘测试 {i}",
                "importance": 0.3 + (i % 7) * 0.1
            })
        
        # 测试遗忘检查性能
        start = time.time()
        await mh.run_decay_check()
        elapsed = time.time() - start
        
        print(f"\n遗忘检查性能:")
        print(f"  记忆数: 100")
        print(f"  耗时:   {elapsed:.2f}s")
        
        # 应该在 5 秒内完成
        assert elapsed < 5, f"遗忘检查太慢: {elapsed:.2f}s"
    
    @pytest.mark.asyncio
    async def test_decay_with_many_entries(self, temp_dir):
        """测试大量记忆的遗忘"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        # 存储 500 条记忆
        for i in range(500):
            await mh.execute("store", {
                "content": f"大量遗忘测试 {i}",
                "importance": 0.1 + (i % 10) * 0.1
            })
        
        # 遗忘检查
        start = time.time()
        result = await mh.run_decay_check()
        elapsed = time.time() - start
        
        print(f"\n大量遗忘检查:")
        print(f"  记忆数: 500")
        print(f"  耗时:   {elapsed:.2f}s")
        print(f"  遗忘:   {result.get('forget', 0)}")
        print(f"  归档:   {result.get('archive', 0)}")
        
        # 应该在 10 秒内完成
        assert elapsed < 10, f"大量遗忘检查太慢: {elapsed:.2f}s"


class TestGraphPerformance:
    """图谱性能测试"""
    
    def test_graph_operations(self, temp_dir):
        """测试图谱操作性能"""
        from L2_graph_store import GraphStore, Entity, EntityType, RelationType, Relation
        
        graph_path = os.path.join(temp_dir, "perf_graph.json")
        store = GraphStore(graph_path)
        
        # 添加 100 个实体
        start = time.time()
        for i in range(100):
            store.add_entity(Entity(name=f"实体{i}", entity_type=EntityType.OTHER))
        entity_time = time.time() - start
        
        # 添加关系
        entity_ids = list(store._entities.keys())[:50]
        start = time.time()
        for i in range(len(entity_ids) - 1):
            store.add_relation(Relation(
                entity_ids[i],
                entity_ids[i + 1],
                RelationType.RELATED_TO
            ))
        relation_time = time.time() - start
        
        # 查询
        start = time.time()
        for _ in range(100):
            store.get_neighbors(entity_ids[0])
        query_time = time.time() - start
        
        print(f"\n图谱性能:")
        print(f"  添加实体: {entity_time:.3f}s (100个)")
        print(f"  添加关系: {relation_time:.3f}s (49个)")
        print(f"  邻居查询: {query_time:.3f}s (100次)")


class TestVectorPerformance:
    """向量操作性能测试"""
    
    def test_vector_operations(self, temp_dir):
        """测试向量操作性能"""
        from L3_vector_store import VectorStore
        
        store_path = os.path.join(temp_dir, "perf_vector.json")
        store = VectorStore(path=store_path, dimensions=128)
        
        # 添加 1000 个向量
        start = time.time()
        for i in range(1000):
            store.add_vector(
                content=f"向量内容 {i}",
                embedding=[float(i % 10) / 10] * 128
            )
        add_time = time.time() - start
        
        # 搜索
        start = time.time()
        for _ in range(100):
            store.search_similar(query_vector=[0.5] * 128, top_k=10)
        search_time = time.time() - start
        
        print(f"\n向量性能:")
        print(f"  添加向量: {add_time:.3f}s (1000个)")
        print(f"  搜索:     {search_time:.3f}s (100次)")
        
        # 性能要求
        assert add_time < 30, f"向量添加太慢: {add_time:.2f}s"
        assert search_time < 10, f"向量搜索太慢: {search_time:.2f}s"


class TestFilePersistencePerformance:
    """文件持久化性能测试"""
    
    def test_file_write_performance(self, temp_dir):
        """测试文件写入性能"""
        from L4_file_persist import FilePersistStore
        
        store = FilePersistStore(base_path=temp_dir)
        
        start = time.time()
        for i in range(100):
            store.store_fact(f"文件性能测试 {i}", {"index": i})
        write_time = time.time() - start
        
        print(f"\n文件写入性能:")
        print(f"  写入: {write_time:.3f}s (100条)")
        
        # 应该在 10 秒内完成
        assert write_time < 10, f"文件写入太慢: {write_time:.2f}s"
    
    def test_file_search_performance(self, temp_dir):
        """测试文件搜索性能"""
        from L4_file_persist import FilePersistStore
        
        store = FilePersistStore(base_path=temp_dir)
        
        # 先写入数据
        for i in range(100):
            store.store_fact(f"搜索性能测试内容 {i}", {"index": i})
        
        # 搜索
        start = time.time()
        for _ in range(100):
            store.search_facts("搜索性能")
        search_time = time.time() - start
        
        print(f"\n文件搜索性能:")
        print(f"  搜索: {search_time:.3f}s (100次)")
        
        # 应该在 5 秒内完成
        assert search_time < 5, f"文件搜索太慢: {search_time:.2f}s"
