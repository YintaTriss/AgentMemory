# AgentMemory v0.3 — 架构实现说明 (ARCHITECTURE-IMPL)

> **版本**：v0.3（双轨 + 图书馆）
> **状态**：架构已确定，进入实现阶段
> **目标读者**：后端 / 前端 / 测试工程师
> **替代文档**：本文件取代 `ARCHITECTURE-v0.3.md` 中的“概念架构”章节，给出**可直接编码**的模块、数据流与边界定义。

---

## 一、项目目标

| 维度 | 目标 |
|------|------|
| **核心能力** | 为 AI Agent 提供持久化记忆，支持**双轨检索**（语义 + 图书馆分类） |
| **多 Agent 共享** | 整个记忆库是一个文件夹，复制即迁移，**热插拔** |
| **零外部依赖** | 默认 HashEmbedder 即可工作；可选 DashScope API 提升语义质量 |
| **可热插拔** | L4 / L3 / L1 各层接口独立，Embedder 可替换 |
| **安全基线** | API Key 缺失必须报错（不允许静默降级为假向量）；并发写有文件锁；热插拔文件夹需 HMAC 校验 |

**非目标（v0.3 不做）**：

- ❌ **不做** L2 Graph-DB（图谱关系）—— 审查发现过度设计，删除。
- ❌ **不做** 相变（v0.2 概念）—— 双轨永远并存。
- ❌ **不做** 服务端数据库（PostgreSQL / Qdrant）—— 整个系统跑在本地文件夹上。
- ❌ **不做** 跨机器自动同步（交给 Git / rsync / 文件夹共享）。

---

## 二、简化三层架构

```
                    ┌────────────────────────────────────────┐
                    │          AI Agent / CLI            │
                    └──────────────┴───────────┴──────────┘
                                 │            │
                  ┌───────────────▼─┐      ┌────▼───────────┐
                  │   L1 LCM       │      │  Library         │
                  │  Compressor    │      │  Classifier      │
                  │ (上下文压缩)   │      │  (层级分类)      │
                  └──────────────┴──┐      └─────┴─────────┘
                               │               │
                               ▼               ▼
                    ┌───────────────────────────────────┐
                    │       L4 Files (3个文件)     │
                    │   <id>.md + <id>.vec.json    │
                    │   + <id>.meta.json           │
                    └─────────────────┴─────────────┘
                                   │ 自动同步
                                   ▼
                    ┌────────────────────────────────────┐
                    │     L3 Vector (纯 JSON)       │
                    │   + BM25 (可选, 混合检索)    │
                    └───────────────────────────────────┘
```

### 各层职责

| 层 | 名称 | 职责 | 实现位置 |
|----|------|------|----------|
| **L4** | Files | 唯一真实数据源（Single Source of Truth）。每个记忆 = 3 文件 | `src/agent_memory/l4_files.py` |
| **L3** | Vector | 向量索引层。L4 → L3 **异步同步**，但 L3 可重建（从 L4 恢复） | `src/agent_memory/l3_vector.py` |
| **L1** | LCM Compressor | 上下文压缩器。从 L4 读取 N 条记忆 → 压缩为适合 prompt 的摘要 | `src/agent_memory/l1_lcm.py` |

**为什么去掉 L2 Graph-DB？**

- 语义关系已被 Embedding 向量捕获。
- 实体关系（"用户 ↔ 项目 ↔ 决策"）由 `meta.json` 的 `tags` + `category` 层级表达。
- 维护图谱的开销远大于收益（VCP 验证结论）。


---

## 三、数据形态

### 3.1 单个记忆的 3 个文件

每个记忆 = 同一目录下的 **3 个** 同名文件：

```
memory/
├── 7a3f9d2e-1b4c-4e8a-9f0a-1234567890ab.md          ← 原始内容（人类可读 Markdown）
├── 7a3f9d2e-1b4c-4e8a-9f0a-1234567890ab.vec.json    ← 向量数据
├── 7a3f9d2e-1b4c-4e8a-9f0a-1234567890ab.meta.json   ← 元数据（分类 / 标签 / 来源）
└── ...
```

### 3.2 `*.md`（内容本体）

纯 Markdown 文本。**唯一**会被人类阅读和编辑的文件。

```markdown
# 2026-06-06 NLLB 训练实验记录

今天跑了 NLLB-200 的 zh-mng 微调，BLEU 提升 1.2。
- 训练步数：5000
- batch_size：16
- 显存占用：18GB
```

### 3.3 `*.vec.json`（向量数据）

```json
{
  "id": "7a3f9d2e-1b4c-4e8a-9f0a-1234567890ab",
  "vector": [0.012, -0.034, ..., 0.087],
  "embedder": "hash",
  "dims": 384,
  "created_at": "2026-06-06T18:23:45Z"
}
```

