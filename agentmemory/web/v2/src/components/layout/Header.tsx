import React from 'react';
import { cn } from '@/utils/cn';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { useAppStore } from '@/stores/appStore';
import { Search, Bell, RefreshCw } from 'lucide-react';
import { systemApi } from '@/api/client';

interface HeaderProps {
  className?: string;
}

const viewTitles: Record<string, string> = {
  library: '图书馆视图',
  memories: '记忆列表',
  search: '检索视图',
  agents: '多 Agent 监控',
  embeddings: '嵌入状态监控',
};

export const Header: React.FC<HeaderProps> = ({ className }) => {
  const { currentView } = useAppStore();
  const [isRefreshing, setIsRefreshing] = React.useState(false);
  const [systemStatus, setSystemStatus] = React.useState<{ status: string; version: string } | null>(null);

  React.useEffect(() => {
    systemApi.health().then(setSystemStatus).catch(console.error);
  }, []);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await systemApi.health();
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <header
      className={cn(
        'flex h-14 items-center justify-between border-b bg-card px-6',
        className
      )}
    >
      {/* Title */}
      <div className="flex items-center space-x-4">
        <h1 className="text-lg font-semibold">{viewTitles[currentView]}</h1>
        {systemStatus && (
          <span className="text-xs text-muted-foreground">
            v{systemStatus.version}
          </span>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center space-x-4">
        {/* Global Search */}
        <div className="relative hidden md:block">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="全局搜索..."
            className="w-64 pl-9"
          />
        </div>

        {/* Refresh */}
        <Button
          variant="ghost"
          size="icon"
          onClick={handleRefresh}
          disabled={isRefreshing}
        >
          <RefreshCw className={cn('h-4 w-4', isRefreshing && 'animate-spin')} />
        </Button>

        {/* Notifications */}
        <Button variant="ghost" size="icon">
          <Bell className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
};

export default Header;
