"""
test_tag_graph.py — TagCooccurrenceGraph 测试
验证 add_memory_tags / get_neighbors / suggest_tags / get_communities / persist
"""

import pytest
import asyncio
from pathlib import Path

from agentmemory.knowledge.tag_graph import TagCooccurrenceGraph


# Helper to get correct edge key
def edge_key(a: str, b: str) -> tuple:
    return (min(a, b), max(a, b))


@pytest.fixture
def graph(tmp_path):
    """创建测试用 TagCooccurrenceGraph 实例"""
    g = TagCooccurrenceGraph(storage_path=tmp_path)
    return g


class TestTagGraphBasics:
    """测试基础操作"""

    @pytest.mark.asyncio
    async def test_add_memory_tags(self, graph):
        """添加记忆标签，更新图谱节点和边"""
        await graph.add_memory_tags("mem_001", ["石榴籽", "省赛", "答辩"])
        await graph.add_memory_tags("mem_002", ["石榴籽", "语料"])

        # 验证节点
        assert graph.nodes["石榴籽"].frequency == 2
        assert graph.nodes["省赛"].frequency == 1
        assert graph.nodes["答辩"].frequency == 1
        assert graph.nodes["语料"].frequency == 1

        # 验证边存在（字典序）
        ek = edge_key("石榴籽", "省赛")
        assert ek in graph.edges
        assert graph.edges[ek].co_count == 1
        assert graph.edges[ek].weight > 0

    @pytest.mark.asyncio
    async def test_add_same_memory_twice(self, graph):
        """同一 memory_id 添加两次，频率应该增加"""
        await graph.add_memory_tags("mem_001", ["A", "B"])
        await graph.add_memory_tags("mem_001", ["A", "B"])

        assert graph.nodes["A"].frequency == 2
        assert graph.nodes["B"].frequency == 2
        # 同一条记忆内部共现只算一次
        assert graph.edges[edge_key("A", "B")].co_count == 1

    @pytest.mark.asyncio
    async def test_remove_memory_tags(self, graph):
        """删除记忆标签，减少计数"""
        await graph.add_memory_tags("mem_001", ["石榴籽", "省赛"])
        await graph.add_memory_tags("mem_002", ["石榴籽", "语料"])

        await graph.remove_memory_tags("mem_001", ["石榴籽", "省赛"])

        assert graph.nodes["石榴籽"].frequency == 1
        assert graph.nodes["省赛"].frequency == 0
        assert "省赛" not in graph.nodes
        # 石榴籽-省赛 边应该被删除
        assert edge_key("石榴籽", "省赛") not in graph.edges

    @pytest.mark.asyncio
    async def test_empty_tags(self, graph):
        """空标签列表不应报错"""
        await graph.add_memory_tags("mem_001", [])
        assert len(graph.nodes) == 0

    @pytest.mark.asyncio
    async def test_single_tag(self, graph):
        """单标签记忆"""
        await graph.add_memory_tags("mem_001", ["独狼"])

        assert graph.nodes["独狼"].frequency == 1
        assert len(graph.edges) == 0


class TestGetNeighbors:
    """测试 get_neighbors"""

    @pytest.mark.asyncio
    async def test_get_neighbors(self, graph):
        """验证共现邻居排序"""
        await graph.add_memory_tags("mem_001", ["石榴籽", "省赛"])
        await graph.add_memory_tags("mem_002", ["石榴籽", "语料"])
        await graph.add_memory_tags("mem_003", ["石榴籽", "答辩"])

        neighbors = await graph.get_neighbors("石榴籽", top_k=3)

        assert len(neighbors) == 3
        tags = [t for t, _ in neighbors]
        weights = [w for _, w in neighbors]

        assert "省赛" in tags
        assert "语料" in tags
        assert "答辩" in tags
        # 验证按 weight 降序排列
        assert weights == sorted(weights, reverse=True)

    @pytest.mark.asyncio
    async def test_get_neighbors_top_k(self, graph):
        """验证 top_k 限制"""
        await graph.add_memory_tags("mem_001", ["A", "B"])
        await graph.add_memory_tags("mem_002", ["A", "C"])
        await graph.add_memory_tags("mem_003", ["A", "D"])
        await graph.add_memory_tags("mem_004", ["A", "E"])

        neighbors = await graph.get_neighbors("A", top_k=2)
        assert len(neighbors) == 2

    @pytest.mark.asyncio
    async def test_get_neighbors_no_neighbors(self, graph):
        """孤立的 tag 没有邻居"""
        await graph.add_memory_tags("mem_001", ["A", "B"])
        neighbors = await graph.get_neighbors("C")
        assert neighbors == []


