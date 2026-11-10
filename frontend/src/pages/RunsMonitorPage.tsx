import React, { useEffect, useState } from 'react';
import { useAppStore } from '../store/useAppStore';
import { PipelineRun, ActivityRun, ExecutionLog, TimelineItem, AlertEvent, AlertRule } from '../types';
import api from '../api/client';
import { 
  PlayCircle, 
  CheckCircle2, 
  XCircle, 
  Clock, 
  RefreshCw, 
  Terminal, 
  Layers, 
  HardDrive,
  FileText,
  Download,
  AlertTriangle,
  RotateCcw,
  Ban,
  Activity,
  Cpu,
  Server,
  Zap,
  BarChart2,
  Bell,
  Search,
  Filter,
  Eye,
  Copy,
  ChevronRight,
  ShieldAlert,
  ArrowRight,
  Database,
  Code,
  ArrowLeft
} from 'lucide-react';

export const RunsMonitorPage: React.FC = () => {
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<PipelineRun | null>(null);
  const [selectedActivity, setSelectedActivity] = useState<ActivityRun | null>(null);
  const [logs, setLogs] = useState<ExecutionLog[]>([]);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [metricsData, setMetricsData] = useState<any>(null);
  const [alertEvents, setAlertEvents] = useState<AlertEvent[]>([]);
  const [activeTab, setActiveTab] = useState<'timeline' | 'activities' | 'metrics' | 'alerts'>('timeline');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [logLevelFilter, setLogLevelFilter] = useState<string>('ALL');
  const [logSearch, setLogSearch] = useState<string>('');
  const [showDiagnosticsModal, setShowDiagnosticsModal] = useState<boolean>(false);
  const [diagnosticsActivity, setDiagnosticsActivity] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isExporting, setIsExporting] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const fetchRuns = async () => {
    try {
      const url = filterStatus === 'all' ? '/runs' : `/runs?status=${filterStatus}`;
      const res = await api.get(url);
      setRuns(res.data);
      if (res.data.length > 0 && !selectedRun) {
        setSelectedRun(res.data[0]);
      }
    } catch (err) {
      console.error('Failed to load runs', err);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchLogs = async (runId: string, activityId: string) => {
    try {
      const res = await api.get(`/runs/${runId}/activities/${activityId}/logs`);
      setLogs(res.data);
    } catch (err) {
      console.error('Failed to fetch activity logs', err);
      setLogs([]);
    }
  };

  const fetchTelemetry = async (runId: string) => {
    try {
      const [timelineRes, metricsRes, alertsRes] = await Promise.all([
        api.get(`/runs/${runId}/timeline`),
        api.get(`/runs/${runId}/metrics`),
        api.get(`/alerts/events?pipeline_run_id=${runId}`)
      ]);
      setTimeline(timelineRes.data.timeline || []);
      setMetricsData(metricsRes.data);
      setAlertEvents(alertsRes.data || []);
    } catch (err) {
      console.error('Failed to fetch run telemetry', err);
    }
  };

  const openDiagnostics = async (runId: string, activityId: string) => {
    try {
      const res = await api.get(`/runs/${runId}/activities/${activityId}/diagnostics`);
      setDiagnosticsActivity(res.data);
      setShowDiagnosticsModal(true);
    } catch (err) {
      console.error('Failed to load diagnostics', err);
    }
  };

  const downloadReport = async (format: 'json' | 'csv' | 'text') => {
    if (!selectedRun) return;
    setIsExporting(true);
    try {
      const res = await api.get(`/runs/${selectedRun.id}/report?format=${format}`, {
        responseType: format === 'json' ? 'json' : 'blob'
      });
      const blob = format === 'json'
        ? new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' })
        : new Blob([res.data], { type: format === 'csv' ? 'text/csv' : 'text/plain' });

      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `dataflow_run_${selectedRun.id.slice(0, 8)}.${format === 'text' ? 'txt' : format}`);
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
    } catch (err) {
      console.error('Failed to export execution report', err);
    } finally {
      setIsExporting(false);
    }
  };

  const handleCancelRun = async () => {
    if (!selectedRun) return;
    try {
      await api.post(`/runs/${selectedRun.id}/cancel`);
      setActionMessage('Execution cancellation requested.');
      fetchRuns();
    } catch (err: any) {
      setActionMessage(`Cancel failed: ${err.response?.data?.detail || err.message}`);
    }
    setTimeout(() => setActionMessage(null), 3000);
  };

  const handleRerunPipeline = async () => {
    if (!selectedRun) return;
    try {
      const res = await api.post(`/runs/${selectedRun.id}/rerun`);
      setActionMessage(`Rerun triggered (New Run ID: ${res.data.id.slice(0, 8)}...)`);
      fetchRuns();
    } catch (err: any) {
      setActionMessage(`Rerun failed: ${err.response?.data?.detail || err.message}`);
    }
    setTimeout(() => setActionMessage(null), 3000);
  };

  useEffect(() => {
    fetchRuns();
    const interval = setInterval(fetchRuns, 4000);
    return () => clearInterval(interval);
  }, [filterStatus]);

  useEffect(() => {
    if (selectedRun) {
      fetchTelemetry(selectedRun.id);
      if (selectedRun.activity_runs?.length > 0 && !selectedActivity) {
        setSelectedActivity(selectedRun.activity_runs[0]);
      }
    }
  }, [selectedRun]);

  useEffect(() => {
    if (selectedRun && selectedActivity) {
      fetchLogs(selectedRun.id, selectedActivity.activity_id);
    }
  }, [selectedRun, selectedActivity]);

  const filteredRuns = runs.filter((r) => {
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    return r.id.toLowerCase().includes(term) || r.pipeline_id.toLowerCase().includes(term);
  });

  const filteredLogs = logs.filter((l) => {
    if (logLevelFilter !== 'ALL' && l.level !== logLevelFilter) return false;
    if (logSearch && !l.message.toLowerCase().includes(logSearch.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto text-slate-200">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div className="flex items-start gap-3">
          <button
            onClick={() => {
              if (window.history.length > 1) {
                window.history.back();
              } else {
                useAppStore.getState().setCurrentTab('dashboard');
              }
            }}
            className="p-2 mt-0.5 rounded-lg bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-400 hover:text-white transition shadow-sm flex items-center justify-center group"
            title="Go back (Alt + Left Arrow)"
          >
            <ArrowLeft className="h-4 w-4 group-hover:-translate-x-0.5 transition-transform" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <Activity className="h-5 w-5 text-brand-400" />
              <h1 className="text-xl font-bold text-white tracking-tight">Monitoring & Observability</h1>
              <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-brand-500/10 text-brand-400 border border-brand-500/20">
                ADF Parity v1.0
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Real-time pipeline Gantt timeline, throughput telemetry, diagnostics, and SLA alerts
            </p>
          </div>
        </div>

        {/* Global Controls */}
        <div className="flex items-center gap-2 flex-wrap">
          <div className="relative">
            <Search className="h-3.5 w-3.5 text-slate-500 absolute left-2.5 top-2.5" />
            <input
              type="text"
              placeholder="Search run ID..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="bg-slate-900 border border-slate-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-brand-500 w-44"
            />
          </div>

          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-brand-500"
          >
            <option value="all">All Statuses</option>
            <option value="Succeeded">Succeeded</option>
            <option value="Failed">Failed</option>
            <option value="Running">Running</option>
            <option value="Cancelled">Cancelled</option>
          </select>

          <button
            onClick={fetchRuns}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
            title="Refresh Runs"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      {actionMessage && (
        <div className="p-3 bg-brand-600/20 border border-brand-500/40 rounded-lg text-xs text-brand-300 flex items-center justify-between">
          <span>{actionMessage}</span>
          <button onClick={() => setActionMessage(null)} className="text-slate-400 hover:text-white">&times;</button>
        </div>
      )}

      {/* Main Grid: Runs List on Left (4 cols), Execution Console on Right (8 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Execution History */}
        <div className="lg:col-span-4 bg-slate-900/90 border border-slate-800 rounded-xl overflow-hidden flex flex-col h-[750px]">
          <div className="p-3 border-b border-slate-800 bg-slate-900/90 font-semibold text-xs text-slate-300 flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5 text-slate-400" />
              Runs Ledger ({filteredRuns.length})
            </span>
            <span className="text-[10px] text-slate-500">Live 4s poll</span>
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-slate-800/80">
            {filteredRuns.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500">No execution runs matched.</div>
            ) : (
              filteredRuns.map((r) => {
                const isSelected = selectedRun?.id === r.id;
                return (
                  <div
                    key={r.id}
                    onClick={() => {
                      setSelectedRun(r);
                      if (r.activity_runs?.length > 0) {
                        setSelectedActivity(r.activity_runs[0]);
                      } else {
                        setSelectedActivity(null);
                      }
                    }}
                    className={`p-3.5 cursor-pointer transition text-xs ${
                      isSelected
                        ? 'bg-brand-600/15 border-l-4 border-brand-500 shadow-inner'
                        : 'hover:bg-slate-800/40'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-slate-200 font-bold">
                            {r.id.substring(0, 8)}
                          </span>
                          <span className={`px-2 py-0.2 rounded-full text-[10px] font-medium border ${
                            r.status === 'Succeeded'
                              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                              : r.status === 'Failed'
                              ? 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                              : r.status === 'Cancelled'
                              ? 'bg-slate-500/10 text-slate-400 border-slate-500/20'
                              : 'bg-brand-500/10 text-brand-400 border-brand-500/20 animate-pulse'
                          }`}>
                            {r.status}
                          </span>
                        </div>
                        <div className="text-[11px] text-slate-400">
                          {r.run_type} • <span className="font-mono">{r.duration_seconds}s</span>
                        </div>
                        <div className="text-[10px] text-slate-500 font-mono">
                          {new Date(r.started_at).toLocaleString()}
                        </div>
                      </div>

                      <div className="text-right space-y-1">
                        <div className="text-[11px] font-semibold text-slate-300">
                          {r.total_rows_written.toLocaleString()} rows
                        </div>
                        <div className="text-[10px] text-slate-500">
                          {r.succeeded_activities}/{r.total_activities} acts
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Observability Console */}
        <div className="lg:col-span-8 space-y-4">
          {selectedRun ? (
            <>
              {/* Executive Summary Bar */}
              <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 flex flex-wrap items-center justify-between gap-4">
                <div className="space-y-0.5">
                  <div className="text-[11px] text-slate-400">Selected Pipeline Run</div>
                  <div className="font-mono text-sm font-bold text-white flex items-center gap-2">
                    {selectedRun.id}
                    <button
                      onClick={() => navigator.clipboard.writeText(selectedRun.id)}
                      className="p-1 hover:text-brand-400 text-slate-500 transition"
                      title="Copy Run ID"
                    >
                      <Copy className="h-3 w-3" />
                    </button>
                  </div>
                </div>

                <div className="flex items-center gap-6 text-xs">
                  <div>
                    <div className="text-slate-500 text-[10px] uppercase tracking-wider">Status</div>
                    <span className={`font-semibold ${
                      selectedRun.status === 'Succeeded' ? 'text-emerald-400' :
                      selectedRun.status === 'Failed' ? 'text-rose-400' : 'text-brand-400'
                    }`}>
                      {selectedRun.status}
                    </span>
                  </div>

                  <div>
                    <div className="text-slate-500 text-[10px] uppercase tracking-wider">Duration</div>
                    <span className="font-mono font-semibold text-slate-200">{selectedRun.duration_seconds}s</span>
                  </div>

                  <div>
                    <div className="text-slate-500 text-[10px] uppercase tracking-wider">Ingested</div>
                    <span className="font-mono font-semibold text-emerald-400">
                      {selectedRun.total_rows_written.toLocaleString()} rows
                    </span>
                  </div>
                </div>

                {/* Run Actions & Download Dropdown */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleRerunPipeline}
                    className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs transition border border-slate-700"
                    title="Rerun Pipeline"
                  >
                    <RotateCcw className="h-3.5 w-3.5 text-brand-400" />
                    <span>Rerun</span>
                  </button>

                  {selectedRun.status === 'Running' && (
                    <button
                      onClick={handleCancelRun}
                      className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-rose-950/60 hover:bg-rose-900 text-rose-300 text-xs transition border border-rose-800"
                      title="Cancel Execution"
                    >
                      <Ban className="h-3.5 w-3.5" />
                      <span>Cancel</span>
                    </button>
                  )}

                  {/* Export Menu */}
                  <div className="flex items-center gap-1 bg-slate-800 rounded-lg p-1 border border-slate-700">
                    <span className="text-[10px] text-slate-400 px-1 font-medium">Export:</span>
                    <button
                      onClick={() => downloadReport('json')}
                      disabled={isExporting}
                      className="px-2 py-0.5 rounded text-[11px] font-mono text-slate-300 hover:bg-slate-700 hover:text-white transition"
                    >
                      JSON
                    </button>
                    <button
                      onClick={() => downloadReport('csv')}
                      disabled={isExporting}
                      className="px-2 py-0.5 rounded text-[11px] font-mono text-slate-300 hover:bg-slate-700 hover:text-white transition"
                    >
                      CSV
                    </button>
                    <button
                      onClick={() => downloadReport('text')}
                      disabled={isExporting}
                      className="px-2 py-0.5 rounded text-[11px] font-mono text-slate-300 hover:bg-slate-700 hover:text-white transition"
                    >
                      TXT
                    </button>
                  </div>
                </div>
              </div>

              {/* Navigation Tabs */}
              <div className="flex items-center gap-1 border-b border-slate-800 text-xs">
                <button
                  onClick={() => setActiveTab('timeline')}
                  className={`flex items-center gap-2 px-4 py-2 font-medium border-b-2 transition ${
                    activeTab === 'timeline'
                      ? 'border-brand-500 text-white bg-slate-800/40'
                      : 'border-transparent text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Clock className="h-3.5 w-3.5 text-brand-400" />
                  <span>Gantt Timeline</span>
                </button>

                <button
                  onClick={() => setActiveTab('activities')}
                  className={`flex items-center gap-2 px-4 py-2 font-medium border-b-2 transition ${
                    activeTab === 'activities'
                      ? 'border-brand-500 text-white bg-slate-800/40'
                      : 'border-transparent text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Layers className="h-3.5 w-3.5 text-emerald-400" />
                  <span>Activities & Logs ({selectedRun.activity_runs?.length || 0})</span>
                </button>

                <button
                  onClick={() => setActiveTab('metrics')}
                  className={`flex items-center gap-2 px-4 py-2 font-medium border-b-2 transition ${
                    activeTab === 'metrics'
                      ? 'border-brand-500 text-white bg-slate-800/40'
                      : 'border-transparent text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <BarChart2 className="h-3.5 w-3.5 text-amber-400" />
                  <span>Throughput & Metrics</span>
                </button>

                <button
                  onClick={() => setActiveTab('alerts')}
                  className={`flex items-center gap-2 px-4 py-2 font-medium border-b-2 transition ${
                    activeTab === 'alerts'
                      ? 'border-brand-500 text-white bg-slate-800/40'
                      : 'border-transparent text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Bell className="h-3.5 w-3.5 text-rose-400" />
                  <span>SLA Alerts ({alertEvents.length})</span>
                </button>
              </div>

              {/* Tab 1: Gantt Timeline View */}
              {activeTab === 'timeline' && (
                <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-4">
                  <div className="flex items-center justify-between text-xs">
                    <div className="font-semibold text-slate-300 uppercase tracking-wider text-[11px]">
                      Activity Execution Gantt Waterfall
                    </div>
                    <div className="flex items-center gap-4 text-[10px] text-slate-400">
                      <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-emerald-500"></span> Succeeded</span>
                      <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-rose-500"></span> Failed</span>
                      <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-brand-500"></span> Running</span>
                      <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-slate-600"></span> Skipped</span>
                    </div>
                  </div>

                  {timeline.length === 0 ? (
                    <div className="p-8 text-center text-xs text-slate-500">No activity timeline telemetry recorded.</div>
                  ) : (
                    <div className="space-y-3 pt-2">
                      {timeline.map((item) => {
                        const statusColor = item.status === 'Succeeded'
                          ? 'bg-emerald-500/80 hover:bg-emerald-400 border-emerald-400'
                          : item.status === 'Failed'
                          ? 'bg-rose-500/80 hover:bg-rose-400 border-rose-400'
                          : item.status === 'Skipped'
                          ? 'bg-slate-600/80 hover:bg-slate-500 border-slate-500'
                          : 'bg-brand-500/80 hover:bg-brand-400 border-brand-400 animate-pulse';

                        return (
                          <div key={item.activity_id} className="space-y-1 text-xs">
                            <div className="flex items-center justify-between text-[11px]">
                              <span className="font-medium text-slate-200 flex items-center gap-2">
                                {item.activity_name} <span className="font-mono text-slate-500 text-[10px]">({item.activity_type})</span>
                                {item.execution_engine && (
                                  <span className={`px-1.5 py-0.2 rounded text-[9px] font-mono border ${
                                    item.execution_engine === 'SQL_PUSHDOWN'
                                      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                                      : item.execution_engine === 'SPARK'
                                      ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                                      : 'bg-sky-500/20 text-sky-300 border-sky-500/30'
                                  }`}>
                                    {item.execution_engine === 'SQL_PUSHDOWN' ? '⚡ SQL Pushdown' : item.execution_engine === 'SPARK' ? '🔥 Spark' : '🚀 Copy Engine'}
                                  </span>
                                )}
                              </span>
                              <div className="flex items-center gap-3 text-[10px]">
                                <span className="text-slate-400 font-mono">Offset: +{item.offset_seconds}s</span>
                                <span className="font-bold text-slate-300 font-mono">{item.duration_seconds}s</span>
                                <button
                                  onClick={() => openDiagnostics(selectedRun.id, item.activity_id)}
                                  className="text-brand-400 hover:text-brand-300 font-medium underline"
                                >
                                  Inspect
                                </button>
                              </div>
                            </div>

                            {/* Waterfall Bar Track */}
                            <div className="w-full bg-slate-950 rounded-md h-6 p-0.5 border border-slate-800/80 relative overflow-hidden">
                              <div
                                style={{
                                  marginLeft: `${item.start_percentage}%`,
                                  width: `${item.width_percentage}%`
                                }}
                                onClick={() => openDiagnostics(selectedRun.id, item.activity_id)}
                                className={`h-full rounded cursor-pointer transition flex items-center justify-between px-2 text-[10px] text-white font-mono shadow-sm border ${statusColor}`}
                              >
                                <span className="truncate">{item.activity_id}</span>
                                <span className="shrink-0">{item.duration_seconds}s</span>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* Tab 2: Activities Breakdown & Logs */}
              {activeTab === 'activities' && (
                <div className="space-y-4">
                  {/* Activity Grid */}
                  <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 space-y-3">
                    <h3 className="text-xs font-semibold text-white uppercase tracking-wider">
                      Activity Ledgers ({selectedRun.activity_runs?.length || 0})
                    </h3>

                    <div className="space-y-2">
                      {selectedRun.activity_runs?.map((act) => {
                        const isActSelected = selectedActivity?.id === act.id;
                        const engine = act.metrics?.execution_engine;
                        const partitionCol = act.metrics?.partition_column;
                        const concurrency = act.metrics?.concurrency_limit;
                        const isPushdown = engine === 'SQL_PUSHDOWN';
                        return (
                          <div
                            key={act.id}
                            onClick={() => setSelectedActivity(act)}
                            className={`p-3 rounded-lg border cursor-pointer transition flex items-center justify-between text-xs ${
                              isActSelected
                                ? 'bg-slate-800/90 border-brand-500'
                                : 'bg-slate-950/70 border-slate-800 hover:border-slate-700'
                            }`}
                          >
                            <div className="flex items-center gap-3">
                              <div className="p-1.5 rounded bg-slate-800 border border-slate-700 text-brand-400">
                                <Layers className="h-3.5 w-3.5" />
                              </div>
                              <div>
                                <div className="font-semibold text-slate-200 flex items-center gap-2 flex-wrap">
                                  <span>{act.activity_name}</span>
                                  {act.error_classification && (
                                    <span className="px-1.5 py-0.2 rounded text-[9px] bg-rose-500/20 text-rose-300 border border-rose-500/30 font-mono">
                                      [{act.error_classification}]
                                    </span>
                                  )}
                                  {engine && (
                                    <span className={`px-1.5 py-0.2 rounded text-[9px] font-mono border flex items-center gap-1 ${
                                      engine === 'SQL_PUSHDOWN'
                                        ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                                        : engine === 'SPARK'
                                        ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                                        : 'bg-sky-500/20 text-sky-300 border-sky-500/30'
                                    }`}>
                                      {engine === 'SQL_PUSHDOWN' ? '⚡ SQL Pushdown' : engine === 'SPARK' ? '🔥 Spark' : '🚀 Copy Engine'}
                                    </span>
                                  )}
                                  {isPushdown && (
                                    <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-teal-500/20 text-teal-300 border border-teal-500/30">
                                      0 Egress
                                    </span>
                                  )}
                                  {partitionCol && (
                                    <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-purple-500/20 text-purple-300 border border-purple-500/30">
                                      ⎇ {concurrency ? `${concurrency}x ` : ''}Part. ({partitionCol})
                                    </span>
                                  )}
                                </div>
                                <div className="text-[10px] text-slate-500 font-mono">
                                  {act.activity_type} • ID: {act.activity_id} • Duration: {act.duration_seconds}s
                                </div>
                              </div>
                            </div>

                            <div className="flex items-center gap-4 text-[11px]">
                              <div>
                                <span className="text-slate-400">Read:</span>{' '}
                                <span className="font-mono font-semibold text-slate-200">
                                  {act.rows_read.toLocaleString()}
                                </span>
                              </div>
                              <div>
                                <span className="text-slate-400">Written:</span>{' '}
                                <span className="font-mono font-semibold text-emerald-400">
                                  {act.rows_written.toLocaleString()}
                                </span>
                              </div>
                              <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                                act.status === 'Succeeded'
                                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                  : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                              }`}>
                                {act.status}
                              </span>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  openDiagnostics(selectedRun.id, act.activity_id);
                                }}
                                className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[10px] font-medium border border-slate-700"
                              >
                                Diagnostics
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Logs Terminal */}
                  <div className="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden">
                    <div className="p-3 bg-slate-900 border-b border-slate-800 flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <Terminal className="h-3.5 w-3.5 text-brand-400" />
                        <span className="text-xs font-semibold text-white">
                          Logs: {selectedActivity?.activity_name || 'Select activity'}
                        </span>
                        <span className="text-[10px] text-slate-500 font-mono">
                          ({filteredLogs.length} lines)
                        </span>
                      </div>

                      {/* Filter controls */}
                      <div className="flex items-center gap-2 text-xs">
                        <input
                          type="text"
                          placeholder="Search logs..."
                          value={logSearch}
                          onChange={(e) => setLogSearch(e.target.value)}
                          className="bg-slate-950 border border-slate-800 rounded px-2 py-1 text-[11px] text-slate-200 focus:outline-none focus:border-brand-500 w-36"
                        />
                        <select
                          value={logLevelFilter}
                          onChange={(e) => setLogLevelFilter(e.target.value)}
                          className="bg-slate-950 border border-slate-800 rounded px-2 py-1 text-[11px] text-slate-300 focus:outline-none focus:border-brand-500"
                        >
                          <option value="ALL">ALL Levels</option>
                          <option value="INFO">INFO</option>
                          <option value="WARNING">WARNING</option>
                          <option value="ERROR">ERROR</option>
                        </select>
                      </div>
                    </div>

                    <div className="p-4 font-mono text-[11px] space-y-1 max-h-64 overflow-y-auto bg-slate-950">
                      {filteredLogs.length === 0 ? (
                        <div className="text-slate-600">No logs emitted matching filter criteria.</div>
                      ) : (
                        filteredLogs.map((log) => (
                          <div key={log.id} className="flex items-start gap-2">
                            <span className="text-slate-500 shrink-0">
                              [{new Date(log.timestamp).toLocaleTimeString()}]
                            </span>
                            <span className={`font-bold shrink-0 ${
                              log.level === 'ERROR'
                                ? 'text-rose-400'
                                : log.level === 'WARNING'
                                ? 'text-amber-400'
                                : 'text-brand-400'
                            }`}>
                              [{log.level}]
                            </span>
                            <span className="text-slate-300 break-all">{log.message}</span>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Tab 3: Throughput & Metrics */}
              {activeTab === 'metrics' && metricsData && (
                <div className="space-y-4">
                  {/* KPI Cards */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-xl space-y-1">
                      <div className="text-[10px] text-slate-400 uppercase font-semibold flex items-center justify-between">
                        <span>Write Throughput</span>
                        <Zap className="h-3.5 w-3.5 text-brand-400" />
                      </div>
                      <div className="text-lg font-bold font-mono text-white">
                        {metricsData.data_movement.write_throughput_rows_sec} <span className="text-xs text-slate-400">rows/s</span>
                      </div>
                      <div className="text-[10px] text-slate-500 font-mono">
                        MB/s: {metricsData.data_movement.throughput_mb_sec} MB/s
                      </div>
                    </div>

                    <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-xl space-y-1">
                      <div className="text-[10px] text-slate-400 uppercase font-semibold flex items-center justify-between">
                        <span>Data Volume</span>
                        <HardDrive className="h-3.5 w-3.5 text-emerald-400" />
                      </div>
                      <div className="text-lg font-bold font-mono text-emerald-400">
                        {metricsData.data_movement.total_mb_processed} <span className="text-xs text-slate-400">MB</span>
                      </div>
                      <div className="text-[10px] text-slate-500 font-mono">
                        {metricsData.data_movement.total_bytes_processed.toLocaleString()} bytes
                      </div>
                    </div>

                    <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-xl space-y-1">
                      <div className="text-[10px] text-slate-400 uppercase font-semibold flex items-center justify-between">
                        <span>Success Rate</span>
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                      </div>
                      <div className="text-lg font-bold font-mono text-white">
                        {metricsData.activity_summary.success_rate_percentage}%
                      </div>
                      <div className="text-[10px] text-slate-500">
                        {metricsData.activity_summary.counts.Succeeded} Succeeded / {metricsData.activity_summary.counts.Total} Total
                      </div>
                    </div>

                    <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-xl space-y-1">
                      <div className="text-[10px] text-slate-400 uppercase font-semibold flex items-center justify-between">
                        <span>Retries</span>
                        <RotateCcw className="h-3.5 w-3.5 text-amber-400" />
                      </div>
                      <div className="text-lg font-bold font-mono text-amber-400">
                        {metricsData.activity_summary.total_retry_attempts}
                      </div>
                      <div className="text-[10px] text-slate-500">
                        Automatic resilience executions
                      </div>
                    </div>
                  </div>

                  {/* Intelligent Execution Engine Analytics */}
                  {metricsData.engine_analytics && (
                    <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-xl space-y-3">
                      <h3 className="text-xs font-semibold text-white uppercase tracking-wider flex items-center justify-between">
                        <span className="flex items-center gap-2">
                          <Zap className="h-3.5 w-3.5 text-brand-400" />
                          Intelligent Execution Engine Analytics
                        </span>
                        <span className="text-[10px] text-slate-400 font-mono font-normal">
                          Empirical Telemetry
                        </span>
                      </h3>

                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2">
                          <div className="text-[10px] text-slate-400 uppercase font-semibold">Engine Distribution</div>
                          <div className="flex flex-wrap items-center gap-1.5 font-mono text-xs">
                            <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                              ⚡ Pushdown: {metricsData.engine_analytics.engine_distribution?.SQL_PUSHDOWN || 0}
                            </span>
                            <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                              🔥 Spark: {metricsData.engine_analytics.engine_distribution?.SPARK || 0}
                            </span>
                            <span className="px-2 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20">
                              🚀 Copy: {metricsData.engine_analytics.engine_distribution?.COPY || 0}
                            </span>
                          </div>
                        </div>

                        <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-1">
                          <div className="text-[10px] text-slate-400 uppercase font-semibold">Cloud Egress Avoided</div>
                          <div className="text-lg font-bold font-mono text-emerald-400">
                            {metricsData.engine_analytics.egress_avoided_mb || 0} <span className="text-xs text-slate-400">MB</span>
                          </div>
                          <div className="text-[10px] text-slate-500">
                            Zero network transfer overhead for in-database transformations
                          </div>
                        </div>

                        <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-1">
                          <div className="text-[10px] text-slate-400 uppercase font-semibold">Parallel Partition Slices</div>
                          <div className="text-lg font-bold font-mono text-purple-400">
                            {metricsData.engine_analytics.total_partition_slices || 0} <span className="text-xs text-slate-400">slices</span>
                          </div>
                          <div className="text-[10px] text-slate-500">
                            Concurrent data chunk workers across activities
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Worker & Environment Details */}
                  <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-xl space-y-2">
                    <h3 className="text-xs font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                      <Server className="h-3.5 w-3.5 text-brand-400" />
                      Worker Execution Environment
                    </h3>

                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-mono pt-2">
                      <div>
                        <div className="text-[10px] text-slate-500">Hostname</div>
                        <div className="font-semibold text-slate-200">{metricsData.worker_info.hostname || 'N/A'}</div>
                      </div>
                      <div>
                        <div className="text-[10px] text-slate-500">Worker PID</div>
                        <div className="font-semibold text-brand-400">{metricsData.worker_info.pid || 'N/A'}</div>
                      </div>
                      <div>
                        <div className="text-[10px] text-slate-500">Platform</div>
                        <div className="font-semibold text-slate-200 truncate">{metricsData.worker_info.platform || 'Linux'}</div>
                      </div>
                      <div>
                        <div className="text-[10px] text-slate-500">Engine Process</div>
                        <div className="font-semibold text-slate-200">{metricsData.worker_info.process_title || 'DataFlow-Worker'}</div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Tab 4: Alerts & Events */}
              {activeTab === 'alerts' && (
                <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-4">
                  <div className="flex items-center justify-between text-xs">
                    <div className="font-semibold text-slate-300 uppercase tracking-wider text-[11px] flex items-center gap-2">
                      <Bell className="h-3.5 w-3.5 text-rose-400" />
                      Alert Notifications Ledger
                    </div>
                    <span className="text-[10px] text-slate-500">{alertEvents.length} events logged</span>
                  </div>

                  {alertEvents.length === 0 ? (
                    <div className="p-8 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-lg">
                      No alert events fired for this execution run. All SLA thresholds and quality boundaries were respected.
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {alertEvents.map((evt) => (
                        <div
                          key={evt.id}
                          className="p-3.5 bg-slate-950 border border-slate-800 rounded-lg space-y-2 text-xs"
                        >
                          <div className="flex items-start justify-between">
                            <div className="flex items-center gap-2">
                              <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                                evt.severity === 'Critical'
                                  ? 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                                  : evt.severity === 'Warning'
                                  ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                                  : 'bg-brand-500/10 text-brand-400 border-brand-500/20'
                              }`}>
                                {evt.severity}
                              </span>
                              <span className="font-semibold text-white">{evt.title}</span>
                            </div>

                            <span className="text-[10px] text-slate-500 font-mono">
                              {new Date(evt.created_at).toLocaleTimeString()}
                            </span>
                          </div>

                          <p className="text-slate-300 text-[11px]">{evt.message}</p>

                          <div className="flex items-center justify-between text-[10px] text-slate-500 font-mono pt-1 border-t border-slate-900">
                            <span>Status: <strong className="text-slate-300">{evt.status}</strong></span>
                            {evt.delivered_at && <span>Delivered: {new Date(evt.delivered_at).toLocaleTimeString()}</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          ) : (
            <div className="p-16 text-center text-slate-500 bg-slate-900/40 border border-slate-800 rounded-xl text-xs">
              Select an execution run on the left to inspect Gantt timeline waterfall, diagnostics, and metrics.
            </div>
          )}
        </div>
      </div>

      {/* Diagnostics Modal / Inspector Drawer */}
      {showDiagnosticsModal && diagnosticsActivity && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-3xl w-full max-h-[85vh] overflow-hidden flex flex-col shadow-2xl">
            {/* Modal Header */}
            <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/90">
              <div className="flex items-center gap-2">
                <ShieldAlert className="h-4 w-4 text-brand-400" />
                <h3 className="font-bold text-white text-sm">
                  Activity Diagnostics: {diagnosticsActivity.activity_name}
                </h3>
              </div>
              <button
                onClick={() => setShowDiagnosticsModal(false)}
                className="text-slate-400 hover:text-white text-lg font-bold"
              >
                &times;
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-5 space-y-4 overflow-y-auto flex-1 text-xs font-mono">
              {/* Classification Banner */}
              {diagnosticsActivity.error_classification && (
                <div className="p-3 bg-rose-950/40 border border-rose-800/60 rounded-lg space-y-1">
                  <div className="text-[10px] uppercase font-bold text-rose-400">
                    Failure Classification: [{diagnosticsActivity.error_classification}]
                  </div>
                  <div className="text-rose-200 text-xs">
                    {diagnosticsActivity.error_message || 'Activity execution error'}
                  </div>
                </div>
              )}

              {/* Execution Summary Table */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-slate-950 p-3 rounded-lg border border-slate-800">
                <div>
                  <div className="text-[10px] text-slate-500">Status</div>
                  <div className="font-bold text-slate-200">{diagnosticsActivity.status}</div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-500">Duration</div>
                  <div className="font-bold text-slate-200">{diagnosticsActivity.duration_seconds}s</div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-500">Retries</div>
                  <div className="font-bold text-brand-400">{diagnosticsActivity.retry_attempt}</div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-500">Rows Written</div>
                  <div className="font-bold text-emerald-400">{diagnosticsActivity.rows_written}</div>
                </div>
              </div>

              {/* Execution Engine & Plan Rationale */}
              {diagnosticsActivity.metrics?.execution_engine && (
                <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-300 text-xs uppercase tracking-wider flex items-center gap-1.5">
                      <Zap className="h-3.5 w-3.5 text-brand-400" />
                      Execution Engine & Planner Rationale
                    </span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-mono border ${
                      diagnosticsActivity.metrics.execution_engine === 'SQL_PUSHDOWN'
                        ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                        : diagnosticsActivity.metrics.execution_engine === 'SPARK'
                        ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                        : 'bg-sky-500/20 text-sky-300 border-sky-500/30'
                    }`}>
                      {diagnosticsActivity.metrics.execution_engine}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-[11px] pt-1">
                    <div>
                      <span className="text-slate-500">Strategy: </span>
                      <span className="font-semibold text-slate-300">
                        {diagnosticsActivity.metrics.planner_strategy || 'AUTO'}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500">Planner Confidence: </span>
                      <span className="font-semibold text-emerald-400">
                        {diagnosticsActivity.metrics.planner_confidence
                          ? `${Math.round(diagnosticsActivity.metrics.planner_confidence * 100)}%`
                          : '100%'}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500">Workload Profile: </span>
                      <span className="font-semibold text-slate-300">
                        {diagnosticsActivity.metrics.execution_engine === 'SQL_PUSHDOWN'
                          ? 'Pushdown-Eligible SQL'
                          : diagnosticsActivity.metrics.execution_engine === 'SPARK'
                          ? 'Distributed Spark DF'
                          : 'Parallel Streaming Copy'}
                      </span>
                    </div>
                  </div>

                  {diagnosticsActivity.metrics.planner_explanation && (
                    <div className="text-[11px] text-slate-400 bg-slate-900/60 p-2 rounded border border-slate-800/80">
                      <span className="text-slate-500 font-semibold">Decision: </span>
                      {diagnosticsActivity.metrics.planner_explanation}
                    </div>
                  )}
                </div>
              )}

              {/* In-Database Pushdown Telemetry & SQL Query Plan */}
              {diagnosticsActivity.metrics?.generated_sql && (
                <div className="space-y-2 p-3 bg-slate-950 border border-emerald-950/60 rounded-lg">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-emerald-400 text-xs uppercase tracking-wider flex items-center gap-1.5">
                      <Code className="h-3.5 w-3.5 text-emerald-400" />
                      Pushdown SQL Execution Plan (0 Network Egress)
                    </span>
                    <button
                      onClick={() => navigator.clipboard.writeText(diagnosticsActivity.metrics.generated_sql)}
                      className="text-emerald-400 hover:text-emerald-300 text-[11px] flex items-center gap-1 font-mono"
                    >
                      <Copy className="h-3 w-3" /> Copy SQL
                    </button>
                  </div>
                  <div className="flex items-center gap-3 text-[10px] text-slate-400">
                    <span>Dialect: <strong className="text-slate-200">{diagnosticsActivity.metrics.pushdown_dialect || 'PostgreSQL'}</strong></span>
                    <span>Egress Avoided: <strong className="text-emerald-400">{((diagnosticsActivity.bytes_processed || 0) / (1024 * 1024)).toFixed(2)} MB</strong></span>
                  </div>
                  <pre className="p-3 bg-slate-900 border border-slate-800 rounded-lg text-emerald-300 text-[10px] overflow-x-auto whitespace-pre-wrap max-h-44 font-mono">
                    {diagnosticsActivity.metrics.generated_sql}
                  </pre>
                </div>
              )}

              {/* Partition Slicing & Checkpoints */}
              {(diagnosticsActivity.metrics?.partition_column || diagnosticsActivity.metrics?.concurrency_limit) && (
                <div className="p-3 bg-slate-950 border border-purple-950/60 rounded-lg space-y-2">
                  <span className="font-semibold text-purple-400 text-xs uppercase tracking-wider flex items-center gap-1.5">
                    <Database className="h-3.5 w-3.5 text-purple-400" />
                    Partition Slicing & Concurrency Telemetry
                  </span>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-[11px]">
                    <div>
                      <span className="text-slate-500">Partition Column: </span>
                      <span className="font-semibold text-slate-300 font-mono">
                        {diagnosticsActivity.metrics.partition_column || 'Row-chunked'}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500">Strategy: </span>
                      <span className="font-semibold text-slate-300 font-mono">
                        {diagnosticsActivity.metrics.partition_strategy || 'DYNAMIC_RANGE'}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500">Concurrent Slices: </span>
                      <span className="font-semibold text-purple-400 font-mono">
                        {diagnosticsActivity.metrics.concurrency_limit || 1} slices
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* Distributed Spark Telemetry */}
              {diagnosticsActivity.metrics?.execution_engine === 'SPARK' && (
                <div className="p-3 bg-slate-950 border border-amber-950/60 rounded-lg space-y-2">
                  <span className="font-semibold text-amber-400 text-xs uppercase tracking-wider flex items-center gap-1.5">
                    <Cpu className="h-3.5 w-3.5 text-amber-400" />
                    Spark Cluster & Session Observability
                  </span>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-[11px]">
                    <div>
                      <span className="text-slate-500">Master: </span>
                      <span className="font-semibold text-slate-300 font-mono">
                        {diagnosticsActivity.metrics.spark_master || 'local[*]'}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500">App ID: </span>
                      <span className="font-semibold text-slate-300 font-mono truncate">
                        {diagnosticsActivity.metrics.spark_app_id || 'spark-df-session'}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500">Stages: </span>
                      <span className="font-semibold text-amber-400 font-mono">
                        {diagnosticsActivity.metrics.spark_stages || 'Stage 0/0 Completed'}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* Retry History Timeline */}
              {diagnosticsActivity.retry_history?.length > 0 && (
                <div className="space-y-2">
                  <div className="font-semibold text-slate-300 text-xs uppercase tracking-wider">
                    Retry Attempt Ledger ({diagnosticsActivity.retry_history.length})
                  </div>
                  <div className="space-y-1.5">
                    {diagnosticsActivity.retry_history.map((att: any, idx: number) => (
                      <div
                        key={idx}
                        className="p-2.5 rounded bg-slate-950 border border-slate-800 flex items-center justify-between"
                      >
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-brand-400">Attempt #{att.attempt + 1}</span>
                          <span className={`px-1.5 py-0.2 rounded text-[10px] ${
                            att.status === 'Succeeded' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
                          }`}>
                            {att.status}
                          </span>
                          {att.error && <span className="text-slate-400 truncate max-w-md">{att.error}</span>}
                        </div>
                        <span className="text-slate-500 text-[10px]">{att.duration_ms}ms</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Stack Trace Viewer */}
              {diagnosticsActivity.error_stack_trace && (
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-300 text-xs uppercase tracking-wider">Error Stack Trace</span>
                    <button
                      onClick={() => navigator.clipboard.writeText(diagnosticsActivity.error_stack_trace)}
                      className="text-brand-400 hover:text-brand-300 text-[11px] flex items-center gap-1"
                    >
                      <Copy className="h-3 w-3" /> Copy Trace
                    </button>
                  </div>
                  <pre className="p-3 bg-slate-950 border border-slate-800 rounded-lg text-rose-300 text-[10px] overflow-x-auto whitespace-pre-wrap max-h-52">
                    {diagnosticsActivity.error_stack_trace}
                  </pre>
                </div>
              )}

              {/* Worker Information */}
              {diagnosticsActivity.worker_info && (
                <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg space-y-1">
                  <div className="text-[10px] text-slate-400 font-bold uppercase">Worker Process Context</div>
                  <div className="text-slate-300 text-[11px]">
                    Host: <span className="text-white">{diagnosticsActivity.worker_info.hostname}</span> • PID: <span className="text-brand-400">{diagnosticsActivity.worker_info.pid}</span> • Thread: <span className="text-slate-400">{diagnosticsActivity.worker_info.thread_id}</span>
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-3 bg-slate-950 border-t border-slate-800 flex justify-end">
              <button
                onClick={() => setShowDiagnosticsModal(false)}
                className="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs transition"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
