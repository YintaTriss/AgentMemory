<p align="center">
  <a href="README_EN.md">English</a> |
  <a href="README.md">简体中文</a> |
  <a href="README_ZHT.md">繁體中文</a> |
  <a href="README_JA.md">日本語</a> |
  <a href="README_KO.md">한국어</a> |
  <a href="README_FR.md">Français</a>
</p>

# AgentMemory v0.3

> **デュアルトラック＋図書館記憶システム** — AI Agent向けの永続化・移植可能・ハotswap可能な記憶インフラストラクチャ

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)

---

## 設計思想：記憶を図書館のように

> **本そのものは変わらないが、目次システムがあれば検索が正確になる。**

従来の記憶システムが直面する根本的矛盾：**セマンティック検索（ファジー一致）と精密な分類（ドメインフィルタリング）は両立できない**。

AgentMemoryの答え：**両方のトラック并存、決して妥協しない。**

同じ記憶が同時に2つのトラックに存在：

```
同じ記憶：
├─ 図書館分類トラック（.md本体 + .meta.jsonメタデータ）→ 精密検索、管理境界
└─ Embeddingベクトルトラック（.vec.json）→ セマンティック検索、ファジー一致
```

**粒度の保証**：最低3層分類（図書館/書架/本分類）を確保し、すべての記憶が正確に分類できることを保証 最大層数に制限なし、必要に応じて延伸可能。

---

## アーキテクチャ概要

```
┌──────────────────────────────────────────────────────────────┐
│                     ホストアプリ (Agent / CLI / Web API)     │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│  MemoryManager（統合非同期API）                               │
│  add() / get() / delete() / search() / list() / compress() │
└────────────────────────────┬─────────────────────────────────┘
                             │
          ┌──────────────────┴──────────────────┐
          ▼                                      ▼
┌─────────────────────┐              ┌─────────────────────────┐
│   L4FilesStore      │              │   L3LanceDBStore        │
│   （ファイル永続化）  │              │   （ベクトル意味検索）    │
│                     │              │                         │
│  memory/<id>.md     │◄──── sync ──►│  LanceDB Table         │
│  memory/<id>.meta   │              │  (意味的類似度検索)      │
│  memory/<id>.vec.json              │                         │
└─────────────────────┘              └─────────────────────────┘
          │                                      │
          ▼ (読み取り時)                          │
┌─────────────────────┐              ┌─────────────────────────┐
│   L1LCMCompressor   │              │   BM25 ハイブリッド検索  │
│   （コンテキスト圧縮）│              │   (Pure Python, 依存ゼロ)│
│                     │              │                         │
│  エンティティ抽出→要約│              │  k1=1.2, b=0.75         │
│  → AI Context注入    │              │  α=0.7 (vector/BM25)   │
└─────────────────────┘              └─────────────────────────┘
```

### 3層の責任

| 層 | コンポーネント | 責任 |
|-----|--------------|------|
| **L4** | `L4FilesStore` | `.md`コンテンツ + `.meta.json`メタデータ + `.vec.json`ベクトル、ファイルシステム永続化 |
| **L3** | `L3LanceDBStore` | LanceDBベクトル検索（利用不可時は自動的にPure JSON + numpyにフォールバック）、BM25ハイブリッド検索対応 |
| **L1** | `L1LCMCompressor` | 記憶を要約 + エンティティリストに圧縮、AIプロンプト注入時に使用、query関連性強化をサポート |
| **L3** | `SyncManager` | L4 ↔ L3 デュアルトラック同期、auto_syncキーワード検出、portalockerファイルロック |
| **L3** | `LibraryClassifier` | 5大トップレベルカテゴリ自動分類、キーワード正規化スコアリング、キャッシュトークン化 |
| **L3** | `IntegrityVerifier` | HMAC-SHA256ファイル整合性署名、改ざん検出 |

### デュアルトラック検索

| トラック | 方式 | 最適な用途 |
|---------|------|-----------|
| **トラック1** | 図書館分類（category_path / tags） | 精密検索、ドメインフィルタリング |
| **トラック2** | Embeddingベクトル（意味的類似度） | ファジー検索、意味的関連 |

