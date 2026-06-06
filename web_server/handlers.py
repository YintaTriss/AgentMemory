"""
AgentMemory Web Server - HTTP Handlers
处理所有 API 路由
"""

import json
import asyncio
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

# 添加 src 目录到路径
SRC_PATH = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_PATH))

# 尝试导入后端 - 多种方式
BACKEND_AVAILABLE = False
MemoryManager = None
BACKEND_TYPE = "unknown"

# 方式1: 新版 agent_memory
try:
    from agent_memory import MemoryManager as MMNew
    MemoryManager = MMNew
    BACKEND_AVAILABLE = True
    BACKEND_TYPE = "new"
except ImportError as e:
    print(f"Cannot import from agent_memory: {e}")

# 方式2: 旧版 memory_manager
if not BACKEND_AVAILABLE:
    try:
        from memory_manager import MemoryHermes
        MemoryManager = MemoryHermes
        BACKEND_AVAILABLE = True
        BACKEND_TYPE = "hermes"
    except ImportError as e:
        print(f"Cannot import from memory_manager: {e}")

print(f"[web_server] Backend available: {BACKEND_AVAILABLE}, type: {BACKEND_TYPE}")

# 全局内存管理器实例
_memory_manager: Optional[Any] = None


def get_memory_manager() -> Optional[Any]:
    """获取或初始化 MemoryManager 实例"""
    global _memory_manager
    if _memory_manager is None and BACKEND_AVAILABLE:
        try:
            _memory_manager = MemoryManager()
        except Exception as e:
            print(f"Error initializing MemoryManager: {e}")
            return None
    return _memory_manager


