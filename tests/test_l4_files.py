"""
L4 文件层单元测试
测试 L4FilesStore
"""
import json
import pytest
import asyncio
from pathlib import Path
from datetime import datetime

from src.agent_memory.l4_files import L4FilesStore, MemoryMeta, MemoryVec, generate_mem_id


class TestL4FilesStore:
    """L4FilesStore 单元测试"""

    @pytest.mark.asyncio
    async def test_save_creates_files(self, tmp_memory_dir):
        """save 后文件生成"""
        store = L4FilesStore(str(tmp_memory_dir))

        memory_id = generate_mem_id()
        content = "测试记忆内容"
        metadata = {"importance": 0.9, "tags": ["test"], "category_path": "测试"}

        result = await store.save(memory_id, content, metadata)

        assert result == memory_id
        # 验证文件生成
        md_file = tmp_memory_dir / f"{memory_id}.md"
        meta_file = tmp_memory_dir / f"{memory_id}.meta.json"
        assert md_file.exists()
        assert meta_file.exists()

    @pytest.mark.asyncio
    async def test_load_returns_content(self, tmp_memory_dir):
        """load 返回正确内容"""
        store = L4FilesStore(str(tmp_memory_dir))

        memory_id = generate_mem_id()
        content = "测试记忆内容 🎉"
        metadata = {"importance": 0.9}

        await store.save(memory_id, content, metadata)
        loaded_content = await store.load(memory_id)

        assert loaded_content == content

    @pytest.mark.asyncio
    async def test_get_meta_returns_metadata(self, tmp_memory_dir):
        """load_existing 返回正确元数据"""
        store = L4FilesStore(str(tmp_memory_dir))

        memory_id = generate_mem_id()
        content = "测试内容"
        metadata = {"importance": 0.8, "tags": ["tag1", "tag2"], "category_path": "项目/测试"}

        await store.save(memory_id, content, metadata)
        data = await store.load_existing(memory_id)

        assert data is not None
        meta = data["meta"]
        assert meta["id"] == memory_id
        assert meta["importance"] == 0.8
        assert meta["tags"] == ["tag1", "tag2"]
        assert meta["category_path"] == "项目/测试"

    @pytest.mark.asyncio
    async def test_list_returns_all_ids(self, tmp_memory_dir):
        """list 返回所有记忆ID"""
        store = L4FilesStore(str(tmp_memory_dir))

        # 存储多条记忆
        ids = []
        for i in range(3):
            memory_id = generate_mem_id()
            await store.save(memory_id, f"记忆{i}", {"importance": 0.5 + i * 0.1})
            ids.append(memory_id)

        all_ids = store.list()

        assert len(all_ids) >= 3
        for id in ids:
            assert id in all_ids

    @pytest.mark.asyncio
    async def test_delete_removes_files(self, tmp_memory_dir):
        """delete 删除文件"""
        store = L4FilesStore(str(tmp_memory_dir))

        memory_id = generate_mem_id()
        await store.save(memory_id, "测试内容", {"importance": 0.5})

        result = await store.delete(memory_id)

        assert result == True
        md_file = tmp_memory_dir / f"{memory_id}.md"
        meta_file = tmp_memory_dir / f"{memory_id}.meta.json"
        assert not md_file.exists()
        assert not meta_file.exists()

    @pytest.mark.asyncio
    async def test_update_meta_partial(self, tmp_memory_dir):
        """部分更新元数据（通过 load_existing + re-save）"""
        store = L4FilesStore(str(tmp_memory_dir))

        memory_id = generate_mem_id()
        await store.save(memory_id, "测试内容", {"importance": 0.5, "tags": ["tag1"]})

        # 读取后重新保存（模拟部分更新）
        data = await store.load_existing(memory_id)
        meta = data["meta"]
        meta["importance"] = 0.9
        meta["tags"] = ["tag1", "tag2"]
        await store.save(memory_id, data["content"], meta)

        updated = await store.load_existing(memory_id)
        assert updated["meta"]["importance"] == 0.9
        assert updated["meta"]["tags"] == ["tag1", "tag2"]

    @pytest.mark.asyncio
    async def test_unicode_content(self, tmp_memory_dir):
        """支持 Unicode 内容"""
        store = L4FilesStore(str(tmp_memory_dir))

        memory_id = generate_mem_id()
        content = "中文测试内容 🎉 Emoji 测试"

        await store.save(memory_id, content, {"importance": 0.9})
        loaded = await store.load(memory_id)

        assert loaded == content

    @pytest.mark.asyncio
    async def test_memory_meta_class(self):
        """MemoryMeta 数据类"""
        meta = MemoryMeta(
            id="test_id",
            importance=0.8,
            tags=["tag1", "tag2"],
            category_path="项目/测试"
        )

        d = meta.to_dict()

        assert d["id"] == "test_id"
        assert d["importance"] == 0.8
        assert d["tags"] == ["tag1", "tag2"]
        assert d["category_path"] == "项目/测试"
        assert "created_at" in d
        assert "updated_at" in d

    @pytest.mark.asyncio
    async def test_memory_vec_class(self):
        """MemoryVec 数据类"""
        vec = MemoryVec(
            id="test_id",
            vector=[0.1, 0.2, 0.3],
            embedder="test-embedder"
        )

        assert vec.id == "test_id"
        assert len(vec.vector) == 3
        assert vec.embedder == "test-embedder"


class TestGenerateMemId:
    """Memory ID 生成测试"""

    def test_generate_mem_id_format(self):
        """生成的 ID 格式正确"""
        memory_id = generate_mem_id()

        assert memory_id.startswith("mem_")
        assert len(memory_id) == 12  # mem_ + 8 chars

    def test_generate_mem_id_unique(self):
        """每次生成唯一 ID"""
        ids = [generate_mem_id() for _ in range(100)]

        assert len(set(ids)) == 100  # 全部唯一


class TestSyncMethods:
    """同步方法测试（L4FilesStore 的方法是 async，但 sync 测试用 asyncio 运行）"""

    @pytest.mark.asyncio
    async def test_save(self, tmp_memory_dir):
        """异步保存"""
        store = L4FilesStore(str(tmp_memory_dir))

        memory_id = generate_mem_id()
        result = await store.save(memory_id, "同步测试", {"importance": 0.8})

        assert result == memory_id
        assert (tmp_memory_dir / f"{memory_id}.md").exists()

    @pytest.mark.asyncio
    async def test_load(self, tmp_memory_dir):
        """异步加载"""
        store = L4FilesStore(str(tmp_memory_dir))

        memory_id = generate_mem_id()
        await store.save(memory_id, "异步加载测试", {"importance": 0.5})

        content = await store.load(memory_id)

        assert content == "异步加载测试"

    @pytest.mark.asyncio
    async def test_delete(self, tmp_memory_dir):
        """异步删除"""
        store = L4FilesStore(str(tmp_memory_dir))

        memory_id = generate_mem_id()
        await store.save(memory_id, "待删除", {"importance": 0.5})

        result = await store.delete(memory_id)

        assert result == True
        assert not (tmp_memory_dir / f"{memory_id}.md").exists()

    @pytest.mark.asyncio
    async def test_get_stats(self, tmp_memory_dir):
        """获取统计"""
        store = L4FilesStore(str(tmp_memory_dir))

        # 添加一些记忆
        for i in range(3):
            memory_id = generate_mem_id()
            await store.save(memory_id, f"记忆{i}", {"importance": 0.5})

        stats = store.get_stats()

        assert stats["memory_count"] >= 3
        assert stats["total_size_bytes"] > 0
