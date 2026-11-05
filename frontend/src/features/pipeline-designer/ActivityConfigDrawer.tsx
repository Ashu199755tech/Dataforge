import React, { useState } from 'react';
import { useAppStore } from '../../store/useAppStore';
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
  Globe 
} from 'lucide-react';

interface ConfigDrawerProps {
  selectedNode: any;
  onUpdateNode: (nodeId: string, updatedData: any) => void;
  onClose: () => void;
}

export const ActivityConfigDrawer: React.FC<ConfigDrawerProps> = ({
  selectedNode,
  onUpdateNode,
  onClose
}) => {
  const { connections } = useAppStore();
  const [sourceTables, setSourceTables] = useState<string[]>([]);
  const [destTables, setDestTables] = useState<string[]>([]);

  if (!selectedNode) return null;

  const { id } = selectedNode;
  const data = selectedNode.data || {};
  const config = data.config || {};
  const activityType = data.activityType || 'CopyData';

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
    <div className="w-96 bg-slate-900 border-l border-slate-800 p-5 space-y-5 overflow-y-auto shrink-0 flex flex-col justify-between">
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Settings2 className="h-4 w-4 text-brand-400" />
            <h3 className="text-sm font-semibold text-white">Activity Settings</h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white">
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* General Info */}
        <div className="space-y-3 text-xs">
          <div>
            <label className="block text-slate-400 mb-1 font-medium">Activity Name</label>
            <input
              type="text"
              value={data.label || ''}
              onChange={(e) => onUpdateNode(id, { ...data, label: e.target.value })}
              className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500 font-medium"
            />
          </div>

          <div>
            <label className="block text-slate-400 mb-1 font-medium">Activity Type</label>
            <div className="px-3 py-1.5 bg-slate-950/80 border border-slate-800 rounded font-mono text-[11px] text-brand-400">
              {activityType}
            </div>
          </div>
        </div>

        {/* ================= COPY DATA ================= */}
        {activityType === 'CopyData' && (
          <div className="space-y-4 pt-2 border-t border-slate-800/80 text-xs">
            <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
              <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                <span>1. Source Connection</span>
                <Database className="h-3.5 w-3.5 text-amber-400" />
              </div>

              <div>
                <label className="block text-slate-400 mb-1 text-[11px]">Source Connection</label>
                <select
                  value={config.source?.connection_id || ''}
                  onChange={(e) => handleSourceConnChange(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 focus:outline-none focus:border-brand-500"
                >
                  <option value="">Select connection...</option>
                  {connections.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({c.connector_type})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-slate-400 mb-1 text-[11px]">Source Table</label>
                <input
                  type="text"
                  placeholder="e.g. source_orders"
                  value={config.source?.table_name || ''}
                  onChange={(e) =>
                    updateConfig({
                      source: { ...(config.source || {}), table_name: e.target.value }
                    })
                  }
                  className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 focus:outline-none focus:border-brand-500"
                />
              </div>

              {/* Watermark Section */}
              <div className="pt-2 border-t border-slate-800/80 space-y-2">
                <div className="text-[11px] font-medium text-slate-400">Incremental Watermark</div>
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="text"
                    placeholder="Column (updated_at)"
                    value={config.source?.incremental?.column || ''}
                    onChange={(e) =>
                      updateConfig({
                        source: {
                          ...(config.source || {}),
                          incremental: {
                            ...(config.source?.incremental || {}),
                            mode: 'watermark',
                            column: e.target.value
                          }
                        }
                      })
                    }
                    className="bg-slate-900 border border-slate-700/80 rounded px-2 py-1 text-slate-200 text-[11px]"
                  />
                  <input
                    type="text"
                    placeholder="Value (@variables('watermark'))"
                    value={config.source?.incremental?.watermark_value || ''}
                    onChange={(e) =>
                      updateConfig({
                        source: {
                          ...(config.source || {}),
                          incremental: {
                            ...(config.source?.incremental || {}),
                            watermark_value: e.target.value
                          }
                        }
                      })
                    }
                    className="bg-slate-900 border border-slate-700/80 rounded px-2 py-1 text-slate-200 text-[11px]"
                  />
                </div>
              </div>
            </div>

            <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
              <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                <span>2. Destination Target</span>
                <Database className="h-3.5 w-3.5 text-blue-400" />
              </div>

              <div>
                <label className="block text-slate-400 mb-1 text-[11px]">Destination Connection</label>
                <select
                  value={config.destination?.connection_id || ''}
                  onChange={(e) => handleDestConnChange(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 focus:outline-none focus:border-brand-500"
                >
                  <option value="">Select connection...</option>
                  {connections.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({c.connector_type})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-slate-400 mb-1 text-[11px]">Target Table</label>
                <input
                  type="text"
                  placeholder="e.g. target_orders"
                  value={config.destination?.table_name || ''}
                  onChange={(e) =>
                    updateConfig({
                      destination: { ...(config.destination || {}), table_name: e.target.value }
                    })
                  }
                  className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 focus:outline-none focus:border-brand-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Write Mode</label>
                  <select
                    value={config.destination?.write_mode || 'append'}
                    onChange={(e) =>
                      updateConfig({
                        destination: { ...(config.destination || {}), write_mode: e.target.value }
                      })
                    }
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
                    onChange={(e) =>
                      updateConfig({
                        destination: {
                          ...(config.destination || {}),
                          key_columns: e.target.value.split(',').map((s) => s.trim()).filter(Boolean)
                        }
                      })
                    }
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2 py-1 text-slate-200 text-[11px]"
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ================= LOOKUP ================= */}
        {activityType === 'Lookup' && (
          <div className="space-y-3 pt-2 border-t border-slate-800 text-xs">
            <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
              <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                <span>Lookup Configuration</span>
                <Search className="h-3.5 w-3.5 text-teal-400" />
              </div>

              <div>
                <label className="block text-slate-400 mb-1 text-[11px]">Connection</label>
                <select
                  value={config.connection_id || ''}
                  onChange={(e) => updateConfig({ connection_id: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 focus:outline-none focus:border-brand-500"
                >
                  <option value="">Select connection...</option>
                  {connections.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-slate-400 mb-1 text-[11px]">Table Name</label>
                <input
                  type="text"
                  placeholder="e.g. source_orders"
                  value={config.table_name || ''}
                  onChange={(e) => updateConfig({ table_name: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1 text-[11px]">Or Custom Query</label>
                <textarea
                  rows={2}
                  placeholder="SELECT MAX(updated_at) as max_date FROM orders"
                  value={config.query || ''}
                  onChange={(e) => updateConfig({ query: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono text-[11px]"
                />
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="first_row"
                  checked={config.first_row_only !== false}
                  onChange={(e) => updateConfig({ first_row_only: e.target.checked })}
                  className="rounded bg-slate-800 border-slate-700 text-brand-500"
                />
                <label htmlFor="first_row" className="text-slate-300 text-[11px]">First Row Only</label>
              </div>
            </div>
          </div>
        )}

        {/* ================= SET VARIABLE ================= */}
        {activityType === 'SetVariable' && (
          <div className="space-y-3 pt-2 border-t border-slate-800 text-xs">
            <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
              <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                <span>Set Variable Configuration</span>
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
                <label className="block text-slate-400 mb-1 text-[11px]">Value / Expression</label>
                <input
                  type="text"
                  placeholder="@activity('Lookup').output.first_row.max_date"
                  value={config.value || ''}
                  onChange={(e) => updateConfig({ value: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono"
                />
              </div>
            </div>
          </div>
        )}

        {/* ================= IF CONDITION ================= */}
        {activityType === 'IfCondition' && (
          <div className="space-y-3 pt-2 border-t border-slate-800 text-xs">
            <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
              <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                <span>Condition Expression</span>
                <GitFork className="h-3.5 w-3.5 text-orange-400" />
              </div>

              <div>
                <label className="block text-slate-400 mb-1 text-[11px]">Boolean Expression</label>
                <input
                  type="text"
                  placeholder="@equals(@parameters('env'), 'production')"
                  value={config.expression || ''}
                  onChange={(e) => updateConfig({ expression: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono"
                />
              </div>
            </div>
          </div>
        )}

        {/* ================= WAIT ================= */}
        {activityType === 'Wait' && (
          <div className="space-y-3 pt-2 border-t border-slate-800 text-xs">
            <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
              <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                <span>Wait Duration</span>
                <Clock className="h-3.5 w-3.5 text-amber-400" />
              </div>

              <div>
                <label className="block text-slate-400 mb-1 text-[11px]">Duration (seconds)</label>
                <input
                  type="number"
                  placeholder="5"
                  value={config.wait_time_in_seconds || 1}
                  onChange={(e) => updateConfig({ wait_time_in_seconds: parseInt(e.target.value) || 1 })}
                  className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-slate-200 font-mono"
                />
              </div>
            </div>
          </div>
        )}

        {/* ================= REST API ================= */}
        {activityType === 'RestApi' && (
          <div className="space-y-3 pt-2 border-t border-slate-800 text-xs">
            <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2.5">
              <div className="flex items-center justify-between text-slate-300 font-semibold text-[11px] uppercase tracking-wider">
                <span>HTTP Request</span>
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
                    placeholder="https://api.example.com/v1/webhook"
                    value={config.url || ''}
                    onChange={(e) => updateConfig({ url: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded px-2 py-1 text-slate-200 font-mono text-[11px]"
                  />
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="pt-3 border-t border-slate-800">
        <button
          onClick={onClose}
          className="w-full py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-xs font-semibold transition"
        >
          Done
        </button>
      </div>
    </div>
  );
};
