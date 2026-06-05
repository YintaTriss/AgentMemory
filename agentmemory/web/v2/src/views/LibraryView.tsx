import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { libraryApi } from '@/api/client';
import { useLibraryStore } from '@/stores/appStore';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Search,
  ChevronRight,
  ChevronDown,
  FolderOpen,
  Folder,
  FileText,
  Plus,
  RefreshCw,
  Filter,
  SortAsc,
  MoreHorizontal,
} from 'lucide-react';
import { cn } from '@/utils/cn';
import type { LibraryNode } from '@/types';

const CategoryIcon: React.FC<{ type: string; expanded?: boolean }> = ({ type, expanded }) => {
  if (type === 'A.项目' || type === 'B.个人' || type === 'C.知识') {
    return <FolderOpen className="h-4 w-4 text-blue-500" />;
  }
  return expanded ? <FolderOpen className="h-4 w-4 text-yellow-500" /> : <Folder className="h-4 w-4 text-yellow-500" />;
};

interface TreeNodeProps {
  node: LibraryNode;
  level: number;
  selectedId: string | null;
  expandedNodes: Set<string>;
  onToggle: (id: string) => void;
  onSelect: (node: LibraryNode) => void;
}

const TreeNode: React.FC<TreeNodeProps> = ({
  node,
  level,
  selectedId,
  expandedNodes,
  onToggle,
  onSelect,
}) => {
  const isExpanded = expandedNodes.has(node.id);
  const isSelected = selectedId === node.path;
  const hasChildren = node.children && node.children.length > 0;

  return (
    <div>
      <div
        className={cn(
          'group flex items-center py-2 px-3 rounded-md cursor-pointer transition-colors hover:bg-accent',
          isSelected && 'bg-accent'
        )}
        style={{ paddingLeft: `${level * 16 + 12}px` }}
        onClick={() => onSelect(node)}
      >
        {hasChildren && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onToggle(node.id);
            }}
            className="mr-1 p-0.5 hover:bg-accent rounded"
          >
            {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          </button>
        )}
        {!hasChildren && <span className="w-4" />}
        <CategoryIcon type={node.type} expanded={isExpanded} />
        <span className="ml-2 flex-1 truncate text-sm">{node.name}</span>
        {node.memoryCount > 0 && (
          <Badge variant="secondary" className="ml-2 text-xs">{node.memoryCount}</Badge>
        )}
        <Button variant="ghost" size="icon" className="h-6 w-6 opacity-0 group-hover:opacity-100">
          <MoreHorizontal className="h-3 w-3" />
        </Button>
      </div>
      {isExpanded && node.children && (
        <div>
          {node.children.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              level={level + 1}
              selectedId={selectedId}
              expandedNodes={expandedNodes}
              onToggle={onToggle}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export const LibraryView: React.FC = () => {
  const {
    tree,
    setTree,
    selectedCategory,
    setSelectedCategory,
    expandedNodes,
    toggleExpanded,
    searchQuery,
    setSearchQuery,
  } = useLibraryStore();

  const { data: treeData, isLoading, refetch } = useQuery({
    queryKey: ['library-tree'],
    queryFn: libraryApi.getTree,
  });

  React.useEffect(() => {
    if (treeData) {
      setTree(treeData);
    }
  }, [treeData, setTree]);

  const handleSelect = (node: LibraryNode) => {
    setSelectedCategory(node.path);
  };

  const filterTree = (nodes: LibraryNode[], query: string): LibraryNode[] => {
    if (!query) return nodes;
    return nodes
      .map((node) => {
        const filteredChildren = filterTree(node.children || [], query);
        if (node.name.toLowerCase().includes(query.toLowerCase()) || filteredChildren.length > 0) {
          return { ...node, children: filteredChildren };
        }
        return null;
      })
      .filter((n): n is LibraryNode => n !== null);
  };

  const filteredTree = filterTree(tree, searchQuery);

  if (isLoading) {
    return (
      <div className="flex h-full gap-4 p-6">
        <div className="w-80 space-y-4">
          <Skeleton className="h-10 w-full" />
          <div className="space-y-2">
            {[1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-10 w-full" />)}
          </div>
        </div>
        <div className="flex-1"><Skeleton className="h-full w-full" /></div>
      </div>
    );
  }

  return (
    <div className="flex h-full gap-4 p-6">
      <Card className="w-80 flex-shrink-0 flex flex-col">
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">分类树</CardTitle>
            <div className="flex gap-1">
              <Button variant="ghost" size="icon" onClick={() => refetch()}>
                <RefreshCw className="h-4 w-4" />
              </Button>
              <Button variant="ghost" size="icon">
                <Plus className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="搜索分类..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
        </CardHeader>
        <CardContent className="flex-1 overflow-hidden">
          <ScrollArea className="h-full">
            <div className="space-y-1">
              {filteredTree.map((node) => (
                <TreeNode
                  key={node.id}
                  node={node}
                  level={0}
                  selectedId={selectedCategory}
                  expandedNodes={expandedNodes}
                  onToggle={toggleExpanded}
                  onSelect={handleSelect}
                />
              ))}
              {filteredTree.length === 0 && (
                <div className="py-8 text-center text-muted-foreground">
                  {searchQuery ? '没有找到匹配的分类' : '暂无分类数据'}
                </div>
              )}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>

      <Card className="flex-1">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">
              {selectedCategory ? `分类: ${selectedCategory}` : '请选择一个分类'}
            </CardTitle>
            <div className="flex gap-2">
              <Button variant="outline" size="sm">
                <Filter className="h-4 w-4 mr-1" />筛选
              </Button>
              <Button variant="outline" size="sm">
                <SortAsc className="h-4 w-4 mr-1" />排序
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {selectedCategory ? (
            <div className="text-center py-12 text-muted-foreground">
              <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>已选择分类：{selectedCategory}</p>
              <p className="text-sm mt-2">记忆列表将在此处显示</p>
              <p className="text-xs mt-1">（等待后端 API 对接）</p>
            </div>
          ) : (
            <div className="text-center py-12 text-muted-foreground">
              <FolderOpen className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>请从左侧选择一个分类</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default LibraryView;