class TestSuggestTags:
    """测试 suggest_tags"""

    @pytest.mark.asyncio
    async def test_suggest_tags(self, graph):
        """验证推荐共现标签"""
        await graph.add_memory_tags("mem_001", ["石榴籽", "省赛"])
        await graph.add_memory_tags("mem_002", ["石榴籽", "语料"])
        await graph.add_memory_tags("mem_003", ["石榴籽", "答辩"])

        suggestions = await graph.suggest_tags(["省赛"], top_k=2)
        assert len(suggestions) >= 1
        suggested_tags = [t for t, _ in suggestions]
        assert "石榴籽" in suggested_tags

    @pytest.mark.asyncio
    async def test_suggest_tags_excludes_input(self, graph):
        """推荐结果不包含输入标签本身"""
        await graph.add_memory_tags("mem_001", ["A", "B", "C"])

        suggestions = await graph.suggest_tags(["A"], top_k=5)
        suggested_tags = [t for t, _ in suggestions]
        assert "A" not in suggested_tags

    @pytest.mark.asyncio
    async def test_suggest_tags_multiple_inputs(self, graph):
        """多标签输入聚合推荐"""
        await graph.add_memory_tags("mem_001", ["A", "B"])
        await graph.add_memory_tags("mem_002", ["A", "C"])
        await graph.add_memory_tags("mem_003", ["B", "C"])

        suggestions = await graph.suggest_tags(["A", "B"], top_k=3)
        suggested_tags = [t for t, _ in suggestions]
        # C 和 A、B 都共现过，应该被推荐
        assert "C" in suggested_tags

    @pytest.mark.asyncio
    async def test_suggest_tags_empty_graph(self, graph):
        """空图谱无推荐"""
        suggestions = await graph.suggest_tags(["未知"], top_k=3)
        assert suggestions == []


class TestCommunityDiscovery:
    """测试社区发现"""

    @pytest.mark.asyncio
    async def test_community_discovery(self, graph):
        """验证发现多个独立的 Tag 群组"""
        # 群组1: A-B-C
        await graph.add_memory_tags("mem_001", ["A", "B", "C"])
        await graph.add_memory_tags("mem_002", ["A", "B"])
        # 群组2: X-Y-Z
        await graph.add_memory_tags("mem_003", ["X", "Y", "Z"])
        await graph.add_memory_tags("mem_004", ["X", "Y"])

        communities = await graph.get_communities(weight_threshold=0.3)

        # 至少两个群组
        assert len(communities) >= 2
        # 验证群组内的 tag 确实在一起
        all_tags = [tag for community in communities for tag in community]
        assert set(all_tags) == {"A", "B", "C", "X", "Y", "Z"}

    @pytest.mark.asyncio
    async def test_community_single_group(self, graph):
        """所有 tag 属于同一群组"""
        await graph.add_memory_tags("mem_001", ["A", "B", "C"])

        communities = await graph.get_communities()
        assert len(communities) == 1

    @pytest.mark.asyncio
    async def test_community_threshold(self, graph):
        """阈值过滤"""
        await graph.add_memory_tags("mem_001", ["A", "B", "C"])

        communities_low = await graph.get_communities(weight_threshold=0.1)
        communities_high = await graph.get_communities(weight_threshold=0.9)

        # 低阈值可能产生群组，高阈值可能没有
        assert len(communities_low) >= len(communities_high)


class TestSearchByCooccurrence:
    """测试 search_by_cooccurrence"""

    @pytest.mark.asyncio
    async def test_search_depth_0(self, graph):
        """depth=0 只返回种子"""
        await graph.add_memory_tags("mem_001", ["A", "B", "C"])
        result = await graph.search_by_cooccurrence(["A"], depth=0)
        assert result == ["A"]

    @pytest.mark.asyncio
    async def test_search_depth_1(self, graph):
        """depth=1 返回种子和直接邻居"""
        await graph.add_memory_tags("mem_001", ["A", "B"])
        await graph.add_memory_tags("mem_002", ["A", "C"])

        result = await graph.search_by_cooccurrence(["B"], depth=1)
        assert "A" in result
        assert "B" in result

    @pytest.mark.asyncio
    async def test_search_depth_2(self, graph):
        """depth=2 扩展到邻居的邻居"""
        await graph.add_memory_tags("mem_001", ["A", "B"])
        await graph.add_memory_tags("mem_002", ["B", "C"])
        await graph.add_memory_tags("mem_003", ["C", "D"])

        result = await graph.search_by_cooccurrence(["A"], depth=2)
        assert "A" in result
        assert "B" in result
        assert "C" in result
        # D 是 C 的邻居，BFS depth=2 应该包含
        assert "D" in result

    @pytest.mark.asyncio
    async def test_search_multiple_seeds(self, graph):
        """多种子搜索"""
        await graph.add_memory_tags("mem_001", ["A", "B"])
        await graph.add_memory_tags("mem_002", ["C", "D"])

        result = await graph.search_by_cooccurrence(["A", "C"], depth=1)
        assert "A" in result
        assert "B" in result
        assert "C" in result
        assert "D" in result


