# AgentMemory v2.1.0 市面对比与升级方向

> 日期: 2026-07-15
> 调研对象: **Mem0** / **Zep** / **Letta** / **VCP** (内部对标)
> 资料来源: docs.mem0.ai, getzep.com, docs.letta.com, VCP JavaScript 源码(已对标)

---

## 1. 架构概览

| 系统 | 架构范式 | 存储层 | 关键创新 |
|------|---------|--------|---------|
| **AgentMemory (我们)** | 四层闭环 + 梦境子系统 | L4 文件 + L3 Qdrant + SQLite WAL | Spike Routing + 残差金字塔梦境 |
| **Mem0** | SQL + Vector + Graph 三轨 | 任意组合(OSS 自管 / Platform 托管) | 自动矛盾检测 + Temporal 评分 |
| **Zep** | Context Graph Engine(专利) + Context Lake | Temporal Graph + 行级 ACL | 时间有效性 + 自动 invalidate |
| **Letta** | Memory blocks + Archival | Postgres + pgvector | Stateful agent + Memory-first |
| **VCP** | TagMemo v3.7 波浪算法 + Spike Routing | SQLite + JSON + FS | EPA + Spike + 共现矩阵(范式源头) |

---

## 2. 写入路径对比

| 系统 | 写入步骤 | LLM 调用次数 |
|------|----------|------------|
| **AgentMemory** | L1LCM 压缩 → 4 文件存储 + Qdrant 嵌入 → SQLite 元数据 | 0~2(FactExtractor 可选) |
| **Mem0** | Context lookup → Fact extraction → Deduplication → Embedding → Entity linking | **5 次**(5 LLM 步骤全部调) |
| **Zep** | Episode 写入 → 自动 Fact extract → Temporal 标注 → 矛盾检查 → invalidate 旧事实 | **3-5 次** |
| **Letta** | Block update(LLM 重写) + Archival insert + Embedding | **2-3 次** |
| **VCP** | Tag 提取 → 共现矩阵更新 → Spike 触发 → 残差存储 | **0-1 次** |

**我们的优势**:
- ✅ LLM 调用次数最少(0~2 vs Mem0 的 5 次)
- ✅ 完全可离线(rule-based fallback)

**我们的劣势**:
- ❌ 没有矛盾自动检测 — 用户说"我从 Austin 搬到 Seattle"后,我们并存两条事实,而 Mem0/Zep 会自动 invalidate
- ❌ 没有 entity linking(Mem0 默认开启)

---

## 3. 读取路径对比

| 系统 | 召回路径 | 时间查询能力 | 性能基线 |
|------|----------|------------|---------|
| **AgentMemory** | Fuzzy → BM25 → Vector → Reranker → 加权融合 | ❌ 仅 created_at 排序 | 全量 in-memory(~10ms @ 1k) |
| **Mem0** | Semantic + Keyword + Entity + **Temporal** 4 路融合 | ✅ "when did I..." 类型查询 | managed |
| **Zep** | Graph traversal + semantic + temporal | ✅ 强(核心卖点) | **p95 < 200ms @ 100M graph** |
| **Letta** | Block read(快)+ Archival vector search | ✅(块版本化) | hosted |
| **VCP** | Tag match + 共现 + Spike | ❌ | 本地 + 内存 |

**核心差距**: **Temporal 召回**。

我们现在只能"按创建时间排序",无法回答:
- "去年我说我想换什么手机?"
- "我在搬到 Seattle 之前住在哪?"

---

## 4. 关键差异化特性对比

### 4.1 时间有效性 (Temporal Validity)

| 系统 | 实现 |
|------|------|
| Zep | ✅ 核心卖点:`Valid: 2024-11-14 — present`,旧事实保留为历史 |
| Mem0 | ✅ Temporal scoring 信号 |
| Letta | ✅ Memory blocks 版本化 |
| **AgentMemory** | ❌ **最大缺口** |

### 4.2 矛盾处理 (Invalidation)

| 系统 | 实现 |
|------|------|
| Zep | ✅ "Robbie 不再穿 Adidas" → 自动 invalidate "Robbie 喜欢 Adidas" 但保留历史 |
| Mem0 | ⚠️ 部分(additive extraction + 显式 update/delete) |
| Letta | ✅ Block update 自动覆盖 |
| **AgentMemory** | ❌ **最大缺口** |

### 4.3 观察 / 模式 (Observations)

| 系统 | 实现 |
|------|------|
| Zep | ✅ "Jane 在过去三次产品发布后 2 周内都升级" — 自动分析图结构产生 |
| Mem0 | ❌ |
| Letta | ❌ |
| **AgentMemory** | ⚠️ **部分**:Spike Routing 的"涌现节点"在功能上等价,但未命名 + 未在 prompt 暴露 |

### 4.4 Provenance(出处追溯)

| 系统 | 实现 |
|------|------|
| Zep | ✅ 每个 fact 可追溯到源 episode |
| Mem0 | ✅ metadata filter |
| Letta | ✅ block history |
| **AgentMemory** | ⚠️ L4 `.meta.json` 存了 source,但 `compress_for_context` 没暴露 |

### 4.5 治理 (Governance)

| 系统 | 实现 |
|------|------|
| Zep | ✅ **企业级**:ABAC + 保留策略 + 法律冻结 + 审计 |
| Mem0 | ✅ user/agent/run scope |
| Letta | ✅ Permissions + retention |
| **AgentMemory** | ⚠️ namespace 隔离(已实现)+ ACL/retention/audit 未实现 |

---

## 5. 性能对比

