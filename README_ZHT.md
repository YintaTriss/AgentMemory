<p align="center">
  <a href="README_EN.md">English</a> |
  <a href="README.md">简体中文</a> |
  <a href="README_ZHT.md">繁體中文</a> |
  <a href="README_JA.md">日本語</a> |
  <a href="README_KO.md">한국어</a> |
  <a href="README_FR.md">Français</a>
</p>

# AgentMemory v0.3

> **雙軌 + 圖書館記憶系統** — 為 AI Agent 打造的持久化、可遷移、熱插拔的記憶基礎設施

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)

---

## 設計哲學：記憶如圖書館

> **書籍本身不變，但目錄系統讓查找變得精確。**

傳統記憶系統的核心矛盾：**語義搜索（模糊匹配）與精確分類（按領域篩選）只能二選一**。

AgentMemory 的答案：**雙軌並存，永不取捨。**

同一份記憶同時存在於兩條軌道：

```
同一份記憶：
├─ 圖書館分類軌（.md 本體 + .meta.json 元數據）→ 精確查找，管理邊界
└─ Embedding 向量軌（.vec.json）→ 語義搜索，模糊匹配
```

**顆粒度保證**：最少 3 層分類（館分類 / 書架分類 / 書分類），確保每一份記憶都能被精確歸類，最大層數不設限，按需延伸。

---

## 架構總覽

```
┌──────────────────────────────────────────────────────────────┐
│                     宿主應用 (Agent / CLI / Web API)        │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│  MemoryManager（統一異步 API）                                │
│  add() / get() / delete() / search() / list() / compress() │
└────────────────────────────┬─────────────────────────────────┘
                             │
          ┌──────────────────┴──────────────────┐
          ▼                                      ▼
┌─────────────────────┐              ┌─────────────────────────┐
│   L4FilesStore      │              │   L3LanceDBStore        │
│   （文件持久化）      │              │   （向量語義搜索）        │
│                     │              │                         │
│  memory/<id>.md     │◄──── sync ──►│  LanceDB Table         │
│  memory/<id>.meta   │              │  (語義相似度檢索)        │
│  memory/<id>.vec.json              │                         │
└─────────────────────┘              └─────────────────────────┘
          │                                      │
          ▼ (讀取時)                              │
┌─────────────────────┐              ┌─────────────────────────┐
│   L1LCMCompressor   │              │   BM25 混合檢索          │
│   （上下文壓縮）      │              │   (純 Python, 零依賴)    │
│                     │              │                         │
│  實體提取 → 摘要     │              │  k1=1.2, b=0.75         │
│  → AI Context 注入   │              │  α=0.7 (向量/BM25)       │
└─────────────────────┘              └─────────────────────────┘
```

### 三層職責

| 層級 | 組件 | 職責 |
|------|------|------|
| **L4** | `L4FilesStore` | `.md` 內容 + `.meta.json` 元數據 + `.vec.json` 向量，檔案系統持久化 |
| **L3** | `L3LanceDBStore` | LanceDB 向量搜索（不可用時自動降級為純 JSON + numpy），支援 BM25 混合檢索 |
| **L1** | `L1LCMCompressor` | 記憶壓縮為摘要 + 實體列表，注入 AI prompt 時使用，支援 query 相關性增強 |
| **L3** | `SyncManager` | L4 ↔ L3 雙軌同步，自動同步關鍵詞檢測，portalocker 檔案鎖 |
| **L3** | `LibraryClassifier` | 5 大頂層類自動分類，關鍵詞歸一化評分，緩存分詞 |
| **L3** | `IntegrityVerifier` | HMAC-SHA256 檔案完整性簽名，防篡改 |

### 雙軌檢索

| 軌道 | 方法 | 適用場景 |
|------|------|---------|
| **軌道一** | 圖書館分類（category_path / tags） | 精確查找、按領域篩選 |
| **軌道二** | Embedding 向量（語義相似度） | 模糊搜索、語義關聯 |

