"""
DataLake 单元测试

测试 DataLake 模块的核心功能：
- 目录管理
- 原子写入
- 路径安全验证
- 并发操作
"""

import pytest
import os
import asyncio
from pathlib import Path
from datetime import datetime

from agentmemory.data import DataLake
from agentmemory.data.datalake import (
    PathSecurityError,
    MemoryNotFoundError,
    MemoryContent,
    MemoryMeta,
    MemoryVector,
)


class TestDataLakeInit:
    """DataLake 初始化测试"""
    
    def test_init_creates_memory_library_dir(self, datalake: DataLake):
        """测试初始化创建 memory_library 目录"""
        assert datalake.memory_library.exists()
        assert datalake.memory_library.is_dir()
    
    def test_init_with_custom_library_name(self, temp_dir: str):
        """测试自定义 library 名称"""
        lake = DataLake(root_dir=temp_dir, memory_library_name="custom_library")
        asyncio.run(lake.init())
        custom_path = Path(temp_dir) / "custom_library"
        assert custom_path.exists()


class TestDataLakePathSecurity:
    """DataLake 路径安全测试"""
    
    def test_validate_path_inside_whitelist(self, datalake: DataLake):
        """测试白名单内路径验证通过"""
        valid_path = datalake.memory_library / "test.md"
        result = datalake._validate_path(valid_path)
        assert result == valid_path.resolve()
    
    def test_validate_path_outside_whitelist_raises_error(self, datalake: DataLake, temp_dir: str):
        """测试白名单外路径验证失败"""
        outside_path = Path(temp_dir) / "outside.md"
        with pytest.raises(PathSecurityError):
            datalake._validate_path(outside_path)
    
    def test_validate_relative_path(self, datalake: DataLake):
        """测试相对路径验证"""
        relative_path = datalake.memory_library / "subdir" / "test.md"
        result = datalake._validate_path(relative_path)
        assert result == relative_path.resolve()


class TestDataLakeCategoryOperations:
    """DataLake 分类操作测试"""
    
    @pytest.mark.asyncio
    async def test_create_category(self, datalake: DataLake):
        """测试创建分类目录"""
        category_path = "A.项目/石榴籽"
        result = await datalake.create_category(category_path)
        
        expected_dir = datalake.memory_library / category_path
        assert result == expected_dir
        assert expected_dir.exists()
        assert expected_dir.is_dir()
    
    @pytest.mark.asyncio
    async def test_create_nested_category(self, datalake: DataLake):
        """测试创建嵌套分类目录"""
        category_path = "A.项目/石榴籽/语料/翻译"
        await datalake.create_category(category_path)
        
        expected_dir = datalake.memory_library / category_path
        assert expected_dir.exists()
    
    @pytest.mark.asyncio
    async def test_scan_empty_category(self, datalake: DataLake):
        """测试扫描空分类"""
        await datalake.create_category("A.项目/测试")
        memories = await datalake.scan_category("A.项目/测试")
        
        assert memories == []
    
    @pytest.mark.asyncio
    async def test_scan_category_with_memories(self, datalake_with_category):
        """测试扫描包含记忆的分类"""
        lake, category_path = datalake_with_category
        
        # 创建测试记忆
        await lake.create_memory(
            category_path=category_path,
            content="# Test Memory",
            tags=["test"]
        )
        
        memories = await lake.scan_category(category_path)
        assert len(memories) == 1


