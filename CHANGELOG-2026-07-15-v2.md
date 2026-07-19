# AgentMemory v2.1.0 — 2026-07-15 6 方向升级

> **做给主人看的**:`CHANGELOG-MARKET-COMPARISON-2026-07-15.md` 调研发现的差异化方向全部实现。
> 零回归、零 LLM 额外开销(纯启发式)、向后兼容。

---

## 🎯 总体成果

| 维度 | 前 | 后 |
|------|----|----|
| 全量测试 | 542 passed | **644 passed** (+102) |
| 跳过的旧测试 | 72 | 72 |
| Warnings | 186 | 189 |
| 总耗时 | ~130s | ~134s |
| 新模块 | — | 6 个 |
| 新 `MemoryManager` 方法 | — | 5 个 |

---

## 📋 6 个方向

### 方向 1-4: P0 差异化方向(已完成,详见上一版)

| # | 方向 | 模块 | 测试 | 完成 |
|---|------|------|------|------|
| 4 | Provenance 暴露 | `l1_lcm.py` | 11 | ✅ |
| 3 | Observations 命名 | `observations.py` | 14 | ✅ |
| 1 | 时间有效性 + 矛盾 | `contradiction.py` + `MemoryMeta` | 25 | ✅ |
| 2 | Temporal 召回 | `temporal.py` | 26 | ✅ |

### 方向 5: 梦境节奏自适应 ✅
**目标**:不再硬编码梦境阶段,根据系统状态自动决定跑哪个

**核心**:`DreamPhaseSelector` — 4 个决策信号 + 优先级
- **信号**:`memory_count` / `tag_density` / `last_rem_iso` / `emergent_tension`
- **优先级**:`rem > deep > light > skip`
- **决策理由**:每个决策都含人类可读 `reason` + 原始 `signals` (audit 用)
- **集成**:`MemoryManager.auto_dream(force=None)`

**为什么护城河**:Mem0/Zep/Letta 都是定时器调度,我们的状态自适应是差异化能力

### 方向 6: 梦境产物可追溯 ✅
**目标**:每个涌现节点 / 关联 / 隐式 tag 都能回答"为什么出现"

**核心**:`DreamProvenance` + `DreamProvenanceTracker`
- **数据结构**:每个产物记录 inputs / method / parameters / confidence / parent_artifacts / explanation
- **持久化**:JSONL 文件,可重载
- **追溯**:`trace_chain()` 递归上游产物(防环)
- **解释**:`explain(artifact_id)` 输出人类可读因果报告

**为什么护城河**:Mem0/Zep/Letta 全部是"黑盒自动聚合",我们是唯一能解释梦境产物因果的

**集成**:`MemoryManager.explain_artifact()` / `trace_artifact_chain()` / `record_dream_provenance()`

---

## 📁 文件清单

### 新增模块
| 文件 | 方向 | 行数 |
|------|------|------|
| `src/agent_memory/observations.py` | 3 | ~120 |
| `src/agent_memory/contradiction.py` | 1 | ~190 |
| `src/agent_memory/temporal.py` | 2 | ~210 |
| `src/agent_memory/dream_phase_selector.py` | **5** | ~190 |
| `src/agent_memory/dream_provenance.py` | **6** | ~230 |

### 新增测试
| 文件 | 测试数 |
|------|--------|
| `tests/test_observations.py` | 14 |
| `tests/test_provenance_integration.py` | 11 |
| `tests/test_temporal_validity.py` | 25 |
| `tests/test_temporal_recall.py` | 26 |
| `tests/test_dream_intelligence.py` | **26** |

---

## 🚀 用法

### 自动梦境调度
```python
# 自动选择阶段
result = mm.auto_dream()
print(result["decision"].phase)      # 'rem' | 'deep' | 'light' | 'skip'
print(result["decision"].reason)     # '涌现张力 0.85 ≥ 0.7,触发深度信号分解'
print(result["decision"].signals)    # {'memory_count': 100, 'tag_density': 0.5, ...}

# 强制指定
result = mm.auto_dream(force="deep")
```

### 梦境产物追溯
```python
# 记录涌现节点
mm.record_dream_provenance(
    artifact_id="emergent_001",
    artifact_type="emergent_node",
    phase="rem",
    inputs=["01ABC", "01DEF"],
    method="spike_routing",
    confidence=0.88,
    explanation="跨 2 跳从 2 个种子记忆涌现",
)

# 解释
print(mm.explain_artifact("emergent_001"))
# 输出:含 类型/阶段/置信度/方法/输入/上游产物的完整因果报告

# 追溯因果链
chain = mm.trace_artifact_chain("emergent_001")
# 返回从根到当前的因果链 Dict 列表
```

---

## 🎓 关键工程决策

1. **纯启发式优先于 LLM** — 6 个方向全零 LLM 调用,token 成本 = 0
2. **向后兼容** — 旧 API 路径不变,新能力全 opt-in
3. **测试驱动** — 每个方向先实现再写测试,**跑过才算完成**
4. **Windows Qdrant 文件锁绕过** — MemoryManager 测试用 `__new__` + AsyncMock
5. **可追溯性第一** — 每个新能力都考虑"为什么这样?"和"如何审计?"

---

## 📊 ROI

| 投入 | 产出 |
|------|------|
| 总耗时: ~15h | 6 个差异化方向 + 102 个新测试 + 全栈向后兼容 |
| 调研 2h | 差异化路线明确(梦境强化 + 时间维度 + 可追溯) |
| 零 LLM 额外成本 | 可服务 100% 用户场景(不依赖 API key) |

---

_作者:楚零 · 2026-07-15 13:25_