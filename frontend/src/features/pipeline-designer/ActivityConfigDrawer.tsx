import React, { useState, useEffect } from 'react';
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
  RotateCw,
  Terminal,
  DatabaseZap,
  CloudLightning,
  Flame,
  Cpu,
  Send,
  CheckCheck,
  FolderCog,
  Archive,
  Sparkles,
  BarChart3,
  Scale,
  ShieldAlert,
  Plus,
  Maximize2,
  Minimize2
} from 'lucide-react';
import { ExpressionBuilderModal } from '../../components/common/ExpressionBuilderModal';
import { CopyDataConfigTabs } from './CopyDataConfigTabs';

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
  const [isExpanded, setIsExpanded] = useState(activityType === 'CopyData');
  const [availableRuntimes, setAvailableRuntimes] = useState<any[]>([]);

  useEffect(() => {
    api.get('/runtimes')
      .then(res => setAvailableRuntimes(res.data))
      .catch(err => console.error('Failed to fetch runtimes', err));
  }, []);

  // Incoming edges (dependencies for this activity)
  const incomingEdges = allEdges.filter((e) => e.target === id);

  // Phase 7: Dynamic Expression Builder state
  const [exprModalOpen, setExprModalOpen] = useState(false);
  const [exprTarget, setExprTarget] = useState<{ fieldName: string; value: string; onApply: (val: string) => void } | null>(null);

  const openExpressionBuilder = (fieldName: string, value: string, onApply: (val: string) => void) => {
    setExprTarget({ fieldName, value, onApply });
    setExprModalOpen(true);
  };

  const upstreamNodeIds = incomingEdges.map((e) => e.source);
  const upstreamActivities = allNodes
    .filter((n) => upstreamNodeIds.includes(n.id))
    .map((n) => ({
      id: n.id,
      name: (n.data as any)?.label || n.id,
      type: (n.data as any)?.activityType || 'Activity'
    }));

  const DynamicContentTrigger: React.FC<{ fieldName: string; value: string; onApply: (val: string) => void }> = ({
    fieldName,
    value,
    onApply
  }) => (
    <button
      type="button"
      onClick={() => openExpressionBuilder(fieldName, value, onApply)}
      className="text-[10px] text-indigo-400 hover:text-indigo-300 hover:underline flex items-center gap-1 font-mono transition"
      title="Add dynamic content [Alt+P]"
    >
      <Sparkles className="w-3 h-3 text-indigo-400" />
      <span>Dynamic content</span>
    </button>
  );

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
    <div
      className={`${
        isExpanded || activityType === 'CopyData' ? 'w-[640px] xl:w-[740px]' : 'w-[400px]'
      } bg-slate-900 border-l border-slate-800 p-5 space-y-4 overflow-y-auto shrink-0 flex flex-col justify-between select-none transition-all duration-150`}
    >
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Settings2 className="h-4 w-4 text-brand-400" />
            <h3 className="text-sm font-semibold text-white">
              {activityType === 'CopyData' ? 'Copy Data Activity (Multi-Cloud)' : 'Activity Properties'}
            </h3>
          </div>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setIsExpanded(!isExpanded)}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
              title={isExpanded ? 'Collapse Drawer Width' : 'Expand Drawer Width'}
            >
              {isExpanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
            </button>
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
            {/* COPY DATA (MULTI-CLOUD ENGINE) */}
            {activityType === 'CopyData' && (
              <CopyDataConfigTabs
                activityId={id}
                activityLabel={data.label || ''}
                activityDescription={data.description || ''}
                activityState={state}
                retryPolicy={retryPolicy}
                config={config}
                connections={connections}
                onUpdateGeneral={(updates) => {
                  const updated = {
                    ...data,
                    ...(updates.label !== undefined ? { label: updates.label } : {}),
                    ...(updates.description !== undefined ? { description: updates.description } : {}),
                    ...(updates.state !== undefined ? { state: updates.state } : {}),
                    ...(updates.retry_policy !== undefined ? { retry_policy: updates.retry_policy } : {})
                  };
                  if (updates.timeout_seconds !== undefined) {
                    updated.config = {
                      ...(updated.config || {}),
                      advanced: {
                        ...((updated.config || {}).advanced || {}),
                        timeout_seconds: updates.timeout_seconds
                      }
                    };
                  }
                  onUpdateNode(id, updated);
                }}
                onUpdateConfig={updateConfig}
                onOpenExpressionBuilder={openExpressionBuilder}
              />
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
                  <div className="flex items-center justify-between mb-1">
                    <label className="block text-slate-400 text-[11px]">Expression / Value</label>
                    <DynamicContentTrigger
                      fieldName="value"
                      value={config.value || ''}
                      onApply={(val) => updateConfig({ value: val })}
                    />
                  </div>
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
                  <div className="flex items-center justify-between mb-1">
                    <label className="block text-slate-400 text-[11px]">Expression</label>
                    <DynamicContentTrigger
                      fieldName="expression"
                      value={config.expression || ''}
                      onApply={(val) => updateConfig({ expression: val })}
                    />
                  </div>
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
                    <div className="flex items-center justify-between mb-1">
                      <label className="block text-slate-400 text-[11px]">Endpoint URL</label>
                      <DynamicContentTrigger
                        fieldName="url"
                        value={config.url || ''}
                        onApply={(val) => updateConfig({ url: val })}
                      />
                    </div>
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
                  <div className="flex items-center justify-between mb-1">
                    <label className="block text-slate-400 text-[11px]">Input Items Array</label>
                    <DynamicContentTrigger
                      fieldName="items"
                      value={typeof config.items === 'string' ? config.items : JSON.stringify(config.items || [])}
                      onApply={(val) => updateConfig({ items: val })}
                    />
                  </div>
                  <input
                    type="text"
                    placeholder="@activity('Lookup').output.items"
                    value={typeof config.items === 'string' ? config.items : JSON.stringify(config.items || [])}
                    onChange={(e) => updateConfig({ items: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="block text-slate-400 text-[11px]">Filter Condition</label>
                    <DynamicContentTrigger
                      fieldName="condition"
                      value={config.condition || ''}
                      onApply={(val) => updateConfig({ condition: val })}
                    />
                  </div>
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

            {/* PYTHON SCRIPT */}
            {activityType === 'PythonScript' && (
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>Python Script Execution</span>
                  <Terminal className="h-3.5 w-3.5 text-emerald-400" />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Python Code</label>
                  <textarea
                    rows={7}
                    placeholder={`# Write custom Python logic\nimport json\nresult = {"status": "success", "processed": 42}\ncontext.set_output("result", result)`}
                    value={config.script || ''}
                    onChange={(e) => updateConfig({ script: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1.5 text-slate-200 font-mono text-[11px]"
                  />
                  <p className="text-[10px] text-slate-500 mt-0.5">Use <code className="text-emerald-400">context.set_output(key, val)</code> to export outputs.</p>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Timeout (seconds)</label>
                    <input
                      type="number"
                      min={1}
                      max={3600}
                      value={config.timeout_seconds || 120}
                      onChange={(e) => updateConfig({ timeout_seconds: parseInt(e.target.value) || 120 })}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Parameters (JSON)</label>
                    <input
                      type="text"
                      placeholder='{"batch_id": 101}'
                      value={typeof config.parameters === 'string' ? config.parameters : JSON.stringify(config.parameters || {})}
                      onChange={(e) => {
                        try {
                          updateConfig({ parameters: JSON.parse(e.target.value) });
                        } catch {
                          updateConfig({ parameters: e.target.value });
                        }
                      }}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* STORED PROCEDURE */}
            {activityType === 'StoredProcedure' && (
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>Stored Procedure / Routine</span>
                  <DatabaseZap className="h-3.5 w-3.5 text-purple-400" />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Database Connection</label>
                  <select
                    value={config.connection_id || ''}
                    onChange={(e) => updateConfig({ connection_id: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 text-[11px]"
                  >
                    <option value="">Select connection...</option>
                    {connections.map((c) => (
                      <option key={c.id} value={c.id}>{c.name} ({c.connector_type})</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Procedure / Function Name</label>
                  <input
                    type="text"
                    placeholder="e.g. recalculate_customer_metrics"
                    value={config.procedure_name || ''}
                    onChange={(e) => updateConfig({ procedure_name: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Procedure Parameters (JSON map)</label>
                  <input
                    type="text"
                    placeholder='{"p_customer_id": 1001, "p_date": "2026-11-05"}'
                    value={typeof config.parameters === 'string' ? config.parameters : JSON.stringify(config.parameters || {})}
                    onChange={(e) => {
                      try {
                        updateConfig({ parameters: JSON.parse(e.target.value) });
                      } catch {
                        updateConfig({ parameters: e.target.value });
                      }
                    }}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                <div className="flex items-center gap-2 pt-1">
                  <input
                    type="checkbox"
                    id="is_func"
                    checked={config.is_function !== false}
                    onChange={(e) => updateConfig({ is_function: e.target.checked })}
                    className="rounded bg-slate-800 text-brand-500"
                  />
                  <label htmlFor="is_func" className="text-slate-300 text-[11px]">Invoke as Function (SELECT func(...) vs CALL proc(...))</label>
                </div>
              </div>
            )}

            {/* CUSTOM ACTIVITY */}
            {activityType === 'CustomActivity' && (
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>Custom Command Activity</span>
                  <Cpu className="h-3.5 w-3.5 text-amber-400" />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Executable Command / Binary</label>
                  <input
                    type="text"
                    placeholder="e.g. /usr/bin/python3, dbt, curl"
                    value={config.command || ''}
                    onChange={(e) => updateConfig({ command: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Arguments (JSON Array or String)</label>
                  <input
                    type="text"
                    placeholder='["run", "--select", "my_model"]'
                    value={typeof config.arguments === 'string' ? config.arguments : JSON.stringify(config.arguments || [])}
                    onChange={(e) => {
                      try {
                        updateConfig({ arguments: JSON.parse(e.target.value) });
                      } catch {
                        updateConfig({ arguments: e.target.value });
                      }
                    }}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Working Directory</label>
                    <input
                      type="text"
                      placeholder="/tmp or custom path"
                      value={config.working_directory || ''}
                      onChange={(e) => updateConfig({ working_directory: e.target.value })}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Timeout (seconds)</label>
                    <input
                      type="number"
                      min={1}
                      max={7200}
                      value={config.timeout_seconds || 120}
                      onChange={(e) => updateConfig({ timeout_seconds: parseInt(e.target.value) || 120 })}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* DATABRICKS NOTEBOOK */}
            {activityType === 'DatabricksNotebook' && (
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>Databricks Notebook Execution</span>
                  <CloudLightning className="h-3.5 w-3.5 text-orange-400" />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Workspace Host URL</label>
                  <input
                    type="text"
                    placeholder="https://adb-123456789.azuredatabricks.net"
                    value={config.host || ''}
                    onChange={(e) => updateConfig({ host: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Personal Access Token (PAT)</label>
                  <input
                    type="password"
                    placeholder="dapi..."
                    value={config.token || ''}
                    onChange={(e) => updateConfig({ token: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Notebook Workspace Path</label>
                  <input
                    type="text"
                    placeholder="/Users/data-eng/etl_pipeline"
                    value={config.notebook_path || ''}
                    onChange={(e) => updateConfig({ notebook_path: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Existing Cluster ID</label>
                    <input
                      type="text"
                      placeholder="1025-112233-cluster"
                      value={config.cluster_id || ''}
                      onChange={(e) => updateConfig({ cluster_id: e.target.value })}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Polling Interval (s)</label>
                    <input
                      type="number"
                      min={2}
                      max={60}
                      value={config.poll_interval_seconds || 5}
                      onChange={(e) => updateConfig({ poll_interval_seconds: parseInt(e.target.value) || 5 })}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Base Parameters (JSON map)</label>
                  <input
                    type="text"
                    placeholder='{"env": "prod", "date": "@pipeline().TriggerTime"}'
                    value={typeof config.base_parameters === 'string' ? config.base_parameters : JSON.stringify(config.base_parameters || {})}
                    onChange={(e) => {
                      try {
                        updateConfig({ base_parameters: JSON.parse(e.target.value) });
                      } catch {
                        updateConfig({ base_parameters: e.target.value });
                      }
                    }}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>
              </div>
            )}

            {/* PYSPARK JOB */}
            {activityType === 'PySparkJob' && (
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>Apache Spark / PySpark Job</span>
                  <Flame className="h-3.5 w-3.5 text-rose-400" />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">PySpark Script Path or Code</label>
                  <input
                    type="text"
                    placeholder="e.g. jobs/transform.py or s3://scripts/job.py"
                    value={config.script || ''}
                    onChange={(e) => updateConfig({ script: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Spark Master URL</label>
                  <input
                    type="text"
                    placeholder="local[*], spark://master:7077, or yarn"
                    value={config.master || 'local[*]'}
                    onChange={(e) => updateConfig({ master: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Spark Submit Arguments (JSON Array)</label>
                  <input
                    type="text"
                    placeholder='["--executor-memory", "4g", "--driver-memory", "2g"]'
                    value={typeof config.spark_args === 'string' ? config.spark_args : JSON.stringify(config.spark_args || [])}
                    onChange={(e) => {
                      try {
                        updateConfig({ spark_args: JSON.parse(e.target.value) });
                      } catch {
                        updateConfig({ spark_args: e.target.value });
                      }
                    }}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>
              </div>
            )}

            {/* WEB ACTIVITY */}
            {activityType === 'WebActivity' && (
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>Web HTTP Request</span>
                  <Globe className="h-3.5 w-3.5 text-sky-400" />
                </div>

                <div className="grid grid-cols-4 gap-2">
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
                      <option value="PATCH">PATCH</option>
                    </select>
                  </div>
                  <div className="col-span-3">
                    <label className="block text-slate-400 mb-1 text-[11px]">URL Endpoint</label>
                    <input
                      type="text"
                      placeholder="https://api.example.com/v1/orders"
                      value={config.url || ''}
                      onChange={(e) => updateConfig({ url: e.target.value })}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Headers (JSON map)</label>
                  <input
                    type="text"
                    placeholder='{"Content-Type": "application/json"}'
                    value={typeof config.headers === 'string' ? config.headers : JSON.stringify(config.headers || {})}
                    onChange={(e) => {
                      try {
                        updateConfig({ headers: JSON.parse(e.target.value) });
                      } catch {
                        updateConfig({ headers: e.target.value });
                      }
                    }}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                {['POST', 'PUT', 'PATCH'].includes(config.method || 'GET') && (
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Request Body</label>
                    <textarea
                      rows={3}
                      placeholder='{"order_id": 100, "status": "APPROVED"}'
                      value={typeof config.body === 'string' ? config.body : JSON.stringify(config.body || {}, null, 2)}
                      onChange={(e) => {
                        try {
                          updateConfig({ body: JSON.parse(e.target.value) });
                        } catch {
                          updateConfig({ body: e.target.value });
                        }
                      }}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                    />
                  </div>
                )}

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Timeout (s)</label>
                    <input
                      type="number"
                      min={1}
                      max={600}
                      value={config.timeout_seconds || 30}
                      onChange={(e) => updateConfig({ timeout_seconds: parseInt(e.target.value) || 30 })}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                    />
                  </div>
                  <div className="flex items-center gap-1.5 pt-4">
                    <input
                      type="checkbox"
                      id="dis_ssl"
                      checked={config.disable_cert_validation || false}
                      onChange={(e) => updateConfig({ disable_cert_validation: e.target.checked })}
                      className="rounded bg-slate-800 text-brand-500"
                    />
                    <label htmlFor="dis_ssl" className="text-slate-300 text-[10px]">Disable SSL verify</label>
                  </div>
                </div>
              </div>
            )}

            {/* WEBHOOK */}
            {activityType === 'Webhook' && (
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>Asynchronous Webhook</span>
                  <Send className="h-3.5 w-3.5 text-teal-400" />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">External Service URL</label>
                  <input
                    type="text"
                    placeholder="https://external-service.io/api/start-job"
                    value={config.url || ''}
                    onChange={(e) => updateConfig({ url: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                  <p className="text-[10px] text-slate-500 mt-0.5">The platform auto-injects a unique <code className="text-teal-400">callBackUri</code> into the request.</p>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Callback Param Name</label>
                    <input
                      type="text"
                      placeholder="callBackUri"
                      value={config.callback_param_name || 'callBackUri'}
                      onChange={(e) => updateConfig({ callback_param_name: e.target.value })}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Timeout (seconds)</label>
                    <input
                      type="number"
                      min={5}
                      max={86400}
                      value={config.timeout_seconds || 300}
                      onChange={(e) => updateConfig({ timeout_seconds: parseInt(e.target.value) || 300 })}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Request Body (JSON)</label>
                  <input
                    type="text"
                    placeholder='{"job_name": "daily_report", "priority": "high"}'
                    value={typeof config.body === 'string' ? config.body : JSON.stringify(config.body || {})}
                    onChange={(e) => {
                      try {
                        updateConfig({ body: JSON.parse(e.target.value) });
                      } catch {
                        updateConfig({ body: e.target.value });
                      }
                    }}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>
              </div>
            )}

            {/* VALIDATION */}
            {activityType === 'Validation' && (
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>Prerequisite Validation Gate</span>
                  <CheckCheck className="h-3.5 w-3.5 text-lime-400" />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Database Connection (Optional)</label>
                  <select
                    value={config.connection_id || ''}
                    onChange={(e) => updateConfig({ connection_id: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 text-[11px]"
                  >
                    <option value="">None (Local / Direct Path)</option>
                    {connections.map((c) => (
                      <option key={c.id} value={c.id}>{c.name} ({c.connector_type})</option>
                    ))}
                  </select>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="block text-slate-400 text-[11px]">Dataset / Table / File Name</label>
                    <DynamicContentTrigger
                      fieldName="dataset_name"
                      value={config.dataset_name || ''}
                      onApply={(val) => updateConfig({ dataset_name: val })}
                    />
                  </div>
                  <input
                    type="text"
                    placeholder="e.g. daily_transactions.parquet or dim_customers"
                    value={config.dataset_name || ''}
                    onChange={(e) => updateConfig({ dataset_name: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="block text-slate-400 text-[11px]">Direct File Path (Optional)</label>
                    <DynamicContentTrigger
                      fieldName="file_path"
                      value={config.file_path || ''}
                      onApply={(val) => updateConfig({ file_path: val })}
                    />
                  </div>
                  <input
                    type="text"
                    placeholder="/data/incoming/ready.flag"
                    value={config.file_path || ''}
                    onChange={(e) => updateConfig({ file_path: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Min Size (bytes)</label>
                    <input
                      type="number"
                      min={0}
                      value={config.minimum_size_bytes || 0}
                      onChange={(e) => updateConfig({ minimum_size_bytes: parseInt(e.target.value) || 0 })}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Min Rows</label>
                    <input
                      type="number"
                      min={0}
                      value={config.minimum_row_count || 0}
                      onChange={(e) => updateConfig({ minimum_row_count: parseInt(e.target.value) || 0 })}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Timeout (seconds)</label>
                    <input
                      type="number"
                      min={1}
                      max={3600}
                      value={config.timeout_seconds || 60}
                      onChange={(e) => updateConfig({ timeout_seconds: parseInt(e.target.value) || 60 })}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Poll Interval (s)</label>
                    <input
                      type="number"
                      min={1}
                      max={60}
                      value={config.sleep_interval_seconds || 5}
                      onChange={(e) => updateConfig({ sleep_interval_seconds: parseInt(e.target.value) || 5 })}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* FILE OPERATION */}
            {activityType === 'FileOperation' && (
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>File System Operation</span>
                  <FolderCog className="h-3.5 w-3.5 text-amber-400" />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Operation</label>
                  <select
                    value={config.operation || 'copy'}
                    onChange={(e) => updateConfig({ operation: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 text-[11px]"
                  >
                    <option value="copy">Copy File / Directory</option>
                    <option value="move">Move File / Directory</option>
                    <option value="rename">Rename File</option>
                    <option value="delete">Delete File / Directory</option>
                    <option value="file_exists">Check File Exists</option>
                  </select>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Source Path / Pattern</label>
                  <input
                    type="text"
                    placeholder="/data/inbox/*.csv or /data/raw/feed.json"
                    value={config.source_path || ''}
                    onChange={(e) => updateConfig({ source_path: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                {config.operation !== 'delete' && config.operation !== 'file_exists' && (
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Destination Path / Target</label>
                    <input
                      type="text"
                      placeholder="/data/archive/ or /data/processed/feed_2026.json"
                      value={config.destination_path || ''}
                      onChange={(e) => updateConfig({ destination_path: e.target.value })}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                    />
                  </div>
                )}

                <div className="flex items-center gap-2 pt-1">
                  <input
                    type="checkbox"
                    id="ovrw"
                    checked={config.overwrite !== false}
                    onChange={(e) => updateConfig({ overwrite: e.target.checked })}
                    className="rounded bg-slate-800 text-brand-500"
                  />
                  <label htmlFor="ovrw" className="text-slate-300 text-[11px]">Overwrite existing target files</label>
                </div>
              </div>
            )}

            {/* ARCHIVE & UNZIP */}
            {activityType === 'Archive' && (
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>Archive & Decompress</span>
                  <Archive className="h-3.5 w-3.5 text-indigo-400" />
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Action</label>
                    <select
                      value={config.action || 'compress'}
                      onChange={(e) => updateConfig({ action: e.target.value })}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 text-[11px]"
                    >
                      <option value="compress">Compress to Archive</option>
                      <option value="extract">Extract / Unzip</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Format</label>
                    <select
                      value={config.format || 'zip'}
                      onChange={(e) => updateConfig({ format: e.target.value })}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 text-[11px]"
                    >
                      <option value="zip">ZIP Archive (.zip)</option>
                      <option value="tar.gz">GZip Tarball (.tar.gz)</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Source Path</label>
                  <input
                    type="text"
                    placeholder="/data/raw_feed/ or /data/package.zip"
                    value={config.source_path || ''}
                    onChange={(e) => updateConfig({ source_path: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Destination Path</label>
                  <input
                    type="text"
                    placeholder="/data/backups/feed.zip or /data/extracted/"
                    value={config.destination_path || ''}
                    onChange={(e) => updateConfig({ destination_path: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                <div className="flex items-center gap-2 pt-1">
                  <input
                    type="checkbox"
                    id="rem_src"
                    checked={config.remove_source === true}
                    onChange={(e) => updateConfig({ remove_source: e.target.checked })}
                    className="rounded bg-slate-800 text-brand-500"
                  />
                  <label htmlFor="rem_src" className="text-slate-300 text-[11px]">Remove source file/folder after process</label>
                </div>
              </div>
            )}

            {/* DATA QUALITY CHECK */}
            {(activityType === 'DataQualityCheck' || activityType === 'DataQuality') && (
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-3">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>Data Quality & Integrity Suite</span>
                  <ShieldCheck className="h-3.5 w-3.5 text-purple-400" />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Target Connection (Optional)</label>
                  <select
                    value={config.connection_id || ''}
                    onChange={(e) => updateConfig({ connection_id: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 text-[11px]"
                  >
                    <option value="">None (Local / File Path)</option>
                    {connections.map((c) => (
                      <option key={c.id} value={c.id}>{c.name} ({c.connector_type})</option>
                    ))}
                  </select>
                </div>

                {config.connection_id ? (
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Table Name</label>
                    <input
                      type="text"
                      placeholder="e.g. fact_orders"
                      value={config.table_name || ''}
                      onChange={(e) => updateConfig({ table_name: e.target.value })}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                    />
                  </div>
                ) : (
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="block text-slate-400 text-[11px]">Dataset File Path (CSV / JSON / Parquet)</label>
                      <DynamicContentTrigger
                        fieldName="file_path"
                        value={config.file_path || ''}
                        onApply={(val) => updateConfig({ file_path: val })}
                      />
                    </div>
                    <input
                      type="text"
                      placeholder="/data/warehouse/orders.parquet"
                      value={config.file_path || ''}
                      onChange={(e) => updateConfig({ file_path: e.target.value })}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                    />
                  </div>
                )}

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Min DQ Score (%)</label>
                    <input
                      type="number"
                      min={0}
                      max={100}
                      value={config.min_score_threshold ?? 100}
                      onChange={(e) => updateConfig({ min_score_threshold: parseFloat(e.target.value) || 100 })}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2 py-1 text-slate-200 text-[11px]"
                    />
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="block text-slate-400 text-[11px]">Quarantine Path</label>
                      <DynamicContentTrigger
                        fieldName="quarantine_path"
                        value={config.quarantine_path || ''}
                        onApply={(val) => updateConfig({ quarantine_path: val })}
                      />
                    </div>
                    <input
                      type="text"
                      placeholder="/data/quarantine/bad_rows.csv"
                      value={config.quarantine_path || ''}
                      onChange={(e) => updateConfig({ quarantine_path: e.target.value })}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2 py-1 text-slate-200 font-mono text-[11px]"
                    />
                  </div>
                </div>

                {/* Rules List */}
                <div className="pt-2 border-t border-slate-800">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] font-semibold text-slate-300">
                      Validation Rules ({(config.rules || []).length})
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        const currentRules = config.rules || [];
                        updateConfig({
                          rules: [
                            ...currentRules,
                            {
                              rule_type: 'NotNull',
                              column: '',
                              threshold_percent: 100.0,
                              severity: 'Error'
                            }
                          ]
                        });
                      }}
                      className="text-[10px] px-2 py-0.5 bg-purple-600/30 hover:bg-purple-600/50 text-purple-300 border border-purple-500/40 rounded flex items-center gap-1 transition"
                    >
                      <Plus className="w-3 h-3" /> Add Rule
                    </button>
                  </div>

                  <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                    {(config.rules || []).map((r: any, rIdx: number) => (
                      <div key={rIdx} className="p-2 bg-slate-900/90 border border-slate-800 rounded text-[11px] space-y-1.5">
                        <div className="flex items-center justify-between gap-1">
                          <select
                            value={r.rule_type}
                            onChange={(e) => {
                              const updated = [...(config.rules || [])];
                              updated[rIdx] = { ...updated[rIdx], rule_type: e.target.value };
                              updateConfig({ rules: updated });
                            }}
                            className="bg-slate-950 border border-slate-700 rounded px-1.5 py-0.5 text-indigo-300 text-[10px] font-mono flex-1"
                          >
                            <option value="MandatoryFieldCheck">Mandatory Field Check</option>
                            <option value="NonBlankCheck">Non-Blank Check</option>
                            <option value="NullValidation">Null Validation</option>
                            <option value="DuplicateCheck">Duplicate Check</option>
                            <option value="PrimaryKeyUniqueness">Primary Key Uniqueness</option>
                            <option value="ReferentialIntegrity">Referential Integrity</option>
                            <option value="RangeValidation">Range Validation</option>
                            <option value="DateValidation">Date Validation</option>
                            <option value="ControlledListValidation">Controlled List</option>
                            <option value="SchemaValidation">Schema Validation</option>
                            <option value="SchemaDriftDetection">Schema Drift Detection</option>
                            <option value="RowCountValidation">Row Count Check</option>
                            <option value="PIIDetection">PII Detection</option>
                          </select>
                          <select
                            value={r.severity || 'Error'}
                            onChange={(e) => {
                              const updated = [...(config.rules || [])];
                              updated[rIdx] = { ...updated[rIdx], severity: e.target.value };
                              updateConfig({ rules: updated });
                            }}
                            className="bg-slate-950 border border-slate-700 rounded px-1.5 py-0.5 text-[10px]"
                          >
                            <option value="Error">Error</option>
                            <option value="Warning">Warning</option>
                          </select>
                          <button
                            type="button"
                            onClick={() => {
                              const updated = (config.rules || []).filter((_: any, i: number) => i !== rIdx);
                              updateConfig({ rules: updated });
                            }}
                            className="p-1 text-slate-500 hover:text-rose-400 transition"
                          >
                            <X className="w-3 h-3" />
                          </button>
                        </div>
                        <div className="grid grid-cols-2 gap-1.5">
                          <input
                            type="text"
                            placeholder="Column name"
                            value={r.column || ''}
                            onChange={(e) => {
                              const updated = [...(config.rules || [])];
                              updated[rIdx] = { ...updated[rIdx], column: e.target.value };
                              updateConfig({ rules: updated });
                            }}
                            className="bg-slate-950 border border-slate-700 rounded px-1.5 py-0.5 text-slate-200 text-[10px] font-mono"
                          />
                          <input
                            type="number"
                            min={0}
                            max={100}
                            placeholder="Threshold %"
                            value={r.threshold_percent ?? 100}
                            onChange={(e) => {
                              const updated = [...(config.rules || [])];
                              updated[rIdx] = { ...updated[rIdx], threshold_percent: parseFloat(e.target.value) || 100 };
                              updateConfig({ rules: updated });
                            }}
                            className="bg-slate-950 border border-slate-700 rounded px-1.5 py-0.5 text-slate-200 text-[10px]"
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex items-center gap-2 pt-1">
                  <input
                    type="checkbox"
                    id="fail_dq"
                    checked={config.fail_pipeline_on_error !== false}
                    onChange={(e) => updateConfig({ fail_pipeline_on_error: e.target.checked })}
                    className="rounded bg-slate-800 text-brand-500"
                  />
                  <label htmlFor="fail_dq" className="text-slate-300 text-[11px]">Fail activity if score is below threshold</label>
                </div>
              </div>
            )}

            {/* DATA PROFILING */}
            {activityType === 'DataProfiling' && (
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>Statistical Data Profiler</span>
                  <BarChart3 className="h-3.5 w-3.5 text-cyan-400" />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="block text-slate-400 text-[11px]">Target File / Dataset Path</label>
                    <DynamicContentTrigger
                      fieldName="file_path"
                      value={config.file_path || ''}
                      onApply={(val) => updateConfig({ file_path: val })}
                    />
                  </div>
                  <input
                    type="text"
                    placeholder="/data/incoming/transactions.parquet"
                    value={config.file_path || ''}
                    onChange={(e) => updateConfig({ file_path: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>
                <div className="p-2 bg-slate-900 border border-slate-800 rounded text-[11px] text-slate-400 leading-relaxed">
                  Computes column types, null counts, null distributions, distinct counts, uniqueness percentages, min, max, mean, stddev, and frequent value histograms.
                </div>
              </div>
            )}

            {/* RECONCILIATION */}
            {activityType === 'Reconciliation' && (
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>Source-to-Target Reconciliation</span>
                  <Scale className="h-3.5 w-3.5 text-emerald-400" />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Source Dataset Path</label>
                  <input
                    type="text"
                    placeholder="/data/source/extract.csv"
                    value={config.source_file_path || ''}
                    onChange={(e) => updateConfig({ source_file_path: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Target Dataset Path</label>
                  <input
                    type="text"
                    placeholder="/data/warehouse/loaded.parquet"
                    value={config.target_file_path || ''}
                    onChange={(e) => updateConfig({ target_file_path: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Key Columns (csv)</label>
                    <input
                      type="text"
                      placeholder="id, order_num"
                      value={Array.isArray(config.key_columns) ? config.key_columns.join(', ') : (config.key_columns || '')}
                      onChange={(e) => updateConfig({ key_columns: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2 py-1 text-slate-200 font-mono text-[11px]"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Sum Columns (csv)</label>
                    <input
                      type="text"
                      placeholder="amount, tax"
                      value={Array.isArray(config.numeric_sum_columns) ? config.numeric_sum_columns.join(', ') : (config.numeric_sum_columns || '')}
                      onChange={(e) => updateConfig({ numeric_sum_columns: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded px-2 py-1 text-slate-200 font-mono text-[11px]"
                    />
                  </div>
                </div>

                <div className="flex items-center gap-2 pt-1">
                  <input
                    type="checkbox"
                    id="fail_recon"
                    checked={config.fail_on_discrepancy !== false}
                    onChange={(e) => updateConfig({ fail_on_discrepancy: e.target.checked })}
                    className="rounded bg-slate-800 text-brand-500"
                  />
                  <label htmlFor="fail_recon" className="text-slate-300 text-[11px]">Fail pipeline on reconciliation discrepancy</label>
                </div>
              </div>
            )}

            {/* DATA MASKING */}
            {activityType === 'DataMasking' && (
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
                <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                  <span>Data Masking & Redaction</span>
                  <ShieldAlert className="h-3.5 w-3.5 text-rose-400" />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Source File Path</label>
                  <input
                    type="text"
                    placeholder="/data/raw/customers.csv"
                    value={config.source_file_path || ''}
                    onChange={(e) => updateConfig({ source_file_path: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Masked Output Destination</label>
                  <input
                    type="text"
                    placeholder="/data/sanitized/customers.parquet"
                    value={config.destination_file_path || ''}
                    onChange={(e) => updateConfig({ destination_file_path: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                {/* Masking Rules List */}
                <div className="pt-2 border-t border-slate-800">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] font-semibold text-slate-300">
                      Masking Rules ({(config.masking_rules || []).length})
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        const currentRules = config.masking_rules || [];
                        updateConfig({
                          masking_rules: [
                            ...currentRules,
                            {
                              column: '',
                              strategy: 'redact'
                            }
                          ]
                        });
                      }}
                      className="text-[10px] px-2 py-0.5 bg-rose-600/30 hover:bg-rose-600/50 text-rose-300 border border-rose-500/40 rounded flex items-center gap-1 transition"
                    >
                      <Plus className="w-3 h-3" /> Add Column
                    </button>
                  </div>

                  <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
                    {(config.masking_rules || []).map((mr: any, mIdx: number) => (
                      <div key={mIdx} className="flex items-center gap-1.5 p-1.5 bg-slate-900 border border-slate-800 rounded text-[11px]">
                        <input
                          type="text"
                          placeholder="Column name"
                          value={mr.column || ''}
                          onChange={(e) => {
                            const updated = [...(config.masking_rules || [])];
                            updated[mIdx] = { ...updated[mIdx], column: e.target.value };
                            updateConfig({ masking_rules: updated });
                          }}
                          className="bg-slate-950 border border-slate-700 rounded px-1.5 py-0.5 text-slate-200 text-[10px] font-mono flex-1"
                        />
                        <select
                          value={mr.strategy || 'redact'}
                          onChange={(e) => {
                            const updated = [...(config.masking_rules || [])];
                            updated[mIdx] = { ...updated[mIdx], strategy: e.target.value };
                            updateConfig({ masking_rules: updated });
                          }}
                          className="bg-slate-950 border border-slate-700 rounded px-1.5 py-0.5 text-[10px]"
                        >
                          <option value="redact">Redact ([REDACTED])</option>
                          <option value="hash">SHA-256 Hash</option>
                          <option value="partial_mask">Partial Mask (****1234)</option>
                          <option value="nullify">Nullify (null)</option>
                        </select>
                        <button
                          type="button"
                          onClick={() => {
                            const updated = (config.masking_rules || []).filter((_: any, i: number) => i !== mIdx);
                            updateConfig({ masking_rules: updated });
                          }}
                          className="p-1 text-slate-500 hover:text-rose-400 transition"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </div>
                    ))}
                  </div>
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

            {/* Integration Runtime Override (Feature 1) */}
            <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2">
              <div className="flex items-center justify-between">
                <label className="block text-slate-300 font-semibold text-[11px] uppercase tracking-wider flex items-center gap-1.5">
                  <Cpu className="w-3.5 h-3.5 text-brand-400" />
                  Integration Runtime Override
                </label>
                <span className="text-[10px] text-slate-500 font-mono">
                  {data.runtime_id ? 'Activity Override' : 'Pipeline Default'}
                </span>
              </div>
              <select
                value={data.runtime_id || ''}
                onChange={(e) => onUpdateNode(id, { ...data, runtime_id: e.target.value || null })}
                className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-slate-200"
              >
                <option value="">Default (Inherit Pipeline Runtime)</option>
                {availableRuntimes.map((rt: any) => (
                  <option key={rt.id} value={rt.id}>
                    {rt.name} ({rt.runtime_type} - {rt.status})
                  </option>
                ))}
              </select>
              <p className="text-[10px] text-slate-500">
                Direct this activity to run on a specific private Self-Hosted gateway or Cloud runtime cluster.
              </p>
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

      {/* ADF Expression Builder Modal */}
      {exprModalOpen && exprTarget && (
        <ExpressionBuilderModal
          isOpen={exprModalOpen}
          initialValue={exprTarget.value}
          fieldName={exprTarget.fieldName}
          onClose={() => setExprModalOpen(false)}
          onApply={exprTarget.onApply}
          upstreamActivities={upstreamActivities}
        />
      )}
    </div>
  );
};
