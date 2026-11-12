import React, { useEffect, useState } from 'react';
import { useAppStore } from '../store/useAppStore';
import { Trigger, TriggerRun, Pipeline } from '../types';
import api from '../api/client';
import { ListFilterSortBar } from '../components/common/ListFilterSortBar';
import {
  Clock,
  Plus,
  Play,
  Power,
  Trash2,
  Calendar,
  CheckCircle2,
  XCircle,
  AlertCircle,
  History,
  Layers,
  HardDrive,
  GitBranch,
  Filter,
  ArrowRight,
  ExternalLink,
  ShieldAlert,
  Sparkles,
  RefreshCw,
  Search,
  Eye,
  Settings,
  MoreVertical,
  Copy,
  X,
  ArrowLeft
} from 'lucide-react';

const COMMON_TIMEZONES = [
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'Europe/London',
  'Europe/Paris',
  'Europe/Berlin',
  'Asia/Kolkata',
  'Asia/Tokyo',
  'Asia/Singapore',
  'Australia/Sydney'
];

export const TriggersPage: React.FC = () => {
  const { pipelines, fetchPipelines, setCurrentTab, setSelectedPipelineId } = useAppStore();
  const [triggers, setTriggers] = useState<Trigger[]>([]);
  const [connections, setConnections] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTabFilter, setActiveTabFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<string>('newest');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  // Modals & Drawers
  const [showAddModal, setShowAddModal] = useState(false);
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [selectedTriggerForHistory, setSelectedTriggerForHistory] = useState<Trigger | null>(null);
  const [triggerRuns, setTriggerRuns] = useState<TriggerRun[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // Details Drawer & Context Menu state
  const [selectedTriggerForDetails, setSelectedTriggerForDetails] = useState<Trigger | null>(null);
  const [triggerDetailsRuns, setTriggerDetailsRuns] = useState<TriggerRun[]>([]);
  const [loadingDetailsRuns, setLoadingDetailsRuns] = useState(false);
  const [activeDropdownTriggerId, setActiveDropdownTriggerId] = useState<string | null>(null);
  const [drawerActiveTab, setDrawerActiveTab] = useState<'config' | 'pipelines' | 'runs'>('config');
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Wizard state for trigger creation
  const [wizardType, setWizardType] = useState<string>('schedule');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [selectedPipelineIds, setSelectedPipelineIds] = useState<string[]>([]);
  const [parametersJson, setParametersJson] = useState('{}');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Type-specific form fields:
  // 1. Schedule
  const [cronExpression, setCronExpression] = useState('0 * * * *');
  const [timezoneStr, setTimezoneStr] = useState('UTC');
  const [scheduleStartTime, setScheduleStartTime] = useState('');
  const [scheduleEndTime, setScheduleEndTime] = useState('');

  // 2. Tumbling Window
  const [twFrequency, setTwFrequency] = useState('Hour');
  const [twInterval, setTwInterval] = useState(1);
  const [twStartTime, setTwStartTime] = useState(
    new Date(Date.now() - 3600 * 1000).toISOString().slice(0, 16)
  );
  const [twDelayMinutes, setTwDelayMinutes] = useState(0);
  const [twMaxConcurrency, setTwMaxConcurrency] = useState(1);
  const [twDependsOnPrior, setTwDependsOnPrior] = useState(true);

  // 3. Storage Event
  const [storageConnId, setStorageConnId] = useState('');
  const [storageContainer, setStorageContainer] = useState('');
  const [storagePrefix, setStoragePrefix] = useState('incoming/');
  const [storageSuffix, setStorageSuffix] = useState('.csv');
  const [storageRegex, setStorageRegex] = useState('');
  const [storageIgnoreEmpty, setStorageIgnoreEmpty] = useState(true);

  // 4. Pipeline Dependency
  const [upstreamPipelineId, setUpstreamPipelineId] = useState('');
  const [fireOnStatuses, setFireOnStatuses] = useState<string[]>(['Succeeded']);
  const [forwardParams, setForwardParams] = useState(true);
  const [cycleCheckResult, setCycleCheckResult] = useState<{ checked: boolean; valid: boolean; message: string } | null>(null);

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

  const fetchStorageConnections = async () => {
    try {
      const res = await api.get('/connections');
      const storageTypes = ['local_storage', 'azure_blob', 'azure_adls', 'aws_s3', 'gcp_storage'];
      const stConns = res.data.filter((c: any) => storageTypes.includes(c.connector_type));
      setConnections(stConns);
      if (stConns.length > 0 && !storageConnId) {
        setStorageConnId(stConns[0].id);
      }
    } catch (err) {
      console.error('Failed to load connections', err);
    }
  };

  useEffect(() => {
    fetchTriggers();
    fetchPipelines();
    fetchStorageConnections();
  }, []);

  useEffect(() => {
    const handleDocClick = () => setActiveDropdownTriggerId(null);
    document.addEventListener('click', handleDocClick);
    return () => document.removeEventListener('click', handleDocClick);
  }, []);

  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 3500);
  };

  const handleSelectTrigger = async (trigger: Trigger) => {
    setSelectedTriggerForDetails(trigger);
    setDrawerActiveTab('config');
    setLoadingDetailsRuns(true);
    try {
      const res = await api.get(`/triggers/${trigger.id}/runs`);
      setTriggerDetailsRuns(res.data);
    } catch (err) {
      console.error('Failed to load trigger runs', err);
      setTriggerDetailsRuns([]);
    } finally {
      setLoadingDetailsRuns(false);
    }
  };

  const handleDuplicateTrigger = async (trigger: Trigger) => {
    try {
      const cloneBody: any = {
        name: `${trigger.name} (Copy)`,
        description: trigger.description ? `Copy of ${trigger.description}` : `Copy of ${trigger.name}`,
        trigger_type: trigger.trigger_type,
        pipeline_id: trigger.pipeline_id,
        pipelines_to_run: trigger.pipelines_to_run,
        is_active: false,
        parameters: trigger.parameters || {}
      };
      if (trigger.cron_expression) cloneBody.cron_expression = trigger.cron_expression;
      if (trigger.schedule_config) cloneBody.schedule_config = trigger.schedule_config;
      if (trigger.tumbling_window_config) cloneBody.tumbling_window_config = trigger.tumbling_window_config;
      if (trigger.storage_event_config) cloneBody.storage_event_config = trigger.storage_event_config;
      if (trigger.pipeline_dependency_config) cloneBody.pipeline_dependency_config = trigger.pipeline_dependency_config;

      await api.post('/triggers', cloneBody);
      showToast(`Trigger duplicated successfully as '${cloneBody.name}'`);
      await fetchTriggers();
    } catch (err: any) {
      showToast(`Failed to duplicate trigger: ${err.response?.data?.detail || err.message}`, 'error');
    }
  };

  const handleToggleActivate = async (trigger: Trigger) => {
    try {
      const endpoint = trigger.is_active ? `/triggers/${trigger.id}/deactivate` : `/triggers/${trigger.id}/activate`;
      await api.post(endpoint);
      showToast(`Trigger '${trigger.name}' ${trigger.is_active ? 'paused' : 'activated'}.`);
      if (selectedTriggerForDetails?.id === trigger.id) {
        setSelectedTriggerForDetails((prev) => prev ? { ...prev, is_active: !prev.is_active } : null);
      }
      fetchTriggers();
    } catch (err: any) {
      showToast(`Error toggling trigger: ${err.message}`, 'error');
    }
  };

  const handleFireNow = async (trigger: Trigger) => {
    try {
      const res = await api.post(`/triggers/${trigger.id}/fire-now`);
      showToast(`Trigger "${trigger.name}" dispatched! Run ID: ${res.data.run_id || 'Dispatched'}`);
      fetchTriggers();
      if (selectedTriggerForDetails?.id === trigger.id) {
        handleSelectTrigger(trigger);
      }
    } catch (err: any) {
      showToast(`Error firing trigger: ${err.response?.data?.detail || err.message}`, 'error');
    }
  };

  const handleDeleteTrigger = async (triggerId: string) => {
    if (!confirm('Are you sure you want to delete this trigger and its run history?')) return;
    try {
      await api.delete(`/triggers/${triggerId}`);
      showToast('Trigger deleted successfully.');
      if (selectedTriggerForDetails?.id === triggerId) {
        setSelectedTriggerForDetails(null);
      }
      fetchTriggers();
    } catch (err: any) {
      showToast(`Error deleting trigger: ${err.message}`, 'error');
    }
  };

  const handleOpenHistory = async (trigger: Trigger) => {
    setSelectedTriggerForHistory(trigger);
    setShowHistoryModal(true);
    setLoadingHistory(true);
    try {
      const res = await api.get(`/triggers/${trigger.id}/runs`);
      setTriggerRuns(res.data);
    } catch (err) {
      console.error('Failed to load trigger runs', err);
    } finally {
      setLoadingHistory(false);
    }
  };

  const handlePreflightCycleCheck = async () => {
    if (!upstreamPipelineId || selectedPipelineIds.length === 0) {
      alert('Please select both an Upstream Pipeline and at least one Target Pipeline to check.');
      return;
    }
    try {
      const res = await api.post('/triggers/validate-dependency-cycle', {
        upstream_pipeline_id: upstreamPipelineId,
        downstream_pipeline_ids: selectedPipelineIds
      });
      setCycleCheckResult({
        checked: true,
        valid: res.data.valid,
        message: res.data.valid ? 'No circular dependency detected! Graph is a valid DAG.' : res.data.error
      });
    } catch (err: any) {
      setCycleCheckResult({
        checked: true,
        valid: false,
        message: err.response?.data?.detail || err.message
      });
    }
  };

  const handleCreateTrigger = async (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedPipelineIds.length === 0) {
      alert('Please select at least one target pipeline.');
      return;
    }

    let parsedParams = {};
    try {
      parsedParams = JSON.parse(parametersJson || '{}');
    } catch (pe) {
      alert('Parameters must be a valid JSON object.');
      return;
    }

    setIsSubmitting(true);
    try {
      const pipelinesPayload = selectedPipelineIds.map((pId) => {
        const pObj = pipelines.find((p) => p.id === pId);
        return {
          pipeline_id: pId,
          pipeline_name: pObj?.name || pId,
          parameters: parsedParams
        };
      });

      const body: any = {
        name,
        description,
        trigger_type: wizardType,
        pipeline_id: selectedPipelineIds[0],
        pipelines_to_run: pipelinesPayload,
        is_active: true,
        parameters: parsedParams
      };

      if (wizardType === 'schedule') {
        body.cron_expression = cronExpression;
        body.schedule_config = {
          timezone: timezoneStr,
          frequency: 'Day',
          interval: 1,
          start_time: scheduleStartTime ? new Date(scheduleStartTime).toISOString() : null,
          end_time: scheduleEndTime ? new Date(scheduleEndTime).toISOString() : null
        };
      } else if (wizardType === 'tumbling_window') {
        body.tumbling_window_config = {
          frequency: twFrequency,
          interval: Number(twInterval),
          start_time: new Date(twStartTime).toISOString(),
          delay_minutes: Number(twDelayMinutes),
          max_concurrency: Number(twMaxConcurrency),
          depends_on_prior_window: twDependsOnPrior
        };
      } else if (wizardType === 'storage_event') {
        body.storage_event_config = {
          connection_id: storageConnId,
          container: storageContainer,
          prefix: storagePrefix,
          suffix: storageSuffix,
          blob_path_regex: storageRegex || null,
          event_types: ['created'],
          ignore_empty_blobs: storageIgnoreEmpty
        };
      } else if (wizardType === 'pipeline_dependency') {
        body.pipeline_dependency_config = {
          upstream_pipeline_id: upstreamPipelineId,
          fire_on_status: fireOnStatuses,
          forward_parameters: forwardParams
        };
      }

      await api.post('/triggers', body);
      setShowAddModal(false);
      resetWizardForm();
      fetchTriggers();
    } catch (err: any) {
      alert(`Error creating trigger: ${err.response?.data?.detail || err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const resetWizardForm = () => {
    setName('');
    setDescription('');
    setSelectedPipelineIds([]);
    setParametersJson('{}');
    setCycleCheckResult(null);
  };

  const getPipelineName = (pipelineId?: string) => {
    if (!pipelineId) return 'Multiple Pipelines';
    const p = pipelines.find((pipe) => pipe.id === pipelineId);
    return p ? p.name : pipelineId;
  };

  const getTypeBadge = (type: string) => {
    const norm = (type || '').toLowerCase();
    switch (norm) {
      case 'schedule':
      case 'cron':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <Clock className="h-3 w-3" />
            Schedule
          </span>
        );
      case 'tumbling_window':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
            <Layers className="h-3 w-3" />
            Tumbling Window
          </span>
        );
      case 'storage_event':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <HardDrive className="h-3 w-3" />
            Storage Event
          </span>
        );
      case 'pipeline_dependency':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/20">
            <GitBranch className="h-3 w-3" />
            Dependency
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-800 text-slate-300 border border-slate-700">
            <Play className="h-3 w-3" />
            Manual
          </span>
        );
    }
  };

  const filteredTriggers = triggers.filter((t) => {
    const ttype = (t.trigger_type || '').toLowerCase();
    if (activeTabFilter === 'schedule' && ttype !== 'schedule' && ttype !== 'cron') return false;
    if (activeTabFilter === 'tumbling_window' && ttype !== 'tumbling_window') return false;
    if (activeTabFilter === 'storage_event' && ttype !== 'storage_event') return false;
    if (activeTabFilter === 'pipeline_dependency' && ttype !== 'pipeline_dependency') return false;
    if (activeTabFilter === 'manual' && ttype !== 'manual') return false;

    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const matchName = t.name.toLowerCase().includes(q);
      const matchDesc = (t.description || '').toLowerCase().includes(q);
      return matchName || matchDesc;
    }
    return true;
  });

  // Default: Newest items appear on top
  const sortedTriggers = [...filteredTriggers].sort((a, b) => {
    if (sortBy === 'newest') {
      const dateA = new Date(a.created_at || a.updated_at || 0).getTime();
      const dateB = new Date(b.created_at || b.updated_at || 0).getTime();
      return sortDirection === 'asc' ? dateA - dateB : dateB - dateA;
    }
    if (sortBy === 'oldest') {
      const dateA = new Date(a.created_at || a.updated_at || 0).getTime();
      const dateB = new Date(b.created_at || b.updated_at || 0).getTime();
      return sortDirection === 'asc' ? dateB - dateA : dateA - dateB;
    }
    if (sortBy === 'name_asc') {
      const cmp = a.name.localeCompare(b.name);
      return sortDirection === 'asc' ? cmp : -cmp;
    }
    if (sortBy === 'name_desc') {
      const cmp = b.name.localeCompare(a.name);
      return sortDirection === 'asc' ? cmp : -cmp;
    }
    if (sortBy === 'type') {
      const cmp = (a.trigger_type || '').localeCompare(b.trigger_type || '');
      return sortDirection === 'asc' ? cmp : -cmp;
    }
    return 0;
  });

  const activeCount = triggers.filter((t) => t.is_active).length;

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
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
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
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
            <div className="flex items-center gap-2.5">
              <h1 className="text-xl font-bold text-white tracking-tight">Advanced Trigger Manager</h1>
              <span className="px-2 py-0.5 rounded-full text-[10px] bg-brand-500/20 text-brand-300 font-semibold border border-brand-500/30">
                Enterprise Orchestration
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Configure Schedule, Tumbling Window, Multi-Cloud Storage Event, and Pipeline Dependency Triggers.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2.5">
          <button
            onClick={fetchTriggers}
            className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs transition border border-slate-700"
            title="Refresh Triggers"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          <button
            onClick={() => {
              resetWizardForm();
              setShowAddModal(true);
            }}
            className="px-3.5 py-2 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-xs font-medium transition flex items-center gap-1.5 shadow-sm"
          >
            <Plus className="h-4 w-4" />
            <span>New Enterprise Trigger</span>
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="p-3.5 bg-slate-900/80 border border-slate-800 rounded-xl space-y-1">
          <div className="text-[11px] text-slate-400 font-medium">Total Triggers</div>
          <div className="text-lg font-bold text-white font-mono">{triggers.length}</div>
        </div>
        <div className="p-3.5 bg-slate-900/80 border border-slate-800 rounded-xl space-y-1">
          <div className="text-[11px] text-emerald-400 font-medium">Active Triggers</div>
          <div className="text-lg font-bold text-emerald-400 font-mono">{activeCount}</div>
        </div>
        <div className="p-3.5 bg-slate-900/80 border border-slate-800 rounded-xl space-y-1">
          <div className="text-[11px] text-indigo-400 font-medium">Storage & Event Listeners</div>
          <div className="text-lg font-bold text-indigo-400 font-mono">
            {triggers.filter((t) => t.trigger_type === 'storage_event').length}
          </div>
        </div>
        <div className="p-3.5 bg-slate-900/80 border border-slate-800 rounded-xl space-y-1">
          <div className="text-[11px] text-cyan-400 font-medium">Tumbling Windows & Schedules</div>
          <div className="text-lg font-bold text-cyan-400 font-mono">
            {triggers.filter((t) => ['tumbling_window', 'schedule', 'cron'].includes(t.trigger_type)).length}
          </div>
        </div>
      </div>

      {/* Filter Tabs & Search & Sort Bar */}
      <ListFilterSortBar
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search triggers by name, description..."
        currentSort={sortBy}
        onSortChange={setSortBy}
        sortDirection={sortDirection}
        onToggleDirection={() => setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'))}
        sortOptions={[
          { id: 'newest', label: 'Newest First' },
          { id: 'oldest', label: 'Oldest First' },
          { id: 'name_asc', label: 'Name (A to Z)' },
          { id: 'name_desc', label: 'Name (Z to A)' },
          { id: 'type', label: 'Trigger Type' }
        ]}
        totalCount={triggers.length}
        filteredCount={sortedTriggers.length}
      >
        <div className="flex items-center gap-1 overflow-x-auto text-xs bg-slate-950/70 p-1 rounded-lg border border-slate-800">
          {[
            { id: 'all', label: 'All Triggers' },
            { id: 'schedule', label: 'Schedule' },
            { id: 'tumbling_window', label: 'Tumbling Window' },
            { id: 'storage_event', label: 'Storage Events' },
            { id: 'pipeline_dependency', label: 'Dependencies' },
            { id: 'manual', label: 'Manual' }
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTabFilter(tab.id)}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition ${
                activeTabFilter === tab.id
                  ? 'bg-brand-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </ListFilterSortBar>

      {/* Triggers Table */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-800/60 text-slate-400 uppercase text-[10px] font-semibold tracking-wider">
              <tr>
                <th className="py-3 px-4">Trigger Name</th>
                <th className="py-3 px-3">Type</th>
                <th className="py-3 px-3">Target Pipeline(s)</th>
                <th className="py-3 px-3">Configuration & Recurrence</th>
                <th className="py-3 px-3">Status</th>
                <th className="py-3 px-3">Next Fire Time</th>
                <th className="py-3 px-3">Last Fired</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {isLoading ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-500 text-xs">
                    <RefreshCw className="h-5 w-5 animate-spin mx-auto mb-2 text-brand-400" />
                    Loading triggers...
                  </td>
                </tr>
              ) : sortedTriggers.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-500 text-xs space-y-2">
                    <AlertCircle className="h-6 w-6 mx-auto text-slate-600 mb-1" />
                    <div>No triggers found matching the current criteria.</div>
                    <button
                      onClick={() => setShowAddModal(true)}
                      className="px-3 py-1 bg-brand-600 hover:bg-brand-500 text-white rounded text-[11px] font-medium"
                    >
                      Create First Trigger
                    </button>
                  </td>
                </tr>
              ) : (
                sortedTriggers.map((t) => {
                  const isMenuOpen = activeDropdownTriggerId === t.id;
                  const isSelected = selectedTriggerForDetails?.id === t.id;

                  return (
                    <tr 
                      key={t.id} 
                      onClick={() => handleSelectTrigger(t)}
                      className={`transition-colors cursor-pointer group ${
                        isSelected 
                          ? 'bg-brand-600/15 border-l-4 border-brand-500' 
                          : 'hover:bg-slate-800/50'
                      }`}
                    >
                      <td className="py-3.5 px-4">
                        <div className="font-semibold text-slate-200 group-hover:text-brand-300 transition-colors flex items-center gap-2">
                          <span>{t.name}</span>
                          {isSelected && (
                            <span className="px-1.5 py-0.2 rounded text-[9px] bg-brand-500/20 text-brand-300 border border-brand-500/30">
                              Selected
                            </span>
                          )}
                        </div>
                        {t.description && (
                          <div className="text-[11px] text-slate-400 truncate max-w-xs">{t.description}</div>
                        )}
                        <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                          Click to inspect configuration & options
                        </div>
                      </td>
                      <td className="py-3.5 px-3 whitespace-nowrap">{getTypeBadge(t.trigger_type)}</td>
                      <td className="py-3.5 px-3">
                        {t.pipelines_to_run && t.pipelines_to_run.length > 1 ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-slate-800 text-brand-300 font-medium text-[11px] border border-slate-700">
                            {t.pipelines_to_run.length} Pipelines
                          </span>
                        ) : (
                          <span className="text-brand-400 font-medium">
                            {getPipelineName(t.pipeline_id || t.pipelines_to_run?.[0]?.pipeline_id)}
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-3 text-[11px] text-slate-300">
                        {t.trigger_type === 'schedule' || t.trigger_type === 'cron' ? (
                          <div className="space-y-0.5">
                            <span className="font-mono bg-slate-950/60 px-2 py-0.5 rounded border border-slate-800">
                              {t.cron_expression || 'Recurrence'}
                            </span>
                            <span className="text-slate-500 text-[10px] ml-1.5 font-mono">
                              ({t.schedule_config?.timezone || 'UTC'})
                            </span>
                          </div>
                        ) : t.trigger_type === 'tumbling_window' ? (
                          <div className="space-y-0.5 font-mono text-[10px]">
                            <span>Slice: {t.tumbling_window_config?.interval} {t.tumbling_window_config?.frequency}</span>
                            <span className="text-slate-500 block">Delay: {t.tumbling_window_config?.delay_minutes}m</span>
                          </div>
                        ) : t.trigger_type === 'storage_event' ? (
                          <div className="space-y-0.5 font-mono text-[10px]">
                            <span>Bucket: {t.storage_event_config?.container}</span>
                            <span className="text-emerald-400 block truncate max-w-xs">
                              {t.storage_event_config?.prefix}*{t.storage_event_config?.suffix}
                            </span>
                          </div>
                        ) : t.trigger_type === 'pipeline_dependency' ? (
                          <div className="space-y-0.5 text-[11px]">
                            <span>Upstream: <strong className="text-purple-300">{t.pipeline_dependency_config?.upstream_pipeline_name || t.pipeline_dependency_config?.upstream_pipeline_id}</strong></span>
                          </div>
                        ) : (
                          <span className="text-slate-500">On-demand Manual</span>
                        )}
                      </td>
                      <td className="py-3.5 px-3 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                            t.is_active
                              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                              : 'bg-slate-800 text-slate-500 border-slate-700'
                          }`}
                        >
                          {t.is_active ? <CheckCircle2 className="h-2.5 w-2.5" /> : <XCircle className="h-2.5 w-2.5" />}
                          {t.is_active ? 'Active' : 'Disabled'}
                        </span>
                      </td>
                      <td className="py-3.5 px-3 font-mono text-slate-400 text-[11px] whitespace-nowrap">
                        {t.next_fire_time ? new Date(t.next_fire_time).toLocaleString() : '—'}
                      </td>
                      <td className="py-3.5 px-3 font-mono text-slate-500 text-[11px] whitespace-nowrap">
                        {t.last_fired_at ? new Date(t.last_fired_at).toLocaleTimeString() : 'Never'}
                      </td>
                      <td className="py-3.5 px-4 text-right whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-end gap-1.5 relative">
                          <button
                            onClick={() => handleFireNow(t)}
                            className="p-1.5 rounded hover:bg-slate-800 text-emerald-400 hover:text-emerald-300 transition"
                            title="Trigger Now (Immediate Dispatch)"
                          >
                            <Play className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => handleOpenHistory(t)}
                            className="p-1.5 rounded hover:bg-slate-800 text-cyan-400 hover:text-cyan-300 transition"
                            title="View Execution History"
                          >
                            <History className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => handleToggleActivate(t)}
                            className={`p-1.5 rounded hover:bg-slate-800 transition ${
                              t.is_active ? 'text-amber-400' : 'text-slate-500'
                            }`}
                            title={t.is_active ? 'Deactivate Trigger' : 'Activate Trigger'}
                          >
                            <Power className="h-3.5 w-3.5" />
                          </button>

                          {/* 3-dots Context Menu Button */}
                          <div className="relative">
                            <button
                              onClick={() => setActiveDropdownTriggerId(isMenuOpen ? null : t.id)}
                              className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-white transition"
                              title="Trigger Options"
                            >
                              <MoreVertical className="h-3.5 w-3.5" />
                            </button>

                            {/* Dropdown Menu */}
                            {isMenuOpen && (
                              <div 
                                className="absolute right-0 top-7 w-48 bg-slate-950 border border-slate-800 rounded-lg shadow-xl py-1 z-30 text-xs text-left"
                                onClick={(e) => e.stopPropagation()}
                              >
                                <button
                                  onClick={() => {
                                    setActiveDropdownTriggerId(null);
                                    handleSelectTrigger(t);
                                  }}
                                  className="w-full px-3 py-1.5 text-left text-slate-200 hover:bg-slate-800 flex items-center gap-2 transition"
                                >
                                  <Eye className="h-3.5 w-3.5 text-brand-400" />
                                  <span>View Details</span>
                                </button>
                                <button
                                  onClick={() => {
                                    setActiveDropdownTriggerId(null);
                                    handleFireNow(t);
                                  }}
                                  className="w-full px-3 py-1.5 text-left text-emerald-400 hover:bg-emerald-600 hover:text-white flex items-center gap-2 transition"
                                >
                                  <Play className="h-3.5 w-3.5" />
                                  <span>Fire Trigger Now</span>
                                </button>
                                <button
                                  onClick={() => {
                                    setActiveDropdownTriggerId(null);
                                    handleToggleActivate(t);
                                  }}
                                  className="w-full px-3 py-1.5 text-left text-amber-400 hover:bg-amber-600 hover:text-white flex items-center gap-2 transition"
                                >
                                  <Power className="h-3.5 w-3.5" />
                                  <span>{t.is_active ? 'Pause Trigger' : 'Activate Trigger'}</span>
                                </button>
                                <button
                                  onClick={() => {
                                    setActiveDropdownTriggerId(null);
                                    handleOpenHistory(t);
                                  }}
                                  className="w-full px-3 py-1.5 text-left text-cyan-400 hover:bg-cyan-600 hover:text-white flex items-center gap-2 transition"
                                >
                                  <History className="h-3.5 w-3.5" />
                                  <span>Execution History</span>
                                </button>
                                <button
                                  onClick={() => {
                                    setActiveDropdownTriggerId(null);
                                    handleDuplicateTrigger(t);
                                  }}
                                  className="w-full px-3 py-1.5 text-left text-slate-300 hover:bg-slate-800 flex items-center gap-2 transition"
                                >
                                  <Copy className="h-3.5 w-3.5 text-slate-400" />
                                  <span>Duplicate Trigger</span>
                                </button>
                                {(t.pipeline_id || t.pipelines_to_run?.[0]?.pipeline_id) && (
                                  <button
                                    onClick={() => {
                                      setActiveDropdownTriggerId(null);
                                      const pId = t.pipeline_id || t.pipelines_to_run?.[0]?.pipeline_id;
                                      if (pId) {
                                        setSelectedPipelineId(pId);
                                        setCurrentTab('designer');
                                      }
                                    }}
                                    className="w-full px-3 py-1.5 text-left text-indigo-300 hover:bg-indigo-600 hover:text-white flex items-center gap-2 transition"
                                  >
                                    <ExternalLink className="h-3.5 w-3.5" />
                                    <span>Open Pipeline</span>
                                  </button>
                                )}
                                <div className="my-1 border-t border-slate-800" />
                                <button
                                  onClick={() => {
                                    setActiveDropdownTriggerId(null);
                                    handleDeleteTrigger(t.id);
                                  }}
                                  className="w-full px-3 py-1.5 text-left text-rose-400 hover:bg-rose-600 hover:text-white flex items-center gap-2 transition"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                  <span>Delete Trigger</span>
                                </button>
                              </div>
                            )}
                          </div>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ================================================================= */}
      {/* TRIGGER DETAILS & OPTIONS DRAWER                                  */}
      {/* ================================================================= */}
      {selectedTriggerForDetails && (
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
                    <Clock className="h-5 w-5" />
                  </div>
                  <div>
                    <h2 className="text-base font-bold text-white tracking-tight">
                      {selectedTriggerForDetails.name}
                    </h2>
                    <div className="text-xs text-slate-400 font-mono mt-0.5 flex items-center gap-2">
                      <span>Type: {selectedTriggerForDetails.trigger_type}</span>
                      <span>•</span>
                      <span>ID: {selectedTriggerForDetails.id.slice(0, 8)}...</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                    selectedTriggerForDetails.is_active
                      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                      : 'bg-slate-800 text-slate-400 border-slate-700'
                  }`}>
                    {selectedTriggerForDetails.is_active ? 'Active' : 'Disabled'}
                  </span>
                  <button
                    onClick={() => setSelectedTriggerForDetails(null)}
                    className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>
              </div>

              {selectedTriggerForDetails.description && (
                <p className="text-xs text-slate-300">
                  {selectedTriggerForDetails.description}
                </p>
              )}

              {/* Action Toolbar */}
              <div className="pt-2 flex items-center gap-2 flex-wrap">
                <button
                  onClick={() => handleFireNow(selectedTriggerForDetails)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium transition shadow-sm"
                >
                  <Play className="h-3.5 w-3.5" />
                  <span>Fire Trigger Now</span>
                </button>

                <button
                  onClick={() => handleToggleActivate(selectedTriggerForDetails)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition border ${
                    selectedTriggerForDetails.is_active
                      ? 'bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border-amber-500/30'
                      : 'bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                  }`}
                >
                  <Power className="h-3.5 w-3.5" />
                  <span>{selectedTriggerForDetails.is_active ? 'Pause Trigger' : 'Activate Trigger'}</span>
                </button>

                <button
                  onClick={() => handleDuplicateTrigger(selectedTriggerForDetails)}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition border border-slate-700"
                >
                  <Copy className="h-3.5 w-3.5" />
                  <span>Duplicate</span>
                </button>

                <button
                  onClick={() => handleOpenHistory(selectedTriggerForDetails)}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-cyan-300 text-xs font-medium transition border border-slate-700"
                >
                  <History className="h-3.5 w-3.5" />
                  <span>Runs History</span>
                </button>

                <button
                  onClick={() => handleDeleteTrigger(selectedTriggerForDetails.id)}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 text-xs font-medium transition border border-rose-500/30 ml-auto"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  <span>Delete</span>
                </button>
              </div>

              {/* Drawer Tabs */}
              <div className="flex items-center gap-2 border-b border-slate-800 pt-2 text-xs">
                {[
                  { id: 'config', label: 'Configuration & Recurrence' },
                  { id: 'pipelines', label: `Target Pipelines (${selectedTriggerForDetails.pipelines_to_run?.length || (selectedTriggerForDetails.pipeline_id ? 1 : 0)})` },
                  { id: 'runs', label: `Execution History (${triggerDetailsRuns.length})` }
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setDrawerActiveTab(tab.id as any)}
                    className={`pb-2 px-1 font-medium transition border-b-2 ${
                      drawerActiveTab === tab.id
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
              {drawerActiveTab === 'config' && (
                <div className="space-y-4">
                  {/* Recurrence Card */}
                  <div className="p-4 bg-slate-950/70 border border-slate-800 rounded-xl space-y-3">
                    <div className="font-semibold text-slate-200 flex items-center justify-between">
                      <span>Schedule & Event Parameters</span>
                      {getTypeBadge(selectedTriggerForDetails.trigger_type)}
                    </div>

                    {selectedTriggerForDetails.trigger_type === 'schedule' || selectedTriggerForDetails.trigger_type === 'cron' ? (
                      <div className="space-y-2 text-slate-300">
                        <div className="flex items-center justify-between py-1 border-b border-slate-900">
                          <span className="text-slate-400">Cron Expression:</span>
                          <span className="font-mono bg-slate-900 px-2 py-0.5 rounded text-brand-300">
                            {selectedTriggerForDetails.cron_expression || '0 * * * *'}
                          </span>
                        </div>
                        <div className="flex items-center justify-between py-1 border-b border-slate-900">
                          <span className="text-slate-400">Timezone:</span>
                          <span className="font-mono text-slate-200">
                            {selectedTriggerForDetails.schedule_config?.timezone || 'UTC'}
                          </span>
                        </div>
                        <div className="flex items-center justify-between py-1 border-b border-slate-900">
                          <span className="text-slate-400">Start Time:</span>
                          <span className="font-mono text-slate-200">
                            {selectedTriggerForDetails.schedule_config?.start_time ? new Date(selectedTriggerForDetails.schedule_config.start_time).toLocaleString() : 'Immediate'}
                          </span>
                        </div>
                        <div className="flex items-center justify-between py-1 border-b border-slate-900">
                          <span className="text-slate-400">End Time:</span>
                          <span className="font-mono text-slate-200">
                            {selectedTriggerForDetails.schedule_config?.end_time ? new Date(selectedTriggerForDetails.schedule_config.end_time).toLocaleString() : 'Runs Indefinitely'}
                          </span>
                        </div>
                      </div>
                    ) : selectedTriggerForDetails.trigger_type === 'tumbling_window' ? (
                      <div className="space-y-2 text-slate-300">
                        <div className="flex items-center justify-between py-1 border-b border-slate-900">
                          <span className="text-slate-400">Window Slice:</span>
                          <span className="font-mono text-cyan-300">
                            {selectedTriggerForDetails.tumbling_window_config?.interval} {selectedTriggerForDetails.tumbling_window_config?.frequency}
                          </span>
                        </div>
                        <div className="flex items-center justify-between py-1 border-b border-slate-900">
                          <span className="text-slate-400">Delay Minutes:</span>
                          <span className="font-mono text-slate-200">
                            {selectedTriggerForDetails.tumbling_window_config?.delay_minutes || 0}m
                          </span>
                        </div>
                        <div className="flex items-center justify-between py-1 border-b border-slate-900">
                          <span className="text-slate-400">Max Concurrency:</span>
                          <span className="font-mono text-slate-200">
                            {selectedTriggerForDetails.tumbling_window_config?.max_concurrency || 1}
                          </span>
                        </div>
                        <div className="flex items-center justify-between py-1 border-b border-slate-900">
                          <span className="text-slate-400">Depends on Prior Window:</span>
                          <span className="font-mono text-slate-200">
                            {selectedTriggerForDetails.tumbling_window_config?.depends_on_prior_window ? 'Yes (Enforced)' : 'No'}
                          </span>
                        </div>
                      </div>
                    ) : selectedTriggerForDetails.trigger_type === 'storage_event' ? (
                      <div className="space-y-2 text-slate-300">
                        <div className="flex items-center justify-between py-1 border-b border-slate-900">
                          <span className="text-slate-400">Bucket / Container:</span>
                          <span className="font-mono text-emerald-300">
                            {selectedTriggerForDetails.storage_event_config?.container}
                          </span>
                        </div>
                        <div className="flex items-center justify-between py-1 border-b border-slate-900">
                          <span className="text-slate-400">Prefix Filter:</span>
                          <span className="font-mono text-slate-200">
                            {selectedTriggerForDetails.storage_event_config?.prefix || '/'}
                          </span>
                        </div>
                        <div className="flex items-center justify-between py-1 border-b border-slate-900">
                          <span className="text-slate-400">Suffix Filter:</span>
                          <span className="font-mono text-slate-200">
                            {selectedTriggerForDetails.storage_event_config?.suffix || '*'}
                          </span>
                        </div>
                      </div>
                    ) : (
                      <div className="text-slate-400 text-xs">
                        Manual on-demand dispatch trigger. Fires whenever manually invoked or requested by external webhook.
                      </div>
                    )}
                  </div>

                  {/* Firing Diagnostics Card */}
                  <div className="p-4 bg-slate-950/70 border border-slate-800 rounded-xl space-y-2">
                    <div className="font-semibold text-slate-200">Execution Timestamps</div>
                    <div className="flex items-center justify-between py-1 border-b border-slate-900">
                      <span className="text-slate-400">Next Scheduled Fire:</span>
                      <span className="font-mono text-brand-300">
                        {selectedTriggerForDetails.next_fire_time ? new Date(selectedTriggerForDetails.next_fire_time).toLocaleString() : 'Not Scheduled (Paused)'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between py-1">
                      <span className="text-slate-400">Last Fired At:</span>
                      <span className="font-mono text-slate-300">
                        {selectedTriggerForDetails.last_fired_at ? new Date(selectedTriggerForDetails.last_fired_at).toLocaleString() : 'Never Fired'}
                      </span>
                    </div>
                  </div>

                  {/* Parameters JSON */}
                  <div className="space-y-1.5">
                    <div className="font-medium text-slate-400">Static Trigger Parameters:</div>
                    <pre className="p-3 bg-slate-950 rounded-lg border border-slate-800 text-[11px] font-mono text-slate-300 overflow-x-auto">
                      {JSON.stringify(selectedTriggerForDetails.parameters || {}, null, 2)}
                    </pre>
                  </div>
                </div>
              )}

              {drawerActiveTab === 'pipelines' && (
                <div className="space-y-3">
                  <div className="text-slate-400 font-medium">Pipelines Invoked on Each Trigger Event:</div>
                  {(!selectedTriggerForDetails.pipelines_to_run || selectedTriggerForDetails.pipelines_to_run.length === 0) && !selectedTriggerForDetails.pipeline_id ? (
                    <div className="text-center py-8 text-slate-500">
                      No target pipelines attached to this trigger.
                    </div>
                  ) : (
                    (selectedTriggerForDetails.pipelines_to_run || [{ pipeline_id: selectedTriggerForDetails.pipeline_id! }]).map((tp, idx) => {
                      const pObj = pipelines.find((p) => p.id === tp.pipeline_id);
                      return (
                        <div
                          key={idx}
                          className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-xl flex items-center justify-between gap-3"
                        >
                          <div className="space-y-1">
                            <div className="font-semibold text-white flex items-center gap-2">
                              <GitBranch className="h-4 w-4 text-brand-400" />
                              <span>{pObj ? pObj.name : tp.pipeline_id}</span>
                            </div>
                            <div className="text-[11px] text-slate-400 font-mono">
                              v{pObj?.current_version || 1} • {pObj?.definition_json?.activities?.length || 0} activities
                            </div>
                            {tp.parameters && Object.keys(tp.parameters).length > 0 && (
                              <div className="text-[10px] text-slate-500 font-mono">
                                Overrides: {JSON.stringify(tp.parameters)}
                              </div>
                            )}
                          </div>

                          <button
                            onClick={() => {
                              setSelectedPipelineId(tp.pipeline_id);
                              setCurrentTab('designer');
                            }}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand-600/20 hover:bg-brand-600/30 text-brand-300 border border-brand-500/30 font-medium transition"
                          >
                            <ExternalLink className="h-3.5 w-3.5" />
                            <span>Open Designer</span>
                          </button>
                        </div>
                      );
                    })
                  )}
                </div>
              )}

              {drawerActiveTab === 'runs' && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400 font-medium">Trigger Execution Runs:</span>
                    <button
                      onClick={() => handleOpenHistory(selectedTriggerForDetails)}
                      className="text-brand-400 hover:text-brand-300 font-medium flex items-center gap-1"
                    >
                      <span>Full Audit Log</span>
                      <ExternalLink className="h-3.5 w-3.5" />
                    </button>
                  </div>

                  {loadingDetailsRuns ? (
                    <div className="text-center py-6 text-slate-500">
                      <RefreshCw className="h-4 w-4 animate-spin mx-auto mb-1 text-brand-400" />
                      Loading history...
                    </div>
                  ) : triggerDetailsRuns.length === 0 ? (
                    <div className="text-center py-8 text-slate-500 space-y-2">
                      <History className="h-6 w-6 mx-auto text-slate-600" />
                      <div>No firings recorded for this trigger yet.</div>
                      <button
                        onClick={() => handleFireNow(selectedTriggerForDetails)}
                        className="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs"
                      >
                        Fire Now
                      </button>
                    </div>
                  ) : (
                    triggerDetailsRuns.map((r) => (
                      <div
                        key={r.id}
                        className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2"
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                              r.run_status === 'Succeeded'
                                ? 'bg-emerald-500/20 text-emerald-400'
                                : r.run_status === 'Running'
                                ? 'bg-cyan-500/20 text-cyan-400'
                                : 'bg-rose-500/20 text-rose-400'
                            }`}>
                              {r.run_status}
                            </span>
                            <span className="font-mono text-slate-300 text-[11px]">
                              {new Date(r.fired_at).toLocaleString()}
                            </span>
                          </div>
                          <span className="font-mono text-slate-500 text-[10px]">{r.duration_ms}ms</span>
                        </div>

                        {r.triggered_pipeline_runs && r.triggered_pipeline_runs.length > 0 && (
                          <div className="flex flex-wrap gap-2 pt-1 border-t border-slate-900">
                            {r.triggered_pipeline_runs.map((pr, pidx) => (
                              <button
                                key={pidx}
                                onClick={() => setCurrentTab('runs')}
                                className="px-2 py-0.5 rounded bg-slate-900 hover:bg-slate-800 border border-slate-800 text-brand-300 font-mono text-[10px] flex items-center gap-1.5 transition"
                                title="Inspect Pipeline Run in Monitor"
                              >
                                <span>{pr.pipeline_name || pr.pipeline_id.slice(0, 8)}</span>
                                <span className="text-slate-500">[{pr.status}]</span>
                                <ExternalLink className="h-2.5 w-2.5 text-slate-400" />
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>

            {/* Drawer Footer */}
            <div className="p-4 border-t border-slate-800 bg-slate-900/90 flex justify-between items-center text-xs">
              <span className="text-slate-500 font-mono">
                Trigger ID: {selectedTriggerForDetails.id}
              </span>
              <button
                onClick={() => setSelectedTriggerForDetails(null)}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300"
              >
                Close Drawer
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ================================================================= */}
      {/* CREATE TRIGGER WIZARD MODAL                                       */}
      {/* ================================================================= */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-2xl w-full p-6 space-y-4 my-8">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-brand-400" />
                <h3 className="text-sm font-semibold text-white">Create Enterprise Trigger</h3>
              </div>
              <button onClick={() => setShowAddModal(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <form onSubmit={handleCreateTrigger} className="space-y-4 text-xs">
              {/* Trigger Type Selection Pills */}
              <div>
                <label className="block text-slate-400 mb-1.5 font-medium">Select Trigger Pattern</label>
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                  {[
                    { id: 'schedule', label: 'Schedule', icon: Clock },
                    { id: 'tumbling_window', label: 'Tumbling Window', icon: Layers },
                    { id: 'storage_event', label: 'Storage Event', icon: HardDrive },
                    { id: 'pipeline_dependency', label: 'Dependency', icon: GitBranch },
                    { id: 'manual', label: 'Manual', icon: Play }
                  ].map((item) => {
                    const Icon = item.icon;
                    return (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => setWizardType(item.id)}
                        className={`p-2.5 rounded-lg border flex flex-col items-center gap-1.5 transition text-center ${
                          wizardType === item.id
                            ? 'bg-brand-600/20 border-brand-500 text-brand-300 font-semibold shadow-sm'
                            : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        <Icon className="h-4 w-4 shrink-0" />
                        <span className="text-[11px]">{item.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* General Metadata */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">Trigger Name *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Ingestion_Hourly_ETL"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500 font-medium"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Description</label>
                  <input
                    type="text"
                    placeholder="Optional purpose of this trigger"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500"
                  />
                </div>
              </div>

              {/* Target Pipelines Selection */}
              <div>
                <label className="block text-slate-400 mb-1 font-medium">Target Pipeline(s) *</label>
                <select
                  multiple
                  required
                  value={selectedPipelineIds}
                  onChange={(e) => {
                    const selected = Array.from(e.target.selectedOptions, (option) => option.value);
                    setSelectedPipelineIds(selected);
                  }}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-brand-500 h-24"
                >
                  {pipelines.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} (v{p.current_version})
                    </option>
                  ))}
                </select>
                <span className="text-[10px] text-slate-500">Hold Ctrl / Cmd to select multiple pipelines to execute in parallel.</span>
              </div>

              {/* ============================================================= */}
              {/* TYPE-SPECIFIC PANELS                                          */}
              {/* ============================================================= */}

              {/* 1. Schedule Configuration */}
              {wizardType === 'schedule' && (
                <div className="p-3 bg-slate-950/70 border border-indigo-500/30 rounded-lg space-y-3">
                  <div className="text-[11px] font-semibold text-indigo-300 flex items-center gap-1.5">
                    <Clock className="h-3.5 w-3.5" />
                    Schedule & Timezone Recurrence Settings
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-slate-400 mb-1">Cron Expression (UTC or Local)</label>
                      <input
                        type="text"
                        required
                        placeholder="0 * * * * (hourly)"
                        value={cronExpression}
                        onChange={(e) => setCronExpression(e.target.value)}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500 font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1">Timezone</label>
                      <select
                        value={timezoneStr}
                        onChange={(e) => setTimezoneStr(e.target.value)}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500"
                      >
                        {COMMON_TIMEZONES.map((tz) => (
                          <option key={tz} value={tz}>
                            {tz}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1">Start Date / Time (Optional)</label>
                      <input
                        type="datetime-local"
                        value={scheduleStartTime}
                        onChange={(e) => setScheduleStartTime(e.target.value)}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1">End Date / Time (Expiry Optional)</label>
                      <input
                        type="datetime-local"
                        value={scheduleEndTime}
                        onChange={(e) => setScheduleEndTime(e.target.value)}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500"
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* 2. Tumbling Window Configuration */}
              {wizardType === 'tumbling_window' && (
                <div className="p-3 bg-slate-950/70 border border-cyan-500/30 rounded-lg space-y-3">
                  <div className="text-[11px] font-semibold text-cyan-300 flex items-center gap-1.5">
                    <Layers className="h-3.5 w-3.5" />
                    Tumbling Window Slice & Concurrency Settings
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div>
                      <label className="block text-slate-400 mb-1">Frequency</label>
                      <select
                        value={twFrequency}
                        onChange={(e) => setTwFrequency(e.target.value)}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200"
                      >
                        <option value="Minute">Minute</option>
                        <option value="Hour">Hour</option>
                        <option value="Day">Day</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1">Interval</label>
                      <input
                        type="number"
                        min={1}
                        value={twInterval}
                        onChange={(e) => setTwInterval(parseInt(e.target.value) || 1)}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1">Delay (Minutes)</label>
                      <input
                        type="number"
                        min={0}
                        value={twDelayMinutes}
                        onChange={(e) => setTwDelayMinutes(parseInt(e.target.value) || 0)}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1">Max Concurrency</label>
                      <input
                        type="number"
                        min={1}
                        max={10}
                        value={twMaxConcurrency}
                        onChange={(e) => setTwMaxConcurrency(parseInt(e.target.value) || 1)}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">Historical Window Start Time *</label>
                    <input
                      type="datetime-local"
                      required
                      value={twStartTime}
                      onChange={(e) => setTwStartTime(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-slate-200 font-mono"
                    />
                  </div>
                  <div className="flex items-center gap-2 pt-1">
                    <input
                      type="checkbox"
                      id="tw_prior"
                      checked={twDependsOnPrior}
                      onChange={(e) => setTwDependsOnPrior(e.target.checked)}
                      className="rounded border-slate-700 bg-slate-950 text-cyan-500"
                    />
                    <label htmlFor="tw_prior" className="text-slate-300 text-[11px] cursor-pointer">
                      Depends on Prior Window (Window N only executes if Window N-1 Succeeded)
                    </label>
                  </div>
                </div>
              )}

              {/* 3. Storage Event Configuration */}
              {wizardType === 'storage_event' && (
                <div className="p-3 bg-slate-950/70 border border-emerald-500/30 rounded-lg space-y-3">
                  <div className="text-[11px] font-semibold text-emerald-300 flex items-center gap-1.5">
                    <HardDrive className="h-3.5 w-3.5" />
                    Storage Event Arrival Listener (Azure ADLS/Blob, AWS S3, GCP GCS, Local)
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-slate-400 mb-1">Storage Connection *</label>
                      <select
                        required
                        value={storageConnId}
                        onChange={(e) => setStorageConnId(e.target.value)}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-slate-200"
                      >
                        {connections.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.name} ({c.connector_type})
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1">Container / Bucket Name *</label>
                      <input
                        type="text"
                        required
                        placeholder="e.g. raw-landing or s3-bucket"
                        value={storageContainer}
                        onChange={(e) => setStorageContainer(e.target.value)}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-slate-200 font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1">Folder Prefix</label>
                      <input
                        type="text"
                        placeholder="e.g. incoming/orders/"
                        value={storagePrefix}
                        onChange={(e) => setStoragePrefix(e.target.value)}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-slate-200 font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1">File Suffix / Extension</label>
                      <input
                        type="text"
                        placeholder="e.g. .csv or .parquet"
                        value={storageSuffix}
                        onChange={(e) => setStorageSuffix(e.target.value)}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-slate-200 font-mono"
                      />
                    </div>
                  </div>
                  <div className="flex items-center gap-2 pt-1">
                    <input
                      type="checkbox"
                      id="st_empty"
                      checked={storageIgnoreEmpty}
                      onChange={(e) => setStorageIgnoreEmpty(e.target.checked)}
                      className="rounded border-slate-700 bg-slate-950 text-emerald-500"
                    />
                    <label htmlFor="st_empty" className="text-slate-300 text-[11px] cursor-pointer">
                      Ignore zero-byte empty files
                    </label>
                  </div>
                </div>
              )}

              {/* 4. Pipeline Dependency Configuration */}
              {wizardType === 'pipeline_dependency' && (
                <div className="p-3 bg-slate-950/70 border border-purple-500/30 rounded-lg space-y-3">
                  <div className="text-[11px] font-semibold text-purple-300 flex items-center justify-between">
                    <span className="flex items-center gap-1.5">
                      <GitBranch className="h-3.5 w-3.5" />
                      Upstream Pipeline Dependency & Status Triggers
                    </span>
                    <button
                      type="button"
                      onClick={handlePreflightCycleCheck}
                      className="px-2 py-0.5 rounded bg-purple-600/30 hover:bg-purple-600/50 text-purple-200 border border-purple-500/40 text-[10px] font-medium transition"
                    >
                      Preflight Cycle Check
                    </button>
                  </div>

                  {cycleCheckResult && (
                    <div
                      className={`p-2 rounded border text-[11px] flex items-center gap-1.5 ${
                        cycleCheckResult.valid
                          ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                          : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                      }`}
                    >
                      {cycleCheckResult.valid ? <CheckCircle2 className="h-3.5 w-3.5 shrink-0" /> : <ShieldAlert className="h-3.5 w-3.5 shrink-0" />}
                      <span>{cycleCheckResult.message}</span>
                    </div>
                  )}

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-slate-400 mb-1">Upstream Pipeline *</label>
                      <select
                        required
                        value={upstreamPipelineId}
                        onChange={(e) => setUpstreamPipelineId(e.target.value)}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-slate-200"
                      >
                        <option value="">Select upstream pipeline...</option>
                        {pipelines.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.name}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="block text-slate-400 mb-1">Fire on Status</label>
                      <select
                        value={fireOnStatuses[0] || 'Succeeded'}
                        onChange={(e) => setFireOnStatuses([e.target.value])}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-slate-200"
                      >
                        <option value="Succeeded">Succeeded Only</option>
                        <option value="Failed">Failed Only (Failure Handler)</option>
                        <option value="Completed">Any Terminal Completion (Success or Fail)</option>
                      </select>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 pt-1">
                    <input
                      type="checkbox"
                      id="forward_params"
                      checked={forwardParams}
                      onChange={(e) => setForwardParams(e.target.checked)}
                      className="rounded border-slate-700 bg-slate-950 text-purple-500"
                    />
                    <label htmlFor="forward_params" className="text-slate-300 text-[11px] cursor-pointer">
                      Forward Upstream Pipeline Parameters as @triggerBody() arguments
                    </label>
                  </div>
                </div>
              )}

              {/* Parameters JSON */}
              <div>
                <label className="block text-slate-400 mb-1">Parameters (JSON Object)</label>
                <textarea
                  rows={2}
                  value={parametersJson}
                  onChange={(e) => setParametersJson(e.target.value)}
                  placeholder='{"environment": "prod", "batch_size": 5000}'
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-slate-200 font-mono text-[11px] focus:outline-none focus:border-brand-500"
                />
              </div>

              {/* Action Buttons */}
              <div className="pt-3 border-t border-slate-800 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-1.5 bg-brand-600 hover:bg-brand-500 text-white font-medium rounded transition disabled:opacity-50 flex items-center gap-1.5"
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  <span>{isSubmitting ? 'Creating...' : 'Activate Trigger'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ================================================================= */}
      {/* TRIGGER RUN HISTORY DRAWER / MODAL                                */}
      {/* ================================================================= */}
      {showHistoryModal && selectedTriggerForHistory && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-4xl w-full p-6 space-y-4 max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 shrink-0">
              <div className="flex items-center gap-2">
                <History className="h-4 w-4 text-cyan-400" />
                <div>
                  <h3 className="text-sm font-semibold text-white">
                    Execution History: {selectedTriggerForHistory.name}
                  </h3>
                  <div className="text-[11px] text-slate-400 flex items-center gap-2 mt-0.5">
                    <span>Type: {selectedTriggerForHistory.trigger_type}</span>
                    <span>•</span>
                    <span>Total Runs: {triggerRuns.length}</span>
                  </div>
                </div>
              </div>
              <button onClick={() => setShowHistoryModal(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <div className="overflow-y-auto flex-1 space-y-3">
              {loadingHistory ? (
                <div className="py-12 text-center text-slate-500 text-xs">
                  <RefreshCw className="h-5 w-5 animate-spin mx-auto mb-2 text-cyan-400" />
                  Loading execution runs...
                </div>
              ) : triggerRuns.length === 0 ? (
                <div className="py-12 text-center text-slate-500 text-xs">
                  No historical trigger dispatches recorded yet. Click "Trigger Now" to test!
                </div>
              ) : (
                triggerRuns.map((run) => (
                  <div key={run.id} className="p-3.5 bg-slate-950/60 border border-slate-800 rounded-lg space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                            run.run_status === 'Succeeded'
                              ? 'bg-emerald-500/20 text-emerald-400'
                              : run.run_status === 'Running'
                              ? 'bg-cyan-500/20 text-cyan-400'
                              : 'bg-rose-500/20 text-rose-400'
                          }`}
                        >
                          {run.run_status}
                        </span>
                        <span className="font-mono text-slate-400 text-[11px]">
                          Fired: {new Date(run.fired_at).toLocaleString()}
                        </span>
                        <span className="text-slate-500 text-[10px]">•</span>
                        <span className="text-slate-500 text-[10px] font-mono">{run.duration_ms}ms</span>
                      </div>
                      <span className="font-mono text-slate-600 text-[10px]">ID: {run.id.slice(0, 8)}</span>
                    </div>

                    {/* Dispatched Pipeline Runs */}
                    <div className="text-[11px] text-slate-300">
                      <span className="text-slate-400 text-[10px] uppercase font-semibold">Dispatched Pipelines:</span>
                      <div className="flex flex-wrap gap-2 mt-1">
                        {run.triggered_pipeline_runs && run.triggered_pipeline_runs.length > 0 ? (
                          run.triggered_pipeline_runs.map((pr, idx) => (
                            <span
                              key={idx}
                              className="px-2 py-1 rounded bg-slate-900 border border-slate-700 text-slate-200 font-mono text-[10px] flex items-center gap-1.5"
                            >
                              <span>{pr.pipeline_name || pr.pipeline_id}</span>
                              <span className="text-slate-500">[{pr.status}]</span>
                            </span>
                          ))
                        ) : (
                          <span className="text-slate-500 text-[10px]">Direct Runner Dispatch</span>
                        )}
                      </div>
                    </div>

                    {/* Event Payload Inspector */}
                    {run.event_payload && Object.keys(run.event_payload).length > 0 && (
                      <div className="mt-2 pt-2 border-t border-slate-900">
                        <span className="text-[10px] text-slate-500 font-mono">Event Payload Metadata:</span>
                        <pre className="mt-1 bg-slate-950 p-2 rounded border border-slate-900 text-[10px] font-mono text-slate-300 overflow-x-auto">
                          {JSON.stringify(run.event_payload, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>

            <div className="pt-3 border-t border-slate-800 flex justify-end shrink-0">
              <button
                onClick={() => setShowHistoryModal(false)}
                className="px-4 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs"
              >
                Close History
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
