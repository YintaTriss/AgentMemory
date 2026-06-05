import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { agentApi } from '@/api/client';
import { useAgentMonitorStore } from '@/stores/appStore';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Bot, RefreshCw, Trash2, Activity, ArrowUpRight, ArrowDownRight, Plus, Search, FileText, Edit } from 'lucide-react';
import { cn } from '@/utils/cn';
import { formatDistanceToNow } from 'date-fns';
import { zhCN } from 'date-fns/locale';
import type { Agent, AgentLog } from '@/types';

const statusConfig: Record<Agent['status'], { label: string; color: string; bgColor: string }> = {
  active: { label: '活跃', color: 'text-green-600', bgColor: 'bg-green-100' },
  idle: { label: '空闲', color: 'text-yellow-600', bgColor: 'bg-yellow-100' },
  error: { label: '错误', color: 'text-red-600', bgColor: 'bg-red-100' },
};

const actionIcons: Record<AgentLog['action'], React.ReactNode> = {
  append: <Plus className="h-3 w-3 text-green-500" />,
  search: <Search className="h-3 w-3 text-blue-500" />,
  read: <FileText className="h-3 w-3 text-gray-500" />,
  update: <Edit className="h-3 w-3 text-yellow-500" />,
  delete: <FileText className="h-3 w-3 text-red-500" />,
};

const actionLabels: Record<AgentLog['action'], string> = {
  append: '写入', search: '搜索', read: '读取', update: '更新', delete: '删除',
};

interface AgentCardProps { agent: Agent; isSelected: boolean; onClick: () => void; }
const AgentCard: React.FC<AgentCardProps> = ({ agent, isSelected, onClick }) => {
  const cfg = statusConfig[agent.status];
  return (
    <Card className={cn('cursor-pointer transition-all hover:shadow-md', isSelected && 'ring-2 ring-primary')} onClick={onClick}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-full bg-primary/10"><Bot className="h-4 w-4 text-primary" /></div>
            <div><h3 className="font-medium">{agent.name}</h3><p className="text-xs text-muted-foreground">ID: {agent.id}</p></div>
          </div>
          <Badge className={cn(cfg.bgColor, cfg.color)}>{cfg.label}</Badge>
        </div>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div className="flex items-center gap-1 text-green-600"><ArrowUpRight className="h-3 w-3" /><span className="font-medium">{agent.writeSpeed.toFixed(1)}</span><span className="text-muted-foreground">写入/分</span></div>
          <div className="flex items-center gap-1 text-blue-600"><ArrowDownRight className="h-3 w-3" /><span className="font-medium">{agent.readSpeed.toFixed(1)}</span><span className="text-muted-foreground">读取/分</span></div>
        </div>
        <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
          <span>{agent.memoryCount} 条记忆</span>
          <span>最后: {formatDistanceToNow(new Date(agent.lastActivity), { addSuffix: true, locale: zhCN })}</span>
        </div>
      </CardContent>
    </Card>
  );
};

const LogEntry: React.FC<{ log: AgentLog }> = ({ log }) => (
  <div className="flex items-start gap-3 py-2 border-b border-border last:border-0">
    <div className="mt-0.5">{actionIcons[log.action]}</div>
    <div className="flex-1 min-w-0">
      <div className="flex items-center gap-2"><Badge variant="secondary" className="text-xs">{log.agentName}</Badge><span className="text-sm">{actionLabels[log.action]}</span>{log.memoryId && <span className="text-xs text-muted-foreground truncate">ID: {log.memoryId}</span>}</div>
      {log.details && <p className="text-xs text-muted-foreground mt-1 truncate">{log.details}</p>}
    </div>
    <span className="text-xs text-muted-foreground whitespace-nowrap">{formatDistanceToNow(new Date(log.timestamp), { addSuffix: true, locale: zhCN })}</span>
  </div>
);

