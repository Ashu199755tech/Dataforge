import React, { useState, useEffect } from 'react';
import { useAppStore } from '../store/useAppStore';
import api from '../api/client';
import { 
  ObservabilityOverview, 
  CopyDataPerformanceMetrics, 
  RuntimeFleetOverview, 
  FailureDiagnosticsResponse, 
  AlertRule, 
  AlertEvent,
  OtelTraceResponse,
  PipelineRun
} from '../types';
import { 
  Activity, 
  Server, 
  AlertTriangle, 
  CheckCircle2, 
  XCircle, 
  Clock, 
  Cpu, 
  HardDrive, 
  Zap, 
  RefreshCw, 
  Send, 
  Bell, 
  Sliders, 
  ExternalLink, 
  Copy, 
  Check, 
  Layers, 
  Filter, 
  Search, 
  ChevronRight, 
  Terminal, 
  BarChart2, 
  AlertCircle,
  Eye,
  Plus,
  ShieldAlert,
  Play,
  ArrowLeft
} from 'lucide-react';
import { 
  ResponsiveContainer, 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  Tooltip, 
  CartesianGrid 
} from 'recharts';

export const ObservabilityPage: React.FC = () => {
  const { activeProject } = useAppStore();

  const [activeTab, setActiveTab] = useState<'copy_perf' | 'fleet_health' | 'diagnostics' | 'alerts' | 'telemetry'>('copy_perf');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [autoRefresh, setAutoRefresh] = useState<boolean>(false);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<Date>(new Date());

  // Data states
  const [overview, setOverview] = useState<ObservabilityOverview | null>(null);
  const [copyPerf, setCopyPerf] = useState<CopyDataPerformanceMetrics | null>(null);
  const [fleet, setFleet] = useState<RuntimeFleetOverview | null>(null);
  const [diagnostics, setDiagnostics] = useState<FailureDiagnosticsResponse | null>(null);
  const [alertRules, setAlertRules] = useState<AlertRule[]>([]);
  const [alertEvents, setAlertEvents] = useState<AlertEvent[]>([]);
  const [runs, setRuns] = useState<PipelineRun[]>([]);

  // OpenTelemetry state
  const [selectedRunIdForTrace, setSelectedRunIdForTrace] = useState<string>('');
  const [activeTrace, setActiveTrace] = useState<OtelTraceResponse | null>(null);
  const [isLoadingTrace, setIsLoadingTrace] = useState<boolean>(false);

  // Prometheus live metrics preview
  const [prometheusRawText, setPrometheusRawText] = useState<string>('');
  const [copiedPrometheus, setCopiedPrometheus] = useState<boolean>(false);

  // Modals
  const [showCreateAlertModal, setShowCreateAlertModal] = useState<boolean>(false);
  const [selectedPayloadEvent, setSelectedPayloadEvent] = useState<AlertEvent | null>(null);

  // Create alert form state
  const [newAlertName, setNewAlertName] = useState<string>('');
  const [newAlertTargetType, setNewAlertTargetType] = useState<string>('Pipeline');
  const [newAlertConditionType, setNewAlertConditionType] = useState<string>('OnFailure');
  const [newAlertActionType, setNewAlertActionType] = useState<string>('Teams');
  const [newAlertEndpoint, setNewAlertEndpoint] = useState<string>('');
  const [newAlertCooldown, setNewAlertCooldown] = useState<number>(5);
  const [isSubmittingAlert, setIsSubmittingAlert] = useState<boolean>(false);

  const fetchData = async () => {
    if (!activeProject) return;
    setIsLoading(true);
    try {
      const [ovRes, copyRes, fleetRes, diagRes, rulesRes, eventsRes, runsRes] = await Promise.all([
        api.get(`/observability/overview?project_id=${activeProject.id}`),
        api.get(`/observability/copy-performance?project_id=${activeProject.id}&limit=50`),
        api.get(`/observability/fleet-health?project_id=${activeProject.id}`),
        api.get(`/observability/failure-diagnostics?project_id=${activeProject.id}&days=7`),
        api.get('/alerts/rules'),
        api.get('/alerts/events'),
        api.get('/runs?status=all')
      ]);

      setOverview(ovRes.data);
      setCopyPerf(copyRes.data);
      setFleet(fleetRes.data);
      setDiagnostics(diagRes.data);
      setAlertRules(rulesRes.data || []);
      setAlertEvents(eventsRes.data || []);
      setRuns(runsRes.data || []);

      if (runsRes.data && runsRes.data.length > 0 && !selectedRunIdForTrace) {
        setSelectedRunIdForTrace(runsRes.data[0].id);
      }

      setLastRefreshedAt(new Date());
    } catch (err) {
      console.error('Failed to load observability data:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [activeProject]);

  useEffect(() => {
    let interval: any = null;
    if (autoRefresh) {
      interval = setInterval(() => {
        fetchData();
      }, 10000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [autoRefresh, activeProject]);

  const loadTrace = async (runId: string) => {
    if (!runId) return;
    setIsLoadingTrace(true);
    try {
      const res = await api.get(`/observability/traces/${runId}`);
      setActiveTrace(res.data);
    } catch (err) {
      console.error('Failed to fetch OpenTelemetry trace:', err);
      setActiveTrace(null);
    } finally {
      setIsLoadingTrace(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'telemetry') {
      if (selectedRunIdForTrace) {
        loadTrace(selectedRunIdForTrace);
      }
      // Fetch Prometheus raw
      api.get('/observability/metrics').then(res => {
        setPrometheusRawText(res.data);
      }).catch(err => {
        console.error('Failed to preview prometheus metrics:', err);
      });
    }
  }, [activeTab, selectedRunIdForTrace]);

  const handleCreateAlertRule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newAlertName.trim() || !newAlertEndpoint.trim()) return;

    setIsSubmittingAlert(true);
    try {
      let actionConfig: Record<string, any> = {};
      if (newAlertActionType === 'Teams' || newAlertActionType === 'Slack' || newAlertActionType === 'Webhook') {
        actionConfig = { webhook_url: newAlertEndpoint };
      } else if (newAlertActionType === 'Email') {
        actionConfig = { 
          recipients: newAlertEndpoint.split(',').map(s => s.trim()),
          smtp_host: 'localhost'
        };
      }

      await api.post('/alerts/rules', {
        name: newAlertName,
        target_type: newAlertTargetType,
        condition_type: newAlertConditionType,
        action_type: newAlertActionType,
        action_config: actionConfig,
        cooldown_minutes: newAlertCooldown,
        is_enabled: true
      });

      setShowCreateAlertModal(false);
      setNewAlertName('');
      setNewAlertEndpoint('');
      // Refresh rules
      const rulesRes = await api.get('/alerts/rules');
      setAlertRules(rulesRes.data || []);
    } catch (err) {
      console.error('Failed to create alert rule:', err);
    } finally {
      setIsSubmittingAlert(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedPrometheus(true);
    setTimeout(() => setCopiedPrometheus(false), 2000);
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-5">
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
          <div className="flex items-center gap-3">
            <div className="p-2 bg-brand-500/10 border border-brand-500/20 rounded-lg text-brand-400">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
                Advanced Observability & Telemetry
                <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
                  Enterprise Suite
                </span>
              </h1>
              <p className="text-xs text-slate-400 mt-0.5">
                Real-time Copy Data performance, runtime fleet capacity, root cause error clustering, multi-channel alerts & OpenTelemetry tracing.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
              autoRefresh 
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' 
                : 'bg-slate-900 text-slate-400 border-slate-800 hover:text-slate-200'
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${autoRefresh ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'}`} />
            Auto-refresh {autoRefresh ? '(10s)' : 'Off'}
          </button>

          <button
            onClick={fetchData}
            disabled={isLoading}
            className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg border border-slate-700 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-brand-400' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Executive Telemetry Metric Badges */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* 24h Success Rate */}
        <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl p-4 shadow-sm backdrop-blur-sm">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium mb-1.5">
            <span>24h Success Rate</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-100 font-mono">
              {overview ? overview.success_rate_24h_pct : 100}%
            </span>
            <span className="text-[11px] text-slate-500">pipeline executions</span>
          </div>
          <div className="w-full bg-slate-800 h-1.5 rounded-full mt-3 overflow-hidden">
            <div 
              className="bg-emerald-500 h-full rounded-full transition-all"
              style={{ width: `${overview ? overview.success_rate_24h_pct : 100}%` }}
            />
          </div>
        </div>

        {/* Runtime Fleet Health */}
        <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl p-4 shadow-sm backdrop-blur-sm">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium mb-1.5">
            <span>Fleet CPU Utilization</span>
            <Cpu className="w-4 h-4 text-brand-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-100 font-mono">
              {fleet ? fleet.fleet_cpu_usage_pct : 0}%
            </span>
            <span className="text-[11px] text-slate-500">
              {fleet ? `${fleet.online_count}/${fleet.total_runtimes} online` : '0 online'}
            </span>
          </div>
          <div className="w-full bg-slate-800 h-1.5 rounded-full mt-3 overflow-hidden">
            <div 
              className={`h-full rounded-full transition-all ${
                (fleet?.fleet_cpu_usage_pct || 0) > 80 ? 'bg-rose-500' : 'bg-brand-500'
              }`}
              style={{ width: `${fleet ? Math.min(fleet.fleet_cpu_usage_pct, 100) : 0}%` }}
            />
          </div>
        </div>

        {/* Copy Data Throughput */}
        <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl p-4 shadow-sm backdrop-blur-sm">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium mb-1.5">
            <span>Avg Copy Throughput</span>
            <Zap className="w-4 h-4 text-amber-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-100 font-mono">
              {copyPerf ? copyPerf.average_throughput_mb_sec : 0}
            </span>
            <span className="text-[11px] text-slate-400 font-mono">MB/s</span>
            <span className="text-[11px] text-slate-500 ml-auto">
              Peak: {copyPerf ? copyPerf.peak_throughput_mb_sec : 0} MB/s
            </span>
          </div>
          <div className="text-[11px] text-slate-500 mt-2 truncate">
            Total volume: <span className="text-slate-300 font-mono">{copyPerf?.total_bytes_human || '0 B'}</span>
          </div>
        </div>

        {/* Fleet Task Concurrency */}
        <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl p-4 shadow-sm backdrop-blur-sm">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium mb-1.5">
            <span>Fleet Active Slots</span>
            <Server className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-100 font-mono">
              {fleet ? fleet.active_tasks : 0}
            </span>
            <span className="text-[11px] text-slate-400 font-mono">
              / {fleet ? fleet.total_concurrency_capacity : 0} slots
            </span>
          </div>
          <div className="w-full bg-slate-800 h-1.5 rounded-full mt-3 overflow-hidden">
            <div 
              className="bg-indigo-500 h-full rounded-full transition-all"
              style={{ 
                width: `${fleet && fleet.total_concurrency_capacity > 0 
                  ? Math.min((fleet.active_tasks / fleet.total_concurrency_capacity) * 100, 100) 
                  : 0}%` 
              }}
            />
          </div>
        </div>
      </div>

      {/* Module Navigation Tabs */}
      <div className="flex items-center gap-1 border-b border-slate-800">
        <button
          onClick={() => setActiveTab('copy_perf')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-medium border-b-2 transition-all ${
            activeTab === 'copy_perf'
              ? 'border-brand-500 text-brand-400 bg-brand-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700'
          }`}
        >
          <Zap className="w-4 h-4" />
          Copy Data Performance
        </button>

        <button
          onClick={() => setActiveTab('fleet_health')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-medium border-b-2 transition-all ${
            activeTab === 'fleet_health'
              ? 'border-brand-500 text-brand-400 bg-brand-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700'
          }`}
        >
          <Cpu className="w-4 h-4" />
          Runtime Fleet Telemetry
        </button>

        <button
          onClick={() => setActiveTab('diagnostics')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-medium border-b-2 transition-all ${
            activeTab === 'diagnostics'
              ? 'border-brand-500 text-brand-400 bg-brand-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700'
          }`}
        >
          <AlertCircle className="w-4 h-4" />
          Failure Diagnostics & Root Causes
        </button>

        <button
          onClick={() => setActiveTab('alerts')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-medium border-b-2 transition-all ${
            activeTab === 'alerts'
              ? 'border-brand-500 text-brand-400 bg-brand-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700'
          }`}
        >
          <Bell className="w-4 h-4" />
          Multi-Channel Alert Rules & Stream
        </button>

        <button
          onClick={() => setActiveTab('telemetry')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-medium border-b-2 transition-all ${
            activeTab === 'telemetry'
              ? 'border-brand-500 text-brand-400 bg-brand-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700'
          }`}
        >
          <Terminal className="w-4 h-4" />
          OpenTelemetry & Prometheus Scraper
        </button>
      </div>

      {/* TAB 1: Copy Data Performance */}
      {activeTab === 'copy_perf' && (
        <div className="space-y-6">
          {/* Key Cards Row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 bg-slate-900/40 border border-slate-800 rounded-lg">
              <span className="text-[11px] text-slate-400 uppercase tracking-wider block">Total Moved Rows</span>
              <span className="text-xl font-bold font-mono text-slate-100 mt-1 block">
                {copyPerf?.total_rows_transferred.toLocaleString() || 0}
              </span>
            </div>
            <div className="p-4 bg-slate-900/40 border border-slate-800 rounded-lg">
              <span className="text-[11px] text-slate-400 uppercase tracking-wider block">Total Transferred Volume</span>
              <span className="text-xl font-bold font-mono text-brand-400 mt-1 block">
                {copyPerf?.total_bytes_human || '0 B'}
              </span>
            </div>
            <div className="p-4 bg-slate-900/40 border border-slate-800 rounded-lg">
              <span className="text-[11px] text-slate-400 uppercase tracking-wider block">Peak Throughput</span>
              <span className="text-xl font-bold font-mono text-emerald-400 mt-1 block">
                {copyPerf?.peak_throughput_mb_sec || 0} MB/s
              </span>
            </div>
            <div className="p-4 bg-slate-900/40 border border-slate-800 rounded-lg">
              <span className="text-[11px] text-slate-400 uppercase tracking-wider block">Rejected / Corrupt Rows</span>
              <span className={`text-xl font-bold font-mono mt-1 block ${
                (copyPerf?.total_rejected_rows || 0) > 0 ? 'text-amber-400' : 'text-slate-300'
              }`}>
                {copyPerf?.total_rejected_rows || 0}
              </span>
            </div>
          </div>

          {/* Area Chart: Throughput Over Time */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 mb-4 flex items-center gap-2">
              <BarChart2 className="w-4 h-4 text-brand-400" />
              Throughput Trend (Hourly Average MB/s)
            </h3>
            <div className="h-64 w-full">
              {copyPerf && copyPerf.throughput_trend && copyPerf.throughput_trend.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={copyPerf.throughput_trend} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="tpGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#0284c7" stopOpacity={0.8}/>
                        <stop offset="95%" stopColor="#0284c7" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="hour" stroke="#64748b" tick={{ fontSize: 11 }} />
                    <YAxis stroke="#64748b" tick={{ fontSize: 11 }} unit=" MB/s" />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', fontSize: '12px' }} 
                    />
                    <Area 
                      type="monotone" 
                      dataKey="throughput_mb_sec" 
                      stroke="#38bdf8" 
                      strokeWidth={2}
                      fillOpacity={1} 
                      fill="url(#tpGradient)" 
                      name="Throughput (MB/s)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-xs text-slate-500">
                  No copy data activity runs recorded yet in this project.
                </div>
              )}
            </div>
          </div>

          {/* Ledger Table: Recent Transfers */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden">
            <div className="px-5 py-3 border-b border-slate-800 flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                Recent Data Movement Transfer Ledger
              </h3>
              <span className="text-xs text-slate-500 font-mono">
                {copyPerf?.recent_transfers.length || 0} transfers
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950/60 text-slate-400 font-medium border-b border-slate-800">
                  <tr>
                    <th className="py-2.5 px-4">Activity Name</th>
                    <th className="py-2.5 px-4">Pipeline</th>
                    <th className="py-2.5 px-4 text-right">Rows Read/Written</th>
                    <th className="py-2.5 px-4 text-right">Rejected</th>
                    <th className="py-2.5 px-4 text-right">Transferred Size</th>
                    <th className="py-2.5 px-4 text-right">Duration</th>
                    <th className="py-2.5 px-4 text-right">Throughput</th>
                    <th className="py-2.5 px-4">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {copyPerf && copyPerf.recent_transfers.length > 0 ? (
                    copyPerf.recent_transfers.map((tx) => (
                      <tr key={tx.activity_id} className="hover:bg-slate-800/30 transition-colors font-mono">
                        <td className="py-3 px-4 font-sans font-medium text-slate-200">
                          {tx.activity_name}
                        </td>
                        <td className="py-3 px-4 text-slate-400 font-sans">
                          {tx.pipeline_name}
                        </td>
                        <td className="py-3 px-4 text-right text-slate-300">
                          {tx.rows_read.toLocaleString()} / {tx.rows_written.toLocaleString()}
                        </td>
                        <td className="py-3 px-4 text-right">
                          {tx.rejected_rows > 0 ? (
                            <span className="text-rose-400 font-semibold">{tx.rejected_rows}</span>
                          ) : (
                            <span className="text-slate-500">0</span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-right text-brand-300">
                          {tx.bytes_human}
                        </td>
                        <td className="py-3 px-4 text-right text-slate-400">
                          {tx.duration_seconds.toFixed(1)}s
                        </td>
                        <td className="py-3 px-4 text-right">
                          <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-brand-500/10 text-brand-400 border border-brand-500/20">
                            {tx.throughput_mb_sec} MB/s
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-sans font-semibold ${
                            tx.status === 'Succeeded' 
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                              : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                          }`}>
                            {tx.status}
                          </span>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={8} className="py-8 text-center text-slate-500">
                        No copy data activity execution history found.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: Runtime Fleet Health */}
      {activeTab === 'fleet_health' && (
        <div className="space-y-6">
          {/* Capacity Gauges Row */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
              <div className="flex items-center justify-between text-xs text-slate-400 mb-2 font-medium">
                <span>Fleet CPU Utilization</span>
                <span className="font-mono text-slate-200">{fleet?.fleet_cpu_usage_pct || 0}%</span>
              </div>
              <div className="w-full bg-slate-800 h-2.5 rounded-full overflow-hidden">
                <div 
                  className={`h-full rounded-full transition-all ${
                    (fleet?.fleet_cpu_usage_pct || 0) > 85 ? 'bg-rose-500' : 'bg-brand-500'
                  }`}
                  style={{ width: `${fleet?.fleet_cpu_usage_pct || 0}%` }}
                />
              </div>
              <span className="text-[11px] text-slate-500 mt-2 block">
                Aggregated average across all registered online compute agents.
              </span>
            </div>

            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
              <div className="flex items-center justify-between text-xs text-slate-400 mb-2 font-medium">
                <span>Fleet RAM Utilization</span>
                <span className="font-mono text-slate-200">{fleet?.fleet_memory_usage_pct || 0}%</span>
              </div>
              <div className="w-full bg-slate-800 h-2.5 rounded-full overflow-hidden">
                <div 
                  className="bg-purple-500 h-full rounded-full transition-all"
                  style={{ width: `${fleet?.fleet_memory_usage_pct || 0}%` }}
                />
              </div>
              <span className="text-[11px] text-slate-500 mt-2 block">
                Total active working memory assigned to execution pods.
              </span>
            </div>

            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
              <div className="flex items-center justify-between text-xs text-slate-400 mb-2 font-medium">
                <span>Concurrency Slots Utilization</span>
                <span className="font-mono text-slate-200">
                  {fleet?.active_tasks || 0} / {fleet?.total_concurrency_capacity || 0}
                </span>
              </div>
              <div className="w-full bg-slate-800 h-2.5 rounded-full overflow-hidden">
                <div 
                  className="bg-indigo-500 h-full rounded-full transition-all"
                  style={{ 
                    width: `${fleet && fleet.total_concurrency_capacity > 0 
                      ? (fleet.active_tasks / fleet.total_concurrency_capacity) * 100 
                      : 0}%` 
                  }}
                />
              </div>
              <span className="text-[11px] text-slate-500 mt-2 block">
                Concurrent activity task execution slots available in the cluster.
              </span>
            </div>
          </div>

          {/* Node Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {fleet && fleet.runtimes.length > 0 ? (
              fleet.runtimes.map((rt) => (
                <div key={rt.id} className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 hover:border-slate-700 transition-all">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <div className="p-1.5 bg-slate-800 rounded-md text-brand-400">
                        <Cpu className="w-4 h-4" />
                      </div>
                      <div>
                        <h4 className="text-xs font-bold text-slate-200">{rt.name}</h4>
                        <span className="text-[10px] text-slate-400 font-mono">
                          {rt.runtime_type} • {rt.agent_os || 'Linux'}
                        </span>
                      </div>
                    </div>
                    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                      rt.status === 'Online'
                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                        : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                    }`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${rt.status === 'Online' ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'}`} />
                      {rt.status}
                    </span>
                  </div>

                  <div className="space-y-3 pt-2 border-t border-slate-800/80 text-xs">
                    <div>
                      <div className="flex justify-between text-[11px] text-slate-400 mb-1">
                        <span>CPU ({rt.cpu_cores} cores)</span>
                        <span className="font-mono text-slate-300">{rt.cpu_usage_pct.toFixed(1)}%</span>
                      </div>
                      <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                        <div 
                          className="bg-brand-500 h-full rounded-full" 
                          style={{ width: `${Math.min(rt.cpu_usage_pct, 100)}%` }} 
                        />
                      </div>
                    </div>

                    <div>
                      <div className="flex justify-between text-[11px] text-slate-400 mb-1">
                        <span>Memory</span>
                        <span className="font-mono text-slate-300">
                          {(rt.memory_used_bytes / (1024 * 1024 * 1024)).toFixed(1)} / {(rt.memory_total_bytes / (1024 * 1024 * 1024)).toFixed(1)} GB ({rt.memory_usage_pct.toFixed(1)}%)
                        </span>
                      </div>
                      <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                        <div 
                          className="bg-purple-500 h-full rounded-full" 
                          style={{ width: `${Math.min(rt.memory_usage_pct, 100)}%` }} 
                        />
                      </div>
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1">
                      <span>Active Tasks: <strong className="text-slate-200 font-mono">{rt.active_tasks} / {rt.concurrency_limit}</strong></span>
                      <span className="text-slate-500 text-[10px]">
                        HB: {rt.last_heartbeat_at ? new Date(rt.last_heartbeat_at).toLocaleTimeString() : 'N/A'}
                      </span>
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="col-span-full py-12 text-center text-slate-500">
                No integration runtimes registered. Navigate to Integration Runtimes to provision agents.
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: Failure Diagnostics & Error Clustering */}
      {activeTab === 'diagnostics' && (
        <div className="space-y-6">
          <div className="flex items-center justify-between bg-slate-900/40 p-4 border border-slate-800 rounded-xl">
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
                Automated Root Cause Diagnostics & Error Clusters
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Analyzed {diagnostics?.total_failures || 0} failed pipeline runs across past {diagnostics?.period_days || 7} days.
              </p>
            </div>
            <span className="px-3 py-1 rounded-full text-xs font-mono bg-rose-500/10 text-rose-400 border border-rose-500/20">
              {diagnostics?.clusters.length || 0} recurring error patterns
            </span>
          </div>

          <div className="space-y-4">
            {diagnostics && diagnostics.clusters.length > 0 ? (
              diagnostics.clusters.map((cluster, idx) => (
                <div key={idx} className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-all">
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 mb-3">
                    <div className="flex items-center gap-2.5">
                      <div className="p-2 bg-rose-500/10 border border-rose-500/20 rounded-lg text-rose-400">
                        <AlertTriangle className="w-4 h-4" />
                      </div>
                      <div>
                        <h4 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                          {cluster.error_category}
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono">
                            {cluster.occurrence_count} occurrences
                          </span>
                        </h4>
                        <span className="text-[11px] text-slate-400">
                          Last seen: {cluster.last_seen_at ? new Date(cluster.last_seen_at).toLocaleString() : 'Recently'}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-[11px] text-slate-400 font-medium">Affected:</span>
                      <div className="flex flex-wrap gap-1">
                        {cluster.affected_pipelines.slice(0, 3).map((p, i) => (
                          <span key={i} className="text-[10px] px-2 py-0.5 bg-slate-800 text-brand-300 rounded border border-slate-700">
                            {p}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Sample Raw Error Snippet */}
                  <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/80 font-mono text-xs text-rose-300/90 overflow-x-auto my-3">
                    {cluster.sample_error}
                  </div>

                  {/* Remediation Box */}
                  {cluster.suggested_remediation && (
                    <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg flex items-start gap-2.5 text-xs text-emerald-300">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                      <div>
                        <strong className="font-semibold block text-emerald-200">Suggested Automated Remediation:</strong>
                        <span>{cluster.suggested_remediation}</span>
                      </div>
                    </div>
                  )}
                </div>
              ))
            ) : (
              <div className="bg-slate-900/30 border border-slate-800 rounded-xl p-12 text-center text-slate-400">
                <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
                <p className="text-sm font-medium text-slate-200">Zero Critical Failures Detected</p>
                <p className="text-xs text-slate-500 mt-1">All pipelines and activities executed without recurring error clusters.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 4: Multi-Channel Alert Rules & Stream */}
      {activeTab === 'alerts' && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
                Multi-Channel Alert Rules & Cooldown Suppression
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Send notifications to Microsoft Teams, Slack, Email, and Webhooks with automatic deduplication.
              </p>
            </div>
            <button
              onClick={() => setShowCreateAlertModal(true)}
              className="flex items-center gap-2 px-3 py-1.5 bg-brand-600 hover:bg-brand-500 text-white text-xs font-medium rounded-lg shadow-sm transition-colors"
            >
              <Plus className="w-4 h-4" />
              Create Alert Rule
            </button>
          </div>

          {/* Rules Table */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden">
            <div className="px-5 py-3 border-b border-slate-800">
              <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                Configured Alert Rules ({alertRules.length})
              </h4>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950/60 text-slate-400 font-medium border-b border-slate-800">
                  <tr>
                    <th className="py-2.5 px-4">Rule Name</th>
                    <th className="py-2.5 px-4">Target Type</th>
                    <th className="py-2.5 px-4">Condition</th>
                    <th className="py-2.5 px-4">Channel</th>
                    <th className="py-2.5 px-4 text-center">Cooldown</th>
                    <th className="py-2.5 px-4">Last Fired</th>
                    <th className="py-2.5 px-4">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {alertRules.length > 0 ? (
                    alertRules.map((r) => (
                      <tr key={r.id} className="hover:bg-slate-800/30 transition-colors">
                        <td className="py-3 px-4 font-semibold text-slate-200">
                          {r.name}
                        </td>
                        <td className="py-3 px-4 text-slate-400">
                          {r.target_type}
                        </td>
                        <td className="py-3 px-4 text-amber-400 font-mono">
                          {r.condition_type}
                        </td>
                        <td className="py-3 px-4">
                          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-brand-500/10 text-brand-300 border border-brand-500/20">
                            {r.action_type}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-center font-mono text-slate-400">
                          {r.cooldown_minutes || 5} min
                        </td>
                        <td className="py-3 px-4 text-slate-500 text-[11px]">
                          {r.last_triggered_at ? new Date(r.last_triggered_at).toLocaleTimeString() : 'Never'}
                        </td>
                        <td className="py-3 px-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                            r.is_enabled 
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                              : 'bg-slate-800 text-slate-400'
                          }`}>
                            {r.is_enabled ? 'Active' : 'Disabled'}
                          </span>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={7} className="py-6 text-center text-slate-500">
                        No alert rules created yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Alert Events Stream */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden">
            <div className="px-5 py-3 border-b border-slate-800 flex items-center justify-between">
              <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                Live Alert Events Audit Stream ({alertEvents.length})
              </h4>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950/60 text-slate-400 font-medium border-b border-slate-800">
                  <tr>
                    <th className="py-2.5 px-4">Severity</th>
                    <th className="py-2.5 px-4">Alert Title</th>
                    <th className="py-2.5 px-4">Message</th>
                    <th className="py-2.5 px-4">Triggered At</th>
                    <th className="py-2.5 px-4">Delivery Status</th>
                    <th className="py-2.5 px-4 text-right">Payload</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {alertEvents.length > 0 ? (
                    alertEvents.map((ev) => (
                      <tr key={ev.id} className="hover:bg-slate-800/30 transition-colors">
                        <td className="py-3 px-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            ev.severity === 'Critical'
                              ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                              : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                          }`}>
                            {ev.severity}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-semibold text-slate-200">
                          {ev.title}
                        </td>
                        <td className="py-3 px-4 text-slate-400 max-w-xs truncate">
                          {ev.message}
                        </td>
                        <td className="py-3 px-4 text-slate-500 font-mono text-[11px]">
                          {new Date(ev.created_at).toLocaleString()}
                        </td>
                        <td className="py-3 px-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                            ev.status === 'Delivered' 
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' 
                              : 'bg-slate-800 text-slate-400'
                          }`}>
                            {ev.status}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right">
                          <button
                            onClick={() => setSelectedPayloadEvent(ev)}
                            className="p-1 hover:bg-slate-800 text-slate-400 hover:text-brand-300 rounded transition-colors"
                            title="View Payload"
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={6} className="py-6 text-center text-slate-500">
                        No alert events fired recently.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 5: OpenTelemetry & Prometheus Scraper */}
      {activeTab === 'telemetry' && (
        <div className="space-y-6">
          {/* Prometheus Scraper Card */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 mb-3">
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-200 flex items-center gap-2">
                  <Terminal className="w-4 h-4 text-brand-400" />
                  Prometheus Compatible Metrics Endpoint
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Standard OpenMetrics representation for Prometheus, Datadog, and Grafana scrapers.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => copyToClipboard(prometheusRawText)}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg border border-slate-700 transition-colors"
                >
                  {copiedPrometheus ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  {copiedPrometheus ? 'Copied Metrics' : 'Copy Metrics'}
                </button>
                <a
                  href="/metrics"
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-brand-600 hover:bg-brand-500 text-white text-xs font-medium rounded-lg transition-colors"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  Open /metrics
                </a>
              </div>
            </div>

            {/* Live Scrape Output Box */}
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 font-mono text-[11px] text-slate-300 max-h-52 overflow-y-auto">
              <pre>{prometheusRawText || '# Fetching live metrics from /metrics endpoint...'}</pre>
            </div>
          </div>

          {/* OpenTelemetry Distributed Tracing Explorer */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 mb-4">
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-200 flex items-center gap-2">
                  <Activity className="w-4 h-4 text-purple-400" />
                  OpenTelemetry Distributed Trace Hierarchy (W3C Standard)
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Visual span waterfall for distributed pipeline runs and individual activity tasks.
                </p>
              </div>

              {/* Run Selector */}
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400">Select Pipeline Run:</span>
                <select
                  value={selectedRunIdForTrace}
                  onChange={(e) => {
                    setSelectedRunIdForTrace(e.target.value);
                    loadTrace(e.target.value);
                  }}
                  className="bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded-lg px-2.5 py-1.5 font-mono focus:outline-none focus:border-brand-500"
                >
                  {runs.map((r) => (
                    <option key={r.id} value={r.id}>
                      Run {r.id.slice(0, 8)} ({r.status}) - {r.duration_seconds.toFixed(1)}s
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Trace Meta */}
            {activeTrace ? (
              <div className="space-y-4">
                <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg flex flex-wrap items-center justify-between gap-3 text-xs">
                  <div>
                    <span className="text-slate-400 block text-[10px] uppercase tracking-wider">Trace ID (W3C Traceparent)</span>
                    <span className="font-mono text-purple-400 font-bold">{activeTrace.trace_id}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px] uppercase tracking-wider">Root Pipeline</span>
                    <span className="font-medium text-slate-200">{activeTrace.pipeline_name}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px] uppercase tracking-wider">Total Duration</span>
                    <span className="font-mono text-slate-200">{activeTrace.duration_ms} ms</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px] uppercase tracking-wider">Total Spans</span>
                    <span className="font-mono text-slate-200">{activeTrace.spans.length}</span>
                  </div>
                </div>

                {/* Spans Waterfall */}
                <div className="space-y-2 pt-2">
                  {activeTrace.spans.map((span) => {
                    const isRoot = !span.parent_span_id;
                    const pct = activeTrace.duration_ms > 0 
                      ? Math.max((span.duration_ms / activeTrace.duration_ms) * 100, 5) 
                      : 100;

                    return (
                      <div 
                        key={span.span_id} 
                        className={`p-3 rounded-lg border transition-all ${
                          isRoot 
                            ? 'bg-slate-900 border-purple-500/30' 
                            : 'bg-slate-950/80 border-slate-800 ml-6'
                        }`}
                      >
                        <div className="flex items-center justify-between text-xs mb-1.5">
                          <div className="flex items-center gap-2">
                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold ${
                              isRoot ? 'bg-purple-500/20 text-purple-300' : 'bg-slate-800 text-brand-300'
                            }`}>
                              {span.kind}
                            </span>
                            <span className="font-bold text-slate-200">{span.name}</span>
                          </div>
                          <div className="flex items-center gap-3">
                            <span className="font-mono text-slate-400 text-[11px]">{span.duration_ms} ms</span>
                            <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                              span.status_code === 'OK' 
                                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                            }`}>
                              {span.status_code}
                            </span>
                          </div>
                        </div>

                        {/* Timing bar */}
                        <div className="w-full bg-slate-800/80 h-1.5 rounded-full overflow-hidden mb-2">
                          <div 
                            className={`h-full rounded-full ${isRoot ? 'bg-purple-500' : 'bg-brand-500'}`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>

                        {/* Attributes pill list */}
                        <div className="flex flex-wrap gap-1.5 pt-1 text-[10px] font-mono">
                          <span className="px-1.5 py-0.5 bg-slate-800/90 text-slate-400 rounded">
                            span_id: {span.span_id.slice(0, 8)}
                          </span>
                          {Object.entries(span.attributes).map(([k, v]) => (
                            <span key={k} className="px-1.5 py-0.5 bg-slate-800/60 text-slate-300 rounded">
                              {k}: <strong className="text-slate-100">{String(v)}</strong>
                            </span>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div className="py-8 text-center text-xs text-slate-500">
                {isLoadingTrace ? 'Loading trace spans...' : 'No trace available for the selected execution run.'}
              </div>
            )}
          </div>
        </div>
      )}

      {/* CREATE ALERT RULE MODAL */}
      {showCreateAlertModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 max-w-md w-full shadow-2xl">
            <h3 className="text-base font-bold text-slate-100 mb-4 flex items-center gap-2">
              <Bell className="w-5 h-5 text-brand-400" />
              Create Multi-Channel Alert Rule
            </h3>

            <form onSubmit={handleCreateAlertRule} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-300 font-medium mb-1">Rule Name</label>
                <input
                  type="text"
                  required
                  value={newAlertName}
                  onChange={(e) => setNewAlertName(e.target.value)}
                  placeholder="e.g. Critical_Pipeline_Failure_Slack"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:border-brand-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 font-medium mb-1">Target Type</label>
                  <select
                    value={newAlertTargetType}
                    onChange={(e) => setNewAlertTargetType(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:border-brand-500"
                  >
                    <option value="Pipeline">Pipeline Run</option>
                    <option value="Activity">Activity Run</option>
                    <option value="Runtime">Integration Runtime</option>
                    <option value="DataQuality">Data Quality</option>
                  </select>
                </div>

                <div>
                  <label className="block text-slate-300 font-medium mb-1">Condition</label>
                  <select
                    value={newAlertConditionType}
                    onChange={(e) => setNewAlertConditionType(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:border-brand-500"
                  >
                    <option value="OnFailure">On Failure</option>
                    <option value="DurationExceeded">Duration Exceeded</option>
                    <option value="RuntimeOffline">Runtime Agent Offline</option>
                    <option value="DQScoreBreach">DQ Score Breach</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 font-medium mb-1">Notification Channel</label>
                  <select
                    value={newAlertActionType}
                    onChange={(e) => setNewAlertActionType(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:border-brand-500"
                  >
                    <option value="Teams">Microsoft Teams</option>
                    <option value="Slack">Slack</option>
                    <option value="Email">Email (SMTP)</option>
                    <option value="Webhook">Custom Webhook</option>
                  </select>
                </div>

                <div>
                  <label className="block text-slate-300 font-medium mb-1">Cooldown (Minutes)</label>
                  <input
                    type="number"
                    min="1"
                    max="1440"
                    value={newAlertCooldown}
                    onChange={(e) => setNewAlertCooldown(parseInt(e.target.value) || 5)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:border-brand-500 font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">
                  {newAlertActionType === 'Email' ? 'Email Recipients (comma separated)' : 'Incoming Webhook URL'}
                </label>
                <input
                  type="text"
                  required
                  value={newAlertEndpoint}
                  onChange={(e) => setNewAlertEndpoint(e.target.value)}
                  placeholder={newAlertActionType === 'Email' ? 'ops@company.com, team@company.com' : 'https://hooks.slack.com/services/...'}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:border-brand-500 font-mono text-xs"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowCreateAlertModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingAlert}
                  className="px-4 py-2 bg-brand-600 hover:bg-brand-500 text-white font-medium rounded-lg transition-colors disabled:opacity-50"
                >
                  {isSubmittingAlert ? 'Saving...' : 'Create Rule'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* VIEW PAYLOAD MODAL */}
      {selectedPayloadEvent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 max-w-lg w-full shadow-2xl">
            <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-2">
              <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                Alert Event Dispatch Payload
              </h3>
              <button
                onClick={() => setSelectedPayloadEvent(null)}
                className="text-slate-400 hover:text-slate-200 text-xs"
              >
                Close
              </button>
            </div>
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 font-mono text-xs text-slate-300 max-h-72 overflow-y-auto">
              <pre>{JSON.stringify(selectedPayloadEvent.payload, null, 2)}</pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
export default ObservabilityPage;