### 図書館分類規則

最低3層（図書館/書架/本—粒度を確保）、最大層数無制限、動的深度：

```
プロジェクト/石榴籽/コーパス/NLLB訓練                 ✅ 最低3層
プロジェクト/石榴籽/コーパス/NLLB訓練/2026-06           ✅ 無限に延伸可能
学習/AI/Transformer                                ✅ 3層
AI/Agent/記憶システム/VCP                      ✅ 4層
```

---

## コアコンポーネント

| コンポーネント | ファイル | 説明 |
|--------------|---------|------|
| `MemoryManager` | `manager.py` | 統合非同期API：add/get/delete/search/list/compress |
| `L4FilesStore` | `l4_files.py` | md + meta.json + vec.json トリプルファイルストレージ、portalockerファイルロック |
| `L3LanceDBStore` | `l3_lancedb.py` | LanceDBベクトル検索 + JSON Fallback + BM25ハイブリッド検索 |
| `L1LCMCompressor` | `l1_lcm.py` | コンテキスト圧縮、FactTypeエンティティ抽出、query関連性強化 |
| `SyncManager` | `sync.py` | L4 ↔ L3 デュアルトラック同期、auto_syncキーワード検出 |
| `LibraryClassifier` | `library.py` | 5カテゴリキーワード分類、階層パス検証、キャッシュトークン化 |
| `Embedder` | `embedder.py` | HashEmbedder（依存ゼロ）/ DashScopeEmbedder（OpenAI-Compatible API）|
| `IntegrityVerifier` | `integrity.py` | HMAC-SHA256署名検証 |

---

## データ構造

各記憶 = 同一ディレクトリ内の3ファイル：

```
memory/
├── abc123.md           # 人間が読めるコンテンツ
├── abc123.meta.json   # メタデータ
└── abc123.vec.json    # ベクトルデータ（記憶ごとに1つ、.mdと同じディレクトリ）
```

### meta.json形式

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

## 実装の詳細：コードを优雅にする小手先の技

### アトミック書き込み：tempfile + os.replace（Windows対応）

L4ファイル書き込みは2ステップのアトミック操作を使用：

```python
# 1. 一時ファイルに書き込み
tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tmp", dir=base_dir)
tmp.write(content); tmp.close()
# 2. os.replaceでアトミック置換（Windowsでもアトミックを保証）
os.replace(tmp.name, target_path)
```

os.renameはWindowsでクロスドライブ動作不行。os.replaceは可能。これは多くのクロスプレatform Pythonプロジェクトの盲点。

### portalocker：クロスプレatformファイルロック

```python
with _portalocker_lock(lock_path):
    # 書き込み操作は自動的にロック
    ...
```

`portalocker`を優先、Windowsはmsvcrt、Unixはfcntlにフォールバック。読み取りは共有ロック、書き込みは排他ロックを使用。`contextmanager`パターンは例外があってもロックが必ず解放されることを保証。

### `_embed_fn`パターン：sync/async統一インターフェース

DashScopeEmbedderの`embed()`は`async def`、HashEmbedderは`def`、呼び出し元は統一インターフェースを使用：

```python
# SyncManager.__init__内：
if hasattr(embedder, 'embed_sync'):
    self._embed_fn = embedder.embed_sync
else:
    self._embed_fn = embedder.embed
```

実行時検出、型チェック不要。Embedder基底クラスは`embed_sync`プロパティを提供、async実装はサブスレッドでラップ。

### キャッシュトークン化（LibraryClassifier）

キーワード一致のたびにトークン化をやり直すのは無駄。`_tokenize()`は`@functools.lru_cache(maxsize=512)`を使用：

```python
@functools.lru_cache(maxsize=512)
def _tokenize(self, text: str) -> tuple[str, ...]:
    ...
    return tuple(tokens)  # tupleはハッシュ可能、lru_cacheキーに適している
```

