"""
AgentMemory Web Server - HTTP Handlers
处理所有 API 路由
"""

import json
import asyncio
import sys
import os
from pathlib import Path
from typing import Optional
from datetime import datetime

# 添加 src 目录到路径
SRC_PATH = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_PATH))

# 尝试导入后端
try:
    from memory_manager import MemoryHermes
    BACKEND_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Cannot import MemoryHermes: {e}")
    BACKEND_AVAILABLE = False
    MemoryHermes = None

# 全局内存管理器实例
_memory_hermes: Optional[MemoryHermes] = None


def get_memory_manager() -> Optional[MemoryHermes]:
    """获取或初始化 MemoryHermes 实例"""
    global _memory_hermes
    if _memory_hermes is None and BACKEND_AVAILABLE:
        try:
            _memory_hermes = MemoryHermes()
        except Exception as e:
            print(f"Error initializing MemoryHermes: {e}")
            return None
    return _memory_hermes


class JSONEncoder(json.JSONEncoder):
    """自定义 JSON 编码器，处理日期和特殊类型"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        return super().default(obj)


def json_response(data, status=200):
    """创建 JSON 响应"""
    return {
        "status": status,
        "body": json.dumps(data, ensure_ascii=False, cls=JSONEncoder),
        "content_type": "application/json"
    }


def error_response(message: str, status: int = 400):
    """创建错误响应"""
    return json_response({"error": message, "status": "error"}, status)


def success_response(data, status: int = 200):
    """创建成功响应"""
    return json_response({"status": "ok", **data}, status)


async def handle_health(request) -> dict:
    """健康检查"""
    return success_response({
        "version": "0.3.0",
        "backend_available": BACKEND_AVAILABLE,
        "timestamp": datetime.now().isoformat()
    })


async def handle_stats(request) -> dict:
    """获取统计信息"""
    mm = get_memory_manager()
    if mm is None:
        return error_response("Backend not available", 503)
    
    try:
        stats = mm.get_stats()
        return success_response({"stats": stats})
    except Exception as e:
        return error_response(f"Failed to get stats: {str(e)}", 500)


async def handle_create_memory(request) -> dict:
    """创建新记忆"""
    mm = get_memory_manager()
    if mm is None:
        return error_response("Backend not available", 503)
    
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return error_response("Invalid JSON body", 400)
    
    content = body.get("content")
    if not content:
        return error_response("content is required", 400)
    
    importance = body.get("importance", 0.5)
    category_path = body.get("category_path")
    tags = body.get("tags", [])
    
    # 构建元数据
    metadata = {
        "category_path": category_path,
        "tags": tags,
        "source": "web_api"
    }
    
    try:
        memory_id = await mm.store(
            content=content,
            metadata=metadata,
            importance=importance
        )
        return success_response({
            "id": memory_id,
            "content": content,
            "importance": importance
        }, 201)
    except Exception as e:
        return error_response(f"Failed to create memory: {str(e)}", 500)


async def handle_list_memories(request) -> dict:
    """列出记忆"""
    mm = get_memory_manager()
    if mm is None:
        return error_response("Backend not available", 503)
    
    category = request.query.get("category")
    limit = int(request.query.get("limit", 20))
    
    try:
        # 使用 query 接口获取记忆列表
        query = category or ""
        results = await mm.query(query, limit=limit)
        
        memories = []
        for r in results:
            memories.append({
                "id": r.get("id", ""),
                "content": r.get("content", ""),
                "importance": r.get("importance", 0.5),
                "score": r.get("score", 0),
                "tags": r.get("tags", []),
                "created_at": r.get("created_at", "")
            })
        
        return success_response({
            "memories": memories,
            "count": len(memories)
        })
    except Exception as e:
        return error_response(f"Failed to list memories: {str(e)}", 500)


async def handle_get_memory(request, memory_id: str) -> dict:
    """获取单条记忆详情"""
    mm = get_memory_manager()
    if mm is None:
        return error_response("Backend not available", 503)
    
    try:
        # 通过 query 获取单条记忆
        results = await mm.query(memory_id, limit=1)
        
        if not results:
            return error_response("Memory not found", 404)
        
        r = results[0]
        return success_response({
            "id": r.get("id", ""),
            "content": r.get("content", ""),
            "importance": r.get("importance", 0.5),
            "score": r.get("score", 0),
            "tags": r.get("tags", []),
            "created_at": r.get("created_at", "")
        })
    except Exception as e:
        return error_response(f"Failed to get memory: {str(e)}", 500)


async def handle_delete_memory(request, memory_id: str) -> dict:
    """删除记忆"""
    mm = get_memory_manager()
    if mm is None:
        return error_response("Backend not available", 503)
    
    try:
        success = await mm.forget(memory_id, permanent=True)
        if success:
            return success_response({"id": memory_id, "deleted": True})
        else:
            return error_response("Memory not found or already deleted", 404)
    except Exception as e:
        return error_response(f"Failed to delete memory: {str(e)}", 500)


async def handle_search(request) -> dict:
    """语义搜索"""
    mm = get_memory_manager()
    if mm is None:
        return error_response("Backend not available", 503)
    
    query = request.query.get("q", "")
    if not query:
        return error_response("q parameter is required", 400)
    
    limit = int(request.query.get("limit", 5))
    category = request.query.get("category")
    
    # 构建过滤器
    filters = None
    if category:
        filters = {"category": category}
    
    try:
        results = await mm.query(query, limit=limit, filters=filters)
        
        memories = []
        for r in results:
            memories.append({
                "id": r.get("id", ""),
                "content": r.get("content", ""),
                "score": r.get("score", 0),
                "importance": r.get("importance", 0.5),
                "tags": r.get("tags", [])
            })
        
        return success_response({
            "query": query,
            "results": memories,
            "count": len(memories)
        })
    except Exception as e:
        return error_response(f"Failed to search: {str(e)}", 500)


async def handle_categories(request) -> dict:
    """获取所有已用分类"""
    mm = get_memory_manager()
    if mm is None:
        return error_response("Backend not available", 503)
    
    try:
        stats = mm.get_stats()
        # 从 stats 中提取分类信息
        categories = []
        if "categories" in stats:
            categories = stats["categories"]
        
        return success_response({"categories": categories})
    except Exception as e:
        return error_response(f"Failed to get categories: {str(e)}", 500)


async def handle_sync(request) -> dict:
    """触发全量同步"""
    mm = get_memory_manager()
    if mm is None:
        return error_response("Backend not available", 503)
    
    try:
        # 运行遗忘检查作为同步操作
        result = await mm.run_decay_check()
        return success_response({
            "message": "Sync completed",
            "result": result
        })
    except Exception as e:
        return error_response(f"Failed to sync: {str(e)}", 500)


async def handle_compress(request) -> dict:
    """压缩摘要"""
    mm = get_memory_manager()
    if mm is None:
        return error_response("Backend not available", 503)
    
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return error_response("Invalid JSON body", 400)
    
    memory_ids = body.get("ids", [])
    if not memory_ids:
        return error_response("ids is required", 400)
    
    try:
        # 获取指定记忆并生成摘要
        results = []
        for mem_id in memory_ids:
            mem_result = await mm.query(mem_id, limit=1)
            if mem_result:
                results.append(mem_result[0])
        
        # 生成简单摘要
        summary = "; ".join([r.get("content", "")[:100] for r in results])
        
        return success_response({
            "original_count": len(memory_ids),
            "found_count": len(results),
            "summary": summary
        })
    except Exception as e:
        return error_response(f"Failed to compress: {str(e)}", 500)
