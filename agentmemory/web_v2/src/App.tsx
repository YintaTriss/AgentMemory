// ============================================
// AgentMemory v2.0 Web Panel
// 主应用组件
// ============================================

import { MainLayout } from './components/layout';
import { useUIStore } from './store';
import {
  LibraryView,
  MemoryListView,
  SearchView,
  AgentMonitorView,
  EmbeddingMonitorView,
} from './views';

function App() {
  const { activeView } = useUIStore();

  // 根据当前视图渲染对应组件
  const renderView = () => {
    switch (activeView) {
      case 'library':
        return <LibraryView />;
      case 'memory':
        return <MemoryListView />;
      case 'search':
        return <SearchView />;
      case 'agents':
        return <AgentMonitorView />;
      case 'embedding':
        return <EmbeddingMonitorView />;
      default:
        return <LibraryView />;
    }
  };

  return (
    <MainLayout>
      {renderView()}
    </MainLayout>
  );
}

export default App;
