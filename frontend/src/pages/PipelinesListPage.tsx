import React, { useEffect, useState } from 'react';
import { useAppStore } from '../store/useAppStore';
import { Pipeline, PipelineVersion, Trigger, PipelineRun } from '../types';
import api from '../api/client';
import { 
  GitBranch, 
  Play, 
  Plus, 
  Clock, 
  Layers, 
  Trash2, 
  FileEdit,
  CheckCircle2, 
  AlertCircle,
  History, 
  RotateCcw, 
  Send, 
  Download, 
  Shield, 
  Tag, 
  Zap, 
  Globe,
  MoreVertical,
  Copy,
  Eye,
  Settings,
  Search,
  Filter,
  X,
  ExternalLink,
  ChevronRight,
  PlayCircle,
  Activity,
  ArrowRight,
  Database,
  RefreshCw,
  Power
} from 'lucide-react';

export const PipelinesListPage: React.FC = () => {
  const { pipelines, activeProject, fetchPipelines, setCurrentTab, setSelectedPipelineId } = useAppStore();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [pipelineName, setPipelineName] = useState('');
  const [pipelineDesc, setPipelineDesc] = useState('');
  const [concurrencyLimit, setConcurrencyLimit] = useState(5);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [triggeringId, setTriggeringId] = useState<string | null>(null);

  // Search & Filter state
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'All' | 'Published' | 'Draft'>('All');

  // Active Dropdown state (3 dots menu)
  const [activeDropdownId, setActiveDropdownId] = useState<string | null>(null);

  // Details Drawer state
  const [selectedPipeForDrawer, setSelectedPipeForDrawer] = useState<Pipeline | null>(null);
  const [drawerTab, setDrawerTab] = useState<'activities' | 'triggers' | 'runs' | 'parameters'>('activities');
  const [drawerTriggers, setDrawerTriggers] = useState<Trigger[]>([]);
  const [drawerRuns, setDrawerRuns] = useState<PipelineRun[]>([]);
  const [loadingDrawerData, setLoadingDrawerData] = useState(false);

  // Versioning & Rollback state
  const [showVersionsModal, setShowVersionsModal] = useState(false);
  const [selectedPipeForVersions, setSelectedPipeForVersions] = useState<Pipeline | null>(null);
  const [versionsList, setVersionsList] = useState<PipelineVersion[]>([]);
  const [isRollingBack, setIsRollingBack] = useState(false);

  // Promotion state
  const [showPromoteModal, setShowPromoteModal] = useState(false);
  const [selectedPipeForPromote, setSelectedPipeForPromote] = useState<Pipeline | null>(null);
  const [targetEnv, setTargetEnv] = useState<string>('Prod');
  const [promoteOverrides, setPromoteOverrides] = useState<string>('{\n  "batch_size": 5000\n}');
  const [isPromoting, setIsPromoting] = useState(false);

  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  useEffect(() => {
    fetchPipelines();
  }, [activeProject]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleDocumentClick = () => {
      setActiveDropdownId(null);
    };
    document.addEventListener('click', handleDocumentClick);
    return () => document.removeEventListener('click', handleDocumentClick);
  }, []);

  // When drawer opens, load attached triggers & runs
  useEffect(() => {
    if (!selectedPipeForDrawer) {
      setDrawerTriggers([]);
      setDrawerRuns([]);
      return;
    }

    const loadDrawerData = async () => {
      setLoadingDrawerData(true);
      try {
        const [trigRes, runsRes] = await Promise.allSettled([
          api.get(`/triggers?pipeline_id=${selectedPipeForDrawer.id}`),
          api.get(`/runs?limit=20`)
        ]);

        if (trigRes.status === 'fulfilled') {
          setDrawerTriggers(trigRes.value.data || []);
        }

        if (runsRes.status === 'fulfilled' && Array.isArray(runsRes.value.data)) {
          const pipeRuns = runsRes.value.data.filter(
            (r: any) => r.pipeline_id === selectedPipeForDrawer.id
          );
          setDrawerRuns(pipeRuns);
        }
      } catch (err) {
        console.error('Failed to load pipeline drawer metadata', err);
      } finally {
        setLoadingDrawerData(false);
      }
    };

    loadDrawerData();
  }, [selectedPipeForDrawer]);

  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 3500);
  };

  const handleOpenDesigner = (pipelineId: string) => {
    setSelectedPipelineId(pipelineId);
    setCurrentTab('designer');
  };

  const handleTriggerRun = async (pipelineId: string) => {
    setTriggeringId(pipelineId);
    try {
      await api.post(`/pipelines/${pipelineId}/run`);
      showToast('Pipeline execution triggered successfully.');
      setCurrentTab('runs');
    } catch (err: any) {
      showToast(`Error triggering pipeline: ${err.response?.data?.detail || err.message}`, 'error');
    } finally {
      setTriggeringId(null);
    }
  };

  const handleCreatePipeline = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProject) return;
    setIsSubmitting(true);
    try {
      const res = await api.post('/pipelines', {
        project_id: activeProject.id,
        name: pipelineName,
        description: pipelineDesc,
        concurrency_limit: concurrencyLimit,
        definition_json: {
          parameters: {},
          variables: {},
          activities: []
        }
      });
      setShowCreateModal(false);
      setPipelineName('');
      setPipelineDesc('');
      await fetchPipelines();
      showToast(`Pipeline '${res.data.name}' created!`);
      handleOpenDesigner(res.data.id);
    } catch (err: any) {
      showToast(`Error creating pipeline: ${err.response?.data?.detail || err.message}`, 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDuplicatePipeline = async (pipe: Pipeline) => {
    try {
      const res = await api.post('/pipelines', {
        project_id: pipe.project_id || activeProject?.id,
        name: `${pipe.name} (Copy)`,
        description: pipe.description ? `Copy of ${pipe.description}` : `Copy of ${pipe.name}`,
        concurrency_limit: pipe.concurrency_limit || 5,
        definition_json: pipe.definition_json || { parameters: {}, variables: {}, activities: [] }
      });
      showToast(`Pipeline duplicated successfully as '${res.data.name}'!`);
      await fetchPipelines();
    } catch (err: any) {
      showToast(`Duplicate failed: ${err.response?.data?.detail || err.message}`, 'error');
    }
  };

  const handleDeletePipeline = async (pipeId: string, pipeName: string) => {
    if (!window.confirm(`Are you sure you want to permanently delete pipeline '${pipeName}'?`)) return;
    try {
      await api.delete(`/pipelines/${pipeId}`);
      showToast(`Pipeline '${pipeName}' deleted.`);
      if (selectedPipeForDrawer?.id === pipeId) {
        setSelectedPipeForDrawer(null);
      }
      await fetchPipelines();
    } catch (err: any) {
      showToast(`Delete failed: ${err.response?.data?.detail || err.message}`, 'error');
    }
  };

  const openVersionsDrawer = async (pipe: Pipeline) => {
    setSelectedPipeForVersions(pipe);
    setShowVersionsModal(true);
    try {
      const res = await api.get(`/pipelines/${pipe.id}/versions`);
      setVersionsList(res.data);
    } catch (err: any) {
      showToast(`Failed to load versions: ${err.message}`, 'error');
    }
  };

  const handleRollback = async (versionNumber: number) => {
    if (!selectedPipeForVersions) return;
    setIsRollingBack(true);
    try {
      await api.post(`/pipelines/${selectedPipeForVersions.id}/rollback`, {
        version_number: versionNumber
      });
      showToast(`Pipeline rolled back to Version ${versionNumber}.`);
      await fetchPipelines();
      const res = await api.get(`/pipelines/${selectedPipeForVersions.id}/versions`);
      setVersionsList(res.data);
      if (selectedPipeForDrawer?.id === selectedPipeForVersions.id) {
        setSelectedPipeForDrawer((prev) => prev ? { ...prev, current_version: versionNumber } : null);
      }
    } catch (err: any) {
      showToast(`Rollback failed: ${err.response?.data?.detail || err.message}`, 'error');
    } finally {
      setIsRollingBack(false);
    }
  };

  const openPromoteModal = (pipe: Pipeline) => {
    setSelectedPipeForPromote(pipe);
    setShowPromoteModal(true);
  };

  const handlePromote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPipeForPromote) return;
    setIsPromoting(true);
    try {
      let overrides = {};
      try {
        overrides = JSON.parse(promoteOverrides);
      } catch (jsonErr) {
        showToast("Invalid JSON in parameter overrides", 'error');
        setIsPromoting(false);
        return;
      }

      await api.post(`/pipelines/${selectedPipeForPromote.id}/promote`, {
        target_environment: targetEnv,
        parameter_overrides: overrides
      });
      showToast(`Pipeline successfully promoted to ${targetEnv}!`);
      setShowPromoteModal(false);
      await fetchPipelines();
    } catch (err: any) {
      showToast(`Promotion failed: ${err.response?.data?.detail || err.message}`, 'error');
    } finally {
      setIsPromoting(false);
    }
  };

  const handleExportGit = async (pipe: Pipeline) => {
    try {
      const res = await api.get(`/pipelines/${pipe.id}/export-git`);
      const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${pipe.name.toLowerCase().replace(/\s+/g, '_')}_git.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      showToast(`Exported declarative Git specification for '${pipe.name}'.`);
    } catch (err: any) {
      showToast(`Export failed: ${err.message}`, 'error');
    }
  };

  // Filtered pipelines based on search and status
  const filteredPipelines = pipelines.filter((pipe) => {
    if (statusFilter !== 'All' && pipe.status !== statusFilter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchName = pipe.name.toLowerCase().includes(q);
      const matchDesc = (pipe.description || '').toLowerCase().includes(q);
      return matchName || matchDesc;
    }
    return true;
  });

  const publishedCount = pipelines.filter(p => p.status === 'Published').length;
  const draftCount = pipelines.filter(p => p.status !== 'Published').length;

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto text-slate-200">
      {/* Toast Notification */}
      {notification && (
        <div className={`p-3 rounded-lg text-xs flex items-center justify-between border shadow-lg ${
          notification.type === 'success' 
            ? 'bg-emerald-950/90 border-emerald-500/50 text-emerald-200' 
            : 'bg-rose-950/90 border-rose-500/50 text-rose-200'
        }`}>
          <span>{notification.message}</span>
          <button onClick={() => setNotification(null)} className="text-slate-400 hover:text-white">&times;</button>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <GitBranch className="h-5 w-5 text-brand-400" />
            <h1 className="text-xl font-bold text-white tracking-tight">Data Pipelines</h1>
            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-brand-500/10 text-brand-400 border border-brand-500/20">
              Enterprise CI/CD & DAG Orchestration
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Visual ETL/ELT workflows, version snapshots, Dev/Test/Prod promotion, and declarative Git sync. Click any pipeline to view details and options.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => fetchPipelines()}
            className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs transition border border-slate-700"
            title="Refresh Pipelines"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-3.5 py-2 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-xs font-medium transition flex items-center gap-1.5 shadow-sm"
          >
            <Plus className="h-4 w-4" />
            <span>New Pipeline</span>
          </button>
        </div>
      </div>

      {/* KPI Stats & Search Filters */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* KPI Pills */}
        <div className="flex items-center gap-2 text-xs">
          <button
            onClick={() => setStatusFilter('All')}
            className={`px-3 py-1.5 rounded-lg font-medium transition border ${
              statusFilter === 'All'
                ? 'bg-brand-600/20 text-brand-300 border-brand-500/40'
                : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'
            }`}
          >
            All Pipelines ({pipelines.length})
          </button>
          <button
            onClick={() => setStatusFilter('Published')}
            className={`px-3 py-1.5 rounded-lg font-medium transition border ${
              statusFilter === 'Published'
                ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'
            }`}
          >
            Published ({publishedCount})
          </button>
          <button
            onClick={() => setStatusFilter('Draft')}
            className={`px-3 py-1.5 rounded-lg font-medium transition border ${
              statusFilter === 'Draft'
                ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'
            }`}
          >
            Draft ({draftCount})
          </button>
        </div>

        {/* Search Input */}
        <div className="relative w-full md:w-72">
          <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-500" />
          <input
            type="text"
            placeholder="Search pipelines..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-slate-900 border border-slate-800 rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-brand-500"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2.5 top-2.5 text-slate-500 hover:text-slate-300"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Pipelines Grid */}
      {filteredPipelines.length === 0 ? (
        <div className="p-12 text-center bg-slate-900/50 border border-slate-800 rounded-xl space-y-3">
          <AlertCircle className="h-8 w-8 text-slate-600 mx-auto" />
          <div className="text-sm font-medium text-slate-300">No pipelines found</div>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            {searchQuery ? 'Try clearing your search query or switching filters.' : 'Get started by creating your first enterprise data pipeline.'}
          </p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-3 py-1.5 bg-brand-600 hover:bg-brand-500 text-white rounded text-xs font-medium"
          >
            Create Pipeline
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredPipelines.map((pipe) => {
            const actCount = pipe.definition_json?.activities?.length || 0;
            const isMenuOpen = activeDropdownId === pipe.id;

            return (
              <div 
                key={pipe.id} 
                onClick={() => setSelectedPipeForDrawer(pipe)}
                className={`p-5 rounded-xl bg-slate-900/90 border transition-all duration-150 flex flex-col justify-between space-y-4 cursor-pointer relative group ${
                  selectedPipeForDrawer?.id === pipe.id
                    ? 'border-brand-500 bg-slate-900 shadow-md shadow-brand-500/10'
                    : 'border-slate-800 hover:border-slate-700 hover:bg-slate-900'
                }`}
              >
                <div>
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2.5">
                      <div className="p-2 rounded-lg bg-brand-600/10 border border-brand-500/30 text-brand-400 group-hover:scale-105 transition-transform">
                        <GitBranch className="h-4 w-4" />
                      </div>
                      <div>
                        <h3 className="text-sm font-semibold text-white group-hover:text-brand-300 transition-colors">
                          {pipe.name}
                        </h3>
                        <div className="text-[10px] text-slate-500 font-mono">
                          v{pipe.current_version} • {actCount} acts • Concurrency: {pipe.concurrency_limit || 5}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium border ${
                        pipe.status === 'Published'
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                          : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                      }`}>
                        {pipe.status}
                      </span>

                      {/* 3-dots Context Menu Button */}
                      <div className="relative">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setActiveDropdownId(isMenuOpen ? null : pipe.id);
                          }}
                          className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-slate-800 transition"
                          title="Pipeline Options"
                        >
                          <MoreVertical className="h-4 w-4" />
                        </button>

                        {/* Dropdown Menu */}
                        {isMenuOpen && (
                          <div 
                            className="absolute right-0 top-7 w-48 bg-slate-950 border border-slate-800 rounded-lg shadow-xl py-1 z-30 text-xs"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <button
                              onClick={() => {
                                setActiveDropdownId(null);
                                handleOpenDesigner(pipe.id);
                              }}
                              className="w-full px-3 py-1.5 text-left text-slate-200 hover:bg-brand-600 hover:text-white flex items-center gap-2 transition"
                            >
                              <FileEdit className="h-3.5 w-3.5" />
                              <span>Open in Designer</span>
                            </button>
                            <button
                              onClick={() => {
                                setActiveDropdownId(null);
                                handleTriggerRun(pipe.id);
                              }}
                              className="w-full px-3 py-1.5 text-left text-emerald-400 hover:bg-emerald-600 hover:text-white flex items-center gap-2 transition"
                            >
                              <Play className="h-3.5 w-3.5" />
                              <span>Run Pipeline Now</span>
                            </button>
                            <button
                              onClick={() => {
                                setActiveDropdownId(null);
                                setSelectedPipeForDrawer(pipe);
                              }}
                              className="w-full px-3 py-1.5 text-left text-slate-200 hover:bg-slate-800 flex items-center gap-2 transition"
                            >
                              <Eye className="h-3.5 w-3.5" />
                              <span>View Pipeline Details</span>
                            </button>
                            <button
                              onClick={() => {
                                setActiveDropdownId(null);
                                setCurrentTab('triggers');
                              }}
                              className="w-full px-3 py-1.5 text-left text-indigo-400 hover:bg-indigo-600 hover:text-white flex items-center gap-2 transition"
                            >
                              <Clock className="h-3.5 w-3.5" />
                              <span>Manage Triggers</span>
                            </button>
                            <button
                              onClick={() => {
                                setActiveDropdownId(null);
                                handleDuplicatePipeline(pipe);
                              }}
                              className="w-full px-3 py-1.5 text-left text-slate-200 hover:bg-slate-800 flex items-center gap-2 transition"
                            >
                              <Copy className="h-3.5 w-3.5" />
                              <span>Duplicate Pipeline</span>
                            </button>
                            <div className="my-1 border-t border-slate-800" />
                            <button
                              onClick={() => {
                                setActiveDropdownId(null);
                                openVersionsDrawer(pipe);
                              }}
                              className="w-full px-3 py-1.5 text-left text-slate-200 hover:bg-slate-800 flex items-center gap-2 transition"
                            >
                              <History className="h-3.5 w-3.5" />
                              <span>Version History</span>
                            </button>
                            <button
                              onClick={() => {
                                setActiveDropdownId(null);
                                openPromoteModal(pipe);
                              }}
                              className="w-full px-3 py-1.5 text-left text-slate-200 hover:bg-slate-800 flex items-center gap-2 transition"
                            >
                              <Send className="h-3.5 w-3.5" />
                              <span>Promote Stage</span>
                            </button>
                            <button
                              onClick={() => {
                                setActiveDropdownId(null);
                                handleExportGit(pipe);
                              }}
                              className="w-full px-3 py-1.5 text-left text-slate-200 hover:bg-slate-800 flex items-center gap-2 transition"
                            >
                              <Download className="h-3.5 w-3.5" />
                              <span>Export Git JSON</span>
                            </button>
                            <div className="my-1 border-t border-slate-800" />
                            <button
                              onClick={() => {
                                setActiveDropdownId(null);
                                handleDeletePipeline(pipe.id, pipe.name);
                              }}
                              className="w-full px-3 py-1.5 text-left text-rose-400 hover:bg-rose-600 hover:text-white flex items-center gap-2 transition"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                              <span>Delete Pipeline</span>
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  <p className="mt-3 text-xs text-slate-400 line-clamp-2">
                    {pipe.description || 'Configurable visual ingestion and data transformation pipeline.'}
                  </p>

                  {/* Metadata & Actions row */}
                  <div 
                    className="mt-3 pt-3 border-t border-slate-800/80 text-[11px] text-slate-500 flex items-center justify-between"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {new Date(pipe.updated_at).toLocaleDateString()}
                    </span>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => openVersionsDrawer(pipe)}
                        className="hover:text-brand-400 transition flex items-center gap-1"
                        title="Inspect Version History & Rollback"
                      >
                        <History className="h-3 w-3" />
                        <span>History</span>
                      </button>
                      <span>•</span>
                      <button
                        onClick={() => openPromoteModal(pipe)}
                        className="hover:text-emerald-400 transition flex items-center gap-1"
                        title="Promote to Test or Prod"
                      >
                        <Send className="h-3 w-3" />
                        <span>Promote</span>
                      </button>
                      <span>•</span>
                      <button
                        onClick={() => handleExportGit(pipe)}
                        className="hover:text-slate-300 transition"
                        title="Export Declarative Git JSON"
                      >
                        <Download className="h-3 w-3" />
                      </button>
                    </div>
                  </div>
                </div>

                {/* Bottom Action Buttons */}
                <div 
                  className="pt-2 flex items-center justify-between gap-2 text-xs"
                  onClick={(e) => e.stopPropagation()}
                >
                  <button
                    onClick={() => handleOpenDesigner(pipe.id)}
                    className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 transition font-medium border border-slate-700/60"
                  >
                    <FileEdit className="h-3.5 w-3.5 text-brand-400" />
                    <span>Open Designer</span>
                  </button>

                  <button
                    onClick={() => handleTriggerRun(pipe.id)}
                    disabled={triggeringId === pipe.id}
                    className="flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white transition font-medium disabled:opacity-50"
                    title="Execute Pipeline Now"
                  >
                    <Play className={`h-3.5 w-3.5 ${triggeringId === pipe.id ? 'animate-spin' : ''}`} />
                    <span>Run</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ================= PIPELINE DETAILS & ACTIONS DRAWER ================= */}
      {selectedPipeForDrawer && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-xs transition-opacity animate-fade-in">
          <div 
            className="w-full max-w-xl bg-slate-900 border-l border-slate-800 h-full flex flex-col justify-between shadow-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Drawer Header */}
            <div className="p-5 border-b border-slate-800 bg-slate-900/90 space-y-3">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-xl bg-brand-600/10 border border-brand-500/30 text-brand-400">
                    <GitBranch className="h-5 w-5" />
                  </div>
                  <div>
                    <h2 className="text-base font-bold text-white tracking-tight">
                      {selectedPipeForDrawer.name}
                    </h2>
                    <div className="text-xs text-slate-400 font-mono mt-0.5 flex items-center gap-2">
                      <span>v{selectedPipeForDrawer.current_version}</span>
                      <span>•</span>
                      <span>Concurrency: {selectedPipeForDrawer.concurrency_limit || 5}</span>
                      <span>•</span>
                      <span>ID: {selectedPipeForDrawer.id.slice(0, 8)}...</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                    selectedPipeForDrawer.status === 'Published'
                      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                      : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                  }`}>
                    {selectedPipeForDrawer.status}
                  </span>
                  <button
                    onClick={() => setSelectedPipeForDrawer(null)}
                    className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>
              </div>

              {selectedPipeForDrawer.description && (
                <p className="text-xs text-slate-300">
                  {selectedPipeForDrawer.description}
                </p>
              )}

              {/* Action Toolbar */}
              <div className="pt-2 flex items-center gap-2 flex-wrap">
                <button
                  onClick={() => handleOpenDesigner(selectedPipeForDrawer.id)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-medium transition shadow-sm"
                >
                  <FileEdit className="h-3.5 w-3.5" />
                  <span>Open in Designer</span>
                </button>

                <button
                  onClick={() => handleTriggerRun(selectedPipeForDrawer.id)}
                  disabled={triggeringId === selectedPipeForDrawer.id}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium transition disabled:opacity-50"
                >
                  <Play className={`h-3.5 w-3.5 ${triggeringId === selectedPipeForDrawer.id ? 'animate-spin' : ''}`} />
                  <span>Run Now</span>
                </button>

                <button
                  onClick={() => {
                    handleDuplicatePipeline(selectedPipeForDrawer);
                  }}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition border border-slate-700"
                >
                  <Copy className="h-3.5 w-3.5" />
                  <span>Duplicate</span>
                </button>

                <button
                  onClick={() => openVersionsDrawer(selectedPipeForDrawer)}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition border border-slate-700"
                >
                  <History className="h-3.5 w-3.5" />
                  <span>History</span>
                </button>

                <button
                  onClick={() => handleDeletePipeline(selectedPipeForDrawer.id, selectedPipeForDrawer.name)}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 text-xs font-medium transition border border-rose-500/30 ml-auto"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  <span>Delete</span>
                </button>
              </div>

              {/* Drawer Tabs */}
              <div className="flex items-center gap-2 border-b border-slate-800 pt-2 text-xs">
                {[
                  { id: 'activities', label: `Activities (${selectedPipeForDrawer.definition_json?.activities?.length || 0})` },
                  { id: 'triggers', label: `Triggers (${drawerTriggers.length})` },
                  { id: 'runs', label: `Recent Runs (${drawerRuns.length})` },
                  { id: 'parameters', label: 'Parameters' }
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setDrawerTab(tab.id as any)}
                    className={`pb-2 px-1 font-medium transition border-b-2 ${
                      drawerTab === tab.id
                        ? 'border-brand-500 text-brand-300'
                        : 'border-transparent text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Drawer Body */}
            <div className="p-5 flex-1 overflow-y-auto space-y-4 text-xs">
              {drawerTab === 'activities' && (
                <div className="space-y-3">
                  {(!selectedPipeForDrawer.definition_json?.activities || selectedPipeForDrawer.definition_json.activities.length === 0) ? (
                    <div className="text-center py-8 text-slate-500 space-y-2">
                      <Layers className="h-6 w-6 mx-auto text-slate-600" />
                      <div>No activities defined in this pipeline yet.</div>
                      <button
                        onClick={() => handleOpenDesigner(selectedPipeForDrawer.id)}
                        className="text-brand-400 hover:underline"
                      >
                        Open Designer to add activities
                      </button>
                    </div>
                  ) : (
                    selectedPipeForDrawer.definition_json.activities.map((act: any, idx: number) => (
                      <div
                        key={act.id || idx}
                        className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2"
                      >
                        <div className="flex items-center justify-between">
                          <div className="font-semibold text-slate-200 flex items-center gap-2">
                            <span className="w-5 h-5 rounded bg-brand-600/20 text-brand-400 text-[10px] flex items-center justify-center font-mono">
                              {idx + 1}
                            </span>
                            <span>{act.name}</span>
                          </div>
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-brand-300 border border-slate-700">
                            {act.type}
                          </span>
                        </div>
                        {act.depends_on && act.depends_on.length > 0 && (
                          <div className="text-[11px] text-slate-500 flex items-center gap-1 font-mono">
                            <ArrowRight className="h-3 w-3" />
                            <span>Depends on: {act.depends_on.map((d: any) => typeof d === 'string' ? d : d.activity_id).join(', ')}</span>
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>
              )}

              {drawerTab === 'triggers' && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400 font-medium">Triggers Linked to this Pipeline:</span>
                    <button
                      onClick={() => setCurrentTab('triggers')}
                      className="text-brand-400 hover:text-brand-300 font-medium flex items-center gap-1"
                    >
                      <Plus className="h-3.5 w-3.5" />
                      <span>New Trigger</span>
                    </button>
                  </div>

                  {loadingDrawerData ? (
                    <div className="text-center py-6 text-slate-500">
                      <RefreshCw className="h-4 w-4 animate-spin mx-auto mb-1 text-brand-400" />
                      Loading triggers...
                    </div>
                  ) : drawerTriggers.length === 0 ? (
                    <div className="text-center py-8 text-slate-500 space-y-2">
                      <Clock className="h-6 w-6 mx-auto text-slate-600" />
                      <div>No automated triggers linked to this pipeline.</div>
                      <button
                        onClick={() => setCurrentTab('triggers')}
                        className="px-3 py-1 bg-brand-600 hover:bg-brand-500 text-white rounded text-xs"
                      >
                        Create Trigger
                      </button>
                    </div>
                  ) : (
                    drawerTriggers.map((trig) => (
                      <div
                        key={trig.id}
                        className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg flex items-center justify-between"
                      >
                        <div className="space-y-0.5">
                          <div className="font-semibold text-slate-200">{trig.name}</div>
                          <div className="text-[11px] text-slate-400 font-mono">
                            {trig.trigger_type} • {trig.cron_expression || 'Event-based'}
                          </div>
                          {trig.next_fire_time && (
                            <div className="text-[10px] text-slate-500">
                              Next: {new Date(trig.next_fire_time).toLocaleString()}
                            </div>
                          )}
                        </div>

                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium border ${
                            trig.is_active
                              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                              : 'bg-slate-800 text-slate-500 border-slate-700'
                          }`}>
                            {trig.is_active ? 'Active' : 'Disabled'}
                          </span>
                          <button
                            onClick={async () => {
                              try {
                                await api.post(`/triggers/${trig.id}/fire-now`);
                                showToast(`Trigger '${trig.name}' dispatched!`);
                                setCurrentTab('runs');
                              } catch (err: any) {
                                showToast(`Fire failed: ${err.message}`, 'error');
                              }
                            }}
                            className="p-1.5 rounded hover:bg-slate-800 text-emerald-400"
                            title="Fire Now"
                          >
                            <Play className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}

              {drawerTab === 'runs' && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400 font-medium">Recent Pipeline Executions:</span>
                    <button
                      onClick={() => setCurrentTab('runs')}
                      className="text-brand-400 hover:text-brand-300 font-medium flex items-center gap-1"
                    >
                      <span>Full Monitor</span>
                      <ChevronRight className="h-3.5 w-3.5" />
                    </button>
                  </div>

                  {loadingDrawerData ? (
                    <div className="text-center py-6 text-slate-500">
                      <RefreshCw className="h-4 w-4 animate-spin mx-auto mb-1 text-brand-400" />
                      Loading run history...
                    </div>
                  ) : drawerRuns.length === 0 ? (
                    <div className="text-center py-8 text-slate-500 space-y-2">
                      <Activity className="h-6 w-6 mx-auto text-slate-600" />
                      <div>No runs recorded for this pipeline yet.</div>
                      <button
                        onClick={() => handleTriggerRun(selectedPipeForDrawer.id)}
                        className="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs"
                      >
                        Execute First Run
                      </button>
                    </div>
                  ) : (
                    drawerRuns.map((r) => (
                      <div
                        key={r.id}
                        onClick={() => setCurrentTab('runs')}
                        className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg flex items-center justify-between cursor-pointer hover:bg-slate-800/40 transition"
                      >
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-white font-bold">{r.id.substring(0, 8)}</span>
                            <span className={`px-2 py-0.2 rounded-full text-[10px] font-medium border ${
                              r.status === 'Succeeded'
                                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                                : r.status === 'Failed'
                                ? 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                                : 'bg-brand-500/10 text-brand-400 border-brand-500/20'
                            }`}>
                              {r.status}
                            </span>
                          </div>
                          <div className="text-[11px] text-slate-400 font-mono">
                            Duration: {r.duration_seconds}s • Rows: {r.total_rows_written.toLocaleString()}
                          </div>
                          <div className="text-[10px] text-slate-500">
                            {new Date(r.started_at).toLocaleString()}
                          </div>
                        </div>

                        <ExternalLink className="h-4 w-4 text-slate-500 hover:text-white" />
                      </div>
                    ))
                  )}
                </div>
              )}

              {drawerTab === 'parameters' && (
                <div className="space-y-3">
                  <div className="font-medium text-slate-400">Default Pipeline Parameters:</div>
                  <pre className="p-3 bg-slate-950 rounded-lg border border-slate-800 text-[11px] font-mono text-slate-300 overflow-x-auto">
                    {JSON.stringify(selectedPipeForDrawer.definition_json?.parameters || {}, null, 2)}
                  </pre>
                  <div className="font-medium text-slate-400 mt-3">Pipeline Variables:</div>
                  <pre className="p-3 bg-slate-950 rounded-lg border border-slate-800 text-[11px] font-mono text-slate-300 overflow-x-auto">
                    {JSON.stringify(selectedPipeForDrawer.definition_json?.variables || {}, null, 2)}
                  </pre>
                </div>
              )}
            </div>

            {/* Drawer Footer */}
            <div className="p-4 border-t border-slate-800 bg-slate-900/90 flex justify-between items-center text-xs">
              <span className="text-slate-500 font-mono">
                Updated: {new Date(selectedPipeForDrawer.updated_at).toLocaleString()}
              </span>
              <button
                onClick={() => setSelectedPipeForDrawer(null)}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300"
              >
                Close Drawer
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Version History Drawer / Modal */}
      {showVersionsModal && selectedPipeForVersions && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-2xl w-full p-6 space-y-4 max-h-[85vh] overflow-hidden flex flex-col">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <History className="h-4 w-4 text-brand-400" />
                <h3 className="text-sm font-semibold text-white">
                  Version History: {selectedPipeForVersions.name}
                </h3>
              </div>
              <button onClick={() => setShowVersionsModal(false)} className="text-slate-400 hover:text-white">&times;</button>
            </div>

            <div className="space-y-3 overflow-y-auto flex-1 pr-1 text-xs">
              {versionsList.map((ver) => {
                const isCurrent = ver.version_number === selectedPipeForVersions.current_version;
                return (
                  <div
                    key={ver.id}
                    className={`p-3.5 rounded-lg border flex items-center justify-between ${
                      isCurrent 
                        ? 'bg-brand-600/10 border-brand-500/40' 
                        : 'bg-slate-950 border-slate-800'
                    }`}
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white font-mono">v{ver.version_number}</span>
                        {isCurrent && (
                          <span className="px-1.5 py-0.2 rounded text-[9px] bg-brand-500/20 text-brand-300 border border-brand-500/30">
                            Current Active
                          </span>
                        )}
                        <span className="px-1.5 py-0.2 rounded text-[9px] bg-slate-800 text-slate-300">
                          {ver.environment_name || 'Dev'}
                        </span>
                      </div>
                      <div className="text-slate-400 text-[11px]">{ver.changelog || 'Snapshot version'}</div>
                      <div className="text-slate-500 text-[10px] font-mono">
                        {new Date(ver.created_at).toLocaleString()}
                      </div>
                    </div>

                    {!isCurrent && (
                      <button
                        onClick={() => handleRollback(ver.version_number)}
                        disabled={isRollingBack}
                        className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs transition border border-slate-700 flex items-center gap-1"
                        title={`Restore pipeline to v${ver.version_number}`}
                      >
                        <RotateCcw className="h-3 w-3 text-amber-400" />
                        <span>Rollback</span>
                      </button>
                    )}
                  </div>
                );
              })}
            </div>

            <div className="pt-3 border-t border-slate-800 flex justify-end">
              <button
                onClick={() => setShowVersionsModal(false)}
                className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs rounded-lg"
              >
                Close History
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Promotion Modal */}
      {showPromoteModal && selectedPipeForPromote && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-lg w-full p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Send className="h-4 w-4 text-emerald-400" />
                <h3 className="text-sm font-semibold text-white">
                  Promote Pipeline: {selectedPipeForPromote.name}
                </h3>
              </div>
              <button onClick={() => setShowPromoteModal(false)} className="text-slate-400 hover:text-white">&times;</button>
            </div>

            <form onSubmit={handlePromote} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Target Environment Stage</label>
                <select
                  value={targetEnv}
                  onChange={(e) => setTargetEnv(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500"
                >
                  <option value="Test">Test (Staging & Integration)</option>
                  <option value="Prod">Prod (Mission-Critical Production)</option>
                  <option value="Dev">Dev (Authoring Sandbox)</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Environment Parameter Overrides (JSON)</label>
                <textarea
                  rows={4}
                  value={promoteOverrides}
                  onChange={(e) => setPromoteOverrides(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-200 font-mono text-xs focus:outline-none focus:border-brand-500"
                  placeholder='{"batch_size": 10000, "target_database": "prod_dw"}'
                />
                <p className="text-[10px] text-slate-500 mt-1">
                  These parameters will be injected into the promoted pipeline definition.
                </p>
              </div>

              <div className="pt-3 border-t border-slate-800 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowPromoteModal(false)}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isPromoting}
                  className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded transition disabled:opacity-50"
                >
                  {isPromoting ? 'Promoting...' : `Deploy to ${targetEnv}`}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Create Pipeline Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="text-sm font-semibold text-white">Create New Pipeline</h3>
              <button onClick={() => setShowCreateModal(false)} className="text-slate-400 hover:text-white">&times;</button>
            </div>

            <form onSubmit={handleCreatePipeline} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Pipeline Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Ingest_Orders_MySQL_to_PG"
                  value={pipelineName}
                  onChange={(e) => setPipelineName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Concurrency Limit</label>
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={concurrencyLimit}
                  onChange={(e) => setConcurrencyLimit(parseInt(e.target.value) || 5)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500 font-mono"
                />
                <p className="text-[10px] text-slate-500 mt-1">Maximum concurrent active runs allowed for this pipeline.</p>
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Description</label>
                <textarea
                  rows={3}
                  placeholder="Purpose of this pipeline, source and target data systems..."
                  value={pipelineDesc}
                  onChange={(e) => setPipelineDesc(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500"
                />
              </div>

              <div className="pt-3 border-t border-slate-800 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-3 py-1.5 bg-brand-600 hover:bg-brand-500 text-white font-medium rounded transition disabled:opacity-50"
                >
                  {isSubmitting ? 'Creating...' : 'Create & Design'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
