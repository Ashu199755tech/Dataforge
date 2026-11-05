import React, { useState, useEffect } from 'react';
import {
  Database,
  HardDrive,
  Cloud,
  Server,
  Settings2,
  ArrowRight,
  Sparkles,
  Plus,
  Trash2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Sliders,
  Layers,
  FolderSearch,
  ShieldCheck,
  Cpu,
  Zap,
  FileText,
  FileCode,
  RefreshCw,
  FileSpreadsheet,
  Check
} from 'lucide-react';
import api from '../../api/client';
import { StorageHierarchyBrowserModal } from './StorageHierarchyBrowserModal';

interface ConnectionOption {
  id: string;
  name: string;
  connector_type: string;
}

interface ColumnMapping {
  source_column: string;
  source_type: string;
  destination_column: string;
  destination_type: string;
  mapping_expression?: string;
  exclude?: boolean;
}

interface ExplicitSchemaColumn {
  name: string;
  type: string;
  nullable?: boolean;
}

interface CopyDataConfigTabsProps {
  activityId: string;
  activityLabel: string;
  activityDescription?: string;
  activityState: string;
  retryPolicy: { max_retries: number; retry_interval_seconds: number };
  config: any;
  connections: ConnectionOption[];
  onUpdateGeneral: (updates: {
    label?: string;
    description?: string;
    state?: string;
    retry_policy?: { max_retries: number; retry_interval_seconds: number };
    timeout_seconds?: number;
  }) => void;
  onUpdateConfig: (partialConfig: any) => void;
  onOpenExpressionBuilder?: (fieldName: string, value: string, onApply: (val: string) => void) => void;
}

export type CopyDataTabKey =
  | 'general'
  | 'source'
  | 'source_settings'
  | 'destination'
  | 'mapping'
  | 'performance'
  | 'advanced';

