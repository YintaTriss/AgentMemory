// ============================================
// 图书馆视图 - Library Tree
// 树形展示 A.项目/B.个人/C.知识 分类
// ============================================

import { useEffect, useState, useCallback } from 'react';
import { 
  ChevronRight, 
  ChevronDown, 
  Folder, 
  FolderOpen,
  FileText,
  Search,
  Plus,
  RefreshCw,
  FolderPlus
} from 'lucide-react';
import { Header } from '../components/layout';
import { useLibraryStore } from '../store';
import { libraryApi } from '../api/client';
import type { LibraryNode } from '../types';

export function LibraryView() {
  const { tree, selectedCategory, expandedNodes, isLoading, error, setTree, setSelectedCategory, toggleExpanded, setLoading, setError } = useLibraryStore();
  const [searchQuery, setSearchQuery] = useState('');
  const [filteredTree, setFilteredTree] = useState<LibraryNode[]>([]);

  // 加载图书馆树
  const loadTree = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await libraryApi.getTree();
      setTree(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, [setTree, setLoading, setError]);

  useEffect(() => {
    loadTree();
  }, [loadTree]);

  // 过滤树
  useEffect(() => {
    if (!searchQuery.trim()) {
      setFilteredTree(tree);
      return;
    }
    const filterNodes = (nodes: LibraryNode[]): LibraryNode[] => {
      return nodes
        .map(node => {
          const matchesSearch = node.name.toLowerCase().includes(searchQuery.toLowerCase());
          const filteredChildren = node.children ? filterNodes(node.children) : [];
          if (matchesSearch || filteredChildren.length > 0) {
            return { ...node, children: filteredChildren };
          }
          return null;
        })
        .filter((n): n is LibraryNode => n !== null);
    };
    setFilteredTree(filterNodes(tree));
  }, [tree, searchQuery]);

  // 渲染树节点
  const renderTreeNode = (node: LibraryNode, level: number = 0) => {
    const isExpanded = expandedNodes.has(node.path);
    const hasChildren = node.children && node.children.length > 0;
    const isSelected = selectedCategory === node.path;

    return (
      <div key={node.path}>
        <button
          onClick={() => {
            if (hasChildren) toggleExpanded(node.path);
            setSelectedCategory(node.path);
          }}
          className={`
            w-full flex items-center gap-2 px-3 py-2 text-left rounded-lg transition-colors
            ${isSelected ? 'bg-blue-100 text-blue-700' : 'hover:bg-slate-100'}
          `}
          style={{ paddingLeft: `${12 + level * 20}px` }}
        >
          {/* 展开/折叠图标 */}
          {hasChildren ? (
            isExpanded ? (
              <ChevronDown className="w-4 h-4 text-slate-400 flex-shrink-0" />
            ) : (
              <ChevronRight className="w-4 h-4 text-slate-400 flex-shrink-0" />
            )
          ) : (
            <span className="w-4" />
          )}
          
          {/* 文件夹图标 */}
          {isExpanded && hasChildren ? (
            <FolderOpen className="w-5 h-5 text-yellow-500 flex-shrink-0" />
          ) : (
            <Folder className="w-5 h-5 text-yellow-500 flex-shrink-0" />
          )}
          
          {/* 名称 */}
          <span className="flex-1 truncate text-sm font-medium">{node.name}</span>
          
          {/* 记忆数量 */}
          <span className="text-xs text-slate-400 bg-slate-100 px-2 py-0.5 rounded-full">
            {node.memoryCount}
          </span>
        </button>

        {/* 子节点 */}
        {isExpanded && hasChildren && (
          <div>
            {node.children!.map(child => renderTreeNode(child, level + 1))}
          </div>
        )}
      </div>
    );
  };

  // 获取当前分类下的记忆数量统计
  const getTotalMemoryCount = () => {
    const countNode = (nodes: LibraryNode[]): number => {
      return nodes.reduce((sum, node) => sum + node.memoryCount + (node.children ? countNode(node.children) : 0), 0);
    };
    return countNode(tree);
  };

  return (
    <div className="flex flex-col h-full">
      <Header 
        title="图书馆" 
        subtitle={`共 ${getTotalMemoryCount()} 条记忆`}
        onRefresh={loadTree}
        isRefreshing={isLoading}
      />
      
      <div className="flex-1 flex overflow-hidden">
        {/* 左侧分类树 */}
        <div className="w-72 border-r border-slate-200 bg-white flex flex-col">
          {/* 搜索框 */}
          <div className="p-3 border-b border-slate-100">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                placeholder="搜索分类..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* 新建分类按钮 */}
          <div className="p-3 border-b border-slate-100">
            <button className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm text-blue-600 border border-blue-200 rounded-lg hover:bg-blue-50 transition-colors">
              <FolderPlus className="w-4 h-4" />
              新建分类
            </button>
          </div>

          {/* 树内容 */}
          <div className="flex-1 overflow-y-auto p-2">
            {isLoading && tree.length === 0 ? (
              <div className="flex items-center justify-center h-32">
                <RefreshCw className="w-6 h-6 text-slate-400 animate-spin" />
              </div>
            ) : error ? (
              <div className="p-4 text-center text-red-500 text-sm">{error}</div>
            ) : filteredTree.length === 0 ? (
              <div className="p-4 text-center text-slate-400 text-sm">
                {searchQuery ? '未找到匹配的分类' : '暂无分类'}
              </div>
            ) : (
              <div className="space-y-0.5">
                {filteredTree.map(node => renderTreeNode(node))}
              </div>
            )}
          </div>
        </div>

        {/* 右侧内容区 */}
        <div className="flex-1 p-6 overflow-y-auto">
          {selectedCategory ? (
            <div className="text-center text-slate-500">
              <FileText className="w-12 h-12 mx-auto mb-4 text-slate-300" />
              <p className="text-lg font-medium">当前分类: {selectedCategory}</p>
              <p className="mt-2 text-sm">在左侧选择具体分类查看记忆列表</p>
            </div>
          ) : (
            <div className="text-center text-slate-500">
              <Folder className="w-16 h-16 mx-auto mb-4 text-slate-300" />
              <p className="text-lg font-medium">选择一个分类</p>
              <p className="mt-2 text-sm">从左侧树形结构中选择一个分类来查看和管理记忆</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
