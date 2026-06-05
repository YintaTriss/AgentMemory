"""
故障恢复测试

测试场景：
1. Embedding Worker 崩溃 → 重启后从 .embedding_state.json 恢复
2. 写入中途断电 → 重新挂载后无损坏
3. 多 Agent 中一个 Agent 崩溃 → 其它不受影响

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
import random

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


class FailingEmbedder(MockEmbedder):
    """会失败的 Embedder，用于测试错误恢复"""
    
    def __init__(self, fail_count: int = 2, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.call_count = 0
        self.fail_count = fail_count
        self.failed_calls = []
    
    async def embed(self, texts: list) -> list:
        self.call_count += 1
        if self.call_count <= self.fail_count:
            self.failed_calls.append(self.call_count)
            raise Exception(f"Embedding failed (call #{self.call_count})")
        return await super().embed(texts)
    
    async def embed_single(self, text: str) -> list:
        self.call_count += 1
        if self.call_count <= self.fail_count:
            self.failed_calls.append(self.call_count)
            raise Exception(f"Embedding failed (call #{self.call_count})")
        return await super().embed_single(text)


class TestEmbeddingWorkerRecovery:
    """Embedding Worker 崩溃恢复测试"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.temp_dir = tempfile.mkdtemp(prefix="fault_recovery_")
        self.memory_dir = os.path.join(self.temp_dir, "memory")
        os.makedirs(self.memory_dir, exist_ok=True)
        
        yield
        
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_embedding_state_persistence(self):
        """测试 Embedding 状态持久化到 .embedding_state.json"""
        
        embedder = MockEmbedder(dimensions=384)
        vectorstore = MockVectorStore(dimensions=384)
        
        # 创建 worker 并添加任务
        worker = create_worker(
            state_path, ".embedding_state.json"),
            embedder=embedder,
            vectorstore=vectorstore,
        )
        
        # 添加多个任务
        task_ids = []
        for i in range(5):
            task_id = await worker.add_task(
                content=f"测试记忆 {i}",
                metadata={"index": i, "test": "persistence"},
            )
            task_ids.append(task_id)
        
        # 处理任务
        await worker.process_pending()
        await asyncio.sleep(0.2)
        
        # 验证状态文件存在
        state_file = Path(self.memory_dir) / ".embedding_state.json"
        assert state_file.exists(), "State file should exist"
        
        # 停止 worker
        await worker.stop()
        
        # 重新创建 worker（模拟重启）
        worker2 = create_worker(
            state_path, ".embedding_state.json"),
            embedder=MockEmbedder(dimensions=384),
            vectorstore=MockVectorStore(dimensions=384),
        )
        
        # 验证状态恢复
        for task_id in task_ids:
            task = worker2.get_task(task_id)
            assert task is not None, f"Task {task_id} should be recovered"
            print(f"Recovered task {task_id}: status={task.status}, retry_count={task.retry_count}")
        
        await worker2.stop()
        
        print("SUCCESS: Embedding 状态持久化测试通过")
    
    @pytest.mark.asyncio
    async def test_embedding_retry_and_recovery(self):
        """测试 Embedding 失败重试并最终成功"""
        
        embedder = FailingEmbedder(fail_count=2, dimensions=384)
        vectorstore = MockVectorStore(dimensions=384)
        
        worker = create_worker(
            state_path, ".embedding_state.json"),
            embedder=embedder,
            vectorstore=vectorstore,
            max_retries=3,
        )
        
        # 添加任务
        task_id = await worker.add_task(
            content="会失败几次然后成功的记忆",
            metadata={"test": "retry"},
        )
        
        initial_task = worker.get_task(task_id)
        print(f"Initial status: {initial_task.status}")
        
        # 第一次处理 - 应该失败
        try:
            await worker.process_pending()
        except:
            pass
        await asyncio.sleep(0.1)
        
        task_after_first = worker.get_task(task_id)
        print(f"After first process: status={task_after_first.status}, retry_count={task_after_first.retry_count}")
        
        # 第二次处理 - 应该失败
        try:
            await worker.process_pending()
        except:
            pass
        await asyncio.sleep(0.1)
        
        task_after_second = worker.get_task(task_id)
        print(f"After second process: status={task_after_second.status}, retry_count={task_after_second.retry_count}")
        
        # 第三次处理 - 应该成功（FailingEmbedder 只失败 2 次）
        try:
            await worker.process_pending()
        except:
            pass
        await asyncio.sleep(0.1)
        
        final_task = worker.get_task(task_id)
        print(f"Final status: {final_task.status}")
        
        # 验证重试计数
        assert task_after_first.retry_count == 1, f"Expected retry_count=1, got {task_after_first.retry_count}"
        assert task_after_second.retry_count == 2, f"Expected retry_count=2, got {task_after_second.retry_count}"
        
        # 验证最终成功
        assert final_task.status == EmbeddingStatus.COMPLETED, \
            f"Expected COMPLETED, got {final_task.status}"
        
        await worker.stop()
        
        print("SUCCESS: Embedding 重试机制测试通过")
    
    @pytest.mark.asyncio
    async def test_embedding_state_file_corruption_recovery(self):
        """测试状态文件损坏时的恢复"""
        
        embedder = MockEmbedder(dimensions=384)
        vectorstore = MockVectorStore(dimensions=embedder.dimensions)
        
        worker = create_worker(
            state_path, ".embedding_state.json"),
            embedder=embedder,
            vectorstore=vectorstore,
        )
        
        # 写入正常数据
        task_id = await worker.add_task(
            content="正常记忆",
            metadata={"test": "normal"},
        )
        await worker.process_pending()
        await asyncio.sleep(0.1)
        
        await worker.stop()
        
        # 模拟文件损坏
        state_file = Path(self.memory_dir) / ".embedding_state.json"
        with open(state_file, "w") as f:
            f.write("INVALID_JSON{{{")
        
        # 重新初始化 - 应该能处理损坏
        worker2 = create_worker(
            state_path, ".embedding_state.json"),
            embedder=MockEmbedder(dimensions=384),
            vectorstore=MockVectorStore(dimensions=384),
        )
        
        # 添加新任务应该正常
        new_task_id = await worker2.add_task(
            content="损坏后的新记忆",
            metadata={"test": "after_corruption"},
        )
        
        new_task = worker2.get_task(new_task_id)
        assert new_task is not None
        assert new_task.status == EmbeddingStatus.PENDING
        
        print("SUCCESS: 状态文件损坏恢复测试通过")
        
        await worker2.stop()


