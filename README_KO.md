<p align="center">
  <a href="README_EN.md">English</a> |
  <a href="README.md">简体中文</a> |
  <a href="README_ZHT.md">繁體中文</a> |
  <a href="README_JA.md">日本語</a> |
  <a href="README_KO.md">한국어</a> |
  <a href="README_FR.md">Français</a>
</p>

# AgentMemory v0.3

> **듀얼 트랙 + 도서관 메모리 시스템** — AI Agent를 위한 지속 가능하고 이식 가능한 핫스왑 메모리 인프라

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)

---

## 설계 철학: 기억을 도서관처럼

> **책 자체는 변하지 않지만, 카탈로그 시스템이 정확한 검색을 가능하게 합니다.**

전통적인 메모리 시스템의 핵심 모순: **시맨틱 검색(퍼지 매칭)과 정밀 분류(도메인 필터링)는 하나만 선택 가능**.

AgentMemory의 답: **두 트랙이 공존, 절대 타협하지 않음.**

동일한 기억이 동시에 두 트랙에 존재:

```
동일한 기억:
├─ 도서관 분류 트랙(.md 콘텐츠 + .meta.json 메타데이터) → 정밀 조회, 관리 경계
└─ Embedding 벡터 트랙(.vec.json) → 시맨틱 검색, 퍼지 매칭
```

**그레뉼라리티 보장**: 최소 3층 분류(도서관/서가/책—정확한 분류 보장), 최대 층수 무제한, 필요시 동적 확장.

---

## 아키텍처 개요

```
┌──────────────────────────────────────────────────────────────┐
│                     호스트 앱 (Agent / CLI / Web API)        │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│  MemoryManager (통합 비동기 API)                             │
│  add() / get() / delete() / search() / list() / compress() │
└────────────────────────────┬─────────────────────────────────┘
                             │
          ┌──────────────────┴──────────────────┐
          ▼                                      ▼
┌─────────────────────┐              ┌─────────────────────────┐
│   L4FilesStore      │              │   L3LanceDBStore        │
│   (파일 지속성)       │              │   (벡터 시맨틱 검색)      │
│                     │              │                         │
│  memory/<id>.md     │◄──── sync ──►│  LanceDB Table         │
│  memory/<id>.meta   │              │  (의미 유사도 검색)       │
│  memory/<id>.vec.json              │                         │
└─────────────────────┘              └─────────────────────────┘
          │                                      │
          ▼ (읽기 시)                              │
┌─────────────────────┐              ┌─────────────────────────┐
│   L1LCMCompressor   │              │   BM25 하이브리드 검색    │
│   (컨텍스트 압축)     │              │   (순수 Python, 의존성 0) │
│                     │              │                         │
│  엔티티 추출 → 요약   │              │  k1=1.2, b=0.75         │
│  → AI Context 주입   │              │  α=0.7 (vector/BM25)  │
└─────────────────────┘              └─────────────────────────┘
```

### 3층 책임

| 층 | 컴포넌트 | 책임 |
|----|---------|------|
| **L4** | `L4FilesStore` | `.md` 콘텐츠 + `.meta.json` 메타데이터 + `.vec.json` 벡터, 파일 시스템 지속성 |
| **L3** | `L3LanceDBStore` | LanceDB 벡터 검색(사용 불가 시 자동 Pure JSON + numpy 폴백), BM25 하이브리드 검색 |
| **L1** | `L1LCMCompressor` | 기억을 요약 + 엔티티 목록으로 압축, AI 프롬프트 주입 시 사용, query 관련성 향상 지원 |
| **L3** | `SyncManager` | L4 ↔ L3 듀얼 트랙 동기화, auto_sync 키워드 감지, portalocker 파일 잠금 |
| **L3** | `LibraryClassifier` | 5대 최상위 카테고리 자동 분류, 키워드 정규화 점수화, 캐시 토큰화 |
| **L3** | `IntegrityVerifier` | HMAC-SHA256 파일 무결성 서명, 변조 감지 |

### 듀얼 트랙 검색

