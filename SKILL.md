---
name: agentmemory
version: 1.0.0
family: symphony
role: memory-center
description: 交响乐技能家族 - 四层闭环记忆系统，融合 Hermes + Mem0 优点，多 provider 自适应
---

# agentmemory 记忆技能

> 技能家族：symphony | 四层闭环架构 | 多 provider 自适应 | pip 安装即用

---

## 快速开始

**pip 安装：**
```bash
pip install git+https://github.com/YintaTriss/AgentMemory.git
```

安装后可直接 import：
```python
from agentmemory import MemoryHermes

mh = MemoryHermes()
memory_id = await mh.store("优优参加石榴籽省赛", importance=0.9)
results = await mh.query("石榴籽")
```

**或命令行使用：**
```bash
agentmemory store "优优参加石榴籽省赛" --importance 0.9
agentmemory query "石榴籽"
```

---

## 多 Provider 自适应

**环境变量自动检测**，纯粹根据你机器上设置了哪个 API Key 来决定用哪个 provider，不绑死任何 API：

| 检测到环境变量 | 使用 | 模型 |
|---------------|------|------|
| `MINIMAX_API_KEY` | minimax | MiniMax-M2.7-highspeed |
| `BAILIAN_API_KEY` 或 `DASHSCOPE_API_KEY` | bailian | qwen3.6-plus + text-embedding-v3 |
| `OPENAI_API_KEY` | openai-compatible | GPT-4o 等 |
| 以上都没有 | MockEmbedder（离线模式） | 确定性 hash 向量 |

**你有什么 API 就用什么**，自动匹配，无需配置：

```bash
# 用 minimax
export MINIMAX_API_KEY=xxx
python -c "from agentmemory import MemoryHermes; mh = MemoryHermes(); print('ok')"

# 切换到 openai
export OPENAI_API_KEY=xxx
python -c "from agentmemory import MemoryHermes; mh = MemoryHermes(); print('ok')"
```

**无 API Key 时**：L1/L3 降级到 Mock（确定性 hash 向量），L2/L4 纯离线可用。

---

## 三种使用模式

### 模式一：Python 库（推荐）

```python
from agentmemory import MemoryHermes

mh = MemoryHermes()

# 存储
memory_id = await mh.store(
    "用户参加石榴籽省赛答辩",
    metadata={"source": "conversation"},
    importance=0.9
)

# 查询
results = await mh.query("石榴籽", limit=5)
for r in results:
    print(f"[{r['score']:.2f}] {r['content']}")

# 对话轮次同步（自动 LLM 事实提取）
facts = await mh.sync_turn(
    "用户: 省赛结果出了吗？",
    "助手: 恭喜你通过了！"
)

# 遗忘
await mh.forget(memory_id)

# 统计
stats = mh.get_stats()
```

### 模式二：命令行 CLI

```bash
agentmemory store "记忆内容" --importance 0.8
agentmemory query "关键词" --limit 5
agentmemory layer-status
agentmemory stats
agentmemory sync-turn "用户消息" "助手消息"
agentmemory decay-check
```

### 模式三：HTTP 服务（多框架集成）

```bash
# 启动 HTTP 服务，集成到其他 Agent 框架
agentmemory serve --adapter openclaw --port 8765

# 启动 MCP stdio 服务（供 Claude Code / SpectrAI 使用）
agentmemory serve --adapter claude_code --port stdio
```

支持的适配器：`openclaw` / `claude_code` / `langchain` / `openai_agents` / `crewai`

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

**遗忘评分**：`访问频率×0.3 + 重要性×0.3 + 时效性×0.4`

---

## OpenClaw 技能集成

将本目录放入 OpenClaw skills 目录后，喊相关指令会触发对应功能：

| 触发时机 | 调用的 CLI |
|----------|-----------|
| 需要记忆时 | `agentmemory store ...` |
| 查询记忆时 | `agentmemory query ...` |
| 对话轮次后 | `agentmemory sync-turn ...` |
| 会话结束时 | `agentmemory session-end ...` |
| 心跳检查 | `agentmemory decay-check` |
| 查看状态 | `agentmemory layer-status` |

**注意**：这是一个技能包，OpenClaw 启动后不会默认运行记忆采集。
需要在对话中主动触发，或通过集成模式让它在后台持续运行。

---

## 配置（可选）

环境变量即可，无需配置文件：

```bash
export MINIMAX_API_KEY=xxx      # LLM - minimax
export BAILIAN_API_KEY=xxx      # LLM - bailian（百炼）
export DASHSCOPE_API_KEY=xxx    # Embedding - dashscope
export OPENAI_API_KEY=xxx       # LLM/Embedding - openai兼容
```

如需精细控制，创建 `config.json`：

```json
{
  "llm": {
    "provider": "minimax",
    "model": "MiniMax-M2.7-highspeed"
  },
  "embedding": {
    "model": "text-embedding-v3",
    "dimensions": 1024
  },
  "decay": {
    "enabled": true,
    "half_life_days": 14,
    "threshold": 0.3
  }
}
```

---

## 一句话总结

> **你有什么 API 就用什么模型，四层闭环记忆，pip 安装直接 import，不绑死任何 provider。**

---
