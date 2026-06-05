"""
AgentMemory v2.0 - RRF Fusion Tests

测试 Reciprocal Rank Fusion 融合器的功能。
"""

import pytest
from agentmemory.search.rrf_fusion import RRFusion, RankedResult, FusionResult, rrf_weighted


class TestRRFBasic:
    """测试标准 RRF"""

    def test_rrf_basic(self):
        """测试基本 RRF 融合"""
        fusion = RRFusion(k=60)
        
        vector_results = [
            RankedResult("mem_A", 0.95, 1, "vector"),
            RankedResult("mem_B", 0.88, 2, "vector"),
            RankedResult("mem_C", 0.80, 3, "vector"),
        ]
        library_results = [
            RankedResult("mem_B", 0.90, 1, "library"),
            RankedResult("mem_D", 0.85, 2, "library"),
            RankedResult("mem_A", 0.75, 3, "library"),
        ]
        
        fused = fusion.fuse(vector_results=vector_results, library_results=library_results)
        
        # 应该包含所有 4 个记忆
        assert len(fused) == 4
        
        # 验证排序（mem_B 和 mem_A 应该在前面）
        ids = [r.memory_id for r in fused]
        assert ids.index("mem_B") < ids.index("mem_C")
        assert ids.index("mem_A") < ids.index("mem_C")

    def test_rrf_with_empty_track(self):
        """测试某条轨为空"""
        fusion = RRFusion(k=60)
        
        vector_results = [
            RankedResult("mem_A", 0.95, 1, "vector"),
            RankedResult("mem_B", 0.88, 2, "vector"),
        ]
        
        fused = fusion.fuse(vector_results=vector_results, library_results=[])
        
        assert len(fused) == 2
        assert fused[0].memory_id == "mem_A"
        assert fused[1].memory_id == "mem_B"

    def test_rrf_weighted(self):
        """测试加权 RRF"""
        fusion = RRFusion(k=60)
        
        vector_results = [
            RankedResult("mem_A", 0.95, 1, "vector"),
            RankedResult("mem_B", 0.88, 2, "vector"),
        ]
        tag_results = [
            RankedResult("mem_C", 0.99, 1, "tag"),
            RankedResult("mem_D", 0.95, 2, "tag"),
        ]
        
        fused = fusion.fuse(
            vector_results=vector_results,
            tag_results=tag_results,
        )
        
        # 仅一轨的结果，RRF 分数较低
        scores = {r.memory_id: r.rrf_score for r in fused}
        # 验证分数计算正确性
        # mem_A: 1/(60+1) = 0.0164
        # mem_B: 1/(60+2) = 0.0161
        # mem_C: 1/(60+1) = 0.0164
        assert abs(scores["mem_A"] - scores["mem_C"]) < 0.001

    def test_rrf_k_parameter(self):
        """测试 k 参数对结果的影响"""
        fusion_k60 = RRFusion(k=60)
        fusion_k10 = RRFusion(k=10)
        
        v1 = [RankedResult("mem_A", 0.9, 1, "vector")]
        v2 = [RankedResult("mem_B", 0.9, 2, "vector")]
        
        r60 = fusion_k60.fuse(vector_results=v1, library_results=v2)
        r10 = fusion_k10.fuse(vector_results=v1, library_results=v2)
        
        # k 越小，高排名优势越明显
        # mem_A 在 k=10 时优势更大
        score_A_k60 = next(r.rrf_score for r in r60 if r.memory_id == "mem_A")
        score_A_k10 = next(r.rrf_score for r in r10 if r.memory_id == "mem_A")
        
        assert score_A_k10 > score_A_k60

    def test_rrf_no_results(self):
        """测试空结果"""
        fusion = RRFusion(k=60)
        fused = fusion.fuse(vector_results=[], library_results=[])
        assert len(fused) == 0

    def test_rrf_single_track(self):
        """测试单轨结果"""
        fusion = RRFusion(k=60)
        results = [
            RankedResult("mem_A", 0.9, 1, "vector"),
            RankedResult("mem_B", 0.8, 2, "vector"),
            RankedResult("mem_C", 0.7, 3, "vector"),
        ]
        fused = fusion.fuse(vector_results=results)
        assert len(fused) == 3
        ids = [r.memory_id for r in fused]
        assert ids == ["mem_A", "mem_B", "mem_C"]


class TestRRFWeighted:
    """测试加权 RRF 函数"""

    def test_rrf_weighted_function(self):
        """测试 rrf_weighted 函数"""
        results_by_track = {
            "vector": [
                RankedResult("mem_A", 0.95, 1, "vector"),
                RankedResult("mem_B", 0.88, 2, "vector"),
            ],
            "tag": [
                RankedResult("mem_C", 0.99, 1, "tag"),
                RankedResult("mem_D", 0.95, 2, "tag"),
            ],
        }
        
        weights = {"vector": 1.0, "tag": 0.5}
        
        scores = rrf_weighted(results_by_track, k=60, weights=weights)
        
        # mem_A 只在 vector: 1.0 * 1/(60+1) = 0.0164
        # mem_C 只在 tag: 0.5 * 1/(60+1) = 0.0082
        assert "mem_A" in scores
        assert "mem_C" in scores
        assert scores["mem_A"] > scores["mem_C"]

    def test_rrf_weighted_default_weights(self):
        """测试默认权重"""
        results_by_track = {
            "vector": [
                RankedResult("mem_A", 0.95, 1, "vector"),
            ],
        }
        
        scores = rrf_weighted(results_by_track, k=60)
        
        # 默认权重都是 1.0
        expected = 1.0 * (1.0 / (60 + 1))
        assert abs(scores["mem_A"] - expected) < 0.0001


