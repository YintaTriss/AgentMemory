"""
AgentMemory v2.0.2 - Memory Manager (Unified API)

Main entry point for the memory system.
Provides unified async API for all memory operations.

Team Collaboration:
- namespace: 隔离的命名空间，每个 agent/团队独立存储
- TeamMemoryManager: 多 agent 团队共享记忆管理
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from .l4_files import L4FilesStore, MemoryMeta, MemoryVec
from .bm25 import BM25Indexer
from .l1_lcm import L1LCMCompressor
from .sync import SyncManager
from .library import LibraryClassifier
from .embedder import Embedder, get_embedder
from .observability import metrics
from .search_pipeline import SearchPipeline
from .fuzzy_search import fuzzy_search_with_ids
from .reranker import rerank
from .fact_extractor import FactExtractor  # 2026-07-15: 默认挂上


class MemoryManager:
    """Unified Memory Manager with async API.

    Args:
        namespace: 命名空间 ID，用于多 agent 隔离存储。
                   设置后，base_dir → base_dir/{namespace}/，db_path → db_path/{namespace}/
        base_dir: L4 file storage directory.
        db_path: L3 vector store directory.
                  For Qdrant:  "data/qdrant" (default)
        embedder: Embedder instance for vectorization.
                  Defaults to the same embedder as L3 Qdrant store.
        l3_backend: Which L3 vector store to use. Always "qdrant".
    """

    def __init__(self, base_dir: str = "memory", db_path: str = "data/qdrant",
                 embedder: Optional[Embedder] = None,
                 l3_backend: str = "qdrant",
                 namespace: Optional[str] = None):
        # Namespace isolation: append namespace to paths
        if namespace:
            ns_sanitized = namespace.replace("../", "").replace("..", "").strip("/")
            base_dir = str(Path(base_dir) / ns_sanitized)
            db_path = str(Path(db_path) / ns_sanitized)
        
        self.namespace = namespace
        self.base_dir = base_dir
        self.db_path = db_path
        self.l3_backend = l3_backend
        # 【Bug Fix 2026-07-15 调7】`_store_path` 是 SQLite 文件路径,
        # 独立于 `db_path`(l3 目录)。默认 `data/agentmemory.sqlite`。
        # 在 CLI / 单元测中可手动覆写 `mm._store_path = 'xxx.db'`
        import os as _os
        _default_sqlite = _os.path.join(base_dir, 'agentmemory.sqlite')
        self._store_path = _default_sqlite
        self.l4 = L4FilesStore(base_dir)

        # L3 store: always Qdrant Edge
        from .l3_qdrant import L3QdrantStore
        self.l3 = L3QdrantStore(db_path=db_path)

        self.l1 = L1LCMCompressor()
        # 2026-07-15: 默认构造一个 FactExtractor 并挂到 L1LCMCompressor
        # 行为: L1LCMCompressor.extract_facts 现在默认走 FactExtractor 规则;
        # 用户可调 l1.unbind_fact_extractor() 回到原版。
        # 真正的 LLM 抽取在 compress_with_facts() async 中触发。
        self._fact_extractor = FactExtractor()
        self.l1.bind_fact_extractor(self._fact_extractor)
        self.sync = SyncManager(self.l4, self.l3, embedder, memory_dir=base_dir)
        self.classifier = LibraryClassifier()
        # Use the same embedder as L3 Qdrant store (FastEmbed with correct dimensions)
        # This ensures query vectors match stored vectors (e.g. 512-dim for bge-small-zh-v1.5)
        self.embedder = embedder or self.l3._embedder or get_embedder()
        self._stats_cache = None
        self._stats_timestamp = None

    async def add(self, content: str, importance: float = 0.5,
                  category_path: Optional[str] = None, tags: Optional[List[str]] = None,
                  source: str = "manual") -> str:
        import time
        t0 = time.perf_counter()

        # BUG-3 (P2) fix: reject empty/whitespace-only content to avoid phantom memories
        if not isinstance(content, str) or not content.strip():
            raise ValueError(
                "MemoryManager.add: content must be a non-empty string "
                f"(got {type(content).__name__}: {content!r})"
            )

        if category_path is None:
            category_path = self.classifier.classify(content)
        memory_id = self._generate_id(content)
        now = datetime.now().isoformat()

        # Create metadata as dict (L4FilesStore expects dict)
        meta_dict = {
            "id": memory_id,
            "created_at": now,
            "updated_at": now,
            "category_path": category_path,
            "tags": tags or [],
            "source": source,
            "importance": importance,
            # 2026-07-15 方向 1: 时间有效性默认字段
            "valid_from": now,         # 默认从现在开始有效
            "valid_until": None,        # 默认当前有效
            "invalidated_by": None,
            "supersedes": [],
        }

        # 2026-07-15 方向 1: 矛盾检测 — 检查是否与已有事实矛盾
        # 启发式:同 category + 关键词重合 + 用户说"改为/换成/不再/已经"时触发
        try:
            from .contradiction import ContradictionDetector
            detector = ContradictionDetector()
            superseded = await detector.find_and_invalidate(
                new_content=content,
                new_meta=meta_dict,
                store=self.l4,
            )
            if superseded:
                meta_dict["supersedes"] = superseded
                # 更新旧事实的 invalidated_by 字段
                for old_id in superseded:
                    try:
                        old = await self.l4.load_existing(old_id)
                        if old:
                            old_meta = dict(old.get("meta", {}))
                            old_meta["invalidated_by"] = memory_id
                            old_meta["valid_until"] = now
                            old_meta["updated_at"] = now
                            # 重写 .meta.json (L4 通过 _write_meta / 类似接口)
                            # 这里走 l4.update_meta 如果有,否则保存原 content
                            if hasattr(self.l4, "update_meta"):
                                await self.l4.update_meta(old_id, old_meta)
                    except Exception:
                        # best effort,不让 add 失败
                        pass
        except ImportError:
            pass  # contradiction 模块不存在,跳过 (向后兼容)

        # Save to L4 (async)
        await self.l4.save(memory_id, content, meta_dict)

        # Sync to L3 (this also writes vec.json)
        await self.sync.sync_one(memory_id)

        self._invalidate_cache()
        metrics.inc_add()
        metrics.record_add_latency(time.perf_counter() - t0)
        return memory_id

    async def _search_raw(self, query: str, limit: int = 5,
                    category_path: Optional[str] = None,
                    use_pipeline: bool = True) -> List[Dict[str, Any]]:
        """
        搜索记忆。

        当 use_pipeline=True 且 SQLiteStore 可用时，运行四层搜索管道：
        Fuzzy → BM25 → Vector → Reranker。
        否则回退到纯向量搜索。
        """
        import time
        t0 = time.perf_counter()
        mode = "vector"

        # ========== 管道模式：四层融合搜索 ==========
        if use_pipeline:
            try:
                from .sqlite_store import SQLiteStore
                # 【Bug Fix 2026-07-15 调7】 self._store_path 已经是 sqlite 文件路径(在 __init__ 里设的)
                store = SQLiteStore(db_path=self._store_path)

                # 获取所有记忆作为候选
                conn = store._get_conn()
                cur = conn.execute(
                    "SELECT id, content, category FROM memories ORDER BY importance DESC LIMIT 200"
                )
                all_candidates = [dict(row) for row in cur.fetchall()]

                if all_candidates:
                    # Fuzzy function
                    def fuzzy_wrapper(q, candidates, limit=20):
                        from .fuzzy_search import fuzzy_search_with_ids
                        items = [(c.get('content','') or '', c.get('id','')) for c in candidates]
                        results = fuzzy_search_with_ids(q, items, limit=limit)
                        return [{'content': r[0], 'id': r[2], 'score': r[1]/100.0, 'source': 'fuzzy'} for r in results]

                    # BM25 function — 直接用 _bm25_rerank 包装
                    async def bm25_wrapper(q, top_k=20):
                        # 先做向量搜索获取候选
                        import asyncio
                        if asyncio.iscoroutinefunction(self.embedder.embed):
                            qv = await self.embedder.embed(q)
                        else:
                            qv = self.embedder.embed(q)
                        vec_results = self.l3.search(qv, top_k=top_k*3)
                        if vec_results and all(r.get("score", 0) or 0 == 0 for r in vec_results):
                            # 零分数：BM25 重排
                            texts = []
                            ids = []
                            for vr in vec_results:
                                mem = await self.l4.load_existing(vr.get('id',''))
                                if mem:
                                    texts.append(mem.get('content',''))
                                    ids.append(vr.get('id',''))
                            if texts:
                                from .bm25 import BM25Indexer
                                idx = BM25Indexer()
                                idx.index(texts)
                                bm_results = idx.search(q, top_k=top_k)
                                return [{'content': texts[b['doc_index']], 'id': ids[b['doc_index']], 'score': b['bm25_score']} for b in bm_results]
                        return []

                    # Vector function
                    async def vector_wrapper(q, top_k=20):
                        import asyncio
                        if asyncio.iscoroutinefunction(self.embedder.embed):
                            qv = await self.embedder.embed(q)
                        else:
                            qv = self.embedder.embed(q)
                        results = self.l3.search(qv, top_k=top_k)
                        result_mems = []
                        for r in results:
                            mem_id = r.get('id','')
                            mem = await self.l4.load_existing(mem_id)
                            if mem:
                                result_mems.append({
                                    'content': mem.get('content',''),
                                    'id': mem_id,
                                    'score': float(r.get('score',0) or 0),
                                })
                        return result_mems

                    pipeline = SearchPipeline(
                        fuzzy_fn=fuzzy_wrapper,
                        bm25_fn=bm25_wrapper,
                        vector_fn=vector_wrapper,
                        reranker_fn=lambda q, cands: rerank(q, cands),
                    )
                    results = await pipeline.search(
                        query, all_candidates,
                        weights={'fuzzy': 0.2, 'bm25': 0.3, 'vector': 0.4, 'reranker': 0.1},
                        top_k=limit,
                    )

                    enriched = []
                    for r in results[:limit]:
                        mem = await self.l4.load_existing(r.id)
                        if mem:
                            meta = mem.get('meta', {})
                            enriched.append({
                                'id': r.id,
                                'content': r.content,
                                'score': r.score,
                                'category': meta.get('category_path', ''),
                                'tags': meta.get('tags', []),
                                'importance': meta.get('importance', 0.5),
                                'created_at': meta.get('created_at', ''),
                                'source': r.source,
                            })

                    metrics.inc_search('pipeline')
                    metrics.record_search_latency(time.perf_counter() - t0, 'pipeline')
                    return enriched
            except ImportError:
                pass  # Fall through to vector-only mode
            except Exception:
                pass  # Fall through to vector-only mode

        # ========== 回退：纯向量搜索 ==========
        import asyncio
        if asyncio.iscoroutinefunction(self.embedder.embed):
            query_vector = await self.embedder.embed(query)
        else:
            query_vector = self.embedder.embed(query)

        filter_expr = None
        if category_path:
            # Escape single quotes to prevent injection
            safe_cat = category_path.replace("'", "''")
            filter_expr = f"category_path = '{safe_cat}'"

        results = self.l3.search(query_vector, top_k=limit, filter_expr=filter_expr)

        # L3 vector search failed — detect by zero scores and apply BM25 rerank
        needs_bm25 = (
            len(results) > 0
            and all(r.get("score", None) is None or r.get("score", 0) == 0 for r in results)
        )
        if needs_bm25:
            mode = "bm25"
            metrics.inc_bm25_fallback()
            results = self._bm25_rerank(query, results, top_k=limit)

        enriched = []
        for r in results:
            memory_id = r.get("id", "")
            mem = await self.l4.load_existing(memory_id)
            if mem:
                meta = mem.get("meta", {})
                enriched.append({
                    "id": memory_id,
                    "content": mem.get("content", ""),
                    "score": r.get("score", 0),
                    "category": meta.get("category_path", ""),
                    "tags": meta.get("tags", []),
                    "importance": meta.get("importance", r.get("importance", 0.5)),
                    "created_at": meta.get("created_at", r.get("created_at", "")),
                    "metadata": r.get("metadata", {}),
                })
                metrics.record_search_score(r.get("score", 0))

        metrics.inc_search(mode)
        metrics.record_search_latency(time.perf_counter() - t0, mode)
        return enriched


    async def search(self, query: str, limit: int = 5,
                    category_path: Optional[str] = None,
                    use_pipeline: bool = True,
                    time_range: Optional[Tuple[str, str]] = None,
                    only_valid: bool = True,
                    auto_detect_temporal: bool = True) -> List[Dict[str, Any]]:
        """
        搜索记忆 + Temporal 过滤 (2026-07-15+ 方向 2)

        Args:
            query: 查询文本
            limit: 返回数量
            category_path: 可选类别过滤
            use_pipeline: 是否用四层搜索管道
            time_range: 可选 (start_iso, end_iso) 时间范围
            only_valid: 是否过滤已 invalidated 的记忆(默认 True)
            auto_detect_temporal: 自动从 query 检测时间意图(如 "去年" → last_year)
        """
        # 2026-07-15 方向 2: 自动检测时间意图
        if auto_detect_temporal and not time_range:
            from .temporal import TemporalIntentDetector
            detected = TemporalIntentDetector().detect(query)
            if detected["time_range"]:
                time_range = detected["time_range"]

        # 调原始 search
        results = await self._search_raw(
            query, limit=limit,
            category_path=category_path,
            use_pipeline=use_pipeline,
        )

        # 2026-07-15 方向 2: 后过滤 — only_valid + time_range
        if only_valid:
            from .temporal import filter_only_valid
            results = filter_only_valid(results)
        if time_range:
            from .temporal import filter_by_time_range
            results = filter_by_time_range(
                results,
                start=time_range[0],
                end=time_range[1],
                time_field="created_at",
            )

        return results[:limit]

    async def list(self, category_path: Optional[str] = None,
                   limit: int = 20) -> List[Dict[str, Any]]:
        all_ids = self.l4.list()
        mem_map = {}
        for memory_id in all_ids[:limit]:
            mem = await self.l4.load_existing(memory_id)
            if mem:
                mem_map[memory_id] = mem

        if category_path:
            # Prefix match so '测试' matches '测试/石榴籽', '测试/其他' etc.
            filtered_ids = [
                mid for mid, mem in mem_map.items()
                if mem.get("meta", {}).get("category_path", "").startswith(category_path)
            ]
        else:
            filtered_ids = list(mem_map.keys())

        memories = []
        for memory_id in filtered_ids:
            mem = mem_map[memory_id]
            meta = mem.get("meta", {})
            memories.append({
                "id": memory_id,
                "content": mem.get("content", ""),
                "category": meta.get("category_path", ""),
                "tags": meta.get("tags", []),
                "importance": meta.get("importance", 0.5),
                "created_at": meta.get("created_at", ""),
                "source": meta.get("source", ""),
            })
        return memories

    async def get(self, memory_id: str) -> Optional[Dict[str, Any]]:
        mem = await self.l4.load_existing(memory_id)
        if not mem:
            return None
        meta = mem.get("meta", {})
        return {
            "id": memory_id,
            "content": mem.get("content", ""),
            "category": meta.get("category_path", ""),
            "tags": meta.get("tags", []),
            "importance": meta.get("importance", 0.5),
            "created_at": meta.get("created_at", ""),
            "updated_at": meta.get("updated_at", ""),
            "source": meta.get("source", ""),
        }

    async def delete(self, memory_id: str) -> bool:
        deleted = await self.l4.delete(memory_id)
        l3_ok = self.sync.delete_from_l3(memory_id)
        # L4 delete is the source of truth; L3 failure is non-critical
        # (L3 vector becomes orphaned but cannot be retrieved since L4 content is gone)
        if deleted:
            self._invalidate_cache()
            metrics.inc_delete()
        return deleted

    async def compress_for_context(self, memory_ids: List[str],
                                       query: str = "",
                                       only_valid: bool = True,
                                       time_range: Optional[Tuple[str, str]] = None,
                                       auto_detect_temporal: bool = True) -> str:
        """
        L1 context compression for AI prompt injection.

        2026-07-15+ 强化:
        - only_valid: 过滤已 invalidated 记忆(默认 True)
        - time_range: 时间范围过滤(默认 None)
        - auto_detect_temporal: 从 query 自动检测时间意图(默认 True)

        Args:
            memory_ids: List of memory IDs to compress.
            query: Optional query string. Memories matching the query
                   receive relevance score boost in importance tier sorting.
        """
        from .temporal import (
            TemporalIntentDetector,
            filter_by_time_range,
            filter_only_valid,
        )

        memories = []
        for mid in memory_ids:
            mem = await self.l4.load_existing(mid)
            if mem:
                memories.append(mem)

        # 2026-07-15: Temporal 过滤
        if auto_detect_temporal and not time_range and query:
            detected = TemporalIntentDetector().detect(query)
            if detected["time_range"]:
                time_range = detected["time_range"]

        if only_valid:
            memories = filter_only_valid(memories)
        if time_range:
            memories = filter_by_time_range(
                memories,
                start=time_range[0],
                end=time_range[1],
                time_field="created_at",
            )

        # 2026-07-15: 标记 invalidated fact 给 L1 注释
        original_ids = {m.get("id") for m in memories}
        superseded_notes: list = []
        for mid in memory_ids:
            if mid not in original_ids:
                # 被过滤掉的记忆可能是被 invalidated 或不在时间范围
                superseded_notes.append(mid)

        return self.l1.compress(memories, query=query)

    async def get_observations(self, memory_ids: List[str] = None,
                                 limit: int = 50) -> List[str]:
        """从一组 memory 提取 observations (模式 / 洞察)

        2026-07-15+ 方向 3:
        - 不调 LLM,纯 meta 数据派生
        - 给已实现的 Spike Routing 涌现节点能力起名 + 暴露
        - 默认取最近 limit 条 memory;若 memory_ids 指定则取指定

        Returns:
            字符串列表,每条一句 observation(最多 5 条)
        """
        from .observations import ObservationsGenerator
        memories = []
        if memory_ids:
            for mid in memory_ids:
                mem = await self.l4.load_existing(mid)
                if mem:
                    memories.append(mem)
        else:
            # 取最近 limit 条 memory
            memories = await self.list(limit=limit)

        generator = ObservationsGenerator()
        return generator.generate(memories)

    # ========== 2026-07-15 方向 5 + 6: 梦境调度 + 可追溯 ==========

    def auto_dream(self, namespace: str = "default",
                   force: Optional[str] = None) -> Dict[str, Any]:
        """梦境节奏自适应调度 (方向 5)

        根据当前系统状态自动决定跑 light/deep/rem/skip 哪个梦境阶段。
        """
        from .dream_phase_selector import DreamPhaseSelector

        store = getattr(self, '_store', None)
        if store is None:
            from .sqlite_store import SQLiteStore
            # 【Bug Fix 2026-07-15 调7】 同上
            store = SQLiteStore(db_path=self._store_path)

        selector = DreamPhaseSelector(store=store, namespace=namespace)
        decision = selector.select(force=force)
        explanation = selector.explain(decision)

        result: Dict[str, Any] = {"phase": decision.phase, "skipped": True}
        if decision.phase != "skip":
            try:
                engine = self._get_dream_engine(store)
                result = engine.dream_cycle(
                    phase=decision.phase,
                    dry_run=False,
                    candidate_names=None,
                )
            except Exception as e:
                result = {"error": f"dream_cycle failed: {e}"}

        return {
            "decision": decision,
            "result": result,
            "explanation": explanation,
        }

    def _get_dream_engine(self, store):
        if not hasattr(self, '_dream_engine') or self._dream_engine is None:
            from .dream_engine import DreamEngine
            # 【Bug Fix 2026-07-15 调7】DreamEngine 参数是 sqlite_store
            self._dream_engine = DreamEngine(sqlite_store=store)
        return self._dream_engine

    def explain_artifact(self, artifact_id: str) -> str:
        """梦境产物因果解释 (方向 6)"""
        tracker = self._get_provenance_tracker()
        return tracker.explain(artifact_id)

    def trace_artifact_chain(self, artifact_id: str) -> List[Dict[str, Any]]:
        """递归追溯梦境产物因果链 (方向 6)"""
        tracker = self._get_provenance_tracker()
        chain = tracker.trace_chain(artifact_id)
        return [p.to_dict() for p in chain]

    def _get_provenance_tracker(self):
        if not hasattr(self, '_provenance_tracker') or self._provenance_tracker is None:
            from .dream_provenance import DreamProvenanceTracker
            storage_path = os.path.join(
                os.path.dirname(getattr(self, '_store_path', 'data/agentmemory.db')),
                'dream_provenance.jsonl'
            )
            self._provenance_tracker = DreamProvenanceTracker(storage_path=storage_path)
        return self._provenance_tracker

    def record_dream_provenance(self, artifact_id: str, artifact_type: str,
                                 phase: str, **kwargs) -> Dict[str, Any]:
        """记录梦境产物因果信息 (方向 6)"""
        tracker = self._get_provenance_tracker()
        prov = tracker.record(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            phase=phase,
            **kwargs,
        )
        return prov.to_dict()

    # ========== 2026-07-15 方向 7: 梦境调度器 ==========

    def get_dream_scheduler(self, schedule: Optional[Dict[str, str]] = None):
        """获取梦境调度器 (方向 7)

        用法:
            scheduler = mm.get_dream_scheduler()
            while True:
                scheduler.tick()
                time.sleep(60)

            # 或自定义调度:
            scheduler = mm.get_dream_scheduler({
                "light": "every:1h",
                "deep": "daily:02:00",
                "rem": "weekly:sun:02:00",
            })
        """
        if not hasattr(self, '_dream_scheduler') or self._dream_scheduler is None:
            from .dream_scheduler import DreamScheduler
            store = getattr(self, '_store', None)
            if store is None:
                from .sqlite_store import SQLiteStore
                # 【Bug Fix 2026-07-15 调7】 self._store_path 已经是 sqlite 文件路径(在 __init__ 里设的)
                store = SQLiteStore(db_path=self._store_path)
            self._dream_scheduler = DreamScheduler(store=store, namespace="default")
        if schedule:
            self._dream_scheduler.schedule = dict(schedule)
        return self._dream_scheduler

    async def compress_with_facts(
        self,
        memory_ids: List[str],
        query: str = "",
        max_facts_per_memory: int = 3,
        include_observations: bool = True,
    ) -> str:
        """
        L1 + FactExtractor(LLM 抽取)+ 聚合(2026-07-15+ 高阶方法)。

        流程:
          1. 加载每条 memory
          2. 对每条重要 memory,await self._fact_extractor.extract(content)
             (无 LLM 客户端时降级为规则抽取)
          3. 把 facts 注入到 memory.content 的前缀
          4. 喂给 L1LCMCompressor.compress()

        Args:
            memory_ids: List of memory IDs to compress.
            query: 可选 query,提高相关记忆的排序权重。
            max_facts_per_memory: 每条记忆最多抽几个 fact。
        """
        import asyncio
        memories = []
        for mid in memory_ids:
            mem = await self.l4.load_existing(mid)
            if not mem:
                continue
            content = mem.get("content", "") or ""
            if not content.strip():
                memories.append(mem)
                continue
            # 仅对 importance >= 0.7 的重要 memory 抽 fact(节省调用)
            importance = mem.get("meta", {}).get("importance", 0.5)
            if importance >= 0.7 and self._fact_extractor is not None:
                try:
                    facts = await asyncio.wait_for(
                        self._fact_extractor.extract(content),
                        timeout=10.0,
                    )
                    facts = (facts or [])[:max_facts_per_memory]
                except (asyncio.TimeoutError, Exception):
                    facts = []
                if facts:
                    mem = {**mem}
                    mem["content"] = "[Facts] " + " | ".join(facts) + "\n\n" + content
            memories.append(mem)
        compressed = self.l1.compress(memories, query=query)

        # 2026-07-15 方向 3: 在末尾追加 Observations 段(如果 enabled)
        if include_observations:
            from .observations import ObservationsGenerator
            observations = ObservationsGenerator().generate(memories)
            if observations:
                compressed += "\n\n## Observations\n"
                for obs in observations:
                    compressed += f"- {obs}\n"
        return compressed

    async def stats(self) -> Dict[str, Any]:
        if self._stats_cache and self._stats_timestamp:
            age = (datetime.now() - self._stats_timestamp).total_seconds()
            if age < 300:
                return self._stats_cache

        l4_stats = self.l4.get_stats()
        l3_count = self.l3.count()

        # Detect actual embedder in use: check if FastEmbed was actually loaded
        # _embedder is None when FastEmbed import failed or not installed
        if self.l3_backend == "qdrant":
            actual_embedder = getattr(self.l3, '_embedder', None)
            if actual_embedder is not None:
                # FastEmbed was loaded and is in use
                embedder_name = f"fastembed-{getattr(self.l3, 'embedder_model', 'unknown')}"
                dims = getattr(self.l3, '_vector_dim', None) or getattr(self.l3, 'DEFAULT_DIM', 384)
            else:
                # FastEmbed not loaded — using HashEmbedder fallback
                embedder_name = "hash-v1 (fallback)"
                dims = self.embedder.dim
        else:
            embedder_name = "hash-v1"
            dims = self.embedder.dim

        stats = {
            "total_memories": l4_stats["memory_count"],
            "l3_memories": l3_count,
            "storage_bytes": l4_stats["total_size_bytes"],
            "embedder": embedder_name,
            "embedding_dims": dims,
            "categories": self.l4.get_categories(),
            "l3_backend": self.l3_backend,
        }
        self._stats_cache = stats
        self._stats_timestamp = datetime.now()
        return stats

    def _generate_id(self, content: str) -> str:
        import time, secrets
        return f"mem_{int(time.time()*1000):013x}_{secrets.token_hex(4)}"

    def _invalidate_cache(self) -> None:
        self._stats_cache = None
        self._stats_timestamp = None

    def _bm25_rerank(self, query: str, records: List[Dict[str, Any]],
                     top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Pure-Python BM25 re-ranking when vector search returns zero scores.
        """
        if not records:
            return []
        texts = [r.get("content", "") or "" for r in records]
        indexer = BM25Indexer(k1=1.2, b=0.75)
        indexer.index(texts)
        bm25_results = indexer.search(query, top_k=top_k)
        results = []
        for bm in bm25_results:
            rec = records[bm["doc_index"]]
            results.append({
                "id": rec.get("id", ""),
                "content": rec.get("content", ""),
                "score": bm["bm25_score"],
                "bm25_score": bm["bm25_score"],
                "importance": rec.get("importance", 0.5),
                "category_path": rec.get("category_path", ""),
                "created_at": rec.get("created_at", ""),
            })
        return results

    async def sync_all_memories(self) -> Dict[str, int]:
        return await self.sync.sync_all()


