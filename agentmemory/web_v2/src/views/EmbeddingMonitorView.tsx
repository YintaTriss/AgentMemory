// EmbeddingMonitorView.tsx
import { useEffect, useState, useCallback } from "react";
import { Database, Clock, CheckCircle2, XCircle, RefreshCw, RotateCcw, TrendingUp } from "lucide-react";
import { Header } from "../components/layout";
import { useEmbeddingMonitorStore } from "../store";
import { embeddingApi } from "../api/client";

export function EmbeddingMonitorView() {
  const { stats, tasks, failureSummary, isLoading, setStats, setTasks, setFailureSummary, setLoading, setError } = useEmbeddingMonitorStore();
  const [filterStatus, setFilterStatus] = useState("all");
  const [retryingTasks, setRetryingTasks] = useState(new Set());

  const loadStats = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await Promise.all([
        embeddingApi.getStats(),
        embeddingApi.getTasks({ limit: 100 }),
        embeddingApi.getFailureSummary(),
      ]);
      setStats(data[0]);
      setTasks(data[1].items);
      setFailureSummary(data[2]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [setStats, setTasks, setFailureSummary, setLoading, setError]);

  useEffect(() => { loadStats(); }, [loadStats]);

  const handleRetry = async (taskId: string) => {
    setRetryingTasks(new Set(retryingTasks).add(taskId));
    try {
      await embeddingApi.retry(taskId);
      await loadStats();
    } catch (err) {
      console.error("Retry failed:", err);
    }
    setRetryingTasks(new Set(retryingTasks));
  };

  const filteredTasks = filterStatus === "all" ? tasks : tasks.filter((t: any) => t.status === filterStatus);

  return (
    <div className="flex flex-col h-full">
      <Header title="嵌入状态监控" subtitle="Embedding 向量化任务状态追踪" onRefresh={loadStats} isRefreshing={isLoading} />
      {stats && (
        <div className="bg-white border-b border-slate-200 p-6">
          <div className="grid grid-cols-5 gap-4">
            <div className="p-4 bg-slate-50 rounded-xl">
              <div className="flex items-center gap-3">
                <Database className="w-5 h-5 text-slate-600" />
                <div>
                  <p className="text-2xl font-bold">{stats.total}</p>
                  <p className="text-xs text-slate-500">总任务数</p>
                </div>
              </div>
            </div>
            <div className="p-4 bg-blue-50 rounded-xl">
              <div className="flex items-center gap-3">
                <Clock className="w-5 h-5 text-blue-600" />
                <div>
                  <p className="text-2xl font-bold text-blue-600">{stats.pending + stats.generating}</p>
                  <p className="text-xs text-blue-500">处理中</p>
                </div>
              </div>
            </div>
            <div className="p-4 bg-green-50 rounded-xl">
              <div className="flex items-center gap-3">
                <CheckCircle2 className="w-5 h-5 text-green-600" />
                <div>
                  <p className="text-2xl font-bold text-green-600">{stats.completed}</p>
                  <p className="text-xs text-green-500">已完成</p>
                </div>
              </div>
            </div>
            <div className="p-4 bg-red-50 rounded-xl">
              <div className="flex items-center gap-3">
                <XCircle className="w-5 h-5 text-red-600" />
                <div>
                  <p className="text-2xl font-bold text-red-600">{stats.failed + stats.permanentFailure}</p>
                  <p className="text-xs text-red-500">失败</p>
                </div>
              </div>
            </div>
            <div className="p-4 bg-amber-50 rounded-xl">
              <div className="flex items-center gap-3">
                <TrendingUp className="w-5 h-5 text-amber-600" />
                <div>
                  <p className="text-2xl font-bold text-amber-600">{stats.total > 0 ? ((stats.completed / stats.total) * 100).toFixed(1) : 0}%</p>
                  <p className="text-xs text-amber-500">完成率</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
      <div className="flex-1 overflow-hidden flex flex-col bg-slate-50">
        <div className="bg-white border-b border-slate-200 px-6 py-3">
          <div className="flex items-center gap-4">
            <span className="text-sm font-medium">任务列表</span>
            <div className="flex gap-2">
              {["all", "pending", "generating", "completed", "failed", "permanent_failure"].map((status) => (
                <button key={status} onClick={() => setFilterStatus(status)} className={`px-3 py-1 text-xs rounded-full ${filterStatus === status ? "bg-blue-100 text-blue-700" : "bg-slate-100 text-slate-600"}`}>
                  {status === "all" ? "全部" : status === "pending" ? "等待中" : status === "generating" ? "生成中" : status === "completed" ? "已完成" : status === "failed" ? "失败" : "永久失败"}
                </button>
              ))}
            </div>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-6">
          {isLoading && tasks.length === 0 ? (
            <div className="flex items-center justify-center h-64"><RefreshCw className="w-8 h-8 text-slate-400 animate-spin" /></div>
          ) : filteredTasks.length === 0 ? (
            <div className="text-center text-slate-500 py-12"><Database className="w-16 h-16 mx-auto mb-4 text-slate-300" /><p className="text-lg font-medium">暂无任务</p></div>
          ) : (
            <div className="space-y-3">
              {filteredTasks.map((task: any) => (
                <div key={task.id} className="bg-white rounded-xl border border-slate-200 p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-sm font-medium text-slate-900 mb-1">记忆 ID: {task.memoryId}</p>
                      <div className="flex items-center gap-3 text-xs text-slate-500">
                        <span className={`px-2 py-0.5 rounded-full ${task.status === "completed" ? "bg-green-100 text-green-600" : task.status === "failed" ? "bg-red-100 text-red-600" : "bg-slate-100 text-slate-600"}`}>
                          {task.status === "pending" ? "等待中" : task.status === "generating" ? "生成中" : task.status === "completed" ? "已完成" : task.status === "failed" ? "失败" : "永久失败"}
                        </span>
                        <span>重试 {task.retryCount}/{task.maxRetries}</span>
                      </div>
                      {task.errorMessage && <p className="mt-2 text-xs text-red-500">{task.errorMessage}</p>}
                    </div>
                    {task.status === "failed" && (
                      <button onClick={() => handleRetry(task.id)} disabled={retryingTasks.has(task.id)} className="flex items-center gap-1 px-3 py-1.5 text-sm text-blue-600 border border-blue-200 rounded-lg hover:bg-blue-50">
                        <RotateCcw className={`w-4 h-4 ${retryingTasks.has(task.id) ? "animate-spin" : ""}`} />
                        重试
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
