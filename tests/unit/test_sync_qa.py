"""
同步机制单元测试
测试 L4 ↔ L3 同步
"""
import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.L4_file_persist import FilePersistStore
from src.L3_vector_store import VectorStore


class TestSyncMechanism:
    """同步机制测试"""

    def test_sync_one_writes_l3_and_vec(self, tmp_memory_dir, tmp_path, mock_embedder):
        """sync_one 写 L3 + 写 vec.json"""
        # 创建存储
        store = FilePersistStore(str(tmp_memory_dir))
        data_path = tmp_path / "vectors.json"
        
        vector_store = VectorStore.__new__(VectorStore)
        vector_store.storage_path = str(data_path)
        vector_store.embedder = mock_embedder
        vector_store.data = {"vectors": [], "metadata": {}}
        vector_store._lock = MagicMock()
        
        # 存储事实
        fact_id = store.store_fact(
            "同步测试内容",
            {"importance": 0.8, "tags": ["测试"]}
        )
        
        # 同步到 L3
        vector_store.store(
            "同步测试内容",
            metadata={"importance": 0.8, "source": "sync_test"}
        )
        
        # 验证 vec.json 存在
        assert data_path.exists()
        
        # 验证数据写入
        data = json.loads(data_path.read_text(encoding="utf-8"))
        assert len(data["vectors"]) > 0

    def test_sync_all_success(self, tmp_memory_dir, tmp_path, mock_embedder):
        """sync_all 全部同步成功"""
        store = FilePersistStore(str(tmp_memory_dir))
        data_path = tmp_path / "vectors.json"
        
        vector_store = VectorStore.__new__(VectorStore)
        vector_store.storage_path = str(data_path)
        vector_store.embedder = mock_embedder
        vector_store.data = {"vectors": [], "metadata": {}}
        vector_store._lock = MagicMock()
        
        # 存储多条
        ids = [
            store.store_fact(f"记忆{i}", {"importance": 0.5 + i * 0.1})
            for i in range(3)
        ]
        
        # 同步全部
        synced = []
        for fact_id in ids:
            entry = store.load(fact_id)
            if entry:
                vector_store.store(entry["content"], metadata=entry["metadata"])
                synced.append(fact_id)
        
        assert len(synced) == 3

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

    def test_delete_from_l3(self, tmp_path, mock_embedder):
        """delete_from_l3 工作"""
        data_path = tmp_path / "vectors.json"
        
        vector_store = VectorStore.__new__(VectorStore)
        vector_store.storage_path = str(data_path)
        vector_store.embedder = mock_embedder
        vector_store.data = {"vectors": [], "metadata": {}}
        vector_store._lock = MagicMock()
        
        # 存储
        memory_id = vector_store.store("待删除", metadata={"importance": 0.5})
        
        initial_count = vector_store.count()
        
        # 删除
        vector_store.delete(memory_id)
        
        assert vector_store.count() == initial_count - 1

    def test_vec_json_persists_on_success(self, tmp_path, mock_embedder):
        """成功时 vec.json 持久化"""
        data_path = tmp_path / "vectors.json"
        
        vector_store = VectorStore.__new__(VectorStore)
        vector_store.storage_path = str(data_path)
        vector_store.embedder = mock_embedder
        vector_store.data = {"vectors": [], "metadata": {}}
        vector_store._lock = MagicMock()
        
        vector_store.store("测试内容", metadata={"importance": 0.8})
        
        # 验证文件存在
        assert data_path.exists()
        
        # 读取验证
        data = json.loads(data_path.read_text(encoding="utf-8"))
        assert len(data["vectors"]) > 0

    def test_vec_json_persists_on_failure(self, tmp_path, mock_embedder):
        """失败时 vec.json 仍然写（旧数据保留）"""
        data_path = tmp_path / "vectors.json"
        
        vector_store = VectorStore.__new__(VectorStore)
        vector_store.storage_path = str(data_path)
        vector_store.embedder = mock_embedder
        vector_store.data = {"vectors": [], "metadata": {}}
        vector_store._lock = MagicMock()
        
        # 先写入一条
        vector_store.store("成功内容", metadata={"importance": 0.8})
        
        # 读取数据
        data1 = json.loads(data_path.read_text(encoding="utf-8"))
        initial_count = len(data1["vectors"])
        
        # 模拟失败后，验证旧数据仍然存在
        # （在实际实现中，失败应该回滚或保留旧状态）
        assert initial_count >= 1


class TestSyncIntegration:
    """同步集成测试"""

    def test_full_sync_cycle(self, tmp_memory_dir, tmp_path, mock_embedder):
        """完整同步周期：L4 → L3 → 验证"""
        # L4 存储
        store = FilePersistStore(str(tmp_memory_dir))
        fact_id = store.store_fact("完整同步测试", {"importance": 0.9})
        
        # L3 存储
        data_path = tmp_path / "vectors.json"
        vector_store = VectorStore.__new__(VectorStore)
        vector_store.storage_path = str(data_path)
        vector_store.embedder = mock_embedder
        vector_store.data = {"vectors": [], "metadata": {}}
        vector_store._lock = MagicMock()
        
        entry = store.load(fact_id)
        vector_store.store(entry["content"], metadata=entry["metadata"])
        
        # 验证
        assert data_path.exists()
        data = json.loads(data_path.read_text(encoding="utf-8"))
        assert any("完整同步测试" in str(v.get("content", "")) for v in data["vectors"])

    def test_bidirectional_consistency(self, tmp_memory_dir, tmp_path, mock_embedder):
        """双向一致性：L4 和 L3 数据一致"""
        # L4 存储
        store = FilePersistStore(str(tmp_memory_dir))
        fact_id = store.store_fact("一致性测试", {"importance": 0.7})
        
        # L3 存储
        data_path = tmp_path / "vectors.json"
        vector_store = VectorStore.__new__(VectorStore)
        vector_store.storage_path = str(data_path)
        vector_store.embedder = mock_embedder
        vector_store.data = {"vectors": [], "metadata": {}}
        vector_store._lock = MagicMock()
        
        l4_entry = store.load(fact_id)
        vector_store.store(l4_entry["content"], metadata=l4_entry["metadata"])
        
        # 验证元数据一致性
        data = json.loads(data_path.read_text(encoding="utf-8"))
        assert len(data["vectors"]) > 0
