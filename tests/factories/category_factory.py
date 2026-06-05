"""
Category Factory - 分类工厂方法

提供创建测试用分类的工厂方法。
"""

from typing import Optional


class CategoryFactory:
    """分类工厂类"""
    
    # 预设的分类层级结构
    PRESET_CATEGORIES = [
        "A.项目",
        "A.项目/石榴籽",
        "A.项目/石榴籽/语料",
        "A.项目/石榴籽/进度",
        "A.项目/AgentMemory",
        "A.项目/AgentMemory/开发",
        "B.个人",
        "B.个人/日记",
        "B.个人/日记/2024",
        "B.个人/笔记",
        "B.个人/收藏",
        "C.临时",
        "C.临时/草稿",
        "C.临时/待整理",
    ]
    
    @classmethod
    def create_path(cls, depth: int = 2, prefix: str = "A.项目") -> str:
        """创建指定深度的分类路径"""
        base_paths = {
            "A.项目": ["石榴籽", "AgentMemory", "其他"],
            "B.个人": ["日记", "笔记", "收藏"],
            "C.临时": ["草稿", "待整理"]
        }
        
        if prefix not in base_paths:
            prefix = "A.项目"
        
        parts = [prefix]
        sub_paths = {
            "石榴籽": ["语料", "进度", "文档"],
            "AgentMemory": ["开发", "测试", "文档"],
            "日记": ["2024", "2023"],
            "笔记": ["技术", "生活"],
        }
        
        for _ in range(depth - 1):
            parent = parts[-1]
            children = sub_paths.get(parent, ["子分类"])
            parts.append(children[0])
        
        return "/".join(parts)
    
    @classmethod
    def get_whitelist(cls) -> list[str]:
        """获取默认白名单"""
        return ["A.项目", "B.个人", "C.临时"]
    
    @classmethod
    def create_metadata(cls, description: str = "") -> dict:
        """创建分类元数据"""
        return {
            "description": description,
            "created_by": "CategoryFactory"
        }
