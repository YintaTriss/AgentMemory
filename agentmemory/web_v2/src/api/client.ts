// ============================================
// AgentMemory v2.0 Web Panel - API 客户端
// 基于双轨+图书馆数据模型
// ============================================

import axios, { AxiosInstance } from 'axios';
import type {
  LibraryNode,
  Memory,
  MemoryListItem,
  SearchRequest,
  SearchResult,
  Agent,
  AppendLog,
  EmbeddingTask,
  EmbeddingStats,
  CategoryWhitelist,
} from '../types';

// API 基础路径
const API_BASE = '/api/v1';

// 创建 axios 实例
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    // 可以在这里添加认证 token
    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

// ============================================
// 图书馆 API
// ============================================
export const libraryApi = {
  // 获取图书馆结构树
  getTree: async (): Promise<LibraryNode[]> => {
    const { data } = await apiClient.get('/library/tree');
    return data;
  },

  // 获取指定分类下的记忆列表
  getMemories: async (categoryPath: string, params?: {
    limit?: number;
    offset?: number;
  }): Promise<{ items: MemoryListItem[]; total: number }> => {
    const { data } = await apiClient.get(`/library/${encodeURIComponent(categoryPath)}/memories`, { params });
    return data;
  },

  // 获取分类白名单
  getWhitelist: async (): Promise<CategoryWhitelist> => {
    const { data } = await apiClient.get('/library/whitelist');
    return data;
  },
};

// ============================================
// 记忆 API
// ============================================
export const memoryApi = {
  // 获取记忆详情
  getById: async (id: string): Promise<Memory> => {
    const { data } = await apiClient.get(`/memories/${id}`);
    return data;
  },

  // 更新记忆
  update: async (id: string, updates: Partial<Memory>): Promise<Memory> => {
    const { data } = await apiClient.put(`/memories/${id}`, updates);
    return data;
  },

  // 删除记忆
  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/memories/${id}`);
  },

  // 移动记忆到其他分类
  move: async (id: string, newCategory: string): Promise<Memory> => {
    const { data } = await apiClient.post(`/memories/${id}/move`, { category: newCategory });
    return data;
  },
};

// ============================================
// 检索 API（双轨系统）
// ============================================
export const searchApi = {
  // 执行检索
  search: async (request: SearchRequest): Promise<SearchResult[]> => {
    const { data } = await apiClient.post('/search', request);
    return data;
  },

  // 语义检索（向量轨）
  semantic: async (query: string, limit = 20): Promise<SearchResult[]> => {
    const { data } = await apiClient.post('/search/semantic', { query, limit });
    return data;
  },

  // 分类检索（图书馆轨）
  category: async (categoryPath: string, limit = 20): Promise<Memory[]> => {
    const { data } = await apiClient.get(`/search/category/${encodeURIComponent(categoryPath)}`, {
      params: { limit },
    });
    return data;
  },

  // 混合检索
  hybrid: async (query: string, categoryPath?: string, limit = 20): Promise<SearchResult[]> => {
    const { data } = await apiClient.post('/search/hybrid', { query, categoryPath, limit });
    return data;
  },
};

// ============================================
// Agent 监控 API
// ============================================
export const agentApi = {
  // 获取所有 Agent
  list: async (): Promise<Agent[]> => {
    const { data } = await apiClient.get('/agents');
    return data;
  },

  // 获取单个 Agent 详情
  getById: async (id: string): Promise<Agent> => {
    const { data } = await apiClient.get(`/agents/${id}`);
    return data;
  },

  // 获取 Agent 的活动日志
  getLogs: async (agentId: string, limit = 100): Promise<AppendLog[]> => {
    const { data } = await apiClient.get(`/agents/${agentId}/logs`, { params: { limit } });
    return data;
  },
};

// ============================================
// Append 日志 API（实时）
// ============================================
export const appendLogApi = {
  // 获取最近的 Append 日志
  getRecent: async (limit = 50): Promise<AppendLog[]> => {
    const { data } = await apiClient.get('/logs/append', { params: { limit } });
    return data;
  },

  // 监听实时日志 (SSE)
  subscribe: (onMessage: (log: AppendLog) => void, onError?: (error: Error) => void): (() => void) => {
    const eventSource = new EventSource(`${API_BASE}/logs/append/stream`);
    
    eventSource.onmessage = (event) => {
      try {
        const log = JSON.parse(event.data) as AppendLog;
        onMessage(log);
      } catch (e) {
        console.error('Failed to parse SSE message:', e);
      }
    };

    eventSource.onerror = () => {
      onError?.(new Error('SSE connection error'));
      eventSource.close();
    };

    return () => eventSource.close();
  },
};

// ============================================
// Embedding 监控 API
// ============================================
export const embeddingApi = {
  // 获取 Embedding 统计
  getStats: async (): Promise<EmbeddingStats> => {
    const { data } = await apiClient.get('/embeddings/stats');
    return data;
  },

  // 获取 Embedding 任务列表
  getTasks: async (params?: {
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ items: EmbeddingTask[]; total: number }> => {
    const { data } = await apiClient.get('/embeddings/tasks', { params });
    return data;
  },

  // 重试失败的 Embedding 任务
  retry: async (taskId: string): Promise<EmbeddingTask> => {
    const { data } = await apiClient.post(`/embeddings/tasks/${taskId}/retry`);
    return data;
  },

  // 批量重试
  retryBatch: async (taskIds: string[]): Promise<{ retried: number }> => {
    const { data } = await apiClient.post('/embeddings/tasks/retry-batch', { taskIds });
    return data;
  },

  // 获取失败原因汇总
  getFailureSummary: async (): Promise<{ reason: string; count: number }[]> => {
    const { data } = await apiClient.get('/embeddings/failures');
    return data;
  },
};

// 导出默认 API 客户端
export default apiClient;
