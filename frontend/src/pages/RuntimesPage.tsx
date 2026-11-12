import React, { useState, useEffect, useMemo } from 'react';
import api from '../api/client';
import { useAppStore } from '../store/useAppStore';
import { ListFilterSortBar, SortOption } from '../components/common/ListFilterSortBar';
import { 
  Cpu, 
  Server, 
  Cloud, 
  Laptop, 
  Plus, 
  RefreshCw, 
  Key, 
  Terminal, 
  CheckCircle2, 
  XCircle, 
  Clock, 
  Trash2, 
  Power, 
  Copy, 
  Check, 
  Activity, 
  Layers, 
  HardDrive, 
  AlertTriangle,
  ExternalLink,
  ChevronRight,
  ShieldCheck,
  Zap,
  ArrowLeft
} from 'lucide-react';

export interface IntegrationRuntimeItem {
  id: string;
  project_id?: string;
  name: string;
  description?: string;
  runtime_type: 'Cloud' | 'SelfHosted' | 'LocalDev';
  status: 'Online' | 'Offline' | 'Disabled' | 'Registering';
  is_enabled: boolean;
  registration_key?: string;
  agent_version?: string;
  agent_os?: string;
  host_name?: string;
  ip_address?: string;
  cpu_cores: number;
  cpu_usage_pct: number;
  memory_total_bytes: number;
  memory_used_bytes: number;
  concurrency_limit: number;
  active_task_count: number;
  last_heartbeat_at?: string;
  created_at: string;
  updated_at: string;
}

export interface RuntimeTaskHistoryItem {
  id: string;
  runtime_id: string;
  pipeline_run_id?: string;
  activity_run_id?: string;
  task_type: string;
  status: string;
  queued_at: string;
  dispatched_at?: string;
  started_at?: string;
  completed_at?: string;
  task_result?: any;
}