| 트랙 | 방법 | 최적 사용 시나리오 |
|------|------|-----------------|
| **트랙 1** | 도서관 분류(category_path / tags) | 정밀 조회, 도메인 필터링 |
| **트랙 2** | Embedding 벡터(의미 유사도) | 퍼지 검색, 시맨틱 연관 |

### 도서관 분류 규칙

최소 3층(도서관/서가/책—그레뉼라리티 보장), 최대 무제한, 동적 깊이:

```
프로젝트/石榴籽/코퍼스/NLLB훈련                 ✅ 최소 3층
프로젝트/石榴籽/코퍼스/NLLB훈련/2026-06           ✅ 무한 확장 가능
학습/AI/Transformer                                ✅ 3층
AI/Agent/기억시스템/VCP                      ✅ 4층
```

---

## 핵심 컴포넌트

| 컴포넌트 | 파일 | 설명 |
|---------|------|------|
| `MemoryManager` | `manager.py` | 통합 비동기 API: add/get/delete/search/list/compress |
| `L4FilesStore` | `l4_files.py` | md + meta.json + vec.json 삼중 파일 저장소, portalocker 파일 잠금 |
| `L3LanceDBStore` | `l3_lancedb.py` | LanceDB 벡터 검색 + JSON 폴백 + BM25 하이브리드 검색 |
| `L1LCMCompressor` | `l1_lcm.py` | 컨텍스트 압축, FactType 엔티티 추출, query 관련성 향상 |
| `SyncManager` | `sync.py` | L4 ↔ L3 듀얼 트랙 동기화, auto_sync 키워드 감지 |
| `LibraryClassifier` | `library.py` | 5대 카테고리 키워드 분류, 계층 경로 검증, 캐시 토큰화 |
| `Embedder` | `embedder.py` | HashEmbedder(의존성 0) / DashScopeEmbedder(OpenAI-Compatible API)|
| `IntegrityVerifier` | `integrity.py` | HMAC-SHA256 서명 검증 |

---

## 데이터 구조

각 기억 = 동일 디렉토리의 3개 파일:

```
memory/
├── abc123.md           # 사람이 읽을 수 있는 콘텐츠
├── abc123.meta.json   # 메타데이터
└── abc123.vec.json    # 벡터 데이터(기억당 1개, .md와同一 디렉토리)
```

### meta.json 형식

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

## 구현 세부 사항: 코드를 우아하게 만드는 기술들

### 원자적 쓰기: tempfile + os.replace(Windows 호환)

L4 파일 쓰기는 2단계 원자적 연산 사용:

```python
# 1. 임시 파일에 쓰기
tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tmp", dir=base_dir)
tmp.write(content); tmp.close()
# 2. os.replace 원자적 교체(Windows에서도 원자성 보장)
os.replace(tmp.name, target_path)
```

os.rename은 Windows에서 크로스 드라이브 작동 불가. os.replace는 가능. 이는 많은 크로스 플랫폼 Python 프로젝트의 사각지대.

### portalocker: 크로스 플랫폼 파일 잠금

```python
with _portalocker_lock(lock_path):
    # 쓰기 작업은 자동 잠금
    ...
```

`portalocker` 우선, Windows는 msvcrt, Unix는 fcntl 폴백. 읽기는 공유 잠금, 쓰기는 배타적 잠금 사용. `contextmanager` 패턴은 예외 발생 시에도 잠금이 반드시 해제됨을 보장.

### `_embed_fn` 패턴: sync/async 통합 인터페이스

DashScopeEmbedder의 `embed()`는 `async def`, HashEmbedder는 `def`, 호출자는 통합 인터페이스 사용:

```python
# SyncManager.__init__에서:
if hasattr(embedder, 'embed_sync'):
    self._embed_fn = embedder.embed_sync
else:
    self._embed_fn = embedder.embed
```

런타임 감지, 타입 체크 불필요. Embedder 기본 클래스는 `embed_sync` 프로퍼티 제공, async 구현은 서브 스레드로 래핑.

