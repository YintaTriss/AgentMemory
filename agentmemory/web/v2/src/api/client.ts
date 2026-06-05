import axios from 'axios';
import type {
  MemoryEntry,
  MemoryCreateInput,
  MemoryUpdateInput,
  SearchQuery,
  SearchResult,
  CategoryNode,
  SystemStats,
  EmbeddingStats,
  EmbeddingQueueItem,
  EmbeddingFailure,
  AgentMetrics,
  AppendLogEntry,
  PaginatedResponse,
} from '@/types';

const api = axios.create({
  baseURL: '/api/v2',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ============= 记忆管理 =============
export const memoryApi = {
  // 创建记忆
  async create(input: MemoryCreateInput): Promise<MemoryEntry> {
    const response = await api.post('/memories', input);
    return response.data.data;
  },

  // 读取记忆
  async get(memId: string): Promise<MemoryEntry> {
    const response = await api.get(`/memories/${memId}`);
    return response.data.data;
  },

  // 更新记忆
  async update(memId: string, input: MemoryUpdateInput): Promise<MemoryEntry> {
    const response = await api.patch(`/memories/${memId}`, input);
    return response.data.data;
  },

  // 删除记忆
  async delete(memId: string): Promise<void> {
    await api.delete(`/memories/${memId}`);
  },

  // 列出记忆
  async list(params: {
    category?: string[];
    since?: string;
    until?: string;
    limit?: number;
    offset?: number;
  }): Promise<PaginatedResponse<MemoryEntry>> {
    const response = await api.get('/memories', { params });
    return response.data.data;
  },

  // 移动记忆到新分类
  async move(memId: string, newCategory: string[]): Promise<MemoryEntry> {
    const response = await api.post(`/memories/${memId}/move`, { category: newCategory });
    return response.data.data;
  },
};

// ============= 检索 =============
export const searchApi = {
  // 双轨检索
  async search(query: SearchQuery): Promise<SearchResult[]> {
    const response = await api.post('/search', query);
    return response.data.data;
  },

  // 预取
  async prefetch(query: string, limit: number = 5): Promise<SearchResult[]> {
    const response = await api.post('/search/prefetch', { query, limit });
    return response.data.data;
  },
};

// ============= 图书馆分类 =============
export const libraryApi = {
  // 获取分类树
  async getTree(): Promise<CategoryNode[]> {
    const response = await api.get('/library/tree');
    return response.data.data;
  },

  // 获取分类下的记忆数
  async getCategoryStats(categoryPath: string[]): Promise<{ memoryCount: number }> {
    const response = await api.get(`/library/stats`, {
      params: { category: categoryPath.join('/') },
    });
    return response.data.data;
  },
};

// ============= 嵌入状态监控 =============
export const embeddingApi = {
  // 获取嵌入统计
  async getStats(): Promise<EmbeddingStats> {
    const response = await api.get('/embeddings/stats');
    return response.data.data;
  },

  // 获取重试队列
  async getRetryQueue(): Promise<EmbeddingQueueItem[]> {
    const response = await api.get('/embeddings/retry-queue');
    return response.data.data;
  },

  // 获取失败列表
  async getFailures(): Promise<EmbeddingFailure[]> {
    const response = await api.get('/embeddings/failures');
    return response.data.data;
  },

  // 手动重试
  async retry(memId: string): Promise<void> {
    await api.post(`/embeddings/${memId}/retry`);
  },

  // 批量重试
  async retryBatch(memIds: string[]): Promise<{ succeeded: number; failed: number }> {
    const response = await api.post('/embeddings/retry-batch', { mem_ids: memIds });
    return response.data.data;
  },
};

// ============= 多 Agent 监控 =============
export const agentApi = {
  // 获取活跃 Agent 列表
  async getActiveAgents(): Promise<AgentMetrics[]> {
    const response = await api.get('/agents/active');
    return response.data.data;
  },

  // 获取 Agent 的读写速率
  async getAgentMetrics(agentId: string): Promise<AgentMetrics> {
    const response = await api.get(`/agents/${agentId}/metrics`);
    return response.data.data;
  },

  // 获取 Append 日志
  async getAppendLogs(params: {
    since?: string;
    limit?: number;
  }): Promise<AppendLogEntry[]> {
    const response = await api.get('/agents/append-logs', { params });
    return response.data.data;
  },

  // 订阅实时日志 (SSE)
  subscribeAppendLogs(callback: (entry: AppendLogEntry) => void): () => void {
    const eventSource = new EventSource('/api/v2/agents/append-logs/stream');
    
    eventSource.onmessage = (event) => {
      const entry = JSON.parse(event.data) as AppendLogEntry;
      callback(entry);
    };

    eventSource.onerror = () => {
      console.error('SSE connection error');
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  },
};

// ============= 系统统计 =============
export const statsApi = {
  async get(): Promise<SystemStats> {
    const response = await api.get('/stats');
    return response.data.data;
  },
};

export default api;