- `embedder` 记录用哪个 Embedder 算的向量（防止更换 Embedder 后向量化不一致）。
- `dims` 防止向量长度被裁剪后无法比对。

### 3.4 `*.meta.json`（元数据）

```json
{
  "id": "7a3f9d2e-1b4c-4e8a-9f0a-1234567890ab",
  "category": "项目/石榴籽/NLLB训练",
  "tags": ["NLLB", "微调", "BLEU"],
  "source": "agent:backend-1",
  "importance": 0.85,
  "created_at": "2026-06-06T18:23:45Z",
  "updated_at": "2026-06-06T18:23:45Z",
  "links": ["9b2c4e8a-..."]
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | str (UUID4) | ✅ | 与文件名一致 |
| `category` | str | ✅ | 图书馆分类路径（见第四章） |
| `tags` | list[str] | ❌ | 自由标签，用于 BM25 关键词索引 |
| `source` | str | ✅ | 来源标识（agent 名 / 手动 / 导入） |
| `importance` | float 0-1 | ❌ | 重要性评分（影响 L1 压缩保留） |
| `created_at` | ISO 8601 | ✅ | 创建时间 |
| `updated_at` | ISO 8601 | ✅ | 最后修改时间 |
| `links` | list[UUID] | ❌ | 手动关联的其他记忆 ID（图谱信息用此替代 L2） |

---

## 四、图书馆分类规范

### 4.1 顶层 5 类

**固定**顶层类别（不可新增顶层）：

| 类别 | 含义 | 示例 |
|------|------|------|
| **项目** | 进行中的项目、任务 | 项目/石榴籽/语料/NLLB训练 |
| **学习** | 学习笔记、读书、技术资料 | 学习/AI/Transformer/注意力机制 |
| **人物** | 人际、团队、联系人 | 人物/团队/产品经理/张三 |
| **决策** | 重要决策、架构选择 | 决策/2026-06-采用双轨架构 |
| **偏好** | 用户偏好、习惯、设置 | 偏好/代码风格/Pythonic |

### 4.2 路径深度限制

- **最多 4 层**：`顶层/第二层/第三层/第四层`
- 第 1 层必须是上述 5 个固定类之一。
- 第 2-4 层可自由命名（建议中文，slug 化）。

**有效路径示例**：

```
项目/石榴籽/语料/NLLB训练       ✅ 4 层
学习/AI/Transformer              ✅ 3 层
决策/2026-06-双轨架构             ✅ 2 层
偏好/Pythonic                     ✅ 2 层
```

**无效路径示例**：

```
石榴籽/语料/NLLB训练              ❌ 缺少顶层
项目/A/B/C/D/E                   ❌ 超过 4 层
random_thought                   ❌ 不在 5 个顶层内
```

### 4.3 自动分类策略

`LibraryClassifier` 内部维护**关键词字典** + **降级策略**：

1. **关键词匹配**：内容中出现的关键词 → 命中分类。
2. **Embedder 相似度**：与已知分类示例做余弦相似度。
3. **降级到 `项目/未分类`**：无法分类时使用，避免空分类。

**手动覆盖**：用户可通过 CLI 的 `add --category` 强制指定。

---

## 五、Embedder 策略

### 5.1 抽象接口

```python
class Embedder(ABC):
    @property
    def dim(self) -> int: ...
    def embed(self, text: str) -> list[float]: ...
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
```

### 5.2 实现

| Embedder | 维度 | 依赖 | 何时使用 |
|----------|------|------|----------|
| `HashEmbedder` | 384 | 零依赖（仅 hashlib + numpy） | 默认 / 离线 / 单元测试 |
| `DashScopeEmbedder` | 1024 | `DASHSCOPE_API_KEY` 环境变量 | 生产 / 高质量语义搜索 |
| `OpenAIEmbedder`（可选）| 1536 | `OPENAI_API_KEY` | 跨语言场景 |

### 5.3 切换策略

`get_embedder()` 工厂函数：

```python
def get_embedder() -> Embedder:
    if os.environ.get("DASHSCOPE_API_KEY"):
        return DashScopeEmbedder(...)
    return HashEmbedder(dim=384)  # 零依赖回退