### 캐시 토큰화(LibraryClassifier)

키워드 매칭 시마다 토큰화 재수행은 낭비. `_tokenize()`는 `@functools.lru_cache(maxsize=512)` 사용:

```python
@functools.lru_cache(maxsize=512)
def _tokenize(self, text: str) -> tuple[str, ...]:
    ...
    return tuple(tokens)  # tuple은 해시 가능, lru_cache 키로 적합
```

`list` 대신 `tuple` 반환—tuple은 해시 가능하고 캐시 가능.

### 점수 정규화: sqrt(keyword_count)로 대 카테고리가 소 카테고리 억압 방지

「프로젝트」 카테고리는 20+개 키워드, 「선호」는 8개만 가짐. 단순 합산 시 대 카테고리가 항상 승리:

```python
scores[category] = cat_raw / (len(keywords) ** 0.5)  # 제곱근 정규화
```

`sqrt`를 `len(keywords)`로 직접 나누지 않음: 대 리스트는 도움되지만 지배하지 않음.

### Unicode 정규화 + 듀얼 트랙 감지(injection.py)

난독화 공격 감지에는 2단계 필요:

```python
texts_to_check = [text, _normalize_text(text)]  # 원본 텍스트 + 정규화된 텍스트
```

정규화 단계: 제로 너비 문자 처리, HTML 엔티티 디코딩, 전각→반각 변환, Unicode 이스케이프 시퀀스 디코딩, 백슬래시 단어 복원, BIDI 제어 문자 제거. 난독화 공격(`rm\u200b-rf`, `rm&#x72;f`)은 정규화 후 노출.

### BM25 매개변수 설정 가능

BM25의 `k1`(용어 빈도 포화)과 `b`(문서 길이 정규화)는 시나리오에 따라 조정 가능:

```python
# k1=1.2, b=0.75는 Lucene 기본값
l3_store.search_bm25(query, top_k=5, k1=1.2, b=0.75)
```

### 하이브리드 검색 α 가중치 조정 가능

벡터 유사도와 BM25의 하이브리드 가중치 α 기본값 0.7(벡터 70%, BM25 30%):

```python
alpha = 0.7
final_score = alpha * vec_score + (1 - alpha) * bm25_score
```

### 5분 stats 캐시

`MemoryManager.stats()`는 로컬 캐시로 매번 파일 시스템 읽기 방지:

```python
age = (datetime.now() - self._stats_timestamp).total_seconds()
if age < 300:  # 5분 이내면 캐시 반환
    return self._stats_cache
```

### `access_count` 지속성(메모리 변수가 아님)

很多 기억 시스템은 접근 횟수를 메모리에 저장—재시작 시 소멸. AgentMemory는 `access_count`를 `.meta.json`에 기록, `load_existing()` 호출마다 자동 +1 및 지속성.

### query 매개변수로 L1 압축 관련성 순서 강화

`compress_for_context(memory_ids, query="...")`는 query 매개변수 지원; 동일 query 키워드 가진 기억이 동일 중요도階層에서 상위 순위:

```python
def _relevance_score(mem):
    if not query_toks: return 0
    return sum(1 for tok in query_toks if tok in mem.get("content","").lower())
```

---

## 보안(P0 레벨)

| 보호 | 구현 위치 | 설명 |
|------|----------|------|
| **인젝션 감지** | `utils/injection.py` | Unicode 정규화 + 듀얼 트랙 감지(원본/정규화 모두 체크), 50+ 공격 패턴(JNDI/SSTI/Shellshock/Prompt Injection 포함) |
| **trust_score** | `sync.py` | < 0.2는 L3 쓰기 거부, ≤ 0.35는 flagged 표시 및 경고 |
| **HMAC 검증** | `integrity.py` | HMAC-SHA256 서명, `.meta.json`의 `signed_at` 필드에 기록 |
| **API Key 검증** | `embedder.py` | `DashScopeEmbedder.__init__` 즉시 검증, 없을 시 RuntimeError 발생 |
| **LanceDB 인젝션 보호** | `web.py` / `cli.py` | category_path의 작은따옴표를 `''`로 이스케이프(SQL 표준) |
| **원자적 쓰기** | `l4_files.py` | tempfile + os.replace — 프로세스 크래시해도 더티 파일 없음 |
| **파일 잠금** | `l4_files.py` | portalocker 배타적 잠금, 쓰기 작업은 상호 배제 |

