import React from 'react';
import { cn } from '@/utils/cn';
import { useAppStore } from '@/stores/appStore';
import { Button } from '@/components/ui/button';
import { Tooltip } from '@/components/ui/tooltip';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Library,
  ListTodo,
  Search,
  Bot,
  Database,
  ChevronLeft,
  ChevronRight,
  Sun,
  Moon,
} from 'lucide-react';

interface NavItem {
  id: 'library' | 'memories' | 'search' | 'agents' | 'embeddings';
  label: string;
  icon: React.ReactNode;
  description: string;
}

const navItems: NavItem[] = [
  { id: 'library', label: '图书馆', icon: <Library className="h-5 w-5" />, description: '浏览分类树' },
  { id: 'memories', label: '记忆列表', icon: <ListTodo className="h-5 w-5" />, description: '查看所有记忆' },
  { id: 'search', label: '检索', icon: <Search className="h-5 w-5" />, description: '双轨检索记忆' },
  { id: 'agents', label: 'Agent 监控', icon: <Bot className="h-5 w-5" />, description: '监控多 Agent 活动' },
  { id: 'embeddings', label: '嵌入状态', icon: <Database className="h-5 w-5" />, description: 'Embedding 任务状态' },
];

interface SidebarProps {
  className?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({ className }) => {
  const { currentView, setCurrentView, sidebarCollapsed, toggleSidebar } = useAppStore();
  const [darkMode, setDarkMode] = React.useState(false);

  const toggleDarkMode = () => {
    setDarkMode(!darkMode);
    document.documentElement.classList.toggle('dark');
  };

  return (
    <aside
      className={cn(
        'flex flex-col border-r bg-card transition-all duration-300',
        sidebarCollapsed ? 'w-16' : 'w-64',
        className
      )}
    >
      {/* Logo */}
      <div className="flex h-14 items-center justify-between border-b px-4">
        {!sidebarCollapsed && (
          <span className="font-semibold text-lg">AgentMemory</span>
        )}
        <Button variant="ghost" size="icon" onClick={toggleSidebar}>
          {sidebarCollapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </Button>
      </div>

      {/* Navigation */}
      <ScrollArea className="flex-1 py-4">
        <nav className="space-y-1 px-2">
          {navItems.map((item) => {
            const isActive = currentView === item.id;
            const button = (
              <Button
                key={item.id}
                variant={isActive ? 'secondary' : 'ghost'}
                className={cn(
                  'w-full justify-start',
                  sidebarCollapsed && 'justify-center px-2'
                )}
                onClick={() => setCurrentView(item.id)}
              >
                {item.icon}
                {!sidebarCollapsed && <span className="ml-2">{item.label}</span>}
              </Button>
            );

            return sidebarCollapsed ? (
              <Tooltip key={item.id} content={item.description} side="right">
                {button}
              </Tooltip>
            ) : (
              button
            );
          })}
        </nav>
      </ScrollArea>

      {/* Footer */}
      <div className="border-t p-4">
        <Tooltip content={darkMode ? '切换亮色模式' : '切换暗色模式'} side="right">
          <Button variant="ghost" size="icon" onClick={toggleDarkMode} className="w-full">
            {darkMode ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
        </Tooltip>
      </div>
    </aside>
  );
};

export default Sidebar;