```

**安全要求（P0-1）**：DashScopeEmbedder 在 `__init__` 时必须**立即**校验 `DASHSCOPE_API_KEY`，缺失则**抛 `RuntimeError`**，**不允许**回退到 HashEmbedder（避免静默降级产生假向量）。

### 5.4 向量维度不一致的处理

更换 Embedder 后，新写入的向量维度会变化。处理策略：

- L3 JSON 索引按 `embedder` 名分文件：`vector_index_hash.json`, `vector_index_dashscope.json`。
- 检索时只搜索当前 Embedder 对应的索引。
- 历史向量不重算（避免算力浪费），但提供 CLI `reembed` 命令批量重算。


---

## 六、同步机制（L4 → L3）

### 6.1 触发条件

`SyncManager.auto_sync_check(text)` 检测以下关键词时**自动同步**：

| 类别 | 关键词 |
|------|--------|
| **决策** | 决定、决策、确定、敲定 |
| **完成** | 完成、结束、done、finished |
| **重要** | 重要、关键、critical、important |
| **记住** | 记住、记下、备忘、remember |
| **项目** | 项目、project、里程碑、milestone |
| **进展** | 进展、进度、progress、更新 |

**匹配规则**：关键词在文本中**子串匹配**（不分大小写）。命中 ≥ 1 个关键词即触发。

### 6.2 同步流程

```
MemoryManager.add(content)
    │
    ├→ L4FilesStore.save()        # 必做：写 3 个文件
    │
    └→ SyncManager.sync_one()     # 可选：触发后写 L3
         │
         ├→ Embedder.embed()       # 计算向量
         ├→ L3VectorStore.upsert() # 写向量
         └→ 返回 memory_id
```

### 6.3 异步队列

`MemoryManager.add()` 必须**立即返回**（不阻塞 AI Agent）：

```python
from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="memory-sync")

def add(self, content: str) -> str:
    memory_id = generate_uuid()
    _executor.submit(self._add_sync, memory_id, content)
    return memory_id
```

**重要**：

- L4 文件写入是**强同步**（失败要报错）。
- L3 向量同步是**弱同步**（失败仅记录警告，下次启动时重试）。

### 6.4 启动时重建

每次 `MemoryManager.__init__` 时：

1. 扫描 L4 目录，列出所有 `*.md`。
2. 与 L3 向量索引比对，找出 L3 中缺失的 memory_id。
3. 后台批量补同步。

---

## 七、CLI 命令

入口：`python -m agent_memory.cli <subcommand>`

| 命令 | 参数 | 功能 |
|------|------|------|
| `add` | `<content> [--category PATH] [--tags t1,t2]` | 添加一条记忆 |
| `search` | `<query> [--top-k N] [--mode vector\|bm25\|hybrid]` | 搜索记忆 |
| `list` | `[--category PATH] [--limit N]` | 列出记忆（按分类过滤） |
| `show` | `<memory_id>` | 显示单条记忆详情（含 3 文件路径） |
| `delete` | `<memory_id>` | 删除记忆（3 文件 + L3 向量） |
| `category` | `<memory_id> <new_path>` | 重新分类 |
| `stats` | 无 | 显示统计（总数、按分类分布、L3 覆盖率） |
| `reembed` | `[--embedder hash\|dashscope]` | 重新向量化所有记忆 |
| `verify` | `[--hmac-key KEY]` | 校验文件夹 HMAC 签名 |
| `serve` | `[--port 8765]` | 启动 Web 服务器（可选） |

### 7.1 输出格式

- 默认人类可读文本（带颜色）。
- `--json` 全局参数，输出 JSON 便于脚本调用。

### 7.2 退出码

- 0：成功
- 1：参数错误
- 2：记忆不存在
- 3：文件锁冲突（重试）
- 4：API Key 缺失
- 5：HMAC 校验失败

---

## 八、零外部依赖原则

### 8.1 必需依赖（pyproject.toml）

```toml
dependencies = [
    "httpx>=0.25.0",      # DashScope API 异步调用
    "aiofiles>=23.0.0",   # 异步文件 IO
]
```

### 8.2 可选依赖

| 包 | 用途 | 缺失行为 |
|----|------|----------|
| `httpx` | DashScope API | 仅 HashEmbedder 可用 |
| `aiofiles` | 异步文件 | 降级为同步 IO（仍可用） |
| `numpy` | 向量计算 | HashEmbedder 降级为纯 Python list |

### 8.3 不引入

- ❌ `lancedb` —— L3 改用纯 JSON 索引（见 §9）
- ❌ `sentence-transformers` —— 太大，按需 install
- ❌ `chromadb / qdrant-client` —— 违反"无独立服务"原则
- ❌ `pyyaml` —— 配置用 JSON / TOML

> **修订说明**：原 v0.3 草案使用 LanceDB；实现阶段决定用**纯 JSON + numpy** 实现 L3 索引，零二进制依赖，详细见 §9。


---

## 九、L3 向量层实现细节

### 9.1 为什么用纯 JSON 而非 LanceDB

- LanceDB 是 Rust 内核 + Python 绑定，安装包大（~50MB），首次运行要下载 native lib。
- v0.3 数据规模预期：个人 Agent < 10K 条记忆，文件夹总大小 < 100MB。
- 10K 条 × 384 维 × 4 字节 ≈ 15MB JSON，可一次加载到内存。
- 全量加载到内存后，numpy 矩阵乘法做余弦相似度 = 亚毫秒级。

### 9.2 存储结构

```
data/
├── vector_index.json          # 主索引：所有向量 + 元数据引用
└── vector_index.lock          # 文件锁（并发保护）
```

```json
{
  "embedder": "hash",
  "dims": 384,
  "memories": {
    "7a3f9d2e-...": {
      "vector": [0.012, ...],
      "category": "项目/石榴籽/NLLB训练",
      "tags": ["NLLB"],
      "importance": 0.85
    }
  }
}
```

### 9.3 检索算法

```python
def search(query: str, top_k: int = 5) -> list[SearchResult]:
    q_vec = embedder.embed(query)
    # 1. 计算余弦相似度（向量化为矩阵乘法）
    scores = matrix @ q_vec  # shape: (N,)
    # 2. Top-K 索引
    top_idx = np.argpartition(scores, -top_k)[-top_k:]
    # 3. 过滤 importance 阈值（可选）
    return [SearchResult(...) for i in top_idx]
