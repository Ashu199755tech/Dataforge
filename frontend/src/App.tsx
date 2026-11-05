import React, { useEffect } from 'react';
import { useAppStore } from './store/useAppStore';
import { Navbar } from './components/layout/Navbar';
import { Sidebar } from './components/layout/Sidebar';
import { DashboardPage } from './pages/DashboardPage';
import { PipelinesListPage } from './pages/PipelinesListPage';
import { PipelineDesignerPage } from './features/pipeline-designer/PipelineDesignerPage';
import { ConnectionsPage } from './pages/ConnectionsPage';
import { TriggersPage } from './pages/TriggersPage';
import { RunsMonitorPage } from './pages/RunsMonitorPage';
import { DataQualityPage } from './pages/DataQualityPage';

export const App: React.FC = () => {
  const { currentTab, fetchInitialData } = useAppStore();

  useEffect(() => {
    fetchInitialData();
  }, [fetchInitialData]);

  const renderContent = () => {
    switch (currentTab) {
      case 'dashboard':
        return <DashboardPage />;
      case 'pipelines':
        return <PipelinesListPage />;
      case 'designer':
        return <PipelineDesignerPage />;
      case 'connections':
        return <ConnectionsPage />;
      case 'triggers':
        return <TriggersPage />;
      case 'runs':
        return <RunsMonitorPage />;
      case 'dq':
        return <DataQualityPage />;
      default:
        return <DashboardPage />;
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col font-sans">
      <Navbar />
      <div className="flex-1 flex overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto bg-slate-950/50">
          {renderContent()}
        </main>
      </div>
    </div>
  );
};

export default App;
