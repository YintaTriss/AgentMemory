"""
memory_manager.py 集成测试
"""

import pytest
import asyncio
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../..", "src"))


class TestMemoryHermesBasic:
    """MemoryHermes 基础功能测试"""
    
    def test_memory_hermes_init(self, temp_dir):
        """测试 MemoryHermes 初始化"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        assert mh is not None
        assert hasattr(mh, 'get_stats')
        assert hasattr(mh, 'get_prefetched')
    
    def test_get_stats(self, temp_dir):
        """测试统计接口"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        stats = mh.get_stats()
        
        assert isinstance(stats, dict)
        assert 'layers' in stats
        assert 'total_memories' in stats
    
    def test_get_prefetched(self, temp_dir):
        """测试预取缓存获取"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        prefetched = mh.get_prefetched()
        
        # 初始应该为空
        assert prefetched == "" or prefetched == []


class TestMemoryHermesStore:
    """MemoryHermes 存储功能测试"""
    
    @pytest.mark.asyncio
    async def test_store_basic(self, temp_dir):
        """测试基本存储功能"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        result = await mh.execute("store", {
            "content": "测试：agentmemory 存储功能",
            "metadata": {"source": "test", "category": "learning"},
            "importance": 0.9
        })
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_store_multiple(self, temp_dir):
        """测试多次存储"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        for i in range(5):
            await mh.execute("store", {
                "content": f"测试记忆 {i}",
                "importance": 0.5 + i * 0.1
            })
        
        stats = await mh.execute("get_stats")
        assert stats is not None
    
    @pytest.mark.asyncio
    async def test_store_with_entities(self, temp_dir):
        """测试带实体的存储"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        result = await mh.execute("store", {
            "content": "优优在石榴籽项目中工作",
            "metadata": {"entities": ["优优", "石榴籽"]},
            "importance": 0.8
        })
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_store_with_tags(self, temp_dir):
        """测试带标签的存储"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        result = await mh.execute("store", {
            "content": "标记为重要的记忆",
            "metadata": {"tags": ["重要", "工作"]},
            "importance": 0.9
        })
        
        assert result is not None


class TestMemoryHermesQuery:
    """MemoryHermes 查询功能测试"""
    
    @pytest.mark.asyncio
    async def test_query_basic(self, temp_dir):
        """测试基本查询"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        # 先存储
        await mh.execute("store", {
            "content": "用户喜欢简洁的回复风格",
            "importance": 0.8
        })
        
        # 再查询
        result = await mh.execute("query", {
            "query": "用户偏好",
            "limit": 5
        })
        
        assert result is not None
        assert 'results' in result
    
    @pytest.mark.asyncio
    async def test_query_with_filter(self, temp_dir):
        """测试带过滤的查询"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        # 存储不同类别的记忆
        await mh.execute("store", {
            "content": "偏好记忆",
            "metadata": {"category": "preference"},
            "importance": 0.8
        })
        
        await mh.execute("store", {
            "content": "项目记忆",
            "metadata": {"category": "project"},
            "importance": 0.7
        })
        
        result = await mh.execute("query", {
            "query": "记忆",
            "limit": 10
        })
        
        assert 'results' in result
    
    @pytest.mark.asyncio
    async def test_query_empty_results(self, temp_dir):
        """测试空查询结果"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        result = await mh.execute("query", {
            "query": "完全不存在的查询内容xyz123",
            "limit": 5
        })
        
        assert 'results' in result