### 圖書館分類規範

最少 3 層（館分類 / 書架分類 / 書分類，確保顆粒度），最大不設限，動態層數：

```
項目/石榴籽/語料/NLLB訓練                 ✅ 最少 3 層
項目/石榴籽/語料/NLLB訓練/2026-06           ✅ 可繼續延伸（不設上限）
學習/AI/Transformer                        ✅ 3 層
AI/Agent/記憶系統/VCP                      ✅ 4 層
```

---

## 核心組件

| 組件 | 檔案 | 說明 |
|------|------|------|
| `MemoryManager` | `manager.py` | 統一異步 API，add/get/delete/search/list/compress |
| `L4FilesStore` | `l4_files.py` | md + meta.json + vec.json 三檔案存儲，portalocker 檔案鎖 |
| `L3LanceDBStore` | `l3_lancedb.py` | LanceDB 向量搜索 + JSON Fallback + BM25 混合檢索 |
| `L1LCMCompressor` | `l1_lcm.py` | 上下文壓縮，FactType 實體提取，query 相關性增強 |
| `SyncManager` | `sync.py` | L4 ↔ L3 雙軌同步，auto_sync 關鍵詞檢測 |
| `LibraryClassifier` | `library.py` | 5 大類關鍵詞分類，層級路徑驗證，緩存分詞 |
| `Embedder` | `embedder.py` | HashEmbedder（零依賴）/ DashScopeEmbedder（OpenAI-Compatible API）|
| `IntegrityVerifier` | `integrity.py` | HMAC-SHA256 簽名驗證 |

---

## 數據結構

每條記憶 = 同目錄下的 3 個檔案：

```
memory/
├── abc123.md           # 人類可讀內容
├── abc123.meta.json   # 元數據
└── abc123.vec.json    # 向量數據（每個記憶一個，隨 .md 同目錄）
```

### meta.json 格式

```json
{
  "id": "abc123...",
  "created_at": "2026-06-07T00:00:00",
  "updated_at": "2026-06-07T00:00:00",
  "category_path": "Project/Shiliuzi/Training",
  "tags": ["nllb", "success"],
  "source": "manual",
  "importance": 0.8,
  "trust_score": 1.0,
  "flagged": false,
  "signed_at": 1759804800.123
}
```

---

## 實現細節：那些讓代碼更優雅的小巧思

### 原子寫入：tempfile + os.replace（Windows 相容）

L4 檔案寫入使用兩步原子操作：

```python
# 1. 寫入臨時檔案
tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tmp", dir=base_dir)
tmp.write(content); tmp.close()
# 2. os.replace 原子替換（Windows 也保證原子性）
os.replace(tmp.name, target_path)
```

os.rename 在 Windows 上不能跨驅動器工作，os.replace 則可以。這是很多跨平台 Python 專案的盲區。

### portalocker：跨平台檔案鎖

```python
with _portalocker_lock(lock_path):
    # 寫操作自動加鎖
    ...
```

`portalocker` 優先，Windows 用 msvcrt，Unix 用 fcntl 回退。讀操作，用共享鎖；寫操作，用獨占鎖。`contextmanager` 模式確保鎖一定釋放，即使異常也不漏。

### `_embed_fn` 模式：sync/async 統一介面

DashScopeEmbedder 的 `embed()` 是 `async def`，HashEmbedder 是 `def`，調用方用統一介面：

```python
# SyncManager.__init__ 中：
if hasattr(embedder, 'embed_sync'):
    self._embed_fn = embedder.embed_sync
else:
    self._embed_fn = embedder.embed
```

運行時檢測，不需要類型判斷。Embedder 基類提供 `embed_sync` 屬性，async 實現包裝為子線程運行。

### 緩存分詞（LibraryClassifier）

關鍵詞匹配時每次都重新分詞是浪費。`_tokenize()` 用 `@functools.lru_cache(maxsize=512)` 緩存：