class JSONEncoder(json.JSONEncoder):
    """自定义 JSON 编码器"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, "__dict__"):
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


# ============ 旧版 MemoryHermes Handler ============

async def hermes_handle_create_memory(request) -> dict:
    """使用旧版 MemoryHermes 创建记忆"""
    mm = get_memory_manager()
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
    metadata = {"category_path": category_path, "tags": tags, "source": "web_api"}
    
    try:
        memory_id = await mm.store(content=content, metadata=metadata, importance=importance)
        return success_response({"id": memory_id, "content": content}, 201)
    except Exception as e:
        return error_response(f"Failed to create: {str(e)}", 500)


async def hermes_handle_list_memories(request) -> dict:
    """使用旧版 MemoryHermes 列出记忆"""
    mm = get_memory_manager()
    category = request.query.get("category")
    limit = int(request.query.get("limit", 20))
    try:
        results = await mm.query(category or "", limit=limit)
        return success_response({"memories": results, "count": len(results)})
    except Exception as e:
        return error_response(f"Failed to list: {str(e)}", 500)


async def hermes_handle_get_memory(request, memory_id: str) -> dict:
    """使用旧版 MemoryHermes 获取单条"""
    mm = get_memory_manager()
    try:
        results = await mm.query(memory_id, limit=1)
        if not results:
            return error_response("Memory not found", 404)
        return success_response(results[0])
    except Exception as e:
        return error_response(f"Failed to get: {str(e)}", 500)


async def hermes_handle_delete_memory(request, memory_id: str) -> dict:
    """使用旧版 MemoryHermes 删除"""
    mm = get_memory_manager()
    try:
        success = await mm.forget(memory_id, permanent=True)
        if success:
            return success_response({"id": memory_id, "deleted": True})
        return error_response("Memory not found", 404)
    except Exception as e:
        return error_response(f"Failed to delete: {str(e)}", 500)


async def hermes_handle_search(request) -> dict:
    """使用旧版 MemoryHermes 搜索"""
    mm = get_memory_manager()
    query = request.query.get("q", "")
    if not query:
        return error_response("q parameter is required", 400)
    limit = int(request.query.get("limit", 5))
    try:
        results = await mm.query(query, limit=limit)
        return success_response({"query": query, "results": results, "count": len(results)})
    except Exception as e:
        return error_response(f"Failed to search: {str(e)}", 500)


async def hermes_handle_stats(request) -> dict:
    """使用旧版 MemoryHermes 统计"""
    mm = get_memory_manager()
    try:
        stats = mm.get_stats()
        return success_response({"stats": stats})
    except Exception as e:
        return error_response(f"Failed to get stats: {str(e)}", 500)


async def hermes_handle_sync(request) -> dict:
    """使用旧版 MemoryHermes 同步"""
    mm = get_memory_manager()
    try:
        result = await mm.run_decay_check()
        return success_response({"message": "Sync completed", "result": result})
    except Exception as e:
        return error_response(f"Failed to sync: {str(e)}", 500)


async def hermes_handle_compress(request) -> dict:
    """使用旧版 MemoryHermes 压缩"""
    mm = get_memory_manager()
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return error_response("Invalid JSON body", 400)
    memory_ids = body.get("ids", [])
    if not memory_ids:
        return error_response("ids is required", 400)
    try:
        results = []
        for mem_id in memory_ids:
            mem_result = await mm.query(mem_id, limit=1)
            if mem_result:
                results.append(mem_result[0])
        summary = "; ".join([r.get("content", "")[:100] for r in results])
        return success_response({"original_count": len(memory_ids), "found_count": len(results), "summary": summary})
    except Exception as e:
        return error_response(f"Failed to compress: {str(e)}", 500)


# ============ 新版 MemoryManager Handler ============

async def new_handle_create_memory(request) -> dict:
    """使用新版 MemoryManager 创建记忆"""
    mm = get_memory_manager()
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
    try:
        memory_id = await mm.add(content=content, importance=importance, category_path=category_path, tags=tags, source="web_api")
        return success_response({"id": memory_id, "content": content, "importance": importance}, 201)
    except Exception as e:
        return error_response(f"Failed to create: {str(e)}", 500)


async def new_handle_list_memories(request) -> dict:
    """使用新版 MemoryManager 列出记忆"""
    mm = get_memory_manager()
    category = request.query.get("category")
    limit = int(request.query.get("limit", 20))
    try:
        results = await mm.list(category_path=category, limit=limit)
        return success_response({"memories": results, "count": len(results)})
    except Exception as e:
        return error_response(f"Failed to list: {str(e)}", 500)


async def new_handle_get_memory(request, memory_id: str) -> dict:
    """使用新版 MemoryManager 获取单条"""
    mm = get_memory_manager()
    try:
        result = await mm.get(memory_id)
        if result is None:
            return error_response("Memory not found", 404)
        return success_response(result)
    except Exception as e:
        return er

# ============ 统一 Handler 分派 ============

async def handle_health(request) -> dict:
    """健康检查"""
    return success_response({"version": "0.3.0", "backend_available": BACKEND_AVAILABLE, "backend_type": BACKEND_TYPE, "timestamp": datetime.now().isoformat()})


async def handle_stats(request) -> dict:
    """获取统计信息"""
    mm = get_memory_manager()
    if mm is None:
        return error_response("Backend not available", 503)
    try:
        if BACKEND_TYPE == "hermes":
            stats = mm.get_stats()
        else:
            stats = await mm.stats()
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
    try:
        if BACKEND_TYPE == "hermes":
            metadata = {"category_path": category_path, "tags": tags, "source": "web_api"}
            memory_id = await mm.store(content=content, metadata=metadata, importance=importance)
        else:
            memory_id = await mm.add(content=content, importance=importance, category_path=category_path, tags=tags, source="web_api")
        return success_response({"id": memory_id, "content": content, "importance": importance}, 201)
    except Exception as e:
        return error_response(f"Failed to create: {str(e)}", 500)


async def handle_list_memories(request) -> dict:
    """列出记忆"""
    mm = get_memory_manager()
    if mm is None:
        return error_response("Backend not available", 503)
    category = request.query.get("category")
    limit = int(request.query.get("limit", 20))
    try:
        if BACKEND_TYPE == "hermes":
            results = await mm.query(category or "", limit=limit)
        else:
            results = await mm.list(category_path=category, limit=limit)
        return success_response({"memories": results, "count": len(results)})
    except Exception as e:
        return error_response(f"Failed to list: {str(e)}", 500)


async def handle_get_memory(request, memory_id: str) -> dict:
    """获取单条记忆详情"""
    mm = get_memory_manager()
    if mm is None:
        return error_response("Backend not available", 503)
    try:
        if BACKEND_TYPE == "hermes":
            results = await mm.query(memory_id, limit=1)
            if not results:
                return error_response("Memory not found", 404)
            result = results[0]
        else:
            result = await mm.get(memory_id)
            if result is None:
                return error_response("Memory not found", 404)
        return success_response(result)
    except Exception as e:
        return error_response(f"Failed to get: {str(e)}", 500)


async def handle_delete_memory(request, memory_id: str) -> dict:
    """删除记忆"""
    mm = get_memory_manager()
    if mm is None:
        return error_response("Backend not available", 503)
    try:
        if BACKEND_TYPE == "hermes":
            success = await mm.forget(memory_id, permanent=True)
        else:
            success = await mm.delete(memory_id)
        if success:
            return success_response({"id": memory_id, "deleted": True})
        return error_response("Memory not found", 404)
    except Exception as e:
        return error_response(f"Failed to delete: {str(e)}", 500)


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
    try:
        if BACKEND_TYPE == "hermes":
            results = await mm.query(query, limit=limit)
        else:
            results = await mm.search(query=query, limit=limit, category_path=category)
        return success_response({"query": query, "results": results, "count": len(results)})
    except Exception as e:
        return error_response(f"Failed to search: {str(e)}", 500)


async def handle_categories(request) -> dict:
    """获取所有已用分类"""
    mm = get_memory_manager()
    if mm is None:
        return error_response("Backend not available", 503)
    try:
        if BACKEND_TYPE == "hermes":
            stats = mm.get_stats()
        else:
            stats = await mm.stats()
        categories = stats.get("categories", [])
        return success_response({"categories": categories})
    except Exception as e:
        return error_response(f"Failed to get categories: {str(e)}", 500)


async def handle_sync(request) -> dict:
    """触发全量同步"""
    mm = get_memory_manager()
    if mm is None:
        return error_response("Backend not available", 503)
    try:
        if BACKEND_TYPE == "hermes":
            result = await mm.run_decay_check()
            return success_response({"message": "Sync completed", "result": result})
        else:
            result = mm.sync_all_memories()
            return success_response({"message": "Sync completed", "synced": result.get("synced", 0), "failed": result.get("failed", 0)})
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
        if BACKEND_TYPE == "hermes":
            results = []
            for mem_id in memory_ids:
                mem_result = await mm.query(mem_id, limit=1)
                if mem_result:
                    results.append(mem_result[0])
            summary = "; ".join([r.get("content", "")[:100] for r in results])
            return success_response({"original_count": len(memory_ids), "found_count": len(results), "summary": summary})
        else:
            summary = await mm.compress_for_context(memory_ids)
            return success_response({"original_count": len(memory_ids), "summary": summary})
    except Exception as e:
        return error_response(f"Failed to compress: {str(e)}", 500)
