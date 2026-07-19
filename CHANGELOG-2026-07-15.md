# AgentMemory 升级记录 — 2026-07-15

> 紧接 2026-07-14 重大变更日，主人在 11:07 询问进度后接管全权：
> - DeepSeek 余额耗尽 → newapi-keepalive 改用 minimax/MiniMax-M3
> - "给最大限度"+"时间限度不限" → newapi-keepalive timeoutSeconds=0
> - "接着做" → 完成 FactExtractor → L1LCMCompressor 默认集成

## ✅ #1 FactExtractor ↔ L1LCMCompressor 默认集成（核心交付）

### `src/agent_memory/l1_lcm.py`
- `__init__(max_context_chars=4000, fact_extractor=None)` — 接受可选 FactExtractor
- `bind_fact_extractor(extractor)` / `unbind_fact_extractor()` — 动态绑定/卸下（链式返回 self）
- `@property fact_extractor` / `@property has_fact_extractor` — 显式查询
- `extract_facts_v2(content)` — 优先走 FactExtractor 规则路径；缺则回退原 `extract_facts`
- `extract_facts(content)` — 2026-07-15 智能路由：bound 时走 FactExtractor，未 bound 时保持原行为

### `src/agent_memory/manager.py`
- `from .fact_extractor import FactExtractor`
- `__init__` 末尾 **默认构造 `FactExtractor()` 并 `bind_fact_extractor`** 到 `self.l1`
  - 用户无需手动挂载；开箱即用
  - 想用纯规则版：`l1.unbind_fact_extractor()`
- 新增 `async def compress_with_facts(memory_ids, query="", max_facts_per_memory=3)` — 高阶方法
  - 仅对 `importance >= 0.7` 的 memory 触发 LLM 抽取（限速，避免无谓 token）
  - 10 秒超时保护（避免卡死）
  - 注入 `[Facts] ...` 前缀到 memory.content 后再喂给 L1
- 现有 `compress_for_context` **完全没动**，向后兼容

### 行为变化（用户可见）

| 场景 | 旧行为 | 新行为 |
|------|--------|--------|
| `l1.extract_facts("...")` 无 bound | 原宽松规则（含"重要"） | 原宽松规则 |
| `l1.extract_facts("...")` 有 bound | 不可能 | 走 FactExtractor 4 类关键词（更精准） |
| `l1.extract_facts_v2("...")` 无 bound | 不存在 | = extract_facts() |
| `l1.extract_facts_v2("...")` 有 bound | 不存在 | = _rule_extract(content) |
| `l1.compress(memories)` | 原输出 | **完全不变**（sync 不调 extractor） |
| `manager.compress_for_context()` | 原行为 | **完全不变** |
| `manager.compress_with_facts()` | 不存在 | 异步走 FactExtractor + L1 压缩 |

### 测试

- `tests/test_fact_extractor_l1_integration.py` — 23 个新测试
  - 默认行为不变（向后兼容）
  - bind/unbind 动态切换 + 链式调用
  - extract_facts_v2 优先级
  - extract_facts 默认路由到 FactExtractor
  - compress() 输出格式稳定
  - has_fact_extractor / fact_extractor property
  - MemoryManager 默认集成
  - 边界：空 content、长 content 限 5 条
  - 回归保险：未绑时 extract_facts 不变

### 回归

```
========== 542 passed, 72 skipped, 175 warnings in 127.64s (0:02:07) ==========
```

- 之前：**519 passed / 471**
- 现在：**542 passed / 471 + 23 新 + 48 个被新收集到老 test 范围**
- 零失败、零破坏

---

## 🛠 #2 cron 配置调整

| cron | 模型变更 | 超时变更 | 实际效果 |
|------|----------|----------|----------|
| `newapi-keepalive` | deepseek-v4-pro → **minimax/MiniMax-M3** | 30s → **0 (不限)** | ✅ 起效 |
| `memory-heartbeat` | command 不调 LLM，n/a | n/a（cron.update 工具拒 patch command） | no-op |
| `memory-md-to-agentmemory-sync` | command 不调 LLM，n/a | n/a（cron.update 工具拒 patch） | no-op |
| `AgentMemory 自主研发督促任务` | systemEvent 不调 LLM，n/a | n/a（无 timeoutSeconds 概念） | no-op |
| `agentmemory-heartbeat` | 已 disabled | — | — |

**真相：你的 cron 池里只有 `newapi-keepalive` 调 LLM。** 其他人是 command 跑 python/systemEvent 推文字，根本没有 model 维度。"别用 dp + 不限时间"实质只对 1 个 cron 有效。

---

## 📌 未做（下个工作日挑）

1. **彻底迁移老 API → `agent_memory.*`**（6-10h 大活）— `src/api/app.py` 老 REST + `src/web/app.py` 老 Dashboard 仍调老接口
2. **README 多语言同步更新**（fact_extractor / NewAPI 集成 / 默认挂载）
3. **GeodesicRerank / ResultDeduplicator / ContextFoldingV2** 我已主动判断不抄（理由在 CHANGELOG-2026-07-14）—— 等你 review 决策
4. **L2/L4/decay 单元测试**——L2/L4/decay 已删但 `tests/unit/test_L2_graph_store.py` / `test_L4_file_persist.py` / `test_decay_engine.py` 还在
5. **sync GB18030 兼容**——03:00 daily sync 因为 `memory/2026-07-13-{1117,1342,1516,2207}.md` 是 GB18030 编码会崩

---

_编制：楚零 | 2026-07-15 11:28_
