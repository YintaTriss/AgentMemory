// ============================================
// 侧边栏组件
// ============================================

import { 
  Library, 
  FileText, 
  Search, 
  Bot, 
  Database,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import { useUIStore } from '../../store';

interface NavItem {
  id: 'library' | 'memory' | 'search' | 'agents' | 'embedding';
  label: string;
  icon: React.ReactNode;
}

const navItems: NavItem[] = [
  { id: 'library', label: '图书馆', icon: <Library className="w-5 h-5" /> },
  { id: 'memory', label: '记忆列表', icon: <FileText className="w-5 h-5" /> },
  { id: 'search', label: '检索', icon: <Search className="w-5 h-5" /> },
  { id: 'agents', label: 'Agent 监控', icon: <Bot className="w-5 h-5" /> },
  { id: 'embedding', label: '嵌入状态', icon: <Database className="w-5 h-5" /> },
];

export function Sidebar() {
  const { sidebarCollapsed, toggleSidebar, activeView, setActiveView } = useUIStore();

  return (
    <aside 
      className={`
        flex flex-col bg-slate-900 text-white transition-all duration-300
        ${sidebarCollapsed ? 'w-16' : 'w-64'}
      `}
    >
      {/* Logo 区域 */}
      <div className="flex items-center justify-between h-16 px-4 border-b border-slate-700">
        {!sidebarCollapsed && (
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
              <span className="text-sm font-bold">AM</span>
            </div>
            <span className="font-semibold">AgentMemory</span>
          </div>
        )}
        <button
          onClick={toggleSidebar}
          className="p-1.5 rounded-lg hover:bg-slate-700 transition-colors"
          title={sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'}
        >
          {sidebarCollapsed ? <ChevronRight className="w-5 h-5" /> : <ChevronLeft className="w-5 h-5" />}
        </button>
      </div>

      {/* 导航菜单 */}
      <nav className="flex-1 py-4">
        <ul className="space-y-1 px-2">
          {navItems.map((item) => (
            <li key={item.id}>
              <button
                onClick={() => setActiveView(item.id)}
                className={`
                  w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all
                  ${activeView === item.id 
                    ? 'bg-blue-600 text-white' 
                    : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                  }
                `}
                title={sidebarCollapsed ? item.label : undefined}
              >
                {item.icon}
                {!sidebarCollapsed && <span className="font-medium">{item.label}</span>}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {/* 底部信息 */}
      {!sidebarCollapsed && (
        <div className="p-4 border-t border-slate-700">
          <div className="text-xs text-slate-400">
            <p>AgentMemory v2.0</p>
            <p className="mt-1">双轨 + 图书馆架构</p>
          </div>
        </div>
      )}
    </aside>
  );
}