```

**性能目标**：1 万条记忆，检索 < 10ms。

### 9.4 BM25 混合检索（可选）

在 `embedder.py` 旁实现 `BM25Indexer`（纯 Python），与向量检索做加权融合：

```
final_score = α × vector_score + (1-α) × bm25_score
```

默认 α = 0.7（偏向语义）。

---

## 十、热插拔设计

### 10.1 文件夹即记忆库

整个 `memory/` 目录可以：

- **复制**到另一台机器 → 立即可用（前提是 Embedder 维度一致）。
- **Git 同步**（推荐，记忆是文本）。
- **NAS 共享**（多 Agent 共享工作空间）。

### 10.2 Embedder 兼容性检查

加载文件夹时：

1. 读取 `data/vector_index.json` 中的 `embedder` 字段。
2. 当前环境的 Embedder 与之一致 → 直接使用。
3. 不一致 → 提示用户：是否重新向量化（`reembed`）？

### 10.3 HMAC 签名（P0-4 安全要求）

**问题**：恶意文件夹可注入 prompt 或瘦痛加载。

**修复**：加载前校验所有 `*.md` 的 HMAC 签名。

```python
# 签名生成（管理员）
def sign_folder(folder: Path, hmac_key: bytes):
    for md in folder.glob("*.md"):
        sig = hmac.new(hmac_key, md.read_bytes(), hashlib.sha256).hexdigest()
        md.with_suffix(".md.sig").write_text(sig)

# 加载时校验
def verify_folder(folder: Path, hmac_key: bytes) -> bool:
    for md in folder.glob("*.md"):
        sig_path = md.with_suffix(".md.sig")
        if not sig_path.exists():
            return False
        expected = hmac.new(hmac_key, md.read_bytes(), hashlib.sha256).hexdigest()
        actual = sig_path.read_text().strip()
        if not hmac.compare_digest(expected, actual):
            return False
    return True
```

**默认行为**：

- 无 `.md.sig` 文件 → **拒绝加载**，提示"未签名的文件夹不可信"。
- 显式 `--trust` 参数 → 跳过校验（仅本地开发用）。

---

## 十一、并发与文件锁（P0-3 安全要求）

### 11.1 锁的范围

- `L4FilesStore` 写操作：按 `memory_id` 加细粒度锁。
- `L3VectorStore.upsert`：整个索引一把全局锁（写不频繁）。
- `data/vector_index.json` 重写：用临时文件 + 原子 rename。

### 11.2 跨平台锁

```python
# Windows / Unix 统一用 filelock 库（轻量，~10KB）
from filelock import FileLock

with FileLock(str(path) + ".lock"):
    # 临界区
    ...
```

`filelock` 作为必需依赖（比直接用 `fcntl` / `msvcrt` 简单）。

### 11.3 重试策略

- 锁冲突 → 自动重试 3 次（间隔 50ms / 100ms / 200ms）。
- 仍冲突 → 抛 `LockTimeout` 异常（CLI 退出码 3）。


---

## 十二、Prompt 注入防护（P0-2 安全要求）

### 12.1 输入检测

用户输入写入 L4 前，过滤以下高危模式：

```python
INJECTION_PATTERNS = [
    r"忽略(之前|以上|前面)的(指令|提示)",
    r"forget (everything|all|previous)",
    r"ignore (all|previous|above)",
    r"system:\s*",
    r"<\|im_start\|>",
    r"### (System|Assistant|User):",
]