---

## 동시성 안전성

쓰기 안전은 `portalocker` 보장, Windows는 `msvcrt`, Unix는 `fcntl` 폴백:

```python
# L4FilesStore 쓰기: 자동 배타적 잠금
with _portalocker_lock(lock_path):
    ...

# 읽기: 자동 공유 잠금
with _file_lock(lock_path, exclusive=False):
    ...
```

---

## 설치

```bash
cd AgentMemory
pip install -e .
```

### 의존성

**런타임 의존성(단 3개, 외부 서비스 불필요):**

```
httpx>=0.25.0    # DashScope API 비동기 호출
aiofiles>=23.0.0 # 비동기 파일 I/O
pydantic>=2.5    # 데이터 검증(런타임 필수)
```

**선택적 의존성:**

```bash
pip install agentmemory[web]     # Web API 지원(FastAPI + uvicorn)
pip install agentmemory[lancedb] # LanceDB 벡터 데이터베이스(고성능 시나리오)
pip install agentmemory[dev]     # 개발 의존성(pytest 등)
```

> LanceDB 사용 불가 시(설치되지 않음), 시스템은 자동으로 Pure JSON + numpy로 폴백—추가 의존성 없이 실행 가능.

### Embedder 선택

```python
from agent_memory import MemoryManager, get_embedder

# 기본값(auto 모드): API Key 없음 → HashEmbedder(의존성 0, 오프라인 동작)
#                   API Key 있음 → OpenAI-Compatible 임베딩(임의의 호환 provider)
mm = MemoryManager()

# 명시적 지정(API Key 없을 시 즉시 RuntimeError 발생, 자동 폴백 없음)
mm = MemoryManager(embedder=get_embedder(backend="openai-compat"))

# 기본 auto 모드와 동등
mm = MemoryManager(embedder=get_embedder())
```

> **모델 종속 없음**: 내부적으로 OpenAI-Compatible API 형식 사용, `/v1/embeddings`을 지원하는 임의의 provider 자동 감지(DashScope / Minimax / OpenAI / 로컬 Embedding Server 등).

### 환경 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `AGENT_MEMORY_DIR` | `memory` | 기억 저장 디렉토리 |
| `AGENT_MEMORY_DATA_DIR` | `data` | 벡터 데이터 디렉토리(LanceDB 테이블 / JSON 폴백) |
| `EMBEDDING_API_KEY` | - | OpenAI-Compatible API(권장, 임의의 호환 provider 동작) |
| `DASHSCOPE_API_KEY` | - | 하위 호환, `EMBEDDING_API_KEY`와 선택 |
| `OPENAI_API_KEY` | - | 하위 호환 |

---

## 빠른 시작

### Python API

```python
import asyncio
from agent_memory import MemoryManager

async def main():
    mm = MemoryManager()

    # 기억 추가
    mem_id = await mm.add(
        content="NLLB 훈련 성공적으로 완료, 어휘 정확도 85% 달성",
        category_path="Project/Shiliuzi/Training",
        tags=["nllb", "success", "training"],
        importance=0.9
    )
    print(f"Added: {mem_id}")

    # 시맨틱 검색(기본 벡터 모드)
    results = await mm.search("NLLB 모델 훈련")
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:60]}")

    # 카테고리로 목록
    all_memories = await mm.list(category_path="Project/Shiliuzi")
    print(f"Found {len(all_memories)} memories")

    # 통계
    stats = await mm.stats()
    print(f"Total: {stats['total_memories']}, Categories: {stats['categories']}")

    # L1 압축(AI Context에 주입)
    # query 매개변수: query와 관련된 기억 우선 표시
    compressed = await mm.compress_for_context([mem_id], query="NLLB훈련")
    print(compressed)

    # 삭제
    await mm.delete(mem_id)

asyncio.run(main())
```

