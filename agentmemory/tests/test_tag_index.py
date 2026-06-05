"""
test_tag_index.py — TagIndex 标签索引测试
验证 add/remove/query/save/load
"""
import pytest
import asyncio
from agentmemory.data.tag_index import TagIndex


@pytest.fixture
def tag_index(tmp_path):
    """创建测试用 TagIndex 实例"""
    ti = TagIndex(root_dir=str(tmp_path))
    return ti


class TestTagIndexAddRemove:
    """测试添加和移除标签"""

    @pytest.mark.asyncio
    async def test_tag_index_add_remove(self, tag_index):
        """添加标签，移除标签"""
        await tag_index.init()
        await tag_index.add_tag("python", "mem-001", "A.项目")
        await tag_index.add_tag("python", "mem-002", "A.项目")
        await tag_index.add_tag("java", "mem-003", "B.个人")

        # 查询 python 标签
        result = await tag_index.get_by_tag("python")
        assert len(result) == 2
        mem_ids = [mid for mid, _ in result]
        assert "mem-001" in mem_ids
        assert "mem-002" in mem_ids

        # 移除标签
        await tag_index.remove_tag("python", "mem-001")
        result_after = await tag_index.get_by_tag("python")
        mem_ids_after = [mid for mid, _ in result_after]
        assert "mem-001" not in mem_ids_after
        assert "mem-002" in mem_ids_after

    @pytest.mark.asyncio
    async def test_tag_index_add_tags(self, tag_index):
        """批量添加标签"""
        await tag_index.init()
        await tag_index.add_tags(["AI", "机器学习", "Python"], "mem-100", "A.项目")
        assert "AI" in await tag_index.get_all_tags()
        assert "机器学习" in await tag_index.get_all_tags()
        assert "Python" in await tag_index.get_all_tags()


class TestTagIndexQuery:
    """测试按标签查询"""

    @pytest.mark.asyncio
    async def test_tag_index_query(self, tag_index):
        """按标签查询"""
        await tag_index.init()
        await tag_index.add_tag("query-test", "mem-q1", "A.项目")
        await tag_index.add_tag("query-test", "mem-q2", "B.个人")

        results = await tag_index.query("query-test")
        assert isinstance(results, list)
        assert "mem-q1" in results
        assert "mem-q2" in results

    @pytest.mark.asyncio
    async def test_tag_index_query_wildcard(self, tag_index):
        """通配符查询"""
        await tag_index.init()
        await tag_index.add_tag("python-v3", "mem-py1", "A")
        await tag_index.add_tag("python-v4", "mem-py2", "A")
        await tag_index.add_tag("java-v8", "mem-ja1", "B")

        results = await tag_index.query("python*")
        assert "mem-py1" in results
        assert "mem-py2" in results
        assert "mem-ja1" not in results

    @pytest.mark.asyncio
    async def test_tag_index_search_tags(self, tag_index):
        """前缀搜索标签"""
        await tag_index.init()
        await tag_index.add_tag("python", "mem-1", "A")
        await tag_index.add_tag("pytest", "mem-2", "A")
        await tag_index.add_tag("java", "mem-3", "A")

        results = await tag_index.search_tags("py")
        assert "python" in results
        assert "pytest" in results
        assert "java" not in results


class TestTagIndexSaveLoad:
    """测试持久化保存和加载"""

    @pytest.mark.asyncio
    async def test_tag_index_save_load(self, tag_index, tmp_path):
        """持久化保存和加载"""
        # 写入一些数据
        await tag_index.init()
        await tag_index.add_tag("persist-test", "mem-p1", "A.项目")
        await tag_index.add_tag("persist-test", "mem-p2", "A.项目")
        await tag_index.add_tag("another", "mem-p3", "B.个人")

        # 再创建一个新的 TagIndex 实例指向同一目录
        tag_index2 = TagIndex(root_dir=str(tmp_path))
        await tag_index2.load()  # 或 init() 会加载

        # 验证数据已持久化
        all_tags = await tag_index2.get_all_tags()
        assert "persist-test" in all_tags
        assert "another" in all_tags

        results = await tag_index2.get_by_tag("persist-test")
        mem_ids = [mid for mid, _ in results]
        assert "mem-p1" in mem_ids
        assert "mem-p2" in mem_ids

    @pytest.mark.asyncio
    async def test_tag_index_remove_memory(self, tag_index):
        """删除记忆时清理所有标签"""
        await tag_index.init()
        await tag_index.add_tags(["tag1", "tag2", "tag3"], "mem-to-remove", "A.项目")
        await tag_index.remove_memory("mem-to-remove")

        for tag in ["tag1", "tag2", "tag3"]:
            result = await tag_index.get_by_tag(tag)
            mem_ids = [mid for mid, _ in result]
            assert "mem-to-remove" not in mem_ids


class TestTagIndexStats:
    """测试标签统计"""

    @pytest.mark.asyncio
    async def test_tag_index_get_tag_stats(self, tag_index):
        """获取标签统计"""
        await tag_index.init()
        await tag_index.add_tag("stats-test", "mem-s1", "A")
        await tag_index.add_tag("stats-test", "mem-s2", "A")
        await tag_index.add_tag("stats-test", "mem-s3", "B")

        stats = await tag_index.get_tag_stats("stats-test")
        assert stats is not None
        assert stats.count == 3
        assert "A" in stats.categories
        assert "B" in stats.categories

    @pytest.mark.asyncio
    async def test_tag_index_get_tags_for_memory(self, tag_index):
        """获取记忆的所有标签"""
        await tag_index.init()
        await tag_index.add_tags(["tagA", "tagB", "tagC"], "mem-multi", "A")
        tags = await tag_index.get_tags_for_memory("mem-multi")
        assert set(tags) == {"tagA", "tagB", "tagC"}
