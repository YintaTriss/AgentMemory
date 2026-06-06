# SpectrAI 任务书：AgentMemory v0.3 实现

**团队：** AgentMemory 实现团队
**日期：** 2026-06-06
**GitHub：** https://github.com/YintaTriss/AgentMemory
**工作树：** `C:\Users\31683\.openclaw\workspace\AgentMemory`

---

## 一、项目现状

| 层次 | 状态 | 说明 |
|------|------|------|
| v0.3 架构文档 | ✅ 完成 | `ARCHITECTURE-v0.3.md`，双轨检索+图书馆分类 |
| 代码 | ❌ 未实现 | 架构设计完了，但没有任何实现代码 |
| 向量库同步 | ⚠️ 手动 | 142条历史记忆手动导入 LanceDB，不是系统自动跑 |

**参考架构文档：** `ARCHITECTURE-v0.3.md`（在仓库根目录）

---

## 二、架构说明（简化版，不需要L2 Graph-DB）

**注意：审查发现 L2（图谱关联）是过度设计，删除，只做三层。**

### 简化后的三层架构

```
L4 Files（文件系统）
    ↓ 读取/写入
L3 LanceDB（向量检索）
    ↓ 语义搜索
L1 LCM（长期记忆压缩）→ 输出给 AI 上下文
```

### 数据形态

每个记忆单元 = 3个文件（同级目录）：
```
memory/
├── <id>.md          ← 原始内容（markdown）
├── <id>.vec.json    ← 向量数据（embedding）
└── <id>.meta.json   ← 元数据（时间/标签/来源/关联）
```

### 图书馆分类（层级标签）

最多4层，如：`项目/石榴籽/语料/NLLB训练`
用于精确检索，绕过语义搜索的模糊性问题。

### 同步机制（触发条件）

以下情况触发 L4→L3 同步（写入向量）：
- 用户说"记住这个"
- 用户给出重要决策/项目进展
- 重大外部变化（服务器宕机/API变更）

同步方法：
```bash
# 构造 JSON
# 执行 openclaw memory-pro import
# 验证成功（Import completed: X imported, 0 skipped）
```

---

## 三、实现任务

### 第一步：搭架子

**目录结构：**
```
src/agent_memory/
├── __init__.py
├── l4_files.py       # L4 文件读写
├── l3_lancedb.py     # L3 向量存储与检索
├── l1_lcm.py         # L1 记忆压缩
├── sync.py           # L4↔L3 同步
├── library.py        # 图书馆分类系统
└── config.py         # 配置（路径/Embedding模型）
```

### 第二步：L4 文件系统

实现 `L4FilesStore`：
- `save(id, content, metadata)` → 写 `<id>.md` + `<id>.meta.json`
- `load(id)` → 读 md 内容
- `list()` → 列出所有记忆 id
- `delete(id)` → 删除三个文件

### 第三步：L3 LanceDB 向量检索

实现 `L3LanceDBStore`：
- `upsert(id, content, vector)` → 写入 LanceDB
- `search(query_vector, top_k)` → 语义检索
- `delete(id)` → 删除记录

**Embedding 模型：**
- 默认：本地 `bge-large-zh`（免费）
- 可选：API 模式（OPENAI/火山引擎等）

### 第四步：L1 记忆压缩

实现 `L1LCMCompressor`：
- `compress(memory_ids)` → 从 L4 读取多条记忆，压缩为适合上下文的摘要
- 输出格式：分段叙述 + 关键事实列表

### 第五步：同步机制

实现 `SyncManager`：
- `sync(id)` → 单条 L4→L3
- `sync_all()` → 全量同步
- `auto_sync()` → 根据触发条件自动调用

### 第六步：CLI 入口

```bash
# 写入记忆
python -m agent_memory.cli add "今天NLLB训练成功了"

# 检索记忆
python -m agent_memory.cli search "NLLB训练"

# 列出记忆
python -m agent_memory.cli list
```

---

## 四、交付标准

- [ ] `python -m agent_memory.cli add "测试记忆"` 能正常保存
- [ ] `python -m agent_memory.cli search "测试"` 能搜到刚才保存的内容
- [ ] `python -m agent_memory.cli list` 能列出所有记忆
- [ ] L4 文件三个一组（.md / .vec.json / .meta.json）正确生成
- [ ] 推送 GitHub master

---

## 五、技术约束

- **Python：** 3.13
- **向量库：** LanceDB（本地，无需服务器）
- **Embedding：** 本地 `bge-large-zh`（免费），或 API
- **无外部依赖服务：** 不能有 PostgreSQL/Redis/Qdrant 等需要独立部署的服务

---

## 六、已有参考

- 架构文档：`ARCHITECTURE-v0.3.md`
- 记忆文件示例：`memory/MEMORY.md`（参考格式）
- 同步脚本参考：工作空间 `.openclaw/memory-l4-sync-temp.json`（临时同步用的JSON格式）

---

## 七、注意

1. **先跑通架子**：L4 + L3 能读写就行，L1压缩可以后面再做
2. **不要过度设计**：没有 L2，不需要 Graph-DB，不要加
3. **向量库用 LanceDB**：Python 直接装 `lancedb` 包就行，本地文件存储
