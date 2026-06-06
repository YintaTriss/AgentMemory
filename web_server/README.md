# AgentMemory Web Server

轻量级 REST API 服务，为 AgentMemory 四层闭环记忆系统提供 HTTP 接口。

## 快速开始

### 1. 安装依赖

```bash
cd web_server
pip install -r requirements.txt
```

### 2. 启动服务器

```bash
python -m web_server
# 或
python web_server/app.py
```

默认端口: **8765**

### 3. 访问

- Web界面: http://localhost:8765/
- API文档: http://localhost:8765/api/health

---

## API 端点

### 健康检查

```bash
curl http://localhost:8765/api/health
```

### 统计信息

```bash
curl http://localhost:8765/api/stats
```

### 创建记忆

```bash
curl -X POST http://localhost:8765/api/memories \
  -H "Content-Type: application/json" \
  -d '{
    "content": "测试记忆内容",
    "importance": 0.8,
    "category_path": "测试/单元测试",
    "tags": ["test", "api"]
  }'
```

### 列出记忆

```bash
# 所有记忆（最多20条）
curl http://localhost:8765/api/memories

# 指定分类
curl "http://localhost:8765/api/memories?category=测试&limit=10"
```

### 获取单条记忆

```bash
curl http://localhost:8765/api/memories/<memory_id>
```

### 删除记忆

```bash
curl -X DELETE http://localhost:8765/api/memories/<memory_id>
```

### 语义搜索

```bash
curl "http://localhost:8765/api/search?q=测试&limit=5"
```

### 获取所有分类

```bash
curl http://localhost:8765/api/categories
```

### 触发全量同步

```bash
curl -X POST http://localhost:8765/api/sync
```

### 压缩摘要

```bash
curl -X POST http://localhost:8765/api/compress \
  -H "Content-Type: application/json" \
  -d '{"ids": ["mem_xxx", "mem_yyy"]}'
```

---

## API 响应格式

### 成功响应

```json
{
  "status": "ok",
  "data": {...}
}
```

### 错误响应

```json
{
  "status": "error",
  "error": "错误信息"
}
```

---

## 运行测试

```bash
bash web_server/test_api.sh
```

---

## 配置

环境变量:
- `DASHSCOPE_API_KEY` - 通义千问 API Key（可选）
- `BAILIAN_API_KEY` - 百炼 API Key（可选）

---

## 项目结构

```
web_server/
├── __init__.py      # 包标识
├── app.py           # 主应用入口
├── handlers.py      # 路由处理函数
├── models.py        # 数据模型
├── static/
│   └── index.html   # Web界面
├── requirements.txt # 依赖
├── README.md        # 本文档
└── test_api.sh      # 测试脚本
```

---

## 许可证

MIT License
