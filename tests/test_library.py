"""
图书馆分类系统测试
测试 LibraryClassifier
"""
import pytest
from src.agent_memory.library import LibraryClassifier, TOP_LEVEL_CATEGORIES, CATEGORY_DICTIONARY


class TestLibraryClassifier:
    """LibraryClassifier 单元测试"""

    def test_classify_project_content(self):
        """分类项目相关内容"""
        classifier = LibraryClassifier()
        
        result = classifier.classify("开发 AgentMemory 项目")
        
        assert result.startswith("项目")

    def test_classify_learning_content(self):
        """分类学习相关内容"""
        classifier = LibraryClassifier()
        
        result = classifier.classify("学习 Python 编程教程")
        
        assert result.startswith("学习")

    def test_classify_person_content(self):
        """分类人物相关内容"""
        classifier = LibraryClassifier()
        
        result = classifier.classify("我的同事张三今天告诉我")
        
        assert result.startswith("人物")

    def test_classify_decision_content(self):
        """分类决策相关内容"""
        classifier = LibraryClassifier()
        
        result = classifier.classify("我决定使用 Python 作为主语言")
        
        assert result.startswith("决策")

    def test_classify_preference_content(self):
        """分类偏好相关内容"""
        classifier = LibraryClassifier()
        
        result = classifier.classify("我更喜欢简洁的代码风格")
        
        assert result.startswith("偏好")

    def test_classify_unclassified(self):
        """无法分类的内容"""
        classifier = LibraryClassifier()
        
        result = classifier.classify("今天天气很好")
        
        assert result == "未分类"

    def test_classify_empty_content(self):
        """空内容"""
        classifier = LibraryClassifier()
        
        result = classifier.classify("")
        
        assert result == "未分类"

    def test_validate_path_max_depth(self):
        """超过4层自动截断"""
        classifier = LibraryClassifier(max_depth=4)
        
        deep_path = "项目/子项目/模块/功能/细节"
        result = classifier._validate_path(deep_path)
        
        parts = result.split("/")
        assert len(parts) <= 4

    def test_validate_path_empty(self):
        """空路径返回 未分类"""
        classifier = LibraryClassifier()
        
        result = classifier._validate_path("")
        
        assert result == "未分类"

    def test_validate_path_whitespace(self):
        """空白路径返回 未分类"""
        classifier = LibraryClassifier()
        
        result = classifier._validate_path("   ")
        
        assert result == "未分类"

    def test_validate_path_trailing_slash(self):
        """尾部斜杠被移除"""
        classifier = LibraryClassifier()
        
        result = classifier._validate_path("项目/")
        
        assert not result.endswith("/")

    def test_validate_path_consecutive_slashes(self):
        """连续斜杠被规范化"""
        classifier = LibraryClassifier()
        
        result = classifier._validate_path("a//b///c")
        
        assert "//" not in result

    def test_top_level_categories_fixed(self):
        """顶层类别固定"""
        assert len(TOP_LEVEL_CATEGORIES) == 5
        assert "项目" in TOP_LEVEL_CATEGORIES
        assert "学习" in TOP_LEVEL_CATEGORIES
        assert "人物" in TOP_LEVEL_CATEGORIES
        assert "决策" in TOP_LEVEL_CATEGORIES
        assert "偏好" in TOP_LEVEL_CATEGORIES

    def test_get_categories(self):
        """获取所有顶层类别"""
        classifier = LibraryClassifier()
        
        categories = classifier.get_categories()
        
        assert len(categories) == 5
        assert categories == TOP_LEVEL_CATEGORIES

    def test_add_keyword(self):
        """添加自定义关键词"""
        classifier = LibraryClassifier()
        
        classifier.add_keyword("项目", "自定义项目词")
        
        assert "自定义项目词" in classifier.dictionary["项目"]

    def test_get_all_paths(self):
        """获取所有可能的分类路径"""
        classifier = LibraryClassifier()
        
        paths = classifier.get_all_paths()
        
        assert "项目" in paths
        assert "学习" in paths
        assert "人物" in paths
        assert "决策" in paths
        assert "偏好" in paths


class TestCategoryDictionary:
    """分类词典测试"""

    def test_dictionary_has_all_categories(self):
        """词典包含所有顶层类别"""
        for category in TOP_LEVEL_CATEGORIES:
            assert category in CATEGORY_DICTIONARY

    def test_dictionary_keywords_are_strings(self):
        """关键词都是字符串"""
        for category, keywords in CATEGORY_DICTIONARY.items():
            assert isinstance(keywords, list)
            for kw in keywords:
                assert isinstance(kw, str)


class TestSubcategoryInference:
    """子分类推断测试"""

    def test_infer_shiliuzi_project(self):
        """识别石榴籽项目"""
        classifier = LibraryClassifier()
        
        result = classifier.classify("石榴籽项目的进展如何")
        
        assert "石榴籽" in result

    def test_infer_spectrai_project(self):
        """识别 SpectrAI 项目"""
        classifier = LibraryClassifier()
        
        result = classifier.classify("SpectrAI 平台的新功能")
        
        assert "SpectrAI" in result or "项目" in result

    def test_infer_python_learning(self):
        """识别 Python 学习"""
        classifier = LibraryClassifier()
        
        result = classifier.classify("学习 Python 异步编程")
        
        assert "学习" in result
