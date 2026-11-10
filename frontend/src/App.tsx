import React, { useEffect } from 'react';
import { useAppStore, parseRouteFromHash } from './store/useAppStore';
import { StudioNavbar } from './components/layout/StudioNavbar';
import { StudioSidebar } from './components/layout/StudioSidebar';
import { DataForgeHomePage } from './pages/DataForgeHomePage';
import { PipelinesListPage } from './pages/PipelinesListPage';
import { PipelineDesignerPage } from './features/pipeline-designer/PipelineDesignerPage';
import { ConnectionsPage } from './pages/ConnectionsPage';
import { TriggersPage } from './pages/TriggersPage';
import { RunsMonitorPage } from './pages/RunsMonitorPage';
import { DataQualityPage } from './pages/DataQualityPage';
import { DataFlowsListPage } from './features/dataflow-designer/DataFlowsListPage';
import { RuntimesPage } from './pages/RuntimesPage';
import { DatasetsPage } from './pages/DatasetsPage';
import { DeploymentsPage } from './pages/DeploymentsPage';
import { LineagePage } from './pages/LineagePage';
import { ObservabilityPage } from './pages/ObservabilityPage';
import { BillingPage } from './pages/BillingPage';

export const App: React.FC = () => {
  const { currentTab, fetchInitialData, setCurrentTab, setSelectedPipelineId } = useAppStore();

  useEffect(() => {
    fetchInitialData();
  }, [fetchInitialData]);

  // Handle browser back/forward buttons & URL hash changes
  useEffect(() => {
    // If no initial hash present, establish base hash state without adding extra history entry
    if (typeof window !== 'undefined' && !window.location.hash) {
      window.history.replaceState({ tab: 'dashboard', selectedPipelineId: null }, '', '#/dashboard');
    }

    const handleRouteChange = () => {
      const { tab, pipelineId } = parseRouteFromHash(window.location.hash);
      const state = useAppStore.getState();
      if (state.currentTab !== tab) {
        state.setCurrentTab(tab, false);
      }
      if (state.selectedPipelineId !== pipelineId) {
        state.setSelectedPipelineId(pipelineId, false);
      }
    };

    window.addEventListener('popstate', handleRouteChange);
    window.addEventListener('hashchange', handleRouteChange);

    return () => {
      window.removeEventListener('popstate', handleRouteChange);
      window.removeEventListener('hashchange', handleRouteChange);
    };
  }, [setCurrentTab, setSelectedPipelineId]);

  const renderContent = () => {
    switch (currentTab) {
      case 'dashboard':
        return <DataForgeHomePage />;
      case 'pipelines':
        return <PipelinesListPage />;
      case 'designer':
        return <PipelineDesignerPage />;
      case 'dataflows':
        return <DataFlowsListPage />;
      case 'connections':
        return <ConnectionsPage />;
      case 'datasets':
        return <DatasetsPage />;
      case 'runtimes':
        return <RuntimesPage />;
      case 'triggers':
        return <TriggersPage />;
      case 'lineage':
        return <LineagePage />;
      case 'deployments':
        return <DeploymentsPage />;
      case 'runs':
        return <RunsMonitorPage />;
      case 'observability':
        return <ObservabilityPage />;
      case 'dq':
        return <DataQualityPage />;
      case 'billing':
        return <BillingPage />;
      default:
        return <DataForgeHomePage />;
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col font-sans">
      <StudioNavbar />
      <div className="flex-1 flex overflow-hidden">
        <StudioSidebar />
        <main className="flex-1 overflow-y-auto bg-slate-950/50">
          {renderContent()}
        </main>
      </div>
    </div>
  );
};

export default App;
