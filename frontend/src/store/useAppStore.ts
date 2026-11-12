import { create } from 'zustand';
import { Workspace, Project, Connection, Pipeline } from '../types';
import api from '../api/client';

export type EnvironmentType = 'Development' | 'Testing' | 'Staging' | 'Production';

export type TabType = 
  | 'dashboard' 
  | 'pipelines' 
  | 'designer' 
  | 'dataflows' 
  | 'connections' 
  | 'datasets' 
  | 'triggers' 
  | 'runs' 
  | 'dq' 
  | 'runtimes' 
  | 'deployments' 
  | 'lineage' 
  | 'observability' 
  | 'billing';

export const VALID_TABS: readonly TabType[] = [
  'dashboard', 
  'pipelines', 
  'designer', 
  'dataflows', 
  'connections', 
  'datasets', 
  'triggers', 
  'runs', 
  'dq', 
  'runtimes', 
  'deployments', 
  'lineage', 
  'observability', 
  'billing'
] as const;

export function parseRouteFromHash(hashStr: string): { tab: TabType; pipelineId: string | null } {
  if (!hashStr) return { tab: 'dashboard', pipelineId: null };
  const clean = hashStr.replace(/^#\/?/, '').trim();
  if (!clean) return { tab: 'dashboard', pipelineId: null };

  const parts = clean.split('/');
  const rawTab = parts[0];
  const pipelineId = parts[1] || null;

  const tab: TabType = (VALID_TABS as readonly string[]).includes(rawTab)
    ? (rawTab as TabType)
    : 'dashboard';

  return { tab, pipelineId };
}

export function buildRouteHash(tab: TabType, pipelineId?: string | null): string {
  if (tab === 'designer' && pipelineId) {
    return `#/designer/${pipelineId}`;
  }
  return `#/${tab}`;
}

const initialRoute = typeof window !== 'undefined'
  ? parseRouteFromHash(window.location.hash)
  : { tab: 'dashboard' as TabType, pipelineId: null };

interface AppState {
  currentTab: TabType;
  selectedPipelineId: string | null;
  selectedEnvironment: EnvironmentType;
  isSidebarCollapsed: boolean;
  workspaces: Workspace[];
  activeWorkspace: Workspace | null;
  projects: Project[];
  activeProject: Project | null;
  connections: Connection[];
  pipelines: Pipeline[];
  isLoading: boolean;
  
  setCurrentTab: (tab: TabType, pushHistory?: boolean) => void;
  setSelectedPipelineId: (id: string | null, pushHistory?: boolean) => void;
  setSelectedEnvironment: (env: EnvironmentType) => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleSidebar: () => void;
  setActiveWorkspace: (ws: Workspace) => void;
  setActiveProject: (proj: Project) => void;
  fetchInitialData: () => Promise<void>;
  fetchConnections: () => Promise<void>;
  fetchPipelines: () => Promise<void>;
}

export const useAppStore = create<AppState>((set, get) => ({
  currentTab: initialRoute.tab,
  selectedPipelineId: initialRoute.pipelineId,
  selectedEnvironment: 'Development',
  isSidebarCollapsed: typeof window !== 'undefined' ? localStorage.getItem('dataforge_sidebar_collapsed') === 'true' : false,
  workspaces: [],
  activeWorkspace: null,
  projects: [],
  activeProject: null,
  connections: [],
  pipelines: [],
  isLoading: false,

  setCurrentTab: (tab, pushHistory = true) => {
    const prevTab = get().currentTab;
    const prevPipelineId = get().selectedPipelineId;
    if (prevTab === tab && (!prevPipelineId || tab !== 'designer')) {
      return;
    }

    const newPipelineId = tab === 'designer' ? prevPipelineId : null;
    set({ currentTab: tab, selectedPipelineId: newPipelineId });

    if (pushHistory && typeof window !== 'undefined') {
      const targetHash = buildRouteHash(tab, newPipelineId);
      if (window.location.hash !== targetHash) {
        window.history.pushState({ tab, selectedPipelineId: newPipelineId }, '', targetHash);
      }
    }
  },

  setSelectedPipelineId: (id, pushHistory = true) => {
    set({ selectedPipelineId: id });
    const tab = get().currentTab;
    if (tab === 'designer' && id && pushHistory && typeof window !== 'undefined') {
      const targetHash = buildRouteHash('designer', id);
      if (window.location.hash !== targetHash) {
        window.history.pushState({ tab: 'designer', selectedPipelineId: id }, '', targetHash);
      }
    }
  },
  setSelectedEnvironment: (env) => set({ selectedEnvironment: env }),
  setSidebarCollapsed: (collapsed) => {
    try {
      localStorage.setItem('dataforge_sidebar_collapsed', String(collapsed));
    } catch {}
    set({ isSidebarCollapsed: collapsed });
  },
  toggleSidebar: () => {
    const next = !get().isSidebarCollapsed;
    try {
      localStorage.setItem('dataforge_sidebar_collapsed', String(next));
    } catch {}
    set({ isSidebarCollapsed: next });
  },
  setActiveWorkspace: async (ws) => {
    set({ activeWorkspace: ws });
    try {
      const projRes = await api.get(`/workspaces/${ws.id}/projects`);
      const projects: Project[] = projRes.data;
      const activeProj = projects.length > 0 ? projects[0] : null;
      set({ projects, activeProject: activeProj });
      if (activeProj) {
        await get().fetchConnections();
        await get().fetchPipelines();
      } else {
        set({ connections: [], pipelines: [] });
      }
    } catch (err) {
      console.error('Failed to load projects for workspace', err);
    }
  },
  setActiveProject: (proj) => {
    set({ activeProject: proj });
    get().fetchConnections();
    get().fetchPipelines();
  },

  fetchInitialData: async () => {
    try {
      set({ isLoading: true });
      const wsRes = await api.get('/workspaces');
      const workspaces: Workspace[] = wsRes.data;
      const activeWs = workspaces.find((w) => w.name === 'Default Enterprise Workspace') || (workspaces.length > 0 ? workspaces[0] : null);

      let projects: Project[] = [];
      let activeProj: Project | null = null;
      if (activeWs) {
        const projRes = await api.get(`/workspaces/${activeWs.id}/projects`);
        projects = projRes.data;
        activeProj = projects.find((p) => p.name === 'Core Analytics & Ingestion') || (projects.length > 0 ? projects[0] : null);
      }

      set({
        workspaces,
        activeWorkspace: activeWs,
        projects,
        activeProject: activeProj,
        isLoading: false
      });

      if (activeProj) {
        await get().fetchConnections();
        await get().fetchPipelines();
      }
    } catch (err) {
      console.error('Failed to load initial metadata', err);
      set({ isLoading: false });
    }
  },

  fetchConnections: async () => {
    const { activeProject } = get();
    if (!activeProject) return;
    try {
      const res = await api.get(`/connections?project_id=${activeProject.id}`);
      set({ connections: res.data });
    } catch (err) {
      console.error('Failed to load connections', err);
    }
  },

  fetchPipelines: async () => {
    const { activeProject } = get();
    if (!activeProject) return;
    try {
      const res = await api.get(`/pipelines?project_id=${activeProject.id}`);
      set({ pipelines: res.data });
    } catch (err) {
      console.error('Failed to load pipelines', err);
    }
  }
}));