def check_injection(text: str) -> list[str]:
    """返回命中的模式列表；空列表表示安全"""
    return [p for p in INJECTION_PATTERNS if re.search(p, text, re.IGNORECASE)]
```

### 12.2 处理策略

- **不阻塞写入**，但 `meta.json` 添加 `trust_score` 字段（命中模式 → 0.3，否则 1.0）。
- L1 压缩时，优先保留 `trust_score >= 0.7` 的记忆。
- 日志记录警告（不阻止用户操作）。

---

## 十三、模块依赖图

```
┌───────────────┐
│   cli.py        │  ← CLI 入口
└─────────┴──────┘
         │
         ▼
┌───────────────┐
│ MemoryManager   │  ← 业务门面（Facade）
└───┴───┴─────┘
     │   │   │
     ▼   │   ▼
   L4Files│   LibraryClassifier
     │   │   │
     │   ▼   │
     │ SyncManager ──→ Embedder (Hash/DashScope)
     │   │
     ▼   ▼
   L3VectorStore (JSON + numpy)
     │
     ▼
   L1LCMCompressor
```

依赖方向：**上层 → 下层**，下层不知道上层存在。

---

## 十四、关键设计决策（ADR 摘要）

| ID | 决策 | 理由 | 替代方案 |
|----|------|------|----------|
| ADR-001 | 删除 L2 Graph-DB | 过度设计；embedding + tags 已能表达关系 | Neo4j / Mem0 图层 |
| ADR-002 | 双轨永远并存（无相变） | 简化心智模型；同步无歧义 | v0.2 的"热/冹"切换 |
| ADR-003 | L3 用纯 JSON 而非 LanceDB | 零二进制依赖；10K 规模够用 | LanceDB / Chroma |
| ADR-004 | 最多 4 层分类 | 平衡表达力与认知负担 | 无限制 / 树形结构 |
| ADR-005 | HashEmbedder 默认 | 零依赖即可工作；测试友好 | 必须 API 联网 |
| ADR-006 | L4 写同步 / L3 写异步 | L4 是 SoT 不能丢；L3 可重建 | 全同步（慢） |
| ADR-007 | HMAC 签名强制 | 防止恶意文件夹注入 | 可选签名（不防小白） |
| ADR-008 | 并发用 filelock | 跨平台；API 简洁 | fcntl + msvcrt 分平台 |

---

## 十五、验收清单（Definition of Done）

- [ ] `python -m agent_memory.cli add "测试"` 成功写 3 文件
- [ ] `python -m agent_memory.cli search "测试"` 命中（向量 + BM25）
- [ ] `python -m agent_memory.cli list` 列出所有
- [ ] 启动时 `DASHSCOPE_API_KEY` 缺失 → 报错（非静默）
- [ ] 多进程并发 `add` → 文件锁生效，无损坏
- [ ] 篡改 `*.md` 后 `verify` → 检出
- [ ] `auto_sync_check("今天决定用双轨")` → 返回 True
- [ ] 更换 Embedder 后 `stats` 提示需 reembed
- [ ] L1 `compress(memory_ids=[...])` 输出 < 2000 token 摘要
- [ ] 全部测试通过（`pytest tests/ -v`）

---

## 十六、参考与延伸阅读

- `ARCHITECTURE-v0.3.md`：原始概念架构（v0.3 哲学）
- `docs/SPRINT-BRIEF.md`：本 sprint 任务书
- `docs/INTERFACE-SPEC.md`：**所有 Python 接口签名**（下一份文档）
- `docs/DIRECTORY-LAYOUT.md`：**完整目录树**（再下一份文档）
- 安全审查：`reports/agentmemory-security-review.md`（P0-1 ~ P0-4）
- `docs/SECURITY.md`：**已知风险 + P0 修复总结 + 安全建议**（用户面向）
- 本文档第 17 章「安全模型」：P0-1/2/3/4 落地的代码片段

---

_文档作者：架构师 ⚔️_
_最后更新：2026-06-07_

---

## 十七、安全模型

> **本章为安全补充说明**。原安全评审报告见：`reports/agentmemory-security-review.md`（P0 修复项 H-01 · H-02 · H-03 · H-04 · H-05）。
> **实现状态**：P0-1 / P0-2 / P0-3 / P0-4 在本 sprint 收尾中全部落地。

### 17.1 P0-1 ｜API Key 校验策略（H-05）

**问题**：`L3._embed_single/_embed_batch` 在 `DASHSCOPE_API_KEY` 缺失时静默返回伪随机向量，产生“假成功”。

**修复**：`embedder.py · get_embedder()` 工厂函数采取**双轨策略**。

```python
# src/agent_memory/embedder.py
import os
from typing import Optional

