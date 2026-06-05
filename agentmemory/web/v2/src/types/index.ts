// AgentMemory v2.0 类型定义

// ============= 分类与标签 =============
export type CategoryTier = 'A' | 'B' | 'C';

export interface CategoryNode {
  id: string;
  name: string;
  tier: CategoryTier;
  path: string[];  // e.g. ['A.项目', '石榴籽', '语料']
  children?: CategoryNode[];
  memoryCount?: number;
}

// ============= 记忆条目 =============
export type EmbeddingStatus = 'pending' | 'generating' | 'completed' | 'failed' | 'permanent_failure';

export interface MemoryEntry {
  mem_id: string;
  content: string;
  content_summary: string;  // 前100字的摘要
  category: string[];
  tags: string[];
  importance: number;  // 0.0 - 1.0
  embedding_status: EmbeddingStatus;
  created_at: string;
  updated_at: string;
  agent_id?: string;
}

export interface MemoryCreateInput {
  content: string;
  category?: string[];
  tags?: string[];
  importance?: number;
}

export interface MemoryUpdateInput {
  content?: string;
  category?: string[];
  tags?: string[];
  importance?: number;
}

// ============= 检索结果 =============
export type SearchMode = 'hybrid' | 'vector' | 'category' | 'tag';

export interface SearchResult {
  mem_id: string;
  memory: MemoryEntry;
  score: number;  // 0.0 - 1.0 相关性分数
  score_breakdown?: {
    vector_score: number;
    category_score: number;
  };
}

export interface SearchQuery {
  query: string;
  mode: SearchMode;
  limit?: number;
  category?: string[];
  tags?: string[];
  min_score?: number;
}

// ============= 嵌入状态监控 =============
export interface EmbeddingStats {
  total: number;
  pending: number;
  generating: number;
  completed: number;
  failed: number;
  permanent_failure: number;
}

export interface EmbeddingQueueItem {
  mem_id: string;
  memory: MemoryEntry;
  retry_count: number;
  max_retries: number;
  error_message?: string;
  queued_at: string;
}

export interface EmbeddingFailure {
  mem_id: string;
  memory: MemoryEntry;
  error_message: string;
  failed_at: string;
  retry_count: number;
}

// ============= 多 Agent 监控 =============
export interface AgentMetrics {
  agent_id: string;
  name: string;
  is_active: boolean;
  write_rate: number;    // 每分钟写入次数
  read_rate: number;     // 每分钟读取次数
  last_active: string;
}

export interface AppendLogEntry {
  id: string;
  agent_id: string;
  agent_name: string;
  action: 'store' | 'update' | 'delete';
  mem_id: string;
  category: string[];
  timestamp: string;
}

// ============= 统计信息 =============
export interface SystemStats {
  total_memories: number;
  total_categories: number;
  embedding_stats: EmbeddingStats;
  active_agents: number;
  storage_bytes: number;
}

// ============= API 响应 =============
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
  };
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
  has_more: boolean;
}