def create_memory_manager(base_dir: str = "memory",
                          db_path: str = "data/qdrant",
                          l3_backend: str = "qdrant",
                          namespace: Optional[str] = None) -> MemoryManager:
    """Create a MemoryManager instance.

    Args:
        base_dir: L4 file storage directory.
        db_path: L3 vector store directory.
        l3_backend: Always "qdrant" (Qdrant Edge embedded, default).
        namespace: 命名空间，用于多 agent 隔离存储。
    """
    return MemoryManager(base_dir=base_dir, db_path=db_path, l3_backend=l3_backend, namespace=namespace)


class TeamMemoryManager:
    """
    团队协作记忆管理器。
    
    支持多 agent 共享同一个团队的记忆，同时保持各自独立的空间。
    
    存储结构:
        memory/
            {team}/              ← 团队共享记忆
                _shared/         ← 团队成员共享的记忆
                {agent1}/        ← agent1 私有记忆
                {agent2}/        ← agent2 私有记忆
            data/
                qdrant/
                    {team}/
                        _shared/
                        {agent1}/
                        {agent2}/

    Args:
        team: 团队 ID
        base_dir: 根存储目录
        db_path: 向量库根目录
        embedder: Embedder 实例
    """

    def __init__(self, team: str,
                 base_dir: str = "memory",
                 db_path: str = "data/qdrant",
                 embedder: Optional[Embedder] = None):
        self.team = team
        self.base_dir = base_dir
        self.db_path = db_path
        self._embedder = embedder
        
        # Shared memory manager for the team
        self.shared = MemoryManager(
            base_dir=str(Path(base_dir) / team / "_shared"),
            db_path=str(Path(db_path) / team / "_shared"),
            embedder=embedder,
            namespace=None,
        )
        # Track registered agents
        self._agents: Dict[str, MemoryManager] = {}

    def register_agent(self, agent_id: str) -> MemoryManager:
        """
        注册一个 agent，获得其私有的记忆空间。
        
        Args:
            agent_id: Agent 唯一标识
        Returns:
            该 agent 的 MemoryManager 实例
        """
        if agent_id not in self._agents:
            self._agents[agent_id] = MemoryManager(
                base_dir=str(Path(self.base_dir) / self.team / agent_id),
                db_path=str(Path(self.db_path) / self.team / agent_id),
                embedder=self._embedder,
                namespace=None,
            )
        return self._agents[agent_id]

    def get_agent(self, agent_id: str) -> Optional[MemoryManager]:
        """获取已注册的 agent MemoryManager，未注册返回 None"""
        return self._agents.get(agent_id)

    def list_agents(self) -> List[str]:
        """列出所有已注册的 agent ID"""
        return list(self._agents.keys())

    async def share_to_team(self, agent_id: str, memory_id: str) -> bool:
        """
        将某 agent 的记忆共享到团队空间。
        
        Args:
            agent_id: 来源 agent
            memory_id: 要共享的记忆 ID
        Returns:
            是否共享成功
        """
        agent_mem = self._agents.get(agent_id)
        if not agent_mem:
            return False
        mem = await agent_mem.get(memory_id)
        if not mem:
            return False
        # Write to team shared space
        shared_id = await self.shared.add(
            content=mem["content"],
            importance=mem.get("importance", 0.5),
            category_path=f"team:{self.team}/shared",
            tags=["shared", f"from:{agent_id}"],
            source=f"agent:{agent_id}",
        )
        return True

    async def get_shared(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取团队共享的所有记忆"""
        return await self.shared.list(limit=limit)

    async def stats_all(self) -> Dict[str, Any]:
        """获取团队所有 agent 的统计"""
        stats = {
            "team": self.team,
            "shared": await self.shared.stats(),
            "agents": {},
        }
        for agent_id, mgr in self._agents.items():
            stats["agents"][agent_id] = await mgr.stats()
        return stats


def create_team_memory_manager(team: str,
                               base_dir: str = "memory",
                               db_path: str = "data/qdrant",
                               embedder: Optional[Embedder] = None) -> TeamMemoryManager:
    """Create a TeamMemoryManager instance.

    Args:
        team: 团队 ID
        base_dir: 根存储目录
        db_path: 向量库根目录
        embedder: Embedder 实例
    """
    return TeamMemoryManager(team=team, base_dir=base_dir, db_path=db_path, embedder=embedder)
