"""
AgentMemory Web API Server
基于FastAPI的REST API服务器，暴露AgentMemory后端功能
"""

import sys
import os
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi import FastAPI
import uvicorn

# 添加AgentMemory src目录到路径
# 方式：默认从 web_server/ 的父目录（即项目根目录）找 src/
# 环境变量 AGENTMEMORY_PATH 可覆盖（用于非标准安装）
_AGENTMEMORY_ROOT = Path(os.environ.get(
    "AGENTMEMORY_PATH",
    Path(__file__).parent.parent  # 默认：AgentMemory/ (即 web_server 的上两级)
))
AGENTMEMORY_PATH = _AGENTMEMORY_ROOT
sys.path.insert(0, str(_AGENTMEMORY_ROOT / "src"))

from models import (
    StoreRequest, QueryRequest, StoreResponse, QueryResponse,
    MemoryResult, StatsResponse, ForgetRequest, ForgetResponse,
    SyncTurnRequest, SyncTurnResponse, DecayCheckResponse,
    PrefetchResponse, HealthResponse, ErrorResponse
)

# 尝试导入AgentMemory核心模块
try:
    from memory_manager import MemoryHermes
    MEMORY_HERMES_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import MemoryHermes: {e}")
    MEMORY_HERMES_AVAILABLE = False
    MemoryHermes = None


# 全局内存管理器实例
memory_hermes: MemoryHermes = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global memory_hermes
    
    # 启动时初始化
    if MEMORY_HERMES_AVAILABLE:
        try:
            memory_hermes = MemoryHermes()
            print("✅ MemoryHermes initialized successfully")
        except Exception as e:
            print(f"⚠️ MemoryHermes initialization failed: {e}")
            memory_hermes = None
    else:
        print("⚠️ MemoryHermes not available, using mock mode")
        memory_hermes = None
    
    yield
    
    # 关闭时清理
    print("🛑 Shutting down AgentMemory Web Server")


# 创建FastAPI应用
app = FastAPI(
    title="AgentMemory Web API",
    description="AgentMemory 四层闭环记忆系统的Web接口",
    version="1.0.0",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件目录
STATIC_PATH = Path(__file__).parent / "static"
if STATIC_PATH.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_PATH)), name="static")


# ==================== 健康检查 ====================

@app.get("/health", response_model=HealthResponse, tags=["健康检查"])
async def health_check():
    """健康检查接口"""
    layers = {
        "l1_compress": True,
        "l2_graph": True,
        "l3_vector": True,
        "l4_files": True
    }
    
    return HealthResponse(
        status="healthy" if memory_hermes else "degraded",
        version="1.0.0",
        layers_enabled=layers
    )


# ==================== 记忆存储 ====================

@app.post("/api/v1/memories", response_model=StoreResponse, tags=["记忆管理"])
async def store_memory(request: StoreRequest):
    """
    存储新记忆
    
    - **content**: 记忆内容（必填）
    - **importance**: 重要性评分 0-1（默认0.5）
    - **metadata**: 元数据字典（可选）
    - **fact_type**: 事实类型（默认general）
    - **tags**: 标签列表（可选）
    """
    if not memory_hermes:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory system not available"
        )
    
    try:
        # 构建元数据
        metadata = request.metadata or {}
        metadata["fact_type"] = request.fact_type
        if request.tags:
            metadata["tags"] = request.tags
        
        # 调用后端存储
        memory_id = await memory_hermes.store(
            content=request.content,
            metadata=metadata,
            importance=request.importance
        )
        
        return StoreResponse(
            success=True,
            memory_id=memory_id,
            content=request.content,
            importance=request.importance,
            created_at=datetime.now().isoformat()
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store memory: {str(e)}"
        )


# ==================== 记忆查询 ====================

