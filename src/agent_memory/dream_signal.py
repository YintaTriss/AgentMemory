"""
dream_signal.py — 梦境 Phase 1: 信号分解

对标 VCP 的 EPA 模块 + 残差金字塔。
- EPA 投影: K-Means → 加权 SVD → 逻辑深度/共振/世界观
- 残差金字塔: 递归 Gram-Schmidt 正交分解
- 握手特征分析: 方向一致性/内部张力/新颖度
"""
from __future__ import annotations

import numpy as np
from typing import Dict, List, Optional, Tuple


class SignalDecomposer:
    """梦境信号分解器"""

    def __init__(self, n_components: int = 10, n_clusters: int = 8):
        self.n_components = n_components
        self.n_clusters = n_clusters
        self._centroids: Optional[np.ndarray] = None
        self._basis: Optional[np.ndarray] = None
        self._mean: Optional[np.ndarray] = None
        self._labels: Optional[List[str]] = None

    # ========== EPA: K-Means + SVD ==========

    def fit_epa(self, tag_vectors: np.ndarray, tag_names: Optional[List[str]] = None):
        """训练 EPA 模型：K-Means 聚类 + SVD 主成分。"""
        n = len(tag_vectors)
        if n < self.n_clusters:
            self.n_clusters = max(2, n)
        k = min(self.n_clusters, n)

        # Forgy 初始化
        import random
        indices = random.sample(range(n), k)
        self._centroids = tag_vectors[indices].copy()

        # 迭代收敛
        for _ in range(20):
            sims = tag_vectors @ self._centroids.T
            labels = np.argmax(sims, axis=1)
            changed = False
            for j in range(k):
                mask = labels == j
                if mask.sum() > 0:
                    new_centroid = tag_vectors[mask].mean(axis=0)
                    new_centroid /= np.linalg.norm(new_centroid) + 1e-8
                    if not np.allclose(self._centroids[j], new_centroid, atol=1e-4):
                        changed = True
                    self._centroids[j] = new_centroid
            if not changed:
                break

        # 加权 SVD via power iteration
        # Weighted Gram matrix: G = X_centered W X_centered^T
        mean = np.average(tag_vectors, axis=0)
        centered = tag_vectors - mean

        n_comp = min(self.n_components, n, centered.shape[1])
        rng = np.random.default_rng(42)
        components = rng.standard_normal((centered.shape[1], n_comp)).astype(np.float32)

        for _ in range(5):
            components = centered.T @ (centered @ components)
            components /= np.linalg.norm(components, axis=0) + 1e-8

        self._basis = components.T  # (n_comp, dim)
        self._mean = mean  # 保存均值用于投影去中心化
        self._labels = tag_names or [f"axis_{i}" for i in range(n_comp)]
        return self

    def project(self, vector: np.ndarray) -> Dict:
        """EPA 投影分析：计算逻辑深度 + 跨域共振。"""
        if self._basis is None:
            return {"logic_depth": 0.5, "resonance": 0.0, "dominant_axes": [], "entropy": 1.0}

        # 去中心化（对标 VCP EPAModule.js:98-100）
        if hasattr(self, '_mean') and self._mean is not None:
            centered = vector - self._mean
        else:
            centered = vector

        projs = self._basis @ centered  # (n_comp,)
        energy = projs ** 2
        total_energy = energy.sum()
        if total_energy < 1e-10:
            return {"logic_depth": 0.0, "resonance": 0.0, "dominant_axes": [], "entropy": 1.0}

        # 投影概率 + 熵
        probs = energy / total_energy
        entropy = -np.sum(probs * np.log2(probs + 1e-10))
        max_entropy = np.log2(self.n_components)
        norm_entropy = entropy / max_entropy if max_entropy > 0 else 1.0
        logic_depth = 1.0 - norm_entropy

        # 主成分轴
        idx_sorted = np.argsort(-energy)
        dominant = []
        for i in idx_sorted[:3]:
            if energy[i] > 0.01:
                dominant.append({
                    "label": self._labels[i] if self._labels and i < len(self._labels) else f"axis_{i}",
                    "energy": float(energy[i]),
                })

        # 跨域共振
        resonance = 0.0
        bridges = []
        for i in range(min(3, len(dominant))):
            for j in range(i + 1, min(3, len(dominant))):
                co_activation = np.sqrt(dominant[i]["energy"] * dominant[j]["energy"])
                if co_activation > 0.15:
                    bridges.append({
                        "from": dominant[i]["label"],
                        "to": dominant[j]["label"],
                        "strength": float(co_activation),
                    })
                    resonance += co_activation

        return {
            "logic_depth": float(logic_depth),
            "resonance": float(min(1.0, resonance)),
            "entropy": float(norm_entropy),
            "dominant_axes": dominant,
            "bridges": bridges,
        }

    # ========== 残差金字塔: Gram-Schmidt ==========

    def decompose(self, query: np.ndarray, tag_vectors: np.ndarray,
                  max_levels: int = 5, top_k: int = 10,
                  energy_threshold: float = 0.9) -> Dict:
        """
        残差金字塔分解。

        Returns:
            levels: 每层分解结果
            total_coverage: 总解释率
            residual: 最终残差向量
            features: 金字塔特征
        """
        dim = len(query)
        levels = []
        basis = []
        projection = np.zeros(dim, dtype=np.float32)
        residual = query.copy()
        orig_energy = float(np.linalg.norm(query) ** 2)

        for level in range(max_levels):
            # 搜索当前残差最近的标签
            norm_residual = residual / (np.linalg.norm(residual) + 1e-8)
            sims = tag_vectors @ norm_residual
            top_indices = np.argsort(-sims)[:top_k]

            level_projection = np.zeros(dim, dtype=np.float32)
            level_tags = []
            for idx in top_indices:
                v = tag_vectors[idx].copy()
                # Gram-Schmidt 正交化
                for u in basis:
                    v -= np.dot(v, u) * u
                mag = float(np.linalg.norm(v))
                if mag > 1e-6:
                    u = v / mag
                    basis.append(u)
                    coeff = float(np.dot(residual, u))
                    level_projection += coeff * u
                    level_tags.append({
                        "index": int(idx),
                        "coeff": coeff,
                        "energy": coeff ** 2,
                    })

            projection += level_projection
            residual = query - projection

            residual_energy = float(np.linalg.norm(residual) ** 2)
            level_energy = float(np.linalg.norm(level_projection) ** 2)
            coverage = 1.0 - residual_energy / orig_energy if orig_energy > 0 else 1.0

            levels.append({
                "level": level,
                "tags": level_tags,
                "energy_explained": level_energy / orig_energy if orig_energy > 0 else 0.0,
                "coverage": coverage,
            })

            if coverage >= energy_threshold:
                break

        # 握手特征分析
        handshake = self._analyze_handshakes(levels, tag_vectors)

        # 金字塔特征
        features = self._extract_features(levels, handshake, orig_energy)

        return {
            "levels": levels,
            "total_coverage": float(coverage),
            "residual_norm": float(np.linalg.norm(residual)),
            "handshake": handshake,
            "features": features,
        }

    def _analyze_handshakes(self, levels: List[Dict], tag_vectors: np.ndarray) -> Dict:
        """握手差值分析。"""
        all_coeffs = []
        for lv in levels:
            for t in lv["tags"]:
                all_coeffs.append(t["coeff"])

        if not all_coeffs:
            return {"direction_coherence": 0.0, "pattern_strength": 0.0,
                    "novelty_signal": 0.0, "noise_signal": 0.0}

        coeffs = np.array(all_coeffs)
        if len(coeffs) > 1:
            direction_coherence = float(np.std(coeffs) / (np.mean(np.abs(coeffs)) + 1e-8))
            pattern_strength = float(np.mean(np.abs(coeffs - coeffs.mean())))
        else:
            direction_coherence = 1.0
            pattern_strength = 0.5

        novelty = direction_coherence * (1 - pattern_strength)
        noise = (1 - direction_coherence) * (1 - pattern_strength)

        return {
            "direction_coherence": min(1.0, direction_coherence),
            "pattern_strength": min(1.0, pattern_strength),
            "novelty_signal": min(1.0, novelty),
            "noise_signal": min(1.0, noise),
        }

    def _extract_features(self, levels: List[Dict], handshake: Dict,
                         orig_energy: float) -> Dict:
        """金字塔特征提取。"""
        coverage = levels[-1]["coverage"] if levels else 0.0
        coherence = handshake.get("pattern_strength", 0)
        residual_ratio = 1.0 - coverage
        novelty = residual_ratio * 0.7 + handshake.get("novelty_signal", 0) * 0.3
        noise = handshake.get("noise_signal", 0)

        return {
            "depth": len(levels),
            "coverage": coverage,
            "novelty": novelty,
            "coherence": coherence,
            "tag_memo_activation": coverage * coherence * (1 - noise),
            "expansion_signal": novelty,
        }