```python
@functools.lru_cache(maxsize=512)
def _tokenize(self, text: str) -> tuple[str, ...]:
    ...
    return tuple(tokens)  # tuple 可雜湊，才能做 lru_cache 的 key
```

返回 `tuple` 而非 `list`，因為 tuple 可雜湊適合做緩存 key。

### 評分歸一化：sqrt(keyword_count) 防止大類欺負小類

分類詞典中「項目」有 20+ 個關鍵詞，「偏好」只有 8 個。直接累加會導致大類永遠勝出。

```python
scores[category] = cat_raw / (len(keywords) ** 0.5)  # 開方歸一化
```

用 `sqrt` 而非直接除以 `len(keywords)`：大列表有幫助，但不能主導結果。

### Unicode 規範化 + 雙軌檢測（injection.py）

檢測混淆攻擊需要兩步：

```python
texts_to_check = [text, _normalize_text(text)]  # 原始文字 + 規範化文字
```

規範化步驟包括：零寬字元處理、HTML 實體 decode、全形→半形、Unicode 轉義序列解碼、反斜線詞還原、BIDI 控制符清除。混淆攻擊（`rm\u200b-rf`、`rm&#x72;f`）在規範化後無處遁形。

### BM25 參數可配置

BM25 的 `k1`（詞頻飽和）和 `b`（文檔長度歸一化）可按場景調整：

```python
# k1=1.2, b=0.75 是 Lucene 預設值
l3_store.search_bm25(query, top_k=5, k1=1.2, b=0.75)
```

### 混合搜索 α 加權可調

向量相似度和 BM25 的混合權重 α 預設 0.7（向量 70%，BM25 30%）：

```python
alpha = 0.7
final_score = alpha * vec_score + (1 - alpha) * bm25_score
```

### 5 分鐘 stats 緩存

`MemoryManager.stats()` 有本地緩存，避免每次都讀檔案系統：

```python
age = (datetime.now() - self._stats_timestamp).total_seconds()
if age < 300:  # 5 分鐘內直接返回緩存
    return self._stats_cache
```

### `access_count` 持久化（不是記憶體變數）

很多記憶系統把訪問計數放記憶體，重啟就丟。AgentMemory 把 `access_count` 寫回 `.meta.json`，每次 `load_existing()` 自動 +1 並持久化。

### query 參數增強 L1 壓縮的相關性排序

`compress_for_context(memory_ids, query="...")` 支援 query 參數，同 query 關鍵詞重合的記憶在同重要性層級中排到前面：

```python
def _relevance_score(mem):
    if not query_toks: return 0
    return sum(1 for tok in query_toks if tok in mem.get("content","").lower())
```

---

## 安全防護（P0 級）

| 防護項 | 實現位置 | 說明 |
|--------|----------|------|
| **注入檢測** | `utils/injection.py` | Unicode 規範化 + 雙軌檢測（原始/規範化雙重匹配），50+ 攻擊模式，含 JNDI/SSTI/Shellshock/Prompt Injection |
| **trust_score** | `sync.py` | < 0.2 拒絕寫入 L3，≤ 0.35 標記 flagged 並警告 |
| **HMAC 驗證** | `integrity.py` | HMAC-SHA256 簽名，寫入 `.meta.json` 的 `signed_at` 欄位 |
| **API Key 校驗** | `embedder.py` | `DashScopeEmbedder.__init__` 立即校驗，缺失拋 RuntimeError |
| **LanceDB 注入防護** | `web.py` / `cli.py` | category_path 中單引號轉義為 `''`（SQL 標準轉義）|
| **原子寫入** | `l4_files.py` | tempfile + os.replace，進程崩潰也不留髒檔案 |
| **檔案鎖** | `l4_files.py` | portalocker 獨占鎖，寫操作互斥 |

---

## 並發安全

寫入安全由 `portalocker` 保證，Windows 回退到 `msvcrt`，Unix 回退到 `fcntl`：

