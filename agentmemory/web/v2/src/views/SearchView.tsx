import React from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { searchApi, libraryApi } from '@/api/client';
import { useSearchStore } from '@/stores/appStore';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Sparkles, FolderTree, Combine, Search as SearchIcon, ChevronRight, BarChart3, Trash2, Edit, Eye, Clock, History } from 'lucide-react';
import { cn } from '@/utils/cn';
import { formatDistanceToNow } from 'date-fns';
import { zhCN } from 'date-fns/locale';
import type { SearchResult, SearchMode, LibraryNode } from '@/types';

const modeConfig: Record<SearchMode, { label: string; icon: React.ReactNode; description: string }> = {
  semantic: { label: '语义检索', icon: <Sparkles className="h-4 w-4" />, description: '基于向量相似度，找到语义相近的记忆' },
  category: { label: '分类检索', icon: <FolderTree className="h-4 w-4" />, description: '在指定分类中查找记忆' },
  hybrid: { label: '混合检索', icon: <Combine className="h-4 w-4" />, description: '结合语义和分类，结果更精准' },
};

const SearchResultCard: React.FC<{ result: SearchResult }> = ({ result }) => {
  const { memory, score, matchType } = result;
  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardContent className="p-4">
        <div className="flex justify-between items-start mb-3">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <Badge variant="outline" className="text-xs">{matchType === 'semantic' ? '语义匹配' : matchType === 'category' ? '分类匹配' : '混合匹配'}</Badge>
              <div className="flex items-center gap-1 text-xs">
                <BarChart3 className="h-3 w-3" />
                <span className={score > 0.8 ? 'text-green-600' : score > 0.5 ? 'text-yellow-600' : 'text-gray-600'}>{(score * 100).toFixed(1)}% 相似度</span>
              </div>
            </div>
            <p className="text-sm line-clamp-3 mb-2">{memory.content}</p>
            <div className="flex flex-wrap gap-1">{memory.tags.map((tag) => <Badge key={tag} variant="secondary" className="text-xs">{tag}</Badge>)}</div>
          </div>
          <div className="flex gap-1 ml-2">
            <Button variant="ghost" size="icon" className="h-7 w-7"><Eye className="h-3 w-3" /></Button>
            <Button variant="ghost" size="icon" className="h-7 w-7"><Edit className="h-3 w-3" /></Button>
          </div>
        </div>
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>{memory.category}</span>
          <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{formatDistanceToNow(new Date(memory.createdAt), { addSuffix: true, locale: zhCN })}</span>
        </div>
      </CardContent>
    </Card>
  );
};

export const SearchView: React.FC = () => {
  const { searchMode, setSearchMode, results, setResults, history, addToHistory, clearHistory } = useSearchStore();
  const [query, setQuery] = React.useState('');
  const [selectedCategory, setSelectedCategory] = React.useState<string | null>(null);

  const { data: categoryTree, isLoading: treeLoading } = useQuery({ queryKey: ['library-tree'], queryFn: libraryApi.getTree, enabled: searchMode !== 'semantic' });

  const searchMutation = useMutation({
    mutationFn: async () => {
      if (searchMode === 'semantic') return searchApi.semantic(query, 20);
      else if (searchMode === 'category' && selectedCategory) { const res = await searchApi.category(selectedCategory, 20); return res.map((m) => ({ memory: m, score: 1, matchType: 'category' as const })); }
      else return searchApi.hybrid(query, selectedCategory || undefined, 20);
    },
    onSuccess: (data) => { setResults(data); if (query) addToHistory(query, searchMode); },
  });

  const handleSearch = (e: React.FormEvent) => { e.preventDefault(); if (query.trim()) searchMutation.mutate(); };
  const handleHistoryClick = (historyQuery: string, mode: SearchMode) => { setQuery(historyQuery); setSearchMode(mode); };
  const flattenCategories = (nodes: LibraryNode[], result: LibraryNode[] = []): LibraryNode[] => { for (const node of nodes) { result.push(node); if (node.children) flattenCategories(node.children, result); } return result; };
  const flatCategories = flattenCategories(categoryTree || []);

  return (
    <div className="flex h-full gap-4 p-6">
      <Card className="w-80 flex-shrink-0 flex flex-col">
        <CardHeader><CardTitle className="text-lg flex items-center gap-2"><SearchIcon className="h-5 w-5" />检索</CardTitle></CardHeader>
        <CardContent className="space-y-4 flex-1 overflow-auto">
          <div className="space-y-2">
            <label className="text-sm font-medium">检索模式</label>
            <div className="space-y-2">
              {(Object.keys(modeConfig) as SearchMode[]).map((mode) => (
                <button key={mode} className={cn('w-full p-3 rounded-lg border text-left transition-colors', searchMode === mode ? 'border-primary bg-primary/5' : 'border-border hover:bg-accent')} onClick={() => setSearchMode(mode)}>
                  <div className="flex items-center gap-2">{modeConfig[mode].icon}<span className="font-medium">{modeConfig[mode].label}</span></div>
                  <p className="text-xs text-muted-foreground mt-1">{modeConfig[mode].description}</p>
                </button>
              ))}
            </div>
          </div>
          <form onSubmit={handleSearch} className="space-y-3">
            <div className="relative">
              <SearchIcon className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input placeholder="输入搜索关键词..." value={query} onChange={(e) => setQuery(e.target.value)} className="pl-9" />
            </div>
            <Button type="submit" className="w-full" disabled={!query.trim() || searchMutation.isPending}>{searchMutation.isPending ? '搜索中...' : '开始搜索'}</Button>
          </form>
          {searchMode !== 'semantic' && (
            <div className="space-y-2">
              <label className="text-sm font-medium">分类筛选</label>
              {treeLoading ? <Skeleton className="h-40 w-full" /> : (
                <ScrollArea className="h-40">
                  <div className="space-y-1">
                    <button className={cn('w-full p-2 rounded text-left text-sm', !selectedCategory ? 'bg-accent' : 'hover:bg-accent')} onClick={() => setSelectedCategory(null)}>全部分类</button>
                    {flatCategories.map((cat) => (
                      <button key={cat.id} className={cn('w-full p-2 rounded text-left text-sm truncate', selectedCategory === cat.path ? 'bg-accent' : 'hover:bg-accent')} onClick={() => setSelectedCategory(cat.path)}><ChevronRight className="inline h-3 w-3 mr-1" />{cat.name}</button>
                    ))}
                  </div>
                </ScrollArea>
              )}
            </div>
          )}
          {history.length > 0 && (
            <div className="space-y-2 pt-4 border-t">
              <div className="flex items-center justify-between"><label className="text-sm font-medium flex items-center gap-1"><History className="h-4 w-4" />搜索历史</label><Button variant="ghost" size="sm" onClick={clearHistory} className="h-6 text-xs">清除</Button></div>
              <div className="space-y-1 max-h-48 overflow-auto">
                {history.slice(0, 10).map((item, index) => (
                  <button key={index} className="w-full p-2 rounded text-left text-sm hover:bg-accent truncate" onClick={() => handleHistoryClick(item.query, item.mode)}><span className="text-muted-foreground">{item.query}</span><Badge variant="outline" className="ml-2 text-xs">{modeConfig[item.mode].label}</Badge></button>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
      <Card className="fle