export const RuntimesPage: React.FC = () => {
  const [runtimes, setRuntimes] = useState<IntegrationRuntimeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedRuntimeForSetup, setSelectedRuntimeForSetup] = useState<IntegrationRuntimeItem | null>(null);
  const [setupOsTab, setSetupOsTab] = useState<'linux' | 'windows' | 'cli'>('linux');
  const [linuxScript, setLinuxScript] = useState<string>('');
  const [windowsScript, setWindowsScript] = useState<string>('');
  const [copiedKey, setCopiedKey] = useState(false);
  const [copiedScript, setCopiedScript] = useState(false);
  const [selectedRuntimeForTasks, setSelectedRuntimeForTasks] = useState<IntegrationRuntimeItem | null>(null);
  const [tasks, setTasks] = useState<RuntimeTaskHistoryItem[]>([]);
  const [loadingTasks, setLoadingTasks] = useState(false);

  // Create form state
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [newType, setNewType] = useState<'Cloud' | 'SelfHosted' | 'LocalDev'>('SelfHosted');
  const [newConcurrency, setNewConcurrency] = useState(4);
  const [submittingCreate, setSubmittingCreate] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Search & Sort state (default newest first)
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('newest');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
  const [typeFilter, setTypeFilter] = useState<'all' | 'Cloud' | 'SelfHosted' | 'LocalDev'>('all');

  const runtimeSortOptions: SortOption[] = [
    { id: 'newest', label: 'Newest First' },
    { id: 'oldest', label: 'Oldest First' },
    { id: 'name', label: 'Name (A to Z)' },
    { id: 'status', label: 'Status' },
    { id: 'type', label: 'Runtime Type' },
    { id: 'tasks', label: 'Active Tasks' },
  ];

  const filteredAndSortedRuntimes = useMemo(() => {
    const list = runtimes.filter((rt) => {
      const q = searchQuery.toLowerCase().trim();
      const matchesSearch = !q || 
        rt.name.toLowerCase().includes(q) ||
        (rt.description && rt.description.toLowerCase().includes(q)) ||
        (rt.host_name && rt.host_name.toLowerCase().includes(q)) ||
        (rt.runtime_type && rt.runtime_type.toLowerCase().includes(q)) ||
        (rt.status && rt.status.toLowerCase().includes(q));
      
      const matchesType = typeFilter === 'all' || rt.runtime_type === typeFilter;
      return matchesSearch && matchesType;
    });

    list.sort((a, b) => {
      let comparison = 0;
      switch (sortBy) {
        case 'newest': {
          const tA = a.created_at ? new Date(a.created_at).getTime() : 0;
          const tB = b.created_at ? new Date(b.created_at).getTime() : 0;
          comparison = tB - tA; // default newest on top
          break;
        }
        case 'oldest': {
          const tA = a.created_at ? new Date(a.created_at).getTime() : 0;
          const tB = b.created_at ? new Date(b.created_at).getTime() : 0;
          comparison = tA - tB;
          break;
        }
        case 'name':
          comparison = a.name.localeCompare(b.name);
          break;
        case 'status':
          comparison = a.status.localeCompare(b.status);
          break;
        case 'type':
          comparison = a.runtime_type.localeCompare(b.runtime_type);
          break;
        case 'tasks':
          comparison = (b.active_task_count || 0) - (a.active_task_count || 0);
          break;
        default: {
          const tA = a.created_at ? new Date(a.created_at).getTime() : 0;
          const tB = b.created_at ? new Date(b.created_at).getTime() : 0;
          comparison = tB - tA;
          break;
        }
      }
      return sortDirection === 'asc' ? -comparison : comparison;
    });

    return list;
  }, [runtimes, searchQuery, sortBy, sortDirection, typeFilter]);

  const fetchRuntimes = async () => {
    try {
      setRefreshing(true);
      const res = await api.get('/runtimes');
      setRuntimes(res.data);
      setErrorMsg(null);
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Failed to load integration runtimes');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchRuntimes();
    // Auto-poll fleet heartbeat every 10 seconds
    const interval = setInterval(() => {
      fetchRuntimes();
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleCreateRuntime = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;

    try {
      setSubmittingCreate(true);
      const res = await api.post('/runtimes', {
        name: newName.trim(),
        description: newDesc.trim() || undefined,
        runtime_type: newType,
        concurrency_limit: newConcurrency
      });
      setShowCreateModal(false);
      setNewName('');
      setNewDesc('');
      await fetchRuntimes();

      // If Self-Hosted was created, immediately open setup agent modal
      if (res.data.runtime_type === 'SelfHosted') {
        openSetupModal(res.data);
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to create integration runtime');
    } finally {
      setSubmittingCreate(false);
    }
  };

  const openSetupModal = async (rt: IntegrationRuntimeItem) => {
    setSelectedRuntimeForSetup(rt);
    setCopiedKey(false);
    setCopiedScript(false);
    try {
      const [linRes, winRes] = await Promise.all([
        api.get(`/runtimes/${rt.id}/install-script/linux`),
        api.get(`/runtimes/${rt.id}/install-script/windows`)
      ]);
      setLinuxScript(linRes.data.script);
      setWindowsScript(winRes.data.script);
    } catch (err) {
      console.error('Failed to load install scripts', err);
    }
  };

  const handleRegenerateKey = async (rtId: string) => {
    if (!window.confirm('Regenerating this key will disconnect any currently active agent sessions until updated with the new key. Proceed?')) {
      return;
    }
    try {
      const res = await api.post(`/runtimes/${rtId}/regenerate-key`);
      await fetchRuntimes();
      if (selectedRuntimeForSetup?.id === rtId) {
        openSetupModal(res.data);
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to regenerate key');
    }
  };

  const handleToggleEnabled = async (rt: IntegrationRuntimeItem) => {
    try {
      await api.patch(`/runtimes/${rt.id}`, { is_enabled: !rt.is_enabled });
      await fetchRuntimes();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update runtime state');
    }
  };

  const handleDelete = async (rtId: string, name: string) => {
    if (!window.confirm(`Are you sure you want to delete Integration Runtime '${name}'?`)) {
      return;
    }
    try {
      await api.delete(`/runtimes/${rtId}`);
      await fetchRuntimes();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to delete runtime');
    }
  };

  const openTasksModal = async (rt: IntegrationRuntimeItem) => {
    setSelectedRuntimeForTasks(rt);
    setLoadingTasks(true);
    try {
      const res = await api.get(`/runtimes/${rt.id}/tasks`);
      setTasks(res.data);
    } catch (err) {
      console.error('Failed to load runtime tasks', err);
    } finally {
      setLoadingTasks(false);
    }
  };

  const formatBytes = (bytes: number) => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
  };

  const formatRelativeTime = (isoString?: string) => {
    if (!isoString) return 'Never';
    const diff = Math.floor((new Date().getTime() - new Date(isoString).getTime()) / 1000);
    if (diff < 15) return 'Just now';
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return `${Math.floor(diff / 3600)}h ago`;
  };

  const totalOnline = runtimes.filter(r => r.status === 'Online').length;
  const totalTasks = runtimes.reduce((acc, r) => acc + (r.active_task_count || 0), 0);
  const totalCapacity = runtimes.reduce((acc, r) => acc + (r.concurrency_limit || 0), 0);

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto">
      {/* Top Banner / Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div className="flex items-start gap-3">
          <button
            onClick={() => {
              if (window.history.length > 1) {
                window.history.back();
              } else {
                useAppStore.getState().setCurrentTab('dashboard');
              }
            }}
            className="p-2 mt-1 rounded-lg bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-400 hover:text-white transition shadow-sm flex items-center justify-center group"
            title="Go back (Alt + Left Arrow)"
          >
            <ArrowLeft className="h-4 w-4 group-hover:-translate-x-0.5 transition-transform" />
          </button>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-brand-500/10 border border-brand-500/20 rounded-xl text-brand-400">
              <Cpu className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
                Integration Runtime Manager
                <span className="px-2 py-0.5 text-xs font-semibold bg-brand-500/20 text-brand-400 border border-brand-500/30 rounded-full">
                  Enterprise Engine
                </span>
              </h1>
              <p className="text-slate-400 text-sm mt-0.5">
                Manage cloud execution clusters and self-hosted agents for hybrid and cross-cloud data movement.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchRuntimes}
            disabled={refreshing}
            className="flex items-center gap-2 px-3 py-2 text-xs font-medium bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-300 rounded-lg transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-brand-400' : ''}`} />
            Refresh Fleet
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2 text-xs font-semibold bg-brand-600 hover:bg-brand-500 text-white rounded-lg shadow-lg shadow-brand-600/20 transition"
          >
            <Plus className="w-4 h-4" />
            New Integration Runtime
          </button>
        </div>
      </div>

      {errorMsg && (
        <div className="p-4 bg-red-950/40 border border-red-800/60 rounded-xl flex items-center gap-3 text-red-300 text-xs">
          <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* KPI Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Fleet Status</span>
            <Server className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-100">{totalOnline}</span>
            <span className="text-xs text-slate-500">/ {runtimes.length} Online</span>
          </div>
          <div className="mt-2 text-[11px] text-emerald-400 flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" />
            All registered nodes responding
          </div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Active Dispatched Tasks</span>
            <Zap className="w-4 h-4 text-amber-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-100">{totalTasks}</span>
            <span className="text-xs text-slate-500">running</span>
          </div>
          <div className="mt-2 text-[11px] text-slate-400">
            Across all cloud & self-hosted nodes
          </div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Concurrent Capacity</span>
            <Layers className="w-4 h-4 text-blue-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-100">{totalCapacity}</span>
            <span className="text-xs text-slate-500">slots</span>
          </div>
          <div className="mt-2 text-[11px] text-slate-400">
            Total task concurrency limit
          </div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Security & Isolation</span>
            <ShieldCheck className="w-4 h-4 text-purple-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-100">Zero Inbound</span>
          </div>
          <div className="mt-2 text-[11px] text-slate-400">
            HTTPS Outbound-only agent tunnel
          </div>
        </div>
      </div>

      {/* Runtimes Table */}
      <div className="bg-slate-900/40 border border-slate-800 rounded-xl overflow-hidden space-y-4 p-4">
        <ListFilterSortBar
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          searchPlaceholder="Search runtimes by name, host, type, status..."
          currentSort={sortBy}
          onSortChange={setSortBy}
          sortDirection={sortDirection}
          onToggleDirection={() => setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc')}
          sortOptions={runtimeSortOptions}
          totalCount={runtimes.length}
          filteredCount={filteredAndSortedRuntimes.length}
        >
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
            {(['all', 'Cloud', 'SelfHosted', 'LocalDev'] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTypeFilter(t)}
                className={`px-2.5 py-1 text-xs rounded-lg font-medium transition ${
                  typeFilter === t
                    ? 'bg-brand-600 text-white'
                    : 'bg-slate-900 text-slate-400 hover:text-slate-200 border border-slate-800 hover:border-slate-700'
                }`}
              >
                {t === 'all' ? 'All Types' : t === 'SelfHosted' ? 'Self-Hosted' : t}
              </button>
            ))}
          </div>
        </ListFilterSortBar>

        {loading ? (
          <div className="py-16 text-center text-slate-500 text-xs">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto text-brand-500 mb-2" />
            Loading runtime fleet...
          </div>
        ) : runtimes.length === 0 ? (
          <div className="py-16 text-center text-slate-500 text-xs">
            No integration runtimes registered. Click "New Integration Runtime" to create one.
          </div>
        ) : filteredAndSortedRuntimes.length === 0 ? (
          <div className="py-16 text-center text-slate-500 text-xs">
            No runtimes matched your search criteria.
            <button
              onClick={() => { setSearchQuery(''); setTypeFilter('all'); }}
              className="block mx-auto mt-2 text-brand-400 hover:underline"
            >
              Clear filters
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-slate-800/80">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-950/60 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                <tr>
                  <th className="px-6 py-3">Runtime Name</th>
                  <th className="px-6 py-3">Type</th>
                  <th className="px-6 py-3">Status</th>
                  <th className="px-6 py-3">Host / Agent Specs</th>
                  <th className="px-6 py-3">Live Telemetry</th>
                  <th className="px-6 py-3">Heartbeat</th>
                  <th className="px-6 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {filteredAndSortedRuntimes.map((rt) => {
                  const isSH = rt.runtime_type === 'SelfHosted';
                  const isOnline = rt.status === 'Online';
                  const isOffline = rt.status === 'Offline';
                  const isRegistering = rt.status === 'Registering';

                  return (
                    <tr key={rt.id} className="hover:bg-slate-800/30 transition">
                      {/* Name & Description */}
                      <td className="px-6 py-4">
                        <div className="font-semibold text-slate-100 text-sm flex items-center gap-2">
                          {rt.name}
                          {!rt.is_enabled && (
                            <span className="px-1.5 py-0.5 text-[9px] font-semibold bg-slate-800 text-slate-400 rounded">
                              Disabled
                            </span>
                          )}
                        </div>
                        {rt.description && (
                          <div className="text-slate-400 text-[11px] mt-0.5 truncate max-w-xs">
                            {rt.description}
                          </div>
                        )}
                        <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                          ID: {rt.id.slice(0, 13)}...
                        </div>
                      </td>

                      {/* Type Badge */}
                      <td className="px-6 py-4">
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium border ${
                          rt.runtime_type === 'Cloud'
                            ? 'bg-sky-500/10 text-sky-400 border-sky-500/20'
                            : rt.runtime_type === 'SelfHosted'
                            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                            : 'bg-purple-500/10 text-purple-400 border-purple-500/20'
                        }`}>
                          {rt.runtime_type === 'Cloud' && <Cloud className="w-3 h-3" />}
                          {rt.runtime_type === 'SelfHosted' && <Server className="w-3 h-3" />}
                          {rt.runtime_type === 'LocalDev' && <Laptop className="w-3 h-3" />}
                          {rt.runtime_type === 'SelfHosted' ? 'Self-Hosted' : rt.runtime_type}
                        </span>
                      </td>

                      {/* Status Badge */}
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <span className={`w-2 h-2 rounded-full ${
                            isOnline
                              ? 'bg-emerald-500 animate-pulse'
                              : isOffline
                              ? 'bg-amber-500'
                              : isRegistering
                              ? 'bg-blue-500 animate-ping'
                              : 'bg-slate-600'
                          }`} />
                          <span className={`font-medium ${
                            isOnline
                              ? 'text-emerald-400'
                              : isOffline
                              ? 'text-amber-400'
                              : isRegistering
                              ? 'text-blue-400'
                              : 'text-slate-400'
                          }`}>
                            {rt.status}
                          </span>
                        </div>
                      </td>

                      {/* Host Specs */}
                      <td className="px-6 py-4 text-slate-400">
                        {isSH ? (
                          rt.host_name ? (
                            <div className="space-y-0.5">
                              <div className="text-slate-200 font-mono text-[11px]">{rt.host_name}</div>
                              <div className="text-[10px] text-slate-500">
                                {rt.agent_os} • {rt.cpu_cores} Cores • {formatBytes(rt.memory_total_bytes)}
                              </div>
                              <div className="text-[10px] text-slate-500 font-mono">
                                Agent v{rt.agent_version || '1.0.0'}
                              </div>
                            </div>
                          ) : (
                            <span className="text-slate-500 italic text-[11px]">No agent registered yet</span>
                          )
                        ) : (
                          <div className="space-y-0.5">
                            <div className="text-slate-200 text-[11px]">DataForge Serverless Engine</div>
                            <div className="text-[10px] text-slate-500">Multi-cloud auto-scaling</div>
                          </div>
                        )}
                      </td>

                      {/* Telemetry */}
                      <td className="px-6 py-4">
                        {isOnline ? (
                          <div className="space-y-1.5 w-36">
                            <div>
                              <div className="flex justify-between text-[10px] text-slate-400 mb-0.5">
                                <span>CPU Usage</span>
                                <span className="font-mono text-slate-300">{rt.cpu_usage_pct.toFixed(1)}%</span>
                              </div>
                              <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                                <div 
                                  className={`h-full rounded-full transition-all duration-500 ${
                                    rt.cpu_usage_pct > 80 ? 'bg-red-500' : rt.cpu_usage_pct > 50 ? 'bg-amber-500' : 'bg-emerald-500'
                                  }`}
                                  style={{ width: `${Math.min(rt.cpu_usage_pct, 100)}%` }}
                                />
                              </div>
                            </div>

                            <div className="flex justify-between text-[10px] text-slate-400">
                              <span>Tasks</span>
                              <span className="font-mono text-slate-300">
                                {rt.active_task_count} / {rt.concurrency_limit}
                              </span>
                            </div>
                          </div>
                        ) : (
                          <span className="text-slate-500 text-[11px]">—</span>
                        )}
                      </td>

                      {/* Heartbeat */}
                      <td className="px-6 py-4 text-slate-400 text-[11px]">
                        {formatRelativeTime(rt.last_heartbeat_at)}
                      </td>

                      {/* Actions */}
                      <td className="px-6 py-4 text-right space-x-1">
                        {isSH && (
                          <button
                            onClick={() => openSetupModal(rt)}
                            title="Setup Agent / View Keys"
                            className="p-1.5 text-slate-400 hover:text-brand-400 hover:bg-slate-800 rounded transition"
                          >
                            <Terminal className="w-4 h-4" />
                          </button>
                        )}
                        <button
                          onClick={() => openTasksModal(rt)}
                          title="View Execution Tasks"
                          className="p-1.5 text-slate-400 hover:text-blue-400 hover:bg-slate-800 rounded transition"
                        >
                          <Activity className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleToggleEnabled(rt)}
                          title={rt.is_enabled ? 'Disable Runtime' : 'Enable Runtime'}
                          className={`p-1.5 rounded transition ${
                            rt.is_enabled
                              ? 'text-slate-400 hover:text-amber-400 hover:bg-slate-800'
                              : 'text-emerald-400 hover:bg-slate-800'
                          }`}
                        >
                          <Power className="w-4 h-4" />
                        </button>
                        {rt.name !== 'AutoResolveIntegrationRuntime' && (
                          <button
                            onClick={() => handleDelete(rt.id, rt.name)}
                            title="Delete Runtime"
                            className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-slate-800 rounded transition"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* MODAL 1: CREATE INTEGRATION RUNTIME */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg shadow-2xl p-6 space-y-5">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
                <Plus className="w-4 h-4 text-brand-400" />
                Create Integration Runtime
              </h3>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-slate-400 hover:text-slate-200"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateRuntime} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-300 font-medium mb-1">Runtime Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. OnPremises-HQ-Gateway"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-brand-500"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">Description</label>
                <textarea
                  placeholder="e.g. Gateway for private SAP database and local corporate file share"
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  rows={2}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-brand-500"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">Runtime Type *</label>
                <div className="grid grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => setNewType('SelfHosted')}
                    className={`p-3 rounded-xl border text-left flex flex-col justify-between transition ${
                      newType === 'SelfHosted'
                        ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300 shadow-sm'
                        : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:border-slate-700'
                    }`}
                  >
                    <Server className="w-4 h-4 mb-2 text-emerald-400" />
                    <span className="font-semibold text-xs">Self-Hosted</span>
                    <span className="text-[10px] text-slate-500 mt-1">Private network agent</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setNewType('Cloud')}
                    className={`p-3 rounded-xl border text-left flex flex-col justify-between transition ${
                      newType === 'Cloud'
                        ? 'bg-sky-500/10 border-sky-500/40 text-sky-300 shadow-sm'
                        : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:border-slate-700'
                    }`}
                  >
                    <Cloud className="w-4 h-4 mb-2 text-sky-400" />
                    <span className="font-semibold text-xs">Cloud</span>
                    <span className="text-[10px] text-slate-500 mt-1">Managed serverless</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setNewType('LocalDev')}
                    className={`p-3 rounded-xl border text-left flex flex-col justify-between transition ${
                      newType === 'LocalDev'
                        ? 'bg-purple-500/10 border-purple-500/40 text-purple-300 shadow-sm'
                        : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:border-slate-700'
                    }`}
                  >
                    <Laptop className="w-4 h-4 mb-2 text-purple-400" />
                    <span className="font-semibold text-xs">Local Dev</span>
                    <span className="text-[10px] text-slate-500 mt-1">Local developer node</span>
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">
                  Concurrency Limit (Active Tasks)
                </label>
                <input
                  type="number"
                  min={1}
                  max={64}
                  value={newConcurrency}
                  onChange={(e) => setNewConcurrency(parseInt(e.target.value) || 4)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-brand-500"
                />
                <p className="text-[10px] text-slate-500 mt-1">
                  Maximum simultaneous execution tasks allowed on this runtime before queueing.
                </p>
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingCreate}
                  className="px-4 py-2 bg-brand-600 hover:bg-brand-500 text-white font-semibold rounded-lg shadow-lg shadow-brand-600/20 transition flex items-center gap-2"
                >
                  {submittingCreate ? 'Creating...' : 'Create Runtime'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: SETUP AGENT (LINUX / WINDOWS / CLI) */}
      {selectedRuntimeForSetup && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl shadow-2xl p-6 space-y-5">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
                  <Terminal className="w-5 h-5 text-emerald-400" />
                  Self-Hosted Agent Setup — {selectedRuntimeForSetup.name}
                </h3>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Install the agent on your private server to securely execute data movement jobs without opening inbound firewall ports.
                </p>
              </div>
              <button
                onClick={() => setSelectedRuntimeForSetup(null)}
                className="text-slate-400 hover:text-slate-200"
              >
                ✕
              </button>
            </div>

            {/* Registration Key Box */}
            <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold text-slate-300 flex items-center gap-1.5 uppercase tracking-wider">
                  <Key className="w-3.5 h-3.5 text-brand-400" />
                  Agent Registration Key
                </span>
                <button
                  onClick={() => handleRegenerateKey(selectedRuntimeForSetup.id)}
                  className="text-[10px] text-slate-400 hover:text-amber-400 flex items-center gap-1 transition"
                >
                  <RefreshCw className="w-3 h-3" />
                  Regenerate Key
                </button>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  readOnly
                  value={selectedRuntimeForSetup.registration_key || 'df-ir-key-loaded'}
                  className="flex-1 bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 font-mono text-xs text-brand-300 select-all"
                />
                <button
                  onClick={() => {
                    if (selectedRuntimeForSetup.registration_key) {
                      navigator.clipboard.writeText(selectedRuntimeForSetup.registration_key);
                      setCopiedKey(true);
                      setTimeout(() => setCopiedKey(false), 2000);
                    }
                  }}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs flex items-center gap-1.5 transition"
                >
                  {copiedKey ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  {copiedKey ? 'Copied' : 'Copy'}
                </button>
              </div>
            </div>

            {/* OS Script Tabs */}
            <div className="space-y-3">
              <div className="flex border-b border-slate-800">
                <button
                  onClick={() => setSetupOsTab('linux')}
                  className={`px-4 py-2 text-xs font-semibold border-b-2 transition ${
                    setupOsTab === 'linux'
                      ? 'border-brand-500 text-brand-400'
                      : 'border-transparent text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Linux (Bash)
                </button>
                <button
                  onClick={() => setSetupOsTab('windows')}
                  className={`px-4 py-2 text-xs font-semibold border-b-2 transition ${
                    setupOsTab === 'windows'
                      ? 'border-brand-500 text-brand-400'
                      : 'border-transparent text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Windows (PowerShell)
                </button>
                <button
                  onClick={() => setSetupOsTab('cli')}
                  className={`px-4 py-2 text-xs font-semibold border-b-2 transition ${
                    setupOsTab === 'cli'
                      ? 'border-brand-500 text-brand-400'
                      : 'border-transparent text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Python Standalone CLI
                </button>
              </div>

              {/* Code viewer */}
              <div className="relative">
                <pre className="p-4 bg-slate-950 border border-slate-800 rounded-xl font-mono text-[11px] text-slate-300 overflow-x-auto max-h-56 leading-relaxed">
                  {setupOsTab === 'linux' && (linuxScript || '# Loading Linux setup script...')}
                  {setupOsTab === 'windows' && (windowsScript || '# Loading Windows PowerShell script...')}
                  {setupOsTab === 'cli' && (
                    `# 1. Install agent requirements:\npip install requests psutil\n\n# 2. Run standalone agent:\npython3 scripts/dataforge_agent.py \\\n  --url "${window.location.origin}" \\\n  --key "${selectedRuntimeForSetup.registration_key || 'YOUR_KEY'}"`
                  )}
                </pre>
                <button
                  onClick={() => {
                    const text = setupOsTab === 'linux' ? linuxScript : (setupOsTab === 'windows' ? windowsScript : `python3 scripts/dataforge_agent.py --url "${window.location.origin}" --key "${selectedRuntimeForSetup.registration_key}"`);
                    navigator.clipboard.writeText(text);
                    setCopiedScript(true);
                    setTimeout(() => setCopiedScript(false), 2000);
                  }}
                  className="absolute top-2 right-2 px-2.5 py-1 bg-slate-800/80 hover:bg-slate-700 text-slate-300 rounded text-[10px] flex items-center gap-1 transition"
                >
                  {copiedScript ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                  {copiedScript ? 'Copied' : 'Copy Command'}
                </button>
              </div>
            </div>

            <div className="flex justify-between items-center pt-2">
              <span className="text-[11px] text-slate-500">
                Agent operates via outbound HTTPS (Port 443/8000) with automatic retry.
              </span>
              <button
                onClick={() => setSelectedRuntimeForSetup(null)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs transition"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 3: VIEW RUNTIME TASKS */}
      {selectedRuntimeForTasks && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-3xl shadow-2xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
                  <Activity className="w-5 h-5 text-blue-400" />
                  Recent Dispatched Tasks — {selectedRuntimeForTasks.name}
                </h3>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Execution queue history dispatched to this Integration Runtime.
                </p>
              </div>
              <button
                onClick={() => setSelectedRuntimeForTasks(null)}
                className="text-slate-400 hover:text-slate-200"
              >
                ✕
              </button>
            </div>

            {loadingTasks ? (
              <div className="py-12 text-center text-slate-500 text-xs">
                <RefreshCw className="w-5 h-5 animate-spin mx-auto text-brand-500 mb-2" />
                Loading tasks...
              </div>
            ) : tasks.length === 0 ? (
              <div className="py-12 text-center text-slate-500 text-xs">
                No recent tasks dispatched to this runtime.
              </div>
            ) : (
              <div className="overflow-y-auto max-h-96">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-slate-950 text-slate-400 uppercase text-[10px] tracking-wider sticky top-0">
                    <tr>
                      <th className="px-4 py-2.5">Task ID</th>
                      <th className="px-4 py-2.5">Type</th>
                      <th className="px-4 py-2.5">Status</th>
                      <th className="px-4 py-2.5">Queued At</th>
                      <th className="px-4 py-2.5">Result</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {tasks.map(t => (
                      <tr key={t.id} className="hover:bg-slate-800/30">
                        <td className="px-4 py-2.5 font-mono text-[10px] text-slate-400">
                          {t.id.slice(0, 13)}...
                        </td>
                        <td className="px-4 py-2.5 font-semibold text-slate-200">
                          {t.task_type}
                        </td>
                        <td className="px-4 py-2.5">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                            t.status === 'Completed'
                              ? 'bg-emerald-500/20 text-emerald-400'
                              : t.status === 'Running'
                              ? 'bg-blue-500/20 text-blue-400 animate-pulse'
                              : t.status === 'Failed'
                              ? 'bg-red-500/20 text-red-400'
                              : 'bg-slate-800 text-slate-400'
                          }`}>
                            {t.status}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-slate-400 text-[11px]">
                          {formatRelativeTime(t.queued_at)}
                        </td>
                        <td className="px-4 py-2.5 text-[11px]">
                          {t.task_result?.rows_written !== undefined ? (
                            <span className="text-emerald-400 font-mono">
                              {t.task_result.rows_written} rows ({formatBytes(t.task_result.bytes_processed || 0)})
                            </span>
                          ) : t.task_result?.error_message ? (
                            <span className="text-red-400 truncate max-w-xs block" title={t.task_result.error_message}>
                              {t.task_result.error_message}
                            </span>
                          ) : (
                            <span className="text-slate-500">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <div className="flex justify-end pt-2 border-t border-slate-800">
              <button
                onClick={() => setSelectedRuntimeForTasks(null)}
                className="px-4 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
