import React, { useEffect, useState } from 'react';
import { PipelineRun, ActivityRun, ExecutionLog } from '../types';
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
  FileText
} from 'lucide-react';

export const RunsMonitorPage: React.FC = () => {
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<PipelineRun | null>(null);
  const [selectedActivity, setSelectedActivity] = useState<ActivityRun | null>(null);
  const [logs, setLogs] = useState<ExecutionLog[]>([]);
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [isLoading, setIsLoading] = useState(true);

  const fetchRuns = async () => {
    try {
      const url = filterStatus === 'all' ? '/runs' : `/runs?status=${filterStatus}`;
      const res = await api.get(url);
      setRuns(res.data);
      if (res.data.length > 0 && !selectedRun) {
        setSelectedRun(res.data[0]);
        if (res.data[0].activity_runs?.length > 0) {
          setSelectedActivity(res.data[0].activity_runs[0]);
        }
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

  useEffect(() => {
    fetchRuns();
    const interval = setInterval(fetchRuns, 4000);
    return () => clearInterval(interval);
  }, [filterStatus]);

  useEffect(() => {
    if (selectedRun && selectedActivity) {
      fetchLogs(selectedRun.id, selectedActivity.activity_id);
    }
  }, [selectedRun, selectedActivity]);

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">Pipeline Runs & Monitoring</h1>
          <p className="text-xs text-slate-400">Observability, real-time activity metrics, and execution logs</p>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-slate-300 focus:outline-none focus:border-brand-500"
          >
            <option value="all">All Statuses</option>
            <option value="Succeeded">Succeeded</option>
            <option value="Failed">Failed</option>
            <option value="Running">Running</option>
          </select>

          <button
            onClick={fetchRuns}
            className="p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
            title="Refresh Runs"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Main Grid: Runs Table on Left, Details & Logs on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Runs List */}
        <div className="lg:col-span-5 bg-slate-900/80 border border-slate-800 rounded-xl overflow-hidden flex flex-col h-[700px]">
          <div className="p-3.5 border-b border-slate-800 bg-slate-900 font-semibold text-xs text-slate-300 flex items-center justify-between">
            <span>Execution History ({runs.length})</span>
            <span className="text-[10px] text-slate-500 font-normal">Auto-refresh: 4s</span>
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-slate-800/80">
            {runs.length === 0 ? (
              <div className="p-6 text-center text-xs text-slate-500">No execution runs found.</div>
            ) : (
              runs.map((r) => {
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
                    className={`p-3.5 cursor-pointer transition flex items-start justify-between text-xs ${
                      isSelected
                        ? 'bg-brand-600/10 border-l-4 border-brand-500'
                        : 'hover:bg-slate-800/40'
                    }`}
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-slate-200 font-bold">
                          {r.id.substring(0, 8)}...
                        </span>
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
                      <div className="text-[11px] text-slate-400">
                        Type: <span className="text-slate-300">{r.run_type}</span> • Duration:{' '}
                        <span className="text-slate-300">{r.duration_seconds}s</span>
                      </div>
                      <div className="text-[10px] text-slate-500 font-mono">
                        {new Date(r.started_at).toLocaleString()}
                      </div>
                    </div>

                    <div className="text-right space-y-0.5">
                      <div className="text-[11px] font-semibold text-slate-300">
                        {r.total_rows_written.toLocaleString()} rows
                      </div>
                      <div className="text-[10px] text-slate-500">
                        {r.succeeded_activities} / {r.total_activities} acts
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Activity Breakdown and Logs */}
        <div className="lg:col-span-7 space-y-4">
          {selectedRun ? (
            <>
              {/* Selected Run Summary Banner */}
              <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 flex items-center justify-between">
                <div>
                  <div className="text-xs text-slate-400">Run ID</div>
                  <div className="font-mono text-xs font-bold text-white">{selectedRun.id}</div>
                </div>
                <div>
                  <div className="text-xs text-slate-400">Status</div>
                  <div className="text-xs font-semibold text-emerald-400">{selectedRun.status}</div>
                </div>
                <div>
                  <div className="text-xs text-slate-400">Rows Ingested</div>
                  <div className="font-mono text-xs font-bold text-brand-400">
                    {selectedRun.total_rows_written.toLocaleString()}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-slate-400">Duration</div>
                  <div className="text-xs font-semibold text-slate-300">
                    {selectedRun.duration_seconds} seconds
                  </div>
                </div>
              </div>

              {/* Activity Breakdown List */}
              <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 space-y-3">
                <h3 className="text-xs font-semibold text-white uppercase tracking-wider">
                  Activities ({selectedRun.activity_runs?.length || 0})
                </h3>

                <div className="space-y-2">
                  {selectedRun.activity_runs?.map((act) => {
                    const isActSelected = selectedActivity?.id === act.id;
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
                            <div className="font-semibold text-slate-200">{act.activity_name}</div>
                            <div className="text-[10px] text-slate-500 font-mono">
                              {act.activity_type} • ID: {act.activity_id}
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
                              ? 'bg-emerald-500/10 text-emerald-400'
                              : 'bg-rose-500/10 text-rose-400'
                          }`}>
                            {act.status}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Execution Logs Terminal */}
              <div className="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden">
                <div className="p-3 bg-slate-900 border-b border-slate-800 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Terminal className="h-3.5 w-3.5 text-brand-400" />
                    <span className="text-xs font-semibold text-white">
                      Execution Logs: {selectedActivity?.activity_name || 'Select activity'}
                    </span>
                  </div>
                  <span className="text-[10px] text-slate-500 font-mono">
                    {logs.length} log lines
                  </span>
                </div>

                <div className="p-4 font-mono text-[11px] space-y-1 max-h-64 overflow-y-auto bg-slate-950">
                  {logs.length === 0 ? (
                    <div className="text-slate-600">No logs emitted for this activity run.</div>
                  ) : (
                    logs.map((log) => (
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
            </>
          ) : (
            <div className="p-12 text-center text-slate-500 bg-slate-900/40 border border-slate-800 rounded-xl text-xs">
              Select a pipeline run on the left to inspect activity breakdowns and live logs.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
