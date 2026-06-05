// AgentMonitorView.tsx
import { useEffect, useState, useCallback, useRef } from "react";
import { Bot, Activity, ArrowUpRight, ArrowDownRight, RefreshCw, Wifi, WifiOff, FileEdit, FileSearch, Trash2, Eye } from "lucide-react";
import { Header } from "../components/layout";
import { useAgentMonitorStore } from "../store";
import { agentApi, appendLogApi } from "../api/client";
import type { Agent, AppendLog } from "../types";

export function AgentMonitorView() {
  const { agents, appendLogs, isConnected, isLoading, setAgents, addLog, setLogs, setConnected, setLoading, setError } = useAgentMonitorStore();
  const [autoScroll, setAutoScroll] = useState(true);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const loadAgents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try { const data = await agentApi.list(); setAgents(data); }
    catch (err) { setError(err instanceof Error ? err.message : "加载失败"); }
    finally { setLoading(false); }
  }, [setAgents, setLoading, setError]);

  const loadLogs = useCallback(async () => {
    try { const data = await appendLogApi.getRecent(50); setLogs(data); }
    catch (err) { console.error("Failed to load logs:", err); }
  }, [setLogs]);

  useEffect(() => {
    loadAgents();
    loadLogs();
    const unsubscribe = appendLogApi.subscribe((log) => addLog(log), () => setConnected(false));
    setConnected(true);
    return () => { unsubscribe(); setConnected(false); };
  }, [loadAgents, loadLogs, addLog, setConnected]);

  useEffect(() => { if (autoScroll && logsEndRef.current) logsEndRef.current.scrollIntoView({ behavior: "smooth" }); }, [appendLogs, autoScroll]);

  const getStatusColor = (status: Agent["status"]) => ({ active: "bg-green-100 text-green-700", idle: "bg-yellow-100 text-yellow-700", offline: "bg-gray-100 text-gray-500" })[status];
  const getStatusText = (status: Agent["status"]) => ({ active: "活跃", idle: "空闲", offline: "离线" })[status];
  const getOperationIcon = (op: AppendLog["operation"]) => ({ write: <FileEdit className="w-4 h-4 text-blue-500" />, read: <Eye className="w-4 h-4 text-green-500" />, search: <FileSearch className="w-4 h-4 text-purple-500" />, delete: <Trash2 className="w-4 h-4 text-red-500" /> })[op];
  const getOperationText = (op: AppendLog["operation"]) => ({ write: "写入", read: "读取", search: "搜索", delete: "删除" })[op];
  const formatTime = (dateStr: string) => new Date(dateStr).toLocaleTimeString("zh-CN");

  return (
    <div className="flex flex-col h-full">
      <Header title="Agent 监控" subtitle={`当前 ${agents.filter(a => a.status === "active").length} 个 Agent 活跃`} onRefresh={loadAgents} isRefreshing={isLoading} />
      <div className="flex-1 overflow-hidden flex flex-col">
        <div className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            {isConnected ? <><Wifi className="w-4 h-4 text-green-500" /><span className="text-sm text-green-600">实时连接中</span></> : <><WifiOff className="w-4 h-4 text-red-500" /><span className="text-sm text-red-600">连接断开</span></>}
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-600"><input type="checkbox" checked={autoScroll} onChange={(e) => setAutoScroll(e.target.checked)} className="w-4 h-4" />自动滚动</label>
        </div>
        <div className="flex-1 flex overflow-hidden">
          <div className="w-80 border-r border-slate-200 bg-white flex flex-col">
            <div className="p-4 border-b border-slate-100"><h3 className="font-medium">活跃 Agent</h3></div>
            <div className="flex-1 overflow-y-auto p-2">
              {agents.length === 0 ? <div className="p-4 text-center text-slate-400 text-sm">暂无 Agent</div> : <div className="space-y-2">{agents.map(agent => (
                <div key={agent.id} className="p-3 bg-slate-50 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2"><Bot className="w-5 h-5" /><span className="font-medium text-sm">{agent.name}</span></div>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${getStatusColor(agent.status)}`}>{getStatusText(agent.status)}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs text-slate-500">
                    <div className="flex items-center gap-1"><ArrowUpRight className="w-3 h-3 text-blue-500" /><span>写入: {agent.writeRate}/分</span></div>
                    <div className="flex items-center gap-1"><ArrowDownRight className="w-3 h-3 text-green-500" /><span>读取: {agent.readRate}/分</span></div>
                  </div>
                </div>
              ))}</div>}
            </div>
          </div>
          <div className="flex-1 flex flex-col bg-slate-50">
            <div className="p-4 bg-white border-b border-slate-200 flex items-center justify-between"><h3 className="font-medium flex items-center gap-2"><Activity className="w-5 h-5" />实时日志</h3><span className="text-xs text-slate-500">{appendLogs.length} 条记录</span></div>
            <div className="flex-1 overflow-y-auto p-4">
              <div className="space-y-2">
                {appendLogs.map(log => (
                  <div key={log.id} className="flex items-start gap-3 p-3 bg-white rounded-lg border">
                    <div className="mt-0.5">{getOperationIcon(log.operation)}</div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-medium">{log.agentName}</span>
                        <span className="text-xs px-1.5 py-0.5 bg-slate-100 rounded">{getOperationText(log.operation)}</span>
                        {log.memoryId && <span className="text-xs text-slate-400 truncate">ID: {log.memoryId.slice(0, 8)}...</span>}
                      </div>
                      {log.content && <p className="text-xs text-slate-500 line-clamp-1">{log.content}</p>}
                    </div>
                    <span className="text-xs text-slate-400">{formatTime(log.timestamp)}</span>
                  </div>
                ))}
                <div ref={logsEndRef} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
