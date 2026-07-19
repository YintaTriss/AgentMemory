"""Test fact_extractor (new in v0.3+)"""
import pytest
import asyncio
from agent_memory.fact_extractor import (
    FactExtractor, FactType, extract_facts, _rule_extract, _LRUCache
)


# ---- FactType ----

def test_fact_type_constants():
    assert FactType.DECISION == "decision"
    assert FactType.PREFERENCE == "preference"
    assert FactType.PROJECT == "project"
    assert FactType.LEARNING == "learning"
    assert FactType.GENERAL == "general"


# ---- Rule extraction ----

def test_rule_extract_chinese_decision():
    # 10+ 字符 + 不同关键词
    text = "我决定把 VCP 默认上游改成 NewAPI，因为这样所有模型可以统一管理。\n\n项目目标是在 7 月底前完成。\n\n今天天气不错。"
    facts = _rule_extract(text)
    assert any("NewAPI" in f for f in facts)
    assert any("项目" in f for f in facts)
    # 天气不算决策/项目，应被过滤
    assert not any("天气" in f for f in facts)


def test_rule_extract_english_decision():
    facts = _rule_extract("I decided to use DeepSeek for our local AI agent system.")
    assert len(facts) >= 1
    assert any("DeepSeek" in f for f in facts)


def test_rule_extract_no_match():
    facts = _rule_extract("今天天气真好。我早上吃了个鸡蛋。")
    assert len(facts) == 0


def test_rule_extract_too_short():
    facts = _rule_extract("abc")
    assert facts == []


def test_rule_extract_empty():
    assert _rule_extract("") == []


# ---- LRU Cache ----

def test_lru_cache_basic():
    c = _LRUCache(capacity=3)
    c.put("a", 1)
    c.put("b", 2)
    c.put("c", 3)
    assert c.get("a") == 1
    c.put("d", 4)  # evicts 'b' (oldest)
    assert c.get("b") is None
    assert c.get("c") == 3
    assert c.get("d") == 4


def test_lru_cache_lru_order():
    c = _LRUCache(capacity=2)
    c.put("a", 1)
    c.put("b", 2)
    c.get("a")  # a becomes most recent
    c.put("c", 3)  # evicts 'b'
    assert c.get("a") == 1
    assert c.get("b") is None


# ---- FactExtractor rule mode ----

@pytest.mark.asyncio
async def test_extractor_rule_mode():
    ex = FactExtractor()
    text = "我决定使用 NewAPI。\n\n项目目标是在 7 月底完成。"
    facts = await ex.extract(text)
    assert len(facts) > 0
    assert all(isinstance(f, str) for f in facts)


@pytest.mark.asyncio
async def test_extractor_empty_content():
    ex = FactExtractor()
    assert await ex.extract("") == []


@pytest.mark.asyncio
async def test_extractor_caching():
    """Same content should be cached, second call should not re-run."""
    ex = FactExtractor()
    content = "我决定把项目切到新框架上。"  # 10+ chars

    f1 = await ex.extract(content)
    cache_size_after_first = len(ex._cache)

    f2 = await ex.extract(content)
    assert f1 == f2
    assert len(ex._cache) == cache_size_after_first


@pytest.mark.asyncio
async def test_extractor_batch():
    ex = FactExtractor()
    contents = [
        "I decided to use VCP for the memory subsystem.",
        "今天天气不错。",
        "项目目标明确：月底前完成所有迁移。",
    ]
    results = await ex.extract_batch(contents)
    assert len(results) == 3
    assert all(isinstance(r, list) for r in results)


@pytest.mark.asyncio
async def test_extractor_batch_with_cache_hits():
    ex = FactExtractor()
    content = "我决定使用 NewAPI 做统一接入。"
    await ex.extract(content)

    contents = [content, content, "项目目标是在本季度内完成。"]
    results = await ex.extract_batch(contents)
    assert len(results) == 3
    assert results[0] == results[1]