def get_embedder() -> Embedder:
    """工厂函数。遵循 P0-1：
    1. DASHSCOPE_API_KEY 存在 → DashScopeEmbedder（含安全校验）
    2. 否则 → HashEmbedder(dim=384)，零依赖、确定性、高速
    
    重要：DashScopeEmbedder 在 __init__ 时**必须**验证 api_key，缺失抛 RuntimeError。
    不允许隐式降级为 HashEmbedder（避免假向量混入真实向量中）。
    \"\"\"
    api_key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if api_key:
        return DashScopeEmbedder(api_key=api_key)  # 里面会验证
    return HashEmbedder(dim=384)  # 明确、确定、零依赖

# DashScopeEmbedder.__init__ 中的安全校验
class DashScopeEmbedder(Embedder):
    def __init__(self, api_key: Optional[str] = None, ...):
        key = api_key or os.environ.get("DASHSCOPE_API_KEY", "")
        if not key or not key.strip():
            raise RuntimeError(
                "DashScopeEmbedder requires DASHSCOPE_API_KEY env var. "
                "Do NOT fall back to HashEmbedder silently — mixed-dim vectors break retrieval."
            )
        self._api_key = key
        ...
```

**验证**：

```bash
unset DASHSCOPE_API_KEY
python -c "from agent_memory.embedder import DashScopeEmbedder; DashScopeEmbedder()"
# 期望：彰错 RuntimeError；实际：✔
```

---

### 17.2 P0-2 ｜Prompt 注入防护（H-04）

**问题**：对话中的恶意指令可能被 L1 提取为 fact → 存入 L3/L4 → 后续检索时注入到 prompt。

**修复**：`sync.sync_one()` 在写入 L3 前调用 `security.check_injection()` 进行关键词检测，**不阻塞写入**但调低 `trust_score`。

```python
# src/agent_memory/security.py
import re
from typing import List

INJECTION_PATTERNS = [
    r"忽略(之前|以上|前面|全部)的?(指令|提示|content)",
    r"forget\s+(everything|all|previous|above)",
    r"ignore\s+(all|previous|above|prior)\s+(instructions?|prompts?)",
    r"system\s*:\s*",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"###\s+(System|Assistant|User)\s*:",
    r"你必须|你应该|请你先|以后你是",
]

def check_injection(text: str) -> List[str]:
    """返回命中的模式列表。空列表表示安全。\"\"\"
    return [p for p in INJECTION_PATTERNS if re.search(p, text, re.IGNORECASE)]

# sync.py 中的调用
def sync_one(self, memory_id: str) -> bool:
    record = self._l4.load(memory_id)
    if record is None:
        return False
    content = record["content"]
    
    # P0-2: 注入检测（不阻塞，只调 trust_score）
    hits = check_injection(content)
    trust_score = 0.3 if hits else 1.0
    self._l4.update_meta(memory_id, trust_score=trust_score, injection_hits=hits)
    
    # ... 后续向量化 + L3 upsert
    vec = self._embedder.embed_sync(content)
    self._l3.upsert(memory_id, vec, {"trust_score": trust_score})
    return True
```

**不阻塞 + 可追溯**：高风险内容仍入库，但 L1 压缩会优先保留 `trust_score >= 0.7` 的记忆，且全部事件进入 `data/audit.log`。


---

### 17.3 P0-3 ｜文件锁（H-01）

**问题**：多 Agent 并发写 L4 文件时无任何锁，可能产生静默覆盖 / 数据损坏。

**修复**：`L4FilesStore.save()` 与 `delete()` 使用 `filelock` 跨平台锁，结合**原子写**（tempfile + os.replace）以一次刷新。

```python
# src/agent_memory/l4_files.py
import os, tempfile, json
from filelock import FileLock, Timeout
from pathlib import Path