export const CopyDataConfigTabs: React.FC<CopyDataConfigTabsProps> = ({
  activityId,
  activityLabel,
  activityDescription = '',
  activityState,
  retryPolicy,
  config,
  connections,
  onUpdateGeneral,
  onUpdateConfig,
  onOpenExpressionBuilder
}) => {
  const [activeTab, setActiveTab] = useState<CopyDataTabKey>('source');

  // Source & Destination connection testing state
  const [testingSrc, setTestingSrc] = useState(false);
  const [srcTestResult, setSrcTestResult] = useState<{ success: boolean; message: string; latency_ms?: number } | null>(null);

  const [testingDst, setTestingDst] = useState(false);
  const [dstTestResult, setDstTestResult] = useState<{ success: boolean; message: string; latency_ms?: number } | null>(null);

  // Storage Hierarchy Browser Modal state
  const [browserModalOpen, setBrowserModalOpen] = useState(false);
  const [browserTarget, setBrowserTarget] = useState<'source' | 'destination'>('source');

  // Source containers list cached
  const [sourceContainers, setSourceContainers] = useState<string[]>([]);
  const [destContainers, setDestContainers] = useState<string[]>([]);

  // Safe nested config access
  const source = config.source || {};
  const sourceSettings = config.source_settings || {};
  const destination = config.destination || {};
  const mappings: ColumnMapping[] = config.column_mappings || [];
  const performance = config.performance || {};
  const advanced = config.advanced || {};

  // Find connection objects
  const srcConn = connections.find((c) => c.id === source.connection_id);
  const dstConn = connections.find((c) => c.id === destination.connection_id);

  const isStorageConnector = (connectorType?: string) => {
    if (!connectorType) return false;
    const t = connectorType.toLowerCase();
    return ['azure_blob', 'blob', 'azure_adls', 'adls', 'adls_gen2', 'aws_s3', 's3', 'gcp_storage', 'gcs', 'local_storage', 'file', 'filesystem'].includes(t);
  };

  const isDatabaseConnector = (connectorType?: string) => {
    if (!connectorType) return false;
    const t = connectorType.toLowerCase();
    return ['postgres', 'postgresql', 'pg', 'mysql', 'mariadb', 'sqlite', 'sqlite3'].includes(t);
  };

  const isSrcStorage = isStorageConnector(srcConn?.connector_type) || Boolean(source.container || source.bucket);
  const isDstStorage = isStorageConnector(dstConn?.connector_type) || Boolean(destination.container || destination.bucket);

  // Load containers on source connection selection
  useEffect(() => {
    if (source.connection_id && isStorageConnector(srcConn?.connector_type)) {
      api
        .get(`/connections/${source.connection_id}/storage/containers`)
        .then((res) => {
          if (res.data.is_storage && res.data.containers) {
            setSourceContainers(res.data.containers);
          }
        })
        .catch(() => setSourceContainers([]));
    }
  }, [source.connection_id, srcConn?.connector_type]);

  // Load containers on destination connection selection
  useEffect(() => {
    if (destination.connection_id && isStorageConnector(dstConn?.connector_type)) {
      api
        .get(`/connections/${destination.connection_id}/storage/containers`)
        .then((res) => {
          if (res.data.is_storage && res.data.containers) {
            setDestContainers(res.data.containers);
          }
        })
        .catch(() => setDestContainers([]));
    }
  }, [destination.connection_id, dstConn?.connector_type]);

  // Connection testing handlers
  const handleTestSourceConnection = async () => {
    if (!source.connection_id) return;
    setTestingSrc(true);
    setSrcTestResult(null);
    try {
      const res = await api.post(`/connections/${source.connection_id}/test`);
      setSrcTestResult({
        success: res.data.success,
        message: res.data.message || (res.data.success ? 'Connection verified successfully.' : 'Connection test failed.'),
        latency_ms: res.data.latency_ms
      });
    } catch (err: any) {
      setSrcTestResult({
        success: false,
        message: err?.response?.data?.detail || err?.message || 'Connection test failed.'
      });
    } finally {
      setTestingSrc(false);
    }
  };

  const handleTestDestConnection = async () => {
    if (!destination.connection_id) return;
    setTestingDst(true);
    setDstTestResult(null);
    try {
      const res = await api.post(`/connections/${destination.connection_id}/test`);
      setDstTestResult({
        success: res.data.success,
        message: res.data.message || (res.data.success ? 'Connection verified successfully.' : 'Connection test failed.'),
        latency_ms: res.data.latency_ms
      });
    } catch (err: any) {
      setDstTestResult({
        success: false,
        message: err?.response?.data?.detail || err?.message || 'Connection test failed.'
      });
    } finally {
      setTestingDst(false);
    }
  };

  // Updaters for nested configs
  const updateSource = (partial: any) => {
    onUpdateConfig({
      source: {
        ...source,
        ...partial
      }
    });
  };

  const updateSourceSettings = (partial: any) => {
    onUpdateConfig({
      source_settings: {
        ...sourceSettings,
        ...partial
      }
    });
  };

  const updateDestination = (partial: any) => {
    onUpdateConfig({
      destination: {
        ...destination,
        ...partial
      }
    });
  };

  const updatePerformance = (partial: any) => {
    onUpdateConfig({
      performance: {
        ...performance,
        ...partial
      }
    });
  };

  const updateAdvanced = (partial: any) => {
    onUpdateConfig({
      advanced: {
        ...advanced,
        ...partial
      }
    });
  };

  // Browser Modal Handlers
  const openStorageBrowser = (target: 'source' | 'destination') => {
    setBrowserTarget(target);
    setBrowserModalOpen(true);
  };

  const handleBrowserSelect = (container: string, path: string, isDirectory: boolean) => {
    if (browserTarget === 'source') {
      updateSource({
        container,
        bucket: container,
        path: path || '',
        ingestion_mode: isDirectory ? 'directory' : 'single_file'
      });
    } else {
      updateDestination({
        container,
        bucket: container,
        path: path || ''
      });
    }
  };

  // Mapping Handlers
  const handleAddMapping = () => {
    const updated = [
      ...mappings,
      {
        source_column: '',
        source_type: 'string',
        destination_column: '',
        destination_type: 'string',
        mapping_expression: '',
        exclude: false
      }
    ];
    onUpdateConfig({ column_mappings: updated });
  };

  const handleUpdateMappingRow = (index: number, partial: Partial<ColumnMapping>) => {
    const updated = [...mappings];
    updated[index] = { ...updated[index], ...partial };
    onUpdateConfig({ column_mappings: updated });
  };

  const handleRemoveMappingRow = (index: number) => {
    const updated = mappings.filter((_, idx) => idx !== index);
    onUpdateConfig({ column_mappings: updated });
  };

  const handleAutoMapColumns = async () => {
    // If source has table name and database connector, fetch table columns
    if (source.connection_id && source.table_name && isDatabaseConnector(srcConn?.connector_type)) {
      try {
        const res = await api.get(`/connections/${source.connection_id}/tables/${source.table_name}/columns`);
        const cols = res.data.columns || [];
        const autoMappings: ColumnMapping[] = cols.map((c: any) => ({
          source_column: c.name,
          source_type: c.data_type || 'string',
          destination_column: c.name,
          destination_type: c.data_type || 'string',
          exclude: false
        }));
        onUpdateConfig({ column_mappings: autoMappings });
        return;
      } catch (err) {
        console.error('Failed to fetch table columns for automap:', err);
      }
    }

    // Default template auto-map
    const defaultCols: ColumnMapping[] = [
      { source_column: 'id', source_type: 'integer', destination_column: 'id', destination_type: 'integer' },
      { source_column: 'name', source_type: 'string', destination_column: 'name', destination_type: 'string' },
      { source_column: 'amount', source_type: 'float', destination_column: 'amount', destination_type: 'float' },
      { source_column: 'status', source_type: 'string', destination_column: 'status', destination_type: 'string' },
      { source_column: 'created_at', source_type: 'timestamp', destination_column: 'created_at', destination_type: 'timestamp' }
    ];
    onUpdateConfig({ column_mappings: defaultCols });
  };

  const getProviderBadge = (connectorType?: string) => {
    if (!connectorType) return null;
    const t = connectorType.toLowerCase();
    if (t.includes('azure') || t.includes('adls') || t.includes('blob')) {
      return (
        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-blue-500/10 text-blue-400 border border-blue-500/20 font-medium">
          <Cloud className="h-3 w-3" /> Azure Storage
        </span>
      );
    }
    if (t.includes('aws') || t.includes('s3')) {
      return (
        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-amber-500/10 text-amber-400 border border-amber-500/20 font-medium">
          <Cloud className="h-3 w-3" /> AWS S3
        </span>
      );
    }
    if (t.includes('gcp') || t.includes('gcs')) {
      return (
        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">
          <Cloud className="h-3 w-3" /> Google Cloud Storage
        </span>
      );
    }
    if (t.includes('local') || t.includes('file')) {
      return (
        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-medium">
          <HardDrive className="h-3 w-3" /> Local Volume
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-purple-500/10 text-purple-400 border border-purple-500/20 font-medium">
        <Database className="h-3 w-3" /> Database ({connectorType})
      </span>
    );
  };

  const tabs: { key: CopyDataTabKey; label: string; icon: any }[] = [
    { key: 'general', label: 'General', icon: Settings2 },
    { key: 'source', label: 'Source', icon: Database },
    { key: 'source_settings', label: 'Source Settings', icon: FileSpreadsheet },
    { key: 'destination', label: 'Destination', icon: Server },
    { key: 'mapping', label: 'Mapping', icon: Layers },
    { key: 'performance', label: 'Performance', icon: Zap },
    { key: 'advanced', label: 'Advanced', icon: ShieldCheck }
  ];

  return (
    <div className="flex flex-col h-full text-xs select-none">
      {/* 7 Enterprise Navigation Tabs */}
      <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs overflow-x-auto shrink-0 mb-3.5 scrollbar-thin">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`py-1.5 px-2.5 rounded-md font-medium transition flex items-center gap-1.5 whitespace-nowrap shrink-0 ${
                isActive
                  ? 'bg-brand-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
              }`}
            >
              <Icon className="h-3.5 w-3.5 shrink-0" />
              <span>{tab.label}</span>
              {tab.key === 'mapping' && mappings.length > 0 && (
                <span className="ml-0.5 px-1.5 py-0.2 rounded-full text-[9px] bg-slate-800 text-brand-300 font-mono font-bold">
                  {mappings.length}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* TAB CONTENT CONTAINER */}
      <div className="flex-1 overflow-y-auto pr-1 space-y-4">
        {/* ================================================================= */}
        {/* TAB 1: GENERAL                                                    */}
        {/* ================================================================= */}
        {activeTab === 'general' && (
          <div className="space-y-4">
            <div className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-lg space-y-3">
              <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                <span>Activity Identification</span>
                <Settings2 className="h-4 w-4 text-brand-400" />
              </div>

              <div>
                <label className="block text-slate-400 mb-1 font-medium">Activity Name</label>
                <input
                  type="text"
                  value={activityLabel || ''}
                  onChange={(e) => onUpdateGeneral({ label: e.target.value })}
                  placeholder="e.g. Copy_Cloud_Orders_To_Lakehouse"
                  className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-slate-200 font-medium focus:border-brand-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1 font-medium">Description</label>
                <textarea
                  rows={2}
                  value={activityDescription || ''}
                  onChange={(e) => onUpdateGeneral({ description: e.target.value })}
                  placeholder="Describe the business purpose and SLA of this cloud copy activity..."
                  className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-slate-200 text-xs focus:border-brand-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1 font-medium">Execution State</label>
                <select
                  value={activityState || 'Active'}
                  onChange={(e) => onUpdateGeneral({ state: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-slate-200 font-medium"
                >
                  <option value="Active">Active (Executes during pipeline run)</option>
                  <option value="Disabled">Disabled / Skip (Bypassed during execution)</option>
                </select>
              </div>
            </div>

            {/* Timeout & Retry Policies */}
            <div className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-lg space-y-3">
              <div className="text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                Timeout & Retry Policy
              </div>

              <div className="grid grid-cols-3 gap-2.5">
                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Timeout (sec)</label>
                  <input
                    type="number"
                    min={10}
                    max={86400}
                    value={advanced.timeout_seconds || 3600}
                    onChange={(e) => {
                      const val = parseInt(e.target.value) || 3600;
                      updateAdvanced({ timeout_seconds: val });
                      onUpdateGeneral({ timeout_seconds: val });
                    }}
                    className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Retry Count</label>
                  <input
                    type="number"
                    min={0}
                    max={10}
                    value={retryPolicy?.max_retries || 0}
                    onChange={(e) =>
                      onUpdateGeneral({
                        retry_policy: {
                          ...retryPolicy,
                          max_retries: parseInt(e.target.value) || 0
                        }
                      })
                    }
                    className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Retry Interval (s)</label>
                  <input
                    type="number"
                    min={1}
                    max={3600}
                    value={retryPolicy?.retry_interval_seconds || 30}
                    onChange={(e) =>
                      onUpdateGeneral({
                        retry_policy: {
                          ...retryPolicy,
                          retry_interval_seconds: parseInt(e.target.value) || 30
                        }
                      })
                    }
                    className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs font-mono"
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* TAB 2: SOURCE                                                     */}
        {/* ================================================================= */}
        {activeTab === 'source' && (
          <div className="space-y-4">
            <div className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-lg space-y-3">
              <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                <span>Source Provider & Connection</span>
                <Database className="h-4 w-4 text-amber-400" />
              </div>

              {/* Connection Dropdown with Provider Badge */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-slate-400 text-[11px] font-medium">Source Connection</label>
                  {getProviderBadge(srcConn?.connector_type)}
                </div>
                <div className="flex items-center gap-2">
                  <select
                    value={source.connection_id || ''}
                    onChange={(e) => updateSource({ connection_id: e.target.value })}
                    className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-slate-200 font-medium focus:border-brand-500 focus:outline-none"
                  >
                    <option value="">Select connection...</option>
                    {connections.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name} ({c.connector_type})
                      </option>
                    ))}
                  </select>

                  <button
                    type="button"
                    onClick={handleTestSourceConnection}
                    disabled={!source.connection_id || testingSrc}
                    className="px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium transition flex items-center gap-1.5 shrink-0 disabled:opacity-50"
                  >
                    <RefreshCw className={`h-3 w-3 ${testingSrc ? 'animate-spin' : ''}`} />
                    <span>Test</span>
                  </button>
                </div>
              </div>

              {/* Test Connection Banner */}
              {srcTestResult && (
                <div
                  className={`p-2 rounded-lg border text-[11px] flex items-center justify-between ${
                    srcTestResult.success
                      ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                      : 'bg-rose-500/10 border-rose-500/20 text-rose-400'
                  }`}
                >
                  <div className="flex items-center gap-1.5">
                    {srcTestResult.success ? (
                      <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                    ) : (
                      <XCircle className="h-3.5 w-3.5 shrink-0" />
                    )}
                    <span>{srcTestResult.message}</span>
                  </div>
                  {srcTestResult.latency_ms !== undefined && (
                    <span className="font-mono text-[10px] opacity-75">{srcTestResult.latency_ms} ms</span>
                  )}
                </div>
              )}
            </div>

            {/* Cloud Object Storage Source Configuration */}
            {isSrcStorage && (
              <div className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-lg space-y-3">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>Storage Container & Objects</span>
                  <HardDrive className="h-4 w-4 text-brand-400" />
                </div>

                {/* Container / Bucket Selection with Browser Modal Trigger */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                  <div className="md:col-span-2">
                    <label className="block text-slate-400 mb-1 text-[11px]">Container / Bucket</label>
                    <div className="flex items-center gap-1.5">
                      {sourceContainers.length > 0 ? (
                        <select
                          value={source.container || source.bucket || ''}
                          onChange={(e) => updateSource({ container: e.target.value, bucket: e.target.value })}
                          className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-slate-200"
                        >
                          <option value="">Select bucket/container...</option>
                          {sourceContainers.map((c) => (
                            <option key={c} value={c}>
                              {c}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <input
                          type="text"
                          placeholder="e.g. raw-telemetry-data"
                          value={source.container || source.bucket || ''}
                          onChange={(e) => updateSource({ container: e.target.value, bucket: e.target.value })}
                          className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-slate-200 font-mono"
                        />
                      )}
                    </div>
                  </div>

                  <div className="flex items-end">
                    <button
                      type="button"
                      onClick={() => openStorageBrowser('source')}
                      disabled={!source.connection_id}
                      className="w-full py-1 px-2.5 rounded bg-brand-600/20 border border-brand-500/40 hover:bg-brand-600/30 text-brand-300 font-medium transition flex items-center justify-center gap-1.5 disabled:opacity-50"
                    >
                      <FolderSearch className="h-3.5 w-3.5" />
                      <span>Browse Storage</span>
                    </button>
                  </div>
                </div>

                {/* Ingestion Mode */}
                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Ingestion Mode</label>
                  <select
                    value={source.ingestion_mode || 'single_file'}
                    onChange={(e) => updateSource({ ingestion_mode: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-slate-200"
                  >
                    <option value="single_file">Single File (e.g. orders.parquet)</option>
                    <option value="directory">Directory (Direct children of folder)</option>
                    <option value="recursive_directory">Recursive Directory (All nested subdirectories)</option>
                    <option value="prefix">Prefix Pattern (All keys matching prefix)</option>
                    <option value="wildcard">Wildcard Pattern (e.g. transactions_*.csv)</option>
                  </select>
                </div>

                {/* Path or Wildcard Input */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-slate-400 text-[11px]">File / Directory Path</label>
                    {onOpenExpressionBuilder && (
                      <button
                        type="button"
                        onClick={() =>
                          onOpenExpressionBuilder('source_path', source.path || '', (val) =>
                            updateSource({ path: val })
                          )
                        }
                        className="text-[10px] text-brand-400 hover:underline flex items-center gap-1 font-mono"
                      >
                        <Sparkles className="h-3 w-3" />
                        <span>Dynamic content</span>
                      </button>
                    )}
                  </div>
                  <input
                    type="text"
                    placeholder="e.g. inbound/2026/05/transactions.parquet"
                    value={source.path || ''}
                    onChange={(e) => updateSource({ path: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-slate-200 font-mono"
                  />
                </div>

                {source.ingestion_mode === 'wildcard' && (
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Wildcard File Filter</label>
                    <input
                      type="text"
                      placeholder="e.g. data_*.parquet or *.json"
                      value={source.wildcard_pattern || ''}
                      onChange={(e) => updateSource({ wildcard_pattern: e.target.value })}
                      className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-slate-200 font-mono"
                    />
                  </div>
                )}
              </div>
            )}

            {/* Relational Database Source Configuration */}
            {!isSrcStorage && (
              <div className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-lg space-y-3">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>Database Extraction Settings</span>
                  <Database className="h-4 w-4 text-purple-400" />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Source Table</label>
                  <input
                    type="text"
                    placeholder="e.g. public.orders"
                    value={source.table_name || ''}
                    onChange={(e) => updateSource({ table_name: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-slate-200 font-mono"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Filter Expression (SQL WHERE clause)</label>
                  <input
                    type="text"
                    placeholder="e.g. status = 'COMPLETED' AND region = 'US'"
                    value={source.filter_expr || source.filter_expression || ''}
                    onChange={(e) => updateSource({ filter_expr: e.target.value, filter_expression: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-slate-200 font-mono"
                  />
                </div>

                {/* Incremental Watermark */}
                <div className="pt-2 border-t border-slate-800 space-y-2">
                  <div className="text-[11px] font-semibold text-slate-300">Incremental Watermark Column</div>
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      type="text"
                      placeholder="Column (updated_at)"
                      value={source.incremental?.column || ''}
                      onChange={(e) =>
                        updateSource({
                          incremental: {
                            ...(source.incremental || {}),
                            mode: 'watermark',
                            column: e.target.value
                          }
                        })
                      }
                      className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs font-mono"
                    />
                    <input
                      type="text"
                      placeholder="Start Watermark Value"
                      value={source.incremental?.watermark_value || ''}
                      onChange={(e) =>
                        updateSource({
                          incremental: {
                            ...(source.incremental || {}),
                            watermark_value: e.target.value
                          }
                        })
                      }
                      className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs font-mono"
                    />
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ================================================================= */}
        {/* TAB 3: SOURCE SETTINGS (FILE FORMATS & SERIALIZATION)             */}
        {/* ================================================================= */}
        {activeTab === 'source_settings' && (
          <div className="space-y-4">
            <div className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-lg space-y-3">
              <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                <span>File Format & Codec</span>
                <FileSpreadsheet className="h-4 w-4 text-emerald-400" />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Format Type</label>
                  <select
                    value={sourceSettings.format || 'parquet'}
                    onChange={(e) => updateSourceSettings({ format: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-slate-200 font-medium"
                  >
                    <option value="parquet">Parquet (Apache Parquet)</option>
                    <option value="csv">CSV (Delimited Text)</option>
                    <option value="json">JSON (Standard JSON Document)</option>
                    <option value="jsonl">JSON Lines (Newline-delimited JSON)</option>
                    <option value="avro">Avro (Apache Avro)</option>
                    <option value="orc">ORC (Optimized Row Columnar)</option>
                    <option value="excel">Excel (.xlsx / .xls)</option>
                    <option value="text">Plain Text (.txt)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Compression Codec</label>
                  <select
                    value={sourceSettings.compression || 'none'}
                    onChange={(e) => updateSourceSettings({ compression: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-slate-200 font-medium"
                  >
                    <option value="none">None (Uncompressed)</option>
                    <option value="snappy">Snappy (.snappy)</option>
                    <option value="gzip">Gzip (.gz)</option>
                    <option value="zstd">Zstandard (.zst)</option>
                    <option value="bzip2">Bzip2 (.bz2)</option>
                    <option value="deflate">Deflate</option>
                  </select>
                </div>
              </div>

              {/* CSV / Delimited Options */}
              {(sourceSettings.format === 'csv' || sourceSettings.format === 'text') && (
                <div className="pt-2 border-t border-slate-800 space-y-2.5">
                  <div className="text-[11px] font-semibold text-slate-300">Delimited Text Options</div>
                  <div className="grid grid-cols-3 gap-2">
                    <div>
                      <label className="block text-slate-400 mb-1 text-[10px]">Delimiter</label>
                      <select
                        value={sourceSettings.delimiter || ','}
                        onChange={(e) => updateSourceSettings({ delimiter: e.target.value })}
                        className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs font-mono"
                      >
                        <option value=",">Comma (,)</option>
                        <option value="	">Tab (\t)</option>
                        <option value=";">Semicolon (;)</option>
                        <option value="|">Pipe (|)</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-slate-400 mb-1 text-[10px]">Encoding</label>
                      <select
                        value={sourceSettings.encoding || 'utf-8'}
                        onChange={(e) => updateSourceSettings({ encoding: e.target.value })}
                        className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs font-mono"
                      >
                        <option value="utf-8">UTF-8</option>
                        <option value="utf-16">UTF-16</option>
                        <option value="latin1">ISO-8859-1 (Latin-1)</option>
                        <option value="ascii">ASCII</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-slate-400 mb-1 text-[10px]">Skip Rows</label>
                      <input
                        type="number"
                        min={0}
                        value={sourceSettings.skip_rows || 0}
                        onChange={(e) => updateSourceSettings({ skip_rows: parseInt(e.target.value) || 0 })}
                        className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs font-mono"
                      />
                    </div>
                  </div>

                  <div className="flex items-center gap-2 pt-1">
                    <input
                      type="checkbox"
                      id="has_header"
                      checked={sourceSettings.has_header ?? true}
                      onChange={(e) => updateSourceSettings({ has_header: e.target.checked })}
                      className="rounded border-slate-700 bg-slate-900 text-brand-600 focus:ring-brand-500"
                    />
                    <label htmlFor="has_header" className="text-slate-300 font-medium text-[11px] cursor-pointer">
                      First row contains column headers
                    </label>
                  </div>
                </div>
              )}

              {/* JSON Options */}
              {sourceSettings.format === 'json' && (
                <div className="pt-2 border-t border-slate-800 space-y-2">
                  <div className="text-[11px] font-semibold text-slate-300">JSON Parser Settings</div>
                  <div>
                    <label className="block text-slate-400 mb-1 text-[10px]">JSON Array Root Path (Optional)</label>
                    <input
                      type="text"
                      placeholder="e.g. $.records or $.data.items[*]"
                      value={sourceSettings.json_root_path || ''}
                      onChange={(e) => updateSourceSettings({ json_root_path: e.target.value })}
                      className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs font-mono"
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="multi_line_json"
                      checked={sourceSettings.multi_line ?? false}
                      onChange={(e) => updateSourceSettings({ multi_line: e.target.checked })}
                      className="rounded border-slate-700 bg-slate-900 text-brand-600"
                    />
                    <label htmlFor="multi_line_json" className="text-slate-300 text-[11px] cursor-pointer">
                      Multi-line JSON document parsing
                    </label>
                  </div>
                </div>
              )}

              {/* Schema Inference */}
              <div className="pt-3 border-t border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="text-[11px] font-semibold text-slate-300">Schema Discovery Mode</div>
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="infer_schema"
                      checked={sourceSettings.infer_schema ?? true}
                      onChange={(e) => updateSourceSettings({ infer_schema: e.target.checked })}
                      className="rounded border-slate-700 bg-slate-900 text-brand-600"
                    />
                    <label htmlFor="infer_schema" className="text-slate-300 text-[11px] cursor-pointer">
                      Automatic Schema Inference
                    </label>
                  </div>
                </div>
                <p className="text-[10px] text-slate-500">
                  DataForge will sample leading records using PyArrow to dynamically detect types and schema structure.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* TAB 4: DESTINATION                                                */}
        {/* ================================================================= */}
        {activeTab === 'destination' && (
          <div className="space-y-4">
            <div className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-lg space-y-3">
              <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                <span>Destination Provider & Target</span>
                <Server className="h-4 w-4 text-blue-400" />
              </div>

              {/* Destination Connection Dropdown */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-slate-400 text-[11px] font-medium">Destination Connection</label>
                  {getProviderBadge(dstConn?.connector_type)}
                </div>
                <div className="flex items-center gap-2">
                  <select
                    value={destination.connection_id || ''}
                    onChange={(e) => updateDestination({ connection_id: e.target.value })}
                    className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-slate-200 font-medium focus:border-brand-500 focus:outline-none"
                  >
                    <option value="">Select destination connection...</option>
                    {connections.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name} ({c.connector_type})
                      </option>
                    ))}
                  </select>

                  <button
                    type="button"
                    onClick={handleTestDestConnection}
                    disabled={!destination.connection_id || testingDst}
                    className="px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium transition flex items-center gap-1.5 shrink-0 disabled:opacity-50"
                  >
                    <RefreshCw className={`h-3 w-3 ${testingDst ? 'animate-spin' : ''}`} />
                    <span>Test</span>
                  </button>
                </div>
              </div>

              {/* Test Connection Banner */}
              {dstTestResult && (
                <div
                  className={`p-2 rounded-lg border text-[11px] flex items-center justify-between ${
                    dstTestResult.success
                      ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                      : 'bg-rose-500/10 border-rose-500/20 text-rose-400'
                  }`}
                >
                  <div className="flex items-center gap-1.5">
                    {dstTestResult.success ? (
                      <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                    ) : (
                      <XCircle className="h-3.5 w-3.5 shrink-0" />
                    )}
                    <span>{dstTestResult.message}</span>
                  </div>
                  {dstTestResult.latency_ms !== undefined && (
                    <span className="font-mono text-[10px] opacity-75">{dstTestResult.latency_ms} ms</span>
                  )}
                </div>
              )}
            </div>

            {/* Cloud Storage Destination */}
            {isDstStorage && (
              <div className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-lg space-y-3">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>Destination Lakehouse / Storage Path</span>
                  <HardDrive className="h-4 w-4 text-brand-400" />
                </div>

                {/* Target Bucket/Container with Browse Modal */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                  <div className="md:col-span-2">
                    <label className="block text-slate-400 mb-1 text-[11px]">Target Bucket / Container</label>
                    {destContainers.length > 0 ? (
                      <select
                        value={destination.container || destination.bucket || ''}
                        onChange={(e) => updateDestination({ container: e.target.value, bucket: e.target.value })}
                        className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-slate-200"
                      >
                        <option value="">Select bucket/container...</option>
                        {destContainers.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        type="text"
                        placeholder="e.g. processed-data-lake"
                        value={destination.container || destination.bucket || ''}
                        onChange={(e) => updateDestination({ container: e.target.value, bucket: e.target.value })}
                        className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-slate-200 font-mono"
                      />
                    )}
                  </div>

                  <div className="flex items-end">
                    <button
                      type="button"
                      onClick={() => openStorageBrowser('destination')}
                      disabled={!destination.connection_id}
                      className="w-full py-1 px-2.5 rounded bg-brand-600/20 border border-brand-500/40 hover:bg-brand-600/30 text-brand-300 font-medium transition flex items-center justify-center gap-1.5 disabled:opacity-50"
                    >
                      <FolderSearch className="h-3.5 w-3.5" />
                      <span>Browse Lake</span>
                    </button>
                  </div>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Target Directory / Prefix</label>
                  <input
                    type="text"
                    placeholder="e.g. silver/orders/v1/"
                    value={destination.path || ''}
                    onChange={(e) => updateDestination({ path: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-slate-200 font-mono"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Output File Name Pattern</label>
                  <input
                    type="text"
                    placeholder="e.g. orders_{YYYYMMDD}.parquet (leave empty to preserve filename)"
                    value={destination.file_name_pattern || ''}
                    onChange={(e) => updateDestination({ file_name_pattern: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-slate-200 font-mono"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Target File Format</label>
                    <select
                      value={destination.format || 'parquet'}
                      onChange={(e) => updateDestination({ format: e.target.value })}
                      className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-slate-200"
                    >
                      <option value="parquet">Parquet (Snappy Compressed)</option>
                      <option value="csv">CSV (Delimited)</option>
                      <option value="jsonl">JSON Lines</option>
                      <option value="avro">Apache Avro</option>
                      <option value="orc">Apache ORC</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Write Mode</label>
                    <select
                      value={destination.write_mode || 'overwrite'}
                      onChange={(e) => updateDestination({ write_mode: e.target.value })}
                      className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-slate-200"
                    >
                      <option value="overwrite">Overwrite Target</option>
                      <option value="append">Append / Partition</option>
                      <option value="error_if_exists">Fail If Exists</option>
                    </select>
                  </div>
                </div>
              </div>
            )}

            {/* Relational Database Destination */}
            {!isDstStorage && (
              <div className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-lg space-y-3">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>Database Ingestion Settings</span>
                  <Database className="h-4 w-4 text-blue-400" />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Target Table</label>
                  <input
                    type="text"
                    placeholder="e.g. public.target_orders"
                    value={destination.table_name || ''}
                    onChange={(e) => updateDestination({ table_name: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-slate-200 font-mono"
                  />
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Write Mode</label>
                    <select
                      value={destination.write_mode || 'append'}
                      onChange={(e) => updateDestination({ write_mode: e.target.value })}
                      className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200"
                    >
                      <option value="append">Append (INSERT)</option>
                      <option value="overwrite">Overwrite (TRUNCATE & INSERT)</option>
                      <option value="upsert">Upsert / Merge (Requires Keys)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Primary Key Columns</label>
                    <input
                      type="text"
                      placeholder="e.g. order_id, line_no"
                      value={(destination.key_columns || []).join(', ')}
                      onChange={(e) =>
                        updateDestination({
                          key_columns: e.target.value
                            .split(',')
                            .map((s) => s.trim())
                            .filter(Boolean)
                        })
                      }
                      className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 font-mono"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Pre-Copy Script (Optional SQL)</label>
                  <input
                    type="text"
                    placeholder="e.g. TRUNCATE TABLE staging_orders"
                    value={destination.pre_copy_script || ''}
                    onChange={(e) => updateDestination({ pre_copy_script: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* ================================================================= */}
        {/* TAB 5: MAPPING (COLUMN PROJECTIONS & EXPRESSIONS)                 */}
        {/* ================================================================= */}
        {activeTab === 'mapping' && (
          <div className="space-y-4">
            <div className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-lg space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                    Column Projections & Conversions
                  </div>
                  <p className="text-[10px] text-slate-500">
                    Map incoming source columns to target schema with type casts and expressions.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handleAutoMapColumns}
                    className="px-2.5 py-1 rounded-lg bg-brand-600/20 border border-brand-500/30 hover:bg-brand-600/30 text-brand-300 font-semibold transition flex items-center gap-1.5"
                  >
                    <Sparkles className="h-3 w-3" />
                    <span>Auto-Map</span>
                  </button>
                  <button
                    type="button"
                    onClick={handleAddMapping}
                    className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold transition flex items-center gap-1"
                  >
                    <Plus className="h-3 w-3" />
                    <span>Add Column</span>
                  </button>
                </div>
              </div>

              {/* Mapping Table */}
              {mappings.length === 0 ? (
                <div className="py-10 text-center text-slate-500 border border-dashed border-slate-800 rounded-lg space-y-2">
                  <Layers className="h-6 w-6 mx-auto text-slate-600" />
                  <p className="text-slate-400 font-medium">1:1 Direct Schema Mapping Active</p>
                  <p className="text-[10px]">
                    All source columns pass directly through to destination with original names.
                    Click <span className="text-brand-400 font-semibold">Auto-Map</span> to customize columns.
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="grid grid-cols-12 gap-1.5 text-[10px] uppercase font-bold text-slate-500 px-1">
                    <span className="col-span-3">Source Column</span>
                    <span className="col-span-2">Type</span>
                    <span className="col-span-1 text-center"></span>
                    <span className="col-span-3">Destination</span>
                    <span className="col-span-2">Target Type</span>
                    <span className="col-span-1 text-center">Excl</span>
                  </div>

                  {mappings.map((m, idx) => (
                    <div
                      key={idx}
                      className={`grid grid-cols-12 gap-1.5 items-center p-2 rounded-lg border transition ${
                        m.exclude
                          ? 'bg-slate-950/40 border-slate-800/60 opacity-50'
                          : 'bg-slate-900/60 border-slate-800'
                      }`}
                    >
                      {/* Source column */}
                      <input
                        type="text"
                        placeholder="source_col"
                        value={m.source_column}
                        onChange={(e) => handleUpdateMappingRow(idx, { source_column: e.target.value })}
                        className="col-span-3 bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 font-mono text-[11px]"
                      />

                      {/* Source type */}
                      <select
                        value={m.source_type}
                        onChange={(e) => handleUpdateMappingRow(idx, { source_type: e.target.value })}
                        className="col-span-2 bg-slate-950 border border-slate-700 rounded px-1.5 py-1 text-slate-300 text-[10px]"
                      >
                        <option value="string">string</option>
                        <option value="integer">integer</option>
                        <option value="float">float</option>
                        <option value="boolean">boolean</option>
                        <option value="timestamp">timestamp</option>
                        <option value="date">date</option>
                        <option value="decimal">decimal</option>
                        <option value="binary">binary</option>
                      </select>

                      {/* Arrow */}
                      <div className="col-span-1 flex items-center justify-center text-slate-600">
                        <ArrowRight className="h-3.5 w-3.5" />
                      </div>

                      {/* Destination column */}
                      <input
                        type="text"
                        placeholder="dest_col"
                        value={m.destination_column}
                        onChange={(e) => handleUpdateMappingRow(idx, { destination_column: e.target.value })}
                        className="col-span-3 bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 font-mono text-[11px]"
                      />

                      {/* Destination type */}
                      <select
                        value={m.destination_type}
                        onChange={(e) => handleUpdateMappingRow(idx, { destination_type: e.target.value })}
                        className="col-span-2 bg-slate-950 border border-slate-700 rounded px-1.5 py-1 text-slate-300 text-[10px]"
                      >
                        <option value="string">string</option>
                        <option value="integer">integer</option>
                        <option value="float">float</option>
                        <option value="boolean">boolean</option>
                        <option value="timestamp">timestamp</option>
                        <option value="date">date</option>
                        <option value="decimal">decimal</option>
                        <option value="binary">binary</option>
                      </select>

                      {/* Exclude / Delete */}
                      <div className="col-span-1 flex items-center justify-center gap-1">
                        <input
                          type="checkbox"
                          title="Exclude column"
                          checked={m.exclude ?? false}
                          onChange={(e) => handleUpdateMappingRow(idx, { exclude: e.target.checked })}
                          className="rounded border-slate-700 bg-slate-900 text-rose-500"
                        />
                        <button
                          type="button"
                          onClick={() => handleRemoveMappingRow(idx)}
                          className="text-slate-500 hover:text-rose-400 transition"
                          title="Delete mapping"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* TAB 6: PERFORMANCE                                                */}
        {/* ================================================================= */}
        {activeTab === 'performance' && (
          <div className="space-y-4">
            <div className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-lg space-y-3">
              <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                <span>Concurrency & Parallel Copies</span>
                <Zap className="h-4 w-4 text-amber-400" />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-slate-400 text-[11px]">Parallel Workers</label>
                    <span className="font-mono text-brand-400 font-bold">{performance.parallel_copies || 4} threads</span>
                  </div>
                  <input
                    type="range"
                    min={1}
                    max={32}
                    value={performance.parallel_copies || 4}
                    onChange={(e) => updatePerformance({ parallel_copies: parseInt(e.target.value) || 4 })}
                    className="w-full accent-brand-500"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-slate-400 text-[11px]">Concurrent Files</label>
                    <span className="font-mono text-brand-400 font-bold">{performance.concurrent_files || 4} files</span>
                  </div>
                  <input
                    type="range"
                    min={1}
                    max={16}
                    value={performance.concurrent_files || 4}
                    onChange={(e) => updatePerformance({ concurrent_files: parseInt(e.target.value) || 4 })}
                    className="w-full accent-brand-500"
                  />
                </div>
              </div>
            </div>

            <div className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-lg space-y-3">
              <div className="text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                Buffering & Chunking Sizes
              </div>

              <div className="grid grid-cols-3 gap-2.5">
                <div>
                  <label className="block text-slate-400 mb-1 text-[10px]">Batch Size (Rows)</label>
                  <input
                    type="number"
                    min={100}
                    max={500000}
                    step={1000}
                    value={performance.batch_size || 10000}
                    onChange={(e) => updatePerformance({ batch_size: parseInt(e.target.value) || 10000 })}
                    className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 font-mono text-xs"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[10px]">Stream Chunk (MB)</label>
                  <input
                    type="number"
                    min={1}
                    max={64}
                    value={performance.chunk_size_mb || 8}
                    onChange={(e) => updatePerformance({ chunk_size_mb: parseInt(e.target.value) || 8 })}
                    className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 font-mono text-xs"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[10px]">Buffer Size (MB)</label>
                  <input
                    type="number"
                    min={16}
                    max={1024}
                    value={performance.buffer_size_mb || 64}
                    onChange={(e) => updatePerformance({ buffer_size_mb: parseInt(e.target.value) || 64 })}
                    className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 font-mono text-xs"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2.5 pt-2 border-t border-slate-800">
                <div>
                  <label className="block text-slate-400 mb-1 text-[10px]">Multipart Threshold (MB)</label>
                  <input
                    type="number"
                    min={5}
                    max={500}
                    value={performance.multipart_threshold_mb || 16}
                    onChange={(e) => updatePerformance({ multipart_threshold_mb: parseInt(e.target.value) || 16 })}
                    className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 font-mono text-xs"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[10px]">Multipart Part Size (MB)</label>
                  <input
                    type="number"
                    min={5}
                    max={100}
                    value={performance.multipart_part_size_mb || 8}
                    onChange={(e) => updatePerformance({ multipart_part_size_mb: parseInt(e.target.value) || 8 })}
                    className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 font-mono text-xs"
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* TAB 7: ADVANCED                                                   */}
        {/* ================================================================= */}
        {activeTab === 'advanced' && (
          <div className="space-y-4">
            <div className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-lg space-y-3">
              <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                <span>Validation & Checksums</span>
                <ShieldCheck className="h-4 w-4 text-emerald-400" />
              </div>

              <div>
                <label className="block text-slate-400 mb-1 text-[11px]">Integrity Checksum Algorithm</label>
                <select
                  value={advanced.checksum_algorithm || 'md5'}
                  onChange={(e) => updateAdvanced({ checksum_algorithm: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-slate-200 font-medium"
                >
                  <option value="none">None (Fastest - No validation)</option>
                  <option value="md5">MD5 / Content-MD5 (AWS S3 & Azure Blob standard)</option>
                  <option value="crc32c">CRC32C (Google Cloud Storage hardware-accelerated)</option>
                  <option value="sha256">SHA-256 (High security cryptographic verification)</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-400 mb-1 text-[11px]">Server-Side Encryption</label>
                <select
                  value={advanced.encryption_mode || 'default'}
                  onChange={(e) => updateAdvanced({ encryption_mode: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-slate-200 font-medium"
                >
                  <option value="default">Provider Default (AES-256 managed keys)</option>
                  <option value="aws_sse_s3">AWS SSE-S3 (AES256)</option>
                  <option value="aws_sse_kms">AWS SSE-KMS (Customer Managed KMS Key)</option>
                  <option value="azure_sse">Azure Storage Service Encryption</option>
                  <option value="gcp_cmek">GCP Customer-Managed Encryption Key (CMEK)</option>
                </select>
              </div>

              {advanced.encryption_mode === 'aws_sse_kms' && (
                <div>
                  <label className="block text-slate-400 mb-1 text-[10px]">KMS Key ARN or Alias</label>
                  <input
                    type="text"
                    placeholder="arn:aws:kms:us-east-1:123456789012:key/..."
                    value={advanced.kms_key_id || ''}
                    onChange={(e) => updateAdvanced({ kms_key_id: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 font-mono text-xs"
                  />
                </div>
              )}
            </div>

            {/* Error Handling & Preservation Toggles */}
            <div className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
              <div className="text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                Fault Tolerance & Hierarchy Flags
              </div>

              <div className="space-y-2 pt-1">
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="preserve_structure"
                    checked={advanced.preserve_directory_structure ?? true}
                    onChange={(e) => updateAdvanced({ preserve_directory_structure: e.target.checked })}
                    className="rounded border-slate-700 bg-slate-900 text-brand-600"
                  />
                  <label htmlFor="preserve_structure" className="text-slate-300 text-[11px] cursor-pointer">
                    Preserve source directory structure in destination
                  </label>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="preserve_names"
                    checked={advanced.preserve_file_names ?? true}
                    onChange={(e) => updateAdvanced({ preserve_file_names: e.target.checked })}
                    className="rounded border-slate-700 bg-slate-900 text-brand-600"
                  />
                  <label htmlFor="preserve_names" className="text-slate-300 text-[11px] cursor-pointer">
                    Preserve source file names
                  </label>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="create_dirs"
                    checked={advanced.create_directories ?? true}
                    onChange={(e) => updateAdvanced({ create_directories: e.target.checked })}
                    className="rounded border-slate-700 bg-slate-900 text-brand-600"
                  />
                  <label htmlFor="create_dirs" className="text-slate-300 text-[11px] cursor-pointer">
                    Create destination parent folders automatically if missing
                  </label>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="skip_invalid"
                    checked={advanced.skip_invalid_records ?? false}
                    onChange={(e) => updateAdvanced({ skip_invalid_records: e.target.checked })}
                    className="rounded border-slate-700 bg-slate-900 text-brand-600"
                  />
                  <label htmlFor="skip_invalid" className="text-slate-300 text-[11px] cursor-pointer">
                    Skip malformed/invalid records (continue loading clean rows)
                  </label>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="fail_schema"
                    checked={advanced.fail_on_schema_mismatch ?? true}
                    onChange={(e) => updateAdvanced({ fail_on_schema_mismatch: e.target.checked })}
                    className="rounded border-slate-700 bg-slate-900 text-brand-600"
                  />
                  <label htmlFor="fail_schema" className="text-slate-300 text-[11px] cursor-pointer">
                    Fail transfer immediately on schema mismatch
                  </label>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Storage Hierarchy Browser Modal */}
      {browserModalOpen && (
        <StorageHierarchyBrowserModal
          isOpen={browserModalOpen}
          onClose={() => setBrowserModalOpen(false)}
          connectionId={
            browserTarget === 'source' ? source.connection_id : destination.connection_id
          }
          connectionName={
            browserTarget === 'source' ? srcConn?.name : dstConn?.name
          }
          initialContainer={
            browserTarget === 'source'
              ? source.container || source.bucket
              : destination.container || destination.bucket
          }
          onSelect={handleBrowserSelect}
        />
      )}
    </div>
  );
};