`list`ではなく`tuple`を返す—tupleはハッシュ可能でキャッシュ可能。

### スコアナル化：sqrt(keyword_count)で大きいカテゴリが小さい方を抑えないようにする

「プロジェクト」カテゴリは20+個のキーワードを持ち、「偏好」は8個だけ。単純な合計では大きいカテゴリが常に勝利：

```python
scores[category] = cat_raw / (len(keywords) ** 0.5)  # 平方根正規化
```

`sqrt`を`len(keywords)`で直接割る代わりに使用：大きいリストは助けになるが、主導にはならない。

### Unicode正規化 + デュアルトラック検出（injection.py）

難読化攻撃の検出には2ステップ必要：

```python
texts_to_check = [text, _normalize_text(text)]  # 元のテキスト + 正規化テキスト
```

正規化ステップ：ゼロ幅文字処理、HTMLエンティティデコード、全角→半角変換、Unicodeエスケープシーケンスデコード、バックスラッシュ語復元、BIDI制御文字削除。難読化攻撃（`rm\u200b-rf`、`rm&#x72;f`）は正規化後に暴露。

### BM25パラメータ設定可能

BM25の`k1`（項頻度飽和）と`b`（ドキュメント長正規化）はシナリオに応じて調整可能：

```python
# k1=1.2, b=0.75はLuceneのデフォルト値
l3_store.search_bm25(query, top_k=5, k1=1.2, b=0.75)
```

### ハイブリッド検索のα重み調整可能

ベクトル類似度とBM25のハイブリッド重みαはデフォルト0.7（ベクトル70%、BM25 30%）：

```python
alpha = 0.7
final_score = alpha * vec_score + (1 - alpha) * bm25_score
```

### 5分statsキャッシュ

`MemoryManager.stats()`はローカルキャッシュを持ち、毎回ファイルシステムを読み取ることを回避：

```python
age = (datetime.now() - self._stats_timestamp).total_seconds()
if age < 300:  # 5分以内ならキャッシュを返す
    return self._stats_cache
```

### `access_count`永続化（メモリ変数ではない）

多くの記憶システムはアクセス回数をメモリに保存—再起動で消失。AgentMemoryは`access_count`を`.meta.json`に書き戻し、`load_existing()`呼び出しごとに自動的に+1して永続化。

### queryパラメータによるL1圧縮関連性順序の強化

`compress_for_context(memory_ids, query="...")`はqueryパラメータをサポート；同じqueryキーワードを持つ記憶は、同じ重要度レベルで上位にランク付け：

```python
def _relevance_score(mem):
    if not query_toks: return 0
    return sum(1 for tok in query_toks if tok in mem.get("content","").lower())
```

---

## セキュリティ（P0レベル）

| 保護 | 実装場所 | 説明 |
|------|---------|------|
| **インジェクション検出** | `utils/injection.py` | Unicode正規化 + デュアルトラック検出（元/正規化両方をチェック）、50+攻撃パターン（JNDI/SSTI/Shellshock/Prompt Injection含む）|
| **trust_score** | `sync.py` | < 0.2はL3書き込みを拒否、≤ 0.35はflaggedをマークして警告 |
| **HMAC検証** | `integrity.py` | HMAC-SHA256署名、`.meta.json`の`signed_at`フィールドに書き込み |
| **API Key検証** | `embedder.py` | `DashScopeEmbedder.__init__`が即座に検証、欠落時はRuntimeErrorをスロー |
| **LanceDBインジェクション保護** | `web.py` / `cli.py` | category_pathの単一引用符を`''`にエスケープ（SQL標準）|
| **アトミック書き込み** | `l4_files.py` | tempfile + os.replace — クラッシュ해도ダーティファイルなし |
| **ファイルロック** | `l4_files.py` | portalocker排他ロック、書き込み操作は相互排他 |

---

## 並行安全性

書き込みの安全は`portalocker`で保証、Windowsは`msvcrt`、Unixは`fcntl`にフォールバック：