class L4FilesStore:
    LOCK_TIMEOUT = 5  # 秒

    def _lock_path(self, memory_id: str) -> Path:
        return self.memory_dir / f".{memory_id}.lock"

    def save(self, memory_id, content, meta, vec) -> str:
        lock = FileLock(str(self._lock_path(memory_id)), timeout=self.LOCK_TIMEOUT)
        try:
            with lock:
                self._atomic_write(f"{memory_id}.md", content)
                self._atomic_write(f"{memory_id}.meta.json", json.dumps(meta.to_dict(), ensure_ascii=False))
                self._atomic_write(f"{memory_id}.vec.json", json.dumps(vec.to_dict()))
        except Timeout as e:
            raise FileLockError(f"锁冲突: {memory_id}") from e
        return memory_id

    def _atomic_write(self, filename: str, data: str) -> None:
        """tempfile + os.replace 原子写，kill -9 也不会留下半成品。\"\"\"
        target = self.memory_dir / filename
        tmp_fd, tmp_path = tempfile.mkstemp(dir=self.memory_dir, prefix=f".{filename}.", suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())  # 硬盘刷新
            os.replace(tmp_path, target)  # 同一文件系下原子
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def delete(self, memory_id: str) -> bool:
        lock = FileLock(str(self._lock_path(memory_id)), timeout=self.LOCK_TIMEOUT)
        with lock:
            for ext in (".md", ".vec.json", ".meta.json", ".md.sig"):
                p = self.memory_dir / f"{memory_id}{ext}"
                if p.exists():
                    p.unlink()
        return True
```

**跨平台说明**：

- `filelock` 在 Unix 上使用 `fcntl.flock`，在 Windows 上使用 `msvcrt.locking`。
- 跨进程、跨线程都能护。
- 如果 5s 内拿不到锁抛 `FileLockError`（退出码 3）。

**验证**：

```python
# tests/test_l4_concurrent.py
import asyncio
from agent_memory import MemoryManager

async def hammer():
    mm = MemoryManager(memory_dir="/tmp/test_mem")
    await asyncio.gather(*[mm.add_async(f"concurrent test {i}") for i in range(50)])
    assert len(mm.list()) == 50
```

---

### 17.4 P0-4 ｜HMAC 签名（H-03）

**问题**：热插拔文件夹未签名，恶意 Agent 可以构造包含 Prompt 注入的 `.md` 传播。

**修复**：`integrity.py` 提供 `sign_file()` / `verify_folder()`，使用 HMAC-SHA256 + 定时置换密钥。

```python
# src/agent_memory/integrity.py
import hmac, hashlib, secrets
from pathlib import Path
from typing import Optional

def _key_from_env() -> bytes:
    """从 env 读取，否则报错。不允许默认值。\"\"\"
    import os
    k = os.environ.get("AGENT_MEMORY_HMAC_KEY", "")
    if not k:
        raise RuntimeError(
            "AGENT_MEMORY_HMAC_KEY is required for folder integrity. "
            "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\" "
            "and set it before sign/verify."
        )
    return k.encode("utf-8")

def sign_file(md_path: Path, key: bytes) -> Path:
    """计算单个 .md 的 HMAC-SHA256，写入 .md.sig。\"\"\"
    data = md_path.read_bytes()
    sig = hmac.new(key, data, hashlib.sha256).hexdigest()
    sig_path = md_path.with_suffix(".md.sig")
    sig_path.write_text(sig, encoding="utf-8")
    return sig_path

def verify_folder(folder: Path, key: bytes) -> tuple[bool, list[str]]:
    """校验文件夹下所有 .md 的签名。
    
    Returns:
        (all_ok, failed_ids): all_ok=True 且 failed_ids 为空 → 全部通过
    \"\"\"
    failed = []
    for md in folder.glob("*.md"):
        sig_path = md.with_suffix(".md.sig")
        if not sig_path.exists():
            failed.append(md.stem + " (no .sig)")
            continue
        expected = hmac.new(key, md.read_bytes(), hashlib.sha256).hexdigest()
        actual = sig_path.read_text().strip()
        if not hmac.compare_digest(expected, actual):
            failed.append(md.stem + " (sig mismatch)")
    return (len(failed) == 0, failed)

# CLI 调用
# python -m agent_memory.cli sign-folder  -> 调用 sign_file 靠该文件夹
# python -m agent_memory.cli verify       -> 调用 verify_folder，不通过退出码 5
```

**安全设计**：

- **不允许缺省密钥**：`AGENT_MEMORY_HMAC_KEY` 缺失直接 `RuntimeError`，防止“空密钥”。
- **用 `hmac.compare_digest`**：防止时间差异攻击。
- **仅签 .md**：`.vec.json` / `.meta.json` 可从 .md 重生，不需额外签名。
- **未签名的文件**被视为不可信，**默认拒绝加载**；需要显式 `--trust` 参数。

**验证**：

```bash
# 创建签名
python -m agent_memory.cli sign-folder memory/
# 修改某个文件后，验证应报错
echo "{}" >> memory/abc.md
python -m agent_memory.cli verify
# echo $?  # 期望 5；实际：✔
```


---

### 17.5 写入不阻塞（fire-and-forget）

**问题**：v0.2 README 承诺“后台入队”，但 v0.1 实现是同步写，AI Agent 调用 `add` 会被文件 IO 阻塞。

**修复**：`memory_manager.add()` 改为 `ThreadPoolExecutor` 后台写，调用者立即拿到 `memory_id`。

```python
# src/agent_memory/memory_manager.py
from concurrent.futures import ThreadPoolExecutor
import uuid

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="mem-sync")