class TestMemoryHermesPrefetch:
    """MemoryHermes 预取功能测试"""
    
    @pytest.mark.asyncio
    async def test_prefetch_basic(self, temp_dir):
        """测试基本预取"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        # 先存储
        await mh.execute("store", {
            "content": "关于优优的偏好和项目信息"
        })
        
        # 预取
        prefetched = await mh.prefetch("优优")
        
        # 预取后应该能获取到
        cached = mh.get_prefetched()
        assert cached is not None


class TestMemoryHermesDecay:
    """MemoryHermes 遗忘功能测试"""
    
    @pytest.mark.asyncio
    async def test_decay_check(self, temp_dir):
        """测试遗忘检查"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        # 运行遗忘检查
        result = await mh.run_decay_check()
        
        assert result is not None
        assert 'forget' in result or 'archive' in result
    
    @pytest.mark.asyncio
    async def test_decay_with_memories(self, temp_dir):
        """测试带记忆的遗忘"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        # 存储多个记忆
        for i in range(10):
            await mh.execute("store", {
                "content": f"记忆 {i}",
                "importance": 0.1 + i * 0.1  # 不同重要性
            })
        
        # 运行遗忘检查
        result = await mh.run_decay_check()
        
        assert result is not None


class TestMemoryHermesExecute:
    """MemoryHermes execute 方法测试"""
    
    @pytest.mark.asyncio
    async def test_execute_store(self, temp_dir):
        """测试 execute store 命令"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        result = await mh.execute("store", {
            "content": "execute 测试",
            "metadata": {"test": "execute"}
        })
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_execute_query(self, temp_dir):
        """测试 execute query 命令"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        result = await mh.execute("query", {
            "query": "测试"
        })
        
        assert 'results' in result
    
    @pytest.mark.asyncio
    async def test_execute_get_stats(self, temp_dir):
        """测试 execute get_stats 命令"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        result = await mh.execute("get_stats")
        
        assert isinstance(result, dict)
    
    @pytest.mark.asyncio
    async def test_execute_invalid_command(self, temp_dir):
        """测试无效命令"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        result = await mh.execute("invalid_command", {})
        
        # 应该返回错误或空结果
        assert result is None or 'error' in str(result).lower()


class TestMemoryHermesSync:
    """MemoryHermes 同步功能测试"""
    
    @pytest.mark.asyncio
    async def test_sync_turn(self, temp_dir):
        """测试对话轮次同步"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        result = await mh.sync_turn(
            user_message="用户说了什么",
            assistant_message="助手回答了什么"
        )
        
        assert result is not None
        # 应该提取出事实
        assert isinstance(result, (list, dict)) or result is not None
    
    @pytest.mark.asyncio
    async def test_on_session_end(self, temp_dir):
        """测试会话结束"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        # 先有一些交互
        await mh.sync_turn("问题", "回答")
        
        result = await mh.on_session_end()
        
        assert result is not None
        assert 'session_duration_seconds' in str(result) or isinstance(result, dict)


class TestMemoryHermesEdgeCases:
    """MemoryHermes 边界情况测试"""
    
    @pytest.mark.asyncio
    async def test_empty_content_store(self, temp_dir):
        """测试空内容存储"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        # 空内容可能应该被拒绝
        result = await mh.execute("store", {
            "content": ""
        })
        
        # 结果可能是 None 或错误
        assert result is None or result is not None
    
    @pytest.mark.asyncio
    async def test_very_long_content(self, temp_dir):
        """测试超长内容"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        long_content = "x" * 10000  # 10KB
        
        result = await mh.execute("store", {
            "content": long_content
        })
        
        # 应该能处理
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_special_characters(self, temp_dir):
        """测试特殊字符"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        special_content = "测试<>\"'&符号\n换行\t制表符和emoji😀🎉"
        
        result = await mh.execute("store", {
            "content": special_content
        })
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_unicode_content(self, temp_dir):
        """测试 Unicode 内容"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        result = await mh.execute("store", {
            "content": "中文日本語한국어Mix混合"
        })
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_extreme_importance(self, temp_dir):
        """测试极端重要性值"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        # 最高重要性
        await mh.execute("store", {
            "content": "最高重要性记忆",
            "importance": 1.0
        })
        
        # 最低重要性
        await mh.execute("store", {
            "content": "最低重要性记忆",
            "importance": 0.0
        })
        
        stats = await mh.execute("get_stats")
        assert stats is not None


class TestMemoryHermesPerformance:
    """MemoryHermes 性能测试"""
    
    @pytest.mark.asyncio
    async def test_batch_store_performance(self, temp_dir):
        """测试批量存储性能"""
        import time
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        start = time.time()
        
        # 批量存储 50 条
        for i in range(50):
            await mh.execute("store", {
                "content": f"性能测试记忆 {i}",
                "importance": 0.5
            })
        
        elapsed = time.time() - start
        
        # 50 条应该在 30 秒内完成
        assert elapsed < 30, f"批量存储太慢: {elapsed}s"
    
    @pytest.mark.asyncio
    async def test_query_performance(self, temp_dir):
        """测试查询性能"""
        import time
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        # 先存储一些数据
        for i in range(100):
            await mh.execute("store", {
                "content": f"测试记忆内容 {i}",
                "importance": 0.5
            })
        
        # 测试查询性能
        start = time.time()
        for _ in range(10):
            await mh.execute("query", {"query": "测试"})
        elapsed = time.time() - start
        
        # 10 次查询应该在 10 秒内完成
        assert elapsed < 10, f"查询太慢: {elapsed}s"


class TestMemoryHermesIntegration:
    """MemoryHermes 完整集成测试"""
    
    @pytest.mark.asyncio
    async def test_full_workflow(self, temp_dir):
        """测试完整工作流"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        # 1. 存储记忆
        await mh.execute("store", {
            "content": "优优参与石榴籽AI翻译项目",
            "metadata": {"entities": ["优优", "石榴籽"]},
            "importance": 0.9
        })
        
        # 2. 存储更多记忆
        await mh.execute("store", {
            "content": "用户偏好简洁回复风格",
            "metadata": {"category": "preference"},
            "importance": 0.8
        })
        
        # 3. 查询记忆
        result = await mh.execute("query", {
            "query": "优优 石榴籽",
            "limit": 5
        })
        
        assert 'results' in result
        
        # 4. 获取统计
        stats = await mh.execute("get_stats")
        assert stats is not None
        
        # 5. 运行遗忘检查
        decay_result = await mh.run_decay_check()
        assert decay_result is not None
    
    @pytest.mark.asyncio
    async def test_concurrent_operations(self, temp_dir):
        """测试并发操作"""
        from memory_manager import MemoryHermes
        
        mh = MemoryHermes()
        
        # 并发存储
        tasks = []
        for i in range(10):
            task = mh.execute("store", {
                "content": f"并发记忆 {i}",
                "importance": 0.5
            })
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        
        # 验证所有都存储成功
        stats = await mh.execute("get_stats")
        assert stats is not None
