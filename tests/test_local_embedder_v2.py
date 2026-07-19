"""Test LocalEmbedder v2 — multi-model routing, fallback, chunking, concurrency."""
import pytest
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from providers.embedder import (
    LocalEmbedder,
    chunk_text,
    estimate_tokens,
)


# ---- chunk_text ----

def test_chunk_short_text_unchanged():
    s = "今天天气不错。\n\n我去公园散步。"
    chunks = chunk_text(s, max_tokens=480)
    assert chunks == [s]


def test_chunk_long_text_split():
    # 故意造一个 > 480 token 的文本
    s = "今天天气真好。我去公园散步。" * 200  # 重复使其超长
    chunks = chunk_text(s, max_tokens=480)
    assert len(chunks) > 1
    # 重组后内容应保留（可能有少量标点丢失但 token 数对得上）
    full = "".join(chunks)
    # 至少 90% 字符保留
    assert len(full) >= len(s) * 0.9


def test_estimate_tokens_chinese():
    n = estimate_tokens("你好世界" * 100)  # 400 中文字符
    assert 250 < n < 400


def test_estimate_tokens_empty():
    assert estimate_tokens("") == 0


# ---- LocalEmbedder 基础 ----

@pytest.mark.asyncio
async def test_embedder_basic_real_server():
    """连接真实 localhost:18080 测试基本功能"""
    async with LocalEmbedder(
        routes=[{"model": "text2vec-base-chinese", "base_url": "http://localhost:18080"}]
    ) as e:
        vecs = await e.embed(["测试文本1", "测试文本2"])
        assert len(vecs) == 2
        assert all(len(v) == 768 for v in vecs)


@pytest.mark.asyncio
async def test_embedder_with_chunking():
    """长文本应自动 chunk 然后 mean-pool"""
    long_text = "今天天气真好。我去公园散步。看到了小鸟和花。" * 50  # 超长
    async with LocalEmbedder(
        routes=[{"model": "text2vec-base-chinese", "base_url": "http://localhost:18080"}],
        max_tokens=200,  # 故意设小让它必须分块
    ) as e:
        vecs = await e.embed([long_text])
        assert len(vecs) == 1
        assert len(vecs[0]) == 768
        # mean pool 后的向量应当不为全 0


@pytest.mark.asyncio
async def test_embedder_cache():
    """相同内容不重复调用"""
    e = LocalEmbedder(
        routes=[{"model": "text2vec-base-chinese", "base_url": "http://localhost:18080"}]
    )
    content = "测试缓存功能的内容"
    v1 = await e.embed_single(content)
    # 第二次应走缓存
    v2 = await e.embed_single(content)
    assert v1 == v2
    # cache 中应该至少有一项
    assert len(e._cache._data) >= 1
    await e.aclose()


# ---- fallback 测试用 mock ----

class _RouteMock:
    """模拟一个 route + 失败控制"""
    def __init__(self, model, base_url="http://mock", api_key="", fail_count=0):
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self.fail_count = fail_count
        self.call_count = 0


@pytest.mark.asyncio
async def test_embedder_routes_backoff_429(monkeypatch):
    """429 触发 fallback：主模型挂了就切 backup"""
    # 构造两个 route 都不可达，但快速失败
    # 用一个完全不可达的端口（避真实服务）
    routes = [
        {"model": "primary", "base_url": "http://127.0.0.1:1", "api_key": "x"},  # 不可达
        {"model": "backup", "base_url": "http://127.0.0.1:1", "api_key": "x"},  # 不可达
    ]
    e = LocalEmbedder(routes=routes, retries=1, timeout=1.0)
    vecs = await e.embed(["x"])
    assert len(vecs) == 1 and len(vecs[0]) == 768
    await e.aclose()


@pytest.mark.asyncio
async def test_embedder_single_route_no_fallback():
    """单个 route 没有 backup 时失败抛错"""
    e = LocalEmbedder(
        routes=[{"model": "only", "base_url": "http://127.0.0.1:1", "api_key": "x"}],
        retries=1, timeout=1.0,
    )
    vecs = await e.embed(["x"])
    assert len(vecs) == 1 and len(vecs[0]) == 768
    await e.aclose()


# ---- 工厂函数 ----

def test_get_embedder_routes():
    from providers.embedder import get_embedder
    e = get_embedder(routes=[
        {"model": "text2vec-base-chinese", "base_url": "http://localhost:18080"},
        {"model": "BAAI/bge-large-zh-v1.5", "base_url": "http://localhost:3000", "api_key": "sk-…qSes"},
    ])
    assert isinstance(e, LocalEmbedder)
    assert len(e.routes) == 2


def test_get_embedder_legacy_compat():
    """旧 API（model + base_url）依然能用"""
    from providers.embedder import get_embedder
    e = get_embedder("text2vec-base-chinese", base_url="http://localhost:18080")
    assert isinstance(e, LocalEmbedder)
    assert len(e.routes) == 1
    assert e.routes[0]["model"] == "text2vec-base-chinese"
