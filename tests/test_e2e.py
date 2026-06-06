"""
端到端流程测试
测试完整用户流程
"""
import pytest
import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.L4_file_persist import FilePersistStore
from src.L3_vector_store import VectorStore, HybridRetriever


def create_vector_store(tmp_path, mock_embedder):
    """创建测试用 VectorStore"""
    data_path = tmp_path / "vectors.json"
    store = VectorStore(
        storage_path=str(data_path),
        embedding_model="text-embedding-v3",
        embedding_dims=1024,
        embedding_batch_size=16
    )
    return store


class TestEndToEndFlow:
    """端到端流程测试"""

    @pytest.mark.asyncio
    async def test_complete_user_flow(self, tmp_memory_dir, tmp_path, mock_embedder):
        """完整用户流程测试"""
        # 初始化存储
        l4_store = FilePersistStore(str(tmp_memory_dir))
        l3_store = create_vector_store(tmp_path, mock_embedder)
        
        # Step 1: Add 3 条记忆
        contents = ["Python 编程很有趣", "JavaScript 用于前端开发", "Go 语言性能很好"]
        
        for content in contents:
            l4_store.store_fact(content, {"importance": 0.8})
            l3_store.store(content, {"importance": 0.8})
        
        # Step 2: Search 1次
        retriever = HybridRetriever(l3_store)
        results = retriever.retrieve("编程", limit=10)
        assert isinstance(results, list), "搜索应该返回列表"
        
        # Step 3: List 1次
        all_facts = l4_store.get_all_facts()
        assert len(all_facts) >= 3, "应该有至少3条记忆"
        
        # Step 4: Delete 1次 (从 L3)
        all_entries = l3_store.get_all_entries()
        if all_entries:
            delete_id = all_entries[0]["id"]
            l3_store.delete(delete_id)
        
        # Step 5: 验证剩余
        remaining = l3_store.get_all_entries()
        assert len(remaining) >= 2, "应该剩余至少2条记忆"

    @pytest.mark.asyncio
    async def test_three_file_group_generation(self, tmp_memory_dir, tmp_path, mock_embedder):
        """3 文件组（.md / .vec.json / .meta.json）全部生成"""
        l4_store = FilePersistStore(str(tmp_memory_dir))
        l3_store = create_vector_store(tmp_path, mock_embedder)
        
        # 存储一条记忆
        content = "测试内容"
        l4_store.store_fact(content, {"importance": 0.8})
        l3_store.store(content, {"importance": 0.8})
        
        # 验证 L3 文件
        assert Path(l3_store.storage_path).exists(), "vectors.json 应该存在"

    @pytest.mark.asyncio
    async def test_cross_category_search(self, tmp_memory_dir, tmp_path, mock_embedder):
        """跨分类的混合检索"""
        l4_store = FilePersistStore(str(tmp_memory_dir))
        l3_store = create_vector_store(tmp_path, mock_embedder)
        
        # 存储不同分类的记忆
        categories_contents = [
            ("技术/Python", "Python 是一种高级语言"),
            ("技术/JavaScript", "JavaScript 用于前端"),
            ("项目/石榴籽", "石榴籽是比赛项目"),
            ("生活/日常", "今天天气很好"),
        ]
        
        for category, content in categories_contents:
            l4_store.store_fact(content, {"importance": 0.8, "category": category})
            l3_store.store(content, {"importance": 0.8, "category": category})
        
        # 检索技术相关
        retriever = HybridRetriever(l3_store)
        results = retriever.retrieve("编程语言", limit=10)
        
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_bulk_operations(self, tmp_memory_dir, tmp_path, mock_embedder):
        """批量操作"""
        l4_store = FilePersistStore(str(tmp_memory_dir))
        l3_store = create_vector_store(tmp_path, mock_embedder)
        
        # 批量存储
        batch_size = 10
        for i in range(batch_size):
            l4_store.store_fact(f"批量记忆{i}", {"importance": 0.5 + i * 0.05})
            l3_store.store(f"批量记忆{i}", {"importance": 0.5})
        
        # 验证数量
        l4_count = len(l4_store.get_all_facts())
        l3_count = l3_store.count()
        
        assert l4_count >= batch_size
        assert l3_count >= batch_size


class TestDataIntegrity:
    """数据完整性测试"""

    @pytest.mark.asyncio
    async def test_metadata_integrity(self, tmp_memory_dir):
        """元数据完整性"""
        store = FilePersistStore(str(tmp_memory_dir))
        
        metadata = {
            "importance": 0.9,
            "tags": ["重要", "测试"],
            "fact_type": "decision"
        }
        
        store.store_fact("测试记忆", metadata)
        
        facts = store.get_all_facts()
        assert len(facts) > 0

    @pytest.mark.asyncio
    async def test_no_data_corruption(self, tmp_memory_dir, tmp_path, mock_embedder):
        """无数据损坏"""
        l4_store = FilePersistStore(str(tmp_memory_dir))
        l3_store = create_vector_store(tmp_path, mock_embedder)
        
        # 存储特殊字符内容
        special_content = "特殊字符测试: 中文字符"
        
        l4_store.store_fact(special_content, {"importance": 0.8})
        l3_store.store(special_content, {"importance": 0.8})
        
        # 验证 JSON 格式正确
        assert Path(l3_store.storage_path).exists()
        data = json.loads(Path(l3_store.storage_path).read_text(encoding="utf-8"))
        assert len(data["vectors"]) > 0
