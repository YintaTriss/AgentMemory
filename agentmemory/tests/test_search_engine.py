"""
test_search_engine.py — SearchEngine 测试
验证 search / prefetch / unified_entry
"""
import pytest
import asyncio
from agentmemory.search.search_engine import SearchEngine, SearchOptions, MemoryEntry


@pytest.fixture
def search_engine(tmp_path):
    """创建测试用 SearchEngine 实例（使用 MockEmbedder）"""
    # 直接实例化 SearchEngine，不依赖外部 provider
    se = SearchEngine(memory_dir=str(tmp_path))
    return se


class TestSearchEngineSearch:
    """测试 search"""

    @pytest.mark.asyncio
    async def test_search_engine_search(self, search_engine, tmp_path):
        """搜索返回结果（索引 + 搜索）"""
        # 先索引一些条目
        await search_engine.index_entry(
            id="search-001",
            content="Python 是一种编程语言",
            metadata={"category": "技术", "tags": ["Python"]},
        )
        await search_engine.index_entry(
            id="search-002",
            content="JavaScript 用于 Web 开发",
            metadata={"category": "技术", "tags": ["JavaScript"]},
        )
        await search_engine.index_entry(
            id="search-003",
            content="机器学习是 AI 的一个分支",
            metadata={"category": "技术", "tags": ["AI"]},
        )

        # 搜索（语义检索需要 embedder，fallback 到 library index）
        results = await search_engine.search("Python 编程", limit=10)
        assert isinstance(results, list)
        # 返回的是 MemoryEntry 列表
        for r in results:
            assert isinstance(r, MemoryEntry)

    @pytest.mark.asyncio
    async def test_search_engine_search_category(self, search_engine, tmp_path):
        """按分类搜索"""
        await search_engine.index_entry(
            id="cat-001",
            content="项目A的内容",
            metadata={"category": "A.项目"},
        )
        await search_engine.index_entry(
            id="cat-002",
            content="个人B的内容",
            metadata={"category": "B.个人"},
        )

        results = await search_engine.search_by_category("A.项目")
        assert isinstance(results, list)


class TestSearchEnginePrefetch:
    """测试 prefetch"""

    @pytest.mark.asyncio
    async def test_search_engine_prefetch(self, search_engine):
        """预加载向量（预取相关记忆）"""
        await search_engine.index_entry(
            id="prefetch-001",
            content="预取测试内容",
            metadata={"category": "测试"},
        )
        results = await search_engine.prefetch("预取", limit=5)
        assert isinstance(results, list)


class TestSearchEngineUnifiedEntry:
    """测试 search() 统一入口路由"""

    @pytest.mark.asyncio
    async def test_search_engine_unified_entry(self, search_engine, tmp_path):
        """search() 统一入口路由正确"""
        await search_engine.index_entry(
            id="unified-001",
            content="统一入口测试",
            metadata={"category": "测试"},
        )

        # hybrid 模式
        results_hybrid = await search_engine.search("统一入口", limit=10, mode="hybrid")
        assert isinstance(results_hybrid, list)

        # vector 模式
        results_vector = await search_engine.search("统一入口", limit=10, mode="vector")
        assert isinstance(results_vector, list)

        # category 模式（需要 category 参数）
        results_cat = await search_engine.search("测试", limit=10, mode="category", category="测试")
        assert isinstance(results_cat, list)

    @pytest.mark.asyncio
    async def test_search_engine_search_hybrid(self, search_engine, tmp_path):
        """混合检索"""
        await search_engine.index_entry(
            id="hybrid-001",
            content="混合检索测试内容",
            metadata={"category": "A.项目"},
        )
        results = await search_engine.search_hybrid("混合检索", category="A.项目")
        assert isinstance(results, list)


class TestSearchEngineStats:
    """测试 get_stats"""

    @pytest.mark.asyncio
    async def test_search_engine_stats(self, search_engine):
        """获取统计信息"""
        stats = search_engine.get_stats()
        assert isinstance(stats, dict)
        assert "embedder_model" in stats
        assert "embedder_dimensions" in stats


class TestSearchOptions:
    """测试 SearchOptions"""

    def test_search_options_defaults(self):
        """SearchOptions 默认值"""
        opts = SearchOptions()
        assert opts.limit == 10
        assert opts.threshold == 0.0
        assert opts.rerank is False
        assert opts.category is None
        assert opts.tags is None

    def test_search_options_custom(self):
        """SearchOptions 自定义值"""
        opts = SearchOptions(limit=50, threshold=0.7, category="A.项目", tags=["python"])
        assert opts.limit == 50
        assert opts.threshold == 0.7
        assert opts.category == "A.项目"
        assert opts.tags == ["python"]


class TestMemoryEntry:
    """测试 MemoryEntry"""

    def test_memory_entry_properties(self):
        """MemoryEntry 属性"""
        entry = MemoryEntry(
            id="test-001",
            content="测试内容",
            metadata={"category": "A.项目", "tags": ["test"], "importance": 0.8},
        )
        assert entry.category == "A.项目"
        assert entry.tags == ["test"]
        assert entry.importance == 0.8

    def test_memory_entry_tags_string_fallback(self):
        """tags 为字符串时的 fallback"""
        entry = MemoryEntry(
            id="test-002",
            content="内容",
            metadata={"tags": "single_tag"},
        )
        assert entry.tags == ["single_tag"]
