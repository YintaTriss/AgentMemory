import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { embeddingApi } from '@/api/client';
import { useEmbeddingStore } from '@/stores/appStore';
import {
  cn,
  formatDate,
  getEmbeddingStatusColor,
  getEmbeddingStatusLabel,
} from '@/lib/utils';
import {
  Database,
  RefreshCw,
  Loader2,
  AlertCircle,
  Clock,
  CheckCircle2,
  XCircle,
  RotateCcw,
  Trash2,
  Play,
  Pause,
  BarChart3,
  PieChart,
  List,
  AlertTriangle,
} from 'lucide-react';
import {
  PieChart as RechartsPie,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from 'recharts';
import type { EmbeddingStats, EmbeddingQueueItem, EmbeddingFailure } from '@/types';

const STATUS_COLORS: Record<string, string> = {
  pending: '#facc15',      // yellow
  generating: '#3b82f6',    // blue
  completed: '#22c55e',     // green
  failed: '#ef4444',         // red
  permanent_failure: '#6b7280', // gray
};

interface StatusCardProps {
  title: string;
  count: number;
  total: number;
  color: string;
  icon: React.ReactNode;
}

function StatusCard({ title, count, total, color, icon }: StatusCardProps) {
  const percentage = total > 0 ? (count / total) * 100 : 0;

  return (
    <div className="bg-card border border-border rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={cn('p-2 rounded-lg', color)}>
            {icon}
          </div>
          <span className="font-medium text-foreground">{title}</span>
        </div>
        <span className="text-2xl font-bold" style={{ color }}>
          {count}
        </span>
      </div>
      <div className="w-full bg-muted rounded-full h-2">
        <div
          className="h-2 rounded-full transition-all duration-500"
          style={{ width: `${percentage}%`, backgroundColor: color }}
        />
      </div>
      <div className="mt-2 text-xs text-muted-foreground text-right">
        {percentage.toFixed(1)}%
      </div>
    </div>
  );
}

function RetryQueueItem({ item, onRetry, onDiscard }: { item: EmbeddingQueueItem; onRetry: () => void; onDiscard: () => void }) {
  return (
    <div className="flex items-center gap-3 px-4 py-3 border-b border-border hover:bg-muted/30 transition-colors">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <Clock className="h-3 w-3 text-yellow-600" />
          <code className="text-xs bg-muted px-1.5 py-0.5 rounded font-mono">
            {item.mem_id.slice(0, 8)}...
          </code>
          <span className="text-xs text-muted-foreground">
            {item.memory.category.join(' / ')}
          </span>
        </div>
        <p className="text-sm text-muted-foreground truncate">
          {item.memory.content_summary || item.memory.content.slice(0, 80)}
        </p>
        <div className="flex items-center gap-2 mt-1">
          <span className="text-xs text-muted-foreground">
            重试 {item.retry_count}/{item.max_retries} 次
          </span>
          {item.error_message && (
            <span className="text-xs text-red-600 truncate">
              {item.error_message}
            </span>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={onRetry}
          className="p-2 rounded-lg hover:bg-primary/10 transition-colors"
          title="重试"
        >
          <RotateCcw className="h-4 w-4 text-primary" />
        </button>
        <button
          onClick={onDiscard}
          className="p-2 rounded-lg hover:bg-destructive/10 transition-colors"
          title="放弃"
        >
          <Trash2 className="h-4 w-4 text-destructive" />
        </button>
      </div>
    </div>
  );
}

function FailureItem({ failure, onRetry }: { failure: EmbeddingFailure; onRetry: () => void }) {
  return (
    <div className="flex items-center gap-3 px-4 py-3 border-b border-border hover:bg-muted/30 transition-colors">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <XCircle className="h-4 w-4 text-red-600" />
          <code className="text-xs bg-muted px-1.5 py-0.5 rounded font-mono">
            {failure.mem_id.slice(0, 8)}...
          </code>
          <span className="text-xs text-muted-foreground">
            {failure.memory.category.join(' / ')}
          </span>
        </div>
        <p className="text-sm text-muted-foreground truncate">
          {failure.memory.content_summary || failure.memory.content.slice(0, 80)}
        </p>
        <div className="flex items-center gap-2 mt-1">
          <span className="text-xs text-red-600">
            失败: {failure.error_message}
          </span>
          <span className="text-xs text-muted-foreground">
            {formatDate(failure.failed_at)}
          </span>
        </div>
      </div>
      <button
        onClick={onRetry}
        className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-primary bg-primary/10 rounded-lg hover:bg-primary/20 transition-colors"
      >
        <RotateCcw className="h-4 w-4" />
        重试
      </button>
    </div>
  );
}

type TabType = 'overview' | 'queue' | 'failures';

export function EmbeddingStatusView() {
  const queryClient = useQueryClient();
  const {
    stats,
    setStats,
    retryQueue,
    setRetryQueue,
    failures,
    setFailures,
    isLoading,
    setLoading,
    autoRefresh,
    setAutoRefresh,
  } = useEmbeddingStore();
  const [activeTab, setActiveTab] = useState<TabType>('overview');

  const {
    data: statsData,
    isLoading: statsLoading,
    error: statsError,
    refetch: refetchStats,
  } = useQuery({
    queryKey: ['embedding-stats'],
    queryFn: embeddingApi.getStats,
    refetchInterval: autoRefresh ? 5000 : false,
  });

  const {
    data: queueData,
    refetch: refetchQueue,
  } = useQuery({
    queryKey: ['embedding-queue'],
    queryFn: embeddingApi.getRetryQueue,
    refetchInterval: autoRefresh ? 10000 : false,
  });

  const {
    data: failuresData,
    refetch: refetchFailures,
  } = useQuery({
    queryKey: ['embedding-failures'],
    queryFn: embeddingApi.getFailures,
    refetchInterval: autoRefresh ? 30000 : false,
  });

  const retryMutation = useMutation({
    mutationFn: (memId: string) => embeddingApi.retry(memId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['embedding-queue'] });
      queryClient.invalidateQueries({ queryKey: ['embedding-failures'] });
      queryClient.invalidateQueries({ queryKey: ['embedding-stats'] });
    },
  });

  const retryBatchMutation = useMutation({
    mutationFn: (memIds: string[]) => embeddingApi.retryBatch(memIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['embedding-queue'] });
      queryClient.invalidateQueries({ queryKey: ['embedding-failures'] });
      queryClient.invalidateQueries({ queryKey: ['embedding-stats'] });
    },
  });

  // 更新状态
  useEffect(() => {
    if (statsData) setStats(statsData);
  }, [statsData, setStats]);

  useEffect(() => {
    if (queueData) setRetryQueue(queueData);
  }, [queueData, setRetryQueue]);

  useEffect(() => {
    if (failuresData) setFailures(failuresData);
  }, [failuresData, setFailures]);

  const handleRetryAll = () => {
    const failedIds = failures.map((f) => f.mem_id);
    if (failedIds.length > 0) {
      retryBatchMutation.mutate(failedIds);
    }
  };

  const pieData = stats
    ? [
        { name: '等待中', value: stats.pending, color: STATUS_COLORS.pending },
        { name: '生成中', value: stats.generating, color: STATUS_COLORS.generating },
        { name: '已完成', value: stats.completed, color: STATUS_COLORS.completed },
        { name: '失败', value: stats.failed, color: STATUS_COLORS.failed },
        { name: '永久失败', value: stats.permanent_failure, color: STATUS_COLORS.permanent_failure },
      ].filter((d) => d.value > 0)
    : [];

  const refreshAll = () => {
    refetchStats();
    refetchQueue();
    refetchFailures();
  };

  return (
    <div className="flex flex-col h-full">
      {/* 头部 */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-border bg-card">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">嵌入状态监控</h1>
          {stats && (
            <span className="text-sm text-muted-foreground">
              共 {stats.total} 条记忆
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={cn(
              'flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-lg transition-colors',
              autoRefresh
                ? 'bg-green-100 text-green-700'
                : 'bg-muted text-muted-foreground'
            )}
          >
            {autoRefresh ? (
              <>
                <Pause className="h-4 w-4" />
                自动刷新
              </>
            ) : (
              <>
                <Play className="h-4 w-4" />
                暂停刷新
              </>
            )}
          </button>
          <button
            onClick={refreshAll}
            className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-muted-foreground bg-muted rounded-lg hover:bg-muted/80 transition-colors"
          >
            <RefreshCw className={cn('h-4 w-4', statsLoading && 'animate-spin')} />
            刷新
          </button>
        </div>
      </header>

      {/* Tab 切换 */}
      <div className="px-6 py-3 border-b border-border bg-background flex items-center gap-4">
        <button
          onClick={() => setActiveTab('overview')}
          className={cn(
            'flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors',
            activeTab === 'overview'
              ? 'bg-primary text-primary-foreground'
              : 'text-muted-foreground hover:bg-muted'
          )}
        >
          <BarChart3 className="h-4 w-4" />
          状态概览
        </button>
        <button
          onClick={() => setActiveTab('queue')}
          className={cn(
            'flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors',
            activeTab === 'queue'
              ? 'bg-primary text-primary-foreground'
              : 'text-muted-foreground hover:bg-muted'
          )}
        >
          <Clock className="h-4 w-4" />
          重试队列
          {retryQueue.length > 0 && (
            <span className="px-1.5 py-0.5 text-xs bg-yellow-500 text-white rounded-full">
              {retryQueue.length}
            </span>
          )}
        </button>
        <button
          onClick={() => setActiveTab('failures')}
          className={cn(
            'flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors',
            activeTab === 'failures'
              ? 'bg-primary text-primary-foreground'
              : 'text-muted-foreground hover:bg-muted'
          )}
        >
          <AlertTriangle className="h-4 w-4" />
          失败列表
          {failures.length > 0 && (
            <span className="px-1.5 py-0.5 text-xs bg-red-500 text-white rounded-full">
              {failures.length}
            </span>
          )}
        </button>
      </div>

      {/* 内容区域 */}
      <div className="flex-1 overflow-auto p-6">
        {statsLoading && !stats ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <span className="ml-3 text-muted-foreground">加载中...</span>
          </div>
        ) : statsError ? (
          <div className="flex flex-col items-center justify-center h-64 text-destructive">
            <AlertCircle className="h-8 w-8 mb-3" />
            <p className="text-lg font-medium">加载失败</p>
            <p className="text-sm mt-1">{statsError instanceof Error ? statsError.message : '未知错误'}</p>
            <button
              onClick={refreshAll}
              className="mt-4 px-4 py-2 text-sm font-medium text-primary bg-primary/10 rounded-lg hover:bg-primary/20 transition-colors"
            >
              重试
            </button>
          </div>
        ) : (
          <>
            {/* 状态概览 */}
            {activeTab === 'overview' && stats && (
              <div className="space-y-6">
                {/* 状态卡片 */}
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                  <StatusCard
                    title="等待中"
                    count={stats.pending}
                    total={stats.total}
                    color="text-yellow-600 bg-yellow-100"
                    icon={<Clock className="h-4 w-4" />}
                  />
                  <StatusCard
                    title="生成中"
                    count={stats.generating}
                    total={stats.total}
                    color="text-blue-600 bg-blue-100"
                    icon={<RefreshCw className="h-4 w-4" />}
                  />
                  <StatusCard
                    title="已完成"
                    count={stats.completed}
                    total={stats.total}
                    color="text-green-600 bg-green-100"
                    icon={<CheckCircle2 className="h-4 w-4" />}
                  />
                  <StatusCard
                    title="失败"
                    count={stats.failed}
                    total={stats.total}
                    color="text-red-600 bg-red-100"
                    icon={<AlertCircle className="h-4 w-4" />}
                  />
                  <StatusCard
                    title="永久失败"
                    count={stats.permanent_failure}
                    total={stats.total}
                    color="text-gray-600 bg-gray-100"
                    icon={<XCircle className="h-4 w-4" />}
                  />
                </div>

                {/* 饼图 */}
                <div className="bg-card border border-border rounded-xl p-6">
                  <h2 className="text-lg font-semibold mb-4">状态分布</h2>
                  {pieData.length > 0 ? (
                    <div className="h-80">
                      <ResponsiveContainer width="100%" height="100%">
                        <RechartsPie>
                          <Pie
                            data={pieData}
                            cx="50%"
                            cy="50%"
                            innerRadius={60}
                            outerRadius={100}
                            paddingAngle={2}
                            dataKey="value"
                          >
                            {pieData.map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={entry.color} />
                            ))}
                          </Pie>
                          <Tooltip
                            formatter={(value: number) => [`${value} 条`, '数量']}
                          />
                          <Legend />
                        </RechartsPie>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <div className="flex items-center justify-center h-64 text-muted-foreground">
                      <p>暂无数据</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* 重试队列 */}
            {activeTab === 'queue' && (
              <div className="bg-card border border-border rounded-xl overflow-hidden">
                <div className="px-4 py-3 border-b border-border bg-muted/30 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Clock className="h-4 w-4 text-yellow-600" />
                    <h2 className="text-sm font-medium">重试队列</h2>
                    <span className="text-xs text-muted-foreground">
                      ({retryQueue.length} 条)
                    </span>
                  </div>
                  {retryQueue.length > 0 && (
                    <button
                      onClick={handleRetryAll}
                      disabled={retryBatchMutation.isPending}
                      className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-primary bg-primary/10 rounded-lg hover:bg-primary/20 transition-colors disabled:opacity-50"
                    >
                      <RotateCcw className="h-4 w-4" />
                      全部重试
                    </button>
                  )}
                </div>
                {retryQueue.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-48 text-muted-foreground">
                    <CheckCircle2 className="h-12 w-12 mb-3 opacity-30" />
                    <p>重试队列为空</p>
                  </div>
                ) : (
                  <div className="max-h-[calc(100vh-300px)] overflow-auto">
                    {retryQueue.map((item) => (
                      <RetryQueueItem
                        key={item.mem_id}
                        item={item}
                        onRetry={() => retryMutation.mutate(item.mem_id)}
                        onDiscard={() => {/* TODO: 实现放弃功能 */}}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* 失败列表 */}
            {activeTab === 'failures' && (
              <div className="bg-card border border-border rounded-xl overflow-hidden">
                <div className="px-4 py-3 border-b border-border bg-muted/30 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 text-red-600" />
                    <h2 className="text-sm font-medium">失败列表</h2>
                    <span className="text-xs text-muted-foreground">
                      ({failures.length} 条)
                    </span>
                  </div>
                  {failures.length > 0 && (
                    <button
                      onClick={handleRetryAll}
                      disabled={retryBatchMutation.isPending}
                      className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-primary bg-primary/10 rounded-lg hover:bg-primary/20 transition-colors disabled:opacity-50"
                    >
                      <RotateCcw className="h-4 w-4" />
                      全部重试
                    </button>
                  )}
                </div>
                {failures.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-48 text-muted-foreground">
                    <CheckCircle2 className="h-12 w-12 mb-3 text-green-500" />
                    <p>暂无失败记录</p>
                  </div>
                ) : (
                  <div className="max-h-[calc(100vh-300px)] overflow-auto">
                    {failures.map((failure) => (
                      <FailureItem
                        key={failure.mem_id}
                        failure={failure}
                        onRetry={() => retryMutation.mutate(failure.mem_id)}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default EmbeddingStatusView;
