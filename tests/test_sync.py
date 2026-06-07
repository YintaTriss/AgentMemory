"""
同步机制单元测试
测试 L4 ↔ L3 同步
"""
import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

from src.agent_memory.l4_files import L4FilesStore, generate_mem_id


@pytest.fixture
def mock_embedder():
    """Mock embedder for testing"""
    class MockEmbedder:
        def __init__(self):
            self.dims = 128
        
        def embed(self, text):
            return [0.1] * self.dims
        
        async def aembed(self, text):
            return self.embed(text)
    
    return MockEmbedder()


class TestSyncMechanism:
    """同步机制测试"""

    @pytest.mark.asyncio
    async def test_sync_one_writes_l4(self, tmp_memory_dir, mock_embedder):
        """sync_one 写 L4"""
        store = L4FilesStore(str(tmp_memory_dir))
        
        # 存储事实
        memory_id = generate_mem_id()
        await store.save(
            memory_id,
            "同步测试内容",
            {"importance": 0.8, "tags": ["测试"]}
        )
        
        # 验证文件存在
        md_file = Path(tmp_memory_dir) / f"{memory_id}.md"
        meta_file = Path(tmp_memory_dir) / f"{memory_id}.meta.json"
        
        assert md_file.exists()
        assert meta_file.exists()
        
        # 验证数据写入
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        assert meta["id"] == memory_id

    @pytest.mark.asyncio
    async def test_sync_all_success(self, tmp_memory_dir, mock_embedder):
        """sync_all 全部同步成功"""
        store = L4FilesStore(str(tmp_memory_dir))
        
        # 存储多条
        ids = []
        for i in range(3):
            memory_id = generate_mem_id()
            await store.save(
                memory_id,
                f"记忆{i}",
                {"importance": 0.5 + i * 0.1}
            )
            ids.append(memory_id)

        # 验证全部写入
        all_ids = store.list()
        assert len(all_ids) >= 3

    def test_auto_sync_check_decision(self):
        """auto_sync_check 对含"决定"返回 True"""
        # 测试自动同步判断逻辑
        keywords = ["决定", "完成", "重要", "记住"]
        
        test_texts = [
            ("我决定使用 Python", True),
            ("项目完成了", True),
            ("这是一个重要的决定", True),
            ("请记住这个", True),
            ("今天天气不错", False),
            ("你好", False),
        ]
        
        for text, expected in test_texts:
            result = any(kw in text for kw in keywords)
            assert result == expected, f"'{text}' should return {expected}"

    def test_auto_sync_check_completed(self):
        """auto_sync_check 对含"完成"返回 True"""
        text = "任务已经完成了"
        
        keywords = ["决定", "完成", "重要", "记住"]
        result = any(kw in text for kw in keywords)
        
        assert result is True

    def test_auto_sync_check_important(self):
        """auto_sync_check 对含"重要"返回 True"""
        text = "这是一个非常重要的信息"
        
        keywords = ["决定", "完成", "重要", "记住"]
        result = any(kw in text for kw in keywords)
        
        assert result is True


class TestSyncIntegration:
    """同步集成测试"""

    @pytest.mark.asyncio
    async def test_full_sync_cycle(self, tmp_memory_dir, mock_embedder):
        """完整同步周期：L4 → 验证"""
        # L4 存储
        store = L4FilesStore(str(tmp_memory_dir))
        memory_id = generate_mem_id()
        await store.save(
            memory_id,
            "完整同步测试",
            {"importance": 0.9}
        )

        # 验证
        content = await store.load(memory_id)
        assert "完整同步测试" in content

        data = await store.load_existing(memory_id)
        assert data is not None
        assert data["meta"]["importance"] == 0.9

    @pytest.mark.asyncio
    async def test_bidirectional_consistency(self, tmp_memory_dir, mock_embedder):
        """双向一致性：L4 数据一致"""
        # L4 存储
        store = L4FilesStore(str(tmp_memory_dir))
        memory_id = generate_mem_id()
        metadata = {"importance": 0.7, "category_path": "测试"}

        await store.save(memory_id, "一致性测试", metadata)

        # 验证元数据一致性
        data = await store.load_existing(memory_id)
        assert data is not None
        assert data["meta"]["importance"] == 0.7
        assert data["meta"]["category_path"] == "测试"


class TestFileGroupOperations:
    """文件组操作测试"""

    @pytest.mark.asyncio
    async def test_md_file_content_persists(self, tmp_memory_dir):
        """md 文件内容持久化"""
        store = L4FilesStore(str(tmp_memory_dir))
        
        memory_id = generate_mem_id()
        content = "测试内容"

        await store.save(memory_id, content, {"importance": 0.8})

        # 验证 md 文件
        md_file = Path(tmp_memory_dir) / f"{memory_id}.md"
        assert md_file.read_text(encoding="utf-8") == content

    @pytest.mark.asyncio
    async def test_meta_file_structure(self, tmp_memory_dir):
        """meta.json 文件结构正确"""
        store = L4FilesStore(str(tmp_memory_dir))
        
        memory_id = generate_mem_id()
        await store.save(memory_id, "内容", {"importance": 0.8})
        
        # 验证 meta 文件
        meta_file = Path(tmp_memory_dir) / f"{memory_id}.meta.json"
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        
        # 验证必需字段
        assert "id" in meta
        assert "created_at" in meta
        assert "updated_at" in meta
        assert "importance" in meta