```python
# L4FilesStore 寫操作：自動加獨占鎖
with _portalocker_lock(lock_path):
    ...

# 讀操作：自動加共享鎖
with _file_lock(lock_path, exclusive=False):
    ...
```

---

## 安裝

```bash
cd AgentMemory
pip install -e .
```

### 依賴項

**運行時依賴（僅有 3 個，無需其他服務）：**

```
httpx>=0.25.0    # DashScope API 異步調用
aiofiles>=23.0.0 # 異步檔案 IO
pydantic>=2.5    # 數據驗證（運行時必需）
```

**可選依賴：**

```bash
pip install agentmemory[web]     # Web API 支援（fastapi + uvicorn）
pip install agentmemory[lancedb] # LanceDB 向量資料庫（高效能場景）
pip install agentmemory[dev]    # 開發依賴（pytest 等）
```

> LanceDB 不可用時（未安裝），系統自動降級為純 JSON + numpy 實現，零額外依賴即可運行。

### Embedder 選擇

```python
from agent_memory import MemoryManager, get_embedder

# 預設（auto 模式）：無 API Key → HashEmbedder（零依賴，離線可用）
#                    有 EMBEDDING_API_KEY → OpenAI-Compatible 嵌入（任意相容 provider）
mm = MemoryManager()

# 顯式指定（無 API Key 時立即拋 RuntimeError，不靜默降級）
mm = MemoryManager(embedder=get_embedder(backend="openai-compat"))

# 等價於預設 auto 模式
mm = MemoryManager(embedder=get_embedder())
```

> **模型不綁定**：內部使用 OpenAI-Compatible API 格式，自動識別任意支援 `/v1/embeddings` 介面的 provider（DashScope / Minimax / OpenAI / 本地 Embedding Server 等）。

### 環境變數

| 變數 | 預設 | 說明 |
|------|------|------|
| `AGENT_MEMORY_DIR` | `memory` | 記憶存儲目錄 |
| `AGENT_MEMORY_DATA_DIR` | `data` | 向量數據目錄（LanceDB 表 / JSON Fallback） |
| `EMBEDDING_API_KEY` | - | OpenAI-Compatible API（推薦，支援任意相容 provider） |
| `DASHSCOPE_API_KEY` | - | 向後相容，與 `EMBEDDING_API_KEY` 二選一 |
| `OPENAI_API_KEY` | - | 向後相容 |

---

## 快速開始

### Python API

```python
import asyncio
from agent_memory import MemoryManager

async def main():
    mm = MemoryManager()

    # 添加記憶
    mem_id = await mm.add(
        content="NLLB 訓練成功完成，詞彙準確率達到 85%",
        category_path="Project/Shiliuzi/Training",
        tags=["nllb", "success", "training"],
        importance=0.9
    )
    print(f"Added: {mem_id}")

    # 語義搜索（預設 vector 模式）
    results = await mm.search("NLLB 模型訓練")
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:60]}")

    # 按分類列出
    all_memories = await mm.list(category_path="Project/Shiliuzi")
    print(f"Found {len(all_memories)} memories")

    # 統計
    stats = await mm.stats()
    print(f"Total: {stats['total_memories']}, Categories: {stats['categories']}")

    # L1 壓縮（注入 AI Context）
    # query 參數：與 query 相關性高的記憶優先展示
    compressed = await mm.compress_for_context([mem_id], query="NLLB訓練")
    print(compressed)

    # 刪除
    await mm.delete(mem_id)

asyncio.run(main())
```

### CLI