@app.post("/api/v1/memories/query", response_model=QueryResponse, tags=["记忆管理"])
async def query_memories(request: QueryRequest):
    """
    查询记忆（混合检索）
    
    - **query**: 查询文本（必填）
    - **limit**: 返回结果数量（默认5，最大100）
    - **mode**: 检索模式 - hybrid/vector/category
    - **tags**: 标签过滤（可选）
    """
    if not memory_hermes:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory system not available"
        )
    
    try:
        # 构建过滤器
        filters = None
        if request.tags:
            filters = {"tags": request.tags}
        
        # 调用后端查询
        results = await memory_hermes.query(
            query=request.query,
            limit=request.limit,
            filters=filters
        )
        
        # 转换结果格式
        memory_results = []
        for r in results:
            memory_results.append(MemoryResult(
                id=r.get("id", ""),
                content=r.get("content", ""),
                score=r.get("score", 0.0),
                importance=r.get("importance", 0.5),
                fact_type=r.get("fact_type", "general"),
                tags=r.get("tags", []),
                created_at=r.get("created_at", datetime.now().isoformat()),
                entities=r.get("entities")
            ))
        
        return QueryResponse(
            success=True,
            query=request.query,
            results=memory_results,
            total=len(memory_results),
            mode=request.mode
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query memories: {str(e)}"
        )


# ==================== 记忆统计 ====================

@app.get("/api/v1/memories/stats", response_model=StatsResponse, tags=["系统管理"])
async def get_stats():
    """获取记忆系统统计信息"""
    if not memory_hermes:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory system not available"
        )
    
    try:
        stats = memory_hermes.get_stats()
        
        return StatsResponse(
            success=True,
            layers=stats.get("layers", {}),
            vector=stats.get("vector"),
            graph=stats.get("graph"),
            file=stats.get("file")
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stats: {str(e)}"
        )


# ==================== 记忆预取 ====================

@app.get("/api/v1/memories/prefetch", response_model=PrefetchResponse, tags=["记忆管理"])
async def prefetch_memories(query: str):
    """
    预取相关记忆（后台缓存）
    
    - **query**: 查询文本
    """
    if not memory_hermes:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory system not available"
        )
    
    try:
        await memory_hermes.prefetch(query)
        prefetched = memory_hermes.get_prefetched(query)
        
        return PrefetchResponse(
            success=True,
            query=query,
            prefetched_count=len(prefetched) if prefetched else 0
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to prefetch: {str(e)}"
        )


# ==================== 遗忘记忆 ====================

@app.delete("/api/v1/memories/{memory_id}", response_model=ForgetResponse, tags=["记忆管理"])
async def forget_memory(memory_id: str, permanent: bool = False):
    """
    遗忘指定记忆
    
    - **memory_id**: 记忆ID
    - **permanent**: 是否永久删除（默认false，会归档）
    """
    if not memory_hermes:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory system not available"
        )
    
    try:
        success = await memory_hermes.forget(memory_id, permanent=permanent)
        
        return ForgetResponse(
            success=success,
            memory_id=memory_id,
            message="Memory forgotten successfully" if success else "Memory not found or already forgotten"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to forget memory: {str(e)}"
        )


# ==================== 对话轮次同步 ====================

@app.post("/api/v1/sync-turn", response_model=SyncTurnResponse, tags=["对话管理"])
async def sync_turn(request: SyncTurnRequest):
    """
    对话轮次同步（LLM自动事实提取）
    
    - **user_msg**: 用户消息
    - **assistant_msg**: 助手消息
    """
    if not memory_hermes:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory system not available"
        )
    
    try:
        facts = await memory_hermes.sync_turn(
            user_msg=request.user_msg,
            assistant_msg=request.assistant_msg
        )
        
        return SyncTurnResponse(
            success=True,
            facts_extracted=len(facts),
            facts=facts
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync turn: {str(e)}"
        )


# ==================== 遗忘引擎检查 ====================