export const AgentMonitorView: React.FC = () => {
  const { agents, setAgents, logs, addLog, clearLogs, selectedAgent, setSelectedAgent, autoScroll, setAutoScroll } = useAgentMonitorStore();
  const logsEndRef = React.useRef<HTMLDivElement>(null);

  const { data: agentsData, isLoading, refetch } = useQuery({ queryKey: ['agents'], queryFn: agentApi.list });

  React.useEffect(() => { if (agentsData) setAgents(agentsData); }, [agentsData, setAgents]);
  React.useEffect(() => {
    const cleanup = agentApi.getLogsStream((log) => addLog(log), (error) => console.error('SSE error:', error));
    return cleanup;
  }, [addLog]);
  React.useEffect(() => { if (autoScroll && logsEndRef.current) logsEndRef.current.scrollIntoView({ behavior: 'smooth' }); }, [logs, autoScroll]);

  const activeAgents = agents.filter((a) => a.status === 'active');
  const avgWriteSpeed = activeAgents.length > 0 ? activeAgents.reduce((sum, a) => sum + a.writeSpeed, 0) / activeAgents.length : 0;
  const avgReadSpeed = activeAgents.length > 0 ? activeAgents.reduce((sum, a) => sum + a.readSpeed, 0) / activeAgents.length : 0;

  if (isLoading) {
    return (
      <div className="flex h-full gap-4 p-6">
        <div className="w-80 space-y-4"><Skeleton className="h-10 w-full" /><div className="space-y-4">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-40" />)}</div></div>
        <div className="flex-1"><Skeleton className="h-full" /></div>
      </div>
    );
  }

  return (
    <div className="flex h-full gap-4 p-6">
      <Card className="w-80 flex-shrink-0 flex flex-col">
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between"><CardTitle className="text-lg">Agent 列表</CardTitle><Button variant="ghost" size="icon" onClick={() => refetch()}><RefreshCw className="h-4 w-4" /></Button></div>
          <div className="grid grid-cols-2 gap-2 mt-2">
            <div className="p-2 rounded-lg bg-muted"><div className="text-xs text-muted-foreground">活跃</div><div className="text-lg font-semibold text-green-600">{activeAgents.length}</div></div>
            <div className="p-2 rounded-lg bg-muted"><div className="text-xs text-muted-foreground">总计</div><div className="text-lg font-semibold">{agents.length}</div></div>
          </div>
        </CardHeader>
        <CardContent className="flex-1 overflow-hidden">
          <ScrollArea className="h-full">
            <div className="space-y-3">
              {agents.map((agent) => <AgentCard key={agent.id} agent={agent} isSelected={selectedAgent === agent.id} onClick={() => setSelectedAgent(agent.id === selectedAgent ? null : agent.id)} />)}
              {agents.length === 0 && <div className="py-8 text-center text-muted-foreground">暂无 Agent 数据</div>}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>

      <Card className="flex-1 flex flex-col">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">实时日志<Badge variant="secondary" className="ml-2">{logs.length} 条</Badge></CardTitle>
            <div className="flex gap-2">
              <Button variant={autoScroll ? 'secondary' : 'outline'} size="sm" onClick={() => setAutoScroll(!autoScroll)}><Activity className="h-4 w-4 mr-1" />自动滚动</Button>
              <Button variant="outline" size="sm" onClick={clearLogs}><Trash2 className="h-4 w-4 mr-1" />清除</Button>
            </div>
          </div>
          <div className="grid grid-cols-4 gap-4 mt-4">
            <div className="p-3 rounded-lg border"><div className="text-xs text-muted-foreground">平均写入速度</div><div className="text-lg font-semibold text-green-600">{avgWriteSpeed.toFixed(2)} /分</div></div>
            <div className="p-3 rounded-lg border"><div className="text-xs text-muted-foreground">平均读取速度</div><div className="text-lg font-semibold text-blue-600">{avgReadSpeed.toFixed(2)} /分</div></div>
            <div className="p-3 rounded-lg border"><div className="text-xs text-muted-foreground">今