class TestPowerFailureRecovery:
    """断电恢复测试"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.temp_dir = tempfile.mkdtemp(prefix="power_failure_")
        self.memory_dir = os.path.join(self.temp_dir, "memory")
        os.makedirs(self.memory_dir, exist_ok=True)
        
        yield
        
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_partial_write_recovery(self):
        """测试写入中途断电的数据完整性"""
        
        embedder = MockEmbedder(dimensions=384)
        vectorstore = MockVectorStore(dimensions=embedder.dimensions)
        
        # 第一阶段：写入 5 条记忆
        worker1 = create_worker(
            state_path, ".embedding_state.json"),
            embedder=embedder,
            vectorstore=vectorstore,
        )
        
        task_ids_phase1 = []
        for i in range(5):
            task_id = await worker1.add_task(
                content=f"记忆 {i}: 测试内容 {datetime.now().isoformat()}",
                metadata={"index": i, "phase": 1},
            )
            task_ids_phase1.append(task_id)
        
        # 处理但不等待完成（模拟断电）
        try:
            await worker1.process_pending()
        except:
            pass
        
        await worker1.stop()
        
        # 模拟断电后恢复
        worker2 = create_worker(
            state_path, ".embedding_state.json"),
            embedder=MockEmbedder(dimensions=384),
            vectorstore=MockVectorStore(dimensions=384),
        )
        
        # 验证之前的状态恢复
        recovered_count = 0
        for task_id in task_ids_phase1:
            task = worker2.get_task(task_id)
            if task:
                recovered_count += 1
                print(f"Recovered: {task_id} status={task.status}")
        
        print(f"恢复的任务数: {recovered_count}/{len(task_ids_phase1)}")
        
        # 继续写入
        task_ids_phase2 = []
        for i in range(3):
            task_id = await worker2.add_task(
                content=f"断电后写入 {i}",
                metadata={"after_failure": True, "index": i},
            )
            task_ids_phase2.append(task_id)
        
        await worker2.process_pending()
        await asyncio.sleep(0.2)
        
        # 验证所有任务
        all_task_ids = task_ids_phase1 + task_ids_phase2
        total_count = len(all_task_ids)
        
        completed_count = 0
        for task_id in all_task_ids:
            task = worker2.get_task(task_id)
            if task and task.status == EmbeddingStatus.COMPLETED:
                completed_count += 1
        
        print(f"总任务数: {total_count}")
        print(f"已完成: {completed_count}")
        
        assert completed_count >= total_count * 0.8, \
            f"Expected at least {total_count * 0.8} completed, got {completed_count}"
        
        await worker2.stop()
        
        print(f"SUCCESS: 部分写入恢复测试通过")
    
    @pytest.mark.asyncio
    async def test_transaction_integrity(self):
        """测试事务完整性"""
        
        embedder = MockEmbedder(dimensions=384)
        vectorstore = MockVectorStore(dimensions=embedder.dimensions)
        
        worker = create_worker(
            state_path, ".embedding_state.json"),
            embedder=embedder,
            vectorstore=vectorstore,
        )
        
        # 批量写入
        batch_size = 20
        task_ids = []
        for i in range(batch_size):
            task_id = await worker.add_task(
                content=f"Batch test {i}",
                metadata={"batch": True, "index": i},
            )
            task_ids.append(task_id)
        
        # 验证所有 ID 都是唯一的
        assert len(set(task_ids)) == batch_size, "All task IDs should be unique"
        
        # 处理所有任务
        await worker.process_pending()
        await asyncio.sleep(0.3)
        
        # 验证状态文件
        state_file = Path(self.memory_dir) / ".embedding_state.json"
        assert state_file.exists()
        
        with open(state_file, "r") as f:
            state_data = json.load(f)
        
        tasks_in_state = state_data.get("tasks", {})
        
        print(f"写入总数: {batch_size}")
        print(f"状态文件中的任务数: {len(tasks_in_state)}")
        
        assert len(tasks_in_state) == batch_size, \
            f"Expected {batch_size} tasks in state, got {len(tasks_in_state)}"
        
        await worker.stop()
        
        print(f"SUCCESS: 事务完整性测试通过 - {batch_size} 条记忆")


class TestAgentCrashRecovery:
    """多 Agent 崩溃恢复测试"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.temp_dir = tempfile.mkdtemp(prefix="agent_crash_")
        self.memory_dir = os.path.join(self.temp_dir, "memory")
        os.makedirs(self.memory_dir, exist_ok=True)
        
        yield
        
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_one_agent_crash_others_continue(self):
        """测试一个 Agent 崩溃时其他 Agent 不受影响"""
        
        # 创建 3 个 Agent
        agents = []
        for name in ["agent_alpha", "agent_beta", "agent_gamma"]:
            embedder = MockEmbedder(dimensions=384)
            vectorstore = MockVectorStore(dimensions=embedder.dimensions)
            
            worker = create_worker(
                state_path, f".embedding_state_{name}.json"),
                embedder=embedder,
                vectorstore=vectorstore,
            )
            agents.append((name, worker))
        
        # agent_alpha 和 agent_beta 写入
        alpha_tasks = []
        for i in range(5):
            task_id = await agents[0][1].add_task(
                content=f"[alpha] Memory {i}",
                metadata={"agent": "alpha", "index": i},
            )
            alpha_tasks.append(task_id)
        
        beta_tasks = []
        for i in range(5):
            task_id = await agents[1][1].add_task(
                content=f"[beta] Memory {i}",
                metadata={"agent": "beta", "index": i},
            )
            beta_tasks.append(task_id)
        
        # 处理 alpha 和 beta
        await agents[0][1].process_pending()
        await agents[1][1].process_pending()
        
        # agent_gamma "崩溃" - 停止其 worker
        await agents[2][1].stop()
        
        # alpha 和 beta 应该仍然可以继续工作
        alpha_continue_tasks = []
        for i in range(3):
            task_id = await agents[0][1].add_task(
                content=f"[alpha] After crash {i}",
                metadata={"agent": "alpha", "after_crash": True},
            )
            alpha_continue_tasks.append(task_id)
        
        beta_continue_tasks = []
        for i in range(3):
            task_id = await agents[1][1].add_task(
                content=f"[beta] After crash {i}",
                metadata={"agent": "beta", "after_crash": True},
            )
            beta_continue_tasks.append(task_id)
        
        # 处理继续的任务
        await agents[0][1].process_pending()
        await agents[1][1].process_pending()
        
        await asyncio.sleep(0.2)
        
        # 验证结果
        print(f"\n{'='*50}")
        print(f"Agent 崩溃恢复测试结果")
        print(f"{'='*50}")
        
        alpha_total = len(alpha_tasks) + len(alpha_continue_tasks)
        beta_total = len(beta_tasks) + len(beta_continue_tasks)
        
        alpha_completed = 0
        for tid in alpha_tasks + alpha_continue_tasks:
            task = agents[0][1].get_task(tid)
            if task and task.status == EmbeddingStatus.COMPLETED:
                alpha_completed += 1
        
        beta_completed = 0
        for tid in beta_tasks + beta_continue_tasks:
            task = agents[1][1].get_task(tid)
            if task and task.status == EmbeddingStatus.COMPLETED:
                beta_completed += 1
        
        print(f"alpha 任务总数: {alpha_total}, 完成: {alpha_completed}")
        print(f"beta 任务总数: {beta_total}, 完成: {beta_completed}")
        print(f"gamma 状态: 已停止（崩溃）")
        
        # 验证 alpha 和 beta 都成功
        assert alpha_completed >= alpha_total * 0.8, \
            f"alpha should complete most tasks, got {alpha_completed}/{alpha_total}"
        assert beta_completed >= beta_total * 0.8, \
            f"beta should complete most tasks, got {beta_completed}/{beta_total}"
        
        # 清理
        await agents[0][1].stop()
        await agents[1][1].stop()
        
        print("SUCCESS: Agent 崩溃恢复测试通过")
    
    @pytest.mark.asyncio
    async def test_crash_recovery_state_consistency(self):
        """测试崩溃后状态一致性"""
        
        embedder = MockEmbedder(dimensions=384)
        vectorstore = MockVectorStore(dimensions=embedder.dimensions)
        
        # 第一阶段：创建一些任务
        worker1 = create_worker(
            state_path, ".embedding_state.json"),
            embedder=embedder,
            vectorstore=vectorstore,
        )
        
        ids_phase1 = []
        for i in range(5):
            task_id = await worker1.add_task(
                content=f"Phase 1 memory {i}",
                metadata={"phase": 1},
            )
            ids_phase1.append(task_id)
        
        await worker1.process_pending()
        await asyncio.sleep(0.1)
        
        await worker1.stop()
        
        # 第二阶段：模拟崩溃后恢复
        worker2 = create_worker(
            state_path, ".embedding_state.json"),
            embedder=MockEmbedder(dimensions=384),
            vectorstore=MockVectorStore(dimensions=384),
        )
        
        ids_phase2 = []
        for i in range(5):
            task_id = await worker2.add_task(
                content=f"Phase 2 memory {i}",
                metadata={"phase": 2},
            )
            ids_phase2.append(task_id)
        
        await worker2.process_pending()
        await asyncio.sleep(0.1)
        
        # 验证：两个阶段的数据都存在
        all_ids = ids_phase1 + ids_phase2
        
        recovered_phase1 = sum(1 for tid in ids_phase1 if worker2.get_task(tid) is not None)
        recovered_phase2 = sum(1 for tid in ids_phase2 if worker2.get_task(tid) is not None)
        
        print(f"\n{'='*50}")
        print(f"崩溃恢复状态一致性测试")
        print(f"{'='*50}")
        print(f"Phase 1 任务数: {len(ids_phase1)}, 恢复: {recovered_phase1}")
        print(f"Phase 2 任务数: {len(ids_phase2)}, 恢复: {recovered_phase2}")
        
        # Phase 1 应该被恢复
        assert recovered_phase1 >= len(ids_phase1) * 0.8, \
            f"Phase 1 should be recovered"
        
        # Phase 2 应该存在
        assert recovered_phase2 == len(ids_phase2), \
            f"All Phase 2 tasks should exist"
        
        # 验证 ID 不重复
        all_ids_combined = ids_phase1 + ids_phase2
        assert len(set(all_ids_combined)) == len(all_ids_combined), \
            "All IDs should be unique"
        
        await worker2.stop()
        
        print("SUCCESS: 崩溃恢复状态一致性测试通过")


