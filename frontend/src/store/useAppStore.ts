import { create } from 'zustand';
import { Workspace, Project, Connection, Pipeline } from '../types';
import api from '../api/client';

interface AppState {
  currentTab: 'dashboard' | 'pipelines' | 'designer' | 'dataflows' | 'connections' | 'datasets' | 'triggers' | 'runs' | 'dq' | 'runtimes';
  selectedPipelineId: string | null;
  workspaces: Workspace[];
  activeWorkspace: Workspace | null;
  projects: Project[];
  activeProject: Project | null;
  connections: Connection[];
  pipelines: Pipeline[];
  isLoading: boolean;
  
  setCurrentTab: (tab: 'dashboard' | 'pipelines' | 'designer' | 'dataflows' | 'connections' | 'datasets' | 'triggers' | 'runs' | 'dq' | 'runtimes') => void;
  setSelectedPipelineId: (id: string | null) => void;
  fetchInitialData: () => Promise<void>;
  fetchConnections: () => Promise<void>;
  fetchPipelines: () => Promise<void>;
}

export const useAppStore = create<AppState>((set, get) => ({
  currentTab: 'dashboard',
  selectedPipelineId: null,
  workspaces: [],
  activeWorkspace: null,
  projects: [],
  activeProject: null,
  connections: [],
  pipelines: [],
  isLoading: false,

  setCurrentTab: (tab) => set({ currentTab: tab }),
  setSelectedPipelineId: (id) => set({ selectedPipelineId: id }),

  fetchInitialData: async () => {
    try {
      set({ isLoading: true });
      const wsRes = await api.get('/workspaces');
      const workspaces: Workspace[] = wsRes.data;
      const activeWs = workspaces.length > 0 ? workspaces[0] : null;

      let projects: Project[] = [];
      let activeProj: Project | null = null;
      if (activeWs) {
        const projRes = await api.get(`/workspaces/${activeWs.id}/projects`);
        projects = projRes.data;
        activeProj = projects.length > 0 ? projects[0] : null;
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