| 规模 | AgentMemory | Mem0 OSS | Zep |
|------|-------------|----------|-----|
| 1k memories | <10ms | ~50ms | n/a |
| 10k | ~50ms | ~200ms | **148ms (p95)** |
| 100k | ~200ms(estimated) | ~500ms | **152ms** |
| 1M | ⚠️ 待测 | ⚠️ 待测 | **156ms** |
| 100M | ❌ 无数据 | ❌ 无数据 | **168ms** |

**Zep 规模化优势明显** — 但他们是 Rust + Go + Cloud,我们是 Python + numpy + 本地。

---

## 6. 升级方向(按价值/成本比)

### 🎯 P0 — 最高价值,直接借鉴

#### 方向 1: 时间有效性 + 自动矛盾处理
**价值**: 解决我们最大的差异化缺口
**成本**: 中(2-3h 编码 + 1h 测试 + 1h docs)
**参考**: Zep Temporal Context Graph

**实施**:
```python
# 新增到 L4 .meta.json schema
{
  "id": "...",
  "content": "我住在 Seattle",
  "meta": {
    "valid_from": "2026-07-15T00:00:00Z",
    "valid_until": null,          # null = 当前有效
    "invalidated_by": null,        # 指向使其失效的新事实 ID
    "supersedes": ["mem_old_addr"], # 反向链
    ...
  }
}

# FactExtractor 增强
async def extract_with_invalidation(content, llm_client):
    new_facts = await llm_extract(content)
    for fact in new_facts:
        if contradicts_with_existing(fact):
            mark_invalid(fact.supersedes_id, valid_until=now())
    return new_facts
```

#### 方向 2: Temporal 召回(读取路径增强)
**价值**: 让 agent 能回答"去年我说..."
**成本**: 低(2h 编码 + 1h 测试)

**实施**:
- SearchPipeline 加 `temporal_intent` 信号(检测 query 是否含"去年/上个月/那时")
- 重排时考虑 `valid_from/until`
- `compress_for_context` 在 facts 段标注"what's true now"

### 🎯 P1 — 高价值,需较多投入

#### 方向 3: Observations(模式检测)
**价值**: 自动产生"Jane 总在发布后 2 周升级"这种高级洞察
**成本**: 高(4-6h,需要 graph mining 算子)
**参考**: Zep Observations

**实施**:
- 把 `dream_graph.py` 的"涌现节点"机制单独抽出 → `ObservationsGenerator`
- 周期性跑(每周 / 每次添加 100+ 事实时)
- 在 prompt 里以"Patterns"段呈现

#### 方向 4: Provenance 强化
**价值**: 透明性 + 信任
**成本**: 低(1h 编码 + 1h 测试)

**实施**:
- `compress_for_context` 输出格式:
```
## Key Facts (来源标注)
- [Decision] 我决定改用 NewAPI [Source: openclaw-webchat, 2026-07-15 11:12]
- [Project] 梦境子系统对标 VCP TagMemo v3.7 [Source: openclaw-webchat, 2026-07-14 23:25]
```

### 🎯 P2 — 长期建设

#### 方向 5: 多租户治理 (Tenancy)
**价值**: 企业级部署必要
**成本**: 高(8-12h)

**实施**: 新增 `agent_memory.tenancy`:
- `RetentionPolicy` (auto-expire)
- `LegalHold` (冻结删除)
- `AuditLog` (操作追溯)
- ABAC (attribute-based access control)

### 🎯 P3 — 性能对标

#### 方向 6: 大规模性能
**价值**: 100k+ memories 时的延迟
**成本**: 高(需要 Rust 引擎或 C 扩展)

**注意**: 我们现在全量 in-memory + numpy,10k 以下场景足够。
**短期不抄**: Rust VexusIndex — 我们走 Python numpy 路线,接受性能上限。

---

## 7. 我们的差异化战略(对标结论)

我们不应该全盘抄 Mem0/Zep/Letta。**我们的护城河是"梦境子系统"** —— 这是 4 家里**唯一**的。

**保留并强化**:
- ✅ Spike Routing 图传播
- ✅ 残差金字塔 + EPA 投影
- ✅ 梦境 4 阶段编排

**借鉴补齐**:
- 🔄 **时间有效性**(方向 1) — 必须做
- 🔄 **Temporal 召回**(方向 2) — 必须做
- 🔄 **Observations 命名 + 暴露**(方向 3 精简版) — 应做

**暂不做**:
- ⏸️ 企业级 ABAC / 审计 — 个人项目 + 学术研究场景不需要
- ⏸️ Rust 引擎 — Python numpy 已经够用,资源花在差异化特性上
- ⏸️ Mem0 那种 5 步 LLM 流水线 — token 成本不划算

---

## 8. 推荐 Roadmap(未来 2 周)

| 周次 | 任务 | 工时 |
|------|------|------|
| 第 1 周 | 方向 1 + 方向 2(时间有效性 + Temporal 召回) | 6h |
| 第 1 周 | 方向 4(Provenance 暴露) | 2h |
| 第 2 周 | 方向 3 精简版(Observations 命名 + 暴露) | 4h |
| 第 2 周 | 新 benchmark(LoCoMo / MSC / NarrativeRecall) | 4h |

**完成后的 AgentMemory v3.0 定位**:
- 记忆 = 事实 + 时间有效性 + 出处追溯 + 模式观察
- 4 层架构 = 写入(LLM 抽 fact + 自动 invalidation) + 读取(4 路召回 + Temporal) + 整合(梦境 + Observations)

---

## 9. 参考资料

- Mem0 Core Concepts: https://docs.mem0.ai/core-concepts
- Zep Architecture: https://www.getzep.com
- Letta Agent Memory: https://docs.letta.com/letta-agent
- VCP 记忆系统源码: `D:\vcp\modules\KnowledgeBaseManager.js` 等
- 调研者: 楚零
- 调研日期: 2026-07-15 11:43