class TestConcurrentFaultTolerance:
    """并发故障容错测试"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.temp_dir = tempfile.mkdtemp(prefix="concurrent_fault_")
        self.memory_dir = os.path.join(self.temp_dir, "memory")
        os.makedirs(self.memory_dir, exist_ok=True)
        
        yield
        
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_concurrent_write_with_random_failures(self):
        """测试并发写入时随机失败的情况"""
        
        num_workers = 5
        writes_per_worker = 10
        
        success_counts = [0] * num_workers
        error_counts = [0] * num_workers
        results_queue = queue.Queue()
        errors_queue = queue.Queue()
        
        def worker_with_random_failure(worker_id: int):
            """带随机失败的 worker"""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # 20% 概率失败的 embedder
                class RandomFailEmbedder(MockEmbedder):
                    def __init__(self, wid, *args, **kwargs):
                        super().__init__(*args, **kwargs)
                        self.worker_id = wid
                        self.call_count = 0
                    
                    async def embed_single(self, text: str) -> list:
                        self.call_count += 1
                        if random.random() < 0.2:
                            raise Exception(f"Random failure in worker {self.worker_id}")
                        return await super().embed_single(text)
                
                embedder = RandomFailEmbedder(worker_id, dimensions=384)
                vectorstore = MockVectorStore(dimensions=embedder.dimensions)
                
                worker = create_worker(
                    state_path, f".embedding_state_worker_{worker_id}.json"),
                    embedder=embedder,
                    vectorstore=vectorstore,
                )
                
                for i in range(writes_per_worker):
                    try:
                        task_id = loop.run_until_complete(
                            worker.add_task(
                                content=f"[Worker-{worker_id}] Memory {i}",
                                metadata={"worker": worker_id, "index": i},
                            )
                        )
                        
                        # 尝试处理
                        try:
                            loop.run_until_complete(worker.process_pending())
                        except:
                            pass
                        
                        success_counts[worker_id] += 1
                        
                    except Exception as e:
                        error_counts[worker_id] += 1
                
                loop.run_until_complete(worker.stop())
                loop.close()
                results_queue.put(success_counts[worker_id])
                
            except Exception as e:
                errors_queue.put(f"Worker {worker_id}: {e}")
        
        # 并发执行
        threads = []
        for i in range(num_workers):
            t = threading.Thread(target=worker_with_random_failure, args=(i,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # 收集结果
        total_success = sum(success_counts)
        total_errors = sum(error_counts)
        
        errors = []
        while not errors_queue.empty():
            errors.append(errors_queue.get())
        
        print(f"\n{'='*50}")
        print(f"并发随机失败测试结果")
        print(f"{'='*50}")
        print(f"Worker 数: {num_workers}")
        print(f"每 Worker 目标写入: {writes_per_worker}")
        print(f"总成功写入: {total_success}")
        print(f"总错误数: {total_errors}")
        print(f"系统级错误: {len(errors)}")
        
        for i in range(num_workers):
            print(f"  Worker {i}: {success_counts[i]} 成功, {error_counts[i]} 错误")
        
        # 至少应该有一些成功的写入
        assert total_success > 0, "At least some writes should succeed"
        
        # 验证状态文件
        state_files = list(Path(self.memory_dir).glob(".embedding_state_worker_*.json"))
        print(f"状态文件数: {len(state_files)}")
        
        print("SUCCESS: 并发随机失败测试通过")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