### CLI

```bash
# 기억 추가(자동 분류)
python -m agent_memory.cli add "테스트 기억"

# 카테고리와 태그 지정
python -m agent_memory.cli add "NLLB훈련 완료" --category "Project/Shiliuzi/Training" --tags "nllb,done"

# 시맨틱 검색(기본)
python -m agent_memory.cli search "NLLB 모델 훈련"

# 키워드 검색(BM25, 벡터 모델 불필요)
python -m agent_memory.cli search "NLLB" --mode bm25

# 하이브리드 검색(벡터 + BM25 가중치)
python -m agent_memory.cli search "NLLB" --mode hybrid

# 모두 목록
python -m agent_memory.cli list

# 카테고리로 목록
python -m agent_memory.cli list --category "Project/Shiliuzi"

# 단일 기억 보기
python -m agent_memory.cli show <memory_id>

# 통계
python -m agent_memory.cli stats

# 삭제
python -m agent_memory.cli delete <memory_id>

# 모든 최상위 카테고리 표시
python -m agent_memory.cli category --show-all

# 사용된 모든 카테고리 경로 표시
python -m agent_memory.cli category --list

# HMAC 서명(새로 추가된 폴더 필요)
python -m agent_memory.cli sign memory/ --key "your-secret-key-here"

# HMAC 검증(폴더 무결성 검증)
python -m agent_memory.cli verify memory/ --key "your-secret-key-here"

# 재임베딩(embedder 전환 시)
python -m agent_memory.cli --json reembed --embedder hash

# Web API 서버 시작
python -m agent_memory.cli serve --port 8765
```

### MemoryManager API

| 메서드 | 반환 | 설명 |
|--------|------|------|
| `add(content, category_path, tags, importance)` | `str` (memory_id) | 기억 추가, L4 + L3 듀얼 트랙 쓰기 |
| `get(memory_id)` | `dict \| None` | ID로 조회 |
| `delete(memory_id)` | `bool` | 삭제, L4 + L3 + vec.json 동시 삭제 |
| `search(query, limit, category_path, mode)` | `list[dict]` | 벡터/BM25/하이브리드 검색, mode=vector/bm25/hybrid 지원 |
| `list(category_path, limit)` | `list[dict]` | 카테고리로 목록 |
| `compress_for_context(memory_ids, query)` | `str` | L1 압축, query 매개변수로 query 관련 기억 우선순위 향상 |
| `stats()` | `dict` | 통계(5분 캐시): 총계/카테고리/저장 크기/L3 커버리지 |

---

## 투명 백그라운드（자동 메모리 캡처）

트리거 불필요 — TransparentBackground가 자동 실행：

- **하트비트 캡처**：N분마다 대화 프래그먼트를 자동 저장
- **주기적 요약**：20턴마다 세션 요약을 자동 생성（「세션/주기적 요약」에 저장）
- **컨텍스트 프리페치**：응답 전에 관련 기억을 AI Context에 자동 주입

### CLI

```bash
# 지속 실행（5분마다 하트비트）
agentmemory bg --agent-id main

# 단일 트리거（cron용）
agentmemory bg --agent-id main --once
```

### OpenClaw 설정 예시（5분마다 자동 기억）

```json
{
  "name": "memory-heartbeat",
  "sessionTarget": "isolated",
  "schedule": { "kind": "cron", "expr": "*/5 * * * *", "tz": "Asia/Shanghai" },
  "payload": { "kind": "agentTurn", "message": "agentmemory bg --agent-id main --once" }
}
```

### Python API

```python
from src.adapters.transparent_background import TransparentBackground

tb = TransparentBackground(agent_id="main")

# 응답 전에 관련 기억을 주입
context = await tb.inject_context_for_prompt(
    current_message="석리자 성과 진행상황은?",
    max_memories=5,
    max_chars=2000
)
# → "\n\n[관련 기억]\n- [석리자/프로젝트] 프로젝트 마감일은 2026-06-15...\n[/관련 기억]"
```

