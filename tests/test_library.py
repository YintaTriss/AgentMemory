# -*- coding: utf-8 -*-
"""
Library Classifier Tests
"""
import pytest
from src.agent_memory.library import LibraryClassifier, TOP_LEVEL_CATEGORIES, CATEGORY_DICTIONARY


class TestLibraryClassifier:
    """LibraryClassifier unit tests"""

    def test_classify_project_content(self):
        """Classify project-related content"""
        classifier = LibraryClassifier()

        result = classifier.classify("开发 AgentMemory 项目")

        assert result.startswith("项目")

    def test_classify_learning_content(self):
        """Classify learning-related content"""
        classifier = LibraryClassifier()

        result = classifier.classify("学习 Python 编程教程")

        assert result.startswith("学习")

    def test_classify_person_content(self):
        """Classify person-related content"""
        classifier = LibraryClassifier()

        result = classifier.classify("我的同事张三今天告诉我")

        assert result.startswith("人物")

    def test_classify_decision_content(self):
        """Classify decision-related content"""
        classifier = LibraryClassifier()

        # Use pure decision keywords, no other category terms
        result = classifier.classify("经过权衡，我决定采用微服务架构")

        assert result.startswith("决策")

    def test_classify_preference_content(self):
        """Classify preference-related content"""
        classifier = LibraryClassifier()

        result = classifier.classify("我更喜欢简洁的代码风格")

        assert result.startswith("偏好")

    def test_classify_unclassified(self):
        """Unclassifiable content"""
        classifier = LibraryClassifier()

        result = classifier.classify("今天天气很好")

        assert result.startswith("未分类")

    def test_classify_empty_content(self):
        """Empty content"""
        classifier = LibraryClassifier()

        result = classifier.classify("")

        assert result.startswith("未分类")

    def test_validate_path_max_depth(self):
        """Over 4 layers auto-truncated"""
        classifier = LibraryClassifier(max_depth=4)

        deep_path = "项目/子项目/模块/功能/细节"
        result = classifier._validate_path(deep_path)

        parts = result.split("/")
        assert len(parts) <= 4

    def test_validate_path_empty(self):
        """Empty path returns default"""
        classifier = LibraryClassifier()

        result = classifier._validate_path("")

        assert result.startswith("未分类")

    def test_validate_path_whitespace(self):
        """Whitespace path returns default"""
        classifier = LibraryClassifier()

        result = classifier._validate_path("   ")

        assert result.startswith("未分类")

    def test_validate_path_trailing_slash(self):
        """Trailing slash removed"""
        classifier = LibraryClassifier()

        result = classifier._validate_path("项目/")

        assert not result.endswith("/")

    def test_validate_path_consecutive_slashes(self):
        """Consecutive slashes collapsed"""
        classifier = LibraryClassifier()

        result = classifier._validate_path("项目//石榴籽")

        assert "//" not in result

    def test_top_level_categories_fixed(self):
        """Top-level categories are fixed"""
        assert "项目" in TOP_LEVEL_CATEGORIES
        assert "学习" in TOP_LEVEL_CATEGORIES
        assert "人物" in TOP_LEVEL_CATEGORIES
        assert "决策" in TOP_LEVEL_CATEGORIES
        assert "偏好" in TOP_LEVEL_CATEGORIES

    def test_get_categories(self):
        """get_categories returns top-level"""
        classifier = LibraryClassifier()

        cats = classifier.get_categories()

        assert isinstance(cats, list)
        assert len(cats) == 5

    def test_add_keyword(self):
        """add_keyword adds custom keyword"""
        classifier = LibraryClassifier()
        classifier.add_keyword("项目", "我的项目")

        assert "我的项目" in classifier.dictionary.get("项目", [])

    def test_get_all_paths(self):
        """get_all_paths returns all top-level"""
        classifier = LibraryClassifier()

        paths = classifier.get_all_paths()

        assert isinstance(paths, list)
        assert "项目" in paths


class TestCategoryDictionary:
    """Category dictionary tests"""

    def test_dictionary_has_all_categories(self):
        """Dictionary has all required categories"""
        for cat in TOP_LEVEL_CATEGORIES:
            assert cat in CATEGORY_DICTIONARY

    def test_dictionary_keywords_are_strings(self):
        """Dictionary keywords are strings"""
        for cat, keywords in CATEGORY_DICTIONARY.items():
            assert isinstance(cat, str)
            for kw in keywords:
                assert isinstance(kw, str)


class TestSubcategoryInference:
    """Subcategory inference tests"""

    def test_infer_shiliuzi_project(self):
        """Infer石榴籽 as project"""
        classifier = LibraryClassifier()

        result = classifier.classify("石榴籽项目进展顺利")

        assert "项目" in result or "石榴籽" in result

    def test_infer_spectrai_project(self):
        """Infer SpectrAI as project"""
        classifier = LibraryClassifier()

        result = classifier.classify("SpectrAI 代码审查完成")

        assert "项目" in result

    def test_infer_python_learning(self):
        """Infer Python as learning"""
        classifier = LibraryClassifier()

        result = classifier.classify("Python 教程很好")

        assert "学习" in result or "Python" in result
