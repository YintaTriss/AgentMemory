"""
Library 单元测试

测试 Library 模块的核心功能：
- 分类 CRUD
- 白名单校验
- 深度限制
- 索引持久化
"""

import pytest
import os
import json
from pathlib import Path

from agentmemory.data import Library
from agentmemory.data.library import (
    CategoryNotFoundError,
    CategoryDepthExceededError,
    CategoryNotInWhitelistError,
    CategoryAlreadyExistsError,
)


class TestLibraryInit:
    """Library 初始化测试"""
    
    def test_init_creates_index_file(self, library: Library):
        """测试初始化创建索引文件"""
        assert library.index_file.exists()
    
    def test_init_loads_existing_index(self, library_with_categories: Library):
        """测试初始化加载已有索引"""
        lib = library_with_categories
        # 索引文件应该存在且包含数据
        assert lib.index_file.exists()
        
        with open(lib.index_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data) > 0


class TestLibraryWhitelist:
    """Library 白名单测试"""
    
    def test_get_whitelist(self, library: Library):
        """测试获取白名单"""
        whitelist = library.get_whitelist()
        assert isinstance(whitelist, list)
        assert len(whitelist) > 0
    
    def test_is_in_whitelist(self, library: Library):
        """测试检查白名单"""
        assert library.is_in_whitelist("A.项目")
        assert library.is_in_whitelist("A.项目/石榴籽")  # 子分类也算
        assert not library.is_in_whitelist("D.不允许")
    
    def test_add_to_whitelist(self, library: Library):
        """测试添加白名单"""
        library.add_to_whitelist("D.新分类")
        assert library.is_in_whitelist("D.新分类")
    
    def test_remove_from_whitelist(self, library: Library):
        """测试移除白名单"""
        library.remove_from_whitelist("A.项目")
        assert not library.is_in_whitelist("A.项目")
    
    def test_requires_confirmation(self, library: Library):
        """测试需要确认检查"""
        assert not library.requires_confirmation("A.项目")  # 在白名单中
        assert library.requires_confirmation("D.不在白名单")


class TestLibraryCRUD:
    """Library 分类 CRUD 测试"""
    
    @pytest.mark.asyncio
    async def test_create_category(self, library: Library):
        """测试创建分类"""
        result = await library.create_category("A.项目/测试")
        assert result is not None
        
        info = await library.get_category_info("A.项目/测试")
        assert info is not None
        assert info.path == "A.项目/测试"
    
    @pytest.mark.asyncio
    async def test_create_nested_category(self, library: Library):
        """测试创建嵌套分类"""
        await library.create_category("A.项目/石榴籽/语料")
        
        info = await library.get_category_info("A.项目/石榴籽/语料")
        assert info is not None
        assert info.depth == 3
    
    @pytest.mark.asyncio
    async def test_create_category_depth_exceeded(self, library: Library):
        """测试创建超过深度的分类"""
        with pytest.raises(CategoryDepthExceededError):
            await library.create_category("A/B/C/D/E")  # 5层，超过限制
    
    @pytest.mark.asyncio
    async def test_create_category_outside_whitelist(self, library: Library):
        """测试在白名单外创建分类需要确认"""
        # 默认需要确认
        assert library.requires_confirmation("D.不在白名单")
    
    @pytest.mark.asyncio
    async def test_list_categories(self, library_with_categories: Library):
        """测试列出所有分类"""
        categories = await library.list_categories()
        assert len(categories) >= 4  # 我们创建了4个分类
    
    @pytest.mark.asyncio
    async def test_delete_category(self, library_with_categories: Library):
        """测试删除分类"""
        lib = library_with_categories
        
        await lib.delete_category("C.临时")
        
        with pytest.raises(CategoryNotFoundError):
            await lib.get_category_info("C.临时")
    
    @pytest.mark.asyncio
    async def test_delete_category_with_children(self, library_with_categories: Library):
        """测试删除有子分类的分类"""
        lib = library_with_categories
        
        # 删除有子分类的分类
        await lib.delete_category("A.项目/石榴籽", recursive=True)
        
        # 子分类应该也被删除
        with pytest.raises(CategoryNotFoundError):
            await lib.get_category_info("A.项目/石榴籽/语料")


class TestLibraryDepthLimit:
    """Library 深度限制测试"""
    
    @pytest.mark.asyncio
    async def test_max_depth_4(self, library: Library):
        """测试最大深度为 4"""
        # 4 层应该可以
        await library.create_category("A/B/C/D")
        
        # 5 层应该失败
        with pytest.raises(CategoryDepthExceededError):
            await library.create_category("A/B/C/D/E")
    
    def test_get_depth(self, library: Library):
        """测试获取分类深度"""
        assert library._get_depth("A") == 1
        assert library._get_depth("A/B") == 2
        assert library._get_depth("A/B/C/D") == 4


class TestLibrarySerialization:
    """Library 序列化测试"""
    
    @pytest.mark.asyncio
    async def test_index_persistence(self, library_with_categories: Library):
        """测试索引持久化"""
        lib = library_with_categories
        
        # 读取索引文件
        with open(lib.index_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        assert isinstance(data, dict)
        assert len(data) > 0
    
    @pytest.mark.asyncio
    async def test_category_exists(self, library_with_categories: Library):
        """测试分类存在检查"""
        lib = library_with_categories
        
        assert lib._category_exists("A.项目/石榴籽")
        assert not lib._category_exists("Z.不存在")


class TestLibraryInfo:
    """Library 分类信息测试"""
    
    @pytest.mark.asyncio
    async def test_get_category_info(self, library_with_categories: Library):
        """测试获取分类信息"""
        lib = library_with_categories
        
        info = await lib.get_category_info("A.项目/石榴籽")
        assert info is not None
        assert info.name == "石榴籽"
        assert info.depth == 2
    
    @pytest.mark.asyncio
    async def test_get_category_info_not_found(self, library_with_categories: Library):
        """测试获取不存在的分类信息"""
        lib = library_with_categories
        
        with pytest.raises(CategoryNotFoundError):
            await lib.get_category_info("Z.不存在")


class TestLibraryIterator:
    """Library 迭代器测试"""
    
    @pytest.mark.asyncio
    async def test_iterate_categories(self, library_with_categories: Library):
        """测试迭代分类"""
        lib = library_with_categories
        
        categories = []
        async for cat in lib.iterate_categories():
            categories.append(cat)
        
        assert len(categories) >= 4