```python
# L4FilesStore書き込み：自動排他ロック
with _portalocker_lock(lock_path):
    ...

# 読み取り：自動共有ロック
with _file_lock(lock_path, exclusive=False):
    ...
```

---

## インストール

```bash
cd AgentMemory
pip install -e .
```

### 依存関係

**ランタイム依存（たった3つ、外部サービス不要）：**

```
httpx>=0.25.0    # DashScope API非同期呼び出し
aiofiles>=23.0.0 # 非同期ファイルI/O
pydantic>=2.5    # データ検証（ランタイム必需）
```

**オプション依存：**

```bash
pip install agentmemory[web]     # Web APIサポート（FastAPI + uvicorn）
pip install agentmemory[lancedb] # LanceDBベクトルデータベース（高性能シナリオ）
pip install agentmemory[dev]     # 開発依存（pytestなど）
```

> LanceDBが利用できない場合（未インストール）、システムは自動的にPure JSON + numpyにフォールバック—追加依存なしで実行可能。

### Embedder選択

```python
from agent_memory import MemoryManager, get_embedder

# デフォルト（autoモード）：API Keyなし → HashEmbedder（依存ゼロ、オフライン動作）
#                         API Keyあり → OpenAI-Compatible埋め込み（任意の互換provider）
mm = MemoryManager()

# 明示的指定（API Key 없을 때即座にRuntimeErrorをスロー、サイレントデグレードなし）
mm = MemoryManager(embedder=get_embedder(backend="openai-compat"))

# デフォルトautoモードと同等
mm = MemoryManager(embedder=get_embedder())
```

> **モデルロックなし**：内部的にOpenAI-Compatible API形式を使用、`/v1/embeddings`をサポートする任意のproviderを自動検出（DashScope / Minimax / OpenAI / ローカルEmbedding Serverなど）。

### 環境変数

| 変数 | デフォルト | 説明 |
|------|----------|------|
| `AGENT_MEMORY_DIR` | `memory` | 記憶ストレージディレクトリ |
| `AGENT_MEMORY_DATA_DIR` | `data` | ベクトルデータディレクトリ（LanceDBテーブル / JSON Fallback） |
| `EMBEDDING_API_KEY` | - | OpenAI-Compatible API（推奨、任意の互換provider対応） |
| `DASHSCOPE_API_KEY` | - | 後方互換、`EMBEDDING_API_KEY`と選択 |
| `OPENAI_API_KEY` | - | 後方互換 |

---

## クイックスタート

### Python API

```python
import asyncio
from agent_memory import MemoryManager

async def main():
    mm = MemoryManager()

    # 記憶を追加
    mem_id = await mm.add(
        content="NLLB訓練が正常に完了、語彙精度85%達成",
        category_path="Project/Shiliuzi/Training",
        tags=["nllb", "success", "training"],
        importance=0.9
    )
    print(f"Added: {mem_id}")

    # セマンティック検索（デフォルトベクトルモード）
    results = await mm.search("NLLBモデル訓練")
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:60]}")

    # カテゴリでリスト
    all_memories = await mm.list(category_path="Project/Shiliuzi")
    print(f"Found {len(all_memories)} memories")

    # 統計
    stats = await mm.stats()
    print(f"Total: {stats['total_memories']}, Categories: {stats['categories']}")

    # L1圧縮（AI Contextに注入）
    # queryパラメータ：queryに関連する記憶が優先される
    compressed = await mm.compress_for_context([mem_id], query="NLLB訓練")
    print(compressed)

    # 削除
    await mm.delete(mem_id)

asyncio.run(main())
```

### CLI

