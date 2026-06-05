// SearchView.tsx
import { useState, useCallback } from "react";
import { Search, Brain, FolderTree, GitMerge, BarChart3, RefreshCw } from "lucide-react";
import { Header } from "../components/layout";
import { useSearchStore } from "../store";
import { searchApi } from "../api/client";
import type { SearchMode, SearchResult } from "../types";

export function SearchView() {
  const { query, mode, results, isSearching, error, setQuery, setMode, setResults, setSearching, setError, clearResults } = useSearchStore();
  const [selectedCategory, setSelectedCategory] = useState("");

  const handleSearch = useCallback(async () => {
    if (!query.trim() && mode !== "category") return;
    setSearching(true);
    setError(null);
    try {
      let searchResults: SearchResult[];
      switch (mode) {
        case "semantic": searchResults = await searchApi.semantic(query); break;
        case "category": searchResults = await searchApi.category(selectedCategory); break;
        case "hybrid": searchResults = await searchApi.hybrid(query, selectedCategory); break;
        default: searchResults = await searchApi.hybrid(query, selectedCategory);
      }
      setResults(searchResults as unknown as any);
    } catch (err) {
      setError(err instanceof Error ? err.message : "检索失败");
    } finally {
      setSearching(false);
    }
  }, [query, mode, selectedCategory, setResults, setSearching, setError]);

  const renderResult = (result: SearchResult) => {
    const score = result.hybridScore || result.semanticScore || 0;
    const scoreColor = score >= 0.8 ? "text-green-600" : score >= 0.6 ? "text-blue-600" : "text-slate-600";
    return (
      <div key={result.memory.id} className="bg-white rounded-xl border border-slate-200 p-4 hover:shadow-md">
        <div className="flex justify-between items-start mb-2">
          <p className="text-sm text-slate-900 line-clamp-2 flex-1">{result.memory.content}</p>
          <div className={`ml-3 flex items-center gap-1 text-sm font-medium ${scoreColor}`}>
            <BarChart3 className="w-4 h-4" />{(score * 100).toFixed(0)}%
          </div>
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          <span className="px-2 py-0.5 bg-slate-100 rounded">{result.memory.category}</span>
          {result.memory.tags?.map(tag => <span key={tag} className="px-2 py-0.5 bg-blue-50 text-blue-600 rounded">{tag}</span>)}
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full">
      <Header title="检索" subtitle="双轨检索系统：语义检索 + 分类检索" />
      <div className="flex-1 overflow-hidden flex flex-col">
        <div className="bg-white border-b border-slate-200 p-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-sm font-medium">检索模式:</span>
            <div className="flex gap-2">
              <button onClick={() => setMode("semantic")} className={`flex items-center gap-2 px-4 py-2 text-sm rounded-lg ${mode === "semantic" ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-600"}`}><Brain className="w-4 h-4" />语义检索</button>
              <button onClick={() => setMode("category")} className={`flex items-center gap-2 px-4 py-2 text-sm rounded-lg ${mode === "category" ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-600"}`}><FolderTree className="w-4 h-4" />分类检索</button>
              <button onClick={() => setMode("hybrid")} className={`flex items-center gap-2 px-4 py-2 text-sm rounded-lg ${mode === "hybrid" ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-600"}`}><GitMerge className="w-4 h-4" />混合检索</button>
            </div>
          </div>
          <div className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
              <input type="text" placeholder={mode === "category" ? "选择分类进行检索..." : "输入检索关键词..."} value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && handleSearch()} disabled={mode === "category"} className="w-full pl-12 pr-4 py-3 text-lg border rounded-xl" />
            </div>
            <button onClick={handleSearch} disabled={isSearching || (!query.trim() && mode !== "category")} className="px-6 py-3 bg-blue-600 text-white font-medium rounded-xl hover:bg-blue-700 disabled:opacity-50">
              {isSearching ? <RefreshCw className="w-5 h-5 animate-spin" /> : "检索"}
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-6">
          {error && <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">{error}</div>}
          {results.length === 0 && !isSearching && <div className="text-center text-slate-500 py-12"><Search className="w-16 h-16 mx-auto mb-4 text-slate-300" /><p className="text-lg font-medium">开始检索</p><p className="mt-2 text-sm">输入关键词或选择分类来检索记忆</p></div>}
          {results.length > 0 && <div><div className="flex justify-between mb-4"><p className="text-sm font-medium">找到 <span className="text-blue-600">{results.length}</span> 条相关记忆</p><button onClick={clearResults} className="text-sm text-blue-600">清除结果</button></div><div className="space-y-3">{results.map(renderResult)}</div></div>}
        </div>
      </div>
    </div>
  );
}
