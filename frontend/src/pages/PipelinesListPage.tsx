import React, { useEffect, useState } from 'react';
import { useAppStore } from '../store/useAppStore';
import { Pipeline } from '../types';
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
  AlertCircle
} from 'lucide-react';

export const PipelinesListPage: React.FC = () => {
  const { pipelines, activeProject, fetchPipelines, setCurrentTab, setSelectedPipelineId } = useAppStore();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [pipelineName, setPipelineName] = useState('');
  const [pipelineDesc, setPipelineDesc] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [triggeringId, setTriggeringId] = useState<string | null>(null);

  useEffect(() => {
    fetchPipelines();
  }, [activeProject]);

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
      alert(`Error triggering pipeline: ${err.response?.data?.detail || err.message}`);
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
      alert(`Error creating pipeline: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">Data Pipelines</h1>
          <p className="text-xs text-slate-400">Visual ETL/ELT workflows, batch synchronization, and orchestration DAGs</p>
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
              className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-slate-700 transition flex flex-col justify-between space-y-4"
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
                        v{pipe.current_version} • {actCount} activities
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

                <div className="mt-3 pt-3 border-t border-slate-800/80 text-[11px] text-slate-500 flex items-center justify-between">
                  <span>Updated</span>
                  <span>{new Date(pipe.updated_at).toLocaleDateString()}</span>
                </div>
              </div>

              {/* Action Buttons */}
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

      {/* Create Pipeline Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="text-sm font-semibold text-white">Create New Pipeline</h3>
              <button onClick={() => setShowCreateModal(false)} className="text-slate-400 hover:text-white">✕</button>
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
