#!/usr/bin/env python3
"""Script to update search_engine.py with RRF fusion support"""

with open(r'C:\Users\31683\AgentMemory\agentmemory\search\search_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Check if RRF methods already exist
if '_search_vector' in content:
    print('RRF methods already exist, skipping...')
    exit(0)

# Step 1: Add import for RRFusion
import_line = 'from .rrf_fusion import RRFusion, RankedResult, FusionResult\n'
# Find the line 'from ..providers.vectorstore import get_vectorstore'
pattern = 'from ..providers.vectorstore import get_vectorstore\n'
if pattern in content:
    content = content.replace(pattern, pattern + import_line)
    print('Added RRFusion import')
else:
    print('WARNING: Could not find vectorstore import line')

# Step 2: Find the __init__ method and add new attributes
# Find 'self._lock = asyncio.Lock()' inside __init__
lock_pattern = '        self._lock = asyncio.Lock()\n'
if lock_pattern in content:
    insert_code = '''        self._lock = asyncio.Lock()
        self._datalake = None
        self._tag_index = None
        self._hybrid_config = None
        self._rrf = RRFusion(k=60)'''
    content = content.replace(lock_pattern, insert_code)
    print('Added datalake, tag_index, hybrid_config to __init__')
else:
    print('WARNING: Could not find self._lock line')

# Step 3: Find the search_hybrid method and add RRF methods after it
# The search_hybrid method ends with '        return results\n    \n    async def index_entry('
# We want to insert after '        return results' but before the blank line + index_entry

search_hybrid_end = '        return results\n    \n    async def index_entry('
if search_hybrid_end in content:
    # Create the new methods
    new_methods = '''        return results

    # ============================================================================
    # RRF 融合检索方法
    # ============================================================================

    async def _search_vector(self, query: str, limit: int) -> list:
        """
        向量轨检索
        
        Args:
            query: 查询文本
            limit: 返回数量
            
        Returns:
            RankedResult 列表
        """
        try:
            options = SearchOptions(limit=limit)
            entries = await self.search_semantic(query, options)
            return [
                RankedResult(
                    memory_id=entry.id,
                    score=entry.score,
                    rank=i,
                    source="vector"
                )
                for i, entry in enumerate(entries)
            ]
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
            return []

    async def _search_library(
        self, 
        category_path: str = None, 
        limit: int = 10
    ) -> list:
        """
        图书馆轨检索
        
        Args:
            category_path: 分类路径
            limit: 返回数量
            
        Returns:
            RankedResult 列表
        """
        if not category_path:
            return []
        
        try:
            options = SearchOptions(limit=limit)
            entries = await self.search_by_category(
                category_path, 
                options=options
            )
            return [
                RankedResult(
                    memory_id=entry.id,
                    score=entry.score,
                    rank=i,
                    source="library"
                )
                for i, entry in enumerate(entries)
            ]
        except Exception as e:
            logger.warning(f"Library search failed: {e}")
            return []

    async def _search_tags(
        self, 
        tags: list = None, 
        limit: int = 10
    ) -> list:
        """
        Tag 轨检索（基于共现图谱扩展）
        
        Args:
            tags: 标签列表
            limit: 返回数量
            
        Returns:
            RankedResult 列表
        """
        if not tags:
            return []
        
        if self._tag_index is None:
            return []
        
        try:
            matched_ids = set()
            for tag in tags:
                ids = await self._tag_index.query(tag)
                matched_ids.update(ids)
            
            results = []
            for i, memory_id in enumerate(list(matched_ids)[:limit]):
                if self._datalake:
                    content_obj = await self._datalake.get_memory(memory_id)
                    if content_obj:
                        content_tags = content_obj.metadata.get("tags", [])
                        if isinstance(content_tags, str):
                            content_tags = [content_tags]
                        match_count = sum(1 for t in tags if t in content_tags)
                        score = match_count / max(len(tags), 1)
                        results.append(
                            RankedResult(
                                memory_id=memory_id,
                                score=score,
                                rank=i,
                                source="tag"
                            )
                        )
            
            return results
        except Exception as e:
            logger.warning(f"Tag search failed: {e}")
            return []

    async def search_hybrid_rrf(
        self,
        query: str,
        limit: int = 10,
        category_path: str = None,
        tags: list = None,
        fusion_k: int = 60,
        vector_weight: float = 0.5,
        library_weight: float = 0.3,
        tag_weight: float = 0.2,
    ) -> list[dict]:
        """
        双轨混合搜索（RRF 融合）。
        
        同时查询：
        1. 向量轨：semantic search
        2. 图书馆轨：category + tag 精确匹配
        3. Tag 轨：共现图谱扩展搜索
        
        融合策略：RRF + 加权组合
        
        Args:
            query: 查询文本
            limit: 返回数量
            category_path: 分类路径过滤
            tags: 标签过滤
            fusion_k: RRF 衰减参数
            vector_weight: 向量轨权重
            library_weight: 图书馆轨权重
            tag_weight: Tag 轨权重
            
        Returns:
            list[dict]: [{
                "id": "memory_id",
                "content": "...",
                "score": 0.xx,
                "rrf_score": 0.xx,
                "sources": ["vector", "library"],
                "metadata": {...}
            }]
        """
        vector_results = await self._search_vector(query, limit * 2)
        library_results = await self._search_library(category_path, limit * 2) if category_path else []
        tag_results = await self._search_tags(tags, limit * 2) if tags else []
        
        fusion = RRFusion(k=fusion_k)
        fusion_results = fusion.fuse(
            vector_results=vector_results if vector_results else None,
            library_results=library_results if library_results else None,
            tag_results=tag_results if tag_results else None,
        )
        
        final_results = []
        for fr in fusion_results[:limit]:
            content_text = ""
            metadata = {}
            if self._datalake:
                memory_content = await self._datalake.get_memory(fr.memory_id)
                if memory_content:
                    content_text = memory_content.content
                    metadata = memory_content.metadata
            
            final_results.append({
                "id": fr.memory_id,
                "content": content_text,
                "score": fr.rrf_score,
                "rrf_score": fr.rrf_score,
                "sources": list(fr.ranks.keys()),
                "ranks": fr.ranks,
                "details": fr.details,
                "metadata": metadata,
            })
        
        return final_results

'''
    content = content.replace(search_hybrid_end, new_methods)
    print('Added RRF methods after search_hybrid')
else:
    print('WARNING: Could not find search_hybrid end marker')

with open(r'C:\Users\31683\AgentMemory\agentmemory\search\search_engine.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('File update complete')
