// ============================================
// AgentMemory v2.0 Web Panel - 类型定义
// 基于双轨+图书馆数据模型
// ============================================

// 图书馆分类节点
export interface LibraryNode {
  id: string;
  name: string;
  path: string;           // 完整路径: "A.项目/石榴籽/语料"
  type: 'project' | 'personal' | 'knowledge' | 'folder';
  parentId: string | null;
  children?: LibraryNode[];
  memoryCount: number;
  childrenCount: number;
}

// 记忆条目
export interface Memory {
  id: string;
  content: string;        // 原始内容
  summary?: string;       // AI 生成的摘要
  path: string;            // 文件路径
  category: string;       // 所属分类
  tags: string[];
  importance: 1 | 2 | 3 | 4 | 5;  // 重要性等级
  embeddingStatus: EmbeddingStatus;
  relevanceScore?: number;  // 搜索相关性分数
  createdAt: string;
  updatedAt: string;
}

// Embedding 状态
export type EmbeddingStatus = 
  | 'pending'        // 等待处理
  | 'generating'     // 生成中
  | 'completed'      // 完成
  | 'failed'         // 失败（可重试）
  | 'permanent_failure'; // 永久失败

// Embedding 任务
export interface EmbeddingTask {
  id: string;
  memoryId: string;
  status: EmbeddingStatus;
  retryCount: number;
  maxRetries: number;
  errorMessage?: string;
  createdAt: string;
  completedAt?: string;
}

// Agent 信息
export interface Agent {
  id: string;
  name: string;
  status: 'active' | 'idle' | 'offline';
  writeRate: number;      // 写入速率 (条/分钟)
  readRate: number;       // 读取速率 (条/分钟)
  lastActivity: string;
}

// Append 日志条目
export interface AppendLog {
  id: string;
  agentId: string;
  agentName: string;
  operation: 'write' | 'read' | 'search' | 'delete';
  memoryId?: string;
  content?: string;
  timestamp: string;
}

// 检索结果
export interface SearchResult {
  memory: Memory;
  semanticScore?: number;   // 语义相似度
  categoryScore?: number;   // 分类匹配度
  hybridScore?: number;     // 综合分数
  matchedTags?: string[];
}

// 检索模式
export type SearchMode = 'semantic' | 'category' | 'hybrid';

// 检索请求
export interface SearchRequest {
  query: string;
  mode: SearchMode;
  categoryFilter?: string;
  tagFilter?: string[];
  limit?: number;
  offset?: number;
}

// 嵌入状态统计
export interface EmbeddingStats {
  total: number;
  pending: number;
  generating: number;
  completed: number;
  failed: number;
  permanentFailure: number;
}

// 记忆列表项（简化版，用于列表展示）
export interface MemoryListItem {
  id: string;
  summary: string;
  category: string;
  tags: string[];
  importance: number;
  embeddingStatus: EmbeddingStatus;
  createdAt: string;
}

// 视图模式
export type ViewMode = 'card' | 'list';

// 排序字段
export type SortField = 'createdAt' | 'updatedAt' | 'importance' | 'relevance';

// 排序方向
export type SortDirection = 'asc' | 'desc';

// 排序配置
export interface SortConfig {
  field: SortField;
  direction: SortDirection;
}

// 筛选配置
export interface FilterConfig {
  tags?: string[];
  importance?: number[];
  embeddingStatus?: EmbeddingStatus[];
  dateRange?: {
    start: string;
    end: string;
  };
}

// 分类白名单项
export interface CategoryWhitelist {
  categories: string[];
  lastUpdated: string;
}
