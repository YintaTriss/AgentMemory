import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { agentApi } from '@/api/client';
import { useAgentStore } from '@/stores/appStore';
import { cn, formatRelativeTime, formatDate } from '@/lib/utils';
import {
  Bot,
  Activity,
  ArrowUpDown,
  RefreshCw,
  Wifi,
  WifiOff,
  Clock,
  FileText,
  Plus,
  Minus,
  Trash2,
  Play,
  Pause,
  ScrollText,
  Loader2,
  AlertCircle,
} from 'lucide-react';
import type { AgentMetrics, AppendLogEntry } from '@/types';

function AgentCard({ agent, isSelected, onClick }: { agent: AgentMetrics; isSelected: boolean; onClick: () => void }) {
  return (
    <div
      onClick={onClick}
      className={cn(
        'p-4 rounded-xl border cursor-pointer transition-all',
        isSelected
          ? 'bg-primary/5 border-primary shadow-md'
          : 'bg-card border-border hover:border-primary/50 hover:shadow-sm'
      )}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={cn(
            'h-10 w-10 rounded-lg flex items-center justify-center',
            agent.is_active ? 'bg-green-100' : 'bg-gray-100'
          )}>
            <Bot className={cn('h-5 w-5', agent.is_active ? 'text-green-600' : 'text-gray-400')} />
          </div>
          <div>
            <h3 className="font-medium text-foreground">{agent.name}</h3>
            <p className="text-xs text-muted-foreground">{agent.agent_id}</p>
          </div>
        </div>
        <span className={cn(
          'px-2 py-0.5 rounded text-xs font-medium',
          agent.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
        )}>
          {agent.is_active ? '活跃' : '离线'}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="bg-muted/50 rounded-lg p-2">
          <div className="flex items-center gap-1 text-xs text-muted-foreground mb-1">
            <ArrowUpDown className="h-3 w-3" />
            写入速率
          </div>
          <div className="text-lg font-semibold text-green-600">
            {agent.write_rate.toFixed(1)}
          </div>
          <div className="text-xs text-muted-foreground">次/分钟</div>
        </div>
        <div className="bg-muted/50 rounded-lg p-2">
          <div className="flex items-center gap-1 text-xs text-muted-foreground mb-1">
            <ArrowUpDown className="h-3 w-3" />
            读取速率
          </div>
          <div className="text-lg font-semibold text-blue-600">
            {agent.read_rate.toFixed(1)}
          </div>
          <div className="text-xs text-muted-foreground">次/分钟</div>
        </div>
      </div>

      <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
        <Clock className="h-3 w-3" />
        最后活跃: {formatRelativeTime(agent.last_active)}
      </div>
    </div>
  );
}

