---
name: agentmemory
version: 1.0.0
family: symphony
role: memory-center
description: 交响乐技能家族 - 顶尖记忆系统，融合 Hermes + Mem0 优点，四层闭环记忆架构
---

# agentmemory 顶尖记忆技能

> 交响乐技能家族成员 | 融合 Hermes 记忆机制 + Mem0 混合检索 + 四层闭环架构

## 一键启用

```bash
cd skills/agentmemory
pip install -e .
```

然后直接使用 CLI 命令，或在 Python 中导入使用。

---

## CLI 命令（开箱即用）

```bash
# 查看各层状态
agentmemory layer-status

# 存储记忆
agentmemory store "用户参加了石榴籽省赛" --importance 0.8

# 查询记忆（混合检索：BM25 + 重要性）
agentmemory query "石榴籽项目" --limit 5

# 预取相关记忆（后台缓存）
agentmemory prefetch "优优的项目"

# 遗忘指定记忆
agentmemory forget <memory_id>

# 对话轮次同步（LLM 自动事实提取）
agentmemory sync-turn "用户说省赛结果出了" "助手回复恭喜"

# 会话结束总结
agentmemory session-end --summary "讨论了石榴籽项目进展"

# 遗忘引擎检查（心跳触发）
agentmemory decay-check

# 记忆系统统计
agentmemory stats

# 通用动作接口（兼容 AgentSymphony）
agentmemory execute store '{"text":"内容","importance":0.8}'
```

---

## 四层闭环架构

```
L1: LCM 压缩层（对话 → 关键事实）
    └── LLM 提取事实，不存原始对话

L2: Graph 图谱层（事实 → 实体关系）
    └── 实体（人名/项目）+ 关系 + 属性

L3: Vector 向量层（混合检索）
    └── BM25(60%) + 重要性(30%) + 访问频率(10%)

L4: Files 持久化层（记忆归档）
    └── MEMORY.md + 每日日记 memory/

遗忘引擎：评分 = 访问频率×0.3 + 重要性×0.3 + 时效性×0.4
```

---

## Python API

```python
from skills.agentmemory.src.memory_manager import MemoryHermes

mh = MemoryHermes()

# 存储记忆
memory_id = await mh.store(
    "用户参加了石榴籽省赛",
    metadata={"source": "conversation"},
    importance=0.8
)

# 查询记忆
results = await mh.query("石榴籽", limit=5)
for r in results:
    print(f"[{r['score']:.2f}] {r['content']}")

# 对话轮次同步
facts = await mh.sync_turn(
    "用户说省赛结果出了",
    "助手回复恭喜"
)

# 遗忘
await mh.forget(memory_id)

# 统计
stats = mh.get_stats()
```

---

## 配置

环境变量（可选）:
- `BAILIAN_API_KEY` - 百炼 API Key（L1 LLM 压缩用）
- `DASHSCOPE_API_KEY` - 通义 API Key（向量嵌入用）

无 API Key 时：L1/L3 使用备选方案（BM25 纯文本检索），L2/L4 完全离线可用。

---

## 技能调用时机

当需要以下操作时，加载此技能：
- `memory.store` - 存储重要事实
- `memory.query` - 检索相关记忆
- `memory.sync-turn` - 对话后提取事实
- `memory.session-end` - 会话结束总结
- `memory.prefetch` - 预取相关记忆
- `memory.decay-check` - 遗忘引擎检查
- `memory.stats` - 查看记忆状态

---

_ Memory Hermes · 融合 Hermes + Mem0 顶尖记忆技能_