@pytest.mark.asyncio
async def test_extractor_invalidate_cache():
    ex = FactExtractor()
    await ex.extract("我决定测试缓存功能。")
    assert len(ex._cache) > 0
    ex.invalidate_cache()
    assert len(ex._cache) == 0


# ---- FactExtractor LLM mode (mock) ----

class _MockLLM:
    def __init__(self, response_text: str = "- fact one\n- fact two"):
        self.response_text = response_text
        self.call_count = 0

    async def chat(self, messages, **kwargs):
        self.call_count += 1
        class R:
            content = self.response_text
        return R()


@pytest.mark.asyncio
async def test_extractor_llm_mode():
    mock = _MockLLM()
    ex = FactExtractor(llm_client=mock)
    facts = await ex.extract("any content for testing here")
    assert facts == ["fact one", "fact two"]
    assert mock.call_count == 1


@pytest.mark.asyncio
async def test_extractor_llm_caching():
    mock = _MockLLM()
    ex = FactExtractor(llm_client=mock)
    await ex.extract("same content for caching test")
    await ex.extract("same content for caching test")
    assert mock.call_count == 1


@pytest.mark.asyncio
async def test_extractor_llm_fallback_on_error():
    class BrokenLLM:
        async def chat(self, messages, **kwargs):
            raise RuntimeError("API down")

    ex = FactExtractor(llm_client=BrokenLLM())
    facts = await ex.extract("我决定切换项目到 NewAPI。")
    # 失败 → fallback 到规则，应有 "决定" 命中
    assert len(facts) > 0
    assert any("NewAPI" in f for f in facts)


@pytest.mark.asyncio
async def test_extractor_llm_batch():
    """Batch should batch into single LLM call when possible.

    注：实现里 batch 的 LLM 输出按 ---ITEM--- 切分。LLM 通常会先输出
    preamble（被切到第一个空 chunk），然后是 item1/2/3。
    """
    # 6+ 字符的事实才能过 parse_lines 的长度过滤
    mock = _MockLLM(
        "preamble short\n"
        "---ITEM---\n"
        "- fact one alpha\n- fact one beta\n"
        "---ITEM---\n"
        "- fact two alpha\n"
        "---ITEM---\n"
        "- fact three alpha"
    )
    ex = FactExtractor(llm_client=mock)
    contents = ["c1", "c2", "c3"]
    results = await ex.extract_batch(contents)
    assert mock.call_count == 1
    assert len(results) == 3
    # 4 个 chunks、n=3 → 丢掉首段 preamble
    assert results[0] == ["fact one alpha", "fact one beta"]
    assert results[1] == ["fact two alpha"]
    assert results[2] == ["fact three alpha"]


# ---- Line parsing ----

def test_parse_lines_strips_prefixes():
    ex = FactExtractor()
    # 用 6+ 字符的行以避免长度过滤
    assert ex._parse_lines("- hello world") == ["hello world"]
    assert ex._parse_lines("* good morning") == ["good morning"]
    assert ex._parse_lines("• nice day today") == ["nice day today"]
    assert ex._parse_lines("1. one two three") == ["one two three"]
    assert ex._parse_lines("1) foo bar baz") == ["foo bar baz"]
    assert ex._parse_lines("1：hello world test") == ["hello world test"]


def test_parse_lines_filters_short():
    ex = FactExtractor()
    assert ex._parse_lines("- hi") == []  # too short
    assert ex._parse_lines("- this is a valid length line") == ["this is a valid length line"]
    assert ex._parse_lines("- ") == []  # empty after prefix


def test_parse_lines_filters_too_long():
    ex = FactExtractor()
    assert ex._parse_lines("- " + "a" * 500) == []  # > 400 chars


# ---- extract_facts (sync utility) ----

def test_extract_facts_sync():
    facts = extract_facts("我决定使用 NewAPI。")
    assert isinstance(facts, list)
    assert len(facts) >= 1
