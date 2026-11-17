import React, { useState } from 'react';
import {
  ShieldCheck,
  ShieldAlert,
  Database,
  FileCode,
  Settings2,
  Sliders,
  Layers,
  Plus,
  Trash2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Sparkles,
  ArrowRight,
  Gauge,
  Play,
  RotateCw,
  FolderSearch,
  Check
} from 'lucide-react';

interface ConnectionOption {
  id: string;
  name: string;
  connector_type: string;
}

export type DQTabKey =
  | 'source'
  | 'rules'
  | 'cleansing'
  | 'sinks'
  | 'thresholds'
  | 'telemetry'
  | 'general';

interface DataQualityConfigTabsProps {
  activityId: string;
  activityLabel: string;
  activityType: 'DQAssessActivity' | 'DQEnforceActivity' | 'DataQualityCheck';
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
  }) => void;
  onUpdateConfig: (partialConfig: any) => void;
}

export const DataQualityConfigTabs: React.FC<DataQualityConfigTabsProps> = ({
  activityLabel,
  activityType,
  activityDescription = '',
  activityState,
  retryPolicy,
  config,
  connections,
  onUpdateGeneral,
  onUpdateConfig
}) => {
  const isEnforce = activityType === 'DQEnforceActivity';
  const [activeTab, setActiveTab] = useState<DQTabKey>('source');

  // Normalize ADF typeProperties
  const typeProps = config.typeProperties || config;

  const updateTypeProperty = (updates: Record<string, any>) => {
    if (config.typeProperties) {
      onUpdateConfig({
        typeProperties: {
          ...config.typeProperties,
          ...updates
        },
        ...updates
      });
    } else {
      onUpdateConfig(updates);
    }
  };

  const rules: any[] = typeProps.ruleCatalogue?.rules || typeProps.rules || [];
  const cleansingSteps: any[] = typeProps.cleansingMap?.steps || typeProps.cleansing_steps || [];
  const dqiThreshold = Number(typeProps.dqiGateThreshold ?? 0.95);
  const writeStrategy = typeProps.writeStrategy || 'merge';
  const isDualSink = Boolean(typeProps.quarantineDataset || config.quarantine_path);

  // Quick Rule Adder State
  const [newRuleId, setNewRuleId] = useState('');
  const [newRuleType, setNewRuleType] = useState('ATR1');
  const [newTargetCol, setNewTargetCol] = useState('');
  const [newRuleDesc, setNewRuleDesc] = useState('');

  // Quick Step Adder State
  const [newStepCol, setNewStepCol] = useState('');
  const [newStepStrat, setNewStepStrat] = useState('trim');
  const [newStepRuleId, setNewStepRuleId] = useState('');
  const [newStepFire, setNewStepFire] = useState('failed');

  const handleAddRule = () => {
    if (!newRuleId || !newTargetCol) return;
    const newRule = {
      rule_id: newRuleId.trim(),
      rule_type: newRuleType,
      target_column: newTargetCol.trim(),
      technical_description: newRuleDesc || `${newRuleType} check on ${newTargetCol}`,
      severity: 'Error'
    };
    const updated = [...rules, newRule];
    updateTypeProperty({
      rules: updated,
      ruleCatalogue: {
        ...(typeProps.ruleCatalogue || {}),
        referenceName: typeProps.ruleCatalogue?.referenceName || 'DQ_RULE_CATALOGUE',
        rules: updated
      }
    });
    setNewRuleId('');
    setNewTargetCol('');
    setNewRuleDesc('');
  };

  const handleDeleteRule = (idx: number) => {
    const updated = rules.filter((_, i) => i !== idx);
    updateTypeProperty({
      rules: updated,
      ruleCatalogue: {
        ...(typeProps.ruleCatalogue || {}),
        rules: updated
      }
    });
  };

  const handleAddCleansingStep = () => {
    if (!newStepCol) return;
    const newStep = {
      target_column: newStepCol.trim(),
      strategy: newStepStrat,
      rule_id: newStepRuleId.trim() || undefined,
      fire: newStepFire,
      params: {}
    };
    const updated = [...cleansingSteps, newStep];
    updateTypeProperty({
      cleansing_steps: updated,
      cleansingMap: {
        ...(typeProps.cleansingMap || {}),
        referenceName: typeProps.cleansingMap?.referenceName || 'Cleansing_Rules_Config',
        steps: updated
      }
    });
    setNewStepCol('');
    setNewStepRuleId('');
  };

  const handleDeleteCleansingStep = (idx: number) => {
    const updated = cleansingSteps.filter((_, i) => i !== idx);
    updateTypeProperty({
      cleansing_steps: updated,
      cleansingMap: {
        ...(typeProps.cleansingMap || {}),
        steps: updated
      }
    });
  };

  return (
    <div className="h-full flex flex-col bg-slate-950 text-slate-200">
      {/* Activity Subheader Banner */}
      <div className="p-3.5 bg-slate-900/90 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className={`p-2 rounded-lg border ${
            isEnforce 
              ? 'bg-indigo-500/15 border-indigo-500/30 text-indigo-400' 
              : 'bg-purple-500/15 border-purple-500/30 text-purple-400'
          }`}>
            {isEnforce ? <ShieldAlert className="h-4 w-4" /> : <ShieldCheck className="h-4 w-4" />}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-xs text-white tracking-wide">{activityLabel}</span>
              <span className={`px-1.5 py-0.5 rounded text-[9px] font-mono border ${
                isEnforce 
                  ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30' 
                  : 'bg-purple-500/20 text-purple-300 border-purple-500/30'
              }`}>
                {activityType}
              </span>
            </div>
            <p className="text-[10px] text-slate-400 mt-0.5">
              {isEnforce 
                ? 'Precedence-based automated cleansing, two-phase tagging & dual-sink routing'
                : 'Read-only Rulebook audit, compliance DQI calculation & branching telemetry'}
            </p>
          </div>
        </div>

        {/* DQI Gate Pill */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-800/80 border border-slate-700/80 text-[11px] font-mono">
          <Gauge className="h-3 w-3 text-brand-400" />
          <span className="text-slate-400">Gate:</span>
          <span className="text-white font-bold">{Math.round((dqiThreshold <= 1 ? dqiThreshold * 100 : dqiThreshold))}%</span>
        </div>
      </div>

      {/* Navigation Tabs Bar */}
      <div className="flex items-center gap-1 px-3 py-2 bg-slate-900/50 border-b border-slate-800 overflow-x-auto text-[11px]">
        <button
          type="button"
          onClick={() => setActiveTab('source')}
          className={`px-3 py-1.5 rounded-md font-medium transition flex items-center gap-1.5 shrink-0 ${
            activeTab === 'source'
              ? 'bg-brand-600/20 text-brand-300 border border-brand-500/30'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Database className="h-3 w-3" />
          <span>Source Dataset</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('rules')}
          className={`px-3 py-1.5 rounded-md font-medium transition flex items-center gap-1.5 shrink-0 ${
            activeTab === 'rules'
              ? 'bg-brand-600/20 text-brand-300 border border-brand-500/30'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <ShieldCheck className="h-3 w-3" />
          <span>Rule Catalogue ({rules.length})</span>
        </button>

        {isEnforce && (
          <button
            type="button"
            onClick={() => setActiveTab('cleansing')}
            className={`px-3 py-1.5 rounded-md font-medium transition flex items-center gap-1.5 shrink-0 ${
              activeTab === 'cleansing'
                ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Sparkles className="h-3 w-3" />
            <span>Cleansing Engine ({cleansingSteps.length})</span>
          </button>
        )}

        {isEnforce && (
          <button
            type="button"
            onClick={() => setActiveTab('sinks')}
            className={`px-3 py-1.5 rounded-md font-medium transition flex items-center gap-1.5 shrink-0 ${
              activeTab === 'sinks'
                ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Layers className="h-3 w-3" />
            <span>Sinks & Routing</span>
          </button>
        )}

        <button
          type="button"
          onClick={() => setActiveTab('thresholds')}
          className={`px-3 py-1.5 rounded-md font-medium transition flex items-center gap-1.5 shrink-0 ${
            activeTab === 'thresholds'
              ? 'bg-brand-600/20 text-brand-300 border border-brand-500/30'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Sliders className="h-3 w-3" />
          <span>Gates & Thresholds</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('telemetry')}
          className={`px-3 py-1.5 rounded-md font-medium transition flex items-center gap-1.5 shrink-0 ${
            activeTab === 'telemetry'
              ? 'bg-brand-600/20 text-brand-300 border border-brand-500/30'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Gauge className="h-3 w-3" />
          <span>Outputs & Telemetry</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('general')}
          className={`px-3 py-1.5 rounded-md font-medium transition flex items-center gap-1.5 shrink-0 ml-auto ${
            activeTab === 'general'
              ? 'bg-brand-600/20 text-brand-300 border border-brand-500/30'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Settings2 className="h-3 w-3" />
          <span>General</span>
        </button>
      </div>

      {/* Tab Body Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* TAB 1: SOURCE DATASET */}
        {activeTab === 'source' && (
          <div className="space-y-4 max-w-3xl">
            <div className="p-3 bg-slate-900/60 border border-slate-800 rounded-xl space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-white tracking-wide">ADF Source Dataset Reference</span>
                <span className="text-[10px] text-brand-400 font-mono">sourceDataset</span>
              </div>

              <div>
                <label className="block text-slate-400 mb-1 text-[11px]">Dataset Reference Name (ADF-style)</label>
                <input
                  type="text"
                  placeholder="e.g. Bronze_Customers"
                  value={typeProps.sourceDataset?.referenceName || config.source_dataset_name || ''}
                  onChange={(e) => updateTypeProperty({
                    sourceDataset: { referenceName: e.target.value }
                  })}
                  className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-1.5 text-slate-200 font-mono text-xs focus:ring-1 focus:ring-brand-500"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 border-t border-slate-800/80">
                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Direct Connection (Optional)</label>
                  <select
                    value={config.connection_id || ''}
                    onChange={(e) => onUpdateConfig({ connection_id: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-1.5 text-slate-200 text-xs"
                  >
                    <option value="">None (Use File Path or Reusable Dataset)</option>
                    {connections.map((c) => (
                      <option key={c.id} value={c.id}>{c.name} ({c.connector_type})</option>
                    ))}
                  </select>
                </div>

                {(() => {
                  const selectedConn = connections.find((c) => c.id === config.connection_id);
                  const isStorageConn =
                    selectedConn &&
                    [
                      'azure_adls',
                      'adls',
                      'adls_gen2',
                      'azure_blob',
                      'blob',
                      'aws_s3',
                      's3',
                      'gcp_storage',
                      'gcs'
                    ].includes(selectedConn.connector_type.toLowerCase());

                  if (isStorageConn) {
                    return (
                      <div className="space-y-3 col-span-full pt-1">
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                          <div>
                            <label className="block text-slate-400 mb-1 text-[11px]">
                              Container / Filesystem
                            </label>
                            <input
                              type="text"
                              placeholder="e.g. bronze or data-lake"
                              value={config.container || typeProps.container || ''}
                              onChange={(e) => {
                                onUpdateConfig({ container: e.target.value });
                                updateTypeProperty({ container: e.target.value });
                              }}
                              className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-1.5 text-slate-200 font-mono text-xs"
                            />
                          </div>

                          <div>
                            <label className="block text-slate-400 mb-1 text-[11px]">
                              ADLS File / Directory Path
                            </label>
                            <input
                              type="text"
                              placeholder="e.g. customers.parquet or raw/orders/"
                              value={config.file_path || config.path || typeProps.file_path || ''}
                              onChange={(e) => {
                                onUpdateConfig({ file_path: e.target.value });
                                updateTypeProperty({ file_path: e.target.value });
                              }}
                              className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-1.5 text-slate-200 font-mono text-xs"
                            />
                          </div>

                          <div>
                            <label className="block text-slate-400 mb-1 text-[11px]">
                              Storage Format
                            </label>
                            <select
                              value={config.format || typeProps.format || 'parquet'}
                              onChange={(e) => {
                                onUpdateConfig({ format: e.target.value });
                                updateTypeProperty({ format: e.target.value });
                              }}
                              className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-1.5 text-slate-200 text-xs"
                            >
                              <option value="parquet">Parquet (Columnar)</option>
                              <option value="delta">Delta Lake</option>
                              <option value="csv">CSV (Delimited)</option>
                              <option value="json">JSON</option>
                              <option value="avro">Avro</option>
                            </select>
                          </div>
                        </div>
                        <p className="text-[10px] text-slate-500">
                          Dataforge streams ADLS Gen2 partitions directly into vectorized Polars buffers using your encrypted Azure Service Principal, Managed Identity, or Account Key.
                        </p>
                      </div>
                    );
                  }

                  if (config.connection_id) {
                    return (
                      <div>
                        <label className="block text-slate-400 mb-1 text-[11px]">Table Name</label>
                        <input
                          type="text"
                          placeholder="e.g. bronze_customers"
                          value={config.table_name || ''}
                          onChange={(e) => onUpdateConfig({ table_name: e.target.value })}
                          className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-1.5 text-slate-200 font-mono text-xs"
                        />
                      </div>
                    );
                  }

                  return (
                    <div>
                      <label className="block text-slate-400 mb-1 text-[11px]">
                        Dataset Path / Direct Cloud URI
                      </label>
                      <input
                        type="text"
                        placeholder="abfss://container@account.dfs.core.windows.net/... or /path/file.parquet"
                        value={config.file_path || ''}
                        onChange={(e) => onUpdateConfig({ file_path: e.target.value })}
                        className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-1.5 text-slate-200 font-mono text-xs"
                      />
                    </div>
                  );
                })()}
              </div>

              {/* Primary Key Columns */}
              <div className="pt-2 border-t border-slate-800/80">
                <label className="block text-slate-400 mb-1 text-[11px]">
                  Primary Key Columns (Used for Hard Reject Flag 3 & Merge Deduplication)
                </label>
                <input
                  type="text"
                  placeholder="e.g. customer_id or company_id, user_id"
                  value={
                    Array.isArray(typeProps.key_columns)
                      ? typeProps.key_columns.join(', ')
                      : (typeProps.key_columns || config.pk_columns || '')
                  }
                  onChange={(e) => {
                    const raw = e.target.value;
                    const arr = raw.split(',').map((x: string) => x.trim()).filter(Boolean);
                    updateTypeProperty({ key_columns: arr });
                  }}
                  className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-1.5 text-slate-200 font-mono text-xs"
                />
                <span className="text-[10px] text-slate-500 mt-1 block">
                  Single-column PK NULL is flagged as <strong>DQ_FLAG = 3 (Hard Reject)</strong>. Composite keys with partial NULL are flagged as <strong>DQ_FLAG = 2</strong>.
                </span>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: RULE CATALOGUE */}
        {activeTab === 'rules' && (
          <div className="space-y-4 max-w-4xl">
            <div className="p-3 bg-slate-900/60 border border-slate-800 rounded-xl space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-xs font-semibold text-white tracking-wide">Metadata Rule Catalogue</span>
                  <p className="text-[10px] text-slate-400">Metadata-driven schema (DQ_RULE_CATALOGUE / DIM_DQ_RULE)</p>
                </div>
                <span className="text-[10px] text-purple-400 font-mono">
                  {typeProps.ruleCatalogue?.referenceName || 'DQ_RULE_CATALOGUE'}
                </span>
              </div>

              {/* Rulebook Source Selector */}
              <div className="grid grid-cols-3 gap-2 bg-slate-950 p-1.5 rounded-lg border border-slate-800 text-[11px]">
                <button
                  type="button"
                  onClick={() => updateTypeProperty({ rulebook_source: 'catalog' })}
                  className={`py-1 rounded font-medium text-center transition ${
                    (!typeProps.rulebook_source || typeProps.rulebook_source === 'catalog')
                      ? 'bg-purple-600/30 text-purple-300 border border-purple-500/40'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Metadata Catalogue
                </button>
                <button
                  type="button"
                  onClick={() => updateTypeProperty({ rulebook_source: 'cloud_storage' })}
                  className={`py-1 rounded font-medium text-center transition ${
                    typeProps.rulebook_source === 'cloud_storage'
                      ? 'bg-purple-600/30 text-purple-300 border border-purple-500/40'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Cloud (S3 / ADLS / GCS)
                </button>
                <button
                  type="button"
                  onClick={() => updateTypeProperty({ rulebook_source: 'snowflake' })}
                  className={`py-1 rounded font-medium text-center transition ${
                    typeProps.rulebook_source === 'snowflake'
                      ? 'bg-purple-600/30 text-purple-300 border border-purple-500/40'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Snowflake / DB Table
                </button>
              </div>

              {/* Dynamic Rulebook Source Settings */}
              {typeProps.rulebook_source === 'cloud_storage' && (
                <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 space-y-2">
                  <span className="text-[10px] uppercase font-semibold text-purple-300">
                    Cloud Storage Rulebook Source (S3 / ADLS / GCS)
                  </span>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                    <div>
                      <label className="block text-slate-400 mb-0.5 text-[10px]">Cloud Connection</label>
                      <select
                        value={typeProps.rulebook_connection_id || config.rulebook_connection_id || ''}
                        onChange={(e) => updateTypeProperty({ rulebook_connection_id: e.target.value })}
                        className="w-full bg-slate-950 border border-slate-700/80 rounded px-2 py-1 text-slate-200 text-xs"
                      >
                        <option value="">Direct Cloud URI (s3://, abfss://)</option>
                        {connections.map((c) => (
                          <option key={c.id} value={c.id}>{c.name} ({c.connector_type})</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-0.5 text-[10px]">Bucket / Container</label>
                      <input
                        type="text"
                        placeholder="e.g. dataforge-governance"
                        value={typeProps.rulebook_container || config.rulebook_container || ''}
                        onChange={(e) => updateTypeProperty({ rulebook_container: e.target.value })}
                        className="w-full bg-slate-950 border border-slate-700/80 rounded px-2 py-1 text-slate-200 font-mono text-xs"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-0.5 text-[10px]">Rulebook File Key / Path</label>
                      <input
                        type="text"
                        placeholder="rules/customers.json or s3://..."
                        value={typeProps.rulebook_file_key || config.rulebook_file_key || config.rulebook_path || ''}
                        onChange={(e) => updateTypeProperty({ rulebook_file_key: e.target.value, rulebook_path: e.target.value })}
                        className="w-full bg-slate-950 border border-slate-700/80 rounded px-2 py-1 text-slate-200 font-mono text-xs"
                      />
                    </div>
                  </div>
                </div>
              )}

              {typeProps.rulebook_source === 'snowflake' && (
                <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 space-y-2">
                  <span className="text-[10px] uppercase font-semibold text-purple-300">
                    Snowflake / Database Table Rulebook Source
                  </span>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                    <div>
                      <label className="block text-slate-400 mb-0.5 text-[10px]">Database Connection</label>
                      <select
                        value={typeProps.rulebook_connection_id || config.rulebook_connection_id || ''}
                        onChange={(e) => updateTypeProperty({ rulebook_connection_id: e.target.value })}
                        className="w-full bg-slate-950 border border-slate-700/80 rounded px-2 py-1 text-slate-200 text-xs"
                      >
                        <option value="">Select Connection...</option>
                        {connections.map((c) => (
                          <option key={c.id} value={c.id}>{c.name} ({c.connector_type})</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-0.5 text-[10px]">Rule Table Name</label>
                      <input
                        type="text"
                        placeholder="DQ_RULE_CATALOGUE"
                        value={typeProps.rulebook_table_name || config.rulebook_table_name || ''}
                        onChange={(e) => updateTypeProperty({ rulebook_table_name: e.target.value })}
                        className="w-full bg-slate-950 border border-slate-700/80 rounded px-2 py-1 text-slate-200 font-mono text-xs"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-0.5 text-[10px]">Filter Query (Optional)</label>
                      <input
                        type="text"
                        placeholder="WHERE DATASET_NAME = 'CUSTOMERS'"
                        value={typeProps.rulebook_query || config.rulebook_query || ''}
                        onChange={(e) => updateTypeProperty({ rulebook_query: e.target.value })}
                        className="w-full bg-slate-950 border border-slate-700/80 rounded px-2 py-1 text-slate-200 font-mono text-xs"
                      />
                    </div>
                  </div>
                </div>
              )}

              {(!typeProps.rulebook_source || typeProps.rulebook_source === 'catalog') && (
                <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between">
                  <div>
                    <label className="block text-slate-400 text-[10px]">ADF Catalogue Reference Name</label>
                    <span className="text-xs font-mono text-slate-300">
                      {typeProps.ruleCatalogue?.referenceName || 'DQ_RULE_CATALOGUE'}
                    </span>
                  </div>
                  <div className="text-[10px] text-slate-500 font-mono">
                    System Table / In-Memory Catalogue
                  </div>
                </div>
              )}

              {/* Rules Table */}
              <div className="overflow-x-auto rounded-lg border border-slate-800/80 bg-slate-950/80">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-900 text-slate-400 uppercase text-[9px] font-semibold border-b border-slate-800">
                    <tr>
                      <th className="py-2 px-3">Rule ID</th>
                      <th className="py-2 px-3">Type</th>
                      <th className="py-2 px-3">Target Column</th>
                      <th className="py-2 px-3">Technical Description</th>
                      <th className="py-2 px-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/80 font-mono text-[11px]">
                    {rules.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="py-6 text-center text-slate-500 text-xs font-sans">
                          No rules defined in catalogue. Add a rule below!
                        </td>
                      </tr>
                    ) : (
                      rules.map((r, idx) => (
                        <tr key={idx} className="hover:bg-slate-900/40">
                          <td className="py-2 px-3 font-bold text-purple-300">{r.rule_id}</td>
                          <td className="py-2 px-3">
                            <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 text-[10px]">
                              {r.rule_type}
                            </span>
                          </td>
                          <td className="py-2 px-3 text-slate-200">{r.target_column || '*'}</td>
                          <td className="py-2 px-3 text-slate-400 truncate max-w-xs font-sans text-xs">
                            {r.technical_description || r.rule_expression_logic || '-'}
                          </td>
                          <td className="py-2 px-3 text-right">
                            <button
                              type="button"
                              onClick={() => handleDeleteRule(idx)}
                              className="p-1 rounded text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition"
                              title="Delete Rule"
                            >
                              <Trash2 className="h-3 w-3" />
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* Add Rule Form */}
              <div className="p-3 bg-slate-950/90 border border-slate-800 rounded-lg space-y-2.5">
                <span className="text-[11px] font-semibold text-slate-300 block">Add New Validation Rule</span>
                <div className="grid grid-cols-1 sm:grid-cols-4 gap-2">
                  <input
                    type="text"
                    placeholder="Rule ID (e.g. R_EMAIL_NN)"
                    value={newRuleId}
                    onChange={(e) => setNewRuleId(e.target.value)}
                    className="bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                  <select
                    value={newRuleType}
                    onChange={(e) => setNewRuleType(e.target.value)}
                    className="bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 text-[11px]"
                  >
                    <option value="ATR1">ATR1: Not Null</option>
                    <option value="ATR2">ATR2: Non-Blank</option>
                    <option value="ATR3">ATR3: Placeholders / Sentinels</option>
                    <option value="ATR4">ATR4: Pattern / Regex</option>
                    <option value="ATR5">ATR5: Domain / Controlled Set</option>
                    <option value="ATR6">ATR6: Numeric Range</option>
                    <option value="ATR7">ATR7: Temporal / Date Boundary</option>
                    <option value="ATR8">ATR8: Length Validation</option>
                    <option value="DS1">DS1: Uniqueness / PK</option>
                    <option value="CSQL">CSQL: Referential Integrity</option>
                  </select>
                  <input
                    type="text"
                    placeholder="Target Column"
                    value={newTargetCol}
                    onChange={(e) => setNewTargetCol(e.target.value)}
                    className="bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                  <input
                    type="text"
                    placeholder="Technical Description"
                    value={newRuleDesc}
                    onChange={(e) => setNewRuleDesc(e.target.value)}
                    className="bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 text-[11px]"
                  />
                </div>
                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={handleAddRule}
                    disabled={!newRuleId || !newTargetCol}
                    className="px-3 py-1 rounded bg-purple-600 hover:bg-purple-500 disabled:opacity-40 text-white text-[11px] font-medium transition flex items-center gap-1"
                  >
                    <Plus className="h-3 w-3" />
                    <span>Add Rule</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: CLEANSING ENGINE (DQEnforceActivity) */}
        {isEnforce && activeTab === 'cleansing' && (
          <div className="space-y-4 max-w-4xl">
            <div className="p-3 bg-slate-900/60 border border-slate-800 rounded-xl space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-xs font-semibold text-white tracking-wide">Precedence-Based Cleansing Engine</span>
                  <p className="text-[10px] text-slate-400">Automated remediation applied strictly in 3 precedence stages</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-slate-400">Cleansing Active</span>
                  <input
                    type="checkbox"
                    checked={typeProps.cleansingEnabled ?? true}
                    onChange={(e) => updateTypeProperty({ cleansingEnabled: e.target.checked })}
                    className="rounded bg-slate-900 border-slate-700 text-indigo-500 h-4 w-4"
                  />
                </div>
              </div>

              {/* Precedence Stages Legend */}
              <div className="grid grid-cols-3 gap-2 bg-slate-950 p-2.5 rounded-lg border border-slate-800 text-[10px]">
                <div className="p-2 rounded bg-slate-900/80 border border-slate-800">
                  <span className="font-bold text-indigo-300 block mb-0.5">Stage 0: Simple Fixes</span>
                  <p className="text-slate-400">trim, collapse_ws, strip_special, hardcode_constant, set_null, value_remap</p>
                </div>
                <div className="p-2 rounded bg-slate-900/80 border border-slate-800">
                  <span className="font-bold text-teal-300 block mb-0.5">Stage 1: Translate</span>
                  <p className="text-slate-400">Sibling column translation or dictionary lookups (Arabic ↔ English)</p>
                </div>
                <div className="p-2 rounded bg-slate-900/80 border border-slate-800">
                  <span className="font-bold text-amber-300 block mb-0.5">Stage 2: Complex Derivations</span>
                  <p className="text-slate-400">copy_from_column, lookup_source_col, derive_conditional</p>
                </div>
              </div>

              {/* Cleansing Steps Table */}
              <div className="overflow-x-auto rounded-lg border border-slate-800/80 bg-slate-950/80">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-900 text-slate-400 uppercase text-[9px] font-semibold border-b border-slate-800">
                    <tr>
                      <th className="py-2 px-3">Target Column</th>
                      <th className="py-2 px-3">Strategy</th>
                      <th className="py-2 px-3">Trigger Rule</th>
                      <th className="py-2 px-3">Fire Scope</th>
                      <th className="py-2 px-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/80 font-mono text-[11px]">
                    {cleansingSteps.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="py-6 text-center text-slate-500 text-xs font-sans">
                          No cleansing steps configured. Add a remediation step below!
                        </td>
                      </tr>
                    ) : (
                      cleansingSteps.map((s, idx) => (
                        <tr key={idx} className="hover:bg-slate-900/40">
                          <td className="py-2 px-3 font-semibold text-slate-200">{s.target_column}</td>
                          <td className="py-2 px-3">
                            <span className="px-1.5 py-0.5 rounded bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 text-[10px]">
                              {s.strategy || s.op}
                            </span>
                          </td>
                          <td className="py-2 px-3 text-purple-300">{s.rule_id || '(All)'}</td>
                          <td className="py-2 px-3">
                            <span className={`text-[10px] font-sans ${s.fire === 'always' ? 'text-amber-400' : 'text-emerald-400'}`}>
                              {s.fire === 'always' ? 'Always' : 'Failed Rows Only'}
                            </span>
                          </td>
                          <td className="py-2 px-3 text-right">
                            <button
                              type="button"
                              onClick={() => handleDeleteCleansingStep(idx)}
                              className="p-1 rounded text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition"
                              title="Delete Step"
                            >
                              <Trash2 className="h-3 w-3" />
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* Add Step Form */}
              <div className="p-3 bg-slate-950/90 border border-slate-800 rounded-lg space-y-2.5">
                <span className="text-[11px] font-semibold text-slate-300 block">Add Cleansing Remediation Step</span>
                <div className="grid grid-cols-1 sm:grid-cols-4 gap-2">
                  <input
                    type="text"
                    placeholder="Target Column"
                    value={newStepCol}
                    onChange={(e) => setNewStepCol(e.target.value)}
                    className="bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                  <select
                    value={newStepStrat}
                    onChange={(e) => setNewStepStrat(e.target.value)}
                    className="bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 text-[11px]"
                  >
                    <option value="trim">trim (Strip Whitespace)</option>
                    <option value="collapse_ws">collapse_ws (Single Space)</option>
                    <option value="strip_special">strip_special (Clean Text)</option>
                    <option value="hardcode_constant">hardcode_constant (Default Value)</option>
                    <option value="set_null">set_null (Map to NULL)</option>
                    <option value="value_remap">value_remap (Dictionary Map)</option>
                    <option value="translate">translate (Sibling Column)</option>
                    <option value="copy_from_column">copy_from_column (Stage 2)</option>
                  </select>
                  <input
                    type="text"
                    placeholder="Rule ID to fix (optional)"
                    value={newStepRuleId}
                    onChange={(e) => setNewStepRuleId(e.target.value)}
                    className="bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                  <select
                    value={newStepFire}
                    onChange={(e) => setNewStepFire(e.target.value)}
                    className="bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 text-[11px]"
                  >
                    <option value="failed">Failed Rows Only</option>
                    <option value="always">Always (Every Row)</option>
                  </select>
                </div>
                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={handleAddCleansingStep}
                    disabled={!newStepCol}
                    className="px-3 py-1 rounded bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-[11px] font-medium transition flex items-center gap-1"
                  >
                    <Plus className="h-3 w-3" />
                    <span>Add Step</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 4: SINKS & ROUTING (DQEnforceActivity) */}
        {isEnforce && activeTab === 'sinks' && (
          <div className="space-y-4 max-w-3xl">
            <div className="p-3 bg-slate-900/60 border border-slate-800 rounded-xl space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-white tracking-wide">Sink Routing & Write Strategy</span>
                <span className="text-[10px] text-indigo-400 font-mono">{writeStrategy.toUpperCase()}</span>
              </div>

              {/* Mode Selector */}
              <div className="grid grid-cols-2 gap-2 bg-slate-950 p-1.5 rounded-lg border border-slate-800 text-[11px]">
                <button
                  type="button"
                  onClick={() => updateTypeProperty({ quarantineDataset: undefined })}
                  className={`py-1.5 rounded font-medium text-center transition ${
                    !isDualSink
                      ? 'bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 shadow-xs'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Single-Sink Mode (All rows with DQ_FLAG)
                </button>
                <button
                  type="button"
                  onClick={() => updateTypeProperty({
                    quarantineDataset: { referenceName: 'Quarantine_Dataset' }
                  })}
                  className={`py-1.5 rounded font-medium text-center transition ${
                    isDualSink
                      ? 'bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 shadow-xs'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Dual-Sink Mode (Target + Quarantine)
                </button>
              </div>

              {/* Target Dataset */}
              <div>
                <label className="block text-slate-400 mb-1 text-[11px]">
                  Target Dataset (Clean Rows / DQ_FLAG = 1)
                </label>
                <input
                  type="text"
                  placeholder="e.g. Silver_Customers or /data/silver/customers.parquet"
                  value={typeProps.targetDataset?.referenceName || typeProps.targetDataset?.file_path || ''}
                  onChange={(e) => updateTypeProperty({
                    targetDataset: {
                      referenceName: e.target.value,
                      file_path: e.target.value
                    }
                  })}
                  className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-1.5 text-slate-200 font-mono text-xs"
                />
              </div>

              {/* Quarantine Dataset (in Dual Sink) */}
              {isDualSink && (
                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">
                    Quarantine Dataset (Rejected Rows / DQ_FLAG IN 2, 3)
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Silver_Customers_Quarantine or /data/quarantine/bad.parquet"
                    value={typeProps.quarantineDataset?.referenceName || typeProps.quarantineDataset?.file_path || ''}
                    onChange={(e) => updateTypeProperty({
                      quarantineDataset: {
                        referenceName: e.target.value,
                        file_path: e.target.value
                      }
                    })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-1.5 text-slate-200 font-mono text-xs text-rose-300"
                  />
                </div>
              )}

              {/* Write Strategy */}
              <div>
                <label className="block text-slate-400 mb-1 text-[11px]">Persistence Write Strategy</label>
                <select
                  value={writeStrategy}
                  onChange={(e) => updateTypeProperty({ writeStrategy: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-1.5 text-slate-200 text-xs"
                >
                  <option value="merge">merge (Transactional Upsert on Key Columns)</option>
                  <option value="full">full (Overwrite Target Dataset)</option>
                  <option value="insert">insert (Append Incoming Records)</option>
                </select>
              </div>
            </div>
          </div>
        )}

        {/* TAB 5: GATES & THRESHOLDS */}
        {activeTab === 'thresholds' && (
          <div className="space-y-4 max-w-3xl">
            <div className="p-3 bg-slate-900/60 border border-slate-800 rounded-xl space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-white tracking-wide">Data Quality Index (DQI) Gate</span>
                <span className="text-xs font-mono font-bold text-brand-400">
                  {Math.round(dqiThreshold <= 1 ? dqiThreshold * 100 : dqiThreshold)}%
                </span>
              </div>

              <div>
                <label className="block text-slate-400 mb-2 text-[11px]">
                  DQI Gate Compliance Threshold (Clean Records / Total Records)
                </label>
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={Math.round(dqiThreshold <= 1 ? dqiThreshold * 100 : dqiThreshold)}
                  onChange={(e) => updateTypeProperty({ dqiGateThreshold: Number(e.target.value) / 100 })}
                  className="w-full accent-brand-500 h-1.5 bg-slate-800 rounded-lg cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-slate-500 font-mono mt-1">
                  <span>0% (Permissive)</span>
                  <span>50%</span>
                  <span>80%</span>
                  <span>95% (Enterprise SLA)</span>
                  <span>100% (Strict)</span>
                </div>
              </div>

              <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between">
                <div>
                  <span className="text-xs font-semibold text-slate-200 block">Fail Activity on Gate Breach</span>
                  <p className="text-[10px] text-slate-400">
                    If unchecked, activity succeeds with gatePassed=false for downstream IfCondition branching
                  </p>
                </div>
                <input
                  type="checkbox"
                  checked={Boolean(config.fail_pipeline_on_error || config.fail_on_threshold)}
                  onChange={(e) => onUpdateConfig({
                    fail_pipeline_on_error: e.target.checked,
                    fail_on_threshold: e.target.checked
                  })}
                  className="rounded bg-slate-900 border-slate-700 text-brand-500 h-4 w-4"
                />
              </div>

              {/* ADF Downstream Branching Helper */}
              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1 text-[11px] font-mono">
                <span className="text-slate-400 text-[10px] uppercase font-sans font-semibold block mb-1">
                  Downstream ADF Branching Expressions
                </span>
                <p className="text-purple-300">@activity('{activityLabel}').output.gatePassed</p>
                <p className="text-brand-300">@greaterOrEquals(activity('{activityLabel}').output.overallDQI, {dqiThreshold})</p>
              </div>
            </div>
          </div>
        )}

        {/* TAB 6: TELEMETRY & OUTPUTS */}
        {activeTab === 'telemetry' && (
          <div className="space-y-4 max-w-3xl">
            <div className="p-3 bg-slate-900/60 border border-slate-800 rounded-xl space-y-3">
              <span className="text-xs font-semibold text-white tracking-wide block">
                Runtime Execution Metrics (ADF Standard Output)
              </span>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
                <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
                  <span className="text-[10px] text-slate-400 block">Overall DQI</span>
                  <span className="text-lg font-bold text-white font-mono">
                    {config.overallDQI !== undefined ? `${Math.round(config.overallDQI * 100)}%` : 'Pending'}
                  </span>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
                  <span className="text-[10px] text-slate-400 block">Clean Rows (Flag 1)</span>
                  <span className="text-lg font-bold text-emerald-400 font-mono">
                    {config.cleanRows ?? '-'}
                  </span>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
                  <span className="text-[10px] text-slate-400 block">Soft Rejects (Flag 2)</span>
                  <span className="text-lg font-bold text-amber-400 font-mono">
                    {config.softRejectRows ?? '-'}
                  </span>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
                  <span className="text-[10px] text-slate-400 block">Hard Rejects (Flag 3)</span>
                  <span className="text-lg font-bold text-rose-400 font-mono">
                    {config.hardRejectRows ?? '-'}
                  </span>
                </div>
              </div>

              {/* Provenance columns indicator */}
              <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 space-y-1 text-[10px] text-slate-400">
                <span className="font-semibold text-slate-300 block">Stamped Provenance Columns</span>
                <div className="flex flex-wrap gap-1 font-mono text-[9px]">
                  <span className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-purple-300">DQ_FLAG</span>
                  <span className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-purple-300">DQ_FAILED_RULE_IDS</span>
                  <span className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-purple-300">DQ_ORIG_FAILED_RULE_IDS</span>
                  <span className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-indigo-300">PREV_ROW_HASH</span>
                  <span className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-indigo-300">LAST_ROW_HASH</span>
                  <span className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-teal-300">CLEANSING_ID</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 7: GENERAL */}
        {activeTab === 'general' && (
          <div className="space-y-4 max-w-3xl">
            <div className="p-3 bg-slate-900/60 border border-slate-800 rounded-xl space-y-3">
              <div>
                <label className="block text-slate-400 mb-1 text-[11px]">Activity Name</label>
                <input
                  type="text"
                  value={activityLabel}
                  onChange={(e) => onUpdateGeneral({ label: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-1.5 text-slate-200 text-xs"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1 text-[11px]">Description</label>
                <textarea
                  rows={2}
                  value={activityDescription}
                  onChange={(e) => onUpdateGeneral({ description: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-1.5 text-slate-200 text-xs"
                />
              </div>

              <div className="grid grid-cols-2 gap-3 pt-2 border-t border-slate-800/80">
                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Execution State</label>
                  <select
                    value={activityState}
                    onChange={(e) => onUpdateGeneral({ state: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-1.5 text-slate-200 text-xs"
                  >
                    <option value="Active">Active</option>
                    <option value="Disabled">Disabled</option>
                  </select>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Max Retries</label>
                  <input
                    type="number"
                    min={0}
                    max={5}
                    value={retryPolicy.max_retries}
                    onChange={(e) => onUpdateGeneral({
                      retry_policy: {
                        ...retryPolicy,
                        max_retries: parseInt(e.target.value) || 0
                      }
                    })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-1.5 text-slate-200 text-xs"
                  />
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
