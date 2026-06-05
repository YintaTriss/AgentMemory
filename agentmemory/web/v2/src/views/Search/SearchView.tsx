import { useState, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { searchApi, memoryApi } from '@/api/client';
import { useLibraryStore } from '@/stores/appStore';
import {
  cn,
  formatDate,
  truncateText,
  getEmbeddingStatusColor,
  getEmbeddingStatusLabel,
} from '@/lib/utils';
import {
  Search,
  Loader2,
  Sparkles,
  FolderTree,
  GitMerge,
  BarChart3,
  Clock,
  ChevronRight,
  ChevronDown,
  FileText,
  ExternalLink,
} from 'lucide-react';
import type { SearchResult, SearchMode, CategoryNode } from '@/types';

type ViewMode = 'semantic' | 'category' | 'hybrid';

interface CategorySearchResult {
  category: string[];
  memoryCount: number;
  memories: SearchResult[];
}

export function SearchView() {
  const [query, setQuery] = useState('');
  const [viewMode, setViewMode] = useState<ViewMode>('hybrid');
  const [selectedCategory, setSelectedCategory] = useState<string[] | null>(null);
  const [hybridResults, setHybridResults] = useState<SearchResult[]>([]);
  const [categoryResults, setCategoryResults] = useState<CategorySearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const { categories } = useLibraryStore();

  const searchMutation = useMutation({
    mutationFn: async (params: { query: string; mode: SearchMode; category?: string[] }) => {
      return searchApi.search({
        query: params.query,
        mode: params.mode,
        limit: 20,
        category: params.category,
      });
    },
  });

  const handleSearch = async () => {
    if (!query.trim()) return;

    setIsSearching(true);
    try {
      if (viewMode === 'semantic' || viewMode === 'hybrid') {
        const mode: SearchMode = viewMode === 'hybrid' ? 'hybrid' : 'vector';
        const results = await searchMutation.mutateAsync({ query, mode });
        setHybridResults(results);
      }

      if (viewMode === 'category' || viewMode === 'hybrid') {
        // 分类检索：查找包含查询词的分类
        const categoryResults: CategorySearchResult[] = [];

        const searchInCategories = async (nodes: CategoryNode[], path: string[]) => {
          for (const node of nodes) {
            const currentPath = [...path, node.name];
            const isMatch = node.name.toLowerCase().includes(query.toLowerCase());

            if (isMatch) {
              // 获取该分类下的记忆
              try {
                const memories = await memoryApi.list({
                  category: currentPath,
                  limit: 50,
                });
                if (memories.items.length > 0) {
                  categoryResults.push({
                    category: currentPath,
                    memoryCount: memories.total,
                    memories: memories.items.map((m) => ({
                      mem_id: m.mem_id,
                      memory: m,
                      score: 1.0,
                    })),
                  });
                }
              } catch {
                // 忽略错误
              }
            }

            if (node.children) {
              await searchInCategories(node.children, currentPath);
            }
          }
        };

        await searchInCategories(categories, []);
        setCategoryResults(categoryResults);
      }
    } finally {
      setIsSearching(false);
    }
  };

  useEffect(() => {
    const debounce = setTimeout(() => {
      if (query.trim()) {
        handleSearch();
      }
    }, 300);

    return () => clearTimeout(debounce);
  }, [query, viewMode]);

  return (
    <div className="flex flex-col h-full">
      {/* 头部 */}
      <header className="px-6 py-4 border-b border-border bg-card">
        <h1 className="text-2xl font-bold">检索</h1>
        <p className="text-sm text-muted-foreground mt-1">
          双轨检索：语义向量 + 分类树形检索
        </p>
      </header>

      {/* 搜索栏 */}
      <div className="px-6 py-4 border-b border-border bg-background">
        <div className="flex items-center gap-4">
          {/* 搜索输入 */}
          <div className="relative flex-1">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
            <input
              type="text"
              placeholder="输入关键词搜索记忆..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full pl-12 pr-4 py-3 text-lg bg-card border border-input rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
            />
            {isSearching && (
              <Loader2 className="absolute right-4 top-1/2 -translate-y-1/2 h-5 w-5 animate-spin text-primary" />
            )}
          </div>

          {/* 搜索模式切换 */}
          <div className="flex items-center gap-1 p-1 bg-muted rounded-lg">
            <button
              onClick={() => setViewMode('semantic')}
              className={cn(
                'flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors',
                viewMode === 'semantic'
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              <Sparkles className="h-4 w-4" />
              语义
            </button>
            <button
              onClick={() => setViewMode('category')}
              className={cn(
                'flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors',
                viewMode === 'category'
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              <FolderTree className="h-4 w-4" />
              分类
            </button>
            <button
              onClick={() => setViewMode('hybrid')}
              className={cn(
                'flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors',
                viewMode === 'hybrid'
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              <GitMerge className="h-4 w-4" />
              混合
            </button>
          </div>
        </div>
      </div>

      {/* 结果区域 */}
      <div className="flex-1 overflow-auto p-6">
        {!query.trim() ? (
          <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
            <Search className="h-16 w-16 mb-4 opacity-30" />
            <p className="text-lg font-medium">开始检索</p>
            <p className="text-sm mt-1">输入关键词或选择分类查看记忆</p>
          </div>
        ) : isSearching ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <span className="ml-3 text-muted-foreground">检索中...</span>
          </div>
        ) : (
          <div className="space-y-6">
            {/* 语义检索结果 */}
            {(viewMode === 'semantic' || viewMode === 'hybrid') && (
              <div>
                <div className="flex items-center gap-2 mb-4">
                  <Sparkles className="h-5 w-5 text-primary" />
                  <h2 className="text-lg font-semibold">语义检索结果</h2>
                  <span className="text-sm text-muted-foreground">
                    ({hybridResults.length} 条)
                  </span>
                </div>

                {hybridResults.length === 0 ? (
                  <div className="p-8 text-center text-muted-foreground bg-muted/50 rounded-xl">
                    <p>未找到相关记忆</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {hybridResults.map((result) => (
                      <SearchResultCard
                        key={result.mem_id}
                        result={result}
                        showScore
                      />
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* 分类检索结果 */}
            {(viewMode === 'category' || viewMode === 'hybrid') && (
              <div>
                <div className="flex items-center gap-2 mb-4">
                  <FolderTree className="h-5 w-5 text-primary" />
                  <h2 className="text-lg font-semibold">分类检索结果</h2>
                  <span className="text-sm text-muted-foreground">
                    ({categoryResults.length} 个分类)
                  </span>
                </div>

                {categoryResults.length === 0 ? (
                  <div className="p-8 text-center text-muted-foreground bg-muted/50 rounded-xl">
                    <p>未找到匹配分类</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {categoryResults.map((cr, index) => (
                      <div
                        key={index}
                        className="bg-card border border-border rounded-xl overflow-hidden"
                      >
                        <div className="px-4 py-3 bg-muted/50 border-b border-border flex items-center gap-2">
                          <FolderTree className="h-4 w-4 text-primary" />
                          <span className="font-medium">
                            {cr.category.join(' / ')}
                          </span>
                          <span className="text-sm text-muted-foreground">
                            ({cr.memoryCount} 条记忆)
                          </span>
                        </div>
                        <div className="divide-y divide-border">
                          {cr.memories.slice(0, 5).map((result) => (
                            <SearchResultCard
                              key={result.mem_id}
                              result={result}
                              compact
                            />
                          ))}
                          {cr.memoryCount > 5 && (
                            <div className="px-4 py-2 text-center">
                              <button className="text-sm text-primary hover:underline">
                                查看全部 {cr.memoryCount} 条
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

interface SearchResultCardProps {
  result: SearchResult;
  showScore?: boolean;
  compact?: boolean;
}

function SearchResultCard({ result, showScore, compact }: SearchResultCardProps) {
  const { memory, score, score_breakdown } = result;

  if (compact) {
    return (
      <div className="px-4 py-3 hover:bg-muted/50 transition-colors flex items-start gap-3">
        <FileText className="h-4 w-4 text-muted-foreground mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="text-sm text-foreground line-clamp-2">
            {truncateText(memory.content, 100)}
          </p>
          <div className="flex items-center gap-2 mt-1">
            {memory.category.slice(0, 2).map((cat, i) => (
              <span
                key={i}
                className="px-1.5 py-0.5 text-xs bg-primary/10 text-primary rounded"
              >
                {cat}
              </span>
            ))}
          </div>
        </div>
        <ExternalLink className="h-4 w-4 text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="bg-card border border-border rounded-xl p-4 hover:shadow-md transition-shadow">
      {/* 分类标签 */}
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        {memory.category.map((cat, i) => (
          <span
            key={i}
            className="px-2 py-0.5 text-xs font-medium bg-primary/10 text-primary rounded"
          >
            {cat}
          </span>
        ))}
      </div>

      {/* 内容 */}
      <p className="text-sm text-foreground line-clamp-3 mb-3">
        {memory.content_summary || truncateText(memory.content, 200)}
      </p>

      {/* 底部信息 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          {/* 创建时间 */}
          <div className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {formatDate(memory.created_at)}
          </div>

          {/* 标签 */}
          {memory.tags.length > 0 && (
            <div className="flex items-center gap-1">
              {memory.tags.slice(0, 3).map((tag, i) => (
                <span
                  key={i}
                  className="px-1 py-0.5 text-xs bg-muted rounded"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* 分数 */}
        {showScore && (
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1 text-xs">
              <BarChart3 className="h-3 w-3 text-primary" />
              <span className="font-medium text-primary">
                {Math.round(score * 100)}%
              </span>
            </div>
            {score_breakdown && (
              <div className="text-xs text-muted-foreground flex items-center gap-1">
                <span title="向量分数">{Math.round(score_breakdown.vector_score * 100)}%</span>
                <span>/</span>
                <span title="分类分数">{Math.round(score_breakdown.category_score * 100)}%</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default SearchView;
