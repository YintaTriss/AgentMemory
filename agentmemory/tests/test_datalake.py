"""
test_datalake.py — DataLake 测试
验证 write/read/delete/exists/list_memories/hydrate 接口
"""
import pytest
import asyncio
from pathlib import Path
from agentmemory.data.datalake import DataLake


@pytest.fixture
def datalake(tmp_path):
    """创建测试用 DataLake 实例"""
    dl = DataLake(root_dir=str(tmp_path), memory_library_name="test_library")
    return dl


class TestDataLakeWriteAndRead:
    """测试 DataLake 写入和读取"""

    @pytest.mark.asyncio
    async def test_datalake_write_and_read(self, datalake, tmp_path):
        """写入一个 memory，读出来内容一致"""
        await datalake.init()
        category = ["A.项目", "test"]
        memory_id = await datalake.write(
            content="这是测试记忆内容",
            category=category,
            metadata={"source": "test", "tags": ["测试"]},
            importance=0.8,
        )
        assert memory_id.startswith("mem_")

        # 读取
        content_obj = await datalake.read(memory_id)
        assert content_obj is not None
        assert content_obj.content == "这是测试记忆内容"
        assert content_obj.memory_id == memory_id

    @pytest.mark.asyncio
    async def test_datalake_write_multiple(self, datalake):
        """写入多条记忆"""
        await datalake.init()
        ids = []
        for i in range(3):
            mid = await datalake.write(
                content=f"记忆 {i}",
                category=["A.项目", "test"],
                metadata={},
                importance=0.5,
            )
            ids.append(mid)
        assert len(set(ids)) == 3  # 全部唯一


class TestDataLakeExists:
    """测试 exists"""

    @pytest.mark.asyncio
    async def test_datalake_exists(self, datalake):
        """存在的返回 True，不存在的返回 False"""
        await datalake.init()
        memory_id = await datalake.write(
            content="存在性测试",
            category=["A.项目"],
            metadata={},
            importance=0.5,
        )
        assert await datalake.exists(memory_id) is True
        assert await datalake.exists("non_existent_id_12345") is False


class TestDataLakeDelete:
    """测试 delete"""

    @pytest.mark.asyncio
    async def test_datalake_delete(self, datalake):
        """删除后再 exists 应该返回 False"""
        await datalake.init()
        memory_id = await datalake.write(
            content="将被删除的记忆",
            category=["A.项目"],
            metadata={},
            importance=0.5,
        )
        assert await datalake.exists(memory_id) is True

        await datalake.delete(memory_id)
        assert await datalake.exists(memory_id) is False

    @pytest.mark.asyncio
    async def test_datalake_delete_nonexistent(self, datalake):
        """删除不存在的 memory 抛出异常"""
        await datalake.init()
        from agentmemory.data.datalake import MemoryNotFoundError
        with pytest.raises(MemoryNotFoundError):
            await datalake.delete("non_existent_id_xyz")


class TestDataLakeListMemories:
    """测试 list_memories"""

    @pytest.mark.asyncio
    async def test_datalake_list_memories(self, datalake):
        """列出记忆列表"""
        await datalake.init()
        cat = ["A.项目", "list_test"]
        ids = []
        for i in range(3):
            mid = await datalake.write(
                content=f"列表测试 {i}",
                category=cat,
                metadata={},
                importance=0.5,
            )
            ids.append(mid)

        listed = await datalake.list_memories(category=cat)
        assert isinstance(listed, list)
        for mid in ids:
            assert mid in listed

    @pytest.mark.asyncio
    async def test_datalake_list_memories_no_category(self, datalake):
        """不指定分类列出所有记忆"""
        await datalake.init()
        await datalake.write(content="A", category=["A.项目"], metadata={}, importance=0.5)
        await datalake.write(content="B", category=["B.个人"], metadata={}, importance=0.5)

        all_ids = await datalake.list_memories()
        assert len(all_ids) >= 2


class TestDataLakeHydrate:
    """测试 hydrate"""

    @pytest.mark.asyncio
    async def test_datalake_hydrate(self, datalake):
        """组装完整记忆对象"""
        await datalake.init()
        memory_id = await datalake.write(
            content="hydration test",
            category=["A.项目"],
            metadata={"custom_field": "value"},
            importance=0.7,
        )
        results = await datalake.hydrate([memory_id])
        assert len(results) == 1
        assert results[0].content == "hydration test"
        assert results[0].memory_id == memory_id

    @pytest.mark.asyncio
    async def test_datalake_hydrate_nonexistent(self, datalake):
        """hydrate 不存在的 id 被忽略（不抛异常）"""
        await datalake.init()
        results = await datalake.hydrate(["non_existent"])
        assert results == []


class TestDataLakeMove:
    """测试 move"""

    @pytest.mark.asyncio
    async def test_datalake_move(self, datalake):
        """移动记忆到另一个分类"""
        await datalake.init()
        memory_id = await datalake.write(
            content="移动测试",
            category=["A.项目", "source"],
            metadata={},
            importance=0.5,
        )

        await datalake.move(memory_id, ["A.项目", "target"])
        # 移动后依然存在
        assert await datalake.exists(memory_id) is True


class TestDataLakeUpdate:
    """测试 update_memory"""

    @pytest.mark.asyncio
    async def test_datalake_update_content(self, datalake):
        """更新记忆内容"""
        await datalake.init()
        memory_id = await datalake.write(
            content="原始内容",
            category=["A.项目"],
            metadata={},
            importance=0.5,
        )
        await datalake.update_memory(memory_id, content="更新后的内容")

        content_obj = await datalake.read(memory_id)
        assert content_obj.content == "更新后的内容"

    @pytest.mark.asyncio
    async def test_datalake_update_tags(self, datalake):
        """更新标签"""
        await datalake.init()
        memory_id = await datalake.write(
            content="标签测试",
            category=["A.项目"],
            metadata={"tags": ["old"]},
            importance=0.5,
        )
        await datalake.update_memory(memory_id, tags=["new", "tags"])

        content_obj = await datalake.read(memory_id)
        assert "new" in content_obj.metadata.get("tags", [])
        assert "old" not in content_obj.metadata.get("tags", [])
