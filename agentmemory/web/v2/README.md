# AgentMemory v2.0 Web 面板

> 基于双轨 + 图书馆数据模型的 Web 看板

## 功能特性

### 5 个核心视图

1. **图书馆视图 (Library Tree)**
   - 树形展示 A.项目 / B.个人 / C.知识分类
   - 点击分类显示该分类下的记忆列表
   - 支持搜索/筛选/排序

2. **记忆列表 (Memory List)**
   - 卡片/列表双视图
   - 显示：内容摘要、分类、tag、重要性、embedding 状态、创建时间
   - 支持编辑/删除/移动分类

3. **检索视图 (Search)**
   - 双轨检索：语义检索（向量）+ 分类检索（树形）
   - 支持 hybrid 混合模式
   - 实时显示相关性分数

4. **多 Agent 监控 (Multi-Agent Monitor)**
   - 当前活跃 Agent 列表
   - 各 Agent 的写入速率 / 读取速率
   - Append 日志实时滚动（SSE）

5. **嵌入状态监控 (Embedding Status)**
   - pending / generating / completed / failed / permanent_failure 状态分布
   - 重试队列
   - 失败原因汇总
   - 支持手动重试

## 技术栈

- **框架**: React 18 + TypeScript
- **构建**: Vite
- **UI 组件**: Tailwind CSS + 自定义组件
- **状态管理**: Zustand
- **数据获取**: TanStack Query (React Query)
- **HTTP 客户端**: Axios
- **图表**: Recharts
- **图标**: Lucide React
- **路由**: React Router v6

## 快速开始

### 安装依赖

```bash
cd agentmemory/web/v2
npm install
```

### 开发模式

```bash
npm run dev
```

访问 http://localhost:3000

### 构建生产版本

```bash
npm run build
```

构建产物在 `dist/` 目录，可由 FastAPI 静态托管。

### 预览生产构建

```bash
npm run preview
```

## 项目结构

```
agentmemory/web/v2/
├── src/
│   ├── api/               # API 客户端
│   │   └── client.ts      # 所有 API 调用
│   ├── components/        # 共享组件
│   │   └── layout/         # 布局组件
│   │       └── AppLayout.tsx
│   ├── lib/               # 工具函数
│   │   └── utils.ts       # cn(), formatDate() 等
│   ├── stores/            # Zustand 状态管理
│   │   └── appStore.ts    # 全局状态
│   ├── types/             # TypeScript 类型定义
│   │   └── index.ts       # 所有类型
│   ├── views/             # 5 个核心视图
│   │   ├── LibraryTree/   # 图书馆视图
│   │   ├── MemoryList/   # 记忆列表
│   │   ├── Search/       # 检索视图
│   │   ├── MultiAgentMonitor/  # 多 Agent 监控
│   │   └── EmbeddingStatus/    # 嵌入状态监控
│   ├── App.tsx           # 主应用组件
│   ├── main.tsx          # 入口文件
│   └── index.css         # 全局样式
├── index.html
├── package.json
├── tailwind.config.js
├── tsconfig.json
└── vite.config.ts
```

## API 契约

详见 `../../../_inputs/api-contract.md`

### 主要端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/v2/memories` | GET/POST | 列出/创建记忆 |
| `/v2/memories/:id` | GET/PATCH/DELETE | 读取/更新/删除记忆 |
| `/v2/search` | POST | 双轨检索 |
| `/v2/library/tree` | GET | 获取分类树 |
| `/v2/embeddings/stats` | GET | 嵌入统计 |
| `/v2/embeddings/retry-queue` | GET | 重试队列 |
| `/v2/embeddings/failures` | GET | 失败列表 |
| `/v2/agents/active` | GET | 活跃 Agent |
| `/v2/agents/append-logs` | GET | Append 日志 |
| `/v2/agents/append-logs/stream` | SSE | 实时日志流 |

## 硬性约束

- ✅ 全部中文 UI
- ✅ 响应式布局（桌面 + 平板）
- ✅ 现代化（无 jQuery）
- ✅ 真实 API 调用（无 mock 数据）
- ✅ TypeScript 类型安全

## 开发说明

### 环境变量

```env
VITE_API_BASE_URL=/api/v2  # API 基础路径（默认）
```

### 状态管理

使用 Zustand 管理全局状态：
- `useAppStore`: 应用状态（选中的分类、视图模式等）
- `useLibraryStore`: 图书馆状态（分类树、展开状态等）
- `useEmbeddingStore`: 嵌入状态（统计、重试队列等）
- `useAgentStore`: Agent 状态（活跃列表、日志等）

### 数据获取

使用 TanStack Query 管理服务端状态：
- 自动缓存
- 后台刷新
- 乐观更新
- 错误重试

## License

MIT
