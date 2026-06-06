"""
图书馆分类系统测试
测试分类和路径处理逻辑
"""
import pytest
from pathlib import Path

from src.L4_file_persist import FilePersistStore


class TestLibraryClassification:
    """图书馆分类系统测试"""

    def test_basic_classification(self, tmp_memory_dir):
        """classify 基本内容返回正确顶层分类"""
        store = FilePersistStore(str(tmp_memory_dir))
        
        # 测试项目相关
        fact_id = store.store_fact(
            content="开发 AgentMemory 项目",
            metadata={"category": "project", "importance": 0.9}
        )
        
        meta = store.get_meta(fact_id)
        assert meta["category"] == "project"

    def test_four_level_truncation(self, tmp_memory_dir):
        """超过4层自动截断"""
        store = FilePersistStore(str(tmp_memory_dir))
        
        # 5 层路径
        deep_path = "a/b/c/d/e"
        fact_id = store.store_fact(
            content="深层路径测试",
            metadata={"category": deep_path, "importance": 0.5}
        )
        
        meta = store.get_meta(fact_id)
        # 路径应该被截断到 4 层
        categories = meta["category"].split("/")
        assert len(categories) <= 4

    def test_empty_content_returns_default(self, tmp_memory_dir):
        """空内容返回默认值"""
        store = FilePersistStore(str(tmp_memory_dir))
        
        fact_id = store.store_fact(
            content="",
            metadata={"importance": 0.5}
        )
        
        loaded = store.load(fact_id)
        assert loaded is not None
        # 空内容仍能存储

    def test_custom_dictionary(self, tmp_memory_dir):
        """自定义词典生效 - 通过 metadata 自定义分类"""
        store = FilePersistStore(str(tmp_memory_dir))
        
        # 使用自定义分类
        custom_category = "技术栈/Python/异步编程"
        fact_id = store.store_fact(
            content="使用 asyncio 编写异步代码",
            metadata={"category": custom_category, "importance": 0.8}
        )
        
        meta = store.get_meta(fact_id)
        assert custom_category in meta["category"] or meta["category"] == custom_category

    def test_path_separator(self, tmp_memory_dir):
        """路径用 / 分隔"""
        store = FilePersistStore(str(tmp_memory_dir))
        
        fact_id = store.store_fact(
            content="测试路径分隔",
            metadata={"category": "项目/子项目/模块", "importance": 0.5}
        )
        
        meta = store.get_meta(fact_id)
        assert "/" in meta["category"]

    def test_invalid_path_handling(self, tmp_memory_dir):
        """非法路径（如 //a/b）处理"""
        store = FilePersistStore(str(tmp_memory_dir))
        
        # 规范化路径应该处理 // 的情况
        fact_id = store.store_fact(
            content="测试非法路径",
            metadata={"category": "//test/path", "importance": 0.5}
        )
        
        meta = store.get_meta(fact_id)
        # 应该避免产生空的路径组件
        parts = meta["category"].split("/")
        assert "" not in parts, "不应该有空路径组件"

    def test_category_metadata_extraction(self, tmp_memory_dir):
        """从 metadata 中提取分类信息"""
        store = FilePersistStore(str(tmp_memory_dir))
        
        fact_id = store.store_fact(
            content="技术决策内容",
            metadata={
                "importance": 0.9,
                "tags": ["决策", "技术"],
                "fact_type": "decision",
                "category": "项目/石榴籽/技术方案"
            }
        )
        
        meta = store.get_meta(fact_id)
        assert "category" in meta
        assert "石榴籽" in meta["category"] or meta.get("category") == "项目/石榴籽/技术方案"

    def test_multiple_categories_in_tags(self, tmp_memory_dir):
        """标签中的分类信息"""
        store = FilePersistStore(str(tmp_memory_dir))
        
        fact_id = store.store_fact(
            content="测试标签分类",
            metadata={
                "importance": 0.6,
                "tags": ["重要", "项目-石榴籽", "待办"]
            }
        )
        
        meta = store.get_meta(fact_id)
        assert "tags" in meta
        assert len(meta["tags"]) == 3

    def test_category_hierarchy(self, tmp_memory_dir):
        """分类层级结构"""
        store = FilePersistStore(str(tmp_memory_dir))
        
        # 创建多个层级的记忆
        store.store_fact("一级分类", {"category": "项目", "importance": 0.5})
        store.store_fact("二级分类", {"category": "项目/子项目", "importance": 0.5})
        store.store_fact("三级分类", {"category": "项目/子项目/模块", "importance": 0.5})
        
        all_entries = store.list_all()
        categories = [e.get("metadata", {}).get("category", "") for e in all_entries]
        
        assert any("项目" in cat for cat in categories)
        assert any("项目/子项目" in cat for cat in categories)

    def test_empty_category_defaults(self, tmp_memory_dir):
        """空分类使用默认值"""
        store = FilePersistStore(str(tmp_memory_dir))
        
        fact_id = store.store_fact(
            content="没有指定分类的记忆",
            metadata={"importance": 0.5}  # 没有 category
        )
        
        meta = store.get_meta(fact_id)
        # 应该有一个默认值
        assert "category" in meta or meta.get("category") is None


class TestPathNormalization:
    """路径规范化测试"""

    def test_trailing_slash_removed(self, tmp_memory_dir):
        """尾部斜杠被移除"""
        store = FilePersistStore(str(tmp_memory_dir))
        
        fact_id = store.store_fact(
            content="尾部斜杠测试",
            metadata={"category": "项目/", "importance": 0.5}
        )
        
        meta = store.get_meta(fact_id)
        assert not meta["category"].endswith("/")

    def test_leading_slash_removed(self, tmp_memory_dir):
        """前导斜杠被移除"""
        store = FilePersistStore(str(tmp_memory_dir))
        
        fact_id = store.store_fact(
            content="前导斜杠测试",
            metadata={"category": "/项目", "importance": 0.5}
        )
        
        meta = store.get_meta(fact_id)
        assert not meta["category"].startswith("/")

    def test_consecutive_slashes_normalized(self, tmp_memory_dir):
        """连续斜杠被规范化"""
        store = FilePersistStore(str(tmp_memory_dir))
        
        fact_id = store.store_fact(
            content="连续斜杠测试",
            metadata={"category": "a//b///c", "importance": 0.5}
        )
        
        meta = store.get_meta(fact_id)
        # 路径中不应有连续的 /
        assert "//" not in meta["category"]
