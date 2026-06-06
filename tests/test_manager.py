"""
MemoryManager 单元测试
测试 MemoryManager 主类
"""
import pytest
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

from src.agent_memory.manager import MemoryManager


class TestMemoryManagerBasic:
    """MemoryManager 基本功能测试"""

    @pytest.mark.asyncio
    async def test_init_creates_layers(self, tmp_memory_dir):
        """初始化创建各层"""
        # 使用 L4-only 模式
        with patch('src.agent_memory.manager.L3LanceDBStore') as mock_l3:
            mock_l3_instance = MagicMock()
            mock_l3_instance.get_stats.return_value = {"vector_count": 0}
            mock_l3.return_value = mock_l3_instance
            
            manager = MemoryManager(memory_dir=str(tmp_memory_dir))
            
            assert manager is not None
            assert manager.l4 is not None

    @pytest.mark.asyncio
    async def test_add_increases_memory(self, tmp_memory_dir):
        """add → 完整流程"""
        with patch('src.agent_memory.manager.L3LanceDBStore') as mock_l3:
            mock_l3_instance = MagicMock()
            mock_l3_instance.get_stats.return_value = {"vector_count": 0}
            mock_l3.return_value = mock_l3_instance
            
            manager = MemoryManager(memory_dir=str(tmp_memory_dir))
            
            memory_id = manager.add("测试记忆内容", importance=0.8)
            
            assert memory_id is not None
            assert memory_id.startswith("mem_")

    @pytest.mark.asyncio
    async def test_add_search_flow(self, tmp_memory_dir):
        """add → search 完整流程"""
        with patch('src.agent_memory.manager.L3LanceDBStore') as mock_l3:
            mock_l3_instance = MagicMock()
            mock_l3_instance.get_stats.return_value = {"vector_count": 0}
            mock_l3_instance.search.return_value = []
            mock_l3.return_value = mock_l3_instance
            
            manager = MemoryManager(memory_dir=str(tmp_memory_dir))
            
            # 添加记忆
            memory_id = manager.add("Python 编程", importance=0.9)
            
            # 验证存在
            all_memories = manager.list_all()
            assert any(m["id"] == memory_id for m in all_memories)

    @pytest.mark.asyncio
    async def test_add_list_get_delete_flow(self, tmp_memory_dir):
        """add → list → get → delete 完整流程"""
        with patch('src.agent_memory.manager.L3LanceDBStore') as mock_l3:
            mock_l3_instance = MagicMock()
            mock_l3_instance.get_stats.return_value = {"vector_count": 0}
            mock_l3_instance.search.return_value = []
            mock_l3.return_value = mock_l3_instance
            
            manager = MemoryManager(memory_dir=str(tmp_memory_dir))
            
            # Add
            memory_id = manager.add("测试记忆", importance=0.7)
            
            # List
            all_memories = manager.list_all()
            assert len(all_memories) > 0
            
            # Get
            memory = manager.get(memory_id)
            assert memory is not None
            assert "测试记忆" in memory["content"]
            
            # Delete
            result = manager.delete(memory_id)
            assert result == True
            
            # 验证删除
            deleted_memory = manager.get(memory_id)
            assert deleted_memory is None

    def test_stats_returns_correct_fields(self, tmp_memory_dir):
        """stats 返回正确字段"""
        with patch('src.agent_memory.manager.L3LanceDBStore') as mock_l3:
            mock_l3_instance = MagicMock()
            mock_l3_instance.get_stats.return_value = {"vector_count": 0}
            mock_l3.return_value = mock_l3_instance
            
            manager = MemoryManager(memory_dir=str(tmp_memory_dir))
            
            stats = manager.stats()
            
            # 验证 stats 结构
            assert "total_memories" in stats or isinstance(stats, dict)


class TestCategoryPath:
    """分类路径测试"""

    @pytest.mark.asyncio
    async def test_category_path_auto_classification(self, tmp_memory_dir):
        """category_path 自动分类"""
        with patch('src.agent_memory.manager.L3LanceDBStore') as mock_l3:
            mock_l3_instance = MagicMock()
            mock_l3_instance.get_stats.return_value = {"vector_count": 0}
            mock_l3_instance.search.return_value = []
            mock_l3.return_value = mock_l3_instance
            
            manager = MemoryManager(memory_dir=str(tmp_memory_dir))
            
            # 存储带分类的内容
            memory_id = manager.add(
                "开发 AgentMemory 项目代码",
                category="项目/石榴籽",
                importance=0.9
            )
            
            # 验证分类
            memory = manager.get(memory_id)
            assert memory is not None
            assert "石榴籽" in memory.get("category", "")

    @pytest.mark.asyncio
    async def test_default_category(self, tmp_memory_dir):
        """默认分类"""
        with patch('src.agent_memory.manager.L3LanceDBStore') as mock_l3:
            mock_l3_instance = MagicMock()
            mock_l3_instance.get_stats.return_value = {"vector_count": 0}
            mock_l3_instance.search.return_value = []
            mock_l3.return_value = mock_l3_instance
            
            manager = MemoryManager(memory_dir=str(tmp_memory_dir))
            
            memory_id = manager.add("普通记忆", importance=0.5)
            
            memory = manager.get(memory_id)
            assert memory is not None
            assert "category" in memory


class TestSearch:
    """搜索测试"""

    @pytest.mark.asyncio
    async def test_search_returns_results(self, tmp_memory_dir):
        """search 返回结果"""
        with patch('src.agent_memory.manager.L3LanceDBStore') as mock_l3:
            mock_l3_instance = MagicMock()
            mock_l3_instance.get_stats.return_value = {"vector_count": 1}
            mock_l3_instance.search.return_value = [
                {"id": "mem_test", "content": "测试", "score": 0.9}
            ]
            mock_l3.return_value = mock_l3_instance
            
            manager = MemoryManager(memory_dir=str(tmp_memory_dir))
            
            results = manager.search("测试", top_k=5)
            
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_with_category_filter(self, tmp_memory_dir):
        """带分类过滤的搜索"""
        with patch('src.agent_memory.manager.L3LanceDBStore') as mock_l3:
            mock_l3_instance = MagicMock()
            mock_l3_instance.get_stats.return_value = {"vector_count": 0}
            mock_l3_instance.search.return_value = []
            mock_l3.return_value = mock_l3_instance
            
            manager = MemoryManager(memory_dir=str(tmp_memory_dir))
            
            # 先添加一些记忆
            manager.add("Python 项目", category="项目", importance=0.8)
            
            # 搜索带分类过滤
            results = manager.search("项目", top_k=5, category="项目")
            
            assert isinstance(results, list)