function LogEntry({ entry, isNew }: { entry: AppendLogEntry; isNew: boolean }) {
  const getActionIcon = () => {
    switch (entry.action) {
      case 'store':
        return <Plus className="h-3 w-3 text-green-600" />;
      case 'update':
        return <FileText className="h-3 w-3 text-blue-600" />;
      case 'delete':
        return <Trash2 className="h-3 w-3 text-red-600" />;
      default:
        return <Activity className="h-3 w-3 text-gray-600" />;
    }
  };

  const getActionLabel = () => {
    switch (entry.action) {
      case 'store':
        return '写入';
      case 'update':
        return '更新';
      case 'delete':
        return '删除';
      default:
        return entry.action;
    }
  };

  return (
    <div className={cn(
      'flex items-start gap-3 px-4 py-2 border-b border-border hover:bg-muted/30 transition-colors',
      isNew && 'log-new-entry'
    )}>
      <div className="mt-0.5">{getActionIcon()}</div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-medium text-foreground">
            {entry.agent_name}
          </span>
          <span className="text-xs px-1.5 py-0.5 bg-muted rounded text-muted-foreground">
            {getActionLabel()}
          </span>
          <span className="text-xs text-muted-foreground">
            {formatRelativeTime(entry.timestamp)}
          </span>
        </div>
        <div className="text-xs text-muted-foreground">
          记忆 ID: <code className="bg-muted px-1 rounded">{entry.mem_id.slice(0, 8)}...</code>
          {entry.category.length > 0 && (
            <span className="ml-2">
              分类: {entry.category.join(' / ')}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

export function MultiAgentMonitorView() {
  const { agents, setAgents, appendLogs, addAppendLog, clearLogs, isConnected, setConnected } = useAgentStore();
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const logContainerRef = useRef<HTMLDivElement>(null);
  const prevLogCountRef = useRef(0);

  const {
    data: agentsData,
    isLoading: agentsLoading,
    error: agentsError,
    refetch: refetchAgents,
  } = useQuery({
    queryKey: ['active-agents'],
    queryFn: agentApi.getActiveAgents,
    refetchInterval: 30000, // 每30秒刷新
  });

  const {
    data: logsData,
    isLoading: logsLoading,
    refetch: refetchLogs,
  } = useQuery({
    queryKey: ['append-logs'],
    queryFn: () => agentApi.getAppendLogs({ limit: 100 }),
    refetchInterval: 5000, // 每5秒刷新
  });

  // 设置 agents
  useEffect(() => {
    if (agentsData) {
      setAgents(agentsData);
    }
  }, [agentsData, setAgents]);

  // 设置初始日志
  useEffect(() => {
    if (logsData) {
      clearLogs();
      logsData.forEach((log) => addAppendLog(log));
      prevLogCountRef.current = logsData.length;
    }
  }, [logsData]);

  // 检测新日志
  useEffect(() => {
    if (logsData && logsData.length > prevLogCountRef.current) {
      const newLogs = logsData.slice(0, logsData.length - prevLogCountRef.current);
      newLogs.forEach((log) => addAppendLog(log));
      prevLogCountRef.current = logsData.length;
    }
  }, [logsData, addAppendLog]);

  // 自动滚动
  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = 0;
    }
  }, [appendLogs, autoScroll]);

  // SSE 实时订阅
  useEffect(() => {
    const unsubscribe = agentApi.subscribeAppendLogs((entry) => {
      addAppendLog(entry);
      setConnected(true);
    });

    return () => {
      unsubscribe();
    };
  }, [addAppendLog, setConnected]);

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const { scrollTop } = e.currentTarget;
    setAutoScroll(scrollTop === 0);
  };

  const selectedAgentData = agents.find((a) => a.agent_id === selectedAgent);

  return (
    <div className="flex flex-col h-full">
      {/* 头部 */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-border bg-card">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">多 Agent 监控</h1>
          <div className={cn(
            'flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium',
            isConnected ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
          )}>
            {isConnected ? (
              <>
                <Wifi className="h-3 w-3" />
                实时连接
              </>
            ) : (
              <>
                <WifiOff className="h-3 w-3" />
                离线
              </>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">
            {agents.length} 个 Agent
          </span>
          <button
            onClick={() => refetchAgents()}
            className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-muted-foreground bg-muted rounded-lg hover:bg-muted/80 transition-colors"
          >
            <RefreshCw className="h-4 w-4" />
            刷新
          </button>
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden">
        {/* 左侧: Agent 列表 */}
        <div className="w-80 border-r border-border flex flex-col overflow-hidden">
          <div className="px-4 py-3 border-b border-border bg-muted/30">
            <h2 className="text-sm font-medium text-muted-foreground">活跃 Agent</h2>
          </div>
          <div className="flex-1 overflow-auto p-3 space-y-2">
            {agentsLoading ? (
              <div className="flex items-center justify-center h-32">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
              </div>
            ) : agentsError ? (
              <div className="p-4 text-center text-destructive">
                <AlertCircle className="h-6 w-6 mx-auto mb-2" />
                <p className="text-sm">加载失败</p>
              </div>
            ) : agents.length === 0 ? (
              <div className="p-4 text-center text-muted-foreground">
                <Bot className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">暂无活跃 Agent</p>
              </div>
            ) : (
              agents.map((agent) => (
                <AgentCard
                  key={agent.agent_id}
                  agent={agent}
                  isSelected={selectedAgent === agent.agent_id}
                  onClick={() => setSelectedAgent(
                    selectedAgent === agent.agent_id ? null : agent.agent_id
                  )}
                />
              ))
            )}
          </div>
        </div>

        {/* 右侧: 详情和日志 */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Agent 详情 */}
          {selectedAgentData && (
            <div className="px-6 py-4 border-b border-border bg-card">
              <div className="flex items-center gap-4">
                <div className="h-12 w-12 rounded-xl bg-primary/10 flex items-center justify-center">
                  <Bot className="h-6 w-6 text-primary" />
                </div>
                <div className="flex-1">
                  <h2 className="text-lg font-semibold">{selectedAgentData.name}</h2>
                  <p className="text-sm text-muted-foreground">{selectedAgentData.agent_id}</p>
                </div>
                <div className="flex items-center gap-6">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-green-600">
                      {selectedAgentData.write_rate.toFixed(1)}
                    </div>
                    <div className="text-xs text-muted-foreground">写入/分钟</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-blue-600">
                      {selectedAgentData.read_rate.toFixed(1)}
                    </div>
                    <div className="text-xs text-muted-foreground">读取/分钟</div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Append 日志 */}
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="px-6 py-3 border-b border-border bg-muted/30 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ScrollText className="h-4 w-4 text-muted-foreground" />
                <h2 className="text-sm font-medium text-muted-foreground">
                  Append 日志 ({appendLogs.length})
                </h2>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setAutoScroll(!autoScroll)}
                  className={cn(
                    'flex items-center gap-1 px-2 py-1 text-xs rounded transition-colors',
                    autoScroll
                      ? 'bg-primary/10 text-primary'
                      : 'bg-muted text-muted-foreground'
                  )}
                >
                  <Play className="h-3 w-3" />
                  自动滚动
                </button>
                <button
                  onClick={() => {
                    clearLogs();
                    refetchLogs();
                  }}
                  className="flex items-center gap-1 px-2 py-1 text-xs text-muted-foreground bg-muted rounded hover:bg-muted/80 transition-colors"
                >
                  <RefreshCw className="h-3 w-3" />
                  刷新
                </button>
              </div>
            </div>

            <div
              ref={logContainerRef}
              onScroll={handleScroll}
              className="flex-1 overflow-auto"
            >
              {logsLoading ? (
                <div className="flex items-center justify-center h-32">
                  <Loader2 className="h-6 w-6 animate-spin text-primary" />
                </div>
              ) : appendLogs.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-32 text-muted-foreground">
                  <ScrollText className="h-8 w-8 mb-2 opacity-50" />
                  <p className="text-sm">暂无日志</p>
                </div>
              ) : (
                appendLogs.map((entry, index) => (
                  <LogEntry
                    key={entry.id}
                    entry={entry}
                    isNew={index === 0}
                  />
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default MultiAgentMonitorView;
