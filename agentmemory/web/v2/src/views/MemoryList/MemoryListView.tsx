import { useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { memoryApi } from '@/api/client';
import { useAppStore } from '@/stores/appStore';
import {
  cn,
  formatDate,
  truncateText,
  getEmbeddingStatusColor,
  getEmbeddingStatusLabel,
  getImportanceColor,
} from '@/lib/utils';
import {
  LayoutGrid,
  List,
  Search,
  Filter,
  SortAsc,
  SortDesc,
  MoreVertical,
  Edit2,
  Trash2,
  FolderInput,
  Star,
  Tag,
  Calendar,
  Loader2,
  RefreshCw,
  Plus,
} from 'lucide-react';
import type { MemoryEntry } from '@/types';

interface MemoryCardProps {
  memory: MemoryEntry;
  onEdit: (memory: MemoryEntry) => void;
  onDelete: (memId: string) => void;
  onMove: (memory: MemoryEntry) => void;
}

function MemoryCard({ memory, onEdit, onDelete, onMove }: MemoryCardProps) {
  return (
    <div className="bg-card border border-border rounded-xl p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          {/* 分类标签 */}
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            {memory.category.map((cat, i) => (
              <span
                key={i}
                className="px-2 py-0.5 text-xs font-medium bg-primary/10 text-primary rounded"
              >
                {cat}
              </span>
            ))}
          </div>

          {/* 内容摘要 */}
          <p className="text-sm text-foreground line-clamp-3 mb-3">
            {memory.content_summary || truncateText(memory.content, 150)}
          </p>

          {/* 标签 */}
          {memory.tags.length > 0 && (
            <div className="flex items-center gap-1 mb-3 flex-wrap">
              <Tag className="h-3 w-3 text-muted-foreground" />
              {memory.tags.slice(0, 5).map((tag, i) => (
                <span
                  key={i}
                  className="px-1.5 py-0.5 text-xs bg-muted text-muted-foreground rounded"
                >
                  {tag}
                </span>
              ))}
              {memory.tags.length > 5 && (
                <span className="text-xs text-muted-foreground">
                  +{memory.tags.length - 5}
                </span>
              )}
            </div>
          )}

          {/* 元信息 */}
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            {/* 重要性 */}
            <div className="flex items-center gap-1">
              <Star
                className={cn('h-3 w-3', getImportanceColor(memory.importance))}
                fill={memory.importance >= 0.5 ? 'currentColor' : 'none'}
              />
              <span>{Math.round(memory.importance * 100)}%</span>
            </div>

            {/* 创建时间 */}
            <div className="flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              <span>{formatDate(memory.created_at)}</span>
            </div>

            {/* Embedding 状态 */}
            <span
              className={cn(
                'px-1.5 py-0.5 rounded text-xs font-medium',
                getEmbeddingStatusColor(memory.embedding_status)
              )}
            >
              {getEmbeddingStatusLabel(memory.embedding_status)}
            </span>
          </div>
        </div>

        {/* 操作菜单 */}
        <div className="relative group">
          <button className="p-1.5 rounded-lg hover:bg-muted transition-colors">
            <MoreVertical className="h-4 w-4 text-muted-foreground" />
          </button>
          <div className="absolute right-0 top-full mt-1 w-36 bg-card border border-border rounded-lg shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-10">
            <button
              onClick={() => onEdit(memory)}
              className="flex items-center gap-2 w-full px-3 py-2 text-sm text-foreground hover:bg-muted transition-colors rounded-t-lg"
            >
              <Edit2 className="h-4 w-4" />
              编辑
            </button>
            <button
              onClick={() => onMove(memory)}
              className="flex items-center gap-2 w-full px-3 py-2 text-sm text-foreground hover:bg-muted transition-colors"
            >
              <FolderInput className="h-4 w-4" />
              移动
            </button>
            <button
              onClick={() => onDelete(memory.mem_id)}
              className="flex items-center gap-2 w-full px-3 py-2 text-sm text-destructive hover:bg-destructive/10 transition-colors rounded-b-lg"
            >
              <Trash2 className="h-4 w-4" />
              删除
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

interface MemoryListRowProps {
  memory: MemoryEntry;
  onEdit: (memory: MemoryEntry) => void;
  onDelete: (memId: string) => void;
  onMove: (memory: MemoryEntry) => void;
}

function MemoryListRow({ memory, onEdit, onDelete, onMove }: MemoryListRowProps) {
  return (
    <tr className="border-b border-border hover:bg-muted/50 transition-colors">
      <td className="px-4 py-3">
        <div className="max-w-md">
          <p className="text-sm text-foreground truncate">
            {memory.content_summary || truncateText(memory.content, 80)}
          </p>
        </div>
      </td>
      <td className="px-4 py-3">
        <div className="flex gap-1 flex-wrap">
          {memory.category.map((cat, i) => (
            <span
              key={i}
              className="px-1.5 py-0.5 text-xs font-medium bg-primary/10 text-primary rounded"
            >
              {cat}
            </span>
          ))}
        </div>
      </td>
      <td className="px-4 py-3">
        <div className="flex gap-1 flex-wrap">
          {memory.tags.slice(0, 3).map((tag, i) => (
            <span
              key={i}
              className="px-1.5 py-0.5 text-xs bg-muted text-muted-foreground rounded"
            >
              {tag}
            </span>
          ))}
        </div>
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1">
          <Star
            className={cn('h-3 w-3', getImportanceColor(memory.importance))}
            fill={memory.importance >= 0.5 ? 'currentColor' : 'none'}
          />
          <span className="text-sm">{Math.round(memory.importance * 100)}%</span>
        </div>
      </td>
      <td className="px-4 py-3">
        <span
          className={cn(
            'px-1.5 py-0.5 rounded text-xs font-medium',
            getEmbeddingStatusColor(memory.embedding_status)
          )}
        >
          {getEmbeddingStatusLabel(memory.embedding_status)}
        </span>
      </td>
      <td className="px-4 py-3 text-sm text-muted-foreground">
        {formatDate(memory.created_at)}
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1">
          <button
            onClick={() => onEdit(memory)}
            className="p-1.5 rounded hover:bg-muted transition-colors"
            title="编辑"
          >
            <Edit2 className="h-4 w-4 text-muted-foreground" />
          </button>
          <button
            onClick={() => onMove(memory)}
            className="p-1.5 rounded hover:bg-muted transition-colors"
            title="移动"
          >
            <FolderInput className="h-4 w-4 text-muted-foreground" />
          </button>
          <button
            onClick={() => onDelete(memory.mem_id)}
            className="p-1.5 rounded hover:bg-destructive/10 transition-colors"
            title="删除"
          >
            <Trash2 className="h-4 w-4 text-destructive" />
          </button>
        </div>
      </td>
    </tr>
  );
}

export function MemoryListView() {
  const queryClient = useQueryClient();
  const {
    viewMode,
    setViewMode,
    searchQuery,
    setSearchQuery,
    sortBy,
    setSortBy,
    sortOrder,
    setSortOrder,
    selectedCategory,
    setCreateModalOpen,
    setEditModalOpen,
    setSelectedMemory,
    setDeleteConfirmOpen,
    setMemoryToDelete,
  } = useAppStore();

  const {
    data: memoriesData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['memories', selectedCategory, searchQuery],
    queryFn: async () => {
      return memoryApi.list({
        category: selectedCategory || undefined,
        limit: 100,
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: memoryApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['memories'] });
    },
  });

  const handleEdit = (memory: MemoryEntry) => {
    setSelectedMemory(memory);
    setEditModalOpen(true);
  };

  const handleDelete = (memId: string) => {
    setMemoryToDelete(memId);
    setDeleteConfirmOpen(true);
  };

  const handleMove = (memory: MemoryEntry) => {
    setSelectedMemory(memory);
    // 打开移动分类对话框
  };

  const toggleSortOrder = () => {
    setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
  };

  // 排序记忆
  const sortedMemories = [...(memoriesData?.items || [])].sort((a, b) => {
    let aVal: number | string;
    let bVal: number | string;

    switch (sortBy) {
      case 'importance':
        aVal = a.importance;
        bVal = b.importance;
        break;
      case 'updated_at':
        aVal = new Date(a.updated_at).getTime();
        bVal = new Date(b.updated_at).getTime();
        break;
      case 'created_at':
      default:
        aVal = new Date(a.created_at).getTime();
        bVal = new Date(b.created_at).getTime();
    }

    if (sortOrder === 'asc') {
      return aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
    } else {
      return aVal > bVal ? -1 : aVal < bVal ? 1 : 0;
    }
  });

  // 过滤记忆
  const filteredMemories = searchQuery
    ? sortedMemories.filter(
        (m) =>
          m.content.toLowerCase().includes(searchQuery.toLowerCase()) ||
          m.tags.some((t) => t.toLowerCase().includes(searchQuery.toLowerCase()))
      )
    : sortedMemories;

  return (
    <div className="flex flex-col h-full">
      {/* 头部 */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-border bg-card">
        <div>
          <h1 className="text-2xl font-bold">记忆列表</h1>
          <p className="text-sm text-muted-foreground mt-1">
            共 {memoriesData?.total || 0} 条记忆
            {selectedCategory && ` · 分类: ${selectedCategory.join(' / ')}`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => refetch()}
            disabled={isLoading}
            className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-muted-foreground bg-muted rounded-lg hover:bg-muted/80 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={cn('h-4 w-4', isLoading && 'animate-spin')} />
          </button>
          <button
            onClick={() => setCreateModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-primary-foreground bg-primary rounded-lg hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-4 w-4" />
            新建记忆
          </button>
        </div>
      </header>

      {/* 工具栏 */}
      <div className="px-6 py-3 border-b border-border bg-background flex flex-wrap items-center gap-3">
        {/* 搜索 */}
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="搜索记忆内容或标签..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 text-sm bg-background border border-input rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
          />
        </div>

        {/* 筛选 */}
        <button className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-muted-foreground bg-muted rounded-lg hover:bg-muted/80 transition-colors">
          <Filter className="h-4 w-4" />
          筛选
        </button>

        {/* 排序 */}
        <div className="flex items-center gap-1">
          <span className="text-sm text-muted-foreground mr-1">排序:</span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
            className="px-2 py-1.5 text-sm bg-background border border-input rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/20"
          >
            <option value="created_at">创建时间</option>
            <option value="updated_at">更新时间</option>
            <option value="importance">重要性</option>
          </select>
          <button
            onClick={toggleSortOrder}
            className="p-1.5 rounded-lg hover:bg-muted transition-colors"
          >
            {sortOrder === 'asc' ? (
              <SortAsc className="h-4 w-4 text-muted-foreground" />
            ) : (
              <SortDesc className="h-4 w-4 text-muted-foreground" />
            )}
          </button>
        </div>

        {/* 视图切换 */}
        <div className="flex items-center border border-input rounded-lg overflow-hidden">
          <button
            onClick={() => setViewMode('card')}
            className={cn(
              'p-2 transition-colors',
              viewMode === 'card'
                ? 'bg-primary text-primary-foreground'
                : 'bg-background text-muted-foreground hover:bg-muted'
            )}
          >
            <LayoutGrid className="h-4 w-4" />
          </button>
          <button
            onClick={() => setViewMode('list')}
            className={cn(
              'p-2 transition-colors',
              viewMode === 'list'
                ? 'bg-primary text-primary-foreground'
                : 'bg-background text-muted-foreground hover:bg-muted'
            )}
          >
            <List className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* 记忆列表 */}
      <div className="flex-1 overflow-auto p-4">
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <span className="ml-3 text-muted-foreground">加载中...</span>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center h-64 text-destructive">
            <p className="text-lg font-medium">加载失败</p>
            <p className="text-sm mt-1">{error instanceof Error ? error.message : '未知错误'}</p>
            <button
              onClick={() => refetch()}
              className="mt-4 px-4 py-2 text-sm font-medium text-primary bg-primary/10 rounded-lg hover:bg-primary/20 transition-colors"
            >
              重试
            </button>
          </div>
        ) : filteredMemories.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
            <p className="text-lg font-medium">暂无记忆</p>
            <p className="text-sm mt-1">
              {searchQuery ? '尝试调整搜索条件' : '点击"新建记忆"开始添加'}
            </p>
          </div>
        ) : viewMode === 'card' ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {filteredMemories.map((memory) => (
              <MemoryCard
                key={memory.mem_id}
                memory={memory}
                onEdit={handleEdit}
                onDelete={handleDelete}
                onMove={handleMove}
              />
            ))}
          </div>
        ) : (
          <div className="bg-card border border-border rounded-xl overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="bg-muted/50 border-b border-border">
                  <th className="text-left px-4 py-3 text-sm font-medium text-muted-foreground">内容</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-muted-foreground">分类</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-muted-foreground">标签</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-muted-foreground">重要性</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-muted-foreground">状态</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-muted-foreground">创建时间</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-muted-foreground w-28">操作</th>
                </tr>
              </thead>
              <tbody>
                {filteredMemories.map((memory) => (
                  <MemoryListRow
                    key={memory.mem_id}
                    memory={memory}
                    onEdit={handleEdit}
                    onDelete={handleDelete}
                    onMove={handleMove}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default MemoryListView;
