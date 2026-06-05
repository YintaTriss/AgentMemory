// MemoryListView.tsx
import { useEffect, useState, useCallback } from "react";
import { Grid3X3, List, SortAsc, SortDesc, Filter, Search, Edit2, Trash2, FolderInput, Clock, RefreshCw, Plus } from "lucide-react";
import { Header } from "../components/layout";
import { useMemoryListStore, useLibraryStore } from "../store";
import { libraryApi } from "../api/client";
import type { MemoryListItem, EmbeddingStatus } from "../types";

export function MemoryListView() {
  const { memories, total, viewMode, sortConfig, isLoading, setMemories, setViewMode, setSortConfig, setLoading, setError } = useMemoryListStore();
  const { selectedCategory } = useLibraryStore();
  const [searchQuery, setSearchQuery] = useState("");

  const loadMemories = useCallback(async () => {
    if (!selectedCategory) return;
    setLoading(true);
    setError(null);
    try {
      const data = await libraryApi.getMemories(selectedCategory);
      setMemories(data.items, data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [selectedCategory, setMemories, setLoading, setError]);

  useEffect(() => { loadMemories(); }, [loadMemories]);

  const getImportanceStars = (importance: number) => "★".repeat(Math.round(importance)) + "☆".repeat(5 - Math.round(importance));
  const getStatusColor = (status: EmbeddingStatus) => ({ pending: "bg-slate-100 text-slate-600", generating: "bg-blue-100 text-blue-600", completed: "bg-green-100 text-green-600", failed: "bg-red-100 text-red-600", permanent_failure: "bg-gray-100 text-gray-600" })[status];
  const getStatusText = (status: EmbeddingStatus) => ({ pending: "等待中", generating: "生成中", completed: "已完成", failed: "失败", permanent_failure: "永久失败" })[status];
  const formatTime = (dateStr: string) => new Date(dateStr).toLocaleDateString("zh-CN");

  const MemoryCard = ({ memory }: { memory: MemoryListItem }) => (
    <div className="bg-white rounded-xl border border-slate-200 p-4 hover:shadow-md">
      <div className="flex justify-between items-start mb-3">
        <p className="text-sm text-slate-900 line-clamp-2 flex-1">{memory.summary}</p>
        <div className="flex gap-1 ml-2">
          <button className="p-1.5 rounded hover:bg-slate-100 text-slate-400"><Edit2 className="w-4 h-4" /></button>
          <button className="p-1.5 rounded hover:bg-slate-100 text-slate-400"><Trash2 className="w-4 h-4" /></button>
        </div>
      </div>
      <div className="flex items-center gap-2 mb-2">
        <span className={`text-xs px-2 py-0.5 rounded-full ${getStatusColor(memory.embeddingStatus)}`}>{getStatusText(memory.embeddingStatus)}</span>
        <span className="text-xs text-amber-600">{getImportanceStars(memory.importance)}</span>
      </div>
      {memory.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {memory.tags.slice(0, 3).map(tag => <span key={tag} className="text-xs px-2 py-0.5 bg-slate-100 rounded">{tag}</span>)}
        </div>
      )}
      <div className="flex justify-between text-xs text-slate-400">
        <span>{memory.category}</span>
        <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{formatTime(memory.createdAt)}</span>
      </div>
    </div>
  );

  return (
    <div className="flex flex-col h-full">
      <Header title="记忆列表" subtitle={selectedCategory ? `分类: ${selectedCategory} · 共 ${total} 条` : "请先选择分类"} onRefresh={loadMemories} isRefreshing={isLoading} />
      <div className="flex-1 overflow-hidden flex flex-col">
        <div className="bg-white border-b border-slate-200 px-6 py-3">
          <div className="flex items-center justify-between">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input type="text" placeholder="搜索记忆内容..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="w-full pl-9 pr-3 py-2 text-sm border rounded-lg" />
            </div>
            <div className="flex items-center gap-2">
              <button className={`p-2 border rounded-lg ${viewMode === "card" ? "bg-blue-50 text-blue-600" : "text-slate-400"}`}><Grid3X3 className="w-4 h-4" /></button>
              <button className={`p-2 border rounded-lg ${viewMode === "list" ? "bg-blue-50 text-blue-600" : "text-slate-400"}`}><List className="w-4 h-4" /></button>
            </div>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-6">
          {!selectedCategory ? (
            <div className="text-center text-slate-500 py-12"><FolderInput className="w-16 h-16 mx-auto mb-4 text-slate-300" /><p className="text-lg font-medium">请先选择一个分类</p><p className="mt-2 text-sm">在左侧图书馆视图中选择分类</p></div>
          ) : isLoading && memories.length === 0 ? (
            <div className="flex items-center justify-center h-64"><RefreshCw className="w-8 h-8 text-slate-400 animate-spin" /></div>
          ) : memories.length === 0 ? (
            <div className="text-center text-slate-500 py-12"><Plus className="w-16 h-16 mx-auto mb-4 text-slate-300" /><p className="text-lg font-medium">暂无记忆</p></div>
          ) : viewMode === "card" ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">{memories.map(memory => <MemoryCard key={memory.id} memory={memory} />)}</div>
          ) : (
            <div className="bg-white rounded-xl border overflow-hidden">
              <table className="w-full"><thead><tr className="bg-slate-50 border-b"><th className="px-4 py-3 text-left text-xs">内容</th><th className="px-4 py-3 text-left text-xs">状态</th><th className="px-4 py-3 text-left text-xs">重要性</th><th className="px-4 py-3 text-left text-xs">时间</th><th className="px-4 py-3 text-left text-xs">操作</th></tr></thead><tbody>{memories.map(memory => <tr key={memory.id} className="border-b hover:bg-slate-50"><td className="px-4 py-3 text-sm">{memory.summary}</td><td className="px-4 py-3"><span className={`text-xs px-2 py-0.5 rounded-full ${getStatusColor(memory.embeddingStatus)}`}>{getStatusText(memory.embeddingStatus)}</span></td><td className="px-4 py-3 text-amber-600">{getImportanceStars(memory.importance)}</td><td className="px-4 py-3 text-sm text-slate-500">{formatTime(memory.createdAt)}</td><td className="px-4 py-3"><button className="p-1"><Edit2 className="w-4 h-4" /></button></td></tr>)}</tbody></table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