class TestPersistAndReload:
    """测试持久化和重新加载"""

    @pytest.mark.asyncio
    async def test_persist_and_reload(self, graph):
        """图谱持久化后能正确重新加载"""
        await graph.add_memory_tags("mem_001", ["石榴籽", "省赛"])

        # 重新创建实例并加载
        graph2 = TagCooccurrenceGraph(storage_path=graph.storage_path)
        await graph2.load()

        assert "石榴籽" in graph2.nodes
        assert graph2.nodes["石榴籽"].frequency == 1
        assert edge_key("石榴籽", "省赛") in graph2.edges

    @pytest.mark.asyncio
    async def test_persist_multiple_memories(self, graph):
        """多条记忆的图谱持久化"""
        await graph.add_memory_tags("mem_001", ["A", "B", "C"])
        await graph.add_memory_tags("mem_002", ["A", "B"])
        await graph.add_memory_tags("mem_003", ["A", "D"])

        graph2 = TagCooccurrenceGraph(storage_path=graph.storage_path)
        await graph2.load()

        assert graph2.nodes["A"].frequency == 3
        assert graph2.nodes["B"].frequency == 2
        assert graph2.nodes["C"].frequency == 1
        assert graph2.nodes["D"].frequency == 1

    @pytest.mark.asyncio
    async def test_reload_empty_graph(self, graph):
        """重新加载空的图谱文件"""
        # 从未添加任何内容，直接 load 不应报错
        graph2 = TagCooccurrenceGraph(storage_path=graph.storage_path)
        await graph2.load()
        assert len(graph2.nodes) == 0
        assert len(graph2.edges) == 0


class TestEdgeNormalization:
    """测试边权重归一化"""

    @pytest.mark.asyncio
    async def test_weight_normalization(self, graph):
        """验证归一化权重 = co_count / min(freq_a, freq_b)"""
        await graph.add_memory_tags("mem_001", ["A", "B"])
        await graph.add_memory_tags("mem_002", ["A", "B"])

        # A 出现2次，B 出现2次，最小是2
        # co_count=2，weight=2/2=1.0
        edge = graph.edges[edge_key("A", "B")]
        assert edge.co_count == 2
        assert edge.weight == 1.0

    @pytest.mark.asyncio
    async def test_weight_with_different_frequencies(self, graph):
        """不同频率的标签共现"""
        await graph.add_memory_tags("mem_001", ["X", "Y"])
        await graph.add_memory_tags("mem_002", ["X", "Y"])
        await graph.add_memory_tags("mem_003", ["X"])

        # X 出现3次，Y 出现2次，最小是2
        # co_count=2，weight=2/2=1.0
        edge = graph.edges[edge_key("X", "Y")]
        assert edge.weight == 1.0

    @pytest.mark.asyncio
    async def test_partial_cooccurrence(self, graph):
        """并非所有记忆都共现"""
        await graph.add_memory_tags("mem_001", ["P", "Q"])
        await graph.add_memory_tags("mem_002", ["P"])

        # P 出现2次，Q 出现1次，最小是1
        # co_count=1，weight=1/1=1.0
        edge = graph.edges[edge_key("P", "Q")]
        assert edge.co_count == 1
        assert edge.weight == 1.0

    @pytest.mark.asyncio
    async def test_cooccurrence_count_accumulation(self, graph):
        """共现计数正确累加"""
        await graph.add_memory_tags("mem_001", ["K", "L"])
        await graph.add_memory_tags("mem_002", ["K", "L"])
        await graph.add_memory_tags("mem_003", ["K", "L"])

        edge = graph.edges[edge_key("K", "L")]
        assert edge.co_count == 3
        # K 出现3次，L 出现3次，min=3
        assert edge.weight == 3 / 3


class TestTimestamps:
    """测试时间戳更新"""

    @pytest.mark.asyncio
    async def test_first_seen_set_on_first_add(self, graph):
        """首次添加时设置 first_seen"""
        await graph.add_memory_tags("mem_001", ["T1"])

        assert graph.nodes["T1"].first_seen != ""
        assert graph.nodes["T1"].first_seen == graph.nodes["T1"].last_seen

    @pytest.mark.asyncio
    async def test_last_seen_updated_on_re_add(self, graph):
        """重复添加时更新 last_seen"""
        await graph.add_memory_tags("mem_001", ["T2"])
        import asyncio
        await asyncio.sleep(0.01)
        await graph.add_memory_tags("mem_002", ["T2"])

        first = graph.nodes["T2"].first_seen
        last = graph.nodes["T2"].last_seen
        assert first <= last
