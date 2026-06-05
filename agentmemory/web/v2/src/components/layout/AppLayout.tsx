import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { cn } from '@/lib/utils';
import {
  Library,
  List,
  Search,
  Bot,
  Database,
  ChevronLeft,
  ChevronRight,
  Menu,
  X,
} from 'lucide-react';

interface NavItem {
  path: string;
  label: string;
  icon: React.ReactNode;
}

const navItems: NavItem[] = [
  { path: '/library', label: '图书馆', icon: <Library className="h-5 w-5" /> },
  { path: '/memories', label: '记忆列表', icon: <List className="h-5 w-5" /> },
  { path: '/search', label: '检索', icon: <Search className="h-5 w-5" /> },
  { path: '/agents', label: 'Agent 监控', icon: <Bot className="h-5 w-5" /> },
  { path: '/embeddings', label: '嵌入状态', icon: <Database className="h-5 w-5" /> },
];

interface AppLayoutProps {
  children: React.ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex h-screen bg-background">
      {/* 桌面端侧边栏 */}
      <aside
        className={cn(
          'hidden md:flex flex-col bg-card border-r border-border transition-all duration-300',
          collapsed ? 'w-16' : 'w-64'
        )}
      >
        {/* Logo 区域 */}
        <div className="flex items-center h-16 px-4 border-b border-border">
          {!collapsed && (
            <div className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center">
                <span className="text-primary-foreground font-bold text-sm">AM</span>
              </div>
              <div className="flex flex-col">
                <span className="font-semibold text-sm">AgentMemory</span>
                <span className="text-xs text-muted-foreground">v2.0</span>
              </div>
            </div>
          )}
          {collapsed && (
            <div className="h-8 w-8 mx-auto rounded-lg bg-primary flex items-center justify-center">
              <span className="text-primary-foreground font-bold text-sm">AM</span>
            </div>
          )}
        </div>

        {/* 导航菜单 */}
        <nav className="flex-1 py-4 px-2 space-y-1">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors',
                  isActive
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                )}
                title={collapsed ? item.label : undefined}
              >
                {item.icon}
                {!collapsed && <span className="font-medium">{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* 折叠按钮 */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center justify-center h-12 border-t border-border text-muted-foreground hover:text-foreground transition-colors"
        >
          {collapsed ? (
            <ChevronRight className="h-5 w-5" />
          ) : (
            <ChevronLeft className="h-5 w-5" />
          )}
        </button>
      </aside>

      {/* 移动端顶部栏 */}
      <div className="md:hidden fixed top-0 left-0 right-0 h-14 bg-card border-b border-border z-50 flex items-center px-4">
        <button
          onClick={() => setMobileOpen(true)}
          className="p-2 -ml-2 text-muted-foreground hover:text-foreground"
        >
          <Menu className="h-5 w-5" />
        </button>
        <div className="flex items-center gap-2 ml-2">
          <div className="h-7 w-7 rounded-lg bg-primary flex items-center justify-center">
            <span className="text-primary-foreground font-bold text-xs">AM</span>
          </div>
          <span className="font-semibold">AgentMemory v2.0</span>
        </div>
      </div>

      {/* 移动端侧边栏 */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-50">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="absolute left-0 top-0 bottom-0 w-64 bg-card border-r border-border">
            <div className="flex items-center justify-between h-14 px-4 border-b border-border">
              <div className="flex items-center gap-2">
                <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center">
                  <span className="text-primary-foreground font-bold text-sm">AM</span>
                </div>
                <div className="flex flex-col">
                  <span className="font-semibold text-sm">AgentMemory</span>
                  <span className="text-xs text-muted-foreground">v2.0</span>
                </div>
              </div>
              <button
                onClick={() => setMobileOpen(false)}
                className="p-1 text-muted-foreground hover:text-foreground"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <nav className="py-4 px-2 space-y-1">
              {navItems.map((item) => {
                const isActive = location.pathname === item.path;
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    onClick={() => setMobileOpen(false)}
                    className={cn(
                      'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors',
                      isActive
                        ? 'bg-primary text-primary-foreground'
                        : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                    )}
                  >
                    {item.icon}
                    <span className="font-medium">{item.label}</span>
                  </Link>
                );
              })}
            </nav>
          </aside>
        </div>
      )}

      {/* 主内容区 */}
      <main className="flex-1 overflow-hidden pt-14 md:pt-0">
        {children}
      </main>
    </div>
  );
}
