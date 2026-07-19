"""
FastEmbedEmbedder - 本地真·语义向量嵌入器
基于 fastembed 库(ONNX 本地推理,无需 Docker/云端)。

默认模型:BAAI/bge-small-zh-v1.5
  - 512 维
  - ~95MB ONNX 模型
  - 中文友好,本仓库的语料场景首选

用法:
  from agent_memory.fastembed_embedder import FastEmbedEmbedder
  fe = FastEmbedEmbedder()
  v = fe.embed("今晚要提交论证活页")
"""

from __future__ import annotations

import os
import threading
from typing import List, Dict, Any

import numpy as np

from .embedder import Embedder


# 默认模型候选(按推荐顺序)
DEFAULT_MODELS = [
    "BAAI/bge-small-zh-v1.5",          # 中文友好,512 维,~95MB
    "BAAI/bge-base-zh-v1.5",           # 中文 768 维,~400MB
    "intfloat/multilingual-e5-small",   # 多语种 384 维
    "sentence-transformers/all-MiniLM-L6-v2",  # 英文 384 维(兜底)
]

# 模型对应维度
# 2026-07-15 方向 8: 扩展模型注册表
# 所有模型都是单模型支持中英双语,用户自行选择更好的本地模型
MODEL_DIMS = {
    # BGE 中文系列
    "BAAI/bge-small-zh-v1.5": 512,
    "BAAI/bge-base-zh-v1.5": 768,
    "BAAI/bge-large-zh-v1.5": 1024,           # 中文强
    # BGE 多语言
    "BAAI/bge-m3": 1024,                        # ⭐ 推荐:中英双语原生,最强本地模型
    # E5 多语言
    "intfloat/multilingual-e5-small": 384,
    "intfloat/multilingual-e5-base": 768,
    "intfloat/multilingual-e5-large": 1024,     # 多语言强
    # Sentence-Transformers 英文
    "sentence-transformers/all-MiniLM-L6-v2": 384,
}

# 模型元信息(用户选择时能看到描述)
MODEL_INFO: Dict[str, Dict[str, Any]] = {
    "BAAI/bge-small-zh-v1.5": {"dim": 512, "size_mb": 95, "lang": "zh", "quality": "fast"},
    "BAAI/bge-base-zh-v1.5": {"dim": 768, "size_mb": 410, "lang": "zh", "quality": "good"},
    "BAAI/bge-large-zh-v1.5": {"dim": 1024, "size_mb": 1300, "lang": "zh", "quality": "best"},
    "BAAI/bge-m3": {"dim": 1024, "size_mb": 2200, "lang": "zh+en", "quality": "best-bilingual", "recommended": True},
    "intfloat/multilingual-e5-small": {"dim": 384, "size_mb": 470, "lang": "zh+en", "quality": "fast"},
    "intfloat/multilingual-e5-base": {"dim": 768, "size_mb": 1100, "lang": "zh+en", "quality": "good"},
    "intfloat/multilingual-e5-large": {"dim": 1024, "size_mb": 2200, "lang": "zh+en", "quality": "best"},
    "sentence-transformers/all-MiniLM-L6-v2": {"dim": 384, "size_mb": 80, "lang": "en", "quality": "fast-en"},
}

DEFAULT_RECOMMENDED_MODEL = "BAAI/bge-m3"  # ⭐ 推荐默认(中英双语原生,质量最高)

# 模型前缀(用于 query 嵌入)
BGE_QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章: "
E5_QUERY_PREFIX = "query: "


class FastEmbedEmbedder(Embedder):
    """
    本地 ONNX 推理的真·语义向量嵌入器。
    无需 Docker、无需云端 API,首次使用自动下载模型。
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-zh-v1.5",
        cache_dir: str | None = None,
        max_length: int = 512,
    ):
        self._model_name = model_name
        self._max_length = max_length
        self._cache_dir = cache_dir or os.environ.get("FASTEMBED_CACHE_DIR")

        # 验证模型支持
        if model_name not in MODEL_DIMS:
            raise ValueError(
                f"模型 {model_name} 不在支持列表中。"
                f"支持: {list(MODEL_DIMS.keys())}"
            )
        self._dim = MODEL_DIMS[model_name]

        # 懒加载 fastembed + 模型
        self._model = None
        self._lock = threading.Lock()

    def _ensure_model(self):
        """懒加载:第一次调用时才真正下载/加载模型。"""
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            from fastembed import TextEmbedding

            kwargs = {"model_name": self._model_name, "max_length": self._max_length}
            if self._cache_dir:
                kwargs["cache_dir"] = self._cache_dir
            self._model = TextEmbedding(**kwargs)

    @property
    def dim(self) -> int:
        return self._dim

    def _is_bge(self) -> bool:
        return "bge" in self._model_name.lower()

    def _is_e5(self) -> bool:
        return "e5" in self._model_name.lower()

    def _maybe_prefix_query(self, text: str, is_query: bool = True) -> str:
        """不同模型用不同前缀提升检索效果。

        BGE 系列: query 端加 "为这个句子生成表示以用于检索相关文章: "
        E5 系列:  query/document 端分别加 "query: " / "passage: "
        """
        if is_query and self._is_bge():
            return BGE_QUERY_PREFIX + text
        if self._is_e5():
            return ("query: " if is_query else "passage: ") + text
        return text

    def embed(self, text: str) -> List[float]:
        # embed() 接口在 Manager 内部用,默认当作 query(用于检索)
        self._ensure_model()
        processed = self._maybe_prefix_query(text, is_query=True)
        result = list(self._model.embed([processed]))[0]
        return self._to_dense_list(result)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        # embed_batch() 在 add() 时调用,默认当作文档(不需要 query 前缀)
        self._ensure_model()
        processed = [self._maybe_prefix_query(t, is_query=False) for t in texts]
        results = list(self._model.embed(processed))
        return [self._to_dense_list(r) for r in results]

    def embed_query(self, text: str) -> List[float]:
        """显式的 query 嵌入接口,带 BGE 前缀。"""
        return self.embed(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """显式的文档嵌入接口,不带 BGE 前缀。"""
        return self.embed_batch(texts)

    def _to_dense_list(self, vec) -> List[float]:
        """fastembed 返回 numpy 数组,转纯 python list 供 JSON 序列化。"""
        if isinstance(vec, np.ndarray):
            return vec.astype(np.float32).tolist()
        return list(vec)


def quick_test():
    """冒烟测试:导入 + 嵌入 + 简单相似度计算。"""
    print(f"使用模型: BAAI/bge-small-zh-v1.5 (512 维)")
    fe = FastEmbedEmbedder()
    print(f"加载中(首次会下载 ~95MB ONNX 模型)...")
    v1 = fe.embed("今晚要提交论证活页")
    v2 = fe.embed("明天要交活页")  # 语义相近
    v3 = fe.embed("红烧肉很好吃")   # 语义无关
    print(f"维度: {fe.dim}")
    print(f"v1 长度: {len(v1)}")
    s12 = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
    s13 = np.dot(v1, v3) / (np.linalg.norm(v1) * np.linalg.norm(v3))
    print(f"相似度(活页 vs 活页): {s12:.4f}")
    print(f"相似度(活页 vs 红烧肉): {s13:.4f}")
    print(f"差距: {s12 - s13:.4f} (正值越大,语义分辨力越好)")


if __name__ == "__main__":
    quick_test()
