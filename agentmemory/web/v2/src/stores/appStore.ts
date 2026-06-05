import { create } from 'zustand';
import type { CategoryNode, MemoryEntry, EmbeddingStats, AgentMetrics, AppendLogEntry } from '@/types';

interface AppState {
  // 当前选中的分类路径
  selectedCategory: string[] | null;
  setSelectedCategory: (category: string[] | null) => void;

  // 记忆列表视图模式
  viewMode: 'card' | 'list';
  setViewMode: (mode: 'card' | 'list') => void;

  // 搜索关键词
  searchQuery: string;
  setSearchQuery: (query: string) => void;

  // 排序方式
  sortBy: 'created_at' | 'importance' | 'updated_at';
  setSortBy: (sort: 'created_at' | 'importance' | 'updated_at') => void;

  // 排序方向
  sortOrder: 'asc' | 'desc';
  setSortOrder: (order: 'asc' | 'desc') => void;

  // 侧边栏折叠状态
  sidebarCollapsed: boolean;
  setSidebarCollapsed: (collapsed: boolean) => void;

  // 当前选中的记忆
  selectedMemory: MemoryEntry | null;
  setSelectedMemory: (memory: MemoryEntry | null) => void;

  // 模态框状态
  isCreateModalOpen: boolean;
  setCreateModalOpen: (open: boolean) => void;
  isEditModalOpen: boolean;
  setEditModalOpen: (open: boolean) => void;
  isDeleteConfirmOpen: boolean;
  setDeleteConfirmOpen: (open: boolean) => void;
  memoryToDelete: string | null;
  setMemoryToDelete: (memId: string | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  selectedCategory: null,
  setSelectedCategory: (category) => set({ selectedCategory: category }),

  viewMode: 'card',
  setViewMode: (mode) => set({ viewMode: mode }),

  searchQuery: '',
  setSearchQuery: (query) => set({ searchQuery: query }),

  sortBy: 'created_at',
  setSortBy: (sort) => set({ sortBy: sort }),

  sortOrder: 'desc',
  setSortOrder: (order) => set({ sortOrder: order }),

  sidebarCollapsed: false,
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),

  selectedMemory: null,
  setSelectedMemory: (memory) => set({ selectedMemory: memory }),

  isCreateModalOpen: false,
  setCreateModalOpen: (open) => set({ isCreateModalOpen: open }),
  isEditModalOpen: false,
  setEditModalOpen: (open) => set({ isEditModalOpen: open }),
  isDeleteConfirmOpen: false,
  setDeleteConfirmOpen: (open) => set({ isDeleteConfirmOpen: open }),
  memoryToDelete: null,
  setMemoryToDelete: (memId) => set({ memoryToDelete: memId }),
}));

// ============= 图书馆 Store =============
interface LibraryState {
  categories: CategoryNode[];
  setCategories: (categories: CategoryNode[]) => void;
  expandedNodes: Set<string>;
  toggleNode: (nodeId: string) => void;
  expandNode: (nodeId: string) => void;
  collapseNode: (nodeId: string) => void;
  isLoading: boolean;
  setLoading: (loading: boolean) => void;
  error: string | null;
  setError: (error: string | null) => void;
}

export const useLibraryStore = create<LibraryState>((set) => ({
  categories: [],
  setCategories: (categories) => set({ categories }),

  expandedNodes: new Set(),
  toggleNode: (nodeId) =>
    set((state) => {
      const newSet = new Set(state.expandedNodes);
      if (newSet.has(nodeId)) {
        newSet.delete(nodeId);
      } else {
        newSet.add(nodeId);
      }
      return { expandedNodes: newSet };
    }),
  expandNode: (nodeId) =>
    set((state) => {
      const newSet = new Set(state.expandedNodes);
      newSet.add(nodeId);
      return { expandedNodes: newSet };
    }),
  collapseNode: (nodeId) =>
    set((state) => {
      const newSet = new Set(state.expandedNodes);
      newSet.delete(nodeId);
      return { expandedNodes: newSet };
    }),

  isLoading: false,
  setLoading: (loading) => set({ isLoading: loading }),
  error: null,
  setError: (error) => set({ error }),
}));

// ============= 嵌入状态 Store =============
interface EmbeddingState {
  stats: EmbeddingStats | null;
  setStats: (stats: EmbeddingStats) => void;
  retryQueue: EmbeddingQueueItem[];
  setRetryQueue: (queue: EmbeddingQueueItem[]) => void;
  failures: EmbeddingFailure[];
  setFailures: (failures: EmbeddingFailure[]) => void;
  isLoading: boolean;
  setLoading: (loading: boolean) => void;
  autoRefresh: boolean;
  setAutoRefresh: (auto: boolean) => void;
}

export const useEmbeddingStore = create<EmbeddingState>((set) => ({
  stats: null,
  setStats: (stats) => set({ stats }),
  retryQueue: [],
  setRetryQueue: (queue) => set({ retryQueue: queue }),
  failures: [],
  setFailures: (failures) => set({ failures }),
  isLoading: false,
  setLoading: (loading) => set({ isLoading: loading }),
  autoRefresh: true,
  setAutoRefresh: (auto) => set({ autoRefresh: auto }),
}));

// ============= Agent 监控 Store =============
interface AgentState {
  agents: AgentMetrics[];
  setAgents: (agents: AgentMetrics[]) => void;
  appendLogs: AppendLogEntry[];
  addAppendLog: (log: AppendLogEntry) => void;
  clearLogs: () => void;
  isConnected: boolean;
  setConnected: (connected: boolean) => void;
}

export const useAgentStore = create<AgentState>((set) => ({
  agents: [],
  setAgents: (agents) => set({ agents }),
  appendLogs: [],
  addAppendLog: (log) =>
    set((state) => ({
      appendLogs: [log, ...state.appendLogs].slice(0, 500), // 最多保留500条
    })),
  clearLogs: () => set({ appendLogs: [] }),
  isConnected: false,
  setConnected: (connected) => set({ isConnected: connected }),
}));

import type { EmbeddingQueueItem, EmbeddingFailure } from '@/types';