class MemoryManager:
    def add(self, content: str, ...) -> str:
        """立即返回 memory_id。L4 + L3 写入在后台。\"\"\"
        memory_id = str(uuid.uuid4())
        _executor.submit(self._add_sync, memory_id, content, ...)
        return memory_id  # 不等待磁盘 IO

    def _add_sync(self, memory_id: str, content: str, ...) -> None:
        try:
            # 1. L4 写入（强同步，失败抛异常→ audit log）
            meta = MemoryMeta(id=memory_id, ...)
            vec = MemoryVec(id=memory_id, ...)
            self._l4.save(memory_id, content, meta, vec)

            # 2. L3 同步（弱同步，失败只记 log）
            if self._embedder:
                try:
                    emb = self._embedder.embed_sync(content)
                    self._l3.upsert(memory_id, emb, meta.to_dict())
                except Exception as e:
                    log.warning(f"L3 sync failed for {memory_id}: {e}")
        except Exception as e:
            log.error(f"add_sync failed: {memory_id}: {e}", exc_info=True)
            # 不重试：下次启动时 sync_all() 会补临时丢失的
```

**优势**：

- **不阻塞 Agent**：`add()` 返回 < 1ms（只生成 UUID）。
- **背压护航**：线程池 4 worker，不会无限堆积任务。
- **启动时补临**：`MemoryManager.__init__` 中调用 `sync_all()` 补上次未同步成功的记忆。

---

### 17.6 P0 修复总览

| P0 编号 | 原评审编号 | 问题 | 修复点 | 验证方法 |
|------|------|------|------|------|
| P0-1 | H-05 | 无 Key 时隐式降级假向量 | `DashScopeEmbedder.__init__` 严格校验；不走默认 | `unset KEY; DashScopeEmbedder()` 中抛 `RuntimeError` |
| P0-2 | H-04 | 存储型 Prompt 注入 | `sync_one()` 调 `check_injection()`，调 `trust_score` | 写入“忽略以上”后检索该条被 `trust_score=0.3` |
| P0-3 | H-01 | 多进程并发写无锁 | `L4FilesStore.save/delete` 用 `filelock` + 原子写 | 50 并发 `add` 验证不丢失 |
| P0-4 | H-03 | 热插拔文件夹未签名 | `integrity.sign_file/verify_folder`；未签名默认拒负 | 篡改 `.md` 后 `verify` 返回退出码 5 |

> 另外 **H-02**（写入无原子性）在 P0-3 的 `_atomic_write()` 中通过 `tempfile + os.replace + fsync` 同时解决。

### 17.7 未来安全道路图（v0.4）

| 优先级 | 项目 | 描述 |
|------|------|------|
| P1 | base_url 方案校验（M-01） | 不以 `https://` 开头抛 `ValueError`。防 HTTP 明文泄露 API Key。 |
| P1 | config.json 字段白名单（M-02） | `_deep_merge` 只接受预定义字段，忽略未知。防 SSRF 与误配置。 |
| P1 | from_dict schema 严格校验（M-03） | 仅接受白名单字段；vector 维度 ≥ 0且不超过 4096；content < 100KB。 |
| P1 | 忘记前先 archive（M-06） | 删除记忆进入 `memory/.trash/`，30 天后真正清理。防误删。 |
| P2 | Markdown 转义（M-05） | 写入 `.md` 前转义特殊字符。防存储型 XSS。 |
| P2 | 向量维度 + 离群点校验（M-09） | 发现超大 / NaN 向量报警，防“最近邻劫持”。 |
| P2 | 审计日志（A09） | 高 importance 的 store / delete / decay 全部进 audit.log。 |
| P2 | `httpx` 不跟随重定向（A10） | `follow_redirects=False`。防中间人攻击。 |
| P3 | bge-large-zh 本地向量模型 | 隐私场景，避免 DashScope 云端依赖。默认依赖 600MB，但零代理依赖。 |
| P3 | per-folder 加密 | PBKDF2 从用户密码派生密钥，静态加密 `vec.json`。 |
| P3 | 多 Agent 信任模型 | 明确 share 与 isolate 模式：仅同 namespace 可互访。 |
| P3 | 灾难恢复 | 每天自动 backup 到 `memory/.backup/YYYYMMDD/`。 |

---

_本章作者：架构师 ⚔️（安全补充说明）_
_最后更新：2026-06-07_