```bash
# 添加記憶（自動分類）
python -m agent_memory.cli add "測試記憶"

# 指定分類和標籤
python -m agent_memory.cli add "NLLB訓練完成" --category "Project/Shiliuzi/Training" --tags "nllb,done"

# 語義搜索（預設）
python -m agent_memory.cli search "NLLB 模型訓練"

# 關鍵詞搜索（BM25，無需向量模型）
python -m agent_memory.cli search "NLLB" --mode bm25

# 混合搜索（向量 + BM25 加權）
python -m agent_memory.cli search "NLLB" --mode hybrid

# 列出所有
python -m agent_memory.cli list

# 按分類列出
python -m agent_memory.cli list --category "Project/Shiliuzi"

# 查看單條
python -m agent_memory.cli show <memory_id>

# 統計
python -m agent_memory.cli stats

# 刪除
python -m agent_memory.cli delete <memory_id>

# 顯示所有頂層分類
python -m agent_memory.cli category --show-all

# 顯示已使用的所有分類路徑
python -m agent_memory.cli category --list

# HMAC 簽名（新加入的資料夾需要簽名）
python -m agent_memory.cli sign memory/ --key "your-secret-key-here"

# HMAC 校驗（驗證資料夾完整性）
python -m agent_memory.cli verify memory/ --key "your-secret-key-here"

# 重新向量化（更換 embedder 時使用）
python -m agent_memory.cli --json reembed --embedder hash

# 啟動 Web API 伺服器
python -m agent_memory.cli serve --port 8765
```

### MemoryManager API

| 方法 | 返回 | 說明 |
|------|------|------|
| `add(content, category_path, tags, importance)` | `str` (memory_id) | 添加記憶，L4 + L3 雙軌寫入 |
| `get(memory_id)` | `dict \| None` | 按 ID 獲取 |
| `delete(memory_id)` | `bool` | 刪除，L4 + L3 + vec.json 同時清除 |
| `search(query, limit, category_path, mode)` | `list[dict]` | 向量/BM25/混合搜索，支援 mode=vector/bm25/hybrid |
| `list(category_path, limit)` | `list[dict]` | 按分類列出 |
| `compress_for_context(memory_ids, query)` | `str` | L1 壓縮，query 參數增強同 query 相關記憶的優先級 |
| `stats()` | `dict` | 統計（5 分鐘緩存），總數/分類/存儲大小/L3 覆蓋率 |

---

## 與其他系統對比

| 系統 | 數據形態 | 索引方式 | 多 Agent | NAS 支援 | 無外部服務依賴 |
|------|---------|---------|---------|---------|-------|
| Hermes | 檔案 | 無向量 | 共享工作空間 | 原生 | ✅ |
| VCP | 檔案 + 向量雙軌 | Tag + 向量 | 共用資料夾 | SQLite 單檔 | ✅ |
| Mem0 | 向量 + 圖關係 | 向量 + 關係圖 | 多租戶 | 需資料庫 | ❌ |
| Letta | Memory Blocks | 塊索引 | Agent 記憶體 | 需服務 | ❌ |
| **AgentMemory v0.3** | md + vec.json | 雙軌檢索 | 共用資料夾 | 原生 | ✅ |

---

## 架構決策記錄（v0.3）

| 決策 | 說明 | 原因 |
|------|------|------|
| 去掉 L2 Graph-DB | 三層變四層 | Graph-DB 過度設計，實際只用分類路徑就夠了 |
| 去掉了相變機制 | 檔案 + 向量永遠是雙軌 | VCP 驗證：不需要相變 |
| 並發寫入控制 | portalocker 檔案鎖 | 多 Agent 並發寫入場景 |
| Embedder 預設 Hash | 零依賴、確定性 | 生非異也，善假於物也 |
| LanceDB 優先 + JSON Fallback | LanceDB 不可用自動降級 | 高效能場景用 LanceDB，零依賴場景用 JSON |
| BM25 混合檢索 | 純 Python 實現，零額外依賴 | 補充純關鍵詞搜索場景，無需向量模型 |
| min_depth=3 | 館/架/書三層結構 | 確保記憶顆粒度，避免頂層過於籠統 |

---

## 授權

MIT License — 可自由使用、修改和分發。

---

_AgentMemory — 記憶如圖書館，雙軌並存，永不取捨。_
