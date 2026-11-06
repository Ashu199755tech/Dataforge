import React, { useState } from 'react';
import { Node } from '@xyflow/react';
import { useAppStore } from '../../store/useAppStore';
import api from '../../api/client';
import { 
  X, 
  Settings2, 
  Eye, 
  Trash2, 
  Database, 
  Table, 
  Filter, 
  Sliders, 
  PlusCircle, 
  ArrowDownAZ, 
  Sigma, 
  GitMerge, 
  Key 
} from 'lucide-react';

interface DataFlowConfigDrawerProps {
  selectedNode: Node | null;
  dataflowId: string | null;
  onUpdateNode: (nodeId: string, updatedData: any) => void;
  onDeleteNode: (nodeId: string) => void;
  onClose: () => void;
}

export const DataFlowConfigDrawer: React.FC<DataFlowConfigDrawerProps> = ({
  selectedNode,
  dataflowId,
  onUpdateNode,
  onDeleteNode,
  onClose
}) => {
  const { connections } = useAppStore();
  const [activeTab, setActiveTab] = useState<'config' | 'preview'>('config');
  const [previewData, setPreviewData] = useState<any>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  if (!selectedNode) return null;

  const { id } = selectedNode;
  const data = (selectedNode.data as any) || {};
  const config = data.config || {};
  const opType = data.operatorType || 'Select';

  const updateConfig = (partial: any) => {
    onUpdateNode(id, {
      ...data,
      config: {
        ...config,
        ...partial
      }
    });
  };

  const handleFetchPreview = async () => {
    if (!dataflowId) return;
    setPreviewLoading(true);
    setPreviewError(null);
    try {
      const res = await api.post(`/dataflows/${dataflowId}/preview/${id}`);
      setPreviewData(res.data);
    } catch (err: any) {
      setPreviewError(err.response?.data?.detail || err.message || 'Failed to fetch preview');
    } finally {
      setPreviewLoading(false);
    }
  };

  return (
    <div className="w-96 bg-slate-900 border-l border-slate-800 flex flex-col h-full overflow-hidden select-none z-20 shrink-0">
      {/* Header */}
      <div className="p-3 border-b border-slate-800 flex items-center justify-between">
        <div>
          <div className="text-[10px] font-mono text-slate-500 uppercase tracking-wider font-semibold">
            {opType} Configuration
          </div>
          <div className="text-xs font-bold text-slate-200">
            {data.label || id}
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={() => onDeleteNode(id)}
            className="p-1 rounded hover:bg-rose-500/20 text-slate-500 hover:text-rose-400 transition"
            title="Delete operator"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-slate-800 text-slate-500 hover:text-slate-300 transition"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-800 text-xs font-medium">
        <button
          onClick={() => setActiveTab('config')}
          className={`flex-1 py-2 text-center transition flex items-center justify-center gap-1.5 ${
            activeTab === 'config'
              ? 'text-brand-400 border-b-2 border-brand-500 bg-brand-500/10'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Settings2 className="h-3.5 w-3.5" />
          <span>Settings</span>
        </button>
        <button
          onClick={() => {
            setActiveTab('preview');
            if (!previewData && !previewLoading) handleFetchPreview();
          }}
          className={`flex-1 py-2 text-center transition flex items-center justify-center gap-1.5 ${
            activeTab === 'preview'
              ? 'text-brand-400 border-b-2 border-brand-500 bg-brand-500/10'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Eye className="h-3.5 w-3.5" />
          <span>Data Preview</span>
        </button>
      </div>

      {/* Tab Body */}
      <div className="flex-1 overflow-y-auto p-3 text-xs space-y-3">
        {activeTab === 'config' && (
          <div className="space-y-3">
            {/* Operator Label */}
            <div>
              <label className="block text-slate-400 mb-1 text-[11px]">Display Label</label>
              <input
                type="text"
                value={data.label || ''}
                onChange={(e) => onUpdateNode(id, { ...data, label: e.target.value })}
                className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
              />
            </div>

            {/* SOURCE */}
            {opType === 'Source' && (
              <div className="space-y-2.5">
                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Connection</label>
                  <select
                    value={config.connection_id || ''}
                    onChange={(e) => updateConfig({ connection_id: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-slate-200 text-[11px]"
                  >
                    <option value="">Select connection...</option>
                    {connections.map((c) => (
                      <option key={c.id} value={c.id}>{c.name} ({c.connector_type})</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Table or File Name</label>
                  <input
                    type="text"
                    placeholder="e.g. orders or raw_sales.parquet"
                    value={config.table_name || ''}
                    onChange={(e) => updateConfig({ table_name: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>
              </div>
            )}

            {/* SINK */}
            {opType === 'Sink' && (
              <div className="space-y-2.5">
                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Target Connection</label>
                  <select
                    value={config.connection_id || ''}
                    onChange={(e) => updateConfig({ connection_id: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-slate-200 text-[11px]"
                  >
                    <option value="">Select connection...</option>
                    {connections.map((c) => (
                      <option key={c.id} value={c.id}>{c.name} ({c.connector_type})</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Target Table / Dataset</label>
                  <input
                    type="text"
                    placeholder="e.g. clean_orders or out.parquet"
                    value={config.table_name || ''}
                    onChange={(e) => updateConfig({ table_name: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Write Behavior</label>
                  <select
                    value={config.write_mode || 'append'}
                    onChange={(e) => updateConfig({ write_mode: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-slate-200 text-[11px]"
                  >
                    <option value="append">Append (Insert new records)</option>
                    <option value="overwrite">Overwrite (Truncate / Recreate)</option>
                  </select>
                </div>
              </div>
            )}

            {/* SELECT */}
            {opType === 'Select' && (
              <div className="space-y-2.5">
                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Rename Columns (JSON Map)</label>
                  <input
                    type="text"
                    placeholder='{"cust_id": "customer_id", "amt": "total_amount"}'
                    value={typeof config.rename_columns === 'string' ? config.rename_columns : JSON.stringify(config.rename_columns || {})}
                    onChange={(e) => {
                      try {
                        updateConfig({ rename_columns: JSON.parse(e.target.value) });
                      } catch {
                        updateConfig({ rename_columns: e.target.value });
                      }
                    }}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Drop Columns (Array)</label>
                  <input
                    type="text"
                    placeholder='["temp_col", "raw_flag"]'
                    value={typeof config.drop_columns === 'string' ? config.drop_columns : JSON.stringify(config.drop_columns || [])}
                    onChange={(e) => {
                      try {
                        updateConfig({ drop_columns: JSON.parse(e.target.value) });
                      } catch {
                        updateConfig({ drop_columns: e.target.value });
                      }
                    }}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>
              </div>
            )}

            {/* FILTER */}
            {opType === 'Filter' && (
              <div className="space-y-2.5">
                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Filter Column</label>
                  <input
                    type="text"
                    placeholder="e.g. status or amount"
                    value={config.column || ''}
                    onChange={(e) => updateConfig({ column: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Operator</label>
                    <select
                      value={config.operator || '=='}
                      onChange={(e) => updateConfig({ operator: e.target.value })}
                      className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-200 text-[11px]"
                    >
                      <option value="==">== (Equals)</option>
                      <option value="!=">!= (Not Equals)</option>
                      <option value=">">&gt; (Greater)</option>
                      <option value=">=">&gt;= (Greater or Equal)</option>
                      <option value="<">&lt; (Less)</option>
                      <option value="<=">&lt;= (Less or Equal)</option>
                      <option value="contains">contains (Substr)</option>
                      <option value="is_null">is_null</option>
                      <option value="is_not_null">is_not_null</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Value</label>
                    <input
                      type="text"
                      placeholder="e.g. COMPLETED or 100"
                      value={config.value !== undefined ? String(config.value) : ''}
                      onChange={(e) => {
                        const val = e.target.value;
                        const num = Number(val);
                        updateConfig({ value: isNaN(num) || val === '' ? val : num });
                      }}
                      className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-200 font-mono text-[11px]"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* DERIVED COLUMN */}
            {opType === 'DerivedColumn' && (
              <div className="space-y-2.5">
                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Derived Columns (JSON Array)</label>
                  <textarea
                    rows={6}
                    placeholder={`[
  {"column_name": "full_name", "type": "concat", "inputs": ["first_name", "last_name"], "separator": " "},
  {"column_name": "total", "type": "multiply", "col1": "price", "col2": "quantity"}
]`}
                    value={typeof config.derived_columns === 'string' ? config.derived_columns : JSON.stringify(config.derived_columns || [], null, 2)}
                    onChange={(e) => {
                      try {
                        updateConfig({ derived_columns: JSON.parse(e.target.value) });
                      } catch {
                        updateConfig({ derived_columns: e.target.value });
                      }
                    }}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 font-mono text-[11px]"
                  />
                  <p className="text-[10px] text-slate-500 mt-1">Supported types: concat, multiply, add, uppercase, lowercase, literal.</p>
                </div>
              </div>
            )}

            {/* JOIN */}
            {opType === 'Join' && (
              <div className="space-y-2.5">
                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Join Type</label>
                  <select
                    value={config.join_type || 'inner'}
                    onChange={(e) => updateConfig({ join_type: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-slate-200 text-[11px]"
                  >
                    <option value="inner">Inner Join</option>
                    <option value="left">Left Outer Join</option>
                    <option value="full">Full Outer Join</option>
                    <option value="cross">Cross Join</option>
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Left Stream Key</label>
                    <input
                      type="text"
                      placeholder="e.g. customer_id"
                      value={config.left_on || ''}
                      onChange={(e) => updateConfig({ left_on: e.target.value })}
                      className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1 text-[11px]">Right Stream Key</label>
                    <input
                      type="text"
                      placeholder="e.g. id"
                      value={config.right_on || ''}
                      onChange={(e) => updateConfig({ right_on: e.target.value })}
                      className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* AGGREGATE */}
            {opType === 'Aggregate' && (
              <div className="space-y-2.5">
                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Group By Columns (Array)</label>
                  <input
                    type="text"
                    placeholder='["department", "region"]'
                    value={typeof config.group_by === 'string' ? config.group_by : JSON.stringify(config.group_by || [])}
                    onChange={(e) => {
                      try {
                        updateConfig({ group_by: JSON.parse(e.target.value) });
                      } catch {
                        updateConfig({ group_by: e.target.value });
                      }
                    }}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Aggregates (JSON Array)</label>
                  <textarea
                    rows={4}
                    placeholder={`[
  {"function": "sum", "column": "amount", "alias": "total_revenue"},
  {"function": "count", "column": "id", "alias": "order_count"}
]`}
                    value={typeof config.aggregates === 'string' ? config.aggregates : JSON.stringify(config.aggregates || [], null, 2)}
                    onChange={(e) => {
                      try {
                        updateConfig({ aggregates: JSON.parse(e.target.value) });
                      } catch {
                        updateConfig({ aggregates: e.target.value });
                      }
                    }}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 font-mono text-[11px]"
                  />
                </div>
              </div>
            )}

            {/* SURROGATE KEY */}
            {opType === 'SurrogateKey' && (
              <div className="space-y-2.5">
                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Key Column Name</label>
                  <input
                    type="text"
                    placeholder="surrogate_key"
                    value={config.key_name || 'surrogate_key'}
                    onChange={(e) => updateConfig({ key_name: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Start Value</label>
                  <input
                    type="number"
                    min={1}
                    value={config.start_value || 1}
                    onChange={(e) => updateConfig({ start_value: parseInt(e.target.value) || 1 })}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>
              </div>
            )}

            {/* Pushdown Compatibility Info */}
            <div className="p-2.5 rounded bg-slate-950/70 border border-slate-800 text-[11px] text-slate-400 space-y-1">
              <div className="flex items-center justify-between text-slate-300 font-semibold text-[10px] uppercase tracking-wider">
                <span>Execution Compatibility</span>
                <span className="text-emerald-400 font-mono">Pushdown Ready</span>
              </div>
              <p className="text-[10px] text-slate-500">
                This operator compiles into SQL CTE expressions for in-database zero-egress processing when executed against PostgreSQL, MySQL, DuckDB, or SQLite.
              </p>
            </div>
          </div>
        )}

        {/* PREVIEW TAB */}
        {activeTab === 'preview' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold text-slate-300">Vectorized Transformation Preview</span>
              <button
                onClick={handleFetchPreview}
                disabled={previewLoading}
                className="px-2 py-0.5 rounded bg-brand-600 hover:bg-brand-500 text-white font-medium text-[10px] transition disabled:opacity-50"
              >
                {previewLoading ? 'Evaluating...' : 'Refresh'}
              </button>
            </div>

            {previewError && (
              <div className="p-2 rounded bg-rose-500/10 border border-rose-500/30 text-rose-400 text-[10px]">
                {previewError}
              </div>
            )}

            {previewLoading && (
              <div className="p-8 text-center text-slate-500 text-[11px]">
                Computing streaming operator outputs...
              </div>
            )}

            {previewData && (
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-[10px] text-slate-400 font-mono">
                  <span>Rows: <strong className="text-emerald-400">{previewData.row_count}</strong></span>
                  <span>Cols: <strong className="text-cyan-400">{previewData.columns?.length || 0}</strong></span>
                </div>

                <div className="overflow-x-auto border border-slate-800 rounded max-h-[300px]">
                  <table className="w-full text-[10px] text-left border-collapse">
                    <thead className="bg-slate-950 sticky top-0 border-b border-slate-800">
                      <tr>
                        {previewData.columns?.map((col: string) => (
                          <th key={col} className="px-2 py-1 text-slate-300 font-mono whitespace-nowrap">
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 font-mono">
                      {previewData.preview_rows?.slice(0, 20).map((row: any, i: number) => (
                        <tr key={i} className="hover:bg-slate-800/40">
                          {previewData.columns?.map((col: string) => (
                            <td key={col} className="px-2 py-1 text-slate-400 whitespace-nowrap">
                              {String(row[col] !== undefined ? row[col] : '')}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