```bash
# 記憶を追加（自動分類）
python -m agent_memory.cli add "テスト記憶"

# カテゴリとタグを指定
python -m agent_memory.cli add "NLLB訓練完了" --category "Project/Shiliuzi/Training" --tags "nllb,done"

# セマンティック検索（デフォルト）
python -m agent_memory.cli search "NLLBモデル訓練"

# キーワード検索（BM25、ベクトルモデル不要）
python -m agent_memory.cli search "NLLB" --mode bm25

# ハイブリッド検索（ベクトル + BM25加重）
python -m agent_memory.cli search "NLLB" --mode hybrid

# すべてリスト
python -m agent_memory.cli list

# カテゴリでリスト
python -m agent_memory.cli list --category "Project/Shiliuzi"

# 単一記憶を表示
python -m agent_memory.cli show <memory_id>

# 統計
python -m agent_memory.cli stats

# 削除
python -m agent_memory.cli delete <memory_id>

# すべてのトップレベルカテゴリを表示
python -m agent_memory.cli category --show-all

# 使用中のすべてのカテゴリパスを表示
python -m agent_memory.cli category --list

# HMAC署名（新加入フォルダに必要）
python -m agent_memory.cli sign memory/ --key "your-secret-key-here"

# HMAC検証（フォルダ整合性を検証）
python -m agent_memory.cli verify memory/ --key "your-secret-key-here"

# 再埋め込み（embedder切り替え時）
python -m agent_memory.cli --json reembed --embedder hash

# Web APIサーバーを起動
python -m agent_memory.cli serve --port 8765
```

### MemoryManager API

| メソッド | 戻り値 | 説明 |
|---------|-------|------|
| `add(content, category_path, tags, importance)` | `str` (memory_id) | 記憶を追加、L4 + L3デュアルトラック書き込み |
| `get(memory_id)` | `dict \| None` | IDで取得 |
| `delete(memory_id)` | `bool` | 削除、L4 + L3 + vec.jsonを同時にクリア |
| `search(query, limit, category_path, mode)` | `list[dict]` | ベクトル/BM25/ハイブリッド検索、mode=vector/bm25/hybrid対応 |
| `list(category_path, limit)` | `list[dict]` | カテゴリでリスト |
| `compress_for_context(memory_ids, query)` | `str` | L1圧縮、queryパラメータでquery関連記憶の優先度を強化 |
| `stats()` | `dict` | 統計（5分キャッシュ）：合計/カテゴリ/ストレージサイズ/L3カバレッジ |

---

## 他のシステムとの比較

| システム | データ形式 | インデックス | マルチAgent | NAS対応 | 外部依存なし |
|---------|----------|------------|------------|--------|------------|
| Hermes | ファイル | ベクトルなし | 共有ワークスペース | ネイティブ | ✅ |
| VCP | ファイル+ベクトル | Tag+ベクトル | 共有フォルダ | SQLite単一ファイル | ✅ |
| Mem0 | ベクトル+グラフ | ベクトル+関係 | マルチテナント | DB必要 | ❌ |
| Letta | Memory Blocks | ブロックインデックス | Agentメモリ | サービス必要 | ❌ |
| **AgentMemory v0.3** | md + vec.json | デュアルトラック検索 | 共有フォルダ | ネイティブ | ✅ |

---

## アーキテクチャ決定記録（v0.3）

| 決定 | 説明 | 理由 |
|------|------|------|
| L2 Graph-DBを削除 | 3層→4層 | Graph-DBは過設計，实际には分類パスだけで十分 |
| 相転移メカニズムを削除 | ファイル+ベクトルは常にデュアルトラック | VCP検証：相転移は不要 |
| 並行書き込み制御 | portalockerファイルロック | マルチAgent並行書き込みシナリオ |
| EmbedderデフォルトをHashに | 依存ゼロ、決定論的 | 生非異也、善假於物也 |
| LanceDB優先 + JSON Fallback | LanceDB利用不可時に自動デグレード | 高性能シナリオはLanceDB、依存ゼロシナリオはJSON |
| BM25ハイブリッド検索 | Pure Python実装、追加依存ゼロ | キーワード検索シナリオを補完、ベクトルモデル不要 |
| min_depth=3 | 館/棚/本の3層構造 | 記憶粒度を確保、	top層が曖昧になるのを防止 |

---

## ライセンス

MIT License — 自由に使用・変更・配布可能。

---

_AgentMemory — 記憶は図書館のように、デュアルトラック并存、決して妥協しない。_
