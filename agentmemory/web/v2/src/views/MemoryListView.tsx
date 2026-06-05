import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { memoryApi } from '@/api/client';
import { useMemoryListStore } from '@/stores/appStore';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Search, Grid3X3, List, Plus, RefreshCw, Filter, SortAsc, Trash2, Edit, FolderInput, Star, Clock, Eye, ChevronLeft, ChevronRight, CheckSquare, Square,
} from 'lucide-react';
import { cn } from '@/utils/cn';
import { formatDistanceToNow } from 'date-fns';
import { zhCN } from 'date-fns/locale';
import type { Memory, EmbeddingStatus } from '@/types';

const statusConfig: Record<EmbeddingStatus, { label: string; color: string; bgColor: string }> = {
  pending: { label: '等待中', color: 'text-yellow-600', bgColor: 'bg-yellow-100' },
  generating: { label: '生成中', color: 'text-blue-600', bgColor: 'bg-blue-100' },
  completed: { label: '已完成', color: 'text-green-600', bgColor: 'bg-green-100' },
  failed: { label: '失败', color: 'text-red-600', bgColor: 'bg-red-100' },
  permanent_failure: { label: '永久失败', color: 'text-gray-600', bgColor: 'bg-gray-100' },
};

const Stars: React.FC<{ level: 1 | 2 | 3 | 4 | 5 }> = ({ level }) => (
  <div className="flex">
    {[1, 2, 3, 4, 5].map((i) => (
      <Star key={i} className={cn('h-3 w-3', i <= level ? 'text-yellow-500 fill-yellow-500' : 'text-gray-300')} />
    ))}
  </div>
);

interface CardProps { memory: Memory; onEdit: (m: Memory) => void; onDelete: (id: string) => void; onMove: (m: Memory) => void; onSelect: (id: string) => void; isSelected: boolean; }
const MemoryCard: React.FC<CardProps> = ({ memory, onEdit, onDelete, onMove, onSelect, isSelected }) => {
  const cfg = statusConfig[memory.embeddingStatus];
  return (
    <Card className={cn('hover:shadow-md transition-shadow', isSelected && 'ring-2 ring-primary')}>
      <CardContent className="p-4">
        <div className="flex justify-between items-start mb-3">
          <div className="flex items-start gap-2">
            <button onClick={() => onSelect(memory.id)} className="mt-1">
              {isSelected ? <CheckSquare className="h-4 w-4 text-primary" /> : <Square className="h-4 w-4 text-muted-foreground" />}
            </button>
            <div className="flex-1 min-w-0">
              <p className="text-sm line-clamp-2 mb-2">{memory.content}</p>
              <div className="flex flex-wrap gap-1">
                {memory.tags.slice(0, 3).map((tag) => <Badge key={tag} variant="secondary" className="text-xs">{tag}</Badge>)}
                {memory.tags.length > 3 && <Badge variant="outline" className="text-xs">+{memory.tags.length - 3}</Badge>}
              </div>
            </div>
          </div>
          <div className="flex gap-1 ml-2">
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => onEdit(memory)}><Edit className="h-3 w-3" /></Button>
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => onMove(memory)}><FolderInput className="h-3 w-3" /></Button>
            <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive" onClick={() => onDelete(memory.id)}><Trash2 className="h-3 w-3" /></Button>
          </div>
        </div>
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <div className="flex items-center gap-3">
            <Stars level={memory.importance} />
            <span className={cn('px-2 py-0.5 rounded-full', cfg.bgColor)}><span className={cfg.color}>{cfg.label}</span></span>
          </div>
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1"><Eye className="h-3 w-3" />{memory.accessCount}</span>
            <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{formatDistanceToNow(new Date(memory.createdAt), { addSuffix: true, locale: zhCN })}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

interface RowProps { memory: Memory; onEdit: (m: Memory) => void; onDelete: (id: string) => void; onMove: (m: Memory) => void; onSelect: (id: string) => void; isSelected: boolean; }
const MemoryRow: React.FC<RowProps> = ({ memory, onEdit, onDelete, onMove, onSelect, isSelected }) => {
  const cfg = statusConfig[memory.embeddingStatus];
  return (
    <tr className={cn('border-b hover:bg-muted/50 transition-colors', isSelected && 'bg-primary/5')}>
      <td className="py-3 px-4">
        <button onClick={() => onSelect(memory.id)}>
          {isSelected ? <CheckSquare className="h-4 w-4 text-primary" /> : <Square className="h-4 w-4 text-muted-foreground" />}
        </button>
      </td>
      <td className="py-3 px-4"><div className="max-w-md truncate text-sm">{memory.content}</div></td>
      <td className="py-3 px-4"><div className="flex flex-wrap gap-1">{memory.tags.slice(0, 2).map((tag) => <Badge key={tag} variant="secondary" className="text-xs">{tag}</Badge>)}</div></td>
      <td className="py-3 px-4"><Stars level={memory.importance} /></td>
      <td className="py-3 px-4"><span className={cn('text-xs', cfg.color)}>{cfg.label}</span></td>
      <td className="py-3 px-4 text-xs text-muted-foreground">{formatDistanceToNow(new Date(memory.createdAt), { addSuffix: true, locale: zhCN })}</td>
      <td className="py-3 px-4">
        <div className="flex gap-1">
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => onEdit(memory)}><Edit className="h-3 w-3" /></Button>
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => onMove(memory)}><FolderInput className="h-3 w-3" /></Button>
          <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive" onClick={() => onDelete(memory.id)}><Trash2 className="h-3 w-3" /></Button>
        </div>
      </td>
    </tr>
  );
};

export const MemoryListView: React.FC = () => {
  const { 
    memories, setMemories, page, pageSize, total, setPage, 
    viewMode, setViewMode, sortBy, sortOrder, setSort, 
    searchQuery, setSearchQuery, categoryFilter, 
    selectedMemories, toggleSelected, clearSelection 
  } = useMemoryListStore();
  const queryClient = useQueryClient();

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['memories', { page, pageSize, category: categoryFilter, search: searchQuery, sortBy, sortOrder }],
    queryFn: () => memoryApi.list({ page, pageSize, category: categoryFilter || undefined, search: searchQuery || undefined, sortBy, sortOrder }),
  });

  React.useEffect(() => { 
    if (data) { 
      setMemories(data.items); 
    }
  }, [data, setMemories]);

  const deleteMutation = useMutation({ 
    mutationFn: memoryApi.delete, 
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['memories'] }) 
  });
  const handleDelete = (id: string) => { 
    if (confirm('确定要删除这条记忆吗？')) deleteMutation.mutate(id); 
  };

  const handleSelect = (id: string) => toggleSelected(id);

  const totalPages = data?.pages || 1;

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <div className="flex justify-between"><Skeleton className="h-10 w-64" /><Skeleton className="h-10 w-48" /></div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">{[1, 2, 3, 4, 5, 6].map((i) => <Skeleton key={i} className="h-40" />)}</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full p-6">
      {/* Top toolbar */}
      <div className="flex flex-wrap justify-between items-center gap-4 mb-6">
        <div className="flex items-center gap-2 flex-1">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input 
              placeholder="搜索记忆..." 
              value=
