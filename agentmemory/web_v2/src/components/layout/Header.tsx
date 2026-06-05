// ============================================
// 头部组件
// ============================================

import { Bell, Settings, RefreshCw } from 'lucide-react';

interface HeaderProps {
  title: string;
  subtitle?: string;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export function Header({ title, subtitle, onRefresh, isRefreshing }: HeaderProps) {
  return (
    <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-6">
      {/* 标题 */}
      <div>
        <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
        {subtitle && (
          <p className="text-sm text-slate-500">{subtitle}</p>
        )}
      </div>

      {/* 操作按钮 */}
      <div className="flex items-center gap-2">
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="p-2 rounded-lg hover:bg-slate-100 transition-colors disabled:opacity-50"
            title="刷新"
          >
            <RefreshCw className={`w-5 h-5 text-slate-600 ${isRefreshing ? 'animate-spin' : ''}`} />
          </button>
        )}
        <button 
          className="p-2 rounded-lg hover:bg-slate-100 transition-colors"
          title="通知"
        >
          <Bell className="w-5 h-5 text-slate-600" />
        </button>
        <button 
          className="p-2 rounded-lg hover:bg-slate-100 transition-colors"
          title="设置"
        >
          <Settings className="w-5 h-5 text-slate-600" />
        </button>
      </div>
    </header>
  );
}
