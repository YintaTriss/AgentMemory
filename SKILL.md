---
name: agentmemory
version: 1.0.1
family: symphony
role: memory-center
description: 交响乐技能家族 - 双轨图书馆记忆系统，零外部依赖，热插拔
---

# agentmemory 顶尖记忆技能

> 交响乐技能家族成员 | 双轨检索 + 图书馆分类 + 零依赖

## 一键启用

```bash
cd skills/agentmemory
pip install -e .
```

## CLI 命令

```bash
# 存储记忆（自动双轨）
agentmemory store "用户参加了石榴籽省赛答辩" --category "Project/Shiliuzi/Competition" --importance 0.9

# 查询记忆（双轨：语义 + 分类）
agentmemory query "石榴籽项目进展" --limit 5

# 按分类浏览
agentmemory browse Project/Shiliuzi

# 遗忘指定记忆
agentmemory forget <memory_id>

# 统计
agentmemory stats
```

---

## 双轨 + 图书馆架构

**设计哲学：记忆如图书馆。书籍本身不会变，但目录系统让查找变得精确。**

同一份记忆同时存在于两条轨道，永远双轨并存，不存在"相变"切换。

```
同一份记忆：
├─ 图书馆分类轨（.md 本体 + meta.json 元数据）→ 精确查找
└─ Embedding 向量轨（vec.json）→ 语义搜索
```

**层级分类（最多 4 层）：**
```
Project/Shiliuzi/Corpus/NLLB-Training
Project/Shiliuzi/Competition/Provincial
AI/Agent/记忆系统/VCP
```

**检索方式：**
| 轨 | 方式 | 场景 |
|----|------|------|
| 轨一 | Embedding 向量 | 语义模糊匹配 |
| 轨二 | 图书馆分类 | 精确查找 |

---

## Python API

```python
from agent_memory import MemoryManager

mm = MemoryManager()

# 存储（双轨写入）
mem_id = mm.add(
    content="NLLB 训练成功启动",
    category="Project/Shiliuzi/Training",
    importance=0.9
)

# 查询（双轨检索）
results = mm.query("NLLB 训练")
for r in results:
    print(f"[{r['score']:.2f}] {r['content']}")

# 按分类浏览
items = mm.browse("Project/Shiliuzi")
```

---

## 配置

环境变量（可选）：
- `AGENTMEMORY_EMBEDDER` - embedder 类型：`local`（默认）或 `api`
- `AGENTMEMORY_EMBEDDER_API_KEY` - DashScope API Key（API 模式）
- `AGENTMEMORY_VECTOR_DB` - 向量库：`qdrant`（默认）或 `json`

默认模式（local）零外部依赖，文件夹即可运行。

---

## 技能调用时机

当需要以下操作时，加载此技能：
- `memory.store` - 存储记忆
- `memory.query` - 语义 + 分类双轨检索
- `memory.browse` - 按分类浏览
- `memory.forget` - 遗忘
- `memory.stats` - 查看状态

---

## 架构版本

- **v0.3**：当前版本，双轨 + 图书馆架构
- **v0.2**：已废弃，相变机制不需要
- **v0.1**：已废弃，过度抽象（四层 L2 Graph-DB 不存在）

---

_AgentMemory v0.3 · 双轨图书馆记忆系统_
