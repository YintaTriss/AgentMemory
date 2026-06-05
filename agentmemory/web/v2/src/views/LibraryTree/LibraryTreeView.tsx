import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { libraryApi } from '@/api/client';
import { useLibraryStore, useAppStore } from '@/stores/appStore';
import { cn, getCategoryTierColor, getCategoryTierLabel } from '@/lib/utils';
import {
  ChevronRight,
  ChevronDown,
  Folder,
  FolderOpen,
  Search,
  RefreshCw,
  Loader2,
} from 'lucide-react';
import type { CategoryNode } from '@/types';

interface TreeNodeProps {
  node: CategoryNode;
  level: number;
  selectedCategory: string[] | null;
  onSelect: (path: string[]) => void;
}

function TreeNode({ node, level, selectedCategory, onSelect }: TreeNodeProps) {
  const { expandedNodes, toggleNode } = useLibraryStore();
  const isExpanded = expandedNodes.has(node.id);
  const isSelected = selectedCategory?.join('/') === node.path.join('/');
  const hasChildren = node.children && node.children.length > 0;

  const handleClick = () => {
    onSelect(node.path);
  };

  const handleToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (hasChildren) {
      toggleNode(node.id);
    }
  };

  return (
    <div>
      <div
        className={cn(
          'flex items-center gap-1 py-2 px-3 rounded-lg cursor-pointer transition-colors',
          isSelected
            ? 'bg-primary/10 text-primary'
            : 'hover:bg-accent text-foreground'
        )}
        style={{ paddingLeft: `${level * 20 + 12}px` }}
        onClick={handleClick}
      >
        <button
          onClick={handleToggle}
          className={cn(
            'p-0.5 rounded hover:bg-accent transition-colors',
            !hasChildren && 'invisible'
          )}
        >
          {isExpanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
        </button>

        <span className={cn('px-2 py-0.5 rounded text-xs font-medium', getCategoryTierColor(node.tier))}>
          {node.tier}
        </span>

        {isExpanded ? (
          <FolderOpen className="h-4 w-4 text-primary" />
        ) : (
          <Folder className="h-4 w-4 text-muted-foreground" />
        )}

        <span className="flex-1 truncate text-sm">{node.name}</span>

        {node.memoryCount !== undefined && (
          <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
            {node.memoryCount}
          </span>
        )}
      </div>

      {isExpanded && hasChildren && (
        <div>
          {node.children!.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              level={level + 1}
              selectedCategory={selectedCategory}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function LibraryTreeView() {
  const { selectedCategory, setSelectedCategory, searchQuery, setSearchQuery } = useAppStore();
  const { categories, setCategories, isLoading, setLoading, error, setError } = useLibraryStore();
  const [filteredCategories, setFilteredCategories] = useState<CategoryNode[]>([]);

  const { refetch, isFetching } = useQuery({
    queryKey: ['library-tree'],
    queryFn: async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await libraryApi.getTree();
        setCategories(data);
        return data;
      } catch (err) {
        setError(err instanceof Error ? err.message : '加载分类树失败');
        throw err;
      } finally {
        setLoading(false);
      }
    },
  });

  useEffect(() => {
    refetch();
  }, []);

  // 过滤分类树
  useEffect(() => {
    if (!searchQuery.trim()) {
      setFilteredCategories(categories);
      return;
    }

    const filterTree = (nodes: CategoryNode[]): CategoryNode[] => {
      return nodes
        .map((node) => {
          const matchesQuery = node.name.toLowerCase().includes(searchQuery.toLowerCase());
          const filteredChildren = node.children ? filterTree(node.children) : [];
          if (matchesQuery || filteredChildren.length > 0) {
            return {
              ...node,
              children: filteredChildren.length > 0 ? filteredChildren : node.children,
            };
          }
          return null;
        })
        .filter((n): n is CategoryNode => n !== null);
    };

    setFilteredCategories(filterTree(categories));
  }, [searchQuery, categories]);

  const handleSelect = (path: string[]) => {
    setSelectedCategory(path);
  };

  return (
    <div className="flex flex-col h-full">
      {/* 头部 */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-border bg-card">
        <div>
          <h1 className="text-2xl font-bold">图书馆视图</h1>
          <p className="text-sm text-muted-foreground mt-1">
            浏览和管理记忆分类（A.项目 / B.个人 / C.知识）
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-primary bg-primary/10 rounded-lg hover:bg-primary/20 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={cn('h-4 w-4', isFetching && 'animate-spin')} />
          刷新
        </button>
      </header>

      {/* 搜索栏 */}
      <div className="px-6 py-3 border-b border-border bg-background">
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="搜索分类..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 text-sm bg-background border border-input rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
          />
        </div>
      </div>

      {/* 分类树 */}
      <div className="flex-1 overflow-auto p-4">
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <span className="ml-3 text-muted-foreground">加载中...</span>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center h-64 text-destructive">
            <p className="text-lg font-medium">加载失败</p>
            <p className="text-sm mt-1">{error}</p>
            <button
              onClick={() => refetch()}
              className="mt-4 px-4 py-2 text-sm font-medium text-primary bg-primary/10 rounded-lg hover:bg-primary/20 transition-colors"
            >
              重试
            </button>
          </div>
        ) : filteredCategories.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
            <Folder className="h-12 w-12 mb-3 opacity-50" />
            <p className="text-lg font-medium">暂无分类</p>
            <p className="text-sm mt-1">创建记忆后会自动生成分类</p>
          </div>
        ) : (
          <div className="space-y-1">
            {filteredCategories.map((node) => (
              <TreeNode
                key={node.id}
                node={node}
                level={0}
                selectedCategory={selectedCategory}
                onSelect={handleSelect}
              />
            ))}
          </div>
        )}
      </div>

      {/* 选中分类信息 */}
      {selectedCategory && (
        <footer className="px-6 py-4 border-t border-border bg-card">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Folder className="h-4 w-4 text-primary" />
              <span className="text-sm font-medium">
                {selectedCategory.join(' / ')}
              </span>
            </div>
            <div className="flex gap-2">
              <button className="px-3 py-1.5 text-sm font-medium text-primary bg-primary/10 rounded-lg hover:bg-primary/20 transition-colors">
                查看记忆
              </button>
              <button className="px-3 py-1.5 text-sm font-medium text-muted-foreground bg-muted rounded-lg hover:bg-muted/80 transition-colors">
                新建子分类
              </button>
            </div>
          </div>
        </footer>
      )}
    </div>
  );
}

export default LibraryTreeView;
