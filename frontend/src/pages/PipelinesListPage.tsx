import React, { useEffect, useState } from 'react';
import { useAppStore } from '../store/useAppStore';
import { Pipeline, PipelineVersion, Environment } from '../types';
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
  Globe
} from 'lucide-react';

export const PipelinesListPage: React.FC = () => {
  const { pipelines, activeProject, fetchPipelines, setCurrentTab, setSelectedPipelineId } = useAppStore();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [pipelineName, setPipelineName] = useState('');
  const [pipelineDesc, setPipelineDesc] = useState('');
  const [concurrencyLimit, setConcurrencyLimit] = useState(5);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [triggeringId, setTriggeringId] = useState<string | null>(null);

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
      handleOpenDesigner(res.data.id);
    } catch (err: any) {
      showToast(`Error creating pipeline: ${err.response?.data?.detail || err.message}`, 'error');
    } finally {
      setIsSubmitting(false);
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
      // Refresh version drawer list
      const res = await api.get(`/pipelines/${selectedPipeForVersions.id}/versions`);
      setVersionsList(res.data);
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

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto text-slate-200">
      {/* Toast Notification */}
      {notification && (
        <div className={`p-3 rounded-lg text-xs flex items-center justify-between border ${
          notification.type === 'success' 
            ? 'bg-emerald-950/80 border-emerald-500/40 text-emerald-300' 
            : 'bg-rose-950/80 border-rose-500/40 text-rose-300'
        }`}>
          <span>{notification.message}</span>
          <button onClick={() => setNotification(null)} className="text-slate-400 hover:text-white">&times;</button>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <GitBranch className="h-5 w-5 text-brand-400" />
            <h1 className="text-xl font-bold text-white tracking-tight">Data Pipelines</h1>
            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-brand-500/10 text-brand-400 border border-brand-500/20">
              Enterprise CI/CD & RBAC
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Visual ETL/ELT workflows, version snapshots, Dev/Test/Prod promotion, and declarative Git sync
          </p>
        </div>

        <button
          onClick={() => setShowCreateModal(true)}
          className="px-3 py-1.5 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-xs font-medium transition flex items-center gap-1.5 shadow-sm"
        >
          <Plus className="h-3.5 w-3.5" />
          <span>New Pipeline</span>
        </button>
      </div>

      {/* Pipelines Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {pipelines.map((pipe) => {
          const actCount = pipe.definition_json?.activities?.length || 0;
          return (
            <div 
              key={pipe.id} 
              className="p-5 rounded-xl bg-slate-900/90 border border-slate-800 hover:border-slate-700 transition flex flex-col justify-between space-y-4"
            >
              <div>
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2.5">
                    <div className="p-2 rounded-lg bg-brand-600/10 border border-brand-500/30 text-brand-400">
                      <GitBranch className="h-4 w-4" />
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-white">{pipe.name}</h3>
                      <div className="text-[10px] text-slate-500 font-mono">
                        v{pipe.current_version} • {actCount} acts • Concurrency: {pipe.concurrency_limit || 5}
                      </div>
                    </div>
                  </div>

                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium border ${
                    pipe.status === 'Published'
                      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                      : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                  }`}>
                    {pipe.status}
                  </span>
                </div>

                <p className="mt-3 text-xs text-slate-400 line-clamp-2">
                  {pipe.description || 'Configurable visual ingestion and data transformation pipeline.'}
                </p>

                {/* Metadata & Actions row */}
                <div className="mt-3 pt-3 border-t border-slate-800/80 text-[11px] text-slate-500 flex items-center justify-between">
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
              <div className="pt-2 flex items-center justify-between gap-2 text-xs">
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
