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
| 代码 | ⚠️ **以 GitHub v2.0.1 为准** | **本地副本是 v0.1（过期），不要改本地 v0.1** |
| 向量库同步 | ⚠️ 手动 | 142条历史记忆手动导入 LanceDB，不是系统自动跑 |

### ⚠️ 关键澄清：本地副本是 v0.1（过期）

| 路径 | 版本 | 说明 |
|------|------|------|
| `C:\Users\31683\.openclaw\workspace\AgentMemory\` | **v0.1（过期）** | 四层架构，与 v0.3 哲学不符 |
| `https://github.com/YintaTriss/AgentMemory` HEAD | **v2.0.1（准）** | 双轨+图书馆，对齐 v0.3 哲学 |

**实现任务基于 GitHub v2.0.1，清理本地过期内容后再开始。**

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

### 第一步：先清本地过期副本

**注意：这步必须先做，否则会在错误基础上继续开发。**

1. 将 `C:\Users\31683\.openclaw\workspace\AgentMemory\` 标记为 DEPRECATED
2. 从 GitHub clone/fetch 最新 v2.0.1 到工作树
3. 确认 `git log --oneline` 显示 v2.0.1 tag 或 commit

### 第二步：分析 v2.0.1 现有代码

在实现新功能前，先通读 GitHub v2.0.1 最新代码：
- `src/agent_memory/` 目录结构
- 已有接口（`Protocol` 定义）
- 已实现的 `Library` / `SearchEngine` / `MemoryManager`

### 第三步：补充缺失的安全 P0（来自安全审查）

**来源：** `agentmemory-security-review.md`，综合评分 5.5/10，2 个 P0 未处理。

#### 安全 P0-1：API密钥明文/无校验

**问题：** Embedder API Key 直接读写，无校验，Key 缺失时系统静默降级为假向量
**修复：**
```python
# 启动时校验
def _validate_api_key(self) -> None:
    if not os.environ.get(self.api_key_env):
        raise RuntimeError(
            f"{self.__class__.__name__} requires {self.api_key_env} env var. "
            "Do NOT fall back to MockEmbedder silently."
        )
```
**验证：** 故意不设置 API Key，启动时必须报错，不允许静默成功。

#### 安全 P0-2：缺 API 注入校验

**问题：** 用户输入直接拼入 LLM 上下文，无消毒，可能被 prompt 注入
**修复：**
1. 用户输入进入向量存储前，做指令性关键词检测（"忽略之前"、"忘记以上"等）
2. 检测到则记录警告，不阻塞但标记来源不可信
3. LLM 输出到结构化字段前做 schema 校验

#### 安全 P0-3：并发写无锁（H-01）

**问题：** 多进程/多线程并发写同一文件可能损坏状态
**修复：**
```python
import fcntl  # Unix
# 或 Windows: msvcrt + file locking
# 或跨平台: filelock 库
```
至少实现文件锁，确保同一时间只有一个写操作。

#### 安全 P0-4：热插拔无签名（H-03）

**问题：** 恶意文件夹可注入 prompt 或瘫痪加载
**修复：**
```python
import hmac, hashlib

def verify_folder_integrity(folder_path: str, hmac_key: bytes) -> bool:
    """HMAC-SHA256 over all .md files in folder"""
    for md_file in Path(folder_path).glob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        expected = hmac.new(hmac_key, content.encode(), hashlib.sha256).hexdigest()
        sig_file = md_file.with_suffix(".md.sig")
        if not sig_file.exists():
            return False
        if not hmac.compare_digest(expected, sig_file.read_text()):
            return False
    return True
```
文件夹加载前校验 `.md.sig` 签名，不通过则拒绝加载。

### 第四步：真正实现"写入不阻塞"

**问题来源：** v2.0.1 评审发现 README 承诺"后台入队"，代码实际是同步。
**修复：** `memory_manager.store` 改为 fire-and-forget 队列：
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=4)

def store(self, memory_id: str, content: str) -> None:
    """立即返回，写入线程池后台完成"""
    _executor.submit(self._store_sync, memory_id, content)
```

### 第五步：L4 文件系统（已有部分，检查完整性）

检查 v2.0.1 现有实现是否包含：
- `save(id, content, metadata)` → 写 `<id>.md` + `<id>.meta.json`
- `load(id)` → 读 md 内容
- `list()` → 列出所有记忆 id
- `delete(id)` → 删除三个文件

### 第六步：L3 LanceDB 向量检索（已有部分）

检查 v2.0.1 现有实现是否包含：
- `upsert(id, content, vector)` → 写入 LanceDB
- `search(query_vector, top_k)` → 语义检索
- `delete(id)` → 删除记录

### 第七步：L1 记忆压缩

实现 `L1LCMCompressor`：
- `compress(memory_ids)` → 从 L4 读取多条记忆，压缩为适合上下文的摘要
- 输出格式：分段叙述 + 关键事实列表

### 第八步：CLI 入口

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
- [ ] API Key 缺失时启动报错（不静默降级）
- [ ] 并发写有文件锁保护
- [ ] 文件夹加载有 HMAC 校验
- [ ] 推送 GitHub master

---

## 五、技术约束

- **Python：** 3.13
- **向量库：** LanceDB（本地，无需服务器）
- **Embedding：** 本地 `bge-large-zh`（免费），或 API
- **无外部依赖服务：** 不能有 PostgreSQL/Redis/Qdrant 等需要独立部署的服务
- **安全必读：** `C:\Users\31683\AppData\Local\Programs\SpectrAI\reports\agentmemory-security-review.md`

---

## 六、已有参考

- 架构：`ARCHITECTURE-v0.3.md`
- GitHub v2.0.1 最新代码（克隆到本地后阅读）
- 安全审查：`C:\Users\31683\AppData\Local\Programs\SpectrAI\reports\agentmemory-security-review.md`
- 综合评估：`C:\Users\31683\AppData\Local\Programs\SpectrAI\reports\agentmemory-final-review.md`
