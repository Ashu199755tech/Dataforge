import React, { useEffect, useState } from 'react';
import { useAppStore } from '../store/useAppStore';
import { Trigger, Pipeline } from '../types';
import api from '../api/client';
import { 
  Clock, 
  Plus, 
  Play, 
  Power, 
  Trash2, 
  Calendar, 
  CheckCircle2, 
  XCircle,
  AlertCircle
} from 'lucide-react';

export const TriggersPage: React.FC = () => {
  const { pipelines, fetchPipelines, setCurrentTab } = useAppStore();
  const [triggers, setTriggers] = useState<Trigger[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);

  // Form states
  const [selectedPipelineId, setSelectedPipelineId] = useState('');
  const [triggerName, setTriggerName] = useState('');
  const [cronExpression, setCronExpression] = useState('0 * * * *');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchTriggers = async () => {
    try {
      const res = await api.get('/triggers');
      setTriggers(res.data);
    } catch (err) {
      console.error('Failed to load triggers', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTriggers();
    fetchPipelines();
  }, []);

  const handleToggleActivate = async (trigger: Trigger) => {
    try {
      const endpoint = trigger.is_active ? `/triggers/${trigger.id}/deactivate` : `/triggers/${trigger.id}/activate`;
      await api.post(endpoint);
      fetchTriggers();
    } catch (err: any) {
      alert(`Error toggling trigger: ${err.message}`);
    }
  };

  const handleFireNow = async (triggerId: string) => {
    try {
      await api.post(`/triggers/${triggerId}/fire-now`);
      setCurrentTab('runs');
    } catch (err: any) {
      alert(`Error firing trigger: ${err.message}`);
    }
  };

  const handleDeleteTrigger = async (triggerId: string) => {
    if (!confirm('Are you sure you want to delete this schedule?')) return;
    try {
      await api.delete(`/triggers/${triggerId}`);
      fetchTriggers();
    } catch (err: any) {
      alert(`Error deleting trigger: ${err.message}`);
    }
  };

  const handleCreateTrigger = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPipelineId) return;
    setIsSubmitting(true);
    try {
      await api.post('/triggers', {
        pipeline_id: selectedPipelineId,
        name: triggerName,
        trigger_type: 'cron',
        cron_expression: cronExpression,
        is_active: true,
        parameters: {}
      });
      setShowAddModal(false);
      setTriggerName('');
      fetchTriggers();
    } catch (err: any) {
      alert(`Error creating trigger: ${err.response?.data?.detail || err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const getPipelineName = (pipelineId: string) => {
    const p = pipelines.find((pipe) => pipe.id === pipelineId);
    return p ? p.name : pipelineId;
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">Triggers & Schedules</h1>
          <p className="text-xs text-slate-400">Automated recurrence daemon, cron schedules, and event-driven pipeline execution</p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="px-3 py-1.5 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-xs font-medium transition flex items-center gap-1.5 shadow-sm"
        >
          <Plus className="h-3.5 w-3.5" />
          <span>New Schedule</span>
        </button>
      </div>

      {/* Triggers Table */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl overflow-hidden">
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-300">Configured Triggers ({triggers.length})</span>
          <span className="text-[10px] text-slate-500">Scheduler Daemon Active</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-800/50 text-slate-400 uppercase text-[10px] font-semibold">
              <tr>
                <th className="py-2.5 px-3 rounded-l">Schedule Name</th>
                <th className="py-2.5 px-3">Target Pipeline</th>
                <th className="py-2.5 px-3">Cron Expression</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3">Next Fire Time</th>
                <th className="py-2.5 px-3">Last Fired</th>
                <th className="py-2.5 px-3 rounded-r text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {triggers.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-slate-500 text-xs">
                    No active triggers configured. Click "New Schedule" to create a cron trigger!
                  </td>
                </tr>
              ) : (
                triggers.map((t) => (
                  <tr key={t.id} className="hover:bg-slate-800/30 transition">
                    <td className="py-3 px-3 font-semibold text-slate-200">{t.name}</td>
                    <td className="py-3 px-3 text-brand-400 font-medium">
                      {getPipelineName(t.pipeline_id)}
                    </td>
                    <td className="py-3 px-3 font-mono text-[11px] text-slate-300 bg-slate-950/40 rounded px-2">
                      {t.cron_expression || 'Manual'}
                    </td>
                    <td className="py-3 px-3">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border ${
                        t.is_active
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                          : 'bg-slate-800 text-slate-500 border-slate-700'
                      }`}>
                        {t.is_active ? <CheckCircle2 className="h-2.5 w-2.5" /> : <XCircle className="h-2.5 w-2.5" />}
                        {t.is_active ? 'Active' : 'Disabled'}
                      </span>
                    </td>
                    <td className="py-3 px-3 font-mono text-slate-400 text-[11px]">
                      {t.next_fire_time ? new Date(t.next_fire_time).toLocaleString() : '—'}
                    </td>
                    <td className="py-3 px-3 font-mono text-slate-500 text-[11px]">
                      {t.last_fired_at ? new Date(t.last_fired_at).toLocaleTimeString() : 'Never'}
                    </td>
                    <td className="py-3 px-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => handleFireNow(t.id)}
                          className="p-1.5 rounded hover:bg-slate-800 text-emerald-400 hover:text-emerald-300 transition"
                          title="Trigger Now"
                        >
                          <Play className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => handleToggleActivate(t)}
                          className={`p-1.5 rounded hover:bg-slate-800 transition ${t.is_active ? 'text-amber-400' : 'text-slate-500'}`}
                          title={t.is_active ? 'Disable' : 'Enable'}
                        >
                          <Power className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => handleDeleteTrigger(t.id)}
                          className="p-1.5 rounded hover:bg-slate-800 text-slate-500 hover:text-rose-400 transition"
                          title="Delete"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create Trigger Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="text-sm font-semibold text-white">Create Recurrence Schedule</h3>
              <button onClick={() => setShowAddModal(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <form onSubmit={handleCreateTrigger} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Target Pipeline</label>
                <select
                  required
                  value={selectedPipelineId}
                  onChange={(e) => setSelectedPipelineId(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500"
                >
                  <option value="">Select pipeline to schedule...</option>
                  {pipelines.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Schedule Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Daily_Midnight_Ingestion"
                  value={triggerName}
                  onChange={(e) => setTriggerName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Cron Expression (UTC)</label>
                <input
                  type="text"
                  required
                  placeholder="0 * * * * (hourly)"
                  value={cronExpression}
                  onChange={(e) => setCronExpression(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500 font-mono"
                />
                <div className="mt-1 text-[10px] text-slate-500">
                  Examples: <span className="font-mono text-slate-400">0 * * * *</span> (hourly), <span className="font-mono text-slate-400">0 0 * * *</span> (daily midnight), <span className="font-mono text-slate-400">*/15 * * * *</span> (every 15 min)
                </div>
              </div>

              <div className="pt-3 border-t border-slate-800 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-3 py-1.5 bg-brand-600 hover:bg-brand-500 text-white font-medium rounded transition disabled:opacity-50"
                >
                  {isSubmitting ? 'Creating...' : 'Activate Schedule'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
