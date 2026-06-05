// ============================================
// AgentMemory v2.0 Web Panel - 全局状态管理
// 基于双轨+图书馆数据模型
// ============================================

import { create } from 'zustand';
import type {
  LibraryNode,
  MemoryListItem,
  Agent,
  AppendLog,
  EmbeddingStats,
  EmbeddingTask,
  ViewMode,
  SortConfig,
  FilterConfig,
  SearchMode,
} from '../types';

// ============================================
// 图书馆 Store
// ============================================
interface LibraryState {
  tree: LibraryNode[];
  selectedCategory: string | null;
  expandedNodes: Set<string>;
  isLoading: boolean;
  error: string | null;
  
  // Actions
  setTree: (tree: LibraryNode[]) => void;
  setSelectedCategory: (category: string | null) => void;
  toggleExpanded: (nodeId: string) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useLibraryStore = create<LibraryState>((set) => ({
  tree: [],
  selectedCategory: null,
  expandedNodes: new Set(),
  isLoading: false,
  error: null,

  setTree: (tree) => set({ tree }),
  setSelectedCategory: (category) => set({ selectedCategory: category }),
  toggleExpanded: (nodeId) => set((state) => {
    const newExpanded = new Set(state.expandedNodes);
    if (newExpanded.has(nodeId)) {
      newExpanded.delete(nodeId);
    } else {
      newExpanded.add(nodeId);
    }
    return { expandedNodes: newExpanded };
  }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
}));

// ============================================
// 记忆列表 Store
// ============================================
interface MemoryListState {
  memories: MemoryListItem[];
  total: number;
  viewMode: ViewMode;
  sortConfig: SortConfig;
  filterConfig: FilterConfig;
  isLoading: boolean;
  error: string | null;
  
  // Actions
  setMemories: (memories: MemoryListItem[], total?: number) => void;
  setViewMode: (mode: ViewMode) => void;
  setSortConfig: (config: SortConfig) => void;
  setFilterConfig: (config: FilterConfig) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useMemoryListStore = create<MemoryListState>((set) => ({
  memories: [],
  total: 0,
  viewMode: 'card',
  sortConfig: { field: 'createdAt', direction: 'desc' },
  filterConfig: {},
  isLoading: false,
  error: null,

  setMemories: (memories, total) => set((state) => ({ 
    memories, 
    total: total ?? state.total 
  })),
  setViewMode: (mode) => set({ viewMode: mode }),
  setSortConfig: (config) => set({ sortConfig: config }),
  setFilterConfig: (config) => set({ filterConfig: config }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
}));

// ============================================
// 检索 Store
// ============================================
interface SearchState {
  query: string;
  mode: SearchMode;
  results: MemoryListItem[];
  isSearching: boolean;
  error: string | null;
  
  // Actions
  setQuery: (query: string) => void;
  setMode: (mode: SearchMode) => void;
  setResults: (results: MemoryListItem[]) => void;
  setSearching: (searching: boolean) => void;
  setError: (error: string | null) => void;
  clearResults: () => void;
}

export const useSearchStore = create<SearchState>((set) => ({
  query: '',
  mode: 'hybrid',
  results: [],
  isSearching: false,
  error: null,

  setQuery: (query) => set({ query }),
  setMode: (mode) => set({ mode }),
  setResults: (results) => set({ results }),
  setSearching: (searching) => set({ isSearching: searching }),
  setError: (error) => set({ error }),
  clearResults: () => set({ results: [], query: '' }),
}));

// ============================================
// Agent 监控 Store
// ============================================
interface AgentMonitorState {
  agents: Agent[];
  appendLogs: AppendLog[];
  isConnected: boolean;
  isLoading: boolean;
  error: string | null;
  
  // Actions
  setAgents: (agents: Agent[]) => void;
  addLog: (log: AppendLog) => void;
  setLogs: (logs: AppendLog[]) => void;
  setConnected: (connected: boolean) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useAgentMonitorStore = create<AgentMonitorState>((set) => ({
  agents: [],
  appendLogs: [],
  isConnected: false,
  isLoading: false,
  error: null,

  setAgents: (agents) => set({ agents }),
  addLog: (log) => set((state) => ({
    appendLogs: [log, ...state.appendLogs].slice(0, 200), // 保留最近200条
  })),
  setLogs: (logs) => set({ appendLogs: logs }),
  setConnected: (connected) => set({ isConnected: connected }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
}));

// ============================================
// Embedding 监控 Store
// ============================================
interface EmbeddingMonitorState {
  stats: EmbeddingStats | null;
  tasks: EmbeddingTask[];
  failureSummary: { reason: string; count: number }[];
  isLoading: boolean;
  error: string | null;
  
  // Actions
  setStats: (stats: EmbeddingStats) => void;
  setTasks: (tasks: EmbeddingTask[]) => void;
  addTask: (task: EmbeddingTask) => void;
  updateTask: (taskId: string, updates: Partial<EmbeddingTask>) => void;
  setFailureSummary: (summary: { reason: string; count: number }[]) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useEmbeddingMonitorStore = create<EmbeddingMonitorState>((set) => ({
  stats: null,
  tasks: [],
  failureSummary: [],
  isLoading: false,
  error: null,

  setStats: (stats) => set({ stats }),
  setTasks: (tasks) => set({ tasks }),
  addTask: (task) => set((state) => ({ tasks: [task, ...state.tasks] })),
  updateTask: (taskId, updates) => set((state) => ({
    tasks: state.tasks.map((t) => (t.id === taskId ? { ...t, ...updates } : t)),
  })),
  setFailureSummary: (summary) => set({ failureSummary: summary }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
}));

// ============================================
// UI Store
// ============================================
interface UIState {
  sidebarCollapsed: boolean;
  activeView: 'library' | 'memory' | 'search' | 'agents' | 'embedding';
  
  // Actions
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setActiveView: (view: UIState['activeView']) => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarCollapsed: false,
  activeView: 'library',

  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
  setActiveView: (view) => set({ activeView: view }),
}));