class TestDataLakeMemoryOperations:
    """DataLake 记忆操作测试"""
    
    @pytest.mark.asyncio
    async def test_create_memory(self, datalake_with_category):
        """测试创建记忆"""
        lake, category_path = datalake_with_category
        
        memory_id = await lake.create_memory(
            category_path=category_path,
            content="# Test Memory\n\nThis is a test.",
            tags=["test", "important"],
            importance=0.8
        )
        
        assert memory_id is not None
        assert len(memory_id) > 0
        
        # 验证文件存在
        memory_dir = lake.memory_library / category_path
        content_file = memory_dir / f"{memory_id}.md"
        assert content_file.exists()
    
    @pytest.mark.asyncio
    async def test_create_memory_with_whitespace_content(self, datalake_with_category):
        """测试创建包含空白内容的记忆"""
        lake, category_path = datalake_with_category
        
        memory_id = await lake.create_memory(
            category_path=category_path,
            content="   \n\n   \n",
            tags=["test"]
        )
        
        assert memory_id is not None
    
    @pytest.mark.asyncio
    async def test_read_memory(self, datalake_with_category):
        """测试读取记忆内容"""
        lake, category_path = datalake_with_category
        
        content = "# Test Memory\n\nContent here."
        memory_id = await lake.create_memory(
            category_path=category_path,
            content=content,
            tags=["test"]
        )
        
        result = await lake.read_memory(memory_id)
        assert result is not None
        assert result.content == content
    
    @pytest.mark.asyncio
    async def test_read_nonexistent_memory_raises_error(self, datalake: DataLake):
        """测试读取不存在的记忆抛出异常"""
        with pytest.raises(MemoryNotFoundError):
            await datalake.read_memory("nonexistent_id")
    
    @pytest.mark.asyncio
    async def test_update_memory(self, datalake_with_category):
        """测试更新记忆"""
        lake, category_path = datalake_with_category
        
        memory_id = await lake.create_memory(
            category_path=category_path,
            content="# Original",
            tags=["test"]
        )
        
        new_content = "# Updated\n\nNew content."
        await lake.update_memory(
            memory_id=memory_id,
            content=new_content
        )
        
        result = await lake.read_memory(memory_id)
        assert result.content == new_content
    
    @pytest.mark.asyncio
    async def test_delete_memory(self, datalake_with_category):
        """测试删除记忆"""
        lake, category_path = datalake_with_category
        
        memory_id = await lake.create_memory(
            category_path=category_path,
            content="# To Delete",
            tags=["test"]
        )
        
        await lake.delete_memory(memory_id)
        
        # 验证文件已删除
        memory_dir = lake.memory_library / category_path
        content_file = memory_dir / f"{memory_id}.md"
        assert not content_file.exists()


class TestDataLakeAtomicWrite:
    """DataLake 原子写入测试"""
    
    @pytest.mark.asyncio
    async def test_write_creates_tmp_file_then_rename(self, datalake_with_category):
        """测试写入先创建 .tmp 文件再重命名"""
        lake, category_path = datalake_with_category
        
        memory_id = await lake.create_memory(
            category_path=category_path,
            content="# Atomic Test",
            tags=["test"]
        )
        
        # 验证不存在 .tmp 文件
        memory_dir = lake.memory_library / category_path
        tmp_files = list(memory_dir.glob(f"{memory_id}.*.tmp"))
        assert len(tmp_files) == 0
        
        # 验证主文件存在
        content_file = memory_dir / f"{memory_id}.md"
        assert content_file.exists()
    
    @pytest.mark.asyncio
    async def test_concurrent_writes(self, datalake_with_category):
        """测试并发写入不冲突"""
        lake, category_path = datalake_with_category
        
        async def create_memory_task(i: int):
            return await lake.create_memory(
                category_path=category_path,
                content=f"# Memory {i}",
                tags=["test"]
            )
        
        # 并发创建多个记忆
        tasks = [create_memory_task(i) for i in range(10)]
        memory_ids = await asyncio.gather(*tasks)
        
        assert len(memory_ids) == 10
        assert len(set(memory_ids)) == 10  # 所有 ID 唯一


class TestDataLakeHashing:
    """DataLake 内容哈希测试"""
    
    def test_compute_hash_deterministic(self, datalake: DataLake):
        """测试哈希计算是确定性的"""
        content = "Test content"
        hash1 = datalake._compute_hash(content)
     
