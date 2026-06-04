# agentmemory

> 交响乐技能家族成员 | 四层闭环记忆系统 | 多 provider 自适应

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)

融合 **Hermes** 记忆机制 + **Mem0** 混合检索优点，四层闭环记忆架构，为 AI Agent 提供持久化认知能力。

**你有什么 API 就用什么模型**，不绑死任何 provider。

---

## 安装

```bash
pip install git+https://github.com/YintaTriss/AgentMemory.git
```

---

## 快速开始

```python
from agentmemory import MemoryHermes

mh = MemoryHermes()

# 存储记忆
memory_id = await mh.store(
    "优优说石榴籽项目省赛结果要等几天",
    metadata={"source": "conversation"},
    importance=0.8
)

# 查询记忆
results = await mh.query("石榴籽项目进展")
for r in results:
    print(f"[{r['score']:.2f}] {r['content']}")
```

---

## 多 Provider 自适应

环境变量自动检测，**你有什么 API 就用什么模型**：

| 环境变量 | Provider | 模型 |
|----------|----------|------|
| `MINIMAX_API_KEY` | minimax | MiniMax-M2.7-highspeed |
| `BAILIAN_API_KEY` | bailian | qwen3.6-plus |
| `DASHSCOPE_API_KEY` | bailian | text-embedding-v3 |
| `OPENAI_API_KEY` | openai-compatible | gpt-4o |

**无 API Key 时**：L1/L3 降级到 Mock（确定性 hash 向量），L2/L4 纯离线可用。

---

## 核心能力

| 方法 | 说明 |
|------|------|
| `mh.store(content, metadata, importance)` | 存储记忆（自动 LLM 事实提取） |
| `mh.query(query, limit)` | 查询记忆（混合检索：向量+BM25+重要性） |
| `mh.prefetch(query)` | 预取相关记忆（后台异步加载） |
| `mh.forget(memory_id)` | 主动遗忘 |
| `mh.sync_turn(user, assistant)` | 对话轮次同步（提取事实） |
| `mh.on_session_end(summary)` | 会话结束总结 |
| `mh.run_decay_check()` | 遗忘引擎驱动检查 |
| `mh.get_stats()` | 记忆系统统计 |

---

## 四层闭环架构

```
对话 → L1: LLM 压缩事实
         ↓
       L2: 实体关系图谱
         ↓
       L3: 混合向量检索
         ↓
       L4: 文件持久化归档

心跳周期 → 遗忘引擎检查 → 归档/遗忘低分记忆
```

| 层 | 作用 | 存储 |
|----|------|------|
| **L1** LCM压缩 | 对话 → 关键事实（LLM 提取） | 内存 |
| **L2** Graph | 实体 + 关系 + 属性 | `graph_store.json` |
| **L3** Vector | BM25(30%) + 向量(60%) + 重要性(10%) | `vectors.json` |
| **L4** Files | MEMORY.md + 每日日记 | `memory/YYYY-MM-DD.md` |

---

## 遗忘算法

```
遗忘得分 = 访问频率×0.3 + 重要性×0.3 + 时效性×0.4

< 0.3  → 永久删除
0.3-0.5 → 归档到深层存储
> 0.5  → 保留
```

时效性衰减：14天半衰期。

---

## 命令行 CLI

```bash
agentmemory store "记忆内容" --importance 0.8
agentmemory query "关键词" --limit 5
agentmemory layer-status
agentmemory stats
agentmemory sync-turn "用户消息" "助手消息"
agentmemory decay-check
```

## HTTP 服务（框架集成）

```bash
# 启动 HTTP 服务，集成到其他 Agent 框架
agentmemory serve --adapter openclaw --port 8765

# MCP stdio 模式（供 SpectrAI / Claude Code 使用）
agentmemory serve --adapter claude_code --port stdio
```

支持的适配器：`openclaw` / `claude_code` / `langchain` / `openai_agents` / `crewai`

---

## 文件结构

```
agentmemory/
├── __init__.py              # 包入口：from agentmemory import MemoryHermes
├── cli.py                   # CLI 入口：agentmemory 命令
├── memory_manager.py        # 总管理器
├── config.py               # 配置管理
├── L1_lcm_compressor.py    # L1 压缩层
├── L2_graph_store.py        # L2 图谱层
├── L3_vector_store.py       # L3 向量层
├── L4_file_persist.py       # L4 文件层
├── decay_engine.py          # 遗忘引擎
├── providers/               # LLM/Embedding provider 抽象层
│   ├── llm.py              # BailianProvider / MinimaxProvider / OpenAICompatProvider
│   └── embedder.py         # DashScopeEmbedder / MockEmbedder
├── data/                   # 数据存储（运行时生成）
│   ├── vectors.json
│   └── graph_store.json
└── memory/                  # 每日日记（运行时生成）
```

---

## 与市面方案对比

| 维度 | Mem0 | Letta | **agentmemory** |
|------|------|-------|----------------|
| 多 provider | ❌ | ❌ | **✅** minimax/bailian/openai |
| 事实提取 | ✅ | ❌ | ✅ |
| 图谱层 | 混合 | PostgreSQL | ✅ Graph |
| 遗忘算法 | 重要性 | 压缩 | ✅ 完整 |
| 四层架构 | 混合 | 层级 | ✅ 闭环 |
| Prefetch | ❌ | ❌ | ✅ |
| 文件持久化 | ❌ | ❌ | ✅ |
| BM25 实现 | 外部 | 外部 | ✅ 纯 Python |

---

## OpenClaw 技能集成

将本目录放入 OpenClaw skills 目录后，喊相关指令会触发对应功能：

```bash
# 触发记忆存储
openclaw skills run agentmemory --action store --content "优优参加石榴籽省赛答辩"

# 触发记忆查询
openclaw skills run agentmemory --action query --query "石榴籽项目"
```

**注意**：技能系统是被动触发，不自动采集对话。如需后台持续运行，使用 `agentmemory serve --adapter openclaw` 启动 HTTP 服务。

---

_MIT License | 交响乐技能家族_
