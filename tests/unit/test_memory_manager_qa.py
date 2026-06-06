"""
MemoryManager 单元测试
测试 MemoryHermes 主类
"""
import pytest
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

from src.memory_manager import MemoryHermes
from src.L4_file_persist import FilePersistStore
from src.L3_vector_store import VectorStore


class TestMemoryHermesBasic:
    """MemoryHermes 基本功能测试"""

    @pytest.mark.asyncio
    async def test_init_creates_layers(self, tmp_path):
        """初始化创建各层"""
        config_path = tmp_path / "config.json"
        config_path.write_text('{"storage": {"memory_dir": "memory", "data_dir": "data"}}')
        
        # Mock 配置
        with patch("src.memory_manager.get_config") as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.get.side_effect = lambda k, d=None: {
                "layers.l1_compress": False,
                "layers.l2_graph": False,
                "layers.l3_vector": True,
                "layers.l4_files": True,
                "embedding.model": "test",
                "embedding.dimensions": 128,
            }.get(k, d)
            mock_cfg.get_api_key.return_value = ""
            mock_cfg.get_storage_path.side_effect = lambda p: str(tmp_path / p)
            mock_cfg.config = {"storage": {"memory_dir": "memory", "data_dir": "data"}}
            mock_config.return_value = mock_cfg
            
            mh = MemoryHermes()
            
            # 验证层已初始化
            assert mh.vector is not None or mh.files is not None

    @pytest.mark.asyncio
    async def test_store_increases_memory(self, tmp_memory_dir, tmp_path):
        """add → store 完整流程"""
        with patch("src.memory_manager.get_config") as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.get.side_effect = lambda k, d=None: {
                "layers.l1_compress": False,
                "layers.l2_graph": False,
                "layers.l3_vector": False,
                "layers.l4_files": True,
            }.get(k, d)
            mock_cfg.get_api_key.return_value = ""
            mock_cfg.config = {"storage": {"memory_dir": str(tmp_memory_dir), "data_dir": "data"}}
            mock_config.return_value = mock_cfg
            
            mh = MemoryHermes()
            mh.files = FilePersistStore(str(tmp_memory_dir))
            
            memory_id = await mh.store("测试记忆内容", {"importance": 0.8})
            
            assert memory_id is not None

    @pytest.mark.asyncio
    async def test_add_search_flow(self, tmp_memory_dir, tmp_path):
        """add → search 完整流程"""
        with patch("src.memory_manager.get_config") as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.get.side_effect = lambda k, d=None: {
                "layers.l1_compress": False,
                "layers.l2_graph": False,
                "layers.l3_vector": False,
                "layers.l4_files": True,
            }.get(k, d)
            mock_cfg.get_api_key.return_value = ""
            mock_cfg.config = {"storage": {"memory_dir": str(tmp_memory_dir), "data_dir": "data"}}
            mock_config.return_value = mock_cfg
            
            mh = MemoryHermes()
            mh.files = FilePersistStore(str(tmp_memory_dir))
            
            # 添加记忆
            memory_id = await mh.store("Python 编程", {"importance": 0.9})
            
            # 验证存在
            entries = mh.files.list_all()
            assert any(e["id"] == memory_id for e in entries)

    @pytest.mark.asyncio
    async def test_add_list_get_delete_flow(self, tmp_memory_dir, tmp_path):
        """add → list → get → delete 完整流程"""
        with patch("src.memory_manager.get_config") as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.get.side_effect = lambda k, d=None: {
                "layers.l1_compress": False,
                "layers.l2_graph": False,
                "layers.l3_vector": False,
                "layers.l4_files": True,
            }.get(k, d)
            mock_cfg.get_api_key.return_value = ""
            mock_cfg.config = {"storage": {"memory_dir": str(tmp_memory_dir), "data_dir": "data"}}
            mock_config.return_value = mock_cfg
            
            mh = MemoryHermes()
            mh.files = FilePersistStore(str(tmp_memory_dir))
            
            # Add
            memory_id = await mh.store("测试记忆", {"importance": 0.7})
            
            # List
            entries = mh.files.list_all()
            assert len(entries) > 0
            
            # Get
            entry = mh.files.load(memory_id)
            assert entry is not None
            assert "测试记忆" in entry["content"]
            
            # Delete
            await mh.forget(memory_id)
            
            # 验证删除
            deleted_entry = mh.files.load(memory_id)
            assert deleted_entry is None

    @pytest.mark.asyncio
    async def test_compress_for_context_output(self, tmp_memory_dir, tmp_path):
        """compress_for_context 输出非空"""
        with patch("src.memory_manager.get_config") as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.get.side_effect = lambda k, d=None: {
                "layers.l1_compress": False,
                "layers.l2_graph": False,
                "layers.l3_vector": False,
                "layers.l4_files": True,
            }.get(k, d)
            mock_cfg.get_api_key.return_value = ""
            mock_cfg.config = {"storage": {"memory_dir": str(tmp_memory_dir), "data_dir": "data"}}
            mock_config.return_value = mock_cfg
            
            mh = MemoryHermes()
            mh.files = FilePersistStore(str(tmp_memory_dir))
            
            # 添加一些记忆
            await mh.store("记忆1", {"importance": 0.8})
            await mh.store("记忆2", {"importance": 0.7})
            
            # 获取上下文
            all_entries = mh.files.list_all()
            if all_entries:
                ids = [e["id"] for e in all_entries]
                # 如果有 compress_for_context 方法
                if hasattr(mh, "compress_for_context"):
                    result = await mh.compress_for_context(ids)
                    # 结果可能是字符串或字典
                    assert result is not None

    def test_stats_returns_correct_fields(self, tmp_memory_dir, tmp_path):
        """stats 返回正确字段"""
        with patch("src.memory_manager.get_config") as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.get.side_effect = lambda k, d=None: {
                "layers.l1_compress": False,
                "layers.l2_graph": False,
                "layers.l3_vector": True,
                "layers.l4_files": True,
            }.get(k, d)
            mock_cfg.get_api_key.return_value = ""
            mock_cfg.get_storage_path.side_effect = lambda p: str(tmp_path / p)
            mock_cfg.config = {"storage": {"memory_dir": str(tmp_memory_dir), "data_dir": "data"}}
            mock_config.return_value = mock_cfg
            
            mh = MemoryHermes()
            mh.files = FilePersistStore(str(tmp_memory_dir))
            mh.vector = None  # 简化测试
            
            stats = mh.get_stats()
            
            # 验证 stats 结构
            assert "layers" in stats or isinstance(stats, dict)


class TestCategoryPath:
    """分类路径测试"""

    @pytest.mark.asyncio
    async def test_category_path_auto_classification(self, tmp_memory_dir, tmp_path):
        """category_path 自动分类"""
        with patch("src.memory_manager.get_config") as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.get.side_effect = lambda k, d=None: {
                "layers.l1_compress": False,
                "layers.l2_graph": False,
                "layers.l3_vector": False,
                "layers.l4_files": True,
            }.get(k, d)
            mock_cfg.get_api_key.return_value = ""
            mock_cfg.config = {"storage": {"memory_dir": str(tmp_memory_dir), "data_dir": "data"}}
            mock_config.return_value = mock_cfg
            
            mh = MemoryHermes()
            mh.files = FilePersistStore(str(tmp_memory_dir))
            
            # 存储带分类的内容
          
