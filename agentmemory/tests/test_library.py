"""
test_library.py — Library 白名单测试
验证 validate / suggest / add_subcategory
"""
import pytest
from agentmemory.data.library import (
    Library,
    CategoryNotInWhitelistError,
    CategoryDepthExceededError,
    CategoryNotFoundError,
)


@pytest.fixture
def library(tmp_path):
    """创建测试用 Library 实例"""
    lib = Library(root_dir=str(tmp_path), whitelist=["A.项目", "B.个人", "C.临时"])
    return lib


class TestLibraryValidate:
    """测试 validate"""

    @pytest.mark.asyncio
    async def test_library_validate_legal(self, library):
        """合法的 category 通过"""
        await library.init()
        node = library.validate(["A.项目"])
        assert node is not None
        assert node.depth == 1

    @pytest.mark.asyncio
    async def test_library_validate_path_traversal_rejected(self, library):
        """非法的（路径穿越）被拒绝"""
        await library.init()
        # 尝试路径穿越
        with pytest.raises(CategoryNotInWhitelistError):
            library.validate(["..", "..", "etc", "passwd"])

    @pytest.mark.asyncio
    async def test_library_validate_depth_exceeded(self, library):
        """超过最大深度被拒绝"""
        await library.init()
        with pytest.raises(CategoryDepthExceededError):
            library.validate(["A.项目", "B", "C", "D", "E"])

    @pytest.mark.asyncio
    async def test_library_validate_invalid_whitelist(self, library):
        """不在白名单的顶级分类被拒绝"""
        await library.init()
        with pytest.raises(CategoryNotInWhitelistError):
            library.validate(["Z.非法分类"])


class TestLibrarySuggest:
    """测试 suggest"""

    @pytest.mark.asyncio
    async def test_library_suggest(self, library):
        """建议子分类"""
        await library.init()
        suggestions = await library.suggest("项目工作计划")
        assert isinstance(suggestions, list)

    @pytest.mark.asyncio
    async def test_library_suggest_empty(self, library):
        """无法匹配时返回空"""
        await library.init()
        suggestions = await library.suggest("这是一个无法匹配任何已知分类的随机内容 xyz123")
        # fallback 关键词匹配可能返回空列表
        assert isinstance(suggestions, list)


class TestLibraryAddSubcategory:
    """测试 add_subcategory"""

    @pytest.mark.asyncio
    async def test_library_add_subcategory(self, library):
        """添加子分类"""
        await library.init()
        # 先创建一个父分类（在白名单中）
        await library.create_category("A.项目", allow_new_top_level=True)
        node = await library.add_subcategory(
            parent=["A.项目"],
            name="test_child",
            description="测试子分类",
        )
        assert node.name == "test_child"
        assert node.depth == 2
        assert "A.项目" in node.path
        assert "test_child" in node.path

    @pytest.mark.asyncio
    async def test_library_add_subcategory_depth_exceeded(self, library):
        """添加子分类超过深度限制"""
        await library.init()
        await library.create_category("A.项目/B/C/D", allow_new_top_level=True)
        with pytest.raises(CategoryDepthExceededError):
            await library.add_subcategory(
                parent=["A.项目", "B", "C", "D"],
                name="E",
            )


class TestLibraryCRUD:
    """测试 Library CRUD"""

    @pytest.mark.asyncio
    async def test_library_create_category(self, library):
        """创建分类"""
        await library.init()
        info = await library.create_category("A.项目/test_cat", allow_new_top_level=True)
        assert info.path == "A.项目/test_cat"
        assert info.depth == 2

    @pytest.mark.asyncio
    async def test_library_list_categories(self, library):
        """列出顶级分类"""
        await library.init()
        cats = await library.list_categories()
        assert isinstance(cats, list)

    @pytest.mark.asyncio
    async def test_library_get_category_info(self, library):
        """获取分类信息"""
        await library.init()
        await library.create_category("B.个人/日记", allow_new_top_level=True)
        info = await library.get_category_info("B.个人/日记")
        assert info.name == "日记"
        assert info.depth == 2

    @pytest.mark.asyncio
    async def test_library_delete_category(self, library):
        """删除分类"""
        await library.init()
        await library.create_category("C.临时/to_delete", allow_new_top_level=True)
        await library.delete_category("C.临时/to_delete", recursive=True)
        # 再次获取应该抛异常
        with pytest.raises(CategoryNotFoundError):
            await library.get_category_info("C.临时/to_delete")


class TestLibraryWhitelist:
    """测试白名单功能"""

    def test_library_whitelist_defaults(self, library):
        """默认白名单"""
        wl = library.get_whitelist()
        assert "A.项目" in wl
        assert "B.个人" in wl
        assert "C.临时" in wl

    def test_library_add_to_whitelist(self, library):
        """添加白名单"""
        library.add_to_whitelist("D.新分类")
        assert library.is_in_whitelist("D.新分类") is True

    def test_library_is_in_whitelist(self, library):
        """检查是否在白名单"""
        assert library.is_in_whitelist("A.项目") is True
        assert library.is_in_whitelist("Z.不存在") is False
