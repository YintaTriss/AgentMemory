import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { embeddingApi } from '@/api/client';
import { useEmbeddingStore } from '@/stores/appStore';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { RefreshCw, AlertCircle, CheckCircle, Clock, XCircle, Ban, RotateCcw, BarChart3, AlertTriangle, Activity } from 'lucide-react';
import { cn } from '@/utils/cn';
import { formatDistanceToNow } from 'date-fns';
import { zhCN } from 'date-fns/locale';
import type { EmbeddingTask } from '@/types';

const statusConfig: Record<string, { label: string; icon: React.ReactNode; color: string; bgColor: string }> = {
  pending: { label: '等待中', icon: <Clock className="h-4 w-4" />, color: 'text-yellow-600', bgColor: 'bg-yellow-100' },
  generating: { label: '生成中', icon: <Activity className="h-4 w-4 animate-pulse" />, color: 'text-blue-600', bgColor: 'bg-blue-100' },
  completed: { label: '已完成', icon: <CheckCircle className="h-4 w-4" />, color: 'text-green-600', bgColor: 'bg-green-100' },
  failed: { label: '失败', icon: <AlertCircle className="h-4 w-4" />, color: 'text-red-600', bgColor: 'bg-red-100' },
  permanent_failure: { label: '永久失败', icon: <Ban className="h-4 w-4" />, color: 'text-gray-600', bgColor: 'bg-gray-100' },
};

interface TaskCardProps { task: EmbeddingTask; onRetry: (id: string) => void; }
const TaskCard: React.FC<TaskCardProps> = ({ task, onRetry }) => {
  const cfg = statusConfig[task.status];
  const canRetry = task.status === 'failed' && task.retryCount < task.maxRetries;
  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardContent className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className={cn('p-1.5 rounded', cfg.bgColor)}><span className={cfg.color}>{cfg.icon}</span></div>
            <div><h3 className="font-medium text-sm">记忆ID: {task.memoryId}</h3><p className="text-xs text-muted-foreground">任务ID: {task.id}</p></div>
          </div>
          <Badge className={cn(cfg.bgColor, cfg.color)}>{cfg.label}</Badge>
        </div>
        {task.errorMessage && <div className="mb-3 p-2 rounded bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-xs"><AlertTriangle className="inline h-3 w-3 mr-1" />{task.errorMessage}</div>}
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>重试: {task.retryCount} / {task.maxRetries}</span>
          <span>创建: {formatDistanceToNow(new Date(task.createdAt), { addSuffix: true, locale: zhCN })}</span>
        </div>
        {canRetry && <Button variant="outline" size="sm" className="w-full mt-3" onClick={() => onRetry(task.id)}><RotateCcw className="h-3 w-3 mr-1" />重试</Button>}
      </CardContent>
    </Card>
  );
};

interface FailureItemProps { errorCode: string; count: number; lastSeen: string; }
const FailureItem: React.FC<FailureItemProps> = ({ errorCode, count, lastSeen }) => (
  <div className="flex items-center justify-between py-2 border-b border-border last:border-0">
    <code className="text-xs bg-muted px-2 py-0.5 rounded">{errorCode}</code>
    <div className="text-right"><span className="font-semibold text-red-600">{count}</span><span className="text-xs text-muted-foreground ml-2">最后: {formatDistanceToNow(new Date(lastSeen), { addSuffix: true, locale: zhCN })}</span></div>
  </div>
);

export const EmbeddingStatusView: React.FC = () => {
  const { stats, setStats } = useEmbeddingStore();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = React.useState('overview');

  const { data, isLoading, refetch } = useQuery({ queryKey: ['embedding-stats'], queryFn: embeddingApi.getStats });
  const { data: retryQueue } = useQuery({ queryKey: ['embedding-retry-queue'], queryFn: embeddingApi.getRetryQueue });
  const { data: failureSummary } = useQuery({ queryKey: ['embedding-failure-summary'], queryFn: embeddingApi.getFailureSummary });

  React.useEffect(() => { if (data) setStats(data); }, [data, setStats]);

  const retryMutation = useMutation({ mutationFn: embeddingApi.retry, onSuccess: () => queryClient.invalidateQueries({ queryKey: ['embedding-stats'] }) });
  const batchRetryMutation = useMutation({ mutationFn: embeddingApi.batchRetry, onSuccess: () => queryClient.invalidateQueries({ queryKey: ['embedding-stats'] }) });
  const handleRetry = (taskId: string) => retryMutation.mutate(taskId);
  const handleBatchRetry = () => { if (retryQueue && retryQueue.length > 0) batchRetryMutation.mutate(retryQueue.map((t) => t.id)); };

  if (isLoading) {
    return <div className="p-6 space-y-6"><div className="grid grid-cols-1 md:grid-cols-4 gap-4">{[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-24" />)}</div><Skeleton className="h-96" /></div>;
  }

  const currentStats = stats || data;

  return (
    <div className="flex flex-col h-full p-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Card><CardContent className="p-4"><div className="flex items-center gap-3"><div className="p-2 rounded-full bg-blue-100"><Clock className="h-5 w-5 text-blue-600" /></div><div><p className="text-xs text-muted-foreground">等待中</p><p className="text-2xl font-semibold">{currentStats?.pending || 0}</p></div></div></CardContent></Card>
        <Card><CardContent className="p-4"><div className="flex items-center gap-3"><div className="p-2 rounded-full bg-purple-100"><Activity className="h-5 w-5 text-purple-600 animate-pulse" /></div><div><p className="text-xs text-muted-foreground">生成中</p><p className="text-2xl font-semibold">{currentStats?.generating || 0}</p></div></div></CardContent></Card>
        <Card><CardContent className="p-4"><div className="flex items-center gap-3"><div className="p-2 rounded-full bg-green-100"><CheckCircle className="h-5 w-5 text-green-600" /></div><div><p className="text-xs text-muted-foreground">已完成</p><p className="text-2xl font-semibold">{currentStats?.completed || 0}</p></div></div></CardContent></Card>
        <Card><CardContent className="p-4"><div className="flex items-center gap-3"><div className="p-2 rounded-full bg-red-100"><XCircle className="h-5 w-5 text-red-600" /></div><div><p className="text-xs text-muted-foreground">失败</p><p className="text-2xl font-semibold">{currentStats?.failed || 0}</p></div></div></CardContent></Card>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <TabsList><TabsTrigger value="overview">概览</TabsTrigger><TabsTrigger value="retry-queue">重试队列</TabsTrigger><TabsTrigger value="failure-analysis">失败分析</TabsTrigger></TabsList>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => refetch()}><RefreshCw className="h-4 w-4 mr-1" />刷新</Button>
            {retryQueue && retryQueue.length > 0 && <Button variant="destructive" size="sm" onClick={handleBatchRetry} disabled={batchRetryMutation.isPending}><RotateCcw className="h-4 w-4 mr-1" />批量重试 ({retryQueue.length})</Button>}
          </div>
        </div>

        <TabsContent value="overview" className="flex-1 flex flex-col">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 flex-1">
            <Card><CardHeader><CardTitle className="text-lg flex items-center gap-2"><BarChart3 className="h-5 w-5" />成功率</CardTitle></CardHeader><CardContent><div className="text-center mb-4"><span className="text-4xl font-bold text-green-600">{currentStats?.successRate ? (currentStats.successRate * 100).toFixed(1) : 100}%</span></div><Progress value={(currentStats?.succ