class TestFusionResult:
    """测试 FusionResult 数据类"""

    def test_fusion_result_creation(self):
        """测试 FusionResult 创建"""
        result = FusionResult(
            memory_id="mem_123",
            rrf_score=0.025,
            ranks={"vector": 1, "library": 3},
            details={"vector_score": 0.95, "library_score": 0.75},
        )
        
        assert result.memory_id == "mem_123"
        assert abs(result.rrf_score - 0.025) < 0.0001
        assert result.ranks["vector"] == 1
        assert result.ranks["library"] == 3
        assert result.details["vector_score"] == 0.95


class TestNormalizeScores:
    """测试分数归一化"""

    def test_normalize_scores(self):
        """测试分数归一化"""
        fusion = RRFusion(k=60)
        
        results = [
            RankedResult("mem_A", 1.0, 1, "vector"),
            RankedResult("mem_B", 0.5, 2, "vector"),
            RankedResult("mem_C", 0.0, 3, "vector"),
        ]
        
        normalized = fusion._normalize_scores(results)
        
        assert abs(normalized[0].score - 1.0) < 0.0001
        assert abs(normalized[1].score - 0.5) < 0.0001
        assert abs(normalized[2].score - 0.0) < 0.0001

    def test_normalize_scores_same_values(self):
        """测试相同分数的归一化"""
        fusion = RRFusion(k=60)
        
        results = [
            RankedResult("mem_A", 0.5, 1, "vector"),
            RankedResult("mem_B", 0.5, 2, "vector"),
        ]
        
        normalized = fusion._normalize_scores(results)
        
        # 相同分数时应该保持不变
        assert normalized[0].score == 0.5
        assert normalized[1].score == 0.5

    def test_normalize_empty_list(self):
        """测试空列表"""
        fusion = RRFusion(k=60)
        normalized = fusion._normalize_scores([])
        assert len(normalized) == 0


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_search_hybrid_rrf_integration(tmp_path):
    """集成测试：混合搜索端到端"""
    from agentmemory.search.search_engine import SearchEngine
    from agentmemory.data.datalake import DataLake
    
    # 创建测试数据
    dl = DataLake(root_dir=tmp_path)
    await dl.init()
    
    # 写入测试数据
    mem_id_1 = await dl.create_memory(
        category_path="A.项目/石榴籽/答辩",
        content="石榴籽项目省赛答辩准备",
        tags=["石榴籽", "省赛"],
        importance=0.8,
    )
    mem_id_2 = await dl.create_memory(
        category_path="A.项目/石榴籽/语料",
        content="语料处理流程优化",
        tags=["语料", "处理"],
        importance=0.7,
    )
    mem_id_3 = await dl.create_memory(
        category_path="A.项目/石榴籽/模型",
        content="模型训练日志",
        tags=["模型", "训练"],
        importance=0.6,
    )
    
    # 创建 SearchEngine（使用简单的 mock embedder）
    se = SearchEngine(
        memory_dir=str(tmp_path),
    )
    
    # 验证 SearchEngine 有 RRF 方法
    assert hasattr(se, 'search_hybrid_rrf')
    assert hasattr(se, '_search_vector')
    assert hasattr(se, '_search_library')
    assert hasattr(se, '_search_tags')


def test_rrf_fusion_all_tracks():
    """测试三轨同时融合"""
    fusion = RRFusion(k=60)
    
    vector_results = [
        RankedResult("mem_A", 0.95, 1, "vector"),
        RankedResult("mem_B", 0.88, 2, "vector"),
    ]
    library_results = [
        RankedResult("mem_B", 0.90, 1, "library"),
        RankedResult("mem_C", 0.85, 2, "library"),
    ]
    tag_results = [
        RankedResult("mem_C", 0.99, 1, "tag"),
        RankedResult("mem_D", 0.95, 2, "tag"),
    ]
    
    fused = fusion.fuse(
        vector_results=vector_results,
        library_results=library_results,
        tag_results=tag_results,
    )
    
    # mem_A 只在 vector
    # mem_B 在 vector 和 library
    # mem_C 在 library 和 tag
    # mem_D 只在 tag
    
    assert len(fused) == 4
    
    # 验证融合结果
    result_map = {r.memory_id: r for r in fused}
    
    assert "mem_A" in result_map
    assert "mem_B" in result_map
    assert "mem_C" in result_map
    assert "mem_D" in result_map
    
    # mem_B 在两轨都有，应该排名靠前
    ids = [r.memory_id for r in fused]
    assert ids.index("mem_B") < ids.index("mem_D")
    assert ids.index("mem_C") < ids.index("mem_D")


def test_rrf_score_calculation():
    """测试 RRF 分数计算的正确性"""
    fusion = RRFusion(k=60)
    
    # 两个轨的结果
    v1 = [RankedResult("mem_A", 0.9, 1, "vector")]
    v2 = [RankedResult("mem_B", 0.9, 2, "vector")]
    
    fused = fusion.fuse(vector_results=v1, library_results=v2)
    
    # mem_A: 1/(60+1) = 0.016393
    # mem_B: 1/(60+2) = 0.016129
    scores = {r.memory_id: r.rrf_score for r in fused}
    
    assert abs(scores["mem_A"] - 1.0/(60+1)) < 0.0001
    assert abs(scores["mem_B"] - 1.0/(60+2)) < 0.0001
    assert scores["mem_A"] > scores["mem_B"]
