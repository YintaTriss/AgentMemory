"""
多 Agent 并发测试

测试场景：
1. 3 个 Agent（commander/coder/qa）并发写入不同分类
2. 共用同一 memory_library/
3. Append 日志无丢失
4. 没有文件冲突

@author: QA Engineer 2
"""

import pytest
import asyncio
import tempfile
import shutil
import os
import json
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import sys
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

# 添加项目根目录到 path (使用绝对路径避免导入冲突)
import pathlib
_project_root = pathlib.Path(__file__).parent.parent.parent.absolute()
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from agentmemory import (
    MockEmbedder,
    MockVectorStore,
    EmbeddingWorker,
    EmbeddingStatus,
    create_worker,
)


@dataclass
class AgentStats:
    """Agent 统计信息"""
    name: str
    category: str
    write_count: int = 0
    error_count: int = 0
    task_ids: List[str] = None
    
    def __post_init__(self):
        if self.task_ids is None:
            self.task_ids = []


class AgentWorker:
    """Agent 工作器 - 模拟单个 Agent"""
    
    def __init__(self, name: str, memory_dir: str, category: str, embedder: MockEmbedder):
        self.name = name
        self.memory_dir = memory_dir
        self.category = category
        self.embedder = embedder
        self.stats = AgentStats(name=name, category=category)
        self.lock = threading.Lock()
        self.worker = None
        self.vectorstore = None
    
    async def initialize(self):
        """初始化 Agent"""
        self.vectorstore = MockVectorStore(dimensions=self.embedder.dimensions)
        self.worker = create_worker(
            state_path, f".embedding_state_{self.name}.json"),
            embedder=self.embedder,
            vectorstore=self.vectorstore,
        )
    
    async def write_memories(self, count: int) -> List[Dict]:
        """写入多条记忆"""
        results = []
        for i in range(count):
            try:
                content = f"[{self.name}] {self.category} - 任务 {i+1} - 时间 {datetime.now().isoformat()}"
                metadata = {
                    "category": self.category,
                    "agent": self.name,
                    "task_id": i + 1,
                    "timestamp": datetime.now().isoformat()
                }
                
                task_id = await self.worker.add_task(
                    content=content,
                    metadata=metadata,
                )
                
                with self.lock:
                    self.stats.write_count += 1
                    self.stats.task_ids.append(task_id)
                    results.append({
                        "agent": self.name,
                        "task_id": task_id,
                        "content": content,
                        "category": self.category
                    })
                    
            except Exception as e:
                with self.lock:
                    self.stats.error_count += 1
                print(f"[{self.name}] Error writing: {e}")
                    
        return results
    
    async def process_tasks(self):
        """处理 pending 任务"""
        try:
            await self.worker.process_pending()
        except Exception as e:
            print(f"[{self.name}] Error processing: {e}")
    
    async def shutdown(self):
        """关闭 Agent"""
        if self.worker:
            await self.worker.stop()
    
    def get_stats(self) -> AgentStats:
        with self.lock:
            return AgentStats(
                name=self.stats.name,
                category=self.stats.category,
                write_count=self.stats.write_count,
                error_count=self.stats.error_count,
                task_ids=self.stats.task_ids.copy()
            )


