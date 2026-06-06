"""
Embedder 单元测试
测试 VectorStore 的嵌入功能
"""
import pytest
from unittest.mock import MagicMock, patch

from src.L3_vector_store import VectorStore


def create_test_store(tmp_path, mock_embedder):
    """创建测试用 VectorStore"""
    data_path = tmp_path / "vectors.json"
    store = VectorStore(
        storage_path=str(data_path),
        embedding_model="text-embedding-v3",
        embedding_dims=1024,
        embedding_batch_size=16
    )
    return store


class TestVectorStoreEmbedding:
    """VectorStore 嵌入功能测试"""

    def test_embed_single_method_exists(self, tmp_path, mock_embedder):
        """_embed_single 方法存在"""
        store = create_test_store(tmp_path, mock_embedder)
        
        assert hasattr(store, "_embed_single")

    def test_embed_batch_method_exists(self, tmp_path, mock_embedder):
        """_embed_batch 方法存在"""
        store = create_test_store(tmp_path, mock_embedder)
        
        assert hasattr(store, "_embed_batch")

    def test_embedding_dims_config(self, tmp_path):
        """embedding_dims 配置正确"""
        store = create_test_store(tmp_path, MagicMock())
        
        assert store.embedding_dims == 1024

    def test_embedding_model_config(self, tmp_path):
        """embedding_model 配置正确"""
        store = create_test_store(tmp_path, MagicMock())
        
        assert store.embedding_model == "text-embedding-v3"


class TestMockEmbedding:
    """Mock 嵌入测试"""

    def test_mock_embedder_returns_vector(self, tmp_path, mock_embedder):
        """Mock embedder 返回向量"""
        vec = mock_embedder.embed("测试文本")
        
        assert len(vec) == 1024
        assert all(isinstance(x, (int, float)) for x in vec)

    def test_mock_embed_batch(self, tmp_path, mock_embedder):
        """Mock 批量嵌入"""
        texts = ["文本1", "文本2", "文本3"]
        
        vecs = mock_embedder.embed_batch(texts)
        
        assert len(vecs) == 3
        assert all(len(v) == 1024 for v in vecs)


class TestEmbeddingIntegration:
    """嵌入集成测试"""

    def test_store_uses_embedding(self, tmp_path, mock_embedder):
        """VectorStore.store 使用嵌入"""
        store = create_test_store(tmp_path, mock_embedder)
        
        # store 应该调用 embed
        memory_id = store.store("测试内容", metadata={"importance": 0.8})
        
        # 验证 embed 被调用
        mock_embedder.embed.assert_called()

    def test_batch_embedding_consistency(self, tmp_path, mock_embedder):
        """批量嵌入一致性"""
        store = create_test_store(tmp_path, mock_embedder)
        
        # 存储多条
        store.store("内容1", metadata={"importance": 0.5})
        store.store("内容2", metadata={"importance": 0.5})
        
        # 验证多次调用
        assert mock_embedder.embed.call_count >= 2
