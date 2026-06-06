"""
AgentMemory Web Server - Main Application
使用 aiohttp 实现的轻量级 REST API 服务器
"""

import asyncio
import signal
import sys
import os
from pathlib import Path
from aiohttp import web
import json

# 导入 handlers
try:
    from .handlers import (
        handle_health,
        handle_stats,
        handle_create_memory,
        handle_list_memories,
        handle_get_memory,
        handle_delete_memory,
        handle_search,
        handle_categories,
        handle_sync,
        handle_compress,
    )
except ImportError:
    from handlers import (
        handle_health,
        handle_stats,
        handle_create_memory,
        handle_list_memories,
        handle_get_memory,
        handle_delete_memory,
        handle_search,
        handle_categories,
        handle_sync,
        handle_compress,
    )

# 服务器配置
DEFAULT_PORT = 8765
DEFAULT_HOST = "0.0.0.0"

# 静态文件目录
STATIC_DIR = Path(__file__).parent / "static"


INDEX_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AgentMemory API</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 40px 20px;
            color: #333;
        }
        .container { max-width: 1000px; margin: 0 auto; }
        .header {
            background: white;
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 24px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }
        .header h1 { color: #667eea; margin-bottom: 8px; }
        .header p { color: #666; }
        .card {
            background: white;
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }
        .card h2 { color: #333; margin-bottom: 16px; }
        .endpoint {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 12px;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 14px;
        }
        .method {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: bold;
            margin-right: 8px;
            font-size: 12px;
        }
        .method.get { background: #10b981; color: white; }
        .method.post { background: #3b82f6; color: white; }
        .method.delete { background: #ef4444; color: white; }
        .path { color: #333; }
        .desc { color: #666; font-size: 12px; margin-top: 4px; }
        .btn {
            display: inline-block;
            padding: 10px 20px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            margin: 10px 10px 10px 0;
        }
        .btn:hover { opacity: 0.9; }
        #result { margin-top: 20px; padding: 20px; background: #f8f9fa; border-radius: 8px; font-family: monospace; white-space: pre-wrap; display: none; max-height: 400px; overflow-y: auto; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧠 AgentMemory API</h1>
            <p>四层闭环记忆系统 - REST API (v0.3.0)</p>
        </div>
        
        <div class="card">
            <h2>📡 API 端点</h2>
            
            <div class="endpoint">
                <span class="method get">GET</span>
                <span class="path">/api/health</span>
                <div class="desc">健康检查</div>
            </div>
            
            <div class="endpoint">
                <span class="method get">GET</span>
                <span class="path">/api/stats</span>
                <div class="desc">获取各层统计信息</div>
            </div>
            
            <div class="endpoint">
                <span class="method post">POST</span>
                <span class="path">/api/memories</span>
                <div class="desc">创建新记忆 {content, importance, category_path, tags}</div>
            </div>
            
            <div class="endpoint">
                <span class="method get">GET</span>
                <span class="path">/api/memories?category=xx&limit=20</span>
                <div class="desc">列出记忆</div>
            </div>
            
            <div class="endpoint">
                <span class="method get">GET</span>
                <span class="path">/api/memories/{id}</span>
                <div class="desc">获取单条记忆</div>
            </div>
            
            <div class="endpoint">
                <span class="method delete">DELETE</span>
                <span class="path">/api/memories/{id}</span>
                <div class="desc">删除记忆</div>
            </div>
            
            <div class="endpoint">
                <span class="method get">GET</span>
                <span class="path">/api/search?q=xxx&limit=5</span>
                <div class="desc">语义检索</div>
            </div>
            
            <div class="endpoint">
                <span class="method get">GET</span>
                <span class="path">/api/categories</span>
                <div class="desc">获取所有已用分类</div>
            </div>
            
            <div class="endpoint">
                <span class="method post">POST</span>
                <span class="path">/api/sync</span>
                <div class="desc">触发全量同步</div>
            </div>
            
            <div class="endpoint">
                <span class="method post">POST</span>
                <span class="path">/api/compress</span>
                <div class="desc">压缩摘要 {ids: [...]}</div>
            </div>
        </div>
        
        <div class="card">
            <h2>🧪 快速测试</h2>
            <button class="btn" onclick="testHealth()">测试健康检查</button>
            <button class="btn" onclick="testList()">测试列出记忆</button>
            <button class="btn" onclick="testCreate()">测试创建记忆</button>
            <button class="btn" onclick="testSearch()">测试搜索</button>
            <div id="result"></div>
        </div>
    </div>
    
    <script>
        const API = '';
        
        function showResult(data) {
            const el = document.getElementById('result');
            el.style.display = 'block';
            el.textContent = JSON.stringify(data, null, 2);
        }
        
        async function testHealth() {
            const res = await fetch(API + '/api/health');
            const data = await res.json();
            showResult(data);
        }
        
        async function testList() {
            const res = await fetch(API + '/api/memories?limit=5');
            const data = await res.json();
            showResult(data);
        }
        
        async function testCreate() {
            const res = await fetch(API + '/api/memories', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    content: '测试记忆 ' + new Date().toISOString(),
                    importance: 0.8,
                    category_path: '测试/单元测试',
                    tags: ['test', 'api']
                })
            });
            const data = await res.json();
            showResult(data);
        }
        
        async function testSearch() {
            const res = await fetch(API + '/api/search?q=测试&limit=3');
            const data = await res.json();
            showResult(data);
        }
    </script>
</body>
</html>"""


class MemoryServer:
    """记忆服务器"""
    
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self.app = web.Application()
        self.runner = None
        self._setup_routes()
    
    def _setup_routes(self):
        """设置路由"""
        app = self.app
        
        # 首页
        app.router.add_get('/', self.handle_index)
        
        # API 路由
        app.router.add_get('/api/health', self.handle_api_health)
        app.router.add_get('/api/stats', self.handle_api_stats)
        app.router.add_post('/api/memories', self.handle_api_create_memory)
        app.router.add_get('/api/memories', self.handle_api_list_memories)
        app.router.add_get('/api/memories/{memory_id}', self.handle_api_get_memory)
        app.router.add_delete('/api/memories/{memory_id}', self.handle_api_delete_memory)
        app.router.add_get('/api/search', self.handle_api_search)
        app.router.add_get('/api/categories', self.handle_api_categories)
        app.router.add_post('/api/sync', self.handle_api_sync)
        app.router.add_post('/api/compress', self.handle_api_compress)
        
        # 静态文件
        if STATIC_DIR.exists():
            app.router.add_static('/static', str(STATIC_DIR), show_index=True)
    
    async def handle_index(self, request):
        """首页"""
        return web.Response(text=INDEX_HTML, content_type='text/html')
    
    async def handle_api_health(self, request):
        result = await handle_health(request)
        return self._make_response(result)
    
    async def handle_api_stats(self, request):
        result = await handle_stats(request)
        return self._make_response(result)
    
    async def handle_api_create_memory(self, request):
        result = await handle_create_memory(request)
        return self._make_response(result)
    
    async def handle_api_list_memories(self, request):
        result = await handle_list_memories(request)
        return self._make_response(result)
    
    async def handle_api_get_memory(self, request):
        memory_id = request.match_info['memory_id']
        result = await handle_get_memory(request, memory_id)
        return self._make_response(result)
    
    async def handle_api_delete_memory(self, request):
        memory_id = request.match_info['memory_id']
        result = await handle_delete_memory(request, memory_id)
        return self._make_response(result)
    
    async def handle_api_search(self, request):
        result = await handle_search(request)
        return self._make_response(result)
    
    async def handle_api_categories(self, request):
        result = await handle_categories(request)
        return self._make_response(result)
    
    async def handle_api_sync(self, request):
        result = await handle_sync(request)
        return self._make_response(result)
    
    async def handle_api_compress(self, request):
        result = await handle_compress(request)
        return self._make_response(result)
    
    def _make_response(self, result: dict) -> web.Response:
        return web.Response(
            text=result['body'],
            status=result['status'],
            content_type=result.get('content_type', 'application/json')
        )
    
    async def start(self):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, self.host, self.port)
        await site.start()
        print(f"AgentMemory API Server started on {self.host}:{self.port}")
    
    async def stop(self):
        if self.runner:
            await self.runner.cleanup()


async def run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
    server = MemoryServer(host, port)
    stop_event = asyncio.Event()
    
    def signal_handler():
        stop_event.set()
    
    await server.start()
    
    # Windows 不支持 signal handler，使用 Ctrl+C 中断
    try:
        import sys
        if sys.platform != 'win32':
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, signal_handler)
                except (NotImplementedError, OSError):
                    pass  # Windows 不支持 signal handler
    
    except Exception:
        pass  # 忽略信号处理错误
    
    try:
        await stop_event.wait()
    except KeyboardInterrupt:
        print("\nReceived interrupt signal...")
    finally:
        await server.stop()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='AgentMemory Web Server')
    parser.add_argument('--host', default=DEFAULT_HOST)
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    
    print("AgentMemory Web Server v0.3.0")
    try:
        asyncio.run(run_server(args.host, args.port))
    except KeyboardInterrupt:
        print("\nServer stopped")


if __name__ == '__main__':
    main()