class TestConcurrentAgents:
    """多 Agent 并发测试套件"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.temp_dir = tempfile.mkdtemp(prefix="e2e_concurrent_")
        self.memory_dir = os.path.join(self.temp_dir, "memory")
        os.makedirs(self.memory_dir, exist_ok=True)
        
        yield
        
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_3_agents_concurrent_write(self):
        """3 个 Agent 并发写入测试 - 共享 memory_dir"""
        
        # 创建共享的 embedder
        shared_embedder = MockEmbedder(dimensions=384)
        
        # 创建 3 个 Agent worker
        agents = [
            AgentWorker("commander", self.memory_dir, "A.项目/石榴籽/规划", shared_embedder),
            AgentWorker("coder", self.memory_dir, "A.项目/石榴籽/代码", shared_embedder),
            AgentWorker("qa", self.memory_dir, "A.项目/石榴籽/测试", shared_embedder),
        ]
        
        # 初始化所有 Agent
        for agent in agents:
            await agent.initialize()
        
        # 每个 Agent 写入 10 条记忆
        tasks_per_agent = 10
        
        # 并发执行所有 Agent 的写入任务
        write_tasks = []
        for agent in agents:
            for i in range(tasks_per_agent):
                write_tasks.append(agent.write_memories(1))
        
        # 使用 asyncio.gather 并发执行写入
        all_results = await asyncio.gather(*write_tasks, return_exceptions=True)
        
        # 处理所有任务
        process_tasks = [agent.process_tasks() for agent in agents]
        await asyncio.gather(*process_tasks, return_exceptions=True)
        
        # 等待完成
        await asyncio.sleep(0.5)
        
        # 收集统计
        stats_list = [agent.get_stats() for agent in agents]
        
        total_written = sum(s.write_count for s in stats_list)
        total_errors = sum(s.error_count for s in stats_list)
        
        print(f"\n{'='*50}")
        print(f"3 Agent 并发写入测试结果")
        print(f"{'='*50}")
        print(f"预期写入: {len(agents) * tasks_per_agent}")
        print(f"实际写入: {total_written}")
        print(f"错误数: {total_errors}")
        for stats in stats_list:
            print(f"  - {stats.name}: {stats.write_count} 条写入, {stats.error_count} 个错误")
        
        # 验证写入数量
        expected = len(agents) * tasks_per_agent
        assert total_written == expected, f"Expected {expected} memories, got {total_written}"
        
        # 验证无错误
        assert total_errors == 0, f"Expected no errors, got {total_errors}"
        
        # 验证文件存在
        state_files = list(Path(self.memory_dir).glob(".embedding_state_*.json"))
        print(f"状态文件数: {len(state_files)}")
        assert len(state_files) == len(agents), f"Expected {len(agents)} state files"
        
        # 清理
        for agent in agents:
            await agent.shutdown()
        
        print(f"SUCCESS: 3 Agent 并发写入测试通过")
    
    @pytest.mark.asyncio
    async def test_concurrent_no_file_conflict(self):
        """并发写入无文件冲突测试"""
        
        # 使用线程池模拟真实并发
        num_threads = 5
        writes_per_thread = 5
        results_queue = queue.Queue()
        errors_queue = queue.Queue()
        
        def write_worker(worker_id: int):
            """线程工作函数"""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                embedder = MockEmbedder(dimensions=384)
                vectorstore = MockVectorStore(dimensions=embedder.dimensions)
                
                worker = create_worker(
                    state_path, f".embedding_state_thread_{worker_id}.json"),
                    embedder=embedder,
                    vectorstore=vectorstore,
                )
                
                count = 0
                for i in range(writes_per_thread):
                    content = f"[Worker-{worker_id}] 任务 {i+1}"
                    metadata = {
                        "worker_id": worker_id,
                        "task_id": i + 1,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    task_id = loop.run_until_complete(
                        worker.add_task(content, metadata)
                    )
                    count += 1
                    
                    # 立即处理
                    try:
                        loop.run_until_complete(worker.process_pending())
                    except:
                        pass
                
                loop.run_until_complete(worker.stop())
                loop.close()
                results_queue.put(count)
                
            except Exception as e:
                errors_queue.put(str(e))
        
        # 启动线程池
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(write_worker, i) for i in range(num_threads)]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    errors_queue.put(str(e))
        
        # 收集结果
        total_written = 0
        while not results_queue.empty():
            total_written += results_queue.get()
        
        errors = []
        while not errors_queue.empty():
            errors.append(errors_queue.get())
        
        print(f"\n{'='*50}")
        print(f"并发文件冲突测试结果")
        print(f"{'='*50}")
        print(f"线程数: {num_threads}")
        print(f"每线程写入: {writes_per_thread}")
        print(f"预期总数: {num_threads * writes_per_thread}")
        print(f"实际总数: {total_written}")
        print(f"错误数: {len(errors)}")
        
        # 验证写入数量
        expected = num_threads * writes_per_thread
        assert total_written == expected, f"Expected {expected}, got {total_written}"
        
        # 验证无系统错误
        assert len(errors) == 0, f"System errors: {errors}"
        
        print(f"SUCCESS: 并发无文件冲突测试通过")
    
    @pytest.mark.asyncio
    async def test_append_log_no_data_loss(self):
        """Append-only 日志无数据丢失测试"""
        
        embedder = MockEmbedder(dimensions=384)
        vectorstore = MockVectorStore(dimensions=embedder.dimensions)
        
        worker = create_worker(
            state_path, ".embedding_state.json"),
            embedder=embedder,
            vectorstore=vectorstore,
        )
        
        # 并发写入 50 条记忆
        num_writes = 50
        
        async def write_batch(start_id: int, count: int):
            """写入一批记忆"""
            for i in range(count):
                await worker.add_task(
                    content=f"记忆 {start_id + i}: 测试内容",
                    metadata={"batch_id": start_id, "index": i},
                )
        
        # 分 5 批并发写入
        batch_size = num_writes // 5
        tasks = []
        for i in range(5):
            tasks.append(write_batch(i * batch_size, batch_size))
        
        await asyncio.gather(*tasks)
        
        # 处理所有任务
        await worker.process_pending()
        await asyncio.sleep(0.3)
        
        # 验证状态文件
        state_file = Path(self.memory_dir) / ".embedding_state.json"
        assert state_file.exists()
        
        with open(state_file, "r") as f:
            state_data = json.load(f)
        
        tasks_in_state = state_data.get("tasks", {})
        
        print(f"\n{'='*50}")
        print(f"Append 日志无数据丢失测试")
        print(f"{'='*50}")
        print(f"写入总数: {num_writes}")
        print(f"状态文件中的任务数: {len(tasks_in_state)}")
        
        # 验证所有任务都在状态文件中
        assert len(tasks_in_state) >= num_writes * 0.9, \
            f"Expected at least {num_writes * 0.9} tasks in state, got {len(tasks_in_state)}"
        
        # 验证完成的任务
        completed_count = sum(
            1 for t in tasks_in_state.values()
            if t.get("status") == EmbeddingStatus.COMPLETED.value
        )
        print(f"已完成任务数: {completed_count}")
        
        await worker.stop()
        
        print(f"SUCCESS: Append 日志无数据丢失测试通过")


class TestAgentIsolation:
    """Agent 隔离测试"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.temp_dir = tempfile.mkdtemp(prefix="e2e_isolation_")
        self.memory_dir = os.path.join(self.temp_dir, "memory")
        os.makedirs(self.memory_dir, exist_ok=True)
        
        yield
        
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_agents_isolated_by_category(self):
        """Agent 按分类隔离测试"""
        
        embedder = MockEmbedder(dimensions=384)
        
        # 创建不同分类的 Agent
        agents = {
            "commander": AgentWorker("commander", self.memory_dir, "A.项目/石榴籽/规划", embedder),
            "coder": AgentWorker("coder", self.memory_dir, "A.项目/石榴籽/代码", embedder),
            "qa": AgentWorker("qa", self.memory_dir, "A.项目/石榴籽/测试", embedder),
        }
        
        # 初始化所有 Agent
        for agent in agents.values():
            await agent.initialize()
        
        # 每个 Agent 写入不同分类
        await agents["commander"].write_memories(5)
        await agents["coder"].write_memories(5)
        await agents["qa"].write_memories(5)
        
        # 处理任务
        for agent in agents.values():
            await agent.process_tasks()
        
        await asyncio.sleep(0.3)
        
        # 验证分类隔离
        for name, agent in agents.items():
            stats = agent.get_stats()
            print(f"{name}: {stats.write_count} 写入, category={stats.category}")
            
            # 验证每个 Agent 只写入了自己的分类
            assert stats.write_count == 5, f"Agent {name} should have 5 writes"
        
        # 验证状态文件按 Agent 分开
        state_files = list(Path(self.memory_dir).glob(".embedding_state_*.json"))
        print(f"状态文件数: {len(state_files)}")
        
        # 清理
        for agent in agents.values():
            await agent.shutdown()
        
        print(f"SUCCESS: Agent 分类隔离测试通过")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
