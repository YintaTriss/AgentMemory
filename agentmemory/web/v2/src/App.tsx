import { Routes, Route, Navigate } from 'react-router-dom';
import { AppLayout } from '@/components/layout/AppLayout';
import { LibraryTreeView } from '@/views/LibraryTree/LibraryTreeView';
import { MemoryListView } from '@/views/MemoryList/MemoryListView';
import { SearchView } from '@/views/Search/SearchView';
import { MultiAgentMonitorView } from '@/views/MultiAgentMonitor/MultiAgentMonitorView';
import { EmbeddingStatusView } from '@/views/EmbeddingStatus/EmbeddingStatusView';

function App() {
  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<Navigate to="/library" replace />} />
        <Route path="/library" element={<LibraryTreeView />} />
        <Route path="/memories" element={<MemoryListView />} />
        <Route path="/search" element={<SearchView />} />
        <Route path="/agents" element={<MultiAgentMonitorView />} />
        <Route path="/embeddings" element={<EmbeddingStatusView />} />
      </Routes>
    </AppLayout>
  );
}

export default App;