---

## MCP Server（크로스 플랫폼 도구 호출）

MCP（Model Context Protocol）로 메모리 도구를 노출, 모든 주요 AI 코딩 도구 지원：

| 클라이언트 | 프로토콜 | 설정 |
|-----------|----------|------|
| Claude Code | MCP stdio | `~/.claude/settings.json` |
| Codex | MCP stdio | `~/.config/codex/config.json` |
| Cursor | MCP stdio/HTTP | Settings → MCP |
| Windsurf | MCP stdio/HTTP | Settings → MCP |

### MCP Server 시작

```bash
# Claude Code / Codex（stdio 모드）
agentmemory mcp

# 다른 클라이언트（HTTP 모드）
agentmemory mcp --http --port 8765
```

### Claude Code 설정

`~/.claude/settings.json`에 추가：

```json
{
  "mcpServers": {
    "agentmemory": {
      "command": "agentmemory",
      "args": ["mcp"]
    }
  }
}
```

### MCP 도구 목록

| 도구명 | 설명 |
|-------|------|
| `memory_add` | 기억 추가 |
| `memory_search` | 시맨틱/키워드/하이브리드 검색 |
| `memory_list` | 카테고리별 목록 |
| `memory_get` | 단일 기억 조회 |
| `memory_delete` | 기억 삭제 |
| `memory_stats` | 통계 정보 |
| `memory_compress` | L1 컨텍스트 압축 |

### 사용 예시

```
# 중요한 정보 기억
Remember: memory_add content="석리자 성과 답변 2026-06-15" importance=0.9 tags="석리자"

# 관련 기억 검색
Search: memory_search query="성과 일정" limit=5 mode="hybrid"
```

---

## 다른 시스템과의 비교

| 시스템 | 데이터 형태 | 인덱싱 | 멀티 Agent | NAS 지원 | 외부 의존성 없음 |
|--------|-----------|--------|-----------|---------|----------------|
| Hermes | 파일 | 벡터 없음 | 공유 작업 공간 | 네이티브 | ✅ |
| VCP | 파일+벡터 | Tag+벡터 | 공유 폴더 | SQLite 단일 파일 | ✅ |
| Mem0 | 벡터+그래프 | 벡터+관계 | 멀티 테넌트 | DB 필요 | ❌ |
| Letta | Memory Blocks | 블록 인덱스 | Agent 메모리 | 서비스 필요 | ❌ |
| **AgentMemory v0.3** | md + vec.json | 듀얼 트랙 검색 | 공유 폴더 | 네이티브 | ✅ |

---

## 아키텍처 결정 기록(v0.3)

| 결정 | 설명 | 이유 |
|------|------|------|
| L2 Graph-DB 제거 | 3층→4층 | Graph-DB 과도한 설계, 실제로는 분류 경로만으로 충분 |
| 상변화 메커니즘 제거 | 파일+벡터는 항상 듀얼 트랙 | VCP 검증: 상변화 불필요 |
| 동시 쓰기 제어 | portalocker 파일 잠금 | 멀티 Agent 동시 쓰기 시나리오 |
| Embedder 기본값 Hash | 의존성 0, 결정론적 | 生非異也，善假於物也 |
| LanceDB 우선 + JSON 폴백 | LanceDB 사용 불가 시 자동 폴백 | 고성능 시나리오는 LanceDB, 의존성 0 시나리오는 JSON |
| BM25 하이브리드 검색 | 순수 Python 구현, 추가 의존성 0 | 키워드 검색 시나리오 보완, 벡터 모델 불필요 |
| min_depth=3 | 도서관/서가/책 3층 구조 | 기억 그레뉼라리티 보장, 최상위가 너무 포괄적 방지 |

---

## 라이선스

MIT License — 자유롭게 사용, 수정, 배포 가능.

---

_AgentMemory — 기억은 도서관처럼, 듀얼 트랙 공존, 절대 타협하지 않음._