@app.post("/api/v1/decay-check", response_model=DecayCheckResponse, tags=["系统管理"])
async def run_decay_check():
    """运行遗忘引擎检查"""
    if not memory_hermes:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory system not available"
        )
    
    try:
        result = await memory_hermes.run_decay_check()
        
        return DecayCheckResponse(
            success=True,
            forgotten=result.get("forget", 0),
            archived=result.get("archive", 0),
            retained=result.get("retain", result.get("total", 0) - result.get("forget", 0) - result.get("archive", 0)),
            message=f"Forgotten {result.get('forget', 0)}, archived {result.get('archive', 0)}, retained {result.get('total', 0) - result.get('forget', 0) - result.get('archive', 0)}"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to run decay check: {str(e)}"
        )


# ==================== 根路由 - 返回前端页面 ====================

@app.get("/", response_class=HTMLResponse)
async def root():
    """返回前端页面"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AgentMemory - 记忆系统</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            .container { max-width: 1200px; margin: 0 auto; }
            .header { 
                background: white; 
                border-radius: 16px; 
                padding: 30px;
                margin-bottom: 20px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            }
            .header h1 { color: #667eea; margin-bottom: 10px; }
            .header p { color: #666; }
            .status-badge {
                display: inline-block;
                padding: 5px 15px;
                border-radius: 20px;
                font-size: 12px;
                margin-top: 10px;
            }
            .status-healthy { background: #10b981; color: white; }
            .status-degraded { background: #f59e0b; color: white; }
            
            .tabs {
                display: flex;
                gap: 10px;
                margin-bottom: 20px;
                flex-wrap: wrap;
            }
            .tab {
                padding: 12px 24px;
                background: rgba(255,255,255,0.9);
                border: none;
                border-radius: 10px;
                cursor: pointer;
                font-size: 14px;
                font-weight: 500;
                color: #667eea;
                transition: all 0.3s;
            }
            .tab:hover { transform: translateY(-2px); box-shadow: 0 5px 20px rgba(0,0,0,0.1); }
            .tab.active { background: white; box-shadow: 0 5px 20px rgba(0,0,0,0.15); }
            
            .panel {
                background: white;
                border-radius: 16px;
                padding: 30px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.1);
                display: none;
            }
            .panel.active { display: block; }
            
            .form-group { margin-bottom: 20px; }
            .form-group label { display: block; margin-bottom: 8px; font-weight: 500; color: #333; }
            .form-group input, .form-group textarea, .form-group select {
                width: 100%;
                padding: 12px 16px;
                border: 2px solid #e5e7eb;
                border-radius: 10px;
                font-size: 14px;
                transition: border-color 0.3s;
            }
            .form-group input:focus, .form-group textarea:focus, .form-group select:focus {
                outline: none;
                border-color: #667eea;
            }
            .form-group textarea { min-height: 120px; resize: vertical; }
            
            .btn {
                padding: 12px 30px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.3s;
            }
            .btn:hover { transform: translateY(-2px); box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4); }
            .btn:disabled { opacity: 0.6; cursor: not-allowed; }
            
            .result-box {
                margin-top: 20px;
                padding: 20px;
                background: #f9fafb;
                border-radius: 10px;
                border: 1px solid #e5e7eb;
                white-space: pre-wrap;
                font-family: 'Monaco', 'Menlo', monospace;
                font-size: 13px;
                max-height: 400px;
                overflow-y: auto;
            }
            
            .memory-card {
                background: #f9fafb;
                border-radius: 10px;
                padding: 15px;
                margin-bottom: 10px;
                border-left: 4px solid #667eea;
            }
            .memory-card .score { 
                color: #667eea; 
                font-weight: bold; 
                margin-bottom: 5px; 
            }
            .memory-card .content { color: #333; margin-bottom: 10px; }
            .memory-card .meta { 
                display: flex; 
                gap: 10px; 
                font-size: 12px; 
                color: #666; 
            }
            .memory-card .tag {
                background: #e5e7eb;
                padding: 2px 8px;
                border-radius: 4px;
            }
            
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-top: 20px;
            }
            .stat-card {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                border-radius: 12px;
                text-align: center;
            }
            .stat-card .value { font-size: 36px; font-weight: bold; }
            .stat-card .label { font-size: 14px; opacity: 0.9; }
            
            .layer-indicator {
                display: flex;
                gap: 15px;
                margin-top: 20px;
                flex-wrap: wrap;
            }
            .layer {
                padding: 10px 20px;
                background: #f3f4f6;
                border-radius: 8px;
                font-size: 13px;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            .layer .dot {
                width: 8px;
                height: 8px;
                border-radius: 50%;
            }
            .layer .dot.enabled { background: #10b981; }
            .layer .dot.disabled { background: #ef4444; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🧠 AgentMemory</h1>
                <p>四层闭环记忆系统 - 双轨 + 图书馆架构</p>
                <div id="status" class="status-badge">检查中...</div>
            </div>
            
            <div class="tabs">
                <button class="tab active" onclick="showTab('store')">📝 存储记忆</button>
                <button class="tab" onclick="showTab('query')">🔍 查询记忆</button>
                <button class="tab" onclick="showTab('stats')">📊 统计信息</button>
                <button class="tab" onclick="showTab('session')">💬 会话同步</button>
                <button class="tab" onclick="showTab('decay')">🔄 遗忘检查</button>
            </div>
            
            <!-- 存储记忆面板 -->
            <div id="panel-store" class="panel active">
                <h2>存储新记忆</h2>
                <div class="form-group">
                    <label>记忆内容</label>
                    <textarea id="store-content" placeholder="输入要记忆的内容..."></textarea>
                </div>
                <div class="form-group">
                    <label>重要性评分 (0-1)</label>
                    <input type="range" id="store-importance" min="0" max="1" step="0.1" value="0.5">
                    <span id="importance-value">0.5</span>
                </div>
                <div class="form-group">
                    <label>事实类型</label>
                    <select id="store-fact-type">
                        <option value="general">一般</option>
                        <option value="preference">偏好</option>
                        <option value="fact">事实</option>
                        <option value="decision">决策</option>
                        <option value="relationship">关系</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>标签 (逗号分隔)</label>
                    <input type="text" id="store-tags" placeholder="如: 工作, 重要, 私人">
                </div>
                <button class="btn" onclick="storeMemory()">存储记忆</button>
                <div id="store-result" class="result-box" style="display:none;"></div>
            </div>
            
            <!-- 查询记忆面板 -->
            <div id="panel-query" class="panel">
                <h2>查询记忆</h2>
                <div class="form-group">
                    <label>查询文本</label>
                    <input type="text" id="query-text" placeholder="输入查询关键词...">
                </div>
                <div class="form-group">
                    <label>检索模式</label>
                    <select id="query-mode">
                        <option value="hybrid">混合检索 (向量+分类)</option>
                        <option value="vector">仅向量检索</option>
                        <option value="category">仅分类检索</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>返回数量</label>
                    <input type="number" id="query-limit" min="1" max="100" value="5">
                </div>
                <button class="btn" onclick="queryMemories()">查询</button>
                <div id="query-result" class="result-box" style="display:none;"></div>
            </div>
            
            <!-- 统计面板 -->
            <div id="panel-stats" class="panel">
                <h2>记忆系统统计</h2>
                <div id="stats-grid" class="stats-grid"></div>
                <div id="layer-info" class="layer-indicator"></div>
                <button class="btn" onclick="refreshStats()" style="margin-top: 20px;">刷新统计</button>
            </div>
            
            <!-- 会话同步面板 -->
            <div id="panel-session" class="panel">
                <h2>对话轮次同步</h2>
                <div class="form-group">
                    <label>用户消息</label>
                    <textarea id="sync-user" placeholder="用户说了什么..."></textarea>
                </div>
                <div class="form-group">
                    <label>助手回复</label>
                    <textarea id="sync-assistant" placeholder="助手回复了什么..."></textarea>
                </div>
                <button class="btn" onclick="syncTurn()">同步并提取事实</button>
                <div id="sync-result" class="result-box" style="display:none;"></div>
            </div>
            
            <!-- 遗忘检查面板 -->
            <div id="panel-decay" class="panel">
                <h2>遗忘引擎检查</h2>
                <p style="color: #666; margin-bottom: 20px;">
                    运行遗忘检查，根据访问频率、重要性、时效性自动归档或删除低分记忆。
                </p>
                <button class="btn" onclick="runDecayCheck()">运行遗忘检查</button>
                <div id="decay-result" class="result-box" style="display:none;"></div>
            </div>
        </div>
        
        <script>
            const API_BASE = '/api/v1';
            
            // 检查健康状态
            async function checkHealth() {
                try {
                    const res = await fetch('/health');
                    const data = await res.json();
                    const badge = document.getElementById('status');
                    badge.textContent = data.status === 'healthy' ? '✅ 系统正常' : '⚠️ 系统降级';
                    badge.className = 'status-badge ' + (data.status === 'healthy' ? 'status-healthy' : 'status-degraded');
                } catch (e) {
                    document.getElementById('status').textContent = '❌ 系统离线';
                }
            }
            
            // 显示标签页
            function showTab(name) {
                document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.getElementById('panel-' + name).classList.add('active');
                event.target.classList.add('active');
                
                if (name === 'stats') refreshStats();
            }
            
            // 重要性滑块
            document.getElementById('store-importance').addEventListener('input', function() {
                document.getElementById('importance-value').textContent = this.value;
            });
            
            // 存储记忆
            async function storeMemory() {
                const content = document.getElementById('store-content').value.trim();
                if (!content) { alert('请输入记忆内容'); return; }
                
                const importance = parseFloat(document.getElementById('store-importance').value);
                const factType = document.getElementById('store-fact-type').value;
                const tagsInput = document.getElementById('store-tags').value.trim();
                const tags = tagsInput ? tagsInput.split(',').map(t => t.trim()).filter(t => t) : null;
                
                const btn = event.target;
                btn.disabled = true;
                btn.textContent = '存储中...';
                
                try {
                    const res = await fetch(API_BASE + '/memories', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ content, importance, fact_type: factType, tags })
                    });
                    const data = await res.json();
                    
                    const resultBox = document.getElementById('store-result');
                    resultBox.style.display = 'block';
                    resultBox.innerHTML = data.success 
                        ? `✅ <strong>记忆已存储</strong>\n\nID: ${data.memory_id}\n重要性: ${data.importance}\n时间: ${data.created_at}`
                        : `❌ 存储失败: ${JSON.stringify(data)}`;
                } catch (e) {
                    document.getElementById('store-result').style.display = 'block';
                    document.getElementById('store-result').textContent = '❌ 请求失败: ' + e.message;
                } finally {
                    btn.disabled = false;
                    btn.textContent = '存储记忆';
                }
            }
            
            // 查询记忆
            async function queryMemories() {
                const query = document.getElementById('query-text').value.trim();
                if (!query) { alert('请输入查询文本'); return; }
                
                const mode = document.getElementById('query-mode').value;
                const limit = parseInt(document.getElementById('query-limit').value);
                
                const btn = event.target;
                btn.disabled = true;
                btn.textContent = '查询中...';
                
                try {
                    const res = await fetch(API_BASE + '/memories/query', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ query, mode, limit })
                    });
                    const data = await res.json();
                    
                    const resultBox = document.getElementById('query-result');
                    resultBox.style.display = 'block';
                    
                    if (data.success && data.results.length > 0) {
                        resultBox.innerHTML = `<strong>找到 ${data.total} 条相关记忆</strong>\n\n` +
                            data.results.map(r => `
                                <div class="memory-card">
                                    <div class="score">匹配度: ${(r.score * 100).toFixed(1)}%</div>
                                    <div class="content">${r.content}</div>
                                    <div class="meta">
                                        <span>重要性: ${r.importance}</span>
                                        <span>类型: ${r.fact_type}</span>
                                        ${r.tags.map(t => '<span class="tag">' + t + '</span>').join('')}
                                    </div>
                                </div>
                            `).join('');
                    } else {
                        resultBox.innerHTML = '🔍 未找到相关记忆';
                    }
                } catch (e) {
                    document.getElementById('query-result').style.display = 'block';
                    document.getElementById('query-result').textContent = '❌ 请求失败: ' + e.message;
                } finally {
                    btn.disabled = false;
                    btn.textContent = '查询';
                }
            }
            
            // 刷新统计
            async function refreshStats() {
                try {
                    const res = await fetch(API_BASE + '/memories/stats');
                    const data = await res.json();
                    
                    if (data.success) {
                        const statsGrid = document.getElementById('stats-grid');
                        const vector = data.vector || {};
                        const graph = data.graph || {};
                        
                        statsGrid.innerHTML = `
                            <div class="stat-card">
                                <div class="value">${vector.total || 0}</div>
                                <div class="label">总记忆数</div>
                            </div>
                            <div class="stat-card">
                                <div class="value">${graph.entities || 0}</div>
                                <div class="label">实体数量</div>
                            </div>
                            <div class="stat-card">
                                <div class="value">${vector.active || 0}</div>
                                <div class="label">活跃记忆</div>
                            </div>
                            <div class="stat-card">
                                <div class="value">${vector.archived || 0}</div>
                                <div class="label">已归档</div>
                            </div>
                        `;
                        
                        const layerInfo = document.getElementById('layer-info');
                        const layers = data.layers || {};
                        layerInfo.innerHTML = Object.entries(layers).map(([name, enabled]) => `
                            <div class="layer">
                                <span class="dot ${enabled ? 'enabled' : 'disabled'}"></span>
                                ${name}
                            </div>
                        `).join('');
                    }
                } catch (e) {
                    console.error('Failed to load stats:', e);
                }
            }
            
            // 会话同步
            async function syncTurn() {
                const userMsg = document.getElementById('sync-user').value.trim();
                const assistantMsg = document.getElementById('sync-assistant').value.trim();
                
                if (!userMsg || !assistantMsg) {
                    alert('请填写用户消息和助手回复');
                    return;
                }
                
                const btn = event.target;
                btn.disabled = true;
                btn.textContent = '同步中...';
                
                try {
                    const res = await fetch(API_BASE + '/sync-turn', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ user_msg: userMsg, assistant_msg: assistantMsg })
                    });
                    const data = await res.json();
                    
                    const resultBox = document.getElementById('sync-result');
                    resultBox.style.display = 'block';
                    resultBox.innerHTML = data.success
                        ? `✅ <strong>提取了 ${data.facts_extracted} 条事实</strong>\n\n` + 
                          (data.facts.map(f => `• ${f.content || JSON.stringify(f)}`).join('\n') || '无')
                        : `❌ 同步失败: ${JSON.stringify(data)}`;
                } catch (e) {
                    document.getElementById('sync-result').style.display = 'block';
                    document.getElementById('sync-result').textContent = '❌ 请求失败: ' + e.message;
                } finally {
                    btn.disabled = false;
                    btn.textContent = '同步并提取事实';
                }
            }
            
            // 遗忘检查
            async function runDecayCheck() {
                const btn = event.target;
                btn.disabled = true;
                btn.textContent = '运行中...';
                
                try {
                    const res = await fetch(API_BASE + '/decay-check', { method: 'POST' });
                    const data = await res.json();
                    
                    const resultBox = document.getElementById('decay-result');
                    resultBox.style.display = 'block';
                    resultBox.innerHTML = data.success
                        ? `✅ <strong>遗忘检查完成</strong>\n\n遗忘: ${data.forgotten} 条\n归档: ${data.archived} 条\n保留: ${data.retained} 条`
                        : `❌ 检查失败: ${JSON.stringify(data)}`;
                } catch (e) {
                    document.getElementById('decay-result').style.display = 'block';
                    document.getElementById('decay-result').textContent = '❌ 请求失败: ' + e.message;
                } finally {
                    btn.disabled = false;
                    btn.textContent = '运行遗忘检查';
                }
            }
            
            // 初始化
            checkHealth();
            setInterval(checkHealth, 30000); // 每30秒检查一次
        </script>
    </body>
    </html>
    """
