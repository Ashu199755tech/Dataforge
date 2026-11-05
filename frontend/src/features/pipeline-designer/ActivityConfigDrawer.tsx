import React, { useState } from 'react';
import { useAppStore } from '../../store/useAppStore';
import { Node, Edge } from '@xyflow/react';
import api from '../../api/client';
import { 
  X, 
  Database, 
  Settings2, 
  CheckCircle2, 
  ShieldCheck, 
  Search, 
  Variable, 
  Clock, 
  GitFork, 
  Globe,
  Sliders,
  GitPullRequest,
  Ban,
  Trash2,
  FileSearch,
  Repeat,
  Workflow,
  Split,
  Filter,
  AlertOctagon,
  ListPlus,
  RotateCw
} from 'lucide-react';

interface ConfigDrawerProps {
  selectedNode: Node | null;
  allNodes: Node[];
  allEdges: Edge[];
  onUpdateNode: (nodeId: string, updatedData: any) => void;
  onUpdateDependencyCondition: (edgeId: string, newCondition: string) => void;
  onDeleteNode: (nodeId: string) => void;
  onClose: () => void;
}

export const ActivityConfigDrawer: React.FC<ConfigDrawerProps> = ({
  selectedNode,
  allNodes,
  allEdges,
  onUpdateNode,
  onUpdateDependencyCondition,
  onDeleteNode,
  onClose
}) => {
  const { connections, pipelines } = useAppStore();
  const [activeTab, setActiveTab] = useState<'config' | 'general' | 'dependencies'>('config');
  const [sourceTables, setSourceTables] = useState<string[]>([]);
  const [destTables, setDestTables] = useState<string[]>([]);

  if (!selectedNode) return null;

  const { id } = selectedNode;
  const data = (selectedNode.data as any) || {};
  const config = data.config || {};
  const activityType = data.activityType || 'CopyData';
  const state = data.state || 'Active';
  const retryPolicy = data.retry_policy || { max_retries: 0, retry_interval_seconds: 2 };

  // Incoming edges (dependencies for this activity)
  const incomingEdges = allEdges.filter((e) => e.target === id);

  const updateConfig = (newConfigPartial: any) => {
    const updated = {
      ...data,
      config: {
        ...config,
        ...newConfigPartial
      }
    };
    onUpdateNode(id, updated);
  };

  const handleSourceConnChange = async (connId: string) => {
    updateConfig({
      source: {
        ...(config.source || {}),
        connection_id: connId
      }
    });
    try {
      const res = await api.get(`/connections/${connId}/tables`);
      setSourceTables(res.data.tables.map((t: any) => t.name));
    } catch (e) {
      console.error(e);
    }
  };

  const handleDestConnChange = async (connId: string) => {
    updateConfig({
      destination: {
        ...(config.destination || {}),
        connection_id: connId
      }
    });
    try {
      const res = await api.get(`/connections/${connId}/tables`);
      setDestTables(res.data.tables.map((t: any) => t.name));
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="w-[400px] bg-slate-900 border-l border-slate-800 p-5 space-y-4 overflow-y-auto shrink-0 flex flex-col justify-between select-none">
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Settings2 className="h-4 w-4 text-brand-400" />
            <h3 className="text-sm font-semibold text-white">Activity Properties</h3>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => onDeleteNode(id)}
              className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition"
              title="Delete Activity"
            >
              <Trash2 className="h-4 w-4" />
            </button>
            <button onClick={onClose} className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition">
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Navigation Tabs (ADF Style) */}
        <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs">
          <button
            onClick={() => setActiveTab('config')}
            className={`flex-1 py-1.5 px-2 rounded-md font-medium transition flex items-center justify-center gap-1.5 ${
              activeTab === 'config'
                ? 'bg-brand-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Sliders className="h-3.5 w-3.5" />
            <span>Settings</span>
          </button>

          <button
            onClick={() => setActiveTab('dependencies')}
            className={`flex-1 py-1.5 px-2 rounded-md font-medium transition flex items-center justify-center gap-1.5 ${
              activeTab === 'dependencies'
                ? 'bg-brand-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <GitPullRequest className="h-3.5 w-3.5" />
            <span>Conditions ({incomingEdges.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('general')}
            className={`flex-1 py-1.5 px-2 rounded-md font-medium transition flex items-center justify-center gap-1.5 ${
              activeTab === 'general'
                ? 'bg-brand-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <span>General</span>
          </button>
        </div>

        {/* TAB 1: ACTIVITY CONFIGURATION */}
        {activeTab === 'config' && (
          <div className="space-y-4 text-xs">
            {/* COPY DATA */}
            {activityType === 'CopyData' && (
              <div className="space-y-3">
                <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
                  <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                    <span>Source Connection</span>
                    <Database className="h-3.5 w-3.5 text-amber-400" />
                  </div>

                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Connection</label>
                    <select
                      value={config.source?.connection_id || ''}
                      onChange={(e) => handleSourceConnChange(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200"
                    >
                      <option value="">Select connection...</option>
                      {connections.map((c) => (
                        <option key={c.id} value={c.id}>{c.name} ({c.connector_type})</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Source Table</label>
                    <input
                      type="text"
                      placeholder="e.g. source_orders"
                      value={config.source?.table_name || ''}
                      onChange={(e) => updateConfig({ source: { ...(config.source || {}), table_name: e.target.value } })}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200"
                    />
                  </div>

                  <div className="pt-2 border-t border-slate-800/80 space-y-2">
                    <div className="text-[11px] font-medium text-slate-400">Incremental Watermark</div>
                    <div className="grid grid-cols-2 gap-2">
                      <input
                        type="text"
                        placeholder="Column (updated_at)"
                        value={config.source?.incremental?.column || ''}
                        onChange={(e) => updateConfig({
                          source: {
                            ...(config.source || {}),
                            incremental: { ...(config.source?.incremental || {}), mode: 'watermark', column: e.target.value }
                          }
                        })}
                        className="bg-slate-900 border border-slate-700/80 rounded px-2 py-1 text-slate-200 text-[11px]"
                      />
                      <input
                        type="text"
                        placeholder="Watermark Value"
                        value={config.source?.incremental?.watermark_value || ''}
                        onChange={(e) => updateConfig({
                          source: {
                            ...(config.source || {}),
                            incremental: { ...(config.source?.incremental || {}), watermark_value: e.target.value }
                          }
                        })}
                        className="bg-slate-900 border border-slate-700/80 rounded px-2 py-1 text-slate-200 text-[11px]"
                      />
                    </div>
                  </div>
                </div>

                <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
                  <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                    <span>Destination Target</span>
                    <Database className="h-3.5 w-3.5 text-blue-400" />
                  </div>

                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Connection</label>
                    <select
                      value={config.destination?.connection_id || ''}
                      onChange={(e) => handleDestConnChange(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200"
                    >
                      <option value="">Select connection...</option>
                      {connections.map((c) => (
                        <option key={c.id} value={c.id}>{c.name} ({c.connector_type})</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Target Table</label>
                    <input
                      type="text"
                      placeholder="e.g. target_orders"
                      value={config.destination?.table_name || ''}
                      onChange={(e) => updateConfig({ destination: { ...(config.destination || {}), table_name: e.target.value } })}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-slate-400 mb-1 text-[11px]">Write Mode</label>
                      <select
                        value={config.destination?.write_mode || 'append'}
                        onChange={(e) => updateConfig({ destination: { ...(config.destination || {}), write_mode: e.target.value } })}
                        className="w-full bg-slate-900 border border-slate-700/80 rounded px-2 py-1 text-slate-200 text-[11px]"
                      >
                        <option value="append">Append</option>
                        <option value="overwrite">Overwrite</option>
                        <option value="upsert">Upsert / Merge</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1 text-[11px]">Key Column</label>
                      <input
                        type="text"
                        placeholder="order_id"
                        value={(config.destination?.key_columns || []).join(', ')}
                        onChange={(e) => updateConfig({
                          destination: {
                            ...(config.destination || {}),
                            key_columns: e.target.value.split(',').map((s) => s.trim()).filter(Boolean)
                          }
                        })}
                        className="w-full bg-slate-900 border border-slate-700/80 rounded px-2 py-1 text-slate-200 text-[11px]"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Pre-Copy Script (Optional)</label>
                    <input
                      type="text"
                      placeholder="e.g. TRUNCATE TABLE target_orders"
                      value={config.destination?.pre_copy_script || ''}
                      onChange={(e) => updateConfig({ destination: { ...(config.destination || {}), pre_copy_script: e.target.value } })}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* LOOKUP */}
            {activityType === 'Lookup' && (
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>Lookup Query & Table</span>
                  <Search className="h-3.5 w-3.5 text-teal-400" />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Connection</label>
                  <select
                    value={config.connection_id || ''}
                    onChange={(e) => updateConfig({ connection_id: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200"
                  >
                    <option value="">Select connection...</option>
                    {connections.map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Custom Query</label>
                  <textarea
                    rows={3}
                    placeholder="SELECT MAX(updated_at) as max_date FROM source_orders"
                    value={config.query || ''}
                    onChange={(e) => updateConfig({ query: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="first_row"
                    checked={config.first_row_only !== false}
                    onChange={(e) => updateConfig({ first_row_only: e.target.checked })}
                    className="rounded bg-slate-800 text-brand-500"
                  />
                  <label htmlFor="first_row" className="text-slate-300 text-[11px]">First Row Only</label>
                </div>
              </div>
            )}

            {/* SET VARIABLE */}
            {activityType === 'SetVariable' && (
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>Set Variable</span>
                  <Variable className="h-3.5 w-3.5 text-cyan-400" />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Variable Name</label>
                  <input
                    type="text"
                    placeholder="e.g. high_watermark"
                    value={config.variable_name || ''}
                    onChange={(e) => updateConfig({ variable_name: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Expression / Value</label>
                  <input
                    type="text"
                    placeholder="@activity('Lookup').output.first_row.max_date"
                    value={config.value || ''}
                    onChange={(e) => updateConfig({ value: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono"
                  />
                </div>
              </div>
            )}

            {/* IF CONDITION */}
            {activityType === 'IfCondition' && (
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>Condition Expression</span>
                  <GitFork className="h-3.5 w-3.5 text-orange-400" />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Expression</label>
                  <input
                    type="text"
                    placeholder="@equals(@parameters('env'), 'production')"
                    value={config.expression || ''}
                    onChange={(e) => updateConfig({ expression: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono"
                  />
                </div>
              </div>
            )}

            {/* WAIT */}
            {activityType === 'Wait' && (
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>Wait Duration</span>
                  <Clock className="h-3.5 w-3.5 text-amber-400" />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Duration (seconds)</label>
                  <input
                    type="number"
                    value={config.wait_time_in_seconds || 1}
                    onChange={(e) => updateConfig({ wait_time_in_seconds: parseInt(e.target.value) || 1 })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono"
                  />
                </div>
              </div>
            )}

            {/* REST API */}
            {activityType === 'RestApi' && (
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>REST API Endpoint</span>
                  <Globe className="h-3.5 w-3.5 text-sky-400" />
                </div>

                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Method</label>
                    <select
                      value={config.method || 'GET'}
                      onChange={(e) => updateConfig({ method: e.target.value })}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2 py-1 text-slate-200 text-[11px]"
                    >
                      <option value="GET">GET</option>
                      <option value="POST">POST</option>
                      <option value="PUT">PUT</option>
                      <option value="DELETE">DELETE</option>
                    </select>
                  </div>
                  <div className="col-span-2">
                    <label className="block text-slate-400 mb-1 text-[11px]">Endpoint URL</label>
                    <input
                      type="text"
                      placeholder="https://api.example.com/webhook"
                      value={config.url || ''}
                      onChange={(e) => updateConfig({ url: e.target.value })}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2 py-1 text-slate-200 font-mono text-[11px]"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* GET METADATA */}
            {activityType === 'GetMetadata' && (
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>Metadata Inspection</span>
                  <FileSearch className="h-3.5 w-3.5 text-indigo-400" />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Connection</label>
                  <select
                    value={config.connection_id || ''}
                    onChange={(e) => updateConfig({ connection_id: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200"
                  >
                    <option value="">Select connection...</option>
                    {connections.map((c) => (
                      <option key={c.id} value={c.id}>{c.name} ({c.connector_type})</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Dataset / Table Name</label>
                  <input
                    type="text"
                    placeholder="e.g. source_orders or orders.csv"
                    value={config.table_name || ''}
                    onChange={(e) => updateConfig({ table_name: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Schema / Database (Optional)</label>
                  <input
                    type="text"
                    placeholder="public or db_name"
                    value={config.schema_name || ''}
                    onChange={(e) => updateConfig({ schema_name: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                <div className="p-2.5 bg-slate-900/60 border border-slate-800 rounded text-[10px] text-slate-400 space-y-1">
                  <span className="font-semibold text-slate-300">Retrieved Output Attributes:</span>
                  <div>• <code className="text-indigo-300">exists</code>: Boolean check if object exists</div>
                  <div>• <code className="text-indigo-300">rowCount</code>: Exact row count</div>
                  <div>• <code className="text-indigo-300">columnCount</code>: Number of columns</div>
                  <div>• <code className="text-indigo-300">structure</code>: List of columns with datatypes</div>
                  <div>• <code className="text-indigo-300">sizeInBytes</code>: Total storage size in bytes</div>
                </div>
              </div>
            )}

            {/* DELETE DATA */}
            {activityType === 'DeleteData' && (
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>Delete & Cleanup</span>
                  <Trash2 className="h-3.5 w-3.5 text-rose-400" />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Connection</label>
                  <select
                    value={config.connection_id || ''}
                    onChange={(e) => updateConfig({ connection_id: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200"
                  >
                    <option value="">Select connection...</option>
                    {connections.map((c) => (
                      <option key={c.id} value={c.id}>{c.name} ({c.connector_type})</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Dataset / Table Name</label>
                  <input
                    type="text"
                    placeholder="e.g. staging_orders"
                    value={config.table_name || ''}
                    onChange={(e) => updateConfig({ table_name: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Delete Mode</label>
                  <select
                    value={config.delete_mode || 'conditional'}
                    onChange={(e) => updateConfig({ delete_mode: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 text-[11px]"
                  >
                    <option value="conditional">Conditional Filter (DELETE WHERE)</option>
                    <option value="truncate">Fast Table Truncation (TRUNCATE TABLE)</option>
                  </select>
                </div>

                {config.delete_mode !== 'truncate' && (
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Filter Expression (WHERE Clause)</label>
                    <input
                      type="text"
                      placeholder="e.g. status = 'OBSOLETE' or created_at < '2024-01-01'"
                      value={config.filter_expr || ''}
                      onChange={(e) => updateConfig({ filter_expr: e.target.value })}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                    />
                  </div>
                )}
              </div>
            )}

            {/* FOREACH */}
            {activityType === 'ForEach' && (
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>ForEach Loop Configuration</span>
                  <Repeat className="h-3.5 w-3.5 text-emerald-400" />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Items (Array or Expression)</label>
                  <input
                    type="text"
                    placeholder="@activity('GetMetadata').output.childItems"
                    value={typeof config.items === 'string' ? config.items : JSON.stringify(config.items || [])}
                    onChange={(e) => updateConfig({ items: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                  <p className="text-[10px] text-slate-500 mt-1">Use <code className="text-emerald-400">@item()</code> in sub-activities to reference each element.</p>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Execution Mode</label>
                    <select
                      value={config.is_sequential ? 'sequential' : 'parallel'}
                      onChange={(e) => updateConfig({ is_sequential: e.target.value === 'sequential' })}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 text-[11px]"
                    >
                      <option value="parallel">Parallel (Multi-threaded)</option>
                      <option value="sequential">Sequential (One-by-one)</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Batch Count (Concurrency)</label>
                    <input
                      type="number"
                      min={1}
                      max={50}
                      value={config.batch_count || 4}
                      onChange={(e) => updateConfig({ batch_count: parseInt(e.target.value) || 4 })}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 text-[11px] font-mono"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* EXECUTE PIPELINE */}
            {activityType === 'ExecutePipeline' && (
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>Child Pipeline Invocation</span>
                  <Workflow className="h-3.5 w-3.5 text-violet-400" />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Target Child Pipeline</label>
                  <select
                    value={config.pipeline_id || ''}
                    onChange={(e) => {
                      const selectedPipe = pipelines.find((p) => p.id === e.target.value);
                      updateConfig({
                        pipeline_id: e.target.value,
                        pipeline_name: selectedPipe?.name || ''
                      });
                    }}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200"
                  >
                    <option value="">Select pipeline to execute...</option>
                    {pipelines.map((p) => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </select>
                </div>

                <div className="flex items-center gap-2 pt-1">
                  <input
                    type="checkbox"
                    id="wait_comp"
                    checked={config.wait_on_completion !== false}
                    onChange={(e) => updateConfig({ wait_on_completion: e.target.checked })}
                    className="rounded bg-slate-800 text-brand-500"
                  />
                  <label htmlFor="wait_comp" className="text-slate-300 text-[11px]">Wait on child completion</label>
                </div>
              </div>
            )}

            {/* SWITCH */}
            {activityType === 'Switch' && (
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>Switch Expression</span>
                  <Split className="h-3.5 w-3.5 text-yellow-400" />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Evaluation Expression</label>
                  <input
                    type="text"
                    placeholder="@activity('Lookup').output.status"
                    value={config.expression || ''}
                    onChange={(e) => updateConfig({ expression: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                  <p className="text-[10px] text-slate-500 mt-1">Routes execution to matching branch case or default branch.</p>
                </div>
              </div>
            )}

            {/* FILTER */}
            {activityType === 'Filter' && (
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>Array Filter</span>
                  <Filter className="h-3.5 w-3.5 text-blue-400" />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Input Items Array</label>
                  <input
                    type="text"
                    placeholder="@activity('Lookup').output.items"
                    value={typeof config.items === 'string' ? config.items : JSON.stringify(config.items || [])}
                    onChange={(e) => updateConfig({ items: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Filter Condition</label>
                  <input
                    type="text"
                    placeholder="@greater(@item().amount, 100)"
                    value={config.condition || ''}
                    onChange={(e) => updateConfig({ condition: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>
              </div>
            )}

            {/* FAIL */}
            {activityType === 'Fail' && (
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>Deliberate Failure</span>
                  <AlertOctagon className="h-3.5 w-3.5 text-red-500" />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Error Code</label>
                  <input
                    type="text"
                    placeholder="e.g. DATA_VALIDATION_ERROR"
                    value={config.error_code || 'UserError'}
                    onChange={(e) => updateConfig({ error_code: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Failure Message</label>
                  <input
                    type="text"
                    placeholder="e.g. Critical validation failed on row counts"
                    value={config.message || ''}
                    onChange={(e) => updateConfig({ message: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>
              </div>
            )}

            {/* APPEND VARIABLE */}
            {activityType === 'AppendVariable' && (
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>Append to Array Variable</span>
                  <ListPlus className="h-3.5 w-3.5 text-cyan-400" />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Variable Name</label>
                  <input
                    type="text"
                    placeholder="e.g. processed_files"
                    value={config.variable_name || ''}
                    onChange={(e) => updateConfig({ variable_name: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Value to Append</label>
                  <input
                    type="text"
                    placeholder="@item().name"
                    value={config.value || ''}
                    onChange={(e) => updateConfig({ value: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>
              </div>
            )}

            {/* UNTIL */}
            {activityType === 'Until' && (
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>Until Loop Condition</span>
                  <RotateCw className="h-3.5 w-3.5 text-pink-400" />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Break Condition Expression</label>
                  <input
                    type="text"
                    placeholder="@equals(@variables('is_done'), true)"
                    value={config.expression || ''}
                    onChange={(e) => updateConfig({ expression: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Max Iterations</label>
                  <input
                    type="number"
                    min={1}
                    max={100}
                    value={config.max_iterations || 10}
                    onChange={(e) => updateConfig({ max_iterations: parseInt(e.target.value) || 10 })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: DEPENDENCIES & OUTCOME CONDITIONS (ADF STYLE) */}
        {activeTab === 'dependencies' && (
          <div className="space-y-3 text-xs">
            <div className="text-[11px] text-slate-400">
              Configure conditions under which this activity triggers from upstream activities:
            </div>

            {incomingEdges.length === 0 ? (
              <div className="p-6 text-center text-slate-500 bg-slate-950/60 border border-slate-800 rounded-lg text-xs">
                This activity is a root entry point. Connect incoming output handles from other activities to add dependency conditions.
              </div>
            ) : (
              <div className="space-y-2">
                {incomingEdges.map((edge) => {
                  const parentNode = allNodes.find((n) => n.id === edge.source);
                  const parentName = (parentNode?.data as any)?.label || edge.source;
                  const currentCond = (edge.data as any)?.condition || 'Succeeded';

                  return (
                    <div key={edge.id} className="p-3 bg-slate-950/80 border border-slate-800 rounded-lg space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-slate-200">{parentName}</span>
                        <span className="text-[10px] font-mono text-slate-500">{edge.source}</span>
                      </div>

                      <div>
                        <label className="block text-slate-400 mb-1 text-[11px]">Trigger Condition</label>
                        <select
                          value={currentCond}
                          onChange={(e) => onUpdateDependencyCondition(edge.id, e.target.value)}
                          className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-slate-200 text-xs font-semibold"
                        >
                          <option value="Succeeded">🟢 Upon Success (Succeeded)</option>
                          <option value="Failed">🔴 Upon Failure (Failed)</option>
                          <option value="Completed">🔵 Upon Completion (Completed)</option>
                          <option value="Skipped">⚪ Upon Skip (Skipped)</option>
                        </select>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            <div className="p-3 bg-slate-950/50 border border-slate-800/80 rounded text-[11px] text-slate-400 space-y-1">
              <div className="font-semibold text-slate-300">Condition Guide:</div>
              <div>• <span className="text-emerald-400 font-semibold">Success</span>: Runs only if parent succeeds.</div>
              <div>• <span className="text-rose-400 font-semibold">Failure</span>: Runs if parent fails (error handling/cleanup).</div>
              <div>• <span className="text-blue-400 font-semibold">Completion</span>: Runs after parent terminates regardless of success.</div>
              <div>• <span className="text-slate-400 font-semibold">Skip</span>: Runs if parent was skipped due to prior conditions.</div>
            </div>
          </div>
        )}

        {/* TAB 3: GENERAL SETTINGS & STATE (ACTIVE / SKIP) */}
        {activeTab === 'general' && (
          <div className="space-y-4 text-xs">
            <div>
              <label className="block text-slate-400 mb-1 font-medium">Activity Name</label>
              <input
                type="text"
                value={data.label || ''}
                onChange={(e) => onUpdateNode(id, { ...data, label: e.target.value })}
                className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500 font-medium"
              />
            </div>

            {/* Activity State (Active vs Disabled / Skip) */}
            <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2">
              <label className="block text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                Activity Execution State
              </label>
              <select
                value={state}
                onChange={(e) => onUpdateNode(id, { ...data, state: e.target.value })}
                className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-slate-200"
              >
                <option value="Active">Active (Executes normally in pipeline)</option>
                <option value="Disabled">Disabled / Skip (Bypassed during execution)</option>
              </select>
              <p className="text-[10px] text-slate-500">
                Disabled activities will be marked as 'Skipped' at runtime, triggering downstream 'On Skip' paths.
              </p>
            </div>

            {/* Retry Policy (ADF Feature) */}
            <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2">
              <label className="block text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                Retry Policy
              </label>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Max Retries</label>
                  <input
                    type="number"
                    min={0}
                    max={10}
                    value={retryPolicy.max_retries || 0}
                    onChange={(e) => onUpdateNode(id, {
                      ...data,
                      retry_policy: { ...retryPolicy, max_retries: parseInt(e.target.value) || 0 }
                    })}
                    className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Interval (sec)</label>
                  <input
                    type="number"
                    min={1}
                    max={3600}
                    value={retryPolicy.retry_interval_seconds || 2}
                    onChange={(e) => onUpdateNode(id, {
                      ...data,
                      retry_policy: { ...retryPolicy, retry_interval_seconds: parseInt(e.target.value) || 2 }
                    })}
                    className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200"
                  />
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="pt-3 border-t border-slate-800 flex items-center gap-2">
        <button
          onClick={() => onDeleteNode(id)}
          className="flex-1 py-2 bg-rose-600/10 hover:bg-rose-600/20 text-rose-400 border border-rose-500/30 rounded text-xs font-semibold transition flex items-center justify-center gap-1.5"
        >
          <Trash2 className="h-3.5 w-3.5" />
          <span>Delete Activity</span>
        </button>
        <button
          onClick={onClose}
          className="flex-1 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-xs font-semibold transition"
        >
          Done
        </button>
      </div>
    </div>
  );
};